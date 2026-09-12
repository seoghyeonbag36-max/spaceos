import { lazy, Suspense, useEffect, useState } from "react";
import type { TrackKey } from "@/design/tokens/colors";
import SeoulDashboard from "@/pages/SeoulDashboard";
import PlatformConsole from "@/pages/PlatformConsole";
import PostingConsole from "@/pages/PostingConsole";
import PageDashboard from "@/pages/PageDashboard";
import AdminCoverage from "@/pages/AdminCoverage";
import ProgramStudio from "@/pages/ProgramStudio";
import MapHost from "@/components/MapHost";
import { createPageWorkspace, type BuildingSelection } from "@/lib/workspaceState";
import "./App.css";

// 지도 위 오버레이 두 벌 — 지도 SDK 는 MapHost 가 받지만, 이 화면들도 거리뷰·층 스택 등
// 무거운 자식을 끌고 들어오므로 눌렀을 때만 받는다.
const MapShell = lazy(() => import("@/pages/MapShell"));
const HubExplorer = lazy(() => import("@/pages/HubExplorer"));

/**
 * SpaceOS 프론트엔드 진입점.
 * 전환: 서울(25구 로드맵) · 거점(서빙 66거점 보드+심층) + PPPP 네 서비스.
 * TODO: react-router 도입 시 /seoul, /hubs, /platform, /page, /posting, /program 으로 분리.
 *
 * 2026-08-29: **PPPP 네 트랙이 각자 화면을 갖는다.** 그전까지 Program 만 독립 표면이었고
 * (ProgramStudio) 나머지 셋은 거점 심층 뷰 한 페이지에 네 섹션으로 쌓여 있었다 —
 * 트랙 경계는 API 에 이미 있는데 화면에만 없었다.
 *   Platform → PlatformConsole  (상권 정체성 + 자리별 업종)
 *   Page     → MapShell         (공실 히트맵 4레이어 + 2D 층 스택·거리뷰. 종전 "지도" 탭)
 *   Posting  → PostingConsole   (3-Tier 비용-효용 + 권리금 입력 계약)
 *   Program  → ProgramStudio    (가게 단위 마케팅 생성)
 * "주요 Platform" 버튼이 열던 것은 실제로는 거점 보드(PageDashboard)라 **거점**으로
 * 이름을 되돌렸다 — 트랙 이름과 화면 이름이 서로를 가리키고 있었다.
 *
 * 2026-08-29: 상단 네비바를 **좌측 아이콘 레일**로 옮겼다(네이버지도식).
 * 상단 바가 한 줄을 먹으면 지도가 뷰포트 전체를 못 쓰고, 그만큼 오버레이도 밀린다.
 * 레일은 fixed 라 뷰마다 레이아웃 분기를 하지 않는다 — 본문이 margin-left 로 비켜준다.
 *
 * #admin 해시는 관리자 커버리지 패널로 간다. 네비게이션에 버튼을 두지 않는다 —
 * 지도에서 제외된 건물 수는 공개 대상이 아니다(2026-07-26). 데이터 자체도
 * X-Admin-Token 이 있어야 오므로 해시를 안다고 값이 보이지는 않는다.
 */
type View = "seoul" | "hubs" | "platform" | "map" | "posting" | "program";

/* 2026-09-06: 레일이 **어느 트랙인지 색으로** 말한다. 종전엔 활성 버튼이 여섯 개 다
   같은 UI 남색(#3a5a98)이라, 눌린 자리만 알 뿐 트랙은 알 수 없었다.
   track 을 단 넷은 활성일 때 자기 트랙 색으로 칠한다 — 값은 CSS 가 --track-* 토큰에서
   가져오고(App.css), 여기서는 **이름만** 넘긴다(색 하드코딩 금지 — design skill 규칙).
   서울·거점은 트랙이 아니므로 track 이 없다 → 기존 남색 그대로. 그래야 "PPPP 네 개"와
   "그 밖의 화면 둘"이 색으로도 갈린다.
   ⚠ view key 와 track 이름은 하나만 어긋난다 — Page 트랙의 화면 key 는 "map" 이다. */
