import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import type { TrackKey } from "@/design/tokens/colors";
import PageDashboard from "@/pages/PageDashboard";
import AdminCoverage from "@/pages/AdminCoverage";
import MapHost from "@/components/MapHost";
import TrackMapFrame from "@/components/TrackMapFrame";
import BusinessSetup from "@/components/BusinessSetup";
import { listDistricts, listIndustries, type DistrictSummary, type IndustryOption } from "@/lib/api";
import { businessChipText, findIndustry, loadBusiness, saveBusiness, type BusinessProfile, type BusinessState } from "@/lib/businessProfile";
import { createPageWorkspace, type BuildingSelection, type ProgramHandoff } from "@/lib/workspaceState";
import "./App.css";

// 네 트랙 화면은 전부 지도 위 오버레이다. 지도 SDK 는 MapHost 가 받지만, 화면마다
// 거리뷰·층 스택·차트 같은 무거운 자식이 있어 청크를 나눈다.
const loadMapShell = () => import("@/pages/MapShell");
const loadPlatform = () => import("@/pages/PlatformConsole");
const loadPosting = () => import("@/pages/PostingConsole");
const loadProgram = () => import("@/pages/ProgramStudio");
const MapShell = lazy(loadMapShell);
const PlatformConsole = lazy(loadPlatform);
const PostingConsole = lazy(loadPosting);
const ProgramStudio = lazy(loadProgram);

/** 첫 화면이 선 뒤 나머지 트랙 청크를 미리 받아 둔다(2026-09-13 로컬 실화면 확인).
 *  아직 안 받은 트랙 탭을 누르면 React 가 Suspense 폴백을 띄우는 동안 **이전 탭 화면을 지우지 않고
 *  숨긴 채** 둔다 — 지도 표식은 DOM 이 아니라 SDK 객체라 숨겨지지 않아, 느린 망에서는
 *  "화면 불러오는 중…" 아래로 이전 트랙의 칩·선이 그대로 보였다. 미리 받아 두면 탭 전환이
 *  멈추지 않아 그 틈이 생기지 않는다. 첫 화면 로딩을 방해하지 않게 잠시 뒤에 받는다. */
const PRELOAD_DELAY_MS = 1500;

/**
 * PlaceOS 프론트엔드 진입점.
 * TODO: react-router 도입 시 /platform, /page, /posting, /program 으로 분리.
 *
 * 2026-08-29: **PPPP 네 트랙이 각자 화면을 갖는다.**
 *   Platform → PlatformConsole  (상권 정체성 + 자리별 업종)
 *   Page     → MapShell         (공실 히트맵 4레이어 + 2D 층 스택·거리뷰)
 *   Posting  → PostingConsole   (3-Tier 비용-효용 + 권리금 입력 계약)
 *   Program  → ProgramStudio    (검증 program 생성 — 팝업·가오픈·MVP)
 *
 * 2026-08-29: 상단 네비바를 **좌측 아이콘 레일**로 옮겼다(네이버지도식).
 *
 * 2026-09-13: 레일에서 **서울·거점 두 탭을 뺐다.** 레일에는 PPPP 네 트랙만 남는다.
 *   · 서울(SeoulDashboard) — 25구 로드맵 표. 거점 선택은 이미 네 트랙 화면마다 있는
 *     상권 선택기가 하고 있어 따로 둘 이유가 없었다.
 *   · 거점(HubExplorer) — 거점 목록 + 실측 범위 경계. 경계 그리기(`lib/hubBoundary`)는
 *     Platform 지도가 이어받았다("이 상권이 어디까지인가"는 Platform 의 질문이다).
 *
 * 2026-09-13: **네 트랙 모두 지도 전체화면이다.** 그전에는 Page 만 지도 위에 살고
 *   Platform·Posting·Program 은 지도가 없는 대시보드였다. 이제 넷 다 같은 지도(MapHost)
 *   위에 좌측 패널로 뜨고(TrackMapFrame), 각자 자기 답을 지도에 그린다 —
 *   Platform=실측 범위·자리별 추천 / Page=공실·임대시세 / Posting=입점 자리와 월임대료 /
 *   Program=검증할 자리·오프라인 연계 행사.
 *   상권 선택도 **네 트랙이 하나를 공유한다.** 같은 place 에 대한 네 질문이라, 탭을 옮길
 *   때마다 상권을 다시 고르게 하면 흐름이 끊긴다.
 *
 * 2026-09-13(화면설계서 3판): **「내 사업」을 네 트랙이 공유한다.** 주요 고객이 상권을 먼저 고르는
 *   분석가에서 업종·지금 가게에서 출발하는 사업자(창업 · 업종 바꾸기 · 상권 옮기기)로 바뀌었다.
 *   상권과 같은 급의 공유 값이라 여기 둔다 — 처음 방문이면 Page 지도 위에 카드를 펴고,
 *   「시작」하면 Platform 으로 넘어가 「내 업종으로 본 상권」부터 답한다.
 *
 * #admin 해시는 관리자 커버리지 패널로 간다. 네비게이션에 버튼을 두지 않는다 —
 * 지도에서 제외된 건물 수는 공개 대상이 아니다(2026-07-26). 데이터 자체도
 * X-Admin-Token 이 있어야 오므로 해시를 안다고 값이 보이지는 않는다.
 */
