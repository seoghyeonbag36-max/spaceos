import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { caveatKind, CaveatNote } from "@/components/DistrictPicker";
import Verdict, { Fold, type Ground } from "@/components/Verdict";
import { generateProgram, getDistrictEvents, listDistricts, MODE_LABEL, STAGE_LABEL, VALIDATION_MODES } from "@/lib/api";
import type {
  ChannelPlan, DistrictSummary, FounderStage, MarketingEvent, ProgramBriefInput, ProgramPlan,
  ValidationMode, ValidationSignal,
} from "@/lib/api";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import { mapLabelHTML } from "@/design/components/MapMarkerPin";
import { colors } from "@/design/tokens/colors";
import { useMapHost } from "@/components/MapHost";
import { useFitMap, useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import type { ProgramHandoff } from "@/lib/workspaceState";
import type { BusinessGoal } from "@/lib/businessProfile";
import "./ProgramStudio.css";

/**
 * Program 스튜디오 — **검증 program** 생성 화면.
 *
 * ## 2026-09-17 대상 재정의
 *
 * 종전 화면은 **영업 중인 가게**의 리뷰·사진·메뉴를 넣고(상호 검색으로 반자동 채우기까지)
 * 홍보안을 받았다. 지금 대상은 둘이다:
 *
 *   · 예비창업자 — 아직 가게가 없다. 자기 아이템이 통하는 상권을 찾는다.
 *   · 기창업자   — 사업은 하지만 이 상권·이 아이템은 안 해 봤다. 팝업스토어·가오픈·MVP 로 확인한다.
 *
 * 둘 다 그 자리에서 장사한 적이 없어 리뷰가 존재하지 않는다. 그래서 입력은 **검증 브리프**
 * (아이템·검증 방식·가설·기간·예산)이고, 결과는 모객(online)·자리·연계(offline)·
 * **검증 지표(signals)** 세 벌이다. 지표가 이 화면의 결론이다 — 무엇을 세면 통했다고 할지
 * 정하지 않은 검증은 판정이 아니라 지출이다.
 *
 * 사라진 것: 상호 검색(카카오)·블로그 스니펫(네이버)·리뷰/사진/메뉴/키워드 칸·vision 미리보기·
 * 상용 온보딩(점주 제공 원문 동의). 특정할 가게도, 받을 점주 원문도 없다.
 *
 * ## 화면이 한 번에 펴는 양 (2026-09-07 규칙 유지)
 *
 * **결론 1줄 + 근거 3줄.** 나머지는 접는다 — 지우는 것이 아니다. HA 폐기·경고와 스텁 여부는
 * 상세를 접어도 결론 줄에 남긴다. 접힌 자리가 "문제 없음"으로 읽히면 안 된다.
 */

/** 업종 자동완성 후보. 자유 입력이며 이 목록은 힌트일 뿐이다(백엔드는 문자열을 그대로 받는다). */
const CATEGORY_HINTS = [
  "카페", "베이커리", "디저트", "F&B", "주점", "한식", "일식", "양식",
  "의류", "뷰티", "리빙·소품", "공방", "반려동물",
];

interface FormState {
  item: string;
  category: string;
  mode: ValidationMode;
  stage: FounderStage;
  districtId: string;
  address: string;
  hypothesis: string;
  targetCustomer: string;
  startDate: string;
  runDays: string;
  budgetMin: string;
  budgetMax: string;
  differentiatorsText: string;
}

/** 「내 사업」 목적 → 단계. 창업은 예비창업자, 바꾸기·옮기기는 이미 사업을 하는 기창업자다. */
const stageOf = (goal?: BusinessGoal): FounderStage => (goal === "pivot" || goal === "move" ? "founder" : "pre_founder");

const emptyForm = (stage: FounderStage = "pre_founder"): FormState => ({
  item: "", category: "", mode: "popup", stage, districtId: "", address: "",
  hypothesis: "", targetCustomer: "", startDate: "", runDays: "",
  budgetMin: "", budgetMax: "", differentiatorsText: "",
});

/** 데모용 예시 입력. **가상의 아이템**이다 — 실존 브랜드의 계획처럼 읽히지 않게 이름부터 예시임을 밝힌다. */
const SAMPLE: FormState = {
  item: "예시 — 산미 중심 스페셜티 원두 팝업",
  category: "카페",
  mode: "popup",
  stage: "pre_founder",
  districtId: "garosugil",
  address: "",
  hypothesis: "가로수길 20~30대 직장인에게 산미가 강한 싱글오리진이 통한다",
  targetCustomer: "20~30대 직장인",
  startDate: "",
  runDays: "10",
  budgetMin: "300000",
  budgetMax: "800000",
  differentiatorsText: ["주간 단위 원두 교체", "로스팅 당일 추출"].join("\n"),
};

/** 이 화면을 읽는 법 — 접히지만 지우지 않는다 */
const HOW_TO_READ = "아이템과 검증 방식(팝업스토어·가오픈·MVP)을 넣으면, 그 아이템이 이 상권에서 통하는지 "
  + "정해진 기간 안에 판정할 수 있는 program 을 낸다 — 사람을 모으는 온라인안, 자리를 빌리고 상권과 잇는 "
  + "오프라인안, 그리고 무엇을 세면 통했다고 할지 정한 검증 지표. 거점을 고르면 Platform 이 모은 상권 "
  + "수치(업종 분포·검색 트렌드·시간대별 유동/매출·행사)가, Posting 에서 넘어오면 그 공실의 대장 사실이 "
  + "근거로 합류한다. 아직 이 자리에서 장사한 적이 없으므로 단골·기존 고객·쌓인 후기를 전제한 제안은 "
  + "서버가 폐기한다. 이 화면에서 접힌 자리는 한 번 눌러 그대로 편다 — 아무것도 지우지 않았다.";

const linesOf = (t: string) => t.split("\n").map((s) => s.trim()).filter(Boolean);
const toInt = (t: string): number | undefined => {
  const n = Number(t.replace(/[,\s]/g, ""));
  return t.trim() && Number.isInteger(n) && n > 0 ? n : undefined;
};

export default function ProgramStudio({ mapDistrictId, handoff, onArrivalDismiss, defaultCategory, businessGoal }: {
  /** 지도가 비출 상권(App 공유 상권). 폼의 「거점」을 고르지 않았을 때 카메라만 여기로 간다 —
   *  **생성 요청에는 넣지 않는다.** 컨텍스트 결합은 사용자가 폼에서 고른 것만 쓴다. */
  mapDistrictId?: string;
  /** Posting → Program 인계. 거점·업종·주소를 채우고 그 공실을 **검증할 자리**(unit_id)로 싣는다.
   *  App 이 인계마다 key 를 바꿔 새로 마운트하므로 초기값으로만 읽는다. */
  handoff?: ProgramHandoff;
  /** 안내를 걷었을 때 App 에 알린다 — 탭을 다녀와 다시 마운트돼도 걷은 안내가 되살아나지 않게. */
  onArrivalDismiss?: () => void;
  /** 「내 사업」 업종의 입력어. 업종칸의 기본값 — Posting 인계 업종이 있으면 그쪽이 앞선다. */
  defaultCategory?: string;
  /** 「내 사업」 목적. 창업이면 예비창업자, 바꾸기·옮기기면 기창업자가 기본 단계다. */
  businessGoal?: BusinessGoal;
} = {}) {
  const baseStage = stageOf(businessGoal);
  const [form, setForm] = useState<FormState>(() => handoff
    ? { ...emptyForm(baseStage), districtId: handoff.districtId, category: handoff.industry ?? defaultCategory ?? "", address: handoff.unitName }
    : { ...emptyForm(baseStage), category: defaultCategory ?? "" });
  // 「검증할 자리」 안내·지도 핀. 폼을 통째로 갈아엎는 동작(비우기·예시)이나 거점 변경에서 걷는다 —
  // 폼은 다른 상권이 됐는데 안내와 unit_id 만 남으면 엉뚱한 자리를 검증 무대로 싣는다.
  const [arrival, setArrivalState] = useState<ProgramHandoff | null>(handoff ?? null);
  const setArrival = (next: null) => { setArrivalState(next); onArrivalDismiss?.(); };
  const [eventId, setEventId] = useState<string | null>(null);
  const [districts, setDistricts] = useState<DistrictSummary[] | null>(null);
  const [districtErr, setDistrictErr] = useState(false);
  const [result, setResult] = useState<ProgramPlan | null>(null);
  const [resultVersion, setResultVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // 비우기·입력 변경 뒤 늦게 도착한 이전 요청이 초안을 되살리지 않게 한다.
  const generationVersion = useRef(0);
  useEffect(() => () => { generationVersion.current += 1; }, []);

  useEffect(() => {
    // 거점 목록은 상권 컨텍스트 결합용(선택)이라 실패해도 생성 자체는 된다. 다만 **조용히**
    // 비우면 "결합 안 함"만 남은 드롭다운이 정상처럼 보인다 — 실패했음을 화면에 남긴다.
    listDistricts().then(setDistricts).catch(() => { setDistricts([]); setDistrictErr(true); });
  }, []);

  // LLM 실호출은 10~20초가 걸린다. 멈춘 화면처럼 보이지 않게 경과 초를 센다.
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!busy) { if (timer.current) window.clearInterval(timer.current); return; }
    timer.current = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [busy]);

  const differentiators = useMemo(() => linesOf(form.differentiatorsText), [form.differentiatorsText]);
  const budgetMin = toInt(form.budgetMin);
  const budgetMax = toInt(form.budgetMax);
  const runDays = toInt(form.runDays);
  // 예산은 구간이다. 한쪽만 채우면 서버가 422 로 거절한다 — 보내기 전에 여기서 막고 이유를 말한다.
  const halfBudget = (budgetMin === undefined) !== (budgetMax === undefined);
  // 인계된 자리는 **같은 거점일 때만** 싣는다. 거점을 바꿨는데 unit_id 가 남으면 다른 상권의 공실을 인용한다.
  const siteUnitId = arrival && arrival.districtId === form.districtId ? arrival.unitId : undefined;

  const canSubmit = form.item.trim() !== "" && form.category.trim() !== "" && !halfBudget && !busy;

  const hub = (districts ?? []).find((d) => d.id === form.districtId);
  const eventsDistrict = form.districtId || mapDistrictId || null;
  useEffect(() => { setEventId(null); }, [eventsDistrict]);
  const mapEvents = useProgramMap({
    districtId: eventsDistrict, districts: districts ?? [], arrival, eventId, onPickEvent: setEventId,
  });

  function changeField<K extends keyof FormState>(k: K, value: FormState[K]) {
    // 생성 원본의 입력이 바뀌면 이전 응답·초안·근거를 새 브리프에 붙이지 않는다.
    discardResult();
    if (k === "districtId" && arrival && value !== arrival.districtId) setArrival(null);
    setForm((f) => ({ ...f, [k]: value }));
  }

  function discardResult() {
    generationVersion.current += 1;
    setResult(null);
    setBusy(false);
    setError(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    const version = ++generationVersion.current;
    setResultVersion((current) => current + 1);
    setElapsed(0);
    setBusy(true);
    setResult(null);
    setError(null);
    const brief: ProgramBriefInput = {
      item: form.item.trim(),
      category: form.category.trim(),
      mode: form.mode,
      stage: form.stage,
      district_id: form.districtId || undefined,
      unit_id: siteUnitId,
      address: form.address.trim() || undefined,
      hypothesis: form.hypothesis.trim() || undefined,
      target_customer: form.targetCustomer.trim() || undefined,
      start_date: form.startDate || undefined,
      run_days: runDays,
      budget_krw_min: budgetMin,
      budget_krw_max: budgetMax,
      differentiators: differentiators.length ? differentiators : undefined,
      tier: arrival?.strategy ?? undefined,
    };
    try {
      const generated = await generateProgram(brief);
      if (version === generationVersion.current) setResult(generated);
    } catch (err) {
      if (version === generationVersion.current) setError(String(err));
    } finally {
      if (version === generationVersion.current) setBusy(false);
    }
  }

  const head = headline({
    result, busy, elapsed, error, hub, form, siteUnitId,
    filled: {
      hypothesis: form.hypothesis.trim() !== "", target: form.targetCustomer.trim() !== "",
      period: runDays !== undefined || form.startDate !== "", budget: budgetMin !== undefined && budgetMax !== undefined,
      differentiators: differentiators.length,
    },
  });

  return (
    <div className="progstudio"><div className="wrap">
      <Verdict
        eyebrow="PlaceOS · Program" conversion="PROMOTION ▶ PROGRAM"
        question="이 아이템이 이 platform 에서 통하는지, 어떤 검증 program 으로 확인할 것인가"
        verdict={head.verdict} grounds={head.grounds} sources={head.sources}
        note={HOW_TO_READ}
      />

      {/* Posting → Program 인계 안내. 금액은 안내에만 쓰고 생성 요청에는 싣지 않는다 —
          임대료는 Posting 의 추정값이라 브리프의 예산(창업자가 정한 값)과 섞이면 안 된다. */}
      {arrival && (
        <div className="arrival" role="status">
          <b>검증할 자리</b> — {arrival.unitName} · {arrival.area}평 · {arrival.floor} · 월 {arrival.rent.toLocaleString("ko-KR")}만원
          {arrival.strategy && <> · Posting {arrival.strategy} 전략</>}
          <span>아이템과 검증 방식을 넣으면 이 공실에서 돌릴 검증 program 을 만든다. 거점·업종·주소는 Posting 에서 채웠다(바꿀 수 있다).</span>
        </div>
      )}

      {/* 오프라인 연계 후보 — 지도 칩과 **같은 목록**이다. 칩은 키보드로 닿지 않으므로
          여기서 같은 선택을 할 수 있어야 한다. 지도가 없으면 그리지 않는다. */}
      {mapEvents && (
        <OfflinePlaces data={mapEvents} selectedId={eventId}
          onSelect={(e) => { setEventId(e.id); mapEvents.panTo(e.lat, e.lng); }} />
      )}

      <div className="cols">
        {/* ── 입력: 검증 브리프 ── */}
        <form className="panel" onSubmit={submit}>
          <div className="ptitle">
            검증 브리프
            <div className="ptools">
              <Button variant="ghost" type="button" className="ghost" onClick={() => {
                setForm(SAMPLE); setArrival(null); discardResult();
              }}>예시 채우기</Button>
              <Button variant="ghost" type="button" className="ghost" onClick={() => {
                setForm(emptyForm(baseStage)); setArrival(null); discardResult();
              }}>비우기</Button>
            </div>
          </div>

          <Field label="단계" required group>
            <div className="seg" role="radiogroup" aria-label="단계">
              {(["pre_founder", "founder"] as FounderStage[]).map((s) => (
                <button key={s} type="button" role="radio" aria-checked={form.stage === s}
                  className={form.stage === s ? "on" : ""} onClick={() => changeField("stage", s)}>
                  {STAGE_LABEL[s]}
                  <small>{s === "pre_founder" ? "아직 가게가 없다" : "사업 중 · 새 상권·아이템 확인"}</small>
                </button>
              ))}
            </div>
          </Field>

          <Field label="검증 방식" required group
            hint="방식마다 기간 안에 잴 수 있는 것이 다르다 — 팝업은 유입, 가오픈은 객단가·회전, MVP 는 사전 수요. 지표도 이에 맞춰 나온다.">
            <div className="seg seg3" role="radiogroup" aria-label="검증 방식">
              {VALIDATION_MODES.map((m) => (
                <button key={m.key} type="button" role="radio" aria-checked={form.mode === m.key}
                  className={form.mode === m.key ? "on" : ""} onClick={() => changeField("mode", m.key)} title={m.hint}>
                  {m.label}
                </button>
              ))}
            </div>
          </Field>

          <div className="row2">
            <Field label="아이템" required hint="무엇을 팔거나 보여줄지 한 줄. 아직 브랜드명이 없어도 된다.">
              <input value={form.item} onChange={(e) => changeField("item", e.target.value)} placeholder="예: 산미 중심 원두 팝업" />
            </Field>
            <Field label="업종" required>
              <input value={form.category} onChange={(e) => changeField("category", e.target.value)} list="cat-hints" placeholder="예: 카페" />
              <datalist id="cat-hints">
                {CATEGORY_HINTS.map((c) => <option key={c} value={c} />)}
              </datalist>
            </Field>
          </div>

          <Field label="거점(상권 컨텍스트)"
            hint={districtErr
              ? "거점 목록을 불러오지 못했다 — 백엔드 확인 필요. 지금은 컨텍스트 결합 없이만 생성된다."
              : "선택 시 그 거점의 상권 수치(업종 분포·검색 트렌드·시간대별 유동/매출·행사)가 근거로 합류한다. 검증 지표의 목표선도 여기서 나온다."}
            count={districts?.length ? `${districts.length}곳` : undefined}>
            <select value={form.districtId} onChange={(e) => changeField("districtId", e.target.value)} disabled={districts === null}>
              <option value="">{districts === null ? "거점 불러오는 중…" : "— 결합 안 함 —"}</option>
              {(districts ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {caveatKind(d) ? (caveatKind(d) === "mall" ? "▣ " : "▤ ") : ""}{d.name} · {d.gu}
                </option>
              ))}
            </select>
            <CaveatNote district={hub} />
          </Field>

          <Field label="검증 가설"
            hint="이 program 으로 맞는지 확인하려는 한 문장. 기각 조건(지표)이 이 가설을 겨냥해 나온다. 비우면 지표가 일반론이 된다.">
            <textarea rows={2} aria-label="검증 가설" value={form.hypothesis} onChange={(e) => changeField("hypothesis", e.target.value)}
              placeholder="예: 가로수길 20~30대에게 산미 강한 원두가 통한다" />
          </Field>

          {/* 선택 조건 — 넣을수록 근거가 구체적이다. 요약줄이 무엇이 채워졌는지 말하므로 접힌 채로도 빈 칸을 안다. */}
          <Fold title="검증 조건"
            summary={`목표 고객 ${form.targetCustomer.trim() ? "입력됨" : "없음"} · 기간 ${runDays ? `${runDays}일` : "미정"}`
              + ` · 예산 ${budgetMin && budgetMax ? "구간 입력됨" : "없음"} · 차별점 ${differentiators.length}개`}>
            <Field label="목표 고객">
              <input value={form.targetCustomer} onChange={(e) => changeField("targetCustomer", e.target.value)} placeholder="예: 20~30대 직장인" />
            </Field>
            <div className="row2">
              <Field label="시작 예정일">
                <input type="date" aria-label="시작 예정일" value={form.startDate} onChange={(e) => changeField("startDate", e.target.value)} />
              </Field>
              <Field label="검증 기간(일)" hint="오프라인 제안의 시기가 이 안에 들어와야 한다 — 3일짜리 팝업에 '둘째 달부터'는 말이 안 된다.">
                <input inputMode="numeric" aria-label="검증 기간(일)" value={form.runDays} onChange={(e) => changeField("runDays", e.target.value)} placeholder="예: 10" />
              </Field>
            </div>
            <div className="row2">
              <Field label="예산 하한(원)" hint="검증 기간 마케팅 예산의 구간. 생성물은 비율로만 배분하고 절대액은 이 구간에서만 나온다.">
                <input inputMode="numeric" aria-label="예산 하한(원)" value={form.budgetMin} onChange={(e) => changeField("budgetMin", e.target.value)} placeholder="예: 300000" />
              </Field>
              <Field label="예산 상한(원)">
                <input inputMode="numeric" aria-label="예산 상한(원)" value={form.budgetMax} onChange={(e) => changeField("budgetMax", e.target.value)} placeholder="예: 800000" />
              </Field>
            </div>
            {halfBudget && <div className="warn">예산은 하한·상한을 함께 넣거나 둘 다 비운다 — 한쪽만으로는 구간이 아니다.</div>}
            <Field label="차별점" hint="한 줄에 하나. 창업자의 주장이지 확인된 사실이 아니다 — 이게 통하는지가 검증 대상이다."
              count={differentiators.length ? `${differentiators.length}개` : undefined}>
              <textarea rows={3} aria-label="차별점" value={form.differentiatorsText} onChange={(e) => changeField("differentiatorsText", e.target.value)}
                placeholder={"주간 단위 원두 교체\n로스팅 당일 추출"} />
            </Field>
            <Field label="자리 주소">
              <input value={form.address} onChange={(e) => changeField("address", e.target.value)} placeholder="예: 서울 강남구 신사동 …" />
            </Field>
          </Fold>

          <Button type="submit" className="primary" disabled={!canSubmit}>
            {busy ? `생성 중… ${elapsed}초` : "검증 program 생성"}
          </Button>
        </form>

        {/* ── 결과 ── */}
        <Card className="panel">
          {error && (
            <div className="err">
              <strong>생성에 실패했습니다.</strong>
              <div>백엔드가 떠 있는지 확인하세요 — <code>cd apps/backend && uvicorn app.main:app --reload</code></div>
              <div className="errdetail">{error}</div>
            </div>
          )}

          {!error && !result && !busy && (
            <div className="empty">
              {"왼쪽에 아이템과 검증 방식을 넣고 «검증 program 생성»을 누르면 여기에 결과가 나온다. "
                + "처음이라면 «예시 채우기»로 한 번 돌려보면 된다."}
            </div>
          )}

          {busy && <div className="empty">생성 중… {elapsed}초</div>}

          {result && !busy && <Result key={resultVersion} r={result} />}
        </Card>
      </div>
    </div></div>
  );
}

