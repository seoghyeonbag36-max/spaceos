// 공실 위험도 마커 — 네이버 지도 위 커스텀 오버레이. vacancy 색계열 사용.
import React from "react";
import { colors } from "../tokens/colors";

// level: 0(저위험)~4(고위험)
export function MapMarkerPin({ level = 0, label }: { level?: 0 | 1 | 2 | 3 | 4; label?: string }) {
  const c = colors.vacancy[level];
  return (
    <div className="flex flex-col items-center" style={{ filter: "drop-shadow(0 2px 6px rgba(0,0,0,.25))" }}>
      <div className="px-2 h-6 rounded-pill flex items-center text-white text-[11px] font-semibold"
           style={{ background: c, borderRadius: 999 }}>
        {label ?? ""}
      </div>
      <div style={{ width: 0, height: 0, borderLeft: "6px solid transparent",
        borderRight: "6px solid transparent", borderTop: `8px solid ${c}` }} />
    </div>
  );
}
