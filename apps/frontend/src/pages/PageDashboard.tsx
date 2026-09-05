import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { CaveatNote, MeasuredValue } from "@/components/DistrictPicker";
import {
  BASIS_LABEL,
  listDistricts, getDistrict, getPostings, getMarketing, getVacancyHeatmap, getBuildingVacancy,
  getFloorVacancies,
} from "@/lib/api";
import type {
  DistrictSummary, DistrictDetail, Posting, Marketing, TierScenario, VacancyHeatmap, GeoJSONFC,
  VacancySource, FloorVacancyList, FloorVacancyUnit,
} from "@/lib/api";
import { loadNaverMaps, describeNaverMapError } from "@/lib/naverMap";
import { colors } from "@/design/tokens/colors";
import "./PageDashboard.css";

// 거리뷰 SDK·층 스택을 끌고 들어오므로 눌렀을 때만 받는다.
const BuildingViewer = lazy(() => import("@/components/BuildingViewer"));

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
  /** 거리뷰가 바라볼 대상. 없으면 거리뷰 자리에 "이 자리에는 거리뷰가 없다"가 뜬다. */
  center?: { lat: number; lng: number };
  // 층 실배치 — 층 근거가 있는 건물에만 실린다(없으면 층 스택이 근사로 폴백).
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
    // 전체를 그대로 나누던 `avg` 헬퍼는 걷어냈다. 남은 두 평균(감성·공실)이 **둘 다**
    // null 을 분모에서 빼야 해서, 헬퍼를 두면 실수로 그것을 부르는 자리가 생긴다.
    // 감성·리뷰는 경기 거점에 소스가 없어 null 이다. **null 을 0 으로 세면 안 된다** —
    // 평균이 내려가 서울 거점까지 실제보다 낮게 보인다. 실측이 있는 거점만 분모에 넣는다.
    const measured = summaries.filter((s) => s.sentiment !== null && s.sentiment !== undefined);
    const sentAvg = measured.length
      ? measured.reduce((a, s) => a + (s.sentiment ?? 0), 0) / measured.length : null;
    // 공실률도 같다. 대표값을 내린 거점(계획상가 밀집 — vacancy_withheld)을 0 으로 세면
    // 서울 평균이 통째로 내려간다. 감성과 같은 규칙으로 분모에서 뺀다.
    const vacMeasured = summaries.filter(
      (s) => s.vacancy_rate !== null && s.vacancy_rate !== undefined && Number.isFinite(s.vacancy_rate));
    const vacAvg = vacMeasured.length
      ? vacMeasured.reduce((a, s) => a + (s.vacancy_rate ?? 0), 0) / vacMeasured.length : null;
    return {
      n,
      sent: sentAvg,
      sentN: measured.length,
      vac: vacAvg,
      vacN: vacMeasured.length,
      vacant: summaries.reduce((a, s) => a + s.vacant_units, 0),
      reviews: summaries.reduce((a, s) => a + (s.reviews ?? 0), 0),
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
        <div className="kpi"><div className="l">평균 감성지수</div>
          <div className="v" style={{ color: kpi.sent === null ? undefined : sentHex(kpi.sent) }}>
            {kpi.sent === null ? <span className="value-absent">실측 없음</span>
              : <>{kpi.sent.toFixed(1)}<small>pt</small></>}</div>
          {/* 분모를 밝힌다 — 감성 소스가 없는 거점(경기)은 평균에서 뺐다. */}
          <div className="d">추정치 · {kpi.sentN}/{kpi.n}거점 실측</div></div>
        <div className="kpi"><div className="l">평균 공실률</div>
          <div className="v" style={{ color: kpi.vac === null ? undefined : vacHex(kpi.vac) }}>
            {kpi.vac === null ? <span className="value-absent">실측 없음</span>
              : <>{kpi.vac.toFixed(1)}<small>%</small></>}</div>
          {/* 분모를 밝힌다 — 대표값을 내린 거점은 평균에서 뺐다. */}
          <div className="d">100m 그리드 · {kpi.vacN}/{kpi.n}거점 · 실측 {kpi.gold} / 합성 {kpi.n - kpi.gold}</div></div>
        <div className="kpi"><div className="l">공실 호실 합계</div><div className="v">{kpi.vacant.toLocaleString()}<small>개</small></div><div className="d">실측 거점은 건축물대장 호실 기준</div></div>
      </div>

      <div className="grid">
        {summaries.map((s, i) => (
          <button key={s.id} className="dcard"
            style={{ borderLeftColor: s.vacancy_rate === null || s.vacancy_rate === undefined
              ? "var(--line, #d1d5db)" : vacHex(s.vacancy_rate) }}
            onClick={() => onOpen(s.id)}>
            <div className="dtop">
              <div className="dord">{i + 1}</div>
              <div className="dname">{s.name}</div>
              <div className="dpill">{s.gu}</div>
              <SourceBadge source={s.vacancy_source} />
            </div>
            <div className="dhot">{s.type} · {s.note}</div>
            {s.sentiment === null || s.sentiment === undefined
              ? <div className="dmeta"><span className="value-absent"
                  title="이 거점에는 감성 소스가 없다 — 0 이 아니라 재지 않은 것이다">감성 실측 없음</span></div>
              : <Bar k="감성" v={s.sentiment} max={100} color={sentHex(s.sentiment)}
                     text={`${s.sentiment.toFixed(1)}pt`} />}
            {/* 대표값을 내린 거점은 막대를 그리지 않는다 — 길이 0 짜리 막대는 "공실 0%"
                로 읽힌다. 왜 없는지는 카드를 눌러 들어가면 CaveatNote 가 전문으로 밝힌다. */}
            {s.vacancy_rate === null || s.vacancy_rate === undefined
              ? <div className="dmeta"><span className="value-absent"
                  title={s.vacancy_withheld
                    ? "쟀지만 거점을 대표하지 못해 내렸다 — 계획상가 밀집"
                    : "이 거점에는 공실 실측이 없다"}>
                  {s.vacancy_withheld ? "공실 대표값 미제공" : "공실 실측 없음"}</span></div>
              : <Bar k="공실" v={s.vacancy_rate} max={VAC_BAR_MAX} color={vacHex(s.vacancy_rate)}
                     text={`${s.vacancy_rate.toFixed(1)}%`} />}
            <div className="dmeta">
              <span>리뷰 {s.reviews === null || s.reviews === undefined
                ? <span className="value-absent">없음</span> : s.reviews.toLocaleString()}</span>
              <span>공실 {s.vacant_units}개</span>
              {s.risk_zones !== null && s.risk_zones !== undefined &&
                <span className={s.risk_zones > 0 ? "risk" : ""}>위험구역 {s.risk_zones}</span>}
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
      : src === "flr_ouln" ? "층 실측"
        : src === "assumed_1f" ? "1F 가정"
          : src === "seed" ? "추정" : src;
  const title = src === "rone" ? "한국부동산원 R-ONE 소규모상가 임대료 × 면적 × 층 계수"
    : src === "flpop+seed" ? "서울 상권분석 유동인구(거점 수준) + 시드의 거점 내 서열"
      : src === "flr_ouln"
        ? ("층별개요 상업층의 면적 비중으로 임대료를 가중평균했다. "
          + "이 유닛은 건물의 호실당 평균 자리라 특정 한 층이 아니다 — "
          + "실제 임차인이 저층을 고르면 임대료는 이보다 높다(하한).")
        : src === "assumed_1f"
          ? "층 근거가 없어 1층으로 가정했다 — 층 계수가 최댓값이라 임대료 상한이다"
          : "실데이터 소스가 없어 손으로 적은 프록시 값이다";
  return (
    // `assumed_1f` 도 합성 취급이다 — 관측이 아니라 가정이라, 초록(실측) 배지를
    // 달면 "층을 실측했다"로 읽힌다.
    <span className={`srcbadge ${src === "seed" || src === "assumed_1f" ? "is-syn" : "is-gold"}`}
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
  const [sel, setSel] = useState<TwinSel | null>(null);   // 클릭한 건물(층 스택·거리뷰 대상)
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
      .catch((e) => live && setMapErr(describeNaverMapError(e)));

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
      // 만실·부분공실·고공실은 숨긴다(SpaceOS 공실 개별값 목표: 진짜 빈 건물만). 점 클릭 → 상세+거리뷰.
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
            center: { lat: c.lat(), lng: c.lng() },
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
          <button className="twinbtn" onClick={() => setTwinOpen(true)}>🏢 {sel.name} · 층별 공실 · 거리뷰</button>
        )}
      </div>

      <div ref={elRef} className="mapcanvas" />

      <div className="maplegend">
        {layer === "buildings" ? (
          <>
            <span className="ml-chip"><i style={{ background: B_STATUS.empty.color }} />공실의심</span>
            {bld && (() => {
              const vac = bld.features.filter((f) => f.properties.status === "empty").length;
              return <span className="ml-stat">공실의심 {vac.toLocaleString()}동(추정) · 점 클릭 시 상세·거리뷰</span>;
            })()}
          </>
        ) : (
          <>
            <span className="ml-label">공실률</span>
            <span className="ml-grad" />
            <span className="ml-ticks"><em>0%</em><em>{VAC_SCALE_MAX}%+</em></span>
            {hm && (
              <span className="ml-stat">
                평균 {hm.avg_vacancy === null || hm.avg_vacancy === undefined
                  ? <b className="value-absent" title="쟀지만 거점을 대표하지 못해 내렸다">대표값 미제공</b>
                  : <b style={{ color: vacHex(hm.avg_vacancy) }}>{hm.avg_vacancy.toFixed(1)}%</b>}
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

      {/* 건물 상세 — 2D 층 스택 + 네이버 거리뷰 (2026-09-05 에 3D 트윈을 대체했다) */}
      {twinOpen && sel && (
        <div className="twinmodal" onClick={() => setTwinOpen(false)}>
          <div className="twinbox" onClick={(e) => e.stopPropagation()}>
            <div className="twinhead">
              <span>{sel.name} · 층별 공실 · 거리뷰</span>
              <button onClick={() => setTwinOpen(false)}>✕</button>
            </div>
            <div className="twincanvas">
              <Suspense fallback={<div className="twinload">불러오는 중…</div>}>
                <BuildingViewer b={{
                  name: sel.name, capacity: sel.capacity, active: sel.active, floors: sel.floors,
                  statusColor: B_STATUS[sel.status]?.color ?? colors.vacancy[4],
                  statusLabel: B_STATUS[sel.status]?.label, center: sel.center,
                  comFloors: sel.comFloors, occFloors: sel.occFloors, unknownN: sel.unknownN,
                }} />
              </Suspense>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 층 단위 공실 매물 목록 — "이 건물 **몇 층**이 비었고 몇 평인가".
 *
 * 아래 「공실 유닛 · 3-Tier」 섹션과 **다른 것을 센다.** 저쪽은 통째로 빈 건물 1동이
 * 유닛 1개인 ROI 표본이고, 여기는 (지번, 층)이 매물 1개라 **일부 층만 빈 건물**이
 * 들어온다(그래서 수가 훨씬 많다). 층으로 쪼갠 표본을 ROI 계산에 쓰면 프리미엄
 * 트립와이어가 부호를 넘는 것이 확인돼 있어(§0-Q) 두 목록은 계속 갈라져 있다.
 *
 * 확정과 추정을 **한 모양으로 그리지 않는다.** 추정은 상가정보 층 표기 공란(약 30%)
 * 때문에 생기는 괄호이고, 확정처럼 보이면 그게 이 저장소가 반복해 잡아 온 결함이다.
 */
function FloorVacancies({ list }: { list: FloorVacancyList | null }) {
  const [onlyConfirmed, setOnlyConfirmed] = useState(true);
  const [floor, setFloor] = useState<number | null>(null);

  // 층 선택기는 **필터 전** 분포로 그린다 — 필터 뒤 분포로 그리면 층을 고른 순간
  // 나머지 층이 사라져 "원래 없다"와 "걸러서 없다"가 같아 보인다.
  const floors = useMemo(
    () => Object.keys(list?.by_floor ?? {}).map(Number).sort((a, b) => a - b),
    [list],
  );
  const shown = useMemo(() => {
    const u = (list?.units ?? []).filter(
      (x) => (!onlyConfirmed || x.certainty === "confirmed")
        && (floor === null || x.floor === floor));
    // 산출물은 **확정 우선**으로 정렬돼 온다. 그대로 60건에서 자르면 확정이 앞을 다
    // 채워 추정이 한 장도 안 그려진다 — '확정만 보기'를 꺼도 화면이 그대로여서
    // 토글이 고장난 것처럼 보였다(2026-09-05 /verify 에서 실측). 확정만 볼 때는
    // 그 순서가 맞지만, 둘 다 볼 때는 certainty 를 정렬 키에서 빼고 **층 순서**로
    // 읽는다 — 매물 목록은 원래 그렇게 읽는다. certainty 는 배지로 남는다.
    return onlyConfirmed ? u
      : [...u].sort((a, z) => a.floor - z.floor || z.area - a.area);
  }, [list, onlyConfirmed, floor]);

  if (!list) return null;   // 404 = 이 거점에 아직 층 산출물이 없다. 빈 섹션을 그리지 않는다.

  const all = list.counts_all;
  return (
    <>
      <h2 className="sec">층별 공실 매물 <small>
        Page · 건축물대장 층별개요 + 상가정보 층 표기 실측 — 어느 층이 비었고 몇 평인가.
        {" "}면적은 <b>그 층의</b> 대장 실측이다(건물 평균을 나눈 값이 아니다)
      </small></h2>

      <div className="fv-bar">
        <div className="fv-counts">
          거점 전체 <b>{all.units ?? list.total}</b>건
          {" · "}확정 <b>{all.confirmed ?? list.counts.confirmed}</b>
          {" · "}추정 {all.probable ?? list.counts.probable}
          {all.buildings ? <> · 건물 {all.buildings}동</> : null}
        </div>
        <label className="fv-toggle">
          <input type="checkbox" checked={onlyConfirmed}
                 onChange={(e) => setOnlyConfirmed(e.target.checked)} />
          확정만 보기
        </label>
      </div>

      <div className="fv-floors">
        <button className={floor === null ? "on" : ""} onClick={() => setFloor(null)}>전체</button>
        {floors.map((f) => (
          <button key={f} className={floor === f ? "on" : ""} onClick={() => setFloor(f)}>
            {f}F <em>{list.by_floor[String(f)]}</em>
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <div className="fv-empty">
          이 조건에 맞는 매물이 없다. {onlyConfirmed && "‘확정만 보기’를 끄면 추정 매물까지 나온다."}
        </div>
      ) : (
        <div className="fv-list">
          {shown.slice(0, 60).map((u) => <FloorVacancyCard key={u.id} u={u} />)}
        </div>
      )}

      <div className="fv-note">
        {list.fit_meta && (
          <>
            업종은 <b>추천이 아니라 관측</b>이다 — 상가정보 × 건축물대장 층별개요를
            (지번, 층)으로 조인해 "같은 조건의 자리에 실제로 무엇이 들어와 있는가"를 센 것이고,
            그 자리에서 <b>잘 된다는 뜻이 아니다</b>(매출·생존은 안 봤다).
            {list.fit_meta.stats && <> 조인 {list.fit_meta.stats.joined?.toLocaleString()}건
              / 점포 {list.fit_meta.stats.stores?.toLocaleString()}건 —
              상가정보 층 공란과 층별개요 미수집분이 빠진 부분 표본이다.</>}
            <br />
          </>
        )}
        <b>확정</b> = 층 미상 점포를 낮은 층부터 다 앉히고도 남은 층이라 비었음이 확정이다.
        {" "}<b>추정</b> = 그 배정에 먹힌 층이라, 층 미상 점포가 다른 층에 있으면 빈다 —
        괄호의 원인은 상가정보 층 표기 공란(약 30%)이다.
        {shown.length > 60 && <> · 목록은 60건까지만 그린다(조건에 맞는 것 {shown.length}건).</>}
        <br />
        <span style={{ opacity: 0.75 }}>
          이 목록에는 임대료·회수기간이 없다 — 그 계산의 표본은 아래 「공실 유닛 · 3-Tier」다.
          층으로 쪼갠 표본을 ROI 에 쓰면 추정이 실측처럼 굳는다(2026-08-26 실측·되돌림).
        </span>
      </div>
    </>
  );
}

function FloorVacancyCard({ u }: { u: FloorVacancyUnit }) {
  const conf = u.certainty === "confirmed";
  return (
    <div className={"fv-card" + (conf ? "" : " probable")}>
      <div className="fv-head">
        <span className="fv-floor">{u.floor_label}</span>
        <span className="fv-name">{u.n}</span>
        <span className={"fv-badge " + (conf ? "ok" : "maybe")}>{conf ? "확정" : "추정"}</span>
      </div>
      <div className="fv-meta">
        <b>{u.area}평</b>
        <span className="dim">({u.area_m2}㎡)</span>
        {u.purps ? <> · 대장 용도 <b>{u.purps}</b></> : null}
        {u.was ? <> · 건물 주업종 {u.was}</> : null}
      </div>
      {u.fit && (
        <div className={"fv-fit" + (u.fit.basis === "purps_floor" ? "" : " weak")}>
          <span className="fv-fit-k">
            {u.fit.basis === "purps_floor" ? "같은 용도·층에서 영업 중" : "같은 층에서 영업 중"}
          </span>
          {u.fit.top.map((t) => (
            <span key={t.industry} className="fv-fit-v">
              {t.industry} <em>{Math.round(t.share * 100)}%</em>
            </span>
          ))}
          <span className="fv-fit-n">표본 {u.fit.n.toLocaleString()}건</span>
        </div>
      )}
      <div className="fv-sub">
        상업층 {u.com_floors.join("·")}
        {u.occ_floors.length ? <> · 영업 확인 {u.occ_floors.join("·")}층</> : <> · 영업 확인 층 없음</>}
        {u.unknown_n ? <> · 층 미상 점포 {u.unknown_n}곳</> : null}
        {u.bld_floors ? <> · 지상 {u.bld_floors}층</> : null}
        {/* 층 근거는 지번 단위라, 한 지번에 동이 여럿이면 어느 동인지 말할 수 없다.
            숨기면 "이 건물 3층"으로 읽히므로 드러낸다. */}
        {u.bldgs_on_pnu > 1 && (
          <span className="fv-warn"> · 같은 지번 {u.bldgs_on_pnu}동 — 어느 동인지는 미상</span>
        )}
      </div>
    </div>
  );
}

function DistrictDeep({ summary, onBack }: { summary: DistrictSummary; onBack: () => void }) {
  const [detail, setDetail] = useState<DistrictDetail | null>(null);
  const [postings, setPostings] = useState<Posting[] | null>(null);
  const [marketing, setMarketing] = useState<Marketing | null>(null);
  const [floorVac, setFloorVac] = useState<FloorVacancyList | null>(null);
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
    // 층별 매물은 **따로** 받는다. 404(이 거점에 층 산출물이 없다)는 정상 상태이고,
    // 위 Promise.all 에 묶으면 그 하나가 거점 심층 뷰 전체를 에러로 떨어뜨린다.
    // 한 벌 통째로 받아 필터는 화면에서 건다 — 층 선택기가 **필터 전** 층 분포를
    // 보여줘야 "3층은 원래 없다"와 "3층을 걸러서 없다"가 구분된다.
    getFloorVacancies(summary.id, { limit: 2000 })
      .then((v) => { if (live) setFloorVac(v); })
      .catch(() => { if (live) setFloorVac(null); });
    return () => { live = false; };
  }, [summary.id]);

  return (
    <div className="pagedash"><div className="wrap">
      <div className="hd">
        <div>
          <button className="back" onClick={onBack}>← 거점 보드</button>
          <h1>{summary.name}</h1>
          <div className="sub">
            {detail?.sub ?? summary.note} · 공실률{" "}
            <MeasuredValue value={summary.vacancy_rate} unit="%"
              absent={summary.vacancy_withheld ? "대표값 미제공" : "실측 없음"} />
            {" "}<Pred rate={summary.predicted_rate} delta={summary.predicted_delta} direction={summary.predicted_direction} />
            {" "}· 감성 <MeasuredValue value={summary.sentiment} unit="pt" />
            {summary.rec_top ? ` · 추천 상위 Tier ${summary.rec_top}` : ""}
          </div>
          {/* 예외 거점이면 왜 다른지 여기서 전문으로 밝힌다. 목록의 표식(▤·▣)만 보고
              숫자를 그대로 믿지 않게 하는 자리다. */}
          <CaveatNote district={summary} />
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

          {/* 2026-09-05: 손으로 적은 감성 구역을 **행정동 실측 구역**으로 갈았다.
              공실률·점포·건물은 실측이고, 감성만 여전히 없다(좌표를 가진 점포 리뷰
              채널 부재 — docs/feature-platform.md §0-K). 색은 공실 축을 쓴다 —
              감성 축(sentHex)을 쓰면 못 잰 값이 색을 갖는 것처럼 읽힌다. */}
          <h2 className="sec">구역 <small>
            Platform · <b>행정동 실측</b> — 점포·건물·공실은 실측, <b>감성은 아직 못 잰다</b>
          </small></h2>
          {detail.zones.length === 0 && (
            <div className="loading">이 거점의 구역 산출물이 아직 없다 (build_district_zones 미실행).</div>
          )}
          <div className="zones">
            {detail.zones.map((z) => (
              <div key={z.id} className="zone"
                   style={{ borderTopColor: z.vacancy_rate === null ? undefined : vacHex(z.vacancy_rate) }}>
                <div className="zhead">
                  <span className="zname">{z.n}</span>
                  <span className="zscore"
                        style={{ color: z.vacancy_rate === null ? undefined : vacHex(z.vacancy_rate) }}>
                    {z.vacancy_rate === null ? "—" : `${z.vacancy_rate.toFixed(1)}%`}
                  </span>
                  <Src src="gold" />
                </div>
                <div className="zmeta">
                  {z.grp} · 점포 {z.stores?.toLocaleString() ?? "—"} · 건물 {z.buildings ?? "—"}동
                  {z.capacity !== null && ` · 상업 ${z.capacity.toLocaleString()}호`}
                </div>
                {/* 없는 것을 빈 칸으로 두지 않는다 — "0 인가 없는 건가"를 화면이 말해야 한다 */}
                <div className="zmeta">
                  {z.s === null
                    ? <span className="value-absent">감성 실측 없음</span>
                    : <>감성 {z.s.toFixed(1)}</>}
                </div>
                {z.f.length > 0 && (
                  <div className="zkw">
                    {z.f.map(([label, delta], i) => <span key={i} className="kw">{label} {delta}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>

          <FloorVacancies list={floorVac} />

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
                      <span className="upill">
                        {p.floor}<Src src={p.inputs_source?.floor} /> · {p.area}평 · 前 {p.was}
                      </span>
                    </div>
                    <div className="umeta">
                      임대료 {p.rent.toLocaleString()}만원<Src src={p.inputs_source?.rent} />
                      {" · "}권리금 {p.prem ? `${p.prem.toLocaleString()}만원` : "없음"}
                      <Src src={p.inputs_source?.prem} />
                      {" · "}유동 {p.foot}<Src src={p.inputs_source?.foot} />
                      {/* persona·note 는 시드에만 있던 서술 문구다. 실 인벤토리 유닛에는
                          없으므로 자리를 비운다 — 없는 문장을 지어내면 실측 카드가
                          손으로 적은 카드처럼 읽힌다(2026-08-24 배선). */}
                      {p.persona ? <>{" · "}{p.persona}</> : null}
                    </div>
                    {p.note ? <div className="unote">{p.note}</div> : null}
                    <div className="tiers">
                      {Object.values(p.scenarios).map((sc: TierScenario) => (
                        <div key={sc.tier} className={"tier" + (sc.recommended ? " rec" : "")} style={{ borderColor: sc.recommended ? TIER_COLOR[sc.tier] : undefined }}>
                          <div className="tname" style={{ color: TIER_COLOR[sc.tier] }}>{sc.name}{sc.recommended && <em> 추천</em>}</div>
                          <div className="trow"><span>초기투자</span><b>{sc.invest_mn}백만</b></div>
                          <div className="trow"><span>월 순익</span><b className={sc.month_net >= 0 ? "" : "neg"}>{sc.month_net.toLocaleString()}만</b></div>
                          {/* "모른다"(—)와 "안 된다"(회수 불가)는 다른 정보다. 예전에는 둘 다 "—" 였고,
                              비용 모델이 낙관적이라 회수불가가 거의 안 나와 잠복해 있었다. 2026-08-23
                              실측 모델부터 실제로 뜬다(연남·명동처럼 임대료/매출이 높은 거점). */}
                          <div className="trow"><span>회수</span>
                            <b className={sc.viable ? "" : "neg"}>
                              {sc.viable ? `${sc.roi_months}개월` : "회수 불가"}
                            </b>
                          </div>
                        </div>
                      ))}
                    </div>
                    {/* 세 전략 모두 회수불가면 그 사실과 계산의 한계를 함께 밝힌다.
                        숫자만 비워 두면 "데이터가 없다"로 읽힌다. */}
                    {!Object.values(p.scenarios).some((sc: TierScenario) => sc.viable) && (
                      <div className="unote neg">
                        이 자리는 지금 계산으로는 <b>회수 불가</b> — 세 전략 모두 월 순익이 0 이하다.
                        {" "}임대료가 이 면적이 낼 수 있는 매출에 비해 높다.
                      </div>
                    )}
                    <div className="unote">
                      비용 기준: {BASIS_LABEL[Object.values(p.scenarios)[0]?.basis]
                        ?? Object.values(p.scenarios)[0]?.basis ?? "미상"}
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
