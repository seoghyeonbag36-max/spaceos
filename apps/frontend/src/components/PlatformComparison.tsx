import { useId, type ReactNode } from "react";
import { Bar } from "@visx/shape";
import type { OpeningSite } from "@/lib/api";
import "./PlatformComparison.css";

/** 자리 비교는 같은 상권에서 고른 응답만 받는다. 점수·평균·차이는 재계산하지 않는다. */
export default function PlatformComparison({ sites, districtName, source, distinctNote }: {
  sites: OpeningSite[]; districtName: string; source: string; distinctNote?: string;
}) {
  const headingId = useId();
  const chartLabelId = useId();
  const validDeltas = sites.flatMap((site) => isProvided(site.distinct?.delta_pp)
    ? [site.distinct!.delta_pp] : []);
  // 이 비율은 화면 좌표만 정한다. 서버가 준 delta_pp와 표시 정밀도는 유지한다.
  const extent = Math.max(0, ...validDeltas.map(Math.abs));
  const rows: Array<{ label: string; value: (site: OpeningSite) => ReactNode }> = [
    { label: "면적", value: (site) => numberOrAbsent(site.area_py, "평") },
    { label: "층", value: (site) => site.floor || "미제공" },
    { label: "재고", value: (site) => numberOrAbsent(site.capacity, "호") },
    { label: "공실률", value: (site) => numberOrAbsent(site.vacancy_rate, "%") },
    { label: "추천 노드까지 거리", value: (site) => numberOrAbsent(site.matched_distance_m, "m", "매칭 거리 미제공") },
    { label: "GNN 추천 점수 (0~1)", value: (site) => site.recommendations.length
      ? <ul className="platform-comparison-recs">{site.recommendations.map((rec) => (
        <li key={rec.industry}>{rec.industry} <b>{numberOrAbsent(rec.score)}</b></li>
      ))}</ul> : "추천 없음" },
    { label: "상권 평균 대비 두드러진 업종", value: (site) => site.distinct?.industry || "미제공" },
    { label: "해당 업종의 자리 점수 (0~1)", value: (site) => numberOrAbsent(site.distinct?.score) },
    { label: "해당 업종의 상권 평균 (0~1)", value: (site) => numberOrAbsent(site.distinct?.district_mean) },
    { label: "상권 평균 대비 차이 (p)", value: (site) => isProvided(site.distinct?.delta_pp)
      ? deltaLabel(site.distinct!.delta_pp) : "차이 미제공" },
    { label: "직전 업종 · 상가정보 분류", value: (site) => site.was || "미제공" },
  ];

  return (
    <section className="platform-comparison" aria-labelledby={headingId}>
      <div className="platform-comparison-heading">
        <h3 id={headingId}>{districtName} · 선택한 {sites.length}곳 근거 비교</h3>
        <p>GNN 점수는 입점 성공 확률이 아닙니다. 직전 업종과 추천 업종은 분류 기준이 다릅니다.</p>
      </div>
      <p className="platform-comparison-source"><b>출처</b> {source}</p>
      {distinctNote && <p className="platform-comparison-note">{distinctNote}</p>}

      <div className="platform-comparison-chart" aria-labelledby={chartLabelId}>
        <h4 id={chartLabelId}>자리별 상권 평균 대비 차이</h4>
        <p>각 자리에서 두드러진 업종의 차이입니다. 업종명과 함께 읽으세요. 단위 p · 공통 눈금</p>
        {validDeltas.length > 0 ? (
          <>
            <div className="platform-comparison-axis" aria-hidden="true">
              <span>{extent ? `−${extent}p` : "0p"}</span><span>0p</span><span>{extent ? `+${extent}p` : "0p"}</span>
            </div>
            <ul>
              {sites.map((site) => {
                const delta = site.distinct?.delta_pp;
                const valid = isProvided(delta);
                const width = valid && extent > 0 ? Math.abs(delta) / extent * 196 : 0;
                return (
                  <li key={site.unit_id}>
                    <div className="platform-comparison-chart-label">
                      <span>{site.name}<small>{site.unit_id} · {site.distinct?.industry || "업종 미제공"}</small></span>
                      <b>{valid ? deltaLabel(delta) : "차이 미제공"}</b>
                    </div>
                    {valid && (
                      <svg viewBox="0 0 400 28" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                        <line x1={200} x2={200} y1={0} y2={28} className="platform-comparison-zero" />
                        <Bar x={delta < 0 ? 200 - width : 200} y={6} width={width} height={16} rx={4}
                          className="platform-comparison-bar" />
                      </svg>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        ) : <p className="platform-comparison-missing">차이 비교에 필요한 값이 없습니다.</p>}
      </div>

      <div className="platform-comparison-scroll" role="region" aria-label="선택한 자리 근거표" tabIndex={0}>
        <table>
          <caption>같은 상권의 자리별 조건과 근거 · 값이 없는 항목은 미제공</caption>
          <thead><tr>
            <th scope="col">비교 항목</th>
            {sites.map((site) => <th key={site.unit_id} scope="col">{site.name}<small>{site.unit_id}</small></th>)}
          </tr></thead>
          <tbody>{rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {sites.map((site) => <td key={site.unit_id}>{row.value(site)}</td>)}
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function isProvided(value: number | null | undefined): value is number {
  return value != null && Number.isFinite(value);
}

function numberOrAbsent(value: number | null | undefined, unit = "", absent = "미제공"): string {
  return isProvided(value) ? `${value}${unit}` : absent;
}

function deltaLabel(value: number): string {
  return `${value > 0 ? "+" : ""}${value}p`;
}