/* ───────────── 지도 ───────────── */

/** 행사 기간 문자열("YYYY-MM-DD~YYYY-MM-DD")을 가른다. 모양이 다르면 null — 그 행사는 거르지 않는다
 *  (날짜를 모르는 것을 종료로 단정하면 있는 행사를 지운다). */
export function eventRange(when: string | null | undefined): { start: string; end: string } | null {
  const m = /^(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})/.exec(when ?? "");
  if (m) return { start: m[1], end: m[2] };
  const one = /^(\d{4}-\d{2}-\d{2})/.exec(when ?? "");
  return one ? { start: one[1], end: one[1] } : null;
}

/** 종료일이 오늘보다 앞선 행사를 뺀다(화면설계서 PR-01). 끝난 행사를 "연계할 곳"으로 보여주면 거짓 안내가 된다.
 *  `today` 는 로컬 날짜 "YYYY-MM-DD". 남은 것은 시작일 순. */
export function splitEvents(events: MarketingEvent[], today: string): { upcoming: MarketingEvent[]; ended: number } {
  const upcoming: MarketingEvent[] = [];
  let ended = 0;
  for (const e of events) {
    const r = eventRange(e.when);
    if (r && r.end < today) ended += 1; else upcoming.push(e);
  }
  upcoming.sort((a, b) => (eventRange(a.when)?.start ?? "9999").localeCompare(eventRange(b.when)?.start ?? "9999"));
  return { upcoming, ended };
}

