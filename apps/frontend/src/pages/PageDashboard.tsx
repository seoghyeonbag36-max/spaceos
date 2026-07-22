import { useEffect, useMemo, useRef, useState } from "react";
import {
  listDistricts, getDistrict, getPostings, getMarketing, getVacancyHeatmap,
} from "@/lib/api";
import type {
  DistrictSummary, DistrictDetail, Posting, Marketing, TierScenario, VacancyHeatmap,
} from "@/lib/api";
import { loadNaverMaps } from "@/lib/naverMap";
import "./PageDashboard.css";

/**
 * 서울 Page 거점 대시보드 + 거점 심층 뷰(거점 수는 백엔드 시드에 따라 가변 — 2026-07 기준 19곳).
 * 데이터 출처: 백엔드 단일 소스(/api/v1/commercial-districts — 시드 app/data/seoul_pages.py).
 * 고양 버전(CityDashboard/DistrictPPPP, 정적 모듈)과 달리 서버 API로만 조회한다.
 * TODO: Gold 레이어 적재 후 수치가 실측으로 교체된다(백엔드 TODO와 연동).
 */

// 감성(높을수록 좋음): 낮음 #E03E36 → 높음 #22B07D
export function sentHex(s: number): string {
  return lerpHex([224, 62, 54], [34, 176, 125], clamp01((s - 30) / 55));
}
// 공실률(높을수록 나쁨): 낮음 #22B07D → 높음 #E03E36 (디자인 토큰 vacancy 축과 동일 방향)
export function vacHex(v: number): string {
  return lerpHex([34, 176, 125], [224, 62, 54], clamp01(v / 25));
}
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
function lerpHex(a: number[], b: number[], t: number): string {
  const h = (i: number) => Math.round(a[i] + (b[i] - a[i]) * t).toString(16).padStart(2, "0");
  return `#${h(0)}${h(1)}${h(2)}`;
}

const TIER_LABEL: Record<string, string> = { premium: "고급화", value: "가성비", factory: "공장제" };
const TIER_COLOR: Record<string, string> = { premium: "#8B5CF6", value: "#2E6FB7", factory: "#6b7280" };

export default function PageDashboard() {
  const [summaries, setSummaries] = useState<DistrictSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    listDistricts().then(setSummaries).catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="pagedash"><div className="wrap">
        <div className="err">
          <strong>거점 데이터를 불러오지 못했습니다.</strong>
          <div>백엔드가 실행 중인지 확인하세요 — <code>cd apps/backend && uvicorn app.main:app --reload</code></div>
          <div className="errdetail">{error}</div>
        </div>
      </div></div>
    );
  }
  if (!summaries) return <div className="pagedash"><div className="wrap"><div className="loading">서울 Page 거점 불러오는 중…</div></div></div>;

  const sel = selected ? summaries.find((s) => s.id === selected) : undefined;
  return sel
    ? <DistrictDeep summary={sel} onBack={() => setSelected(null)} />
    : <Board summaries={summaries} onOpen={setSelected} />;
}

/* ───────────── 거점 카드 보드 ───────────── */