type View = "platform" | "map" | "posting" | "program";

/* 레일이 **어느 트랙인지 색으로** 말한다(2026-09-06). 값은 CSS 가 --track-* 토큰에서
   가져오고(App.css), 여기서는 **이름만** 넘긴다(색 하드코딩 금지 — design skill 규칙).
   ⚠ view key 와 track 이름은 하나만 어긋난다 — Page 트랙의 화면 key 는 "map" 이다. */
const NAV: { key: View; label: string; icon: JSX.Element; track: TrackKey }[] = [
  // PPPP 네 트랙. 전통 4P 와 1:1 대응한다(2026-09-05 재정의): Place▶Platform · Product▶Page ·
  // Price▶Posting · Promotion▶Program. 라벨을 되돌리지 말 것.
  // 2026-09-15: 레일 순서는 **Page → Platform → Posting → Program** 이다. 프레임워크 순서
  //   (Platform → Page → …)와 일부러 다르다 — 사용자가 실제로 밟는 순서를 따른다. 첫 화면이
  //   Page 지도이고, 거기서 「내 사업」을 「시작」하면 Platform 으로 넘어간다(화면설계서 3판).
  { key: "map", label: "Page", icon: <IconPin />, track: "page" },
  { key: "platform", label: "Platform", icon: <IconSpark />, track: "platform" },
  { key: "posting", label: "Posting", icon: <IconKey />, track: "posting" },
  { key: "program", label: "Program", icon: <IconMegaphone />, track: "program" },
];