const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** 칩·목록에 쓰는 짧은 기간 — "09-20~09-27" 또는 "10-02". */
function shortRange(when: string): string {
  const r = eventRange(when);
  if (!r) return when;
  return r.start === r.end ? r.start.slice(5) : `${r.start.slice(5)}~${r.end.slice(5)}`;
}

interface ProgramMapData {
  events: MarketingEvent[];
  ended: number;
  source: string;
  panTo: (lat: number, lng: number) => void;
}

/**
 * Program 이 지도에 그리는 것 — "어디서 검증을 돌리고 무엇과 잇나".
 *
 *   ① **오프라인 연계 후보** — 상권의 공공 문화행사. **LLM 을 부르지 않는 경로**
 *      (`/marketing/events`)로만 받는다. 시드 폴백은 점선, 종료된 행사는 뺀다.
 *   ② **검증할 자리** — Posting 에서 넘어온 공실(Posting 트랙 색).
 *
 * 종전의 가게 후보 칩·「이 가게」 핀은 사라졌다 — 특정할 영업 중인 가게가 없다(2026-09-17).
 * 지도가 없으면(단독 렌더·테스트) 행사 요청도 보내지 않고 null 을 돌려준다.
 */
function useProgramMap({ districtId, districts, arrival, eventId, onPickEvent }: {
  districtId: string | null; districts: DistrictSummary[];
  arrival: ProgramHandoff | null; eventId: string | null;
  onPickEvent: (id: string) => void;
}): ProgramMapData | null {
  const { map, ready } = useMapHost();
  const [ev, setEv] = useState<{ id: string; events: MarketingEvent[]; source: string } | null>(null);

  useEffect(() => {
    if (!ready || !map || !districtId) return;
    let live = true;
    getDistrictEvents(districtId)
      .then((r) => { if (live) setEv({ id: districtId, events: r.events, source: r.events_source ?? "seed" }); })
      .catch(() => { if (live) setEv({ id: districtId, events: [], source: "unavailable" }); });
    return () => { live = false; };
  }, [ready, map, districtId]);
  const current = ev && ev.id === districtId ? ev : null;
  const split = useMemo(() => splitEvents(current?.events ?? [], localToday()), [current]);

  const markers = useMemo<MapMarkerItem[]>(() => {
    const out: MapMarkerItem[] = [];
    const seed = current?.source !== "seoul-open-data";
    for (const e of split.upcoming) {
      const on = e.id === eventId;
      out.push({
        id: `event-${e.id}`, lat: e.lat, lng: e.lng, zIndex: on ? 220 : 60,
        html: mapLabelHTML({
          text: e.n.length > 14 ? `${e.n.slice(0, 13)}…` : e.n,
          sub: seed ? "예시" : shortRange(e.when),
          color: colors.track.program.base, dashed: seed, active: on,
        }),
      });
    }
    if (arrival) {
      out.push({
        id: "arrival", lat: arrival.lat, lng: arrival.lng, zIndex: 240,
        html: mapLabelHTML({ text: "검증할 자리", sub: `${arrival.area}평 · ${arrival.floor}`, color: colors.track.posting.base, active: true }),
      });
    }
    return out;
  }, [current, split, eventId, arrival]);

  useMapMarkers(markers, (id) => {
    if (id.startsWith("event-")) onPickEvent(id.slice("event-".length));
  });

  // 카메라: 검증할 자리 → 상권 중심 순. 키가 바뀔 때만 움직인다.
  const hubCenter = districts.find((d) => d.id === districtId)?.center;
  const single = arrival ? { lat: arrival.lat, lng: arrival.lng } : null;
  const fitKey = single ? `one:${single.lat},${single.lng}` : districtId ? `hub:${districtId}` : null;
  useFitMap(fitKey, single ? [single] : [], hubCenter ? { lat: hubCenter[0], lng: hubCenter[1] } : null);

  if (!ready || !map || !current) return null;
  return {
    events: split.upcoming, ended: split.ended, source: current.source,
    panTo: (lat, lng) => {
      const naver = (window as any).naver;
      if (naver?.maps) map.panTo?.(new naver.maps.LatLng(lat, lng));
    },
  };
}

