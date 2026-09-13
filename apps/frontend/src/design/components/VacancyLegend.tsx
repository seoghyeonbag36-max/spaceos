// 공실 히트맵 범례 — vacancy 색계열 설명 (저위험→고위험)
//
// 2026-09-13: BottomSheet 과 같은 이유로 Tailwind 유틸리티 클래스(`flex items-center
// gap-2 bg-surface/90 …`)만 들고 있어 스타일이 걸리지 않았다 → design.css 로 옮겼다.
// 스와치 인라인 스타일만 남긴다(색은 colors.vacancy 배열에서 오는 **데이터**라
// CSS 클래스로 뺄 수 없다 — MapMarkerPin 과 같은 이유).
import { colors } from "../tokens/colors";
import "./design.css";

const labels = ["안전", "양호", "주의", "위험", "고위험"];

export function VacancyLegend() {
  return (
    <div className="ds-legend">
      {colors.vacancy.map((c, i) => (
        <span key={c} className="ds-legend-item">
          <span className="ds-legend-swatch" style={{ background: c }} />
          {labels[i]}
        </span>
      ))}
    </div>
  );
}
