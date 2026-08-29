import { lazy, Suspense, useEffect, useState } from "react";
import SeoulDashboard from "@/pages/SeoulDashboard";
import PlatformConsole from "@/pages/PlatformConsole";
import PostingConsole from "@/pages/PostingConsole";
import PageDashboard from "@/pages/PageDashboard";
import AdminCoverage from "@/pages/AdminCoverage";
import ProgramStudio from "@/pages/ProgramStudio";
import "./App.css";

// 지도 뷰는 네이버 지도 SDK·3D 트윈을 끌고 들어와 무겁다 — 눌렀을 때만 받는다.
const MapShell = lazy(() => import("@/pages/MapShell"));

/**
 * SpaceOS 프론트엔드 진입점.
 * 전환: 서울(25구 로드맵) · 거점(54거점 보드+심층) + PPPP 네 서비스.
 * TODO: react-router 도입 시 /seoul, /hubs, /platform, /page, /posting, /program 으로 분리.
 *
 * 2026-08-29: **PPPP 네 트랙이 각자 화면을 갖는다.** 그전까지 Program 만 독립 표면이었고
 * (ProgramStudio) 나머지 셋은 거점 심층 뷰 한 페이지에 네 섹션으로 쌓여 있었다 —
 * 트랙 경계는 API 에 이미 있는데 화면에만 없었다.
 *   Platform → PlatformConsole  (상권 정체성 + 자리별 업종)
 *   Page     → MapShell         (공실 히트맵 4레이어 + 3D 트윈. 종전 "지도" 탭)
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

const NAV: { key: View; label: string; icon: JSX.Element }[] = [
  { key: "seoul", label: "서울", icon: <IconGrid /> },
  { key: "hubs", label: "거점", icon: <IconLayers /> },
  // PPPP 네 트랙 — 순서가 곧 프레임워크 순서다(Platform → Page → Posting → Program)
  { key: "platform", label: "Platform", icon: <IconSpark /> },
  { key: "map", label: "Page", icon: <IconPin /> },
  { key: "posting", label: "Posting", icon: <IconKey /> },
  { key: "program", label: "Program", icon: <IconMegaphone /> },
];

export default function App() {
  const [view, setView] = useState<View>("seoul");
  const [isAdmin, setIsAdmin] = useState(() => window.location.hash === "#admin");

  useEffect(() => {
    const onHash = () => setIsAdmin(window.location.hash === "#admin");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (isAdmin) return <AdminCoverage />;

  // 지도 뷰: MapShell 이 스스로 position:fixed 로 레일 오른쪽 전체를 채운다.
  // 셸은 문서 스크롤만 잠근다(대시보드 두 뷰는 기존대로 창 스크롤 하나만 쓴다 —
  // 내부 overflow 를 두면 스크롤바가 2개로 보인다, 2026-07-24 수정).
  const isMap = view === "map";

  return (
    <div className={"appshell" + (isMap ? " is-map" : "")}>
      <nav className="rail" aria-label="주요 화면">
        <div className="rail-logo" title="SpaceOS">S</div>
        {NAV.map((n) => (
          <button
            key={n.key}
            className={"rail-btn" + (view === n.key ? " active" : "")}
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
        {view === "posting" && <PostingConsole />}
        {view === "hubs" && <PageDashboard />}
        {view === "program" && <ProgramStudio />}
        {isMap && (
          <Suspense fallback={<div style={{ padding: 24, fontSize: 13, color: "#6b7280" }}>지도 불러오는 중…</div>}>
            <MapShell />
          </Suspense>
        )}
      </main>
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