function Board({ summaries, onOpen }: { summaries: DistrictSummary[]; onOpen: (id: string) => void }) {
  const kpi = useMemo(() => {
    const n = summaries.length;
    const avg = (f: (s: DistrictSummary) => number) => summaries.reduce((a, s) => a + f(s), 0) / Math.max(1, n);
    return {
      n,
      sent: avg((s) => s.sentiment),
      vac: avg((s) => s.vacancy_rate),
      vacant: summaries.reduce((a, s) => a + s.vacant_units, 0),
      reviews: summaries.reduce((a, s) => a + s.reviews, 0),
    };
  }, [summaries]);

  return (
    <div className="pagedash"><div className="wrap">
      <div className="hd">
        <div>
          <div className="ey">SpaceOS · Platform</div>
          <h1>주요 Platform — 서울 {summaries.length}거점</h1>
          <div className="sub">감성·공실·리뷰·입점 Tier — 백엔드 단일 소스(시드, Gold 교체 예정) · 카드를 누르면 거점 심층으로 이동</div>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi"><div className="l">거점</div><div className="v">{kpi.n}<small>곳</small></div><div className="d">Phase 1~2 자치구 핫플 상권</div></div>
        <div className="kpi"><div className="l">평균 감성지수</div><div className="v" style={{ color: sentHex(kpi.sent) }}>{kpi.sent.toFixed(1)}<small>pt</small></div><div className="d">리뷰·SNS 감성 (시드)</div></div>
        <div className="kpi"><div className="l">평균 공실률</div><div className="v" style={{ color: vacHex(kpi.vac) }}>{kpi.vac.toFixed(1)}<small>%</small></div><div className="d">100m 그리드 합성</div></div>
        <div className="kpi"><div className="l">공실 점포 합계</div><div className="v">{kpi.vacant.toLocaleString()}<small>개</small></div><div className="d">리뷰 {kpi.reviews.toLocaleString()}건 기준</div></div>
      </div>

      <div className="grid">
        {summaries.map((s, i) => (
          <button key={s.id} className="dcard" style={{ borderLeftColor: vacHex(s.vacancy_rate) }} onClick={() => onOpen(s.id)}>
            <div className="dtop">
              <div className="dord">{i + 1}</div>
              <div className="dname">{s.name}</div>
              <div className="dpill">{s.gu}</div>
            </div>
            <div className="dhot">{s.type} · {s.note}</div>
            <Bar k="감성" v={s.sentiment} max={100} color={sentHex(s.sentiment)} text={`${s.sentiment.toFixed(1)}pt`} />
            <Bar k="공실" v={s.vacancy_rate} max={25} color={vacHex(s.vacancy_rate)} text={`${s.vacancy_rate.toFixed(1)}%`} />
            <div className="dmeta">
              <span>리뷰 {s.reviews.toLocaleString()}</span>
              <span>공실 {s.vacant_units}개</span>
              <span className={s.risk_zones > 0 ? "risk" : ""}>위험구역 {s.risk_zones}</span>
              <Pred rate={s.predicted_rate} delta={s.predicted_delta} direction={s.predicted_direction} />
            </div>
            <div className="dtiers">
              {(["premium", "value", "factory"] as const).map((t) => (
                <span key={t} className="tchip" style={{ color: TIER_COLOR[t], borderColor: TIER_COLOR[t] }}>
                  {TIER_LABEL[t]} {s.tier_mix[t]}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>

      <div className="foot">시드 데이터(app/data/seoul_pages.py) — 수집 파이프라인(Gold) 적재 시 실측으로 자동 교체 · SpaceOS PPPP</div>
    </div></div>
  );
}

/** LSTM 다음 분기 공실 예측 배지 — forecast 미배포(null) 시 렌더하지 않음 */
function Pred({ rate, delta, direction }: { rate: number | null; delta: number | null; direction: "up" | "down" | null }) {
  if (rate == null || delta == null) return null;
  const up = direction === "up";
  return (
    <span className="pred" style={{ color: up ? "#c2410c" : "#1d6feb" }}
      title="Platform·LSTM 다음 분기 공실 예측 (홀드아웃 방향정확도 84.6%)">
      예측 {rate.toFixed(1)}% {up ? "▲" : "▼"}{Math.abs(delta).toFixed(1)}
    </span>
  );
}

function Bar({ k, v, max, color, text }: { k: string; v: number; max: number; color: string; text: string }) {
  return (
    <div className="brow">
      <span className="bk">{k}</span>
      <span className="bw"><i style={{ width: `${clamp01(v / max) * 100}%`, background: color }} /></span>
      <span className="bv">{text}</span>
    </div>
  );
}

/* ───────────── 거점 심층 (Platform 감성 · Posting 3-Tier · Program 행사) ───────────── */

/** 100m 공실 히트맵 — 네이버 지도 위에 그리드 셀(Rectangle)을 공실률 색으로 렌더 */
function VacancyMap({ detail }: { detail: DistrictDetail }) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlaysRef = useRef<any[]>([]);
  const [hm, setHm] = useState<VacancyHeatmap | null>(null);
  const [mapErr, setMapErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;

    const clear = () => {
      overlaysRef.current.forEach((o) => o.setMap?.(null));
      overlaysRef.current = [];
    };

    Promise.all([loadNaverMaps(), getVacancyHeatmap(detail.id)])
      .then(([, heat]) => {
        if (!live || !elRef.current) return;
        setHm(heat);
        const naver = (window as any).naver;

        // 지도는 거점 전환 시마다 재생성 (center/zoom 이 거점 정의를 따름)
        mapRef.current?.destroy?.();
        const map = new naver.maps.Map(elRef.current, {
          center: new naver.maps.LatLng(detail.center[0], detail.center[1]),
          zoom: detail.zoom, scaleControl: false, mapDataControl: false,
        });
        mapRef.current = map;

        const info = new naver.maps.InfoWindow({ borderWidth: 0, disableAnchor: true, backgroundColor: "transparent" });

        // 100m 그리드 셀 — lat/lng 는 SW 모서리, dlat/dlng 만큼의 사각형
        heat.cells.forEach((c) => {
          const rect = new naver.maps.Rectangle({
            map,
            bounds: new naver.maps.LatLngBounds(
              new naver.maps.LatLng(c.lat, c.lng),
              new naver.maps.LatLng(c.lat + c.dlat, c.lng + c.dlng),
            ),
            fillColor: vacHex(c.v), fillOpacity: 0.45,
            strokeColor: "#ffffff", strokeOpacity: 0.25, strokeWeight: 1,
            clickable: true,
          });
          naver.maps.Event.addListener(rect, "click", () => {
            info.setContent(
              `<div style="background:#fff;border:1px solid #e5e7eb;border-radius:9px;padding:7px 11px;`
              + `font:700 11.5px 'Pretendard','Malgun Gothic',sans-serif;color:#1f2937;box-shadow:0 2px 8px rgba(0,0,0,.12)">`
              + `공실률 <span style="color:${vacHex(c.v)}">${c.v.toFixed(1)}%</span>`
              + `<span style="color:#6b7280;font-weight:600"> · 점포 ${c.stores} · 공실 ${c.vac_n}</span></div>`,
            );
            info.open(map, new naver.maps.LatLng(c.c_lat, c.c_lng));
          });
          overlaysRef.current.push(rect);
        });
        naver.maps.Event.addListener(map, "click", () => info.close());

        // 역·랜드마크 POI 라벨
        detail.poi.forEach(([lat, lng, label]) => {
          overlaysRef.current.push(new naver.maps.Marker({
            map, position: new naver.maps.LatLng(lat, lng),
            icon: {
              content: `<div style="background:#1f2937;color:#fff;border-radius:7px;padding:2px 8px;`
                + `font:700 10.5px 'Pretendard','Malgun Gothic',sans-serif;white-space:nowrap;`
                + `box-shadow:0 1px 5px rgba(0,0,0,.3)">${label}</div>`,
              anchor: new naver.maps.Point(0, 12),
            },
          }));
        });
      })
      .catch((e) => live && setMapErr(e?.message ?? String(e)));

    return () => { live = false; clear(); mapRef.current?.destroy?.(); mapRef.current = null; };
  }, [detail]);

  if (mapErr) {
    return (
      <div className="mapnotice">
        지도를 표시할 수 없습니다 — {mapErr}
        <div className="mapnotice-sub">.env 의 VITE_NAVER_MAPS_KEY_ID 설정과 NCP 콘솔 Web 서비스 URL(http://localhost:5173) 등록, 백엔드 기동 여부를 확인하세요.</div>
      </div>
    );
  }
  return (
    <div className="mapsec">
      <div ref={elRef} className="mapbox" />
      <div className="maplegend">
        <span className="ml-label">공실률</span>
        <span className="ml-grad" />
        <span className="ml-ticks"><em>0%</em><em>25%+</em></span>
        {hm && (
          <span className="ml-stat">
            평균 <b style={{ color: vacHex(hm.avg_vacancy) }}>{hm.avg_vacancy.toFixed(1)}%</b>
            {" "}<Pred rate={hm.predicted_rate} delta={hm.predicted_delta} direction={hm.predicted_direction} />
            {" "}· 셀 {hm.cells.length} · 점포 {hm.sum_stores.toLocaleString()} · 공실 {hm.sum_vac}
          </span>
        )}
        <span className="ml-hint">셀 클릭 시 상세</span>
      </div>
    </div>
  );
}

function DistrictDeep({ summary, onBack }: { summary: DistrictSummary; onBack: () => void }) {
  const [detail, setDetail] = useState<DistrictDetail | null>(null);
  const [postings, setPostings] = useState<Posting[] | null>(null);
  const [marketing, setMarketing] = useState<Marketing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([getDistrict(summary.id), getPostings(summary.id), getMarketing(summary.id)])
      .then(([d, p, m]) => { if (live) { setDetail(d); setPostings(p); setMarketing(m); } })
      .catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [summary.id]);

  return (
    <div className="pagedash"><div className="wrap">
      <div className="hd">
        <div>
          <button className="back" onClick={onBack}>← 주요 Platform 보드</button>
          <h1>{summary.name}</h1>
          <div className="sub">
            {detail?.sub ?? summary.note} · 공실률 {summary.vacancy_rate.toFixed(1)}%
            {" "}<Pred rate={summary.predicted_rate} delta={summary.predicted_delta} direction={summary.predicted_direction} />
            {" "}· 감성 {summary.sentiment.toFixed(1)}pt · 추천 상위 Tier {summary.rec_top}
          </div>
        </div>
      </div>

      {error && <div className="err"><strong>거점 상세를 불러오지 못했습니다.</strong><div className="errdetail">{error}</div></div>}
      {!error && !detail && <div className="loading">거점 상세 불러오는 중…</div>}

      {detail && (
        <>
          <h2 className="sec">공실 히트맵 <small>Page · 100m 그리드 합성 — 건축물대장/영업상태 정합 시 실측 교체</small></h2>
          <VacancyMap detail={detail} />

          <h2 className="sec">감성 구역 <small>Platform · 리뷰/SNS 구역별 감성</small></h2>
          <div className="zones">
            {detail.zones.map((z) => (
              <div key={z.id} className="zone" style={{ borderTopColor: sentHex(z.s) }}>
                <div className="zhead">
                  <span className="zname">{z.n}</span>
                  <span className="zscore" style={{ color: sentHex(z.s) }}>{z.s.toFixed(1)}</span>
                </div>
                <div className="zmeta">{z.grp} · 리뷰 {z.r.toLocaleString()}건 · {z.d >= 0 ? "▲" : "▼"}{Math.abs(z.d).toFixed(1)}</div>
                <div className="zkw">
                  {z.f.map(([label, delta], i) => <span key={i} className="kw">{label} {delta}</span>)}
                </div>
              </div>
            ))}
          </div>

          {postings && (
            <>
              <h2 className="sec">공실 유닛 · 3-Tier 시나리오 <small>Posting · 비용-효용(월) — 코파일럿 연동 전 폴백</small></h2>
              <div className="units">
                {postings.map((p) => (
                  <div key={p.id} className="unit">
                    <div className="uhead">
                      <span className="uname">{p.n}</span>
                      <span className="upill">{p.floor} · {p.area}평 · 前 {p.was}</span>
                    </div>
                    <div className="umeta">임대료 {p.rent}만원 · 권리금 {p.prem ? `${p.prem.toLocaleString()}만원` : "없음"} · 유동 {p.foot} · {p.persona}</div>
                    <div className="unote">{p.note}</div>
                    <div className="tiers">
                      {Object.values(p.scenarios).map((sc: TierScenario) => (
                        <div key={sc.tier} className={"tier" + (sc.recommended ? " rec" : "")} style={{ borderColor: sc.recommended ? TIER_COLOR[sc.tier] : undefined }}>
                          <div className="tname" style={{ color: TIER_COLOR[sc.tier] }}>{sc.name}{sc.recommended && <em> 추천</em>}</div>
                          <div className="trow"><span>초기투자</span><b>{sc.invest_mn}백만</b></div>
                          <div className="trow"><span>월 순익</span><b className={sc.month_net >= 0 ? "" : "neg"}>{sc.month_net.toLocaleString()}만</b></div>
                          <div className="trow"><span>회수</span><b>{sc.roi_months >= 99 ? "—" : `${sc.roi_months}개월`}</b></div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {marketing && (
            <>
              <h2 className="sec">상권 행사 · 콘텐츠 <small>Program · Humanistic Authority(균형·공생·공감)</small></h2>
              <div className="events">
                {marketing.events.map((ev) => (
                  <div key={ev.id} className="event">
                    <div className="ehead"><span className="eic">{ev.ic}</span><span className="ename">{ev.n}</span><span className="ek2">{ev.k2}</span></div>
                    <div className="ewhen">{ev.when}</div>
                    <div className="edesc">{ev.desc}</div>
                    <div className="eroles">{ev.roles.map((r, i) => <span key={i} className="role">{r}</span>)}</div>
                    <div className="eha">{ev.ha}</div>
                  </div>
                ))}
              </div>
              <div className="insta">
                {marketing.online_contents.map((c, i) => <div key={i} className="ig">📷 {c}</div>)}
              </div>
            </>
          )}
        </>
      )}
    </div></div>
  );
}
