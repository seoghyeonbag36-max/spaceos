// 공실 히트맵 범례 — vacancy 색계열 설명 (저위험→고위험)
import { colors } from "../tokens/colors";
const labels = ["안전", "양호", "주의", "위험", "고위험"];
export function VacancyLegend() {
  return (
    <div className="flex items-center gap-2 bg-surface/90 rounded-md px-3 py-2 shadow-card">
      {colors.vacancy.map((c, i) => (
        <span key={i} className="flex items-center gap-1 text-[11px] text-muted">
          <span style={{ width: 12, height: 12, borderRadius: 3, background: c, display: "inline-block" }} />
          {labels[i]}
        </span>
      ))}
    </div>
  );
}
