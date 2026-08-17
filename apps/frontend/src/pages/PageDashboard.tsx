import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  listDistricts, getDistrict, getPostings, getMarketing, getVacancyHeatmap, getBuildingVacancy,
} from "@/lib/api";
import type {
  DistrictSummary, DistrictDetail, Posting, Marketing, TierScenario, VacancyHeatmap, GeoJSONFC,
  VacancySource,
} from "@/lib/api";
import { loadNaverMaps } from "@/lib/naverMap";
import { colors } from "@/design/tokens/colors";
import "./PageDashboard.css";

const BuildingTwin = lazy(() => import("@/components/BuildingTwin"));

// 건물 공실 상태 → 색·라벨 (design 토큰 vacancy 색계열 재사용 — MapShell 과 동일 규칙)
const B_STATUS: Record<string, { color: string; label: string }> = {
  full: { color: colors.vacancy[0], label: "만실" },
  partial: { color: colors.vacancy[2], label: "부분공실" },
  high: { color: colors.vacancy[3], label: "고공실" },
  empty: { color: colors.vacancy[4], label: "공실의심" },
};

interface TwinSel {
  name: string; capacity: number; active: number; status: string;
  floors?: number;
  // 층 실배치 — 층 근거가 있는 건물에만 실린다(없으면 트윈이 근사로 폴백).
  comFloors?: number[]; occFloors?: number[]; unknownN?: number;
}

/**
 * 서울 Page 거점 대시보드 + 거점 심층 뷰(거점 수는 백엔드에 따라 가변 — 2026-08 기준 54곳).
 * 데이터 출처: 백엔드 단일 소스(/api/v1/commercial-districts). 고양 버전(CityDashboard/
 * DistrictPPPP, 정적 모듈)과 달리 서버 API로만 조회한다.
 *
 * 공실 수치는 거점마다 출처가 다르다 — `vacancy_source`("gold" 실측 / "synthetic" 합성)를
 * 반드시 화면에 드러낸다(SourceBadge). 합성값이 실측처럼 읽히면 안 된다.
 * TODO: 감성 zones·입점 units 는 아직 시드 — 각각 리뷰 감성분석·R-ONE 조인으로 교체 예정.
 */

// 공실률 색·막대 상한(%). 거점 값과 지도 셀은 분포가 달라 상한을 나눈다(2026-08-01 실측 기준).
//   거점 54곳: 9.2~30.1%          → 막대는 35 로 재야 거점 간 차이가 보인다
//   실측 셀 1,066개: p50 13 · p90 42 · max 100 → 색은 50. 한 셀이 건물 몇 동이라
//     80% 든 100% 든 "거의 비었다"로 같이 읽혀도 되고, 50 을 넘기면 상한을 올릴수록
//     중간대(10~30%)의 색차가 죽는다.
// 범례 눈금은 색 상한(VAC_SCALE_MAX)을 따라간다 — 범례와 셀 색이 어긋나면 안 된다.
export const VAC_SCALE_MAX = 50;
const VAC_BAR_MAX = 35;