export default function App() {
  // 첫 화면은 **Page 지도**다(2026-09-12). 되돌리려면 이 한 줄만 바꾼다.
  const [view, setView] = useState<View>("map");
  const [pageWorkspace, setPageWorkspace] = useState(createPageWorkspace);
  const [postingSelection, setPostingSelection] = useState<(BuildingSelection & { requestId: number })>();
  const reviewBuilding = (selection: BuildingSelection) => {
    setPostingSelection((previous) => ({ ...selection, requestId: (previous?.requestId ?? 0) + 1 }));
    setView("posting");
  };
  // 네 트랙이 공유하는 상권. 단일 출처는 Page 작업공간이다 — 거점을 바꾸면 Page 의
  // 검색·선택이 비워지는 규칙(MapShell setDistrictId)을 다른 트랙에서 바꿔도 똑같이 지킨다.
  const districtId = pageWorkspace.districtId;
  const setDistrictId = useCallback((id: string) => {
    setPageWorkspace((w) => (w.districtId === id ? w
      : { ...w, districtId: id, query: "", status: "all", selectedId: null }));
  }, []);
  // ── 트랙 간 인계(화면설계서 2판 인계 표) ─────────────────────────────────────
  // Platform → Page: 그 건물을 Page 에서 연다. 상권·선택 건물은 Page 작업공간 하나에 쓰고,
  // 검색어·상태 필터는 비운다 — 조건에 걸려 넘겨받은 건물이 목록에서 안 보이면 안 된다.
  const openInPage = useCallback((selection: BuildingSelection) => {
    setPageWorkspace((w) => ({
      ...w, districtId: selection.districtId, selectedId: selection.buildingId, query: "", status: "all",
    }));
    setView("map");
  }, []);
  // Posting → Program: 인계마다 requestId 를 올려 Program 을 새로 마운트한다(초기값으로만 채운다).
  const [programHandoff, setProgramHandoff] = useState<(ProgramHandoff & { requestId: number; dismissed?: boolean })>();
  const makeProgram = useCallback((handoff: ProgramHandoff) => {
    setProgramHandoff((prev) => ({ ...handoff, requestId: (prev?.requestId ?? 0) + 1 }));
    setView("program");
  }, []);
  // 「비우기」 등으로 안내를 걷으면 표시만 끈다. key(requestId)는 그대로 둬 지금 화면을 다시 마운트하지 않는다.
  const dismissArrival = useCallback(() => {
    setProgramHandoff((h) => (h && !h.dismissed ? { ...h, dismissed: true } : h));
  }, []);

  // ── 「내 사업」(화면설계서 3판 공통 프레임) ───────────────────────────────────
  const [business, setBusiness] = useState<BusinessState>(loadBusiness);
  const [bizOpen, setBizOpen] = useState(() => business.status === "unset");
  const [industries, setIndustries] = useState<IndustryOption[] | null | "error">(null);
  // 상권 목록은 카드(지금 가게 상권)와 칩 문구(지금 상권 이름)에만 쓴다 — 필요할 때 한 번만 받는다.
  // 요약 응답은 상권마다 격자를 다시 계산해 무겁다(services/business_fit._served 독스트링).
  const [bizDistricts, setBizDistricts] = useState<DistrictSummary[]>([]);
  const profile = business.status === "set" ? business.profile : null;
  const needDistricts = bizOpen || !!profile?.homeDistrictId;
  useEffect(() => {
    let alive = true;
    listIndustries().then((r) => alive && setIndustries(r.industries)).catch(() => alive && setIndustries("error"));
    return () => { alive = false; };
  }, []);
  useEffect(() => {
    if (!needDistricts || bizDistricts.length) return;
    let alive = true;
    listDistricts()
      .then((all) => alive && setBizDistricts(all.filter((d) => d.vacancy_source === "gold")))
      .catch(() => { /* 카드의 상권 칸만 비활성 — 목적·업종은 계속 고를 수 있다 */ });
    return () => { alive = false; };
  }, [needDistricts, bizDistricts.length]);
  const [bizAnnounce, setBizAnnounce] = useState("");
  const startBusiness = useCallback((next: BusinessProfile) => {
    const state: BusinessState = { status: "set", profile: next };
    setBusiness(state);
    saveBusiness(state);
    setBizOpen(false);
    if (next.homeDistrictId) setDistrictId(next.homeDistrictId);
    setBizAnnounce(`${businessChipText(state, Array.isArray(industries) ? industries : null, bizDistricts)}로 설정됨`);
    setView("platform");
  }, [industries, bizDistricts, setDistrictId]);
  const browse = useCallback(() => {
    const state: BusinessState = { status: "browsing" };
    setBusiness(state);
    saveBusiness(state);
    setBizOpen(false);
  }, []);
  const myIndustry = findIndustry(Array.isArray(industries) ? industries : null, profile?.industryKey);
  // Platform 업종 바꾸기 표 → Posting 업종칸(인계 표 「Platform → Posting」).
  const [postingIndustry, setPostingIndustry] = useState<{ input: string; requestId: number }>();
  const tryIndustry = useCallback((input: string) => {
    setPostingIndustry((prev) => ({ input, requestId: (prev?.requestId ?? 0) + 1 }));
    setView("posting");
  }, []);
  useEffect(() => {
    const t = window.setTimeout(() => {
      // 실패해도 조용히 넘어간다 — 그 탭을 누를 때 lazy 가 다시 받는다.
      for (const load of [loadMapShell, loadPlatform, loadPosting, loadProgram]) load().catch(() => {});
    }, PRELOAD_DELAY_MS);
    return () => window.clearTimeout(t);
  }, []);
  const [isAdmin, setIsAdmin] = useState(() => window.location.hash === "#admin");
  const [isBoard, setIsBoard] = useState(() => window.location.hash === "#board");

  useEffect(() => {
    const onHash = () => {
      setIsAdmin(window.location.hash === "#admin");
      setIsBoard(window.location.hash === "#board");
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (isAdmin) return <AdminCoverage />;
  // #board 는 종전 거점 보드(PageDashboard). 층별 매물·입점·마케팅 섹션이 아직 다른
  // 화면으로 다 옮겨지지 않아 지우지 않고 해시로 남겼다. TODO: 이사가 끝나면 뺀다.
  if (isBoard) return <PageDashboard />;

  return (
    // 네 트랙 모두 지도 뷰라 셸은 늘 문서 스크롤을 잠근다(패널이 스스로 스크롤한다).
    <div className="appshell is-map">
      <nav className="rail" aria-label="주요 화면">
        {/* 2026-09-13: 로고 자리를 "S" 한 글자에서 **PlaceOS** 워드마크로 바꿨다.
            "S"는 SpaceOS 시절의 머리글자라 개명(09-12) 뒤로는 틀린 글자였다. */}
        <div className="rail-logo" title="PlaceOS" aria-label="PlaceOS">
          <span className="rail-logo-mark" aria-hidden>P</span>
          <span className="rail-logo-word">PlaceOS</span>
        </div>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={"rail-btn" + (view === n.key ? " active" : "")}
            data-track={n.track}
            aria-current={view === n.key ? "page" : undefined}
            onClick={() => setView(n.key)}
          >
            {n.icon}
            <span>{n.label}</span>
          </button>
        ))}
      </nav>

      {/* 지도는 앱 수명 동안 **하나**다. 탭이 바뀌어도 언마운트하지 않고 오버레이만
          갈아끼운다 — 그래야 사용자가 맞춰 둔 중심·줌이 탭 왕복에도 남는다. */}
      <MapHost active>
        <Suspense fallback={<div className="map-loading">화면 불러오는 중…</div>}>
          {view === "platform" && (
            <TrackMapFrame track="platform" label="상권 정체성">
              <PlatformConsole districtId={districtId} onDistrictChange={setDistrictId} onOpenInPage={openInPage}
                business={profile} industries={Array.isArray(industries) ? industries : null}
                onOpenBusiness={() => setBizOpen(true)} onTryIndustry={tryIndustry} />
            </TrackMapFrame>
          )}
          {view === "map" && <MapShell workspace={pageWorkspace} onWorkspaceChange={setPageWorkspace} onReview={reviewBuilding}
            myIndustry={myIndustry} />}
          {view === "posting" && (
            <TrackMapFrame track="posting" label="입점 계산">
              <PostingConsole selection={postingSelection} districtId={districtId} onDistrictChange={setDistrictId}
                onMakeProgram={makeProgram} defaultIndustry={myIndustry?.input} industryRequest={postingIndustry} />
            </TrackMapFrame>
          )}
          {view === "program" && (
            <TrackMapFrame track="program" label="검증 program">
              <ProgramStudio key={programHandoff?.requestId ?? "direct"} mapDistrictId={districtId}
                handoff={programHandoff?.dismissed ? undefined : programHandoff} onArrivalDismiss={dismissArrival}
                defaultCategory={myIndustry?.input} businessGoal={profile?.goal} />
            </TrackMapFrame>
          )}
        </Suspense>
        <BusinessSetup state={business} industries={industries} districts={bizDistricts} districtId={districtId}
          open={bizOpen} onOpenChange={setBizOpen} onStart={startBusiness} onBrowse={browse} />
      </MapHost>
      <span className="sr-only" aria-live="polite">{bizAnnounce}</span>
    </div>
  );
}