const NAV: { key: View; label: string; icon: JSX.Element; track?: TrackKey }[] = [
  { key: "seoul", label: "서울", icon: <IconGrid /> },
  { key: "hubs", label: "거점", icon: <IconLayers /> },
  // PPPP 네 트랙 — 순서가 곧 프레임워크 순서다(Platform → Page → Posting → Program).
  // 전통 4P 와 1:1 대응한다(2026-09-05 재정의): Place▶Platform · Product▶Page ·
  // Price▶Posting · Promotion▶Program. 종전엔 Page 가 Product/Price 를 겸하고
  // Posting·Program 이 Promotion 하나를 나눠 가졌다 — 라벨을 되돌리지 말 것.
  { key: "platform", label: "Platform", icon: <IconSpark />, track: "platform" },
  { key: "map", label: "Page", icon: <IconPin />, track: "page" },
  { key: "posting", label: "Posting", icon: <IconKey />, track: "posting" },
  { key: "program", label: "Program", icon: <IconMegaphone />, track: "program" },
];

export default function App() {
  // 첫 화면은 **지도**다(2026-09-12). 그전 기본값은 "seoul"(대시보드)이라, 지도 중심
  // 제품인데 앱을 열면 지도가 한 픽셀도 안 보였다. 대신 비용이 하나 붙는다 —
  // MapHost 가 미루던 지도 SDK 로드를 이제 모든 방문이 첫 화면에서 낸다.
  // 되돌리려면 이 한 줄만 "seoul" 로 바꾼다.
  const [view, setView] = useState<View>("map");
  const [pageWorkspace, setPageWorkspace] = useState(createPageWorkspace);
  const [postingSelection, setPostingSelection] = useState<(BuildingSelection & { requestId: number })>();
  const reviewBuilding = (selection: BuildingSelection) => {
    setPostingSelection((previous) => ({ ...selection, requestId: (previous?.requestId ?? 0) + 1 }));
    setView("posting");
  };
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
  // #board 는 종전 거점 보드(PageDashboard). 「거점」 탭이 HubExplorer 로 바뀌면서
  // 갈 곳을 잃었는데, 층별 매물·입점·마케팅 섹션이 아직 다른 화면으로 다 옮겨지지
  // 않아 지우지 않고 해시로 남겼다. TODO: 세 섹션의 이사가 끝나면 이 화면을 뺀다.
  if (isBoard) return <PageDashboard />;

  // 지도 뷰: 지도는 MapHost 가 position:fixed 로 레일 오른쪽 전체를 채운다.
  // 셸은 문서 스크롤만 잠근다(대시보드 뷰들은 기존대로 창 스크롤 하나만 쓴다 —
  // 내부 overflow 를 두면 스크롤바가 2개로 보인다, 2026-07-24 수정).
  // 2026-09-05: **거점 탭도 지도 뷰다.** 두 탭이 같은 지도 인스턴스를 공유한다.
  const isMap = view === "map" || view === "hubs";

  return (
    <div className={"appshell" + (isMap ? " is-map" : "")}>
      <nav className="rail" aria-label="주요 화면">
        <div className="rail-logo" title="SpaceOS">S</div>
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

      <main className="app-main">
        {view === "seoul" && <SeoulDashboard />}
        {view === "platform" && <PlatformConsole />}
        {view === "posting" && <PostingConsole selection={postingSelection} />}
        {view === "program" && <ProgramStudio />}
      </main>

      {/* 지도는 앱 수명 동안 **하나**다. 탭이 바뀌어도 언마운트하지 않고 오버레이만
          갈아끼운다 — 그래야 사용자가 맞춰 둔 중심·줌이 탭 왕복에도 남는다.
          지도 뷰가 아닐 때는 visibility 로 숨긴다(MapHost.css 참조). */}
      <MapHost active={isMap}>
        <Suspense fallback={<div className="map-loading">지도 화면 불러오는 중…</div>}>
          {view === "hubs" && <HubExplorer />}
          {view === "map" && <MapShell workspace={pageWorkspace} onWorkspaceChange={setPageWorkspace} onReview={reviewBuilding} />}
        </Suspense>
      </MapHost>
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

function IconGrid() {
  return (
    <svg {...SVG}>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.6" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6" />
    </svg>
  );
}

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

function IconLayers() {
  return (
    <svg {...SVG}>
      <path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z" />
      <path d="m3 12.5 9 4.5 9-4.5" />
      <path d="m3 17 9 4.5 9-4.5" />
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
