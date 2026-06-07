import { useState } from "react";
import CityDashboard from "@/pages/CityDashboard";
import DistrictPPPP from "@/pages/DistrictPPPP";
import SeoulDashboard from "@/pages/SeoulDashboard";

/**
 * SpaceOS 프론트엔드 진입점.
 * 도시 전환: 고양시(거점 대시보드 ↔ 거점 PPPP 심층) ↔ 서울(25구 진입 로드맵).
 * 고양 대시보드에서 거점 클릭 → districtId 전달 → 해당 거점 심층 뷰 오픈.
 * TODO: react-router 도입 시 /goyang, /goyang/d/:id, /seoul 로 분리.
 */
type City = "goyang" | "seoul";
type GoyangView = "dashboard" | "district";

export default function App() {
  const [city, setCity] = useState<City>("goyang");
  const [view, setView] = useState<GoyangView>("dashboard");
  const [districtId, setDistrictId] = useState("lafesta");

  return (
    <div>
      <nav style={{
        position: "sticky", top: 0, zIndex: 1000, display: "flex", gap: 8, alignItems: "center",
        padding: "10px 20px", background: "#fff", borderBottom: "1px solid #e5e7eb",
        fontFamily: "'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif",
      }}>
        <strong style={{ fontSize: 14, letterSpacing: "-.3px", marginRight: 6 }}>SpaceOS</strong>
        <NavBtn label="고양시" active={city === "goyang"} onClick={() => setCity("goyang")} />
        <NavBtn label="서울" active={city === "seoul"} onClick={() => setCity("seoul")} />
        {city === "goyang" && (
          <>
            <span style={{ width: 1, height: 18, background: "#e5e7eb", margin: "0 4px" }} />
            <NavBtn label="거점 대시보드" active={view === "dashboard"} onClick={() => setView("dashboard")} />
            <NavBtn label="거점 PPPP 심층" active={view === "district"} onClick={() => setView("district")} />
          </>
        )}
      </nav>
      {city === "seoul" ? (
        <SeoulDashboard />
      ) : view === "dashboard" ? (
        <CityDashboard onOpenDistrict={(id) => { setDistrictId(id); setView("district"); }} />
      ) : (
        <DistrictPPPP districtId={districtId} />
      )}
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