/* 레일 아이콘 — 라이브러리를 더 붙이지 않는다(지도 SDK 만으로도 이미 무겁다).
   currentColor 라 활성/비활성 색이 버튼 상태 하나로 따라온다. */
const SVG = {
  fill: "none", stroke: "currentColor", strokeWidth: 1.7,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24", "aria-hidden": true,
};

/* Platform — 모델(LSTM·GNN) 축을 뜻하는 노드+스파크 */
function IconSpark() {
  return (
    <svg {...SVG}>
      <circle cx="6" cy="17" r="2.2" />
      <circle cx="12.5" cy="9" r="2.2" />
      <circle cx="19" cy="15" r="2.2" />
      <path d="m7.6 15.3 3.5-4.4m3 .3 3.3 3" />
    </svg>
  );
}

function IconPin() {
  return (
    <svg {...SVG}>
      <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.6" />
    </svg>
  );
}

/* Posting — 빈 자리에 들어간다는 뜻의 열쇠 */
function IconKey() {
  return (
    <svg {...SVG}>
      <circle cx="8" cy="15" r="3.4" />
      <path d="m10.5 12.5 8-8" />
      <path d="m16.5 6.5 2 2" />
      <path d="m14 9 2 2" />
    </svg>
  );
}

function IconMegaphone() {
  return (
    <svg {...SVG}>
      <path d="M4 10v4a1 1 0 0 0 1 1h3l7 4V5L8 9H5a1 1 0 0 0-1 1Z" />
      <path d="M18.5 9.5a3.5 3.5 0 0 1 0 5" />
    </svg>
  );
}
