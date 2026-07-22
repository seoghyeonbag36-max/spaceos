import { useState } from "react";
import SeoulDashboard from "@/pages/SeoulDashboard";
import PageDashboard from "@/pages/PageDashboard";

/**
 * SpaceOS 프론트엔드 진입점.
 * 전환: 서울(25구 로드맵) ↔ 주요 Platform(27거점 대시보드+심층).
 * TODO: react-router 도입 시 /seoul, /platforms 로 분리.
 */
type View = "seoul" | "platforms";

export default function App() {
  const [view, setView] = useState<View>("seoul");

  return (
    // 풀높이 flex: 네비바(고정) + 콘텐츠(나머지 전체).
    <div style={{ height: "100dvh", display: "flex", flexDirection: "column" }}>
      <nav style={{
        flex: "0 0 auto", zIndex: 1000, display: "flex", gap: 8, alignItems: "center",
        padding: "10px 20px", background: "#fff", borderBottom: "1px solid #e5e7eb",
        fontFamily: "'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif",
      }}>
        <strong style={{ fontSize: 14, letterSpacing: "-.3px", marginRight: 6 }}>SpaceOS</strong>
        <NavBtn label="서울" active={view === "seoul"} onClick={() => setView("seoul")} />
        <NavBtn label="주요 Platform" active={view === "platforms"} onClick={() => setView("platforms")} />
      </nav>

      <main style={{ flex: 1, minHeight: 0, position: "relative" }}>
        <div style={{ position: "absolute", inset: 0, overflow: "auto" }}>
          {view === "seoul" ? <SeoulDashboard /> : <PageDashboard />}
        </div>
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
