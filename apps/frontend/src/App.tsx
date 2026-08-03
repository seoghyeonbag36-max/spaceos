import { lazy, Suspense, useEffect, useState } from "react";
import SeoulDashboard from "@/pages/SeoulDashboard";
import PageDashboard from "@/pages/PageDashboard";
import AdminCoverage from "@/pages/AdminCoverage";
import ProgramStudio from "@/pages/ProgramStudio";

// 지도 뷰는 네이버 지도 SDK·3D 트윈을 끌고 들어와 무겁다 — 눌렀을 때만 받는다.
const MapShell = lazy(() => import("@/pages/MapShell"));

/**
 * SpaceOS 프론트엔드 진입점.
 * 전환: 서울(25구 로드맵) ↔ 주요 Platform(54거점 대시보드+심층) ↔ 지도(풀스크린 Page)
 *       ↔ Program(가게 단위 마케팅 솔루션 생성).
 * TODO: react-router 도입 시 /seoul, /platforms, /map, /program 으로 분리.
 *
 * #admin 해시는 관리자 커버리지 패널로 간다. 네비게이션에 버튼을 두지 않는다 —
 * 지도에서 제외된 건물 수는 공개 대상이 아니다(2026-07-26). 데이터 자체도
 * X-Admin-Token 이 있어야 오므로 해시를 안다고 값이 보이지는 않는다.
 */
type View = "seoul" | "platforms" | "map" | "program";

export default function App() {
  const [view, setView] = useState<View>("seoul");
  const [isAdmin, setIsAdmin] = useState(() => window.location.hash === "#admin");

  useEffect(() => {
    const onHash = () => setIsAdmin(window.location.hash === "#admin");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (isAdmin) return <AdminCoverage />;

  // 지도 뷰만 레이아웃이 다르다: MapShell 이 position:absolute·inset:0 이라 **위치 지정된**
  // 컨테이너가 있어야 네비바 아래에 갇힌다(없으면 뷰포트를 덮어 상단 오버레이가 가려진다).
  // 대시보드 두 뷰는 기존대로 문서(창) 스크롤 하나만 쓴다 — 내부 overflow 를 두면
  // 스크롤바가 2개로 보인다(2026-07-24 수정).
  const isMap = view === "map";

  return (
    <div style={isMap ? { display: "flex", flexDirection: "column", height: "100dvh" } : undefined}>
      <nav style={{
        position: isMap ? "relative" : "sticky", top: 0, zIndex: 1000,
        display: "flex", gap: 8, alignItems: "center", flex: "0 0 auto",
        padding: "10px 20px", background: "#fff", borderBottom: "1px solid #e5e7eb",
        fontFamily: "'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif",
      }}>
        <strong style={{ fontSize: 14, letterSpacing: "-.3px", marginRight: 6 }}>SpaceOS</strong>
        <NavBtn label="서울" active={view === "seoul"} onClick={() => setView("seoul")} />
        <NavBtn label="주요 Platform" active={view === "platforms"} onClick={() => setView("platforms")} />
        <NavBtn label="지도" active={isMap} onClick={() => setView("map")} />
        <NavBtn label="Program" active={view === "program"} onClick={() => setView("program")} />
      </nav>

      <main style={isMap ? { position: "relative", flex: 1, minHeight: 0 } : undefined}>
        {view === "seoul" && <SeoulDashboard />}
        {view === "platforms" && <PageDashboard />}
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

function NavBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      fontFamily: "inherit", fontSize: 13, fontWeight: 700, cursor: "pointer",
      padding: "7px 13px", borderRadius: 9, border: "1px solid " + (active ? "#3a5a98" : "#e5e7eb"),
      background: active ? "#3a5a98" : "#fafbfc", color: active ? "#fff" : "#6b7280",
    }}>{label}</button>
  );
}
