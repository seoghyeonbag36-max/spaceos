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
// ⚠ 이 컴포넌트는 position:absolute·inset:0 이라 **위치 지정된 부모** 안에 있어야 한다
//   (App.tsx 의 main 이 지도 뷰에서만 position:relative). 지도 캔버스 사이징 함정은
//   MapShell.css 의 .map-canvas 주석 참조.
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { loadNaverMaps } from "@/lib/naverMap";
import { getBuildingVacancy, getRentHeatmap, listDistricts, recommendIndustry, type DistrictSummary, type GeoJSONFC, type IndustryRecommend, type RentHeatmap } from "@/lib/api";
import { colors } from "@/design/tokens/colors";
import "@/styles/tokens.css";
import "./MapShell.css";

const BuildingTwin = lazy(() => import("@/components/BuildingTwin"));

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
  floors?: number;   // 대장 지상 층수 — 3D 트윈 층 스택용. capacity(호 수)와 단위가 다르다.
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

// SAMPLE — 유동인구 히트맵용 포인트. TODO: 서울 생활인구 격자로 교체.
function sampleFootfall(center: { lat: number; lng: number }) {
  const pts: { lat: number; lng: number; w: number }[] = [];
  for (let i = 0; i < 120; i++) {
    const r = Math.pow(Math.random(), 1.6) * 0.004;
    const a = Math.random() * Math.PI * 2;
    pts.push({ lat: center.lat + r * Math.cos(a), lng: center.lng + r * Math.sin(a), w: Math.random() });
  }
  return pts;
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
      .catch((e) => alive && setErr(e?.message ?? "지도 로드 실패"));
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
    } else if (layer === "footfall") {
      // 유동인구: HeatMap(visualization). 미탑재 시 Circle 폴백.
      const data = sampleFootfall(center);
      if (naver.maps.visualization?.HeatMap) {
        const hm = new naver.maps.visualization.HeatMap({
          map, data: data.map((p) => ({ location: new naver.maps.LatLng(p.lat, p.lng), weight: p.w })),
          radius: 24, opacity: 0.7,
        });
        overlaysRef.current.push(hm);
      } else {
        data.forEach((p) => {
          const c = new naver.maps.Circle({
            map, center: new naver.maps.LatLng(p.lat, p.lng), radius: 14,
            fillColor: colors.brand.primary, fillOpacity: 0.25 + p.w * 0.4, strokeWeight: 0,
          });
          overlaysRef.current.push(c);
        });
      }
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
    // rent/density: 구·격자 코로플레스 → 폴리곤 데이터 필요(범례에 안내).
  }, [layer, ready, buildings, rentHm, center.lat, center.lng]);

  const filtered = useMemo(() => buildings.filter((b) => !q || b.name.includes(q)), [buildings, q]);

  return (
    <div className="mapshell">
      <div ref={elRef} className="map-canvas" />

      {err && (
        <div className="map-note">
          <strong>네이버 지도를 불러오지 못했습니다</strong>
          <div>{err}</div>
          <div>
            <code>apps/frontend/.env</code> 의 <code>VITE_NAVER_MAPS_KEY_ID</code> 설정 +
            NCP 콘솔에 <code>http://localhost:5173</code> 도메인 등록이 필요합니다.
          </div>
        </div>
      )}

      {/* 상단: 거점 선택 + 검색 + 레이어 토글 */}
      <div className="overlay overlay-top">
        {hubs.length > 0 && (
          <select className="hub-select" value={districtId} onChange={(e) => setDistrictId(e.target.value)}
            title="건물 폴리곤이 있는 실측 거점만 나온다">
            {hubs.map((h) => (
              <option key={h.id} value={h.id}>{h.name} · 공실 {h.vacancy_rate.toFixed(1)}%</option>
            ))}
          </select>
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
            {hub && ` · 거점 ${hub.vacancy_rate.toFixed(1)}%`}
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

            <button className="b-twin" onClick={() => setTwinOpen(true)}>3D 디지털 트윈 보기</button>
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
        {layer === "footfall" && <span className="note">유동인구 밀도 · 시간대별 (샘플)</span>}
        {layer === "rent" && <span className="note">평당 임대시세 · {rentHm?.unit ?? "만원/평"} <span style={{ color: "#0f7a55", background: "#e3f5ee", border: "1px solid #b7e3d2", borderRadius: 5, padding: "1px 5px", fontSize: 10, fontWeight: 800 }}>R-ONE</span></span>}
        {layer === "density" && <span className="note">인구밀도 · 구/격자 코로플레스 (데이터 연동 예정)</span>}
      </div>

      {/* 3D 디지털 트윈 모달 */}
      {twinOpen && selected && (
        <div className="twin-modal" onClick={() => setTwinOpen(false)}>
          <div className="twin-box" onClick={(e) => e.stopPropagation()}>
            <div className="twin-head">
              <span>{selected.name} · 3D 디지털 트윈</span>
              <button onClick={() => setTwinOpen(false)}>✕</button>
            </div>
            <div className="twin-canvas">
              <Suspense fallback={<div className="twin-load">3D 로딩…</div>}>
                <BuildingTwin b={{
                  name: selected.name, capacity: selected.capacity, active: selected.active,
                  floors: selected.floors, statusColor: STATUS[selected.status].color,
                  comFloors: selected.comFloors, occFloors: selected.occFloors,
                  unknownN: selected.unknownN,
                }} />
              </Suspense>
            </div>
            <div className="twin-foot">
              {selected.comFloors?.length ? (
                <>
                  녹색 = 영업 확인 층({selected.occFloors?.join("·") || "없음"})
                  {selected.unknownN ? ` · 노란색 = 층 미상 점포 ${selected.unknownN}곳이 앉을 수 있는 층` : ""}
                  {" · "}{STATUS[selected.status].label}색 = 공실 · 회색 = 비상업 층(공실률 분모 밖)
                  {" · "}상업 {selected.comFloors.length}개 층 중 {selected.active}개 영업
                  {selected.floors ? ` · 지상 ${selected.floors}층` : ""}
                  <br />
                  <span style={{ opacity: 0.75 }}>
                    근거: 건축물대장 층별개요 + 상가정보 층 표기 — 층 배치는 실측이다
                  </span>
                </>
              ) : (
                <>
                  녹색 = 영업 층(점유율 환산) · {STATUS[selected.status].label}색 = 공실(추정) · {selected.active}/{selected.capacity}호
                  {selected.floors ? ` · 지상 ${selected.floors}층` : ""}
                  <br />
                  <span style={{ opacity: 0.75 }}>
                    이 건물은 층 근거가 없어 <b>아래부터 채운 근사</b>다 — 실제 공실 층과 다를 수 있다
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
