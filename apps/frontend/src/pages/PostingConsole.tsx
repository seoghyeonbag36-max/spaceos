import { useEffect, useMemo, useRef, useState } from "react";
import type { BuildingSelection, ProgramHandoff } from "@/lib/workspaceState";
import DistrictPicker, { CaveatNote } from "@/components/DistrictPicker";
import {
  BASIS_LABEL, getPostings, listDistricts, recommendIndustry, simulateRevenue,
} from "@/lib/api";
import type {
  DistrictSummary, IndustryRec, Posting, SimulateResult, TierScenario,
} from "@/lib/api";
import { Button } from "@/design/components/Button";
import { Card } from "@/design/components/Card";
import { mapLabelHTML, shortManwon } from "@/design/components/MapMarkerPin";
import { colors } from "@/design/tokens/colors";
import Verdict, { type Ground } from "@/components/Verdict";
import { useFitMap, useMapMarkers, type MapMarkerItem } from "@/components/useMapMarkers";
import "./PostingConsole.css";

/**
 * Posting 콘솔 — "이 자리에 들어가면 얼마가 남나"에 답하는 화면.
 *
 * 백엔드 `POST /ai/simulate-revenue`(services/posting)는 2026-07-18 부터 있었지만
 * **이걸 부르는 화면이 없었다** — `simulateRevenue()` 는 api.ts 에 정의만 되어 있고
 * 호출부가 0건이었다. ProgramStudio 가 `/marketing/generate` 에 표면을 준 것과 같은
 * 자리다(2026-08-29).
 *
 * 이 화면이 여는 것 둘:
 *   ① **권리금(prem) 입력 계약** — 공개 통계가 없고 임대인·기존 임차인과의 협상값이라
 *      그 자리에 들어갈 기업만 안다. 입력란이 없어 지금까지 늘 `absent`(0 전제)로만
 *      계산돼 왔다. 계약은 입력란이 있어야 성립한다.
 *   ② **외부 AI 창업 코파일럿 어댑터** — `POSTING_COPILOT_URL` 이 채워지면 같은 화면이
 *      코파일럿 결과를 그린다. `source`/`source_note` 가 어느 쪽이 돌았는지 밝힌다.
 *
 * 화면 원칙:
 *   · 비용 기준(`basis`)과 입력 출처(`inputs_source`)를 결과 옆에 같이 싣는다 —
 *     실측 임대료와 시드 프록시가 같은 숫자처럼 보이면 안 된다.
 *   · `viable === false` 는 "모른다"가 아니라 "회수가 안 된다"다. 셋 다 안 되면
 *     `unviable_note` 를 그대로 보여주고 추천을 만들지 않는다.
 */

const DEFAULT_DISTRICT = "garosugil";

const TIER_LABEL: Record<string, { name: string; sub: string }> = {
  premium: { name: "고급화", sub: "객단가 높이고 회전 낮게" },
  value: { name: "가성비", sub: "객단가 낮추고 회전 높게" },
  factory: { name: "기능중심", sub: "면적·인력 최소로" },
};

const won = (v: number) => `${Math.round(v).toLocaleString()}만원`;

interface PostingConsoleProps {
  selection?: BuildingSelection & { requestId: number };
  /** 네 트랙이 공유하는 상권(App). 주면 제어 모드 — 상권을 바꾸면 `onDistrictChange` 로 올린다.
   *  안 주면 종전대로 화면이 스스로 상권을 든다(단독 렌더·테스트). */
  districtId?: string;
  onDistrictChange?: (id: string) => void;
  /** Posting → Program 인계(화면설계서 2판). 주면 결과 아래 「이 자리로 홍보 program 만들기 →」가 뜬다. */
  onMakeProgram?: (handoff: ProgramHandoff) => void;
}
interface Calculation {
  result: SimulateResult;
  input: { district_id: string; unit_id: string; industry_type?: string; strategy?: string; prem?: number };
}

