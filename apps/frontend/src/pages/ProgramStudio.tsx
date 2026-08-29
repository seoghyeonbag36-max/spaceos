import { useEffect, useMemo, useRef, useState } from "react";
import {
  listDistricts, generateCommercialStoreMarketing, generateStoreMarketing,
  lookupStorePlaces, lookupStoreReviews,
} from "@/lib/api";
import type {
  ChannelPlan, DistrictSummary, StoreMarketing, StorePlace,
} from "@/lib/api";
import "./ProgramStudio.css";

/**
 * Program 스튜디오 — 가게 단위 마케팅 솔루션 생성 화면.
 *
 * 백엔드 `POST /marketing/generate`(services/marketing.py)는 2026-07-18 부터 있었지만
 * 이걸 부르는 화면이 없어서 기능이 API 로만 존재했다. 이 페이지가 그 표면이다.
 *
 * 입력 원칙 — 화면에도 그대로 드러낸다(docs/feature-program.md §0):
 *   네이버 플레이스의 **방문자 리뷰·사진·메뉴에는 공식 API 가 없다.** 그래서 공식 API 로
 *   얻을 수 있는 것만 자동으로 채운다 — 카카오 로컬(상호·카테고리·주소)과 네이버 블로그
 *   검색(리뷰성 스니펫). 사진·메뉴는 여전히 붙여넣기다. 크롤링해 온 원본(특히 사진)은
 *   PoC 내부 검증 한정이고, 상용 경로는 점주 제공(B2B 온보딩 동의) 데이터다.
 */

/** 백엔드가 vision 에 넘기는 사진 수 상한 — services/marketing.py `image_urls[:4]` 와 맞춘다.
 *  화면에서 5장째부터 흐리게 처리해 "넣었는데 안 쓰인" 상태를 숨기지 않는다. */
const VISION_MAX = 4;

/** 카테고리 자동완성 후보. 자유 입력이며 이 목록은 힌트일 뿐이다(백엔드는 문자열을 그대로 받는다). */
const CATEGORY_HINTS = [
  "카페", "베이커리", "F&B", "이자카야", "주점", "한식", "일식", "양식",
  "의류", "뷰티", "헬스·필라테스", "공방", "반려동물",
];

interface FormState {
  name: string;
  category: string;
  districtId: string;
  address: string;
  reviewsText: string;
  imagesText: string;
  menuText: string;
  keywordsText: string;
}

const EMPTY: FormState = {
  name: "", category: "", districtId: "", address: "",
  reviewsText: "", imagesText: "", menuText: "", keywordsText: "",
};

/** 데모용 예시 입력. **가상의 가게**다 — 실존 상호의 리뷰를 지어내 붙이면
 *  그 가게에 대한 허위 근거가 되므로 이름부터 예시임을 밝힌다. */
const SAMPLE: FormState = {
  name: "예시 카페 로우(가로수길점)",
  category: "카페",
  districtId: "garosugil",
  address: "서울 강남구 신사동 가로수길 일대",
  reviewsText: [
    "원두를 매주 바꿔서 소개해주는 게 좋아요. 산미 있는 걸 좋아한다 했더니 딱 맞게 추천해주심.",
    "2층 창가 자리가 조용해서 노트북 작업하기 좋았습니다. 콘센트도 자리마다 있어요.",
    "말차 라떼가 진하고 안 달아서 좋았어요. 디저트는 바스크 치즈케이크 추천.",
    "주말 오후엔 웨이팅 20분 정도 있었어요. 회전은 빠른 편.",
    "사장님이 커피 설명을 길게 해주셔서 좋았는데, 바쁠 땐 주문이 좀 밀립니다.",
    "인테리어가 차분하고 사진 찍기 좋아요. 조명이 따뜻한 편.",
  ].join("\n"),
  imagesText: "",
  menuText: [
    "오늘의 드립 6,000원",
    "말차 라떼 6,500원",
    "바스크 치즈케이크 8,000원",
  ].join("\n"),
  keywordsText: "",
};

const linesOf = (t: string) => t.split("\n").map((s) => s.trim()).filter(Boolean);
const commaOf = (t: string) => t.split(",").map((s) => s.trim()).filter(Boolean);
const isHttp = (u: string) => /^https?:\/\//.test(u);

