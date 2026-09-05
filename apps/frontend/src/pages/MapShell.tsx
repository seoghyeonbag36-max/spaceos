// MapShell — 거지맵/직방식 "지도-우선" 풀스크린 Page 레이아웃.
// 네이버 지도를 화면 전체 배경으로 깔고, 검색·레이어토글·범례·리스트를 오버레이로 띄운다.
// 회의 「Page 방향성」 1번(지도 크게) + 3번(4데이터 표현) 구현의 프론트 골격.
//
// 공실 레이어: 백엔드 /heatmap/buildings GeoJSON → naver.maps.Polygon 렌더(백엔드 다운 시 로컬 샘플 폴백).
// 유동인구: HeatMap + 시간 슬라이더. 임대/인구밀도: 코로플레스(데이터 연동 예정).
//
// 2026-08-01: App.tsx "지도" 탭에 연결(그전까지 라우팅되지 않아 방치돼 있었다).
// 거점은 하드코딩(gangnam-garosugil)이 아니라 **실측 거점 목록에서 고른다** —
// vacancy_source === "gold" 인 거점만 건물 폴리곤이 있고, 합성 거점은 404 라 빈 지도가 된다.
//
// ⚠ 이 컴포넌트는 position:fixed 로 뷰포트(좌측 레일 제외)를 통째로 채운다 —
//   부모 레이아웃에 기대지 않는다. 지도 캔버스 사이징 함정은
//   MapShell.css 의 .map-canvas 주석 참조.
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import DistrictPicker, { CaveatNote } from "@/components/DistrictPicker";
import { loadNaverMaps, describeNaverMapError } from "@/lib/naverMap";
import { getBuildingVacancy, getDensityHeatmap, getFootfallHeatmap, getRentHeatmap, listDistricts, recommendIndustry,
  type DensityHeatmap, type DistrictSummary, type FootfallHeatmap, type GeoJSONFC, type IndustryRecommend, type RentHeatmap } from "@/lib/api";
import { colors } from "@/design/tokens/colors";
import "@/styles/tokens.css";
import "./MapShell.css";

// 거리뷰 SDK·층 스택을 끌고 들어오므로 눌렀을 때만 받는다.
const BuildingViewer = lazy(() => import("@/components/BuildingViewer"));

// 가로수길 코어 (강남구 신사동) — poc-building-vacancy.md §0.5. 거점 목록이 오기 전 초기 중심.
const GAROSU = { lat: 37.5205, lng: 127.023 };
const DEFAULT_DISTRICT = "garosugil";

type Layer = "footfall" | "vacancy" | "rent" | "density";
type VacStatus = "full" | "partial" | "high" | "empty";

const LAYERS: { key: Layer; label: string }[] = [
  { key: "footfall", label: "유동인구" },
  { key: "vacancy", label: "공실" },
  { key: "rent", label: "임대시세" },
  { key: "density", label: "인구밀도" },
];

// 공실 상태 → 색 (design 토큰 vacancy 색계열 재사용, 단일 출처)
const STATUS: Record<VacStatus, { color: string; label: string }> = {
  full: { color: colors.vacancy[0], label: "만실" },
  partial: { color: colors.vacancy[2], label: "부분공실" },
  high: { color: colors.vacancy[3], label: "고공실" },
  empty: { color: colors.vacancy[4], label: "공실의심" },
};

interface Building {
  id: string; name: string; status: VacStatus; capacity: number; active: number; industry: string;
  floors?: number;   // 대장 지상 층수 — 층 스택의 높이. capacity(호 수)와 단위가 다르다.
  // 층 실배치 — 층 근거(건축물대장 층별개요 + 상가정보 flrNo)가 있는 건물에만 실린다.
  comFloors?: number[]; occFloors?: number[]; unknownN?: number;
  center: { lat: number; lng: number };
  ring: [number, number][]; // [lng, lat] (GeoJSON 순서)
}

const vacRate = (b: Building) => Math.round((1 - b.active / b.capacity) * 100);