export default function PostingConsole({ selection, districtId, onDistrictChange, onMakeProgram }: PostingConsoleProps = {}) {
  return <PostingSession key={selection ? `${selection.districtId}:${selection.buildingId}:${selection.requestId}` : "direct"}
    selection={selection} districtId={districtId} onDistrictChange={onDistrictChange} onMakeProgram={onMakeProgram} />;
}

function PostingSession({ selection, districtId: sharedDistrict, onDistrictChange, onMakeProgram }: PostingConsoleProps) {
  const [districts, setDistricts] = useState<DistrictSummary[]>([]);
  const [ownDistrict, setOwnDistrict] = useState(selection?.districtId ?? sharedDistrict ?? DEFAULT_DISTRICT);
  const controlled = sharedDistrict !== undefined && onDistrictChange !== undefined;
  const districtId = controlled ? sharedDistrict : ownDistrict;
  const setDistrictId = (id: string) => (controlled ? onDistrictChange(id) : setOwnDistrict(id));
  const [units, setUnits] = useState<Posting[]>([]);
  // 자리 목록이 **도착한** 상권. 0곳과 불러오는 중을 가르는 데 쓴다(화면설계서 2판 상태표) —
  // 종전에는 0곳인 상권에서 결론이 영원히 "불러오는 중이다"로 남았다.
  const [unitsFor, setUnitsFor] = useState<string | null>(null);
  const [unitId, setUnitId] = useState<string>("");
  const [industry, setIndustry] = useState("");
  const [prem, setPrem] = useState("");
  const [strategy, setStrategy] = useState("");
  const [recs, setRecs] = useState<IndustryRec[] | null>(null);

  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [previous, setPrevious] = useState<Calculation | null>(null);
  const lastCalculation = useRef<Calculation | null>(null);
  const requestSerial = useRef(0);
  const [handoffNote, setHandoffNote] = useState("");
  const result = calculation?.result ?? null;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const unit = useMemo(() => units.find((u) => u.id === unitId), [units, unitId]);

  // 화면 머리(결론 1줄 + 근거 3줄). 계산 결과가 바뀔 때만 다시 짠다.
  const head = useMemo(() => postingHeadline({
    districtName: districts.find((d) => d.id === districtId)?.name ?? districtId,
    unit, unitCount: units.length, unitsLoaded: unitsFor === districtId, result, premInput: prem,
  }), [districts, districtId, unit, units.length, unitsFor, result, prem]);

  useEffect(() => {
    let live = true;
    listDistricts()
      .then((all) => {
        if (!live) return;
        setDistricts(all);
        // 지금 상권이 목록에 없으면 첫 거점으로 떨어진다. 제어 모드면 공유 상권을 기준으로 본다.
        if (!selection && all.length && !all.some((d) => d.id === districtId)) setDistrictId(all[0].id);
      })
      .catch((e) => live && setErr(String(e)));
    return () => { live = false; };
    // 목록은 마운트(또는 인계 선택이 바뀔 때) 한 번만 부른다 — 상권 전환마다 다시 부르지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  useEffect(() => () => { requestSerial.current += 1; }, []);

  function clearCalculation() {
    requestSerial.current += 1;
    setCalculation(null); setPrevious(null); setBusy(false);
    lastCalculation.current = null;
  }

  function chooseDistrict(id: string) {
    clearCalculation(); setUnits([]); setUnitId(""); setRecs(null); setHandoffNote("");
    setIndustry(""); setPrem(""); setStrategy(""); setDistrictId(id);
  }

  function chooseUnit(id: string) {
    clearCalculation(); setRecs(null); setErr(null);
    setIndustry(""); setPrem(""); setStrategy(""); setUnitId(id);
    setHandoffNote("");
  }

  // 자리 목록 — 실측 공실 인벤토리(services/vacant_inventory)에서 온다
  useEffect(() => {
    let live = true;
    setUnits([]); setUnitId(""); setRecs(null); setErr(null);
    getPostings(districtId)
      .then((p) => {
        if (!live) return;
        setUnits(p);
        setUnitsFor(districtId);
        if (selection && districtId === selection.districtId) {
          // build_vacant_units.py의 id=f"vu-{p.get('id')}" 계약을 응답 목록에서 검증한다.
          // 이름·좌표로 추측하거나 층 표본을 ROI 유닛으로 바꾸지 않는다.
          const match = p.find((u) => u.id === `vu-${selection.buildingId}`);
          setUnitId(match?.id ?? "");
          setHandoffNote(match ? `${selection.buildingName}의 입점 계산 유닛을 확인했습니다.`
            : `${selection.buildingName}과 일치하는 입점 계산 유닛이 없습니다. 계산할 자리를 직접 선택해 주세요.`);
        } else setUnitId(p[0]?.id ?? "");
      })
      .catch((e) => { if (live) setErr(String(e)); });
    return () => { live = false; };
  }, [districtId, selection]);

  // 자리를 고르면 그 좌표로 GNN 업종 추천을 물어 온다 — 업종 입력의 출발점이다.
  // (Platform 이 자리마다 답하는 것과 같은 질의다. 여기서는 그 답을 비용 계산에 넘긴다.)
  useEffect(() => {
    if (!unit) { setRecs(null); return; }
    let live = true;
    setRecs(null);
    recommendIndustry({ district_id: districtId, lat: unit.lat, lon: unit.lng })
      .then((r) => { if (live && r.model !== "gnn-stub") setRecs(r.recommendations); })
      .catch(() => { if (live) setRecs(null); });   // 404 = 400m 안에 노드 없음
    return () => { live = false; };
  }, [unit, districtId]);

  // 자리가 정해지면 우선 **입력 없이** 한 번 돌려 빈 화면을 만들지 않는다.
  // 이때 prem 은 보내지 않으므로 결과가 `absent`(0 전제)로 온다 — 그 사실은 화면이 밝힌다.
  useEffect(() => {
    if (!unitId) return;
    run({ quiet: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitId]);

  async function run(opts: { quiet?: boolean } = {}) {
    if (!unit || !unitId) return;
    const serial = ++requestSerial.current;
    setBusy(true);
    if (!opts.quiet) setErr(null);
    try {
      const parsed = prem.trim() === "" ? undefined : Math.max(0, Number(prem));
      const input: Calculation["input"] = {
        district_id: districtId,
        unit_id: unitId,
        industry_type: industry.trim() || undefined,
        strategy: strategy || undefined,
        prem: Number.isFinite(parsed as number) ? (parsed as number) : undefined,
      };
      const r = await simulateRevenue(input);
      if (serial !== requestSerial.current) return;
      // 서버가 유닛을 찾지 못하면 첫 유닛으로 폴백할 수 있어 응답도 대조한다.
      if (r.district_id !== input.district_id || r.unit_id !== input.unit_id) throw new Error("선택한 자리와 계산 응답이 일치하지 않습니다.");
      const before = lastCalculation.current;
      const sameScope = before && before.input.district_id === input.district_id && before.input.unit_id === input.unit_id
        && before.input.industry_type === input.industry_type && before.input.strategy === input.strategy
        && before.input.prem !== input.prem && before.result.source === r.source && before.result.inputs_quarter === r.inputs_quarter
        && Object.entries(r.scenarios).every(([key, tier]) => before.result.scenarios[key]?.basis === tier.basis);
      setPrevious(sameScope ? before : null);
      const next = { result: r, input };
      lastCalculation.current = next;
      setCalculation(next);
    } catch (e) {
      if (serial !== requestSerial.current) return;
      setErr(String(e));
      setCalculation(null); setPrevious(null); lastCalculation.current = null;
    } finally {
      if (serial === requestSerial.current) setBusy(false);
    }
  }

  // ── 지도 (2026-09-13 「네 트랙 모두 지도 전체화면」) ─────────────────────────
  // 계산할 수 있는 자리를 지도에 **월임대료 칩**으로 건다. 드롭다운 한 줄로만 보이던 자리가
  // "어디에 있고 얼마인지"로 먼저 읽힌다. 칩을 누르면 드롭다운에서 고른 것과 똑같이 동작한다.
  // 금액은 목록의 `unit.rent`(R-ONE × 면적 × 층 계수) 그대로다 — 지도에서 따로 계산하지 않는다.
  const markers = useMemo<MapMarkerItem[]>(() => units.map((u) => ({
    id: u.id, lat: u.lat, lng: u.lng, zIndex: u.id === unitId ? 200 : 70,
    html: mapLabelHTML({
      text: `월 ${shortManwon(u.rent)}`, sub: `${u.area}평`,
      color: colors.track.posting.base, active: u.id === unitId,
    }),
  })), [units, unitId]);
  useMapMarkers(markers, chooseUnit);
  const hubCenter = districts.find((d) => d.id === districtId)?.center;
  useFitMap(districtId, units, hubCenter ? { lat: hubCenter[0], lng: hubCenter[1] } : null);

  // Posting → Program 인계 값. 업종은 **계산에 쓴 업종**을 먼저, 없으면 자리의 직전 업종.
  // 전략명은 계산했고 회수되는 전략이 있을 때만 — 없는 추천을 지어내지 않는다.
  function makeProgram() {
    if (!unit || !onMakeProgram) return;
    const used = calculation?.input.unit_id === unit.id ? calculation : null;
    const entries = used ? Object.entries(used.result.scenarios) : [];
    const viable = entries.filter(([, t]) => t.viable);
    const best = entries.find(([, t]) => t.recommended && t.viable)
      ?? [...viable].sort((a, b) => a[1].roi_months - b[1].roi_months)[0];
    onMakeProgram({
      districtId, unitId: unit.id, unitName: unit.n, lat: unit.lat, lng: unit.lng,
      area: unit.area, floor: unit.floor, rent: unit.rent,
      industry: used?.input.industry_type || unit.was?.trim() || null,
      strategy: best ? (TIER_LABEL[best[0]]?.name ?? best[1].name) : null,
    });
  }

  const tiers = result ? Object.entries(result.scenarios) : [];
  const changedInput = calculation && (calculation.input.industry_type !== (industry.trim() || undefined)
    || calculation.input.strategy !== (strategy || undefined)
    || calculation.input.prem !== (prem.trim() === "" ? undefined : Number(prem)));

  return (
    <div className="postconsole"><div className="wrap">
      {/* 2026-09-13: 손으로 짠 `.hd` 헤더를 공용 `Verdict` 로 바꿨다.
          같은 모양(eyebrow · 4P 전환 · 질문 h1 · 설명)을 갖고 있었지만 **결론 문장과
          근거 줄, 출처 줄이 없었다** — Platform·Program 은 이미 Verdict 를 쓰는데
          Posting 만 질문을 던지고 답을 안 했다. 네 트랙이 같은 자리에서 같은 모양으로
          답해야 한다는 것이 Verdict 를 만든 이유다(components/Verdict.tsx).
          근거: design/references/INDEX.md §2-1(Placer.ai — 결론 → 차트 → 원자료). */}
      <Verdict
        eyebrow="PlaceOS · Posting" conversion="PRICE ▶ POSTING"
        question="어느 가격대의 page 를 이 자리에 올릴까"
        verdict={head.verdict} grounds={head.grounds} sources={head.sources}
        note={
          <>
            "얼마에 팔까"가 아니라 <b>어느 가격대를 이 자리에 posting 할까</b>를 답한다.
            실측 공실 자리를 골라 <b>업종·권리금</b>을 넣으면 세 전략(고급화·가성비·기능중심)의
            월 순익과 회수기간을 낸다. 임대료는 R-ONE 실측, 면적은 건축물대장이며,
            <b> 권리금은 공개 통계가 없어 기업이 넣는 입력</b>이다 — 비워 두면 0 을 전제로 계산하고
            결과가 그 사실을 밝힌다.
          </>
        }
      />

      {err && (
        <div className="err">
          <strong>계산에 실패했습니다.</strong>
          <div className="errdetail">{err}</div>
        </div>
      )}

      <div className="cols">
        {/* ── 입력 ── */}
        <form className="panel" onSubmit={(e) => { e.preventDefault(); run(); }}>
          <div className="ptitle">1. 자리와 업종 선택</div>
          {handoffNote && <div className="posting-handoff" role="status">{handoffNote}</div>}

          <label className="field">
            <span className="flabel">상권</span>
            <DistrictPicker districts={districts} value={districtId}
              onChange={chooseDistrict} suffix={(d) => d.gu} />
            <CaveatNote district={districts.find((d) => d.id === districtId)} />
          </label>

          <label className="field">
            <span className="flabel">
              자리 <em>실측 {units.length}곳</em>
            </span>
            <select value={unitId} onChange={(e) => chooseUnit(e.target.value)} disabled={!units.length}>
              {!unitId && <option value="">계산할 자리를 선택하세요</option>}
              {units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.n} · {u.area}평 · {u.floor}
                </option>
              ))}
            </select>
            {unit && (
              <span className="fhint">
                임대료 {won(unit.rent)}/월 · 직전 업종 {unit.was || "미상"}
                {unit.foot ? ` · 유동 ${unit.foot}` : ""}
              </span>
            )}
          </label>

          <label className="field">
            <span className="flabel">업종</span>
            <input value={industry} onChange={(e) => setIndustry(e.target.value)}
              placeholder="예: 카페 (비우면 자리 기본값)" />
            {recs && recs.length > 0 && (
              <span className="chips">
                {recs.map((r) => (
                  <button type="button" key={r.industry}
                    className={"chip" + (industry === r.industry ? " on" : "")}
                    onClick={() => setIndustry(r.industry)}>
                    {r.industry} {Math.round(r.score * 100)}%
                  </button>
                ))}
                <i className="chipnote">GNN 추천 — 이 자리 좌표 기준</i>
              </span>
            )}
          </label>

          <div className="ptitle posting-input-step">2. 비용 조건 입력</div>
          <label className="field">
            <span className="flabel">권리금 <em>입력 계약</em></span>
            <input value={prem} inputMode="numeric"
              onChange={(e) => setPrem(e.target.value.replace(/[^\d]/g, ""))}
              placeholder="만원 — 비우면 0 전제" />
            <span className="fhint">
              공개 통계가 없다(bronze 전수 확인). 임대인·기존 임차인과의 <b>협상값</b>이라
              그 자리에 들어갈 기업만 안다. 비워 두면 0 을 전제로 계산하고
              결과에 <code>absent</code> 로 표시된다.
            </span>
          </label>

          <details className="posting-advanced"><summary>세부 조건 · 전략 선택</summary>
          <label className="field">
            <span className="flabel">전략</span>
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              <option value="">세 전략 비교</option>
              <option value="premium">고급화</option>
              <option value="value">가성비</option>
              <option value="factory">기능중심</option>
            </select>
          </label>

          </details>

          <Button className="run" type="submit" disabled={busy || !unitId}>
            {busy ? "계산 중…" : "시뮬레이션"}
          </Button>
        </form>

        {/* ── 결과 ── */}
        <div className="results">
          {onMakeProgram && (
            <Button type="button" variant="ghost" className="posting-to-program" disabled={!unit}
              onClick={makeProgram}>이 자리로 홍보 program 만들기 →</Button>
          )}
          <div className="posting-result-heading"><h2>세 가격대의 비용과 회수기간</h2><p>처음 필요한 돈 · 매달 나가는 돈 · 투자 회수까지</p></div>
          {!result && !busy && <div className="empty">자리를 고르면 계산한다.</div>}
          {result && (
            <>
              {calculation && <div className="posting-input-summary">
                계산에 사용한 입력: {calculation.input.industry_type || "자리 기본 업종"} · 권리금 {calculation.input.prem === undefined ? "미입력 · 0 전제" : won(calculation.input.prem)} · {TIER_LABEL[calculation.input.strategy ?? ""]?.name ?? "세 전략 비교"}
                {changedInput && <strong role="status">입력이 변경되었습니다. 다시 계산하면 결과에 반영됩니다.</strong>}
              </div>}
              <div className="rhead">
                <div className="rtitle">
                  {unit?.n ?? result.unit_id}
                  {result.industry_type && <span className="rind">{result.industry_type}</span>}
                </div>
                <div className="rbadges">
                  {/* 코파일럿이 돌았는지 폴백인지 — 안 붙였다와 붙였는데 실패했다를 섞지 않는다 */}
                  <span className={"badge " + (result.source === "copilot" ? "is-copilot" : "is-fallback")}>
                    {result.source === "copilot" ? "코파일럿" : "내부 3-Tier 폴백"}
                  </span>
                  {result.inputs_quarter && <span className="badge is-q">{result.inputs_quarter} 기준</span>}
                </div>
              </div>

              {result.source_note && (
                <div className="note is-warn">
                  <b>코파일럿이 설정돼 있는데 실패했다</b> — 아래는 폴백 계산이다.
                  <div className="notedetail">{result.source_note}</div>
                </div>
              )}

              {result.inputs_source && (
                <div className="inputs">
                  {(["area", "rent", "prem", "foot"] as const).map((k) => (
                    <span key={k} className={"isrc " + srcClass(result.inputs_source![k])}>
                      {{ area: "면적", rent: "임대료", prem: "권리금", foot: "유동" }[k]}
                      <i>{srcLabel(result.inputs_source![k])}</i>
                    </span>
                  ))}
                  {result.inputs_source.floor && (
                    <span className={"isrc " + srcClass(result.inputs_source.floor)}>
                      층<i>{result.inputs_source.floor === "flr_ouln" ? "층별개요 실측" : "1층 가정(상한)"}</i>
                    </span>
                  )}
                </div>
              )}

              {result.unviable_note && <div className="note is-bad">{result.unviable_note}</div>}

              <div className="tiers">
                {tiers.map(([key, s]) => (
                  <TierCard key={key} tierKey={key} s={s} before={previous?.result.scenarios[key]} />
                ))}
              </div>
              {previous && calculation && <p className="posting-comparison-note">직전 계산 대비 · 동일 자리·업종·전략·기준분기 · 권리금 {previous.input.prem === undefined ? "미입력(0 전제)" : won(previous.input.prem)} → {calculation.input.prem === undefined ? "미입력(0 전제)" : won(calculation.input.prem)}. 차이는 두 서버 계산 결과를 비교한 값입니다.</p>}

              <div className="rsrc">
                비용 기준: {BASIS_LABEL[tiers[0]?.[1]?.basis] ?? tiers[0]?.[1]?.basis ?? "미상"}
                {" · "}자리 = 건축물대장 실측 공실 인벤토리 · 임대료 = R-ONE ·
                매출 앵커 = KOSIS 서비스업조사 + 공정위 가맹사업 면적
                <br />
                권리금을 넣으면 회수기간이 바뀐다 — 실측 감도(270유닛 전수)로
                <b> 추천 5.2% 뒤집힘 · 회수 가부 판정은 0건 변화</b>였다. 즉 "회수 불가" 결론은
                권리금과 무관하게 성립한다.
              </div>
            </>
          )}
        </div>
      </div>
    </div></div>
  );
}

function TierCard({ tierKey, s, before }: { tierKey: string; s: TierScenario; before?: TierScenario }) {
  const meta = TIER_LABEL[tierKey] ?? { name: s.name ?? tierKey, sub: s.sub ?? "" };
  return (
    <Card className={"tier" + (s.recommended ? " rec" : "") + (s.viable ? "" : " dead")}>
      <div className="thd">
        <span className="tname">{meta.name}</span>
        {s.recommended && <span className="trec">추천</span>}
      </div>
      <div className="tsub">{meta.sub}</div>

      <div className="trow"><span>초기 투자</span><span>{won(s.invest_mn)}</span></div>
      <div className="trow"><span>월 비용</span><span>{won(s.month_cost)}</span></div>
      <div className="trow"><span>월 매출</span><span>{won(s.month_rev)}</span></div>
      <div className="trow big">
        <span>월 순익</span>
        <span className={s.month_net > 0 ? "pos" : "neg"}>{won(s.month_net)}</span>
      </div>
      <div className="trow">
        <span>회수기간</span>
        {/* "모른다"와 "안 된다"는 다른 정보다 — 순익이 0 이하면 회수기간이 정의되지 않는다 */}
        <span>{s.viable ? `${s.roi_months}개월` : "회수 불가"}</span>
      </div>
      {before && <div className="tier-difference" aria-label={`${meta.name} 직전 계산과 비교`}>
        <b>직전 계산 대비</b>
        <span>초기 투자 {difference(s.invest_mn - before.invest_mn, "만원")}</span>
        <span>월 순익 {difference(s.month_net - before.month_net, "만원")}</span>
        <span>회수기간 {s.viable && before.viable && s.roi_months != null && before.roi_months != null
          ? difference(s.roi_months - before.roi_months, "개월") : `${before.viable ? `${before.roi_months}개월` : "회수 불가"} → ${s.viable ? `${s.roi_months}개월` : "회수 불가"}`}</span>
      </div>}
    </Card>
  );
}

function difference(value: number, unit: string): string {
  return `${value > 0 ? "+" : ""}${Number(value.toFixed(2)).toLocaleString()}${unit}`;
}

/** 입력 출처 라벨 — 프록시를 실측으로 오독하지 않게 한다. 모르는 값은 그대로 노출한다. */
/* ───────────────── 결론 1줄 + 근거 3줄 (2026-09-13) ─────────────────
 *
 * 이 화면이 답한 것과 그 답을 세운 값. Platform·Program 의 `headline()` 과 같은 자리다.
 *
 * 상태가 셋이고 **셋을 섞지 않는다**:
 *   ① 아직 자리를 안 골랐다      → 무엇을 고르면 무엇이 나오는지 말한다
 *   ② 골라서 계산했고 회수된다   → 어느 전략이 몇 개월인지 말한다
 *   ③ 계산했는데 셋 다 회수 불가 → **"추천이 없다"가 아니라 "회수가 안 된다"** 고 말한다
 *
 * ⚠ 권리금이 `absent`(입력 없음)면 결론에 그 사실을 싣는다. 0 을 전제로 낸 회수기간을
 *   실측처럼 읽으면 그 숫자가 곧 거짓말이 된다 — 이 화면 주석 §화면 원칙과 같은 규칙이다.
 */
function postingHeadline({ districtName, unit, unitCount, unitsLoaded, result, premInput }: {
  districtName: string;
  unit?: Posting;
  unitCount: number;
  unitsLoaded: boolean;
  result: SimulateResult | null;
  premInput: string;
}): { verdict: React.ReactNode; grounds: Ground[]; sources: React.ReactNode[] } {
  const sources: React.ReactNode[] = [
    "임대료 R-ONE 실측", "면적 건축물대장", "영업비용률 KOSIS", "권리금 기업 입력",
  ];

  // ① 아직 계산 전.
  if (!result) {
    return {
      verdict: unitCount
        ? <>{districtName}에 실측 공실 <b>{unitCount.toLocaleString()}곳</b>이 있다. 자리와 업종을 고르면 세 가격대의 회수기간을 낸다.</>
        : unitsLoaded
          ? <>{districtName}에는 계산할 실측 공실 자리가 없다.</>
          : <>{districtName}의 공실 자리를 불러오는 중이다.</>,
      grounds: [
        { label: "고를 수 있는 자리", value: unitCount ? `${unitCount.toLocaleString()}곳` : unitsLoaded ? "0곳" : "불러오는 중", source: "건축물대장 실측 인벤토리" },
        { label: "비교하는 가격대", value: "고급화 · 가성비 · 기능중심 3전략" },
        { label: "권리금", value: premInput ? `${Number(premInput).toLocaleString()}만원 입력됨` : "미입력 — 0 을 전제로 계산한다", source: "공개 통계 없음 · 기업 입력 계약" },
      ],
      sources,
    };
  }

  // ⚠ 전략 이름은 `TIER_LABEL[key]` 로 읽는다. `scenario.name` 은 백엔드가 원시 키
  //   ("value")를 주기도 해서 그대로 쓰면 화면 나머지(TierCard)와 다른 이름이 뜬다.
  const entries = Object.entries(result.scenarios);
  const label = (key: string, s: TierScenario) => TIER_LABEL[key]?.name ?? s.name;
  const viable = entries.filter(([, t]) => t.viable);
  // 추천 전략이 회수 불가일 수는 없지만, 백엔드가 recommended 를 안 준 경우를 대비해
  // **회수되는 것 중 가장 빠른 것**으로 떨어진다. 없는 값을 지어내지 않는다.
  const best = entries.find(([, t]) => t.recommended && t.viable)
    ?? [...viable].sort((a, b) => a[1].roi_months - b[1].roi_months)[0];
  const where = unit?.n ?? result.unit_id;
  const premAbsent = result.inputs_source?.prem === "absent";
  const basis = BASIS_LABEL[entries[0]?.[1]?.basis] ?? entries[0]?.[1]?.basis ?? "미상";

  // ③ 셋 다 회수 불가 — 이것도 답이다. 비워 두면 "계산이 안 됐다"로 읽힌다.
  if (!best) {
    return {
      verdict: <><b>{where}</b>는 세 전략 모두 회수되지 않는다.{result.unviable_note ? ` ${result.unviable_note}` : ""}</>,
      grounds: [
        { label: "회수되는 전략", value: `없음 (${entries.length}전략 중 0)`, source: `비용 기준 ${basis}` },
        { label: "월 임대료", value: unit ? won(unit.rent) : "미상", source: "R-ONE 실측" },
        { label: "권리금", value: premAbsent ? "미입력 — 0 전제" : "기업 입력 반영", source: premAbsent ? "이 값을 넣으면 회수기간이 더 늘어난다" : undefined },
      ],
      sources,
    };
  }

  // ② 회수된다.
  const [bestKey, bestTier] = best;
  const bestName = label(bestKey, bestTier);
  return {
    verdict: (
      <>
        <b>{where}</b>는 <b>{bestName}</b> 전략으로 <b>{bestTier.roi_months}개월</b>에 회수된다
        {premAbsent && <> — 단 <b>권리금 0 을 전제</b>로 한 값이다</>}.
      </>
    ),
    grounds: [
      {
        label: "가장 빠른 회수",
        value: `${bestName} · ${bestTier.roi_months}개월 (월 순익 ${won(bestTier.month_net)})`,
        source: `비용 기준 ${basis}`,
      },
      {
        label: "회수되는 전략",
        value: `${entries.length}전략 중 ${viable.length}개`,
        source: viable.length < entries.length ? `${entries.length - viable.length}개는 월 순익이 0 이하다` : undefined,
      },
      {
        label: "권리금",
        value: premAbsent ? "미입력 — 0 을 전제로 계산" : "기업 입력 반영",
        source: premAbsent ? "공개 통계가 없어 그 자리에 들어갈 기업만 안다" : "입력 계약",
      },
      // 네 줄째부터는 Verdict 가 접는다 — 규칙이 세 줄이지 값이 셋인 것은 아니다.
      {
        label: "계산 경로",
        value: result.source === "copilot" ? "외부 AI 창업 코파일럿" : "내부 3-Tier 폴백",
        source: result.source_note ?? undefined,
      },
    ],
    sources,
  };
}

function srcLabel(v: string | undefined): string {
  return ({
    rone: "R-ONE 실측", flpop: "유동 실측", "flpop+seed": "유동+서열",
    "flpop+jipgyegu": "유동 실측(집계구)",
    seed: "시드 프록시", absent: "전제(0)", contract: "기업 입력",
    bldg: "대장 실측", "gold-ledger": "대장 실측", "bldg+split": "대장·균등분할",
  } as Record<string, string>)[v ?? ""] ?? (v ?? "미상");
}
/** 실측(초록) / 프록시(회색 점선) / 전제(노랑 점선). 모르는 값은 프록시로 눕힌다 —
 *  라벨을 모르는 것을 실측으로 올리면 그게 곧 출처 왜곡이다. */
function srcClass(v: string | undefined): string {
  if (["contract", "rone", "flpop", "flpop+jipgyegu", "bldg", "gold-ledger", "flr_ouln"].includes(v ?? "")) {
    return "is-real";
  }
  if (v === "absent") return "is-absent";
  return "is-proxy";
}