export default function ProgramStudio() {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [districts, setDistricts] = useState<DistrictSummary[] | null>(null);
  const [districtErr, setDistrictErr] = useState(false);
  const [result, setResult] = useState<StoreMarketing | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [commercialMode, setCommercialMode] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [processingConsent, setProcessingConsent] = useState(false);
  const [externalConsent, setExternalConsent] = useState(false);
  const [retentionAcknowledged, setRetentionAcknowledged] = useState(false);
  const [onboardingReceipt, setOnboardingReceipt] = useState<string | null>(null);

  // 반자동 채우기 — 후보 검색(카카오) → 선택 → 블로그 스니펫 주입(네이버)
  const [places, setPlaces] = useState<StorePlace[] | null>(null);
  const [publicReviews, setPublicReviews] = useState<string[]>([]);
  const [lookupBusy, setLookupBusy] = useState(false);
  const [lookupNote, setLookupNote] = useState<string | null>(null);

  useEffect(() => {
    // 거점 목록은 상권 컨텍스트 결합용(선택)이라 실패해도 생성 자체는 된다. 다만 **조용히**
    // 비우면 "결합 안 함"만 남은 드롭다운이 정상처럼 보인다 — 실패했음을 화면에 남긴다.
    listDistricts().then(setDistricts).catch(() => { setDistricts([]); setDistrictErr(true); });
  }, []);

  // 실호출은 vision 포함 시 10~20초가 걸린다(2026-08-01 실측 12~14초). 멈춘 화면처럼
  // 보이지 않게 경과 초를 센다 — 시연 중 "죽었나?" 소리가 나오지 않게 하는 장치다.
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!busy) { if (timer.current) window.clearInterval(timer.current); return; }
    setElapsed(0);
    timer.current = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [busy]);

  const merchantReviews = useMemo(() => linesOf(form.reviewsText), [form.reviewsText]);
  const reviews = useMemo(
    () => commercialMode ? merchantReviews : [...merchantReviews, ...publicReviews],
    [commercialMode, merchantReviews, publicReviews],
  );
  const images = useMemo(() => linesOf(form.imagesText), [form.imagesText]);
  const menu = useMemo(() => linesOf(form.menuText), [form.menuText]);
  const keywords = useMemo(() => commaOf(form.keywordsText), [form.keywordsText]);
  const badImages = images.filter((u) => !isHttp(u));

  const hasMerchantContent = merchantReviews.length > 0 || images.length > 0
    || menu.length > 0 || keywords.length > 0;
  const commercialReady = apiKey.trim() !== "" && hasMerchantContent
    && rightsConfirmed && processingConsent && externalConsent && retentionAcknowledged;
  const canSubmit = form.name.trim() !== "" && form.category.trim() !== "" && !busy
    && (!commercialMode || commercialReady);

  const set = <K extends keyof FormState>(k: K) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  function toggleCommercialMode() {
    // 공개 검색 스니펫·합성 예시가 점주 제공 데이터로 둔갑하지 않도록 모드를 바꿀 때
    // 입력을 비운다. API 키도 브라우저 저장소에 남기지 않고 현재 메모리에서만 가진다.
    setCommercialMode(!commercialMode);
    setApiKey("");
    setForm(EMPTY);
    setPublicReviews([]);
    setPlaces(null);
    setLookupNote(null);
    setResult(null);
    setError(null);
    setOnboardingReceipt(null);
    setRightsConfirmed(false);
    setProcessingConsent(false);
    setExternalConsent(false);
    setRetentionAcknowledged(false);
  }

  /** 상호로 가게 후보를 찾는다. 자동 선택하지 않는다 — 같은 상호가 전국에 있다. */
  async function searchPlaces() {
    const q = form.name.trim();
    if (!q || lookupBusy) return;
    setLookupBusy(true);
    setPlaces(null);
    setLookupNote(null);
    try {
      const r = await lookupStorePlaces(q, form.districtId || undefined);
      setPlaces(r.places);
      setLookupNote(r.source === "unavailable"
        ? `가게 검색을 쓸 수 없다 — ${r.note ?? "카카오 로컬 키 확인 필요"}`
        : r.note);
    } catch (err) {
      setPlaces([]);
      setLookupNote(`가게 검색 실패: ${String(err)}`);
    } finally {
      setLookupBusy(false);
    }
  }

  /** 후보 선택 → 기본정보를 채우고, 그 주소로 좁힌 블로그 스니펫을 리뷰란에 넣는다.
   *  기존 리뷰 입력이 있으면 **덮어쓰지 않고 뒤에 잇는다** — 점주가 준 원문이 날아가면 안 된다. */
  async function applyPlace(p: StorePlace) {
    setForm((f) => ({
      ...f,
      name: p.name,
      category: p.category || f.category,
      address: p.road_address || p.address || f.address,
    }));
    setPlaces(null);
    setLookupBusy(true);
    setLookupNote(null);
    try {
      const r = await lookupStoreReviews(p.name, p.address ?? p.road_address);
      if (r.reviews.length) setPublicReviews((old) => [...old, ...r.reviews]);
      setLookupNote(`'${r.query}' 검색 → ${r.reviews.length}건 주입. ${r.note ?? ""}`.trim());
    } catch (err) {
      setLookupNote(`리뷰 스니펫 조회 실패: ${String(err)}`);
    } finally {
      setLookupBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setOnboardingReceipt(null);
    try {
      const profile = {
        name: form.name.trim(),
        category: form.category.trim(),
        district_id: form.districtId || undefined,
        address: form.address.trim() || undefined,
        // 상용 경로는 점주가 직접 넣은 원문만 보낸다. 공개 검색 스니펫은 별도 state라
        // 구조적으로 섞일 수 없다.
        reviews: commercialMode ? merchantReviews : reviews,
        image_urls: images.filter(isHttp),
        menu,
        keywords,
      };
      if (commercialMode) {
        // canSubmit 이 네 확인을 모두 요구한다. 여기서는 그 확인 뒤에만 Literal true
        // 계약을 만든다 — 체크박스의 기본값으로 동의를 만들어 보내지 않는다.
        const onboarded = await generateCommercialStoreMarketing(profile, {
          contract_version: "spaceos.program-onboarding/1",
          data_origin: "merchant-provided",
          processing_purpose: "program-marketing-generation",
          consent_to_process: true,
          rights_confirmed: true,
          allow_external_model_processing: true,
          raw_input_retention: "request-only",
        }, apiKey.trim());
        setResult(onboarded.marketing);
        setOnboardingReceipt(onboarded.onboarding_id);
      } else {
        setResult(await generateStoreMarketing(profile));
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="progstudio"><div className="wrap">
      <div className="hd">
        <div className="ey">SpaceOS · Program</div>
        <h1>가게 단위 마케팅 솔루션</h1>
        <div className="sub">
          가게의 리뷰·사진·메뉴·기본정보를 넣으면 온라인/오프라인 광고 솔루션을 근거와 함께 생성한다.
          상호를 검색하면 카카오 로컬(기본정보)과 네이버 블로그(리뷰성 스니펫)로 절반쯤 자동으로 채워진다.
          거점을 고르면 Platform 이 모은 상권 컨텍스트(블로그 키워드·업종 분포·검색 트렌드)가 함께 반영된다.
        </div>
      </div>

      <div className="cols">
        {/* ── 입력 ── */}
        <form className="panel" onSubmit={submit}>
          <div className="ptitle">
            {commercialMode ? "상용 입력 온보딩" : "가게 프로필"}
            <div className="ptools">
              {!commercialMode && (
                <button type="button" className="ghost" onClick={() => setForm(SAMPLE)}>예시 채우기</button>
              )}
              <button type="button" className={`ghost ${commercialMode ? "active" : ""}`}
                onClick={toggleCommercialMode}>
                {commercialMode ? "공개 데모로" : "상용 온보딩"}
              </button>
              <button type="button" className="ghost" onClick={() => {
                setForm(EMPTY); setPublicReviews([]); setResult(null); setError(null);
                setOnboardingReceipt(null);
                setApiKey(""); setRightsConfirmed(false); setProcessingConsent(false);
                setExternalConsent(false); setRetentionAcknowledged(false);
              }}>비우기</button>
            </div>
          </div>

          {commercialMode && (
            <div className="onboardIntro">
              이 경로는 <b>점주 또는 권한을 받은 조직이 직접 제공한 데이터만</b> 받는다.
              카카오·블로그 자동 검색은 끄고, 원문은 생성 요청 중에만 사용한다.
            </div>
          )}

          <div className="row2">
            <Field label="가게명" required
              hint={commercialMode
                ? "점주 또는 권한을 받은 조직이 확인한 상호를 직접 입력한다."
                : "상호를 넣고 검색하면 카카오 로컬에서 후보를 찾아 기본정보·블로그 스니펫을 채운다."}>
              {commercialMode ? (
                <input value={form.name} onChange={set("name")} placeholder="점주 확인 상호" />
              ) : <div className="inputbtn">
                <input value={form.name} onChange={set("name")} placeholder="예: 맡기다"
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); searchPlaces(); } }} />
                <button type="button" className="ghost" onClick={searchPlaces}
                  disabled={!form.name.trim() || lookupBusy}>
                  {lookupBusy ? "…" : "검색"}
                </button>
              </div>}
            </Field>
            <Field label="카테고리" required>
              <input value={form.category} onChange={set("category")} list="cat-hints" placeholder="예: 카페" />
              <datalist id="cat-hints">
                {CATEGORY_HINTS.map((c) => <option key={c} value={c} />)}
              </datalist>
            </Field>
          </div>

          {/* 후보를 자동 선택하지 않는다 — 같은 상호가 전국에 있어(2026-08-01 코퍼스 오염의
              원인) 사람이 골라야 리뷰 질의를 그 동네로 좁힐 수 있다. */}
          {places && places.length > 0 && (
            <div className="cands">
              <div className="candhd">후보 {places.length}곳 — 맞는 가게를 고르면 기본정보와 블로그 스니펫이 채워진다</div>
              {places.map((p, i) => (
                <button type="button" key={i} className="cand" onClick={() => applyPlace(p)}>
                  <span className="cname">{p.name}</span>
                  <span className="ccat">{p.category}</span>
                  <span className="caddr">
                    {p.road_address || p.address}
                    {p.distance_m != null && ` · ${p.distance_m}m`}
                  </span>
                </button>
              ))}
            </div>
          )}
          {places && places.length === 0 && !lookupBusy && (
            <div className="warn">검색 결과가 없다. 지도에 표기된 상호 그대로 넣거나, 아래에 직접 입력하라.</div>
          )}
          {lookupNote && <div className="note">{lookupNote}</div>}

          <Field label="거점(상권 컨텍스트)"
            hint={districtErr
              ? "거점 목록을 불러오지 못했다 — 백엔드 확인 필요. 지금은 컨텍스트 결합 없이만 생성된다."
              : "선택 시 해당 거점의 Gold 컨텍스트가 프롬프트에 결합된다. Gold 미적재 거점이면 컨텍스트 없이 생성된다."}
            count={districts?.length ? `${districts.length}곳` : undefined}>
            <select value={form.districtId} onChange={set("districtId")} disabled={districts === null}>
              <option value="">{districts === null ? "거점 불러오는 중…" : "— 결합 안 함 —"}</option>
              {(districts ?? []).map((d) => (
                <option key={d.id} value={d.id}>{d.name} · {d.gu}</option>
              ))}
            </select>
          </Field>

          <Field label="주소">
            <input value={form.address} onChange={set("address")} placeholder="예: 서울 강남구 신사동 …" />
          </Field>

          {!commercialMode && publicReviews.length > 0 && (
            <div className="sourcebox">
              <b>공개 검색 스니펫 {publicReviews.length}건</b>
              <span>네이버 블로그 검색 결과이며 점주 제공 원문이 아니다. 공개 데모에만 합류한다.</span>
            </div>
          )}

          <Field label={commercialMode ? "점주 제공 리뷰" : "직접 입력 리뷰 · 블로그 텍스트"}
            hint={commercialMode
              ? "한 줄에 하나. 제공·처리 권한을 확인한 원문만 입력한다."
              : "한 줄에 하나. 자동 검색분은 위에 별도 표시되고, 이 칸에는 직접 입력한 원문만 둔다."}
            count={merchantReviews.length ? `${merchantReviews.length}건` : undefined}>
            <textarea rows={8} value={form.reviewsText} onChange={set("reviewsText")}
              placeholder={"원두를 매주 바꿔서 소개해주는 게 좋아요.\n2층 창가 자리가 조용해서 작업하기 좋았습니다.\n…"} />
          </Field>

          <Field label="사진 URL"
            hint={`한 줄에 하나. 앞의 ${VISION_MAX}장만 vision 분석에 쓰인다. 공개 접근 가능한 URL 이어야 한다.`}
            count={images.length ? `${images.length}장` : undefined}>
            <textarea rows={3} value={form.imagesText} onChange={set("imagesText")}
              placeholder={"https://…/store-1.jpg\nhttps://…/menu.jpg"} />
          </Field>

          {badImages.length > 0 && (
            <div className="warn">http/https 로 시작하지 않는 줄 {badImages.length}개는 전송에서 제외된다.</div>
          )}
          {images.filter(isHttp).length > 0 && (
            <div className="thumbs">
              {images.filter(isHttp).map((u, i) => <Thumb key={u + i} url={u} used={i < VISION_MAX} />)}
            </div>
          )}
          {images.length > 0 && (
            <div className="note">
              PoC 내부 검증용 미리보기다. 크롤링해 온 원본 사진은 고객 노출 화면에 직접 서빙하지 않는다 —
              상용은 점주 제공 이미지가 원칙이다.
            </div>
          )}

          <Field label="메뉴"
            hint="한 줄에 하나 — 품목과 가격을 적힌 그대로. 지도 메뉴탭도 공식 API 가 없어 붙여넣기다. 없는 품목·가격은 생성기가 지어내지 않는다."
            count={menu.length ? `${menu.length}개` : undefined}>
            <textarea rows={4} value={form.menuText} onChange={set("menuText")}
              placeholder={"오늘의 드립 6,000원\n말차 라떼 6,500원"} />
          </Field>

          <Field label="키워드(선택)"
            hint="쉼표로 구분. 넣으면 리뷰 빈도 추출 대신 이 값이 톤앤매너 키워드로 쓰인다."
            count={keywords.length ? `${keywords.length}개` : undefined}>
            <input value={form.keywordsText} onChange={set("keywordsText")} placeholder="예: 산미, 조용함, 말차" />
          </Field>

          {reviews.length === 0 && images.length === 0 && menu.length === 0 && (
            <div className="warn">
              리뷰·사진·메뉴가 모두 비어 있다. 근거가 없으면 가게 특성이 빠진 일반론이 나온다.
            </div>
          )}

          {commercialMode && (
            <div className="consentbox">
              <Field label="조직 API 키" required
                hint="발급된 sk_spaceos_… 키. 요청 헤더에만 사용하며 브라우저 저장소에 보관하지 않는다.">
                <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                  autoComplete="off" placeholder="sk_spaceos_…" />
              </Field>
              <label className="consent">
                <input type="checkbox" checked={rightsConfirmed}
                  onChange={(e) => setRightsConfirmed(e.target.checked)} />
                점주 제공 데이터이며 리뷰·사진·메뉴를 제공하고 처리할 권한이 있음을 확인한다.
              </label>
              <label className="consent">
                <input type="checkbox" checked={processingConsent}
                  onChange={(e) => setProcessingConsent(e.target.checked)} />
                Program 마케팅 생성 목적으로 입력을 처리하는 데 동의한다.
              </label>
              <label className="consent">
                <input type="checkbox" checked={externalConsent}
                  onChange={(e) => setExternalConsent(e.target.checked)} />
                설정된 경우 외부 LLM의 텍스트·이미지 처리 경로를 사용할 수 있음에 동의한다.
              </label>
              <label className="consent">
                <input type="checkbox" checked={retentionAcknowledged}
                  onChange={(e) => setRetentionAcknowledged(e.target.checked)} />
                원문은 애플리케이션 DB에 저장하지 않고, 조직·계약 버전·항목별 건수만 감사기록에 남음을 확인한다.
              </label>
            </div>
          )}

          <button type="submit" className="primary" disabled={!canSubmit}>
            {busy ? `생성 중… ${elapsed}초` : commercialMode ? "동의하고 상용 생성" : "마케팅 솔루션 생성"}
          </button>
          {busy && <div className="note">Claude 실호출은 사진 포함 시 10~20초 걸린다.</div>}
        </form>

        {/* ── 결과 ── */}
        <div className="panel">
          <div className="ptitle">생성 결과</div>

          {error && (
            <div className="err">
              <strong>생성에 실패했습니다.</strong>
              <div>백엔드가 떠 있는지 확인하세요 — <code>cd apps/backend && uvicorn app.main:app --reload</code></div>
              <div className="errdetail">{error}</div>
            </div>
          )}

          {!error && !result && !busy && (
            <div className="empty">
              왼쪽에 가게 프로필을 넣고 <b>마케팅 솔루션 생성</b>을 누르면 여기에 결과가 나온다.
              <div className="empty-sub">처음이라면 <b>예시 채우기</b>로 한 번 돌려보면 된다.</div>
            </div>
          )}

          {busy && <div className="empty">생성 중… {elapsed}초</div>}

          {result && !busy && <Result r={result} />}
          {onboardingReceipt && !busy && (
            <div className="receipt">
              상용 입력 동의 영수증 <code>{onboardingReceipt}</code> · 원문 DB 저장 없음
            </div>
          )}
        </div>
      </div>

      <div className="foot">
        Program 1단계(가게 단위) · 백엔드 <code>POST /api/v1/marketing/generate</code> ·
        상권 단위(2단계)는 <b>주요 Platform</b> 탭의 거점 심층에서 볼 수 있다.
      </div>
    </div></div>
  );
}

