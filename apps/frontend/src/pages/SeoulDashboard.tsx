import { useState } from "react";
import { SEOUL_DISTRICTS, PHASE_META, PHASE_COLORS, SEOUL_GENERATED_AT } from "@/lib/seoul/districts";
import type { Phase, SeoulDistrict } from "@/lib/seoul/districts";
import "./SeoulDashboard.css";

/**
 * 서울 25개 자치구 진입 로드맵 보드.
 * 데이터 출처: lib/seoul/districts.ts (gold SSOT에서 _build/gen_seoul_fe_data.py로 생성).
 * phase/순서는 PHASE_PLAN 단일 출처. 지도 없이 Phase별 그룹 + 점수바로 표현.
 * TODO: 거점 심층(공실·리뷰·3D)은 서울 데이터 수집 후 onOpenDistrict로 연결.
 */
type Metric = "phase" | "total" | "b2c" | "b2b";
type ValueMetric = Exclude<Metric, "phase">;

const PHASES: Phase[] = [1, 2, 3, 4];
const METRICS: { k: Metric; label: string }[] = [
  { k: "phase", label: "Phase" },
  { k: "total", label: "합산" },
  { k: "b2c", label: "B2C" },
  { k: "b2b", label: "B2B" },
];

const metricVal = (d: SeoulDistrict, m: ValueMetric): number =>
  m === "total" ? d.total : m === "b2c" ? d.sumB2C : d.sumB2B;

// 연(#E9F0F7) → 진(#16365C) 보간
function shade(t: number): string {
  const A = [233, 240, 247];
  const B = [22, 54, 92];
  const h = (i: number) => Math.round(A[i] + (B[i] - A[i]) * t).toString(16).padStart(2, "0");
  return `#${h(0)}${h(1)}${h(2)}`;
}

export default function SeoulDashboard() {
  const [metric, setMetric] = useState<Metric>("phase");

  const ranges: Record<ValueMetric, [number, number]> = { total: [0, 0], b2c: [0, 0], b2b: [0, 0] };
  (["total", "b2c", "b2b"] as ValueMetric[]).forEach((m) => {
    const vs = SEOUL_DISTRICTS.map((d) => metricVal(d, m));
    ranges[m] = [Math.min(...vs), Math.max(...vs)];
  });

  const accent = (d: SeoulDistrict): string => {
    if (metric === "phase") return PHASE_COLORS[d.phase];
    const [lo, hi] = ranges[metric];
    return shade((metricVal(d, metric) - lo) / ((hi - lo) || 1));
  };

  const metricUnit = metric === "total" ? "합산(/32)" : metric === "b2c" ? "B2C(/16)" : "B2B(/16)";

  return (
    <div className="seouldash">
      <div className="wrap">
        <div className="hd">
          <div>
            <div className="ey">SpaceOS · Seoul Rollout</div>
            <h1>서울 25개 자치구 진입 로드맵</h1>
            <div className="sub">4기준×2대상 점수 모델 · Phase = 진입 계획(PHASE_PLAN) · 색상 기준 전환</div>
          </div>
          <div className="toggle">
            {METRICS.map((m) => (
              <button key={m.k} className={metric === m.k ? "on" : ""} onClick={() => setMetric(m.k)}>{m.label}</button>
            ))}
          </div>
        </div>

        <div className="kpis">
          {PHASES.map((p) => (
            <div className="kpi" key={p} style={{ borderTopColor: PHASE_META[p].color }}>
              <div className="l">{PHASE_META[p].label}</div>
              <div className="v">{PHASE_META[p].count}<small>개 구</small></div>
              <div className="d">진입 {PHASE_META[p].range[0]}~{PHASE_META[p].range[1]}번</div>
            </div>
          ))}
        </div>

        {metric !== "phase" && (
          <div className="legend">
            <span><i style={{ background: shade(0) }} />낮음</span>
            <span><i style={{ background: shade(0.5) }} />중간</span>
            <span><i style={{ background: shade(1) }} />높음</span>
            <span style={{ color: "#9aa3af" }}>· {metricUnit}</span>
          </div>
        )}

        {PHASES.map((p) => {
          const items = SEOUL_DISTRICTS.filter((d) => d.phase === p);
          return (
            <div key={p}>
              <div className="phase">
                <div className="pbar" style={{ background: PHASE_META[p].color }} />
                <h2>{PHASE_META[p].label}</h2>
                <span className="cnt">· {items.length}개 구</span>
              </div>
              <div className="grid">
                {items.map((d) => (
                  <div className="dcard" key={d.code} style={{ borderLeftColor: accent(d) }}>
                    <div className="dtop">
                      <span className="dord">{d.deployOrder}</span>
                      <span className="dname">{d.name}</span>
                      <span className="dpill" style={{ background: PHASE_COLORS[d.phase] }}>P{d.phase}</span>
                    </div>
                    <div className="dhot">{d.hot}</div>
                    <Bar k="합산" v={d.total} max={32} color="#2f3a4d" />
                    <Bar k="B2C" v={d.sumB2C} max={16} color="#2E6FB7" />
                    <Bar k="B2B" v={d.sumB2B} max={16} color="#E8543B" />
                    <div className="dfoot">점수순위 {d.rank}위 · Phase 내 {d.phaseSeq}번째 진입</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        <div className="foot">
          데이터: gold(SSOT) seoul_district_scores.json · 생성 {SEOUL_GENERATED_AT.slice(0, 10)} · 점수·Phase는 PHASE_PLAN 단일 출처<br />
          거점별 심층(공실·리뷰·3D 트윈)은 서울 데이터 수집 후 연결 예정.
        </div>
      </div>
    </div>
  );
}

function Bar({ k, v, max, color }: { k: string; v: number; max: number; color: string }) {
  return (
    <div className="brow">
      <span className="bk">{k}</span>
      <span className="bw"><i style={{ width: `${(v / max) * 100}%`, background: color }} /></span>
      <span className="bv">{v}/{max}</span>
    </div>
  );
}