// ── 로컬 폴백 샘플(백엔드 미기동 시). 백엔드 building_vacancy.py 와 동일 건물. ──
const RAW: Array<{ id: string; name: string; lat: number; lng: number; status: VacStatus; capacity: number; active: number; industry: string }> = [
  { id: "b1", name: "가로수길 A빌딩", lat: 37.5219, lng: 127.0222, status: "empty", capacity: 12, active: 1, industry: "의류" },
  { id: "b2", name: "세로수길 B타워", lat: 37.5211, lng: 127.0231, status: "high", capacity: 10, active: 4, industry: "카페" },
  { id: "b3", name: "신사 C스퀘어", lat: 37.5203, lng: 127.0226, status: "partial", capacity: 8, active: 6, industry: "화장품" },
  { id: "b4", name: "가로수 D플라자", lat: 37.5198, lng: 127.0236, status: "full", capacity: 6, active: 6, industry: "F&B" },
  { id: "b5", name: "도산 E빌딩", lat: 37.5226, lng: 127.0238, status: "empty", capacity: 9, active: 0, industry: "편집숍" },
  { id: "b6", name: "신사 F빌딩", lat: 37.519, lng: 127.0221, status: "partial", capacity: 7, active: 5, industry: "뷰티" },
  { id: "b7", name: "가로수 G동", lat: 37.5215, lng: 127.0245, status: "high", capacity: 11, active: 3, industry: "패션" },
  { id: "b8", name: "신사 H타워", lat: 37.5207, lng: 127.0213, status: "full", capacity: 5, active: 5, industry: "오피스" },
];

const D_LAT = 0.00013, D_LNG = 0.00017;
function rect(lat: number, lng: number): [number, number][] {
  return [
    [lng - D_LNG, lat - D_LAT], [lng + D_LNG, lat - D_LAT],
    [lng + D_LNG, lat + D_LAT], [lng - D_LNG, lat + D_LAT], [lng - D_LNG, lat - D_LAT],
  ];
}
const LOCAL_BUILDINGS: Building[] = RAW.map(({ lat, lng, ...b }) => ({
  ...b, center: { lat, lng }, ring: rect(lat, lng),
}));

function fromGeoJSON(fc: GeoJSONFC): Building[] {
  return (fc.features ?? []).map((f) => {
    const ring = f.geometry.coordinates[0] as [number, number][];
    const lats = ring.map((r) => r[1]), lngs = ring.map((r) => r[0]);
    const p = f.properties;
    return {
      id: p.id, name: p.name, status: p.status, capacity: p.capacity, active: p.active,
      industry: p.industry, floors: p.floors, ring,
      comFloors: p.com_floors ?? undefined, occFloors: p.occ_floors ?? undefined,
      unknownN: p.unknown_n ?? undefined,
      center: { lat: (Math.min(...lats) + Math.max(...lats)) / 2, lng: (Math.min(...lngs) + Math.max(...lngs)) / 2 },
    };
  });
}

// 유동·밀도 레이어는 TRDAR 상권 실측(services/footfall_layer)에서 온다.
// 2026-08-23 이전에는 여기서 `Math.random()` 으로 점 120개를 만들어 그렸고, 시간
// 슬라이더는 그 난수를 건드리지도 않아 **장식**이었다. 지금은 hour 가 API 질의에 들어간다.
// "상권단위" 배지 — 값이 **격자 실측이 아니라** 상권 집계라는 표시다. R-ONE 배지와
// 같은 역할: 화면에서 출처와 해상도를 숨기지 않는다.
const TRDAR_BADGE: React.CSSProperties = {
  color: "#3730a3", background: "#eef2ff", border: "1px solid #c7d2fe",
  borderRadius: 5, padding: "1px 5px", fontSize: 10, fontWeight: 800,
};
const DENSITY_COLORS = ["#EEF2FF", "#C7D2FE", "#A5B4FC", "#818CF8", "#4F46E5"];
function rampColor(v: number, min: number, max: number, ramp: string[]) {
  const span = Math.max(1e-9, max - min);
  const idx = Math.max(0, Math.min(ramp.length - 1, Math.floor(((v - min) / span) * ramp.length)));
  return ramp[idx];
}