/* ───────────── 결과 ───────────── */

function Result({ r }: { r: StoreMarketing }) {
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
          <div className="rname">{r.store_name}</div>
          <div className="rcat">{r.category}</div>
        </div>
        <span className={`srcbadge ${stub ? "is-syn" : "is-gold"}`}
          title={stub
            ? "LLM_API_KEY 미설정이거나 호출이 실패해 규칙 기반 스텁으로 응답했다"
            : "Claude 실호출로 생성된 결과다"}>
          {stub ? "규칙 기반 폴백" : "LLM 생성"}
        </span>
      </div>

      {/* 스텁이 나온 이유가 둘이다. 크레딧·키 문제와 "생성은 됐는데 검증에 걸렸다"를
          같은 문구로 보여주면 엉뚱한 데를 고치게 된다. */}
      {stub && blocked.length > 0 && (
        <div className="warn">
          LLM 이 생성한 결과가 <b>Humanistic Authority 검증에 걸려 폐기</b>됐다 — 아래는 그
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
          LLM 을 타지 못해 <b>규칙 기반 스텁</b>이 나왔다 — 리뷰·사진을 읽은 결과가 아니다.
          <code>LLM_API_KEY</code>(로컬은 <code>apps/backend/.env</code>, 배포는 Vercel 환경변수),
          Anthropic 크레딧 잔액, 백엔드 로그를 확인하라.
        </div>
      )}

      {/* 경고는 사전 매칭이라 오탐이 섞인다. 지우지 않고 근거를 함께 보여 사람이 판단하게 한다. */}
      {!stub && warnings.length > 0 && (
        <div className="hawarn">
          <b>HA 검증 경고 {warnings.length}건</b> — 아래 생성물은 살아 있다. 사전 매칭이라
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

      {r.tone_keywords.length > 0 && (
        <>
          <div className="rlabel">톤앤매너 키워드</div>
          <div className="chips">{r.tone_keywords.map((k, i) => <span key={i} className="chip">{k}</span>)}</div>
        </>
      )}

      <div className="rlabel">온라인 <em>{r.online.length}건</em></div>
      <div className="plans">{r.online.map((p, i) => <Plan key={i} p={p} />)}</div>

      <div className="rlabel">오프라인 <em>{r.offline.length}건</em></div>
      <div className="plans">{r.offline.map((p, i) => <Plan key={i} p={p} />)}</div>

      {/* 자기신고와 서버 검증을 나란히 두되 섞지 않는다 — 아래 문장은 LLM 이 스스로
          적은 것이고, 그게 사실인지는 서버(ha_guard)가 따로 판정한다. */}
      <div className="rlabel">Humanistic Authority 자체점검 <em>LLM 이 적은 문장이다</em></div>
      <div className="ha">{r.ha_check}</div>
      {!stub && warnings.length === 0 && (
        <div className="note">서버 후처리 검증(금액·트렌드 방향·최상급·비방·채널 균형) 통과.</div>
      )}
    </div>
  );
}

function Plan({ p }: { p: ChannelPlan }) {
  return (
    <div className={`plan is-${p.kind}`}>
      <div className="pchannel">{p.channel}</div>
      <div className="pcontent">{p.content}</div>
      <div className="prationale"><b>근거</b> {p.rationale}</div>
    </div>
  );
}

/* ───────────── 조각 ───────────── */

function Field({ label, required, hint, count, children }: {
  label: string; required?: boolean; hint?: string; count?: string; children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span className="flabel">
        {label}{required && <i>*</i>}
        {count && <em>{count}</em>}
      </span>
      {children}
      {hint && <span className="fhint">{hint}</span>}
    </label>
  );
}

/** 사진 미리보기. 브라우저가 못 불러오는 URL 은 백엔드(Claude vision)도 대개 못 불러온다 —
 *  크레딧을 쓰기 전에 여기서 걸러내라고 실패 상태를 그대로 보여준다. */
function Thumb({ url, used }: { url: string; used: boolean }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={`thumb${used ? "" : " unused"}${failed ? " failed" : ""}`}
      title={used ? url : `${url}\n(vision 분석에는 앞 ${VISION_MAX}장만 쓰인다)`}>
      {failed
        ? <span className="thumbx">불러올 수 없음</span>
        : <img src={url} alt="" onError={() => setFailed(true)} />}
    </div>
  );
}