// 감성(높을수록 좋음): 낮음 #E03E36 → 높음 #22B07D
export function sentHex(s: number): string {
  return lerpHex([224, 62, 54], [34, 176, 125], clamp01((s - 30) / 55));
}
// 공실률(높을수록 나쁨): 낮음 #22B07D → 높음 #E03E36 (디자인 토큰 vacancy 축과 동일 방향)
export function vacHex(v: number): string {
  return lerpHex([34, 176, 125], [224, 62, 54], clamp01(v / VAC_SCALE_MAX));
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
      gold: summaries.filter((s) => s.vacancy_source === "gold").length,
    };
  }, [summaries]);

  return (
    <div className="pagedash"><div className="wrap">
      <div className="hd">
        <div>
          <div className="ey">SpaceOS · Platform</div>
          <h1>주요 Platform — 서울 {summaries.length}거점</h1>
          <div className="sub">
            공실은 Gold 실측 {kpi.gold}거점 · 합성 {kpi.n - kpi.gold}거점(카드의 실측/합성 배지로 구분).
            감성·리뷰·입점 Tier 는 아직 시드 · 카드를 누르면 거점 심층으로 이동
          </div>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi"><div className="l">거점</div><div className="v">{kpi.n}<small>곳</small></div><div className="d">Phase 1~2 자치구 핫플 상권</div></div>
        <div className="kpi"><div className="l">평균 감성지수</div><div className="v" style={{ color: sentHex(kpi.sent) }}>{kpi.sent.toFixed(1)}<small>pt</small></div><div className="d">추정치 — 리뷰 수집 미착수</div></div>
        <div className="kpi"><div className="l">평균 공실률</div><div className="v" style={{ color: vacHex(kpi.vac) }}>{kpi.vac.toFixed(1)}<small>%</small></div><div className="d">100m 그리드 · 실측 {kpi.gold} / 합성 {kpi.n - kpi.gold}</div></div>
        <div className="kpi"><div className="l">공실 호실 합계</div><div className="v">{kpi.vacant.toLocaleString()}<small>개</small></div><div className="d">실측 거점은 건축물대장 호실 기준</div></div>
      </div>

      <div className="grid">
        {summaries.map((s, i) => (
          <button key={s.id} className="dcard" style={{ borderLeftColor: vacHex(s.vacancy_rate) }} onClick={() => onOpen(s.id)}>
            <div className="dtop">
              <div className="dord">{i + 1}</div>
              <div className="dname">{s.name}</div>
              <div className="dpill">{s.gu}</div>
              <SourceBadge source={s.vacancy_source} />
            </div>
            <div className="dhot">{s.type} · {s.note}</div>
            <Bar k="감성" v={s.sentiment} max={100} color={sentHex(s.sentiment)} text={`${s.sentiment.toFixed(1)}pt`} />
            <Bar k="공실" v={s.vacancy_rate} max={VAC_BAR_MAX} color={vacHex(s.vacancy_rate)} text={`${s.vacancy_rate.toFixed(1)}%`} />
            <div className="dmeta">
              <span>리뷰 {s.reviews.toLocaleString()}</span>
              <span>공실 {s.vacant_units}개</span>
              <span className={s.risk_zones > 0 ? "risk" : ""}>위험구역 {s.risk_zones}</span>
              <Anchor pct={s.anchor_pct} gap={s.anchor_gap_pp} />
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
      title="Platform·LSTM 다음 분기 공실 예측 (홀드아웃 MAE 1.109 / RMSE 1.494)">
      예측 {rate.toFixed(1)}% {up ? "▲" : "▼"}{Math.abs(delta).toFixed(1)}
    </span>
  );
}

/** R-ONE 앵커 대조 — 우리 추정과 공식 통계의 격차(%p). 앵커 없는 거점(합성)은 표시하지 않는다 */
function Anchor({ pct, gap }: { pct: number | null; gap: number | null }) {
  if (pct == null || gap == null) return null;
  return (
    <span className="anchorchip"
      title={`R-ONE 중대형상가 공실률 ${pct.toFixed(1)}% 대비 ${gap >= 0 ? "+" : ""}${gap.toFixed(1)}%p.`
        + " 모집단·단위가 달라(우리는 호실·전수, R-ONE 은 면적·표본) 격차 0 이 정상은 아니다."
        + " 절대값이 아니라 거점 간 비교·추세 감시에 쓴다."}>
      앵커 {pct.toFixed(1)}% {gap >= 0 ? "+" : ""}{gap.toFixed(1)}%p
    </span>
  );
}

/** Posting 입력 필드의 출처 배지 — 어떤 값이 실측이고 어떤 값이 아직 프록시인지 밝힌다.
 *  임대료·유동인구는 실데이터로 올라갔지만 면적·권리금은 공개 소스가 없어 시드로 남아 있다. */
function Src({ src }: { src?: string }) {
  if (!src) return null;
  const label = src === "rone" ? "R-ONE"
    : src === "flpop+seed" ? "유동인구"
      : src === "seed" ? "추정" : src;
  const title = src === "rone" ? "한국부동산원 R-ONE 소규모상가 임대료 × 면적 × 층 계수"
    : src === "flpop+seed" ? "서울 상권분석 유동인구(거점 수준) + 시드의 거점 내 서열"
      : "실데이터 소스가 없어 손으로 적은 프록시 값이다";
  return (
    <span className={`srcbadge ${src === "seed" ? "is-syn" : "is-gold"}`}
      style={{ marginLeft: 3 }} title={title}>{label}</span>
  );
}

/** 공실 수치가 Gold 실측인지 합성인지 알리는 배지 — 합성값을 실측으로 오독하지 않게 항상 표시 */
function SourceBadge({ source }: { source: VacancySource }) {
  const gold = source === "gold";
  return (
    <span className={`srcbadge ${gold ? "is-gold" : "is-syn"}`}
      title={gold
        ? "Gold 실측 — 건축물대장 호실(capacity) 대비 영업 점포(active) 집계"
        : "합성 — 실측 건물 데이터 미수집 거점. 추세 참고용이며 실측값이 아니다"}>
      {gold ? "실측" : "합성"}
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
  const overlaysRef = useRef<any[]>([]);   // 레이어 전환마다 지우는 오버레이(그리드/건물)
  const poiRef = useRef<any[]>([]);        // 거점 전환까지 유지되는 POI 마커
  const infoRef = useRef<any>(null);
  const [hm, setHm] = useState<VacancyHeatmap | null>(null);
  const [bld, setBld] = useState<GeoJSONFC | null>(null);
  const [layer, setLayer] = useState<"buildings" | "grid">("buildings");
  const [mapReady, setMapReady] = useState(false);
  const [mapErr, setMapErr] = useState<string | null>(null);
  const [sel, setSel] = useState<TwinSel | null>(null);   // 클릭한 건물(3D 트윈 대상)
  const [twinOpen, setTwinOpen] = useState(false);

  const clearOverlays = () => {
    overlaysRef.current.forEach((o) => o.setMap?.(null));
    overlaysRef.current = [];
  };

  // 거점 전환: 지도 재생성 + 그리드/건물 데이터 로드 + POI 그리기
  useEffect(() => {
    let live = true;
    setMapReady(false); setSel(null);

    Promise.all([
      loadNaverMaps(),
      getVacancyHeatmap(detail.id),
      getBuildingVacancy(detail.id).catch(() => null),   // 건물 gold 미배포 거점은 그리드만
    ])
      .then(([, heat, buildings]) => {
        if (!live || !elRef.current) return;
        setHm(heat); setBld(buildings);
        // 거점 전환마다 기본 레이어를 정한다: 건물 gold 가 있으면 건물, 없으면 그리드.
        setLayer(buildings && buildings.features.length ? "buildings" : "grid");
        const naver = (window as any).naver;

        mapRef.current?.destroy?.();
        const map = new naver.maps.Map(elRef.current, {
          center: new naver.maps.LatLng(detail.center[0], detail.center[1]),
          zoom: detail.zoom, scaleControl: false, mapDataControl: false,
        });
        mapRef.current = map;
        infoRef.current = new naver.maps.InfoWindow({ borderWidth: 0, disableAnchor: true, backgroundColor: "transparent" });
        naver.maps.Event.addListener(map, "click", () => infoRef.current?.close());

        // 역·랜드마크 POI 라벨 (레이어 전환과 무관하게 유지)
        poiRef.current.forEach((o) => o.setMap?.(null));
        poiRef.current = detail.poi.map(([lat, lng, label]) => new naver.maps.Marker({
          map, position: new naver.maps.LatLng(lat, lng),
          icon: {
            content: `<div style="background:#1f2937;color:#fff;border-radius:7px;padding:2px 8px;`
              + `font:700 10.5px 'Pretendard','Malgun Gothic',sans-serif;white-space:nowrap;`
              + `box-shadow:0 1px 5px rgba(0,0,0,.3)">${label}</div>`,
            anchor: new naver.maps.Point(0, 12),
          },
        }));

        setMapReady(true);
      })
      .catch((e) => live && setMapErr(e?.message ?? String(e)));

    return () => {
      live = false;
      clearOverlays();
      poiRef.current.forEach((o) => o.setMap?.(null)); poiRef.current = [];
      mapRef.current?.destroy?.(); mapRef.current = null;
    };
  }, [detail]);

  const hasBuildings = !!(bld && bld.features.length);

  // 레이어 전환/데이터 변경 → 오버레이 다시 그림
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const naver = (window as any).naver;
    const map = mapRef.current;
    const info = infoRef.current;
    clearOverlays();

    if (layer === "buildings" && bld) {
      // 공실 지도: 공실의심(empty) 건물만 개별 red dot 으로 — "어디가 비었나".
      // 만실·부분공실·고공실은 숨긴다(SpaceOS 공실 개별값 목표: 진짜 빈 건물만). 점 클릭 → 상세+3D.
      bld.features.forEach((f) => {
        const p = f.properties;
        if (p.status !== "empty") return;
        const st = B_STATUS[p.status];
        const ring = f.geometry.coordinates[0] as [number, number][];
        const lats = ring.map((r) => r[1]); const lngs = ring.map((r) => r[0]);
        const c = new naver.maps.LatLng(
          (Math.min(...lats) + Math.max(...lats)) / 2,
          (Math.min(...lngs) + Math.max(...lngs)) / 2,
        );
        const size = 13;
        const dot = new naver.maps.Marker({
          map, position: c, zIndex: 60,
          icon: {
            content: `<div style="width:${size}px;height:${size}px;border-radius:50%;`
              + `background:${st.color};border:1.5px solid #fff;`
              + `box-shadow:0 0 0 1px rgba(0,0,0,.12),0 1px 3px rgba(0,0,0,.35);opacity:.92"></div>`,
            anchor: new naver.maps.Point(size / 2 + 1.5, size / 2 + 1.5),
          },
        });
        naver.maps.Event.addListener(dot, "click", () => {
          info.setContent(
            `<div style="background:#fff;border:1px solid #e5e7eb;border-radius:9px;padding:8px 11px;`
            + `font:700 11.5px 'Pretendard','Malgun Gothic',sans-serif;color:#1f2937;box-shadow:0 2px 8px rgba(0,0,0,.12);max-width:200px">`
            + `${p.name || "건물"} · <span style="color:${st.color}">${st.label}</span><br>`
            + `<span style="color:#6b7280;font-weight:600">공실률(추정) ${p.vacancy_rate}% · 영업 ${p.active}/${p.capacity}호`
            + `${p.industry ? " · " + p.industry : ""}</span></div>`,
          );
          info.open(map, c);
          setSel({
            name: p.name || "건물", capacity: p.capacity, active: p.active, status: p.status,
            floors: p.floors,
            comFloors: p.com_floors ?? undefined, occFloors: p.occ_floors ?? undefined,
            unknownN: p.unknown_n ?? undefined,
          });
        });
        overlaysRef.current.push(dot);
      });
    } else if (layer === "grid" && hm) {
      // 100m 그리드 셀 — lat/lng 는 SW 모서리, dlat/dlng 만큼의 사각형
      hm.cells.forEach((c) => {
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
    }
  }, [layer, mapReady, hm, bld]);

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
      {/* 레이어 토글: 건물(실측 footprint) ↔ 100m 그리드 */}
      <div className="maptoggle">
        <button className={layer === "buildings" ? "on" : ""} disabled={!hasBuildings}
          onClick={() => setLayer("buildings")}>공실 건물</button>
        <button className={layer === "grid" ? "on" : ""} onClick={() => setLayer("grid")}>100m 그리드</button>
        {sel && layer === "buildings" && (
          <button className="twinbtn" onClick={() => setTwinOpen(true)}>🏢 {sel.name} · 3D 트윈</button>
        )}
      </div>

      <div ref={elRef} className="mapbox" />

      <div className="maplegend">
        {layer === "buildings" ? (
          <>
            <span className="ml-chip"><i style={{ background: B_STATUS.empty.color }} />공실의심</span>
            {bld && (() => {
              const vac = bld.features.filter((f) => f.properties.status === "empty").length;
              return <span className="ml-stat">공실의심 {vac.toLocaleString()}동(추정) · 점 클릭 시 상세·3D</span>;
            })()}
          </>
        ) : (
          <>
            <span className="ml-label">공실률</span>
            <span className="ml-grad" />
            <span className="ml-ticks"><em>0%</em><em>{VAC_SCALE_MAX}%+</em></span>
            {hm && (
              <span className="ml-stat">
                평균 <b style={{ color: vacHex(hm.avg_vacancy) }}>{hm.avg_vacancy.toFixed(1)}%</b>
                {" "}<Pred rate={hm.predicted_rate} delta={hm.predicted_delta} direction={hm.predicted_direction} />
                {" "}· 셀 {hm.cells.length} · 영업 {hm.sum_stores.toLocaleString()} · 공실 {hm.sum_vac}
                {" "}<SourceBadge source={hm.vacancy_source} />
                {hm.vacancy_source === "gold" && hm.buildings != null && (
                  <> · 건물 {hm.buildings.toLocaleString()}동({hm.precision_pct}%)
                    {hm.excluded_mall ? ` · 집합 ${hm.excluded_mall}동 제외` : ""}
                  </>
                )}
                {" "}<Anchor pct={hm.anchor_pct} gap={hm.anchor_gap_pp} />
              </span>
            )}
            <span className="ml-hint">셀 클릭 시 상세</span>
          </>
        )}
      </div>

      {/* 3D 디지털 트윈 모달 */}
      {twinOpen && sel && (
        <div className="twinmodal" onClick={() => setTwinOpen(false)}>
          <div className="twinbox" onClick={(e) => e.stopPropagation()}>
            <div className="twinhead">
              <span>{sel.name} · 3D 디지털 트윈</span>
              <button onClick={() => setTwinOpen(false)}>✕</button>
            </div>
            <div className="twincanvas">
              <Suspense fallback={<div className="twinload">3D 로딩…</div>}>
                <BuildingTwin b={{
                  name: sel.name, capacity: sel.capacity, active: sel.active, floors: sel.floors,
                  statusColor: B_STATUS[sel.status]?.color ?? colors.vacancy[4],
                  comFloors: sel.comFloors, occFloors: sel.occFloors, unknownN: sel.unknownN,
                }} />
              </Suspense>
            </div>
            <div className="twinfoot">
              {sel.comFloors?.length ? (
                <>
                  녹색 = 영업 확인 층({sel.occFloors?.join("·") || "없음"})
                  {sel.unknownN ? ` · 노란색 = 층 미상 점포 ${sel.unknownN}곳이 앉을 수 있는 층` : ""}
                  {" · "}{B_STATUS[sel.status]?.label ?? ""}색 = 공실 · 회색 = 비상업 층
                  {" · "}상업 {sel.comFloors.length}개 층 중 {sel.active}개 영업
                </>
              ) : (
                <>
                  녹색 = 영업 층(점유율 환산) · {B_STATUS[sel.status]?.label ?? ""}색 = 공실(추정) · {sel.active}/{sel.capacity}호
                  <span style={{ opacity: 0.75 }}> · 층 근거가 없어 아래부터 채운 근사다</span>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DistrictDeep({ summary, onBack }: { summary: DistrictSummary; onBack: () => void }) {
  const [detail, setDetail] = useState<DistrictDetail | null>(null);
  const [postings, setPostings] = useState<Posting[] | null>(null);
  const [marketing, setMarketing] = useState<Marketing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const marketingContentGold = marketing?.source === "llm";
  const marketingContentSourceLabel = marketingContentGold ? "Gold 생성" : "시드";
  const marketingContentSourceTitle = marketingContentGold
    ? "Gold(program_content_context)의 블로그 키워드·업종 분포·검색 트렌드를 근거로 생성"
    : "LLM 키 미설정·Gold 미적재·호출 실패 시 폴백 — 손으로 적은 예시 카피다";
  const haFindings = marketing?.ha_findings ?? [];
  const haBlocked = haFindings.filter((f) => f.severity === "violation");
  const haWarnings = haFindings.filter((f) => f.severity !== "violation");

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
          <h2 className="sec">공실 히트맵 <small>{summary.vacancy_source === "gold"
            ? `Page · 100m 그리드 — 건축물대장 호실 대비 영업 점포 실측(건물 ${summary.building_count?.toLocaleString()}동)`
            : "Page · 100m 그리드 합성 — 건물 데이터 수집 시 실측으로 교체"}</small></h2>
          <VacancyMap detail={detail} />

          {/* 감성은 아직 실데이터가 없다 — 리뷰 수집기가 미구현이고(review_crawler),
              블로그 코퍼스는 거점 단위 광고성 스니펫이라 구역 단위 감성으로 못 내린다.
              "리뷰/SNS 근거"라고 쓰면 없는 근거를 주장하는 것이라 표기를 바로잡았다. */}
          <h2 className="sec">감성 구역 <small>
            Platform · <b>전부 추정치다</b> — 리뷰 수집 미착수라 점수·건수·증감 모두 시드값이다
          </small></h2>
          <div className="zones">
            {detail.zones.map((z) => (
              <div key={z.id} className="zone" style={{ borderTopColor: sentHex(z.s) }}>
                <div className="zhead">
                  <span className="zname">{z.n}</span>
                  <span className="zscore" style={{ color: sentHex(z.s) }}>{z.s.toFixed(1)}</span>
                  <Src src="seed" />
                </div>
                {/* "리뷰 N건"으로 쓰면 실제로 센 것처럼 읽힌다 — 센 적이 없다 */}
                <div className="zmeta">{z.grp} · 가정 표본 {z.r.toLocaleString()}건 · {z.d >= 0 ? "▲" : "▼"}{Math.abs(z.d).toFixed(1)}</div>
                <div className="zkw">
                  {z.f.map(([label, delta], i) => <span key={i} className="kw">{label} {delta}</span>)}
                </div>
              </div>
            ))}
          </div>

          {postings && (
            <>
              <h2 className="sec">공실 유닛 · 3-Tier 시나리오 <small>
                Posting · 비용-효용(월) — 코파일럿 연동 전 폴백.
                임대료는 R-ONE 실데이터, 면적·권리금은 아직 추정치다
              </small></h2>
              <div className="units">
                {postings.map((p) => (
                  <div key={p.id} className="unit">
                    <div className="uhead">
                      <span className="uname">{p.n}</span>
                      <span className="upill">{p.floor} · {p.area}평 · 前 {p.was}</span>
                    </div>
                    <div className="umeta">
                      임대료 {p.rent.toLocaleString()}만원<Src src={p.inputs_source?.rent} />
                      {" · "}권리금 {p.prem ? `${p.prem.toLocaleString()}만원` : "없음"}
                      <Src src={p.inputs_source?.prem} />
                      {" · "}유동 {p.foot}<Src src={p.inputs_source?.foot} />
                      {" · "}{p.persona}
                    </div>
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
              <h2 className="sec">상권 행사 · 콘텐츠 <small>
                Program · {marketing.events_source === "seoul-open-data"
                  ? "행사는 서울열린데이터광장 문화행사 실데이터"
                  : "행사는 시드"} · {marketingContentGold
                    ? "콘텐츠는 Gold 컨텍스트 기반 생성"
                    : "콘텐츠는 시드"}
              </small></h2>
              {/* 실데이터인데 0건이면 그 거점에 예정 공공 문화행사가 없는 것이다.
                  시드로 채우면 지어낸 행사를 지도에 다시 찍게 되므로 빈 상태를 보여준다. */}
              {marketing.events_source === "seoul-open-data" && marketing.events.length === 0 && (
                <div className="loading">
                  예정된 공공 문화행사 없음 — 이 API 는 공공·문화시설 행사 중심이라
                  상업 상권의 팝업·마켓은 담기지 않는다
                </div>
              )}
              <div className="events">
                {marketing.events.map((ev) => (
                  <div key={ev.id} className="event">
                    <div className="ehead">
                      <span className="eic">{ev.ic}</span><span className="ename">{ev.n}</span>
                      {ev.k2 ? <span className="ek2">{ev.k2}</span>
                        : ev.category ? <span className="ek2">{ev.category}</span> : null}
                    </div>
                    <div className="ewhen">
                      {ev.when}
                      {ev.distance_m != null && ` · 거점에서 ${ev.distance_m}m`}
                    </div>
                    {/* 실데이터는 desc 대신 장소·주최·요금·대상을 준다 */}
                    <div className="edesc">{ev.desc ?? [ev.place, ev.org].filter(Boolean).join(" · ")}</div>
                    <div className="eroles">
                      {ev.roles
                        ? ev.roles.map((r, i) => <span key={i} className="role">{r}</span>)
                        : [ev.fee, ev.target].filter(Boolean).map((r, i) =>
                          <span key={i} className="role">{r}</span>)}
                    </div>
                    {ev.ha
                      ? <div className="eha">{ev.ha}</div>
                      : ev.link
                        ? <div className="eha"><a href={ev.link} target="_blank" rel="noreferrer">공식 안내 ↗</a></div>
                        : null}
                  </div>
                ))}
              </div>
              <div className="ml-label">
                <span>온라인 콘텐츠</span>{" "}
                <span className={`srcbadge ${marketingContentGold ? "is-gold" : "is-syn"}`}
                  title={marketingContentSourceTitle}>{marketingContentSourceLabel}</span>
              </div>
              {/* 폐기와 경고를 섞지 않는다 — 전자는 이 카피가 시드인 **이유**이고
                  후자는 살아 있는 카피에 붙은 주석이다. ProgramStudio 의 가게 단위 표기와
                  같은 구조로 맞춘다. */}
              {haBlocked.length > 0 && (
                <div className="hablock">
                  LLM 이 생성한 카피가 <b>Humanistic Authority 검증에 걸려 폐기</b>됐다 — 아래는
                  시드 카피다. 키·크레딧 문제가 아니다.
                  <ul className="halist">
                    {haBlocked.map((f, i) => (
                      <li key={i}>
                        <b>{f.message}</b>
                        {f.evidence && <> <code>{f.evidence}</code></>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {haWarnings.length > 0 && (
                <div className="hawarn">
                  <b>HA 검증 경고 {haWarnings.length}건</b> — 아래 카피는 살아 있다. 사전 매칭이라
                  오탐일 수 있으니 근거를 보고 판단하라.
                  <ul className="halist">
                    {haWarnings.map((f, i) => (
                      <li key={i}>
                        {f.message}
                        {f.evidence && <> <code>{f.evidence}</code></>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
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