const RENT_COLORS = ["#E6F8EE", "#BEEAD3", "#7DD9AD", "#35BF7C", "#0F8E5E"];
function rentColor(v: number, min: number, max: number) {
  const span = Math.max(1, max - min);
  const idx = Math.max(0, Math.min(RENT_COLORS.length - 1, Math.floor(((v - min) / span) * RENT_COLORS.length)));
  return RENT_COLORS[idx];
}

export default function MapShell() {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlaysRef = useRef<any[]>([]);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [layer, setLayer] = useState<Layer>("vacancy");
  const [buildings, setBuildings] = useState<Building[]>(LOCAL_BUILDINGS);
  const [rentHm, setRentHm] = useState<RentHeatmap | null>(null);
  const [footHm, setFootHm] = useState<FootfallHeatmap | null>(null);
  const [densHm, setDensHm] = useState<DensityHeatmap | null>(null);
  const [src, setSrc] = useState<"api" | "local">("local");
  const [selected, setSelected] = useState<Building | null>(null);
  const [rec, setRec] = useState<IndustryRecommend | null>(null);
  const [q, setQ] = useState("");
  const [hour, setHour] = useState(18);
  const [twinOpen, setTwinOpen] = useState(false);
  // 건물 폴리곤이 있는 거점만 고른다 — vacancy_source === "gold" 가 곧 "Gold 마스터 보유"다.
  // 합성 거점을 열면 /heatmap/buildings 가 404 라 빈 지도가 된다.
  const [hubs, setHubs] = useState<DistrictSummary[]>([]);
  const [districtId, setDistrictId] = useState(DEFAULT_DISTRICT);

  const hub = useMemo(() => hubs.find((h) => h.id === districtId), [hubs, districtId]);
  const center = hub ? { lat: hub.center[0], lng: hub.center[1] } : GAROSU;

  // 실측 거점 목록
  useEffect(() => {
    let alive = true;
    listDistricts()
      .then((all) => {
        if (!alive) return;
        const gold = all.filter((d) => d.vacancy_source === "gold");
        setHubs(gold);
        // 기본 거점이 아직 Gold 가 아니면 첫 실측 거점으로 떨어진다
        if (gold.length && !gold.some((d) => d.id === DEFAULT_DISTRICT)) setDistrictId(gold[0].id);
      })
      .catch(() => { /* 목록 실패 시 기본 거점 단독으로 계속 */ });
    return () => { alive = false; };
  }, []);

  // 건물 공실 데이터: 백엔드 /heatmap/buildings → 실패 시 로컬 샘플
  useEffect(() => {
    let alive = true;
    setSelected(null);
    getBuildingVacancy(districtId)
      .then((fc) => { if (alive) { setBuildings(fromGeoJSON(fc)); setSrc("api"); } })
      .catch(() => { if (alive) { setBuildings(LOCAL_BUILDINGS); setSrc("local"); } });
    return () => { alive = false; };
  }, [districtId]);

  useEffect(() => {
    let alive = true;
    setRentHm(null);
    getRentHeatmap(districtId)
      .then((hm) => { if (alive) setRentHm(hm); })
      .catch(() => { if (alive) setRentHm(null); });
    return () => { alive = false; };
  }, [districtId]);

  // 유동 레이어는 **hour 에도 의존한다** — 슬라이더가 실제 질의를 바꾼다.
  // 레이어를 보고 있지 않을 때는 부르지 않는다(거점 전환마다 3번 호출할 이유가 없다).
  useEffect(() => {
    if (layer !== "footfall") return;
    let alive = true;
    getFootfallHeatmap(districtId, hour)
      .then((hm) => { if (alive) setFootHm(hm); })
      .catch(() => { if (alive) setFootHm(null); });
    return () => { alive = false; };
  }, [districtId, hour, layer]);

  useEffect(() => {
    if (layer !== "density") return;
    let alive = true;
    getDensityHeatmap(districtId)
      .then((hm) => { if (alive) setDensHm(hm); })
      .catch(() => { if (alive) setDensHm(null); });
    return () => { alive = false; };
  }, [districtId, layer]);

  // 거점이 바뀌면 이전 거점의 값을 그대로 두지 않는다 — 남으면 다른 상권의 수치가
  // 새 지도 위에 잠깐 겹쳐 보인다.
  useEffect(() => { setFootHm(null); setDensHm(null); }, [districtId]);

  // 선택 건물의 GNN 업종 추천 (Platform 5-2)
  // 그래프 노드는 카카오 점포 자리라 건물 대장 키와 join 되지 않는다 → **좌표**로 묻는다.
  // src === "local" 은 백엔드 미기동 폴백이라 샘플 좌표다. 그걸로 추천을 물으면
  // 실제와 무관한 답이 붙으므로 아예 건너뛴다.
  useEffect(() => {
    if (!selected || src !== "api") { setRec(null); return; }
    let alive = true;
    setRec(null);
    recommendIndustry({
      district_id: districtId,
      lat: selected.center.lat,
      lon: selected.center.lng,   // 백엔드 필드명은 lon 이다
      building_id: selected.id,
    })
      .then((r) => { if (alive) setRec(r); })
      .catch(() => { if (alive) setRec(null); });  // 404 = 400m 안에 노드 없음
    return () => { alive = false; };
  }, [selected, districtId, src]);

  // 거점이 바뀌면 지도도 그 거점으로 옮긴다
  useEffect(() => {
    if (!ready || !hub) return;
    const naver = (window as any).naver;
    mapRef.current?.setCenter(new naver.maps.LatLng(center.lat, center.lng));
  }, [ready, hub, center.lat, center.lng]);

  // 지도 1회 초기화
  useEffect(() => {
    let alive = true;
    loadNaverMaps()
      .then(() => {
        if (!alive || !elRef.current) return;
        const naver = (window as any).naver;
        mapRef.current = new naver.maps.Map(elRef.current, {
          center: new naver.maps.LatLng(GAROSU.lat, GAROSU.lng),
          zoom: 16, scaleControl: false, mapDataControl: false,
        });
        setReady(true);
      })
      .catch((e) => alive && setErr(describeNaverMapError(e)));
    return () => { alive = false; };
  }, []);

  const clearOverlays = () => {
    overlaysRef.current.forEach((o) => o.setMap?.(null));
    overlaysRef.current = [];
  };

  const focus = (b: Building) => {
    setSelected(b);
    const naver = (window as any).naver;
    mapRef.current?.panTo(new naver.maps.LatLng(b.center.lat, b.center.lng));
  };

  // 레이어 전환/데이터 변경 → 오버레이 다시 그림 (form follows data)
  useEffect(() => {
    if (!ready) return;
    const naver = (window as any).naver;
    const map = mapRef.current;
    clearOverlays();

    if (layer === "vacancy") {
      // 공실: 건물 footprint 폴리곤을 상태색으로 채움 + 클릭 상세
      buildings.forEach((b) => {
        const poly = new naver.maps.Polygon({
          map,
          paths: b.ring.map(([lng, lat]) => new naver.maps.LatLng(lat, lng)),
          fillColor: STATUS[b.status].color, fillOpacity: 0.6,
          strokeColor: STATUS[b.status].color, strokeWeight: 2, strokeOpacity: 0.95,
          clickable: true,
        });
        naver.maps.Event.addListener(poly, "click", () => focus(b));
        overlaysRef.current.push(poly);
      });
    } else if (layer === "footfall" && footHm) {
      // 유동인구: 셀 중심을 가중 포인트로 넘긴다. 값은 상권 단위라 셀들이 같은 값을
      // 공유하는데, 그게 실제 해상도다 — 매끄럽게 보이려고 난수를 섞지 않는다.
      const span = Math.max(1e-9, footHm.max - footHm.min);
      const pts = footHm.cells.map((c) => ({
        lat: c.c_lat, lng: c.c_lng, w: (c.v - footHm.min) / span,
      }));
      if (naver.maps.visualization?.HeatMap) {
        const hm = new naver.maps.visualization.HeatMap({
          map, data: pts.map((p) => ({ location: new naver.maps.LatLng(p.lat, p.lng), weight: p.w })),
          radius: 30, opacity: 0.7,
        });
        overlaysRef.current.push(hm);
      } else {
        pts.forEach((p) => {
          const c = new naver.maps.Circle({
            map, center: new naver.maps.LatLng(p.lat, p.lng), radius: 32,
            fillColor: colors.brand.primary, fillOpacity: 0.2 + p.w * 0.45, strokeWeight: 0,
          });
          overlaysRef.current.push(c);
        });
      }
    } else if (layer === "density" && densHm) {
      densHm.cells.forEach((cell) => {
        const color = rampColor(cell.v, densHm.min, densHm.max, DENSITY_COLORS);
        const paths = [
          new naver.maps.LatLng(cell.lat, cell.lng),
          new naver.maps.LatLng(cell.lat, cell.lng + cell.dlng),
          new naver.maps.LatLng(cell.lat + cell.dlat, cell.lng + cell.dlng),
          new naver.maps.LatLng(cell.lat + cell.dlat, cell.lng),
        ];
        const poly = new naver.maps.Polygon({
          map, paths, fillColor: color, fillOpacity: 0.5,
          strokeColor: color, strokeWeight: 1, strokeOpacity: 0.8, clickable: false,
        });
        overlaysRef.current.push(poly);
      });
    } else if (layer === "rent" && rentHm) {
      const values = rentHm.cells.map((c) => c.v);
      const min = Math.min(...values);
      const max = Math.max(...values);
      rentHm.cells.forEach((cell) => {
        const color = rentColor(cell.v, min, max);
        const paths = [
          new naver.maps.LatLng(cell.lat, cell.lng),
          new naver.maps.LatLng(cell.lat, cell.lng + cell.dlng),
          new naver.maps.LatLng(cell.lat + cell.dlat, cell.lng + cell.dlng),
          new naver.maps.LatLng(cell.lat + cell.dlat, cell.lng),
        ];
        const poly = new naver.maps.Polygon({
          map, paths, fillColor: color, fillOpacity: 0.52,
          strokeColor: color, strokeWeight: 1, strokeOpacity: 0.85,
          clickable: false,
        });
        overlaysRef.current.push(poly);
      });
    }
  }, [layer, ready, buildings, rentHm, footHm, densHm, center.lat, center.lng]);

  const filtered = useMemo(() => buildings.filter((b) => !q || b.name.includes(q)), [buildings, q]);

  return (
    <div className="mapshell">
      <div ref={elRef} className="map-canvas" />

      {err && (
        <div className="map-note">
          <strong>네이버 지도를 불러오지 못했습니다</strong>
          <div>{err}</div>
          <div>
            NCP 콘솔 &gt; Maps &gt; Application 의 Web 서비스 URL 에{" "}
            <code>{window.location.origin}</code> 을 등록해야 합니다.
          </div>
        </div>
      )}

      {/* 상단: 거점 선택 + 검색 + 레이어 토글 */}
      <div className="overlay overlay-top">
        {hubs.length > 0 && (
          <>
            <DistrictPicker className="hub-select" districts={hubs}
              value={districtId} onChange={setDistrictId} />
            <CaveatNote district={hubs.find((h) => h.id === districtId)} />
          </>
        )}
        <input className="search" placeholder={`건물 검색 (${hub?.name ?? "가로수길"})`} value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg" role="tablist">
          {LAYERS.map((l) => (
            <button key={l.key} className={layer === l.key ? "active" : ""} onClick={() => setLayer(l.key)}>{l.label}</button>
          ))}
        </div>
      </div>

      {/* 좌측 리스트 패널 (모바일: 하단 시트) */}
      <div className="overlay side-panel">
        <div className="sp-head">
          <div className="sp-title">{hub?.name ?? "가로수길"} · 건물 공실</div>
          <div className="sp-sub">
            {hub ? `${hub.gu} · ` : ""}{filtered.length.toLocaleString()}동 · {src === "api" ? "실측" : "샘플"}(추정)
            {/* 거점 대표값이 없으면 그 사실을 적는다 — 조용히 빠지면 있는 값을 못 본
                것처럼 읽힌다. 아래 건물 목록은 그대로다(내린 것은 대표값뿐이다). */}
            {hub && (hub.vacancy_rate !== null && Number.isFinite(hub.vacancy_rate)
              ? ` · 거점 ${hub.vacancy_rate.toFixed(1)}%`
              : hub.vacancy_withheld ? " · 거점 대표값 미제공" : "")}
          </div>
          {hub?.anchor_pct != null && hub.anchor_gap_pp != null && (
            <div className="sp-anchor" title="R-ONE 중대형상가 공실률 대비. 모집단이 달라 격차 0 이 정상은 아니며 거점 간 비교용이다.">
              앵커 {hub.anchor_pct.toFixed(1)}% {hub.anchor_gap_pp >= 0 ? "+" : ""}{hub.anchor_gap_pp.toFixed(1)}%p
            </div>
          )}
        </div>
        <div className="sp-list">
          {filtered.map((b) => (
            <button
              key={b.id}
              className={"b-item" + (selected?.id === b.id ? " active" : "")}
              onClick={() => { if (layer !== "vacancy") setLayer("vacancy"); focus(b); }}
            >
              <span className="b-dot" style={{ background: STATUS[b.status].color }} />
              <span>
                <div className="b-name">{b.name}</div>
                <div className="b-meta">{b.industry} · {STATUS[b.status].label}</div>
              </span>
              <span className="b-vac" style={{ color: STATUS[b.status].color }}>{vacRate(b)}%</span>
            </button>
          ))}
        </div>

        {selected && (
          <div className="b-detail">
            <div className="b-name">{selected.name}</div>
            <div className="row"><span>공실률(추정)</span><span style={{ color: STATUS[selected.status].color }}>{vacRate(selected)}%</span></div>
            <div className="row"><span>상태</span><span>{STATUS[selected.status].label}</span></div>
            <div className="row"><span>상가 수용 / 영업</span><span>{selected.capacity}호 / {selected.active}호</span></div>
            <div className="row"><span>대표 업종</span><span>{selected.industry}</span></div>

            {/* GNN 업종 추천 — 스텁(Gold 미적재)·빈 추천은 그리지 않는다.
                합성값을 실측처럼 보이게 하지 않는 vacancy_source 규칙과 같은 원칙이다. */}
            {rec && rec.model !== "gnn-stub" && rec.recommendations.length > 0 && (
              <div className="b-rec">
                <div className="b-rec-h">
                  이 자리 업종 추천<span className="b-rec-badge">GNN</span>
                </div>
                {rec.recommendations.map((r) => (
                  <div className="row" key={r.industry}>
                    <span>{r.industry}</span>
                    <span>{Math.round(r.score * 100)}%</span>
                  </div>
                ))}
                <div className="b-rec-note">
                  {rec.scope === "node"
                    ? `가장 가까운 점포 자리 기준 · ${Math.round(rec.matched_distance_m ?? 0)}m`
                    : "거점 평균 — 이 건물 근처에 그래프 노드가 없다"}
                  {typeof rec.metrics?.lift_vs_district_prior_pct === "number" && (
                    <> · 거점 평균 대비 <b>+{rec.metrics.lift_vs_district_prior_pct}%</b></>
                  )}
                </div>
              </div>
            )}

            <button className="b-twin" onClick={() => setTwinOpen(true)}>층별 공실 · 거리뷰 보기</button>
          </div>
        )}
      </div>

      {/* 유동인구 레이어 전용 시간 슬라이더 = 흐름 축 */}
      {layer === "footfall" && (
        <div className="overlay time-bar">
          <span className="t">{String(hour).padStart(2, "0")}:00</span>
          <input type="range" min={0} max={23} value={hour} onChange={(e) => setHour(+e.target.value)} />
        </div>
      )}

      {/* 범례 */}
      <div className="overlay legend">
        {layer === "vacancy" && (Object.keys(STATUS) as VacStatus[]).map((k) => (
          <span key={k} className="chip"><span className="sw" style={{ background: STATUS[k].color }} />{STATUS[k].label}</span>
        ))}
        {layer === "footfall" && (
          <span className="note">
            {footHm
              ? <>
                  유동인구 · {footHm.time_source === "trdar_band"
                    ? footHm.band_label
                    : `${String(footHm.hour).padStart(2, "0")}시 (${footHm.daytype === "weekend" ? "주말" : "평일"})`}
                  {" · "}
                  {footHm.resolution === "jipgyegu"
                    ? `집계구 ${footHm.oa_count ?? 0}곳`
                    : `상권 ${footHm.trdar_count}곳`}{" "}
                  {/* 공간 눈금 — 어느 구획의 집계인지 밝힌다. 둘 다 격자 실측은 아니다. */}
                  <span style={TRDAR_BADGE}>
                    {footHm.resolution === "jipgyegu" ? "집계구 단위" : "TRDAR 상권단위"}
                  </span>{" "}
                  {/* 시간 눈금 — 세 축의 값 스케일이 서로 다르다 */}
                  <span style={TRDAR_BADGE}>
                    {footHm.time_source === "jipgyegu_hourly" ? "생활인구 24h(집계구)"
                      : footHm.time_source === "adong_hourly" ? "생활인구 24h(행정동)"
                      : "TRDAR 6구간"}
                  </span>
                </>
              : "유동인구 · 불러오는 중"}
          </span>
        )}
        {layer === "rent" && <span className="note">평당 임대시세 · {rentHm?.unit ?? "만원/평"} <span style={{ color: "#0f7a55", background: "#e3f5ee", border: "1px solid #b7e3d2", borderRadius: 5, padding: "1px 5px", fontSize: 10, fontWeight: 800 }}>R-ONE</span></span>}
        {layer === "density" && (
          <span className="note">
            {densHm
              ? <>
                  {densHm.label} · {densHm.unit} · {densHm.resolution === "jipgyegu"
                    ? `집계구 ${densHm.oa_count ?? 0}곳`
                    : `상권 ${densHm.trdar_count}곳`}{" "}
                  <span style={TRDAR_BADGE}>
                    {densHm.resolution === "jipgyegu" ? "집계구 단위" : "TRDAR 상권단위"}
                  </span>
                </>
              : "밀도 · 불러오는 중"}
          </span>
        )}
      </div>

      {/* 건물 상세 — 2D 층 스택 + 네이버 거리뷰 (2026-09-05 에 3D 트윈을 대체했다) */}
      {twinOpen && selected && (
        <div className="twin-modal" onClick={() => setTwinOpen(false)}>
          <div className="twin-box" onClick={(e) => e.stopPropagation()}>
            <div className="twin-head">
              <span>{selected.name} · 층별 공실 · 거리뷰</span>
              <button onClick={() => setTwinOpen(false)}>✕</button>
            </div>
            <div className="twin-canvas">
              <Suspense fallback={<div className="twin-load">불러오는 중…</div>}>
                <BuildingViewer b={{
                  name: selected.name, capacity: selected.capacity, active: selected.active,
                  floors: selected.floors, statusColor: STATUS[selected.status].color,
                  statusLabel: STATUS[selected.status].label, center: selected.center,
                  comFloors: selected.comFloors, occFloors: selected.occFloors,
                  unknownN: selected.unknownN,
                }} />
              </Suspense>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