/** 오프라인 연계 후보 목록 + 고른 행사 상세. 지도 칩과 같은 목록·같은 선택이다. */
function OfflinePlaces({ data, selectedId, onSelect }: {
  data: ProgramMapData; selectedId: string | null; onSelect: (e: MarketingEvent) => void;
}) {
  const { events, ended, source } = data;
  const selected = events.find((e) => e.id === selectedId) ?? null;
  const seed = source !== "seoul-open-data";
  return (
    <section className="offline-places" aria-label="오프라인 연계 후보">
      <div className="op-head">
        <b>오프라인 연계 후보 · {events.length}곳</b>
        {ended > 0 && <span>종료된 행사 {ended}곳은 뺐다</span>}
      </div>
      <p className="op-src" role="status">
        {source === "unavailable" ? "행사 목록을 불러오지 못했다"
          : source === "seed" ? "행사 실데이터 미적재 — 점선 칩은 예시다"
          : events.length === 0 ? "이 상권에 예정된 공공 문화행사가 없다 — 예시로 채우지 않는다."
          : "서울열린데이터광장 공공 문화행사 · 검증 기간과 겹치면 유입을 붙일 수 있다 · 지도 칩과 같은 목록"}
      </p>
      {events.length > 0 && (
        <ul className="op-list">
          {events.map((e) => (
            <li key={e.id}>
              <button type="button" aria-pressed={e.id === selectedId} onClick={() => onSelect(e)}>
                <span className="op-name">{e.n}{seed && <i> · 예시</i>}</span>
                <span className="op-meta">{shortRange(e.when)}{e.place ? ` · ${e.place}` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <dl className="op-detail" aria-label={`${selected.n} 상세`}>
          <div><dt>일정</dt><dd>{selected.when || "미제공"}</dd></div>
          <div><dt>장소</dt><dd>{selected.place || "미제공"}</dd></div>
          <div><dt>주최</dt><dd>{selected.org || "미제공"}</dd></div>
          <div><dt>요금</dt><dd>{selected.fee || "미제공"}</dd></div>
          <div><dt>대상</dt><dd>{selected.target || "미제공"}</dd></div>
          {selected.link && /^https?:\/\//.test(selected.link) && (
            <a href={selected.link} target="_blank" rel="noopener noreferrer">행사 페이지 열기 ↗</a>
          )}
        </dl>
      )}
    </section>
  );
}

/* ───────────── 결론 1줄 + 근거 3줄 ───────────── */

/**
 * 이 화면이 답한 것과 그 답을 세운 값.
 *
 * 근거 세 줄은 검증의 세 질문이다 — **무엇을 확인하나 / 어떻게 모으나 / 무엇으로 판정하나**.
 * 결과가 없을 때도 세 줄을 그대로 내고, 값이 "아직 무엇이 들어와 있나"로 바뀐다.
 * HA 폐기·경고와 스텁 여부는 상세를 접어도 이 결론 줄에 남긴다.
 */
function headline({ result, busy, elapsed, error, hub, form, siteUnitId, filled }: {
  result: ProgramPlan | null; busy: boolean; elapsed: number; error: string | null;
  hub?: DistrictSummary; form: FormState; siteUnitId?: string;
  filled: { hypothesis: boolean; target: boolean; period: boolean; budget: boolean; differentiators: number };
}): { verdict: ReactNode; grounds: Ground[]; sources: ReactNode[] } {
  const stub = result ? result.source !== "llm" : false;
  const findings = result?.ha_findings ?? [];
  const blocked = findings.filter((f) => f.severity === "violation");
  const warnings = findings.filter((f) => f.severity !== "violation");
  const modeLabel = MODE_LABEL[result?.mode ?? form.mode] ?? form.mode;
  const ctx = hub ? `${hub.name}(${hub.gu}) 상권 수치 결합` : "상권 결합 안 함";

  /* ── 결론 한 문장 ── */
  let verdict: ReactNode;
  if (error) {
    verdict = <span className="value-absent">생성에 실패해 돌릴 검증 program 이 없다 — 아래 오류를 확인한다.</span>;
  } else if (busy) {
    verdict = `생성 중이다 — ${elapsed}초 경과.`;
  } else if (!result) {
    verdict = `아직 돌릴 검증 program 이 없다 — 아이템과 검증 방식을 넣으면 모객·자리·판정 세 벌을 근거와 함께 낸다`
      + ` (현재 ${STAGE_LABEL[form.stage]} · ${modeLabel}).`;
  } else {
    const lead = `${result.item}(${result.category}) — ${modeLabel}로 확인한다: `
      + `온라인 ${result.online.length}건 · 오프라인 ${result.offline.length}건 · 검증 지표 ${result.signals.length}건`
      + `${result.signals[0] ? `, 첫 판정선은 「${result.signals[0].name}」` : ""}.`;
    verdict = stub
      ? <>{lead} <span className="value-absent">{blocked.length > 0
        ? `단 LLM 생성물이 HA 검증에 걸려 폐기됐고(${blocked.length}건), 아래는 규칙 기반 스텁이다.`
        : "단 LLM 을 타지 못해 아래는 규칙 기반 스텁이다."}</span></>
      : lead;
  }

  /* ── 근거 3줄 ── */
  const briefParts = [
    `가설 ${filled.hypothesis ? "있음" : "없음"}`,
    `목표 고객 ${filled.target ? "있음" : "없음"}`,
    `기간 ${filled.period ? "있음" : "미정"}`,
    `예산 구간 ${filled.budget ? "있음" : "없음"}`,
    `차별점 ${filled.differentiators}개`,
    `검증할 자리 ${siteUnitId ? "지정" : "미지정"}`,
  ];

  const haVerdict = blocked.length > 0
    ? <span className="tr-up">HA 폐기 {blocked.length}건</span>
    : warnings.length > 0
      ? <span className="tr-flat">HA 경고 {warnings.length}건 (사전 매칭이라 오탐 가능)</span>
      : "HA 서버 검증 통과";

  const grounds: Ground[] = [
    {
      label: "무엇을 확인하나",
      value: filled.hypothesis
        ? `${STAGE_LABEL[form.stage]} · ${modeLabel} · ${briefParts.join(" · ")}`
        : <>{STAGE_LABEL[form.stage]} · {modeLabel} · {briefParts.join(" · ")} · <span className="value-absent">가설이 없어 판정선이 일반론이 된다</span></>,
      source: "검증 브리프 — 창업자가 넣은 계획과 주장(검증된 사실 아님) · " + ctx,
    },
    {
      label: "어떻게 모으나",
      value: result
        ? `온라인 ${result.online.map((x) => x.channel).join(" / ") || "—"}`
          + ` · 오프라인 ${result.offline.map((x) => x.channel).join(" / ") || "—"}`
        : <span className="value-absent">아직 생성하지 않았다</span>,
      source: "POST /api/v1/marketing/generate · 온라인은 창업자 단독, 오프라인은 건물주·상인회 등과 함께",
    },
    {
      label: "무엇으로 판정하나",
      value: result
        ? <>{result.signals.map((s) => `${s.name}(${s.target})`).join(" · ") || <span className="value-absent">지표 없음</span>}
          {" · "}생성 원본: {stub ? "규칙 기반 폴백" : "LLM 생성"} · {haVerdict}</>
        : <span className="value-absent">아직 생성하지 않았다</span>,
      source: "서버 후처리 ha_guard — 금액·트렌드 방향·미검증 경험·지표 형식을 따로 검증한다"
        + " (LLM 자체점검 문장과 섞지 않는다). 생성 후 편집한 초안은 이 검증에 포함되지 않는다.",
    },
  ];

  /* ── 출처 — 아래가 전부 접혀도 남는다 ── */
  const sources: ReactNode[] = ["POST /api/v1/marketing/generate", "검증 브리프(창업자 입력)"];
  if (hub) sources.push(`Gold 상권 컨텍스트 · ${hub.name}(${hub.gu})`);
  if (siteUnitId) sources.push("gold/vacant_units(검증할 자리 · 건축물대장)");
  sources.push("HA 서버 검증 ha_guard");
  return { verdict, grounds, sources };
}

/* ───────────── 결과 ───────────── */

function Result({ r }: { r: ProgramPlan }) {
  const stub = r.source !== "llm";
  const findings = r.ha_findings ?? [];
  // 폐기(violation)와 경고(warning)는 성격이 다르다 — 전자는 이 응답이 스텁인 **이유**이고,
  // 후자는 살아 있는 생성물에 붙은 주석이다. 섞어 보여주면 둘 다 안 읽힌다.
  const blocked = findings.filter((f) => f.severity === "violation");
  const warnings = findings.filter((f) => f.severity !== "violation");
  return (
    <div className="result">
      <div className="rhead">
        <div>
          <div className="rname">{r.item}</div>
          <div className="rcat">{r.category} · {MODE_LABEL[r.mode] ?? r.mode} · {STAGE_LABEL[r.stage] ?? r.stage}</div>
        </div>
        <span className={`srcbadge ${stub ? "is-syn" : "is-gold"}`}
          title={stub
            ? "LLM_API_KEY 미설정이거나 호출이 실패해 규칙 기반 스텁으로 응답했다"
            : "Claude 실호출로 생성된 결과다"}>
          {stub ? "규칙 기반 폴백" : "LLM 생성"}
        </span>
      </div>

      {/* 판정표를 초안보다 **먼저** 둔다 — 무엇으로 판정할지가 이 결과의 결론이고,
          채널 초안은 그 판정에 쓸 표본을 모으는 수단이다. */}
      <SignalTable signals={r.signals} />

      <DraftWorkspace online={r.online} offline={r.offline} />

      {/* 검증의 **결과**는 위 결론 줄이 이미 말했다. 여기 접힌 것은 그 사유와 원문이다. */}
      <Fold title="생성 원본의 Humanistic Authority 검증"
        badge={blocked.length ? `폐기 ${blocked.length}` : warnings.length ? `경고 ${warnings.length}` : "통과"}
        summary={<>편집 초안은 검증 대상 아님 · LLM 자체점검 문장</>}>

        {/* 스텁이 나온 이유가 둘이다. 크레딧·키 문제와 "생성은 됐는데 검증에 걸렸다"를
            같은 문구로 보여주면 엉뚱한 데를 고치게 된다. */}
        {stub && blocked.length > 0 && (
          <div className="warn">
            LLM 이 생성한 결과가 <b>Humanistic Authority 검증에 걸려 폐기</b>됐다 — 위 카드는 그
            대신 나온 규칙 기반 스텁이다. 키·크레딧 문제가 아니다.
            <ul className="halist">
              {blocked.map((f, i) => (
                <li key={i}>
                  <b>{f.message}</b>
                  {f.evidence && <> <code>{f.evidence}</code></>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {stub && blocked.length === 0 && (
          <div className="warn">
            LLM 을 타지 못해 <b>규칙 기반 스텁</b>이 나왔다 — 브리프·상권 수치를 읽고 쓴 결과가 아니다.
            <code>LLM_API_KEY</code>(로컬은 <code>apps/backend/.env</code>, 배포는 Cloud Run 환경변수),
            Anthropic 크레딧 잔액, 백엔드 로그를 확인하라.
          </div>
        )}

        {/* 경고는 사전 매칭이라 오탐이 섞인다. 지우지 않고 근거를 함께 보여 사람이 판단하게 한다. */}
        {!stub && warnings.length > 0 && (
          <div className="hawarn">
            <b>HA 검증 경고 {warnings.length}건</b> — 위 생성물은 살아 있다. 사전 매칭이라
            오탐일 수 있으니 근거를 보고 판단하라.
            <ul className="halist">
              {warnings.map((f, i) => (
                <li key={i}>
                  {f.message}
                  {f.evidence && <> <code>{f.evidence}</code></>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 자기신고와 서버 검증을 나란히 두되 섞지 않는다 — 아래 문장은 LLM 이 스스로
            적은 것이고, 그게 사실인지는 서버(ha_guard)가 따로 판정한다. */}
        <div className="rlabel">Humanistic Authority 자체점검 <em>LLM 이 적은 문장이다</em></div>
        <div className="ha">{r.ha_check}</div>
        {!stub && warnings.length === 0 && (
          <div className="note">서버 후처리 검증(금액·트렌드 방향·미검증 경험·지표 형식·채널 균형) 통과.</div>
        )}
      </Fold>
    </div>
  );
}

/** 검증 지표 — 이 결과의 결론. 목표선과 **기각 조건**을 나란히 둔다: 기각 조건이 없는 지표는
 *  결과를 보고 사후에 말을 맞추게 되므로, 비어 있으면 비어 있다고 적는다. */
function SignalTable({ signals }: { signals: ValidationSignal[] }) {
  return (
    <section className="signals" aria-label="검증 지표">
      <h2>검증 지표 <span>{signals.length}건 · 시작 전에 정한 판정선</span></h2>
      {signals.length === 0 ? (
        <p className="value-absent">검증 지표가 없다 — 무엇을 세면 통했다고 할지 정하지 않은 검증은 판정이 아니라 지출이다.</p>
      ) : (
        <div className="sig-scroll">
          <table>
            <thead><tr><th>지표</th><th>측정 방법</th><th>목표선</th><th>기각 조건</th></tr></thead>
            <tbody>
              {signals.map((s, i) => (
                <tr key={i}>
                  <th scope="row">{s.name}</th>
                  <td>{s.method}</td>
                  <td className="sig-target">{s.target}</td>
                  <td>{s.decision || <span className="value-absent">비어 있음</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** 채널 한 건의 부가 속성 한 줄 — 온라인은 타겟·예산비율·KPI, 오프라인은 시기·협업 주체. */
function planMeta(p: ChannelPlan): string {
  const bits = p.kind === "online"
    ? [p.target && `타겟 ${p.target}`, p.budget_share != null && `예산 ${p.budget_share}%`, p.kpi && `KPI ${p.kpi}`]
    : [p.timing && `시기 ${p.timing}`, p.actors?.length ? `함께 ${p.actors.join("·")}` : null];
  return bits.filter(Boolean).join(" · ");
}

/** 본문 편집은 현재 화면의 메모리에서만 한다. 서버 원본·근거·출처는 덮어쓰지 않는다. */
function DraftWorkspace({ online, offline }: { online: ChannelPlan[]; offline: ChannelPlan[] }) {
  const plans = [...online, ...offline];
  const [contents, setContents] = useState(() => plans.map((p) => p.content));
  const [selected, setSelected] = useState(0);
  const [preview, setPreview] = useState(false);
  const [copyStatus, setCopyStatus] = useState<"idle" | "copying" | "copied" | "failed">("idle");
  const copyVersion = useRef(0);
  const plan = plans[selected];
  const content = contents[selected] ?? "";
  const edited = plan ? content !== plan.content : false;
  const editedCount = plans.filter((p, i) => contents[i] !== p.content).length;

  function clearCopyStatus() {
    copyVersion.current += 1;
    setCopyStatus("idle");
  }

  function updateContent(next: string) {
    setContents((current) => current.map((value, i) => i === selected ? next : value));
    clearCopyStatus();
  }

  async function copyContent() {
    const version = ++copyVersion.current;
    setCopyStatus("copying");
    try {
      await navigator.clipboard.writeText(content);
      if (version === copyVersion.current) setCopyStatus("copied");
    } catch {
      if (version === copyVersion.current) setCopyStatus("failed");
    }
  }

  if (!plan) return <div className="empty">생성된 채널안이 없습니다. 입력 근거를 확인해 다시 생성하세요.</div>;

  const meta = planMeta(plan);
  return (
    <section className="draft-workspace" aria-label="채널별 실행 초안">
      <div className="draft-intro">
        <h2>채널별 실행 초안 다듬기</h2>
        <p>채널 선택 → 본문 편집 → 미리보기 · 수정한 채널 {editedCount}개</p>
        <p>초안은 이 화면에서만 유지됩니다. 다시 생성하거나 브리프를 바꾸면 사라집니다.</p>
      </div>
      <div className="draft-layout">
        <div className="draft-channels" role="group" aria-label="초안 채널 선택">
          {([
            { label: "온라인 · 모객", items: online, offset: 0 },
            { label: "오프라인 · 자리·연계", items: offline, offset: online.length },
          ]).map((group) => (
            <div key={group.label} className="draft-channel-group">
              <h3>{group.label} <span>{group.items.length}건</span></h3>
              {group.items.length === 0 && <p className="draft-none">생성된 채널 없음</p>}
              {group.items.map((p, i) => {
                const index = group.offset + i;
                const changed = contents[index] !== p.content;
                return (
                  <button key={index} type="button" className="draft-channel"
                    aria-pressed={selected === index} onClick={() => {
                      setSelected(index); clearCopyStatus();
                    }}>
                    <span>{p.channel}</span>
                    <span className={`draft-state${changed ? " is-edited" : ""}`}>{changed ? "편집됨" : "초안"}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="draft-detail">
          <div className="draft-toolbar">
            <h3>{plan.channel}</h3>
            <div className="draft-view" role="group" aria-label="초안 보기 방식">
              <button type="button" aria-pressed={!preview} onClick={() => setPreview(false)}>편집</button>
              <button type="button" aria-pressed={preview} onClick={() => setPreview(true)}>미리보기</button>
            </div>
          </div>
          {meta && <p className="draft-meta">{meta}</p>}
          <p className="draft-validation" id="draft-validation" role="status">
            {edited
              ? "편집됨 · 생성 후 사용자가 수정한 초안입니다. 수정한 본문은 서버 HA 검증을 거치지 않았습니다."
              : "초안 · 생성 원본입니다. 출처와 HA 검증 결과는 아래에서 확인하세요."}
          </p>
          {preview ? (
            <div className="draft-preview" role="region" aria-label={`${plan.channel} 본문 미리보기`}>
              <div className="draft-preview-label">본문 미리보기 · 실제 채널 화면과 다를 수 있습니다</div>
              <div className="draft-preview-content">{content || "본문이 비어 있습니다. 편집에서 내용을 입력하세요."}</div>
            </div>
          ) : (
            <label className="draft-editor">
              <span>초안 본문</span>
              <textarea rows={10} value={content} onChange={(e) => updateContent(e.target.value)}
                aria-describedby="draft-validation" />
            </label>
          )}
          <div className="draft-actions">
            <Button type="button" variant="ghost" disabled={!edited}
              onClick={() => updateContent(plan.content)}>원본 되돌리기</Button>
            <Button type="button" disabled={!content.trim() || copyStatus === "copying"}
              onClick={copyContent}>{copyStatus === "copying" ? "복사 중…" : "본문 복사"}</Button>
          </div>
          {copyStatus === "copied" && <p className="draft-feedback" role="status">현재 초안 본문을 복사했습니다.</p>}
          {copyStatus === "failed" && (
            <p className="draft-feedback" role="alert">복사하지 못했습니다. 편집 화면에서 본문을 선택해 직접 복사하세요.</p>
          )}
          <div className="prationale"><b>생성 원본의 근거</b> {plan.rationale}</div>
          {edited && <p className="draft-scope">위 근거와 아래 HA 결과는 생성 원본에 관한 내용입니다. 수정한 본문을 뒷받침하는지 직접 확인하세요.</p>}
        </div>
      </div>
    </section>
  );
}

/* ───────────── 조각 ───────────── */

function Field({ label, required, hint, count, group, children }: {
  label: string; required?: boolean; hint?: string; count?: string;
  /** 버튼 묶음(라디오 그룹)이면 `<label>` 로 감싸지 않는다. `<label>` 은 첫 버튼을 라벨 대상으로
   *  삼아, 라벨 글자를 누르면 첫 선택지가 눌리고 그 버튼의 접근성 이름도 라벨로 덮인다. */
  group?: boolean;
  children: React.ReactNode;
}) {
  const head = (
    <span className="flabel">
      {label}{required && <i>*</i>}
      {count && <em>{count}</em>}
    </span>
  );
  return (
    <div className="field">
      {group ? <div>{head}{children}</div> : <label>{head}{children}</label>}
      {/* 힌트는 접는다 — 칸마다 설명이 동시에 펴져 있으면 정작 입력칸이 안 보인다.
          `<label>` 밖에 두어야 요약줄 클릭이 라벨 활성화로 새지 않는다. */}
      {hint && <details className="fhint"><summary>입력 규칙</summary><div>{hint}</div></details>}
    </div>
  );
}
