// MapShell — 거지맵/직방식 "지도-우선" 풀스크린 Page 레이아웃.
// 네이버 지도를 화면 전체 배경으로 깔고, 검색·레이어토글·범례·리스트를 오버레이로 띄운다.
// 회의 「Page 방향성」 1번(지도 크게) + 3번(4데이터 표현) 구현의 프론트 골격.
//
// 공실 레이어: 백엔드 /heatmap/buildings GeoJSON → naver.maps.Polygon 렌더(백엔드 다운 시 로컬 샘플 폴백).
// 유동인구: HeatMap + 시간 슬라이더. 임대/인구밀도: 코로플레스(데이터 연동 예정).
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { loadNaverMaps } from "@/lib/naverMap";
import { getBuildingVacancy, type GeoJSONFC } from "@/lib/api";
import { colors } from "@/design/tokens/colors";
import "@/styles/tokens.css";
import "./MapShell.css";

const BuildingTwin = lazy(() => import("@/components/BuildingTwin"));

// 가로수길 코어 (강남구 신사동) — poc-building-vacancy.md §0.5
const GAROSU = { lat: 37.5205, lng: 127.023 };
const DISTRICT = "gangnam-garosugil";

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
      industry: p.industry, ring,
      center: { lat: (Math.min(...lats) + Math.max(...lats)) / 2, lng: (Math.min(...lngs) + Math.max(...lngs)) / 2 },
    };
  });
}

// SAMPLE — 유동인구 히트맵용 포인트. TODO: 서울 생활인구 격자로 교체.
function sampleFootfall() {
  const pts: { lat: number; lng: number; w: number }[] = [];
  for (let i = 0; i < 120; i++) {
    const r = Math.pow(Math.random(), 1.6) * 0.004;
    const a = Math.random() * Math.PI * 2;
    pts.push({ lat: GAROSU.lat + r * Math.cos(a), lng: GAROSU.lng + r * Math.sin(a), w: Math.random() });
  }
  return pts;
}

export default function MapShell() {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlaysRef = useRef<any[]>([]);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [layer, setLayer] = useState<Layer>("vacancy");
  const [buildings, setBuildings] = useState<Building[]>(LOCAL_BUILDINGS);
  const [src, setSrc] = useState<"api" | "local">("local");
  const [selected, setSelected] = useState<Building | null>(null);
  const [q, setQ] = useState("");
  const [hour, setHour] = useState(18);
  const [twinOpen, setTwinOpen] = useState(false);

  // 건물 공실 데이터: 백엔드 /heatmap/buildings → 실패 시 로컬 샘플
  useEffect(() => {
    let alive = true;
    getBuildingVacancy(DISTRICT)
      .then((fc) => { if (alive) { setBuildings(fromGeoJSON(fc)); setSrc("api"); } })
      .catch(() => { if (alive) { setBuildings(LOCAL_BUILDINGS); setSrc("local"); } });
    return () => { alive = false; };
  }, []);

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
      const data = sampleFootfall();
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
    }
    // rent/density: 구·격자 코로플레스 → 폴리곤 데이터 필요(범례에 안내).
  }, [layer, ready, buildings]);

  const filtered = useMemo(() => buildings.filter((b) => !q || b.name.includes(q)), [buildings, q]);
  const isChoropleth = layer === "rent" || layer === "density";

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

      {/* 상단: 검색 + 레이어 토글 */}
      <div className="overlay overlay-top">
        <input className="search" placeholder="건물·상호 검색 (가로수길)" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg" role="tablist">
          {LAYERS.map((l) => (
            <button key={l.key} className={layer === l.key ? "active" : ""} onClick={() => setLayer(l.key)}>{l.label}</button>
          ))}
        </div>
      </div>

      {/* 좌측 리스트 패널 (모바일: 하단 시트) */}
      <div className="overlay side-panel">
        <div className="sp-head">
          <div className="sp-title">가로수길 · 건물 공실</div>
          <div className="sp-sub">강남구 신사동 · {filtered.length}개 · {src === "api" ? "API" : "샘플"}(추정)</div>
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
        {isChoropleth && <span className="note">{layer === "rent" ? "평당 임대시세" : "인구밀도"} · 구/격자 코로플레스 (데이터 연동 예정)</span>}
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
                <BuildingTwin b={{ name: selected.name, capacity: selected.capacity, active: selected.active, statusColor: STATUS[selected.status].color }} />
              </Suspense>
            </div>
            <div className="twin-foot">
              녹색 = 영업 층 · {STATUS[selected.status].label}색 = 공실(추정) · {selected.active}/{selected.capacity}호
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
