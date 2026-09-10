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
// ⚠ 2026-09-05: **지도는 더 이상 이 컴포넌트가 만들지 않는다.** MapHost 가 앱 전체에서
//   하나만 만들어 들고 있고(설계서 §10-1), 여기서는 그 위에 오버레이만 그린다.
//   그전에는 탭을 옮길 때마다 지도가 죽고 다시 태어나 사용자가 맞춘 카메라가 날아갔다.
//   이 컴포넌트의 루트는 이제 MapHost 안을 채우는 절대배치 레이어다(MapShell.css 참조).
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import CandidateCompare from "@/components/CandidateCompare";
import { createPageWorkspace, type PageWorkspace, type BuildingSelection, type VacancyFilter } from "@/lib/workspaceState";
import DistrictPicker, { CaveatNote } from "@/components/DistrictPicker";
import { useMapHost } from "@/components/MapHost";
import { getBuildingVacancy, getDensityHeatmap, getFootfallHeatmap, getRentHeatmap, listDistricts, recommendIndustry,
  type DensityHeatmap, type DistrictSummary, type FootfallHeatmap, type GeoJSONFC, type IndustryRecommend, type RentHeatmap } from "@/lib/api";
import { colors } from "@/design/tokens/colors";
import { vacancyDotAnchor, vacancyDotHTML } from "@/design/components/MapMarkerPin";
import "@/styles/tokens.css";
import "./MapShell.css";

// 거리뷰 SDK·층 스택을 끌고 들어오므로 눌렀을 때만 받는다.
const BuildingViewer = lazy(() => import("@/components/BuildingViewer"));

// 가로수길 코어 (강남구 신사동) — poc-building-vacancy.md §0.5. 거점 목록이 오기 전 초기 중심.
const GAROSU = { lat: 37.5205, lng: 127.023 };
const EMPTY_BUILDINGS: Building[] = [];
const EMPTY_IDS: string[] = [];

type Layer = "footfall" | "vacancy" | "rent" | "density";
type VacStatus = "full" | "partial" | "high" | "empty";

const LAYERS: { key: Layer; label: string }[] = [
  { key: "footfall", label: "유동인구" },
  { key: "vacancy", label: "공실" },
  { key: "rent", label: "임대시세" },
  { key: "density", label: "인구밀도" },
];

// 공실 표현이 갈리는 줌 경계 (2026-09-06 디자이너 피드백 「공실을 red-dot 혹은 핀으로」).
//
// 왜 두 표현인가: 종전에는 줌과 무관하게 **4상태를 전부 폴리곤으로 칠했다.** 거점 하나에
// 건물이 840~1,443동이라 멀리서 보면 화면이 색으로 꽉 차 "어디가 비었나"가 안 읽힌다.
// 멀리서는 **공실의심(empty)만 점으로** 찍어 답을 먼저 주고, 가까이 가면 폴리곤으로
// 건물 형상과 나머지 상태(만실·부분공실·고공실)를 보여준다.
//
// ⚠ 점 표현은 새로 만든 것이 아니라 `PageDashboard.tsx` 에 있던 구현을 옮긴 것이다.
//   그 화면이 `#board` 해시로 밀려나면서 red dot 도 같이 안 보이게 돼 있었다.
const PIN_MAX_ZOOM = 15;   // 이 줌 **이하**면 점, 초과면 폴리곤

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
  borderRadius: 5, padding: "1px 5px", fontSize: 10, fontWeight: 700,
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

interface MapShellProps {
  workspace?: PageWorkspace;
  onWorkspaceChange?: Dispatch<SetStateAction<PageWorkspace>>;
  onReview?: (selection: BuildingSelection) => void;
}

export default function MapShell({ workspace: externalWorkspace, onWorkspaceChange, onReview }: MapShellProps = {}) {
  const [localWorkspace, setLocalWorkspace] = useState(createPageWorkspace);
  const workspace = externalWorkspace ?? localWorkspace;
  const setWorkspace = onWorkspaceChange ?? setLocalWorkspace;
  const { districtId, query: q } = workspace;
  const setQ = (query: string) => setWorkspace((w) => ({ ...w, query }));
  const setDistrictId = (id: string) => {
    setWorkspace((w) => ({ ...w, districtId: id, query: "", status: "all", selectedId: null }));
    setCompareOpen(false);
    setTwinOpen(false);
  };
  // 지도는 MapHost 소유다 — 여기서는 빌려 쓰기만 한다.
  const { map, ready } = useMapHost();
  const overlaysRef = useRef<any[]>([]);
  // 오버레이에 붙인 이벤트 핸들. **오버레이와 같은 수명**이라 같은 자리에서 걷는다.
  // `setMap(null)` 은 지도에서 떼기만 하고 리스너 등록은 건드리지 않으므로, 핸들을
  // 받아 두지 않으면 뗄 방법 자체가 없다 — 거점을 바꿀 때마다 등록이 그대로 남는다
  // (2026-09-08 계측: 10회 전환에 addListener 1,710 / removeListener 0).
  // 짝의 본보기는 아래 zoom_changed 리스너다.
  const listenersRef = useRef<any[]>([]);
  const [layer, setLayer] = useState<Layer>("vacancy");
  const [inventory, setInventory] = useState<{ districtId: string; buildings: Building[]; source: "api" | "local" } | null>(null);
  // 불러오는 중 이전 거점의 건물·출처를 새 거점 이름으로 보여주지 않는다.
  const currentInventory = inventory?.districtId === districtId ? inventory : null;
  const buildings = currentInventory?.buildings ?? EMPTY_BUILDINGS;
  const src = currentInventory?.source ?? "local";
  const [rentHm, setRentHm] = useState<RentHeatmap | null>(null);
  const [footHm, setFootHm] = useState<FootfallHeatmap | null>(null);
  const [densHm, setDensHm] = useState<DensityHeatmap | null>(null);
  const selected = buildings.find((b) => b.id === workspace.selectedId) ?? null;
  const [rec, setRec] = useState<IndustryRecommend | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [savedOnly, setSavedOnly] = useState(false);
  const [hour, setHour] = useState(18);
  const [twinOpen, setTwinOpen] = useState(false);
  // 줌 자체가 아니라 **모드**를 담는다. 줌 값을 state 에 두면 휠을 굴릴 때마다
  // 리렌더가 나고 오버레이 840개를 매 틱 다시 그린다. 불리언이라 전환은 두 번뿐이다.
  const [pinMode, setPinMode] = useState(false);
  // 건물 폴리곤이 있는 거점만 고른다 — vacancy_source === "gold" 가 곧 "Gold 마스터 보유"다.
  // 합성 거점을 열면 /heatmap/buildings 가 404 라 빈 지도가 된다.
  const [hubs, setHubs] = useState<DistrictSummary[]>([]);
  const savedIds = workspace.savedIds[districtId] ?? EMPTY_IDS;
  const saved = src === "api" ? buildings.filter((b) => savedIds.includes(b.id)) : [];
  const filtered = useMemo(() => buildings.filter((b) => (!q.trim() || b.name.toLocaleLowerCase().includes(q.trim().toLocaleLowerCase()))
    && (workspace.status === "all" || b.status === workspace.status)
    && (!savedOnly || savedIds.includes(b.id))), [buildings, q, workspace.status, savedOnly, savedIds]);

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
        if (gold.length) setWorkspace((w) => gold.some((d) => d.id === w.districtId)
          ? w : { ...w, districtId: gold[0].id, query: "", status: "all", selectedId: null });
      })
      .catch(() => { /* 목록 실패 시 기본 거점 단독으로 계속 */ });
    return () => { alive = false; };
  }, [setWorkspace]);

  // 건물 공실 데이터: 백엔드 /heatmap/buildings → 실패 시 로컬 샘플
  useEffect(() => {
    let alive = true;
    getBuildingVacancy(districtId)
      .then((fc) => { if (alive) setInventory({ districtId, buildings: fromGeoJSON(fc), source: "api" }); })
      .catch(() => { if (alive) setInventory({ districtId, buildings: LOCAL_BUILDINGS, source: "local" }); });
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
    if (!ready || !hub || !map) return;
    const naver = (window as any).naver;
    map.setCenter(new naver.maps.LatLng(center.lat, center.lng));
  }, [ready, map, hub, center.lat, center.lng]);

  // 줌 → 표현 모드. 지도는 MapHost 소유라 여기서 만들지 않으므로 리스너만 붙였다 뗀다.
  // 초기값을 한 번 읽어 두지 않으면 사용자가 줌을 건드리기 전까지 모드가 틀린 채로 그려진다.
  useEffect(() => {
    if (!ready || !map) return;
    const naver = (window as any).naver;
    const sync = () => setPinMode(map.getZoom() <= PIN_MAX_ZOOM);
    sync();
    const h = naver.maps.Event.addListener(map, "zoom_changed", sync);
    return () => naver.maps.Event.removeListener(h);
  }, [ready, map]);

  const clearOverlays = () => {
    const naver = (window as any).naver;
    // 리스너를 **먼저** 뗀다 — 오버레이 참조를 버린 뒤에는 짝을 찾을 자리가 없다.
    listenersRef.current.forEach((h) => naver?.maps?.Event?.removeListener(h));
    listenersRef.current = [];
    overlaysRef.current.forEach((o) => o.setMap?.(null));
    overlaysRef.current = [];
  };

  // 이 탭을 떠날 때 Page 레이어를 걷는다 — 지도는 계속 살아 있으므로, 안 걷으면
  // 거점 탭으로 옮겨도 건물 폴리곤이 그대로 남는다.
  useEffect(() => clearOverlays, []);

  const focus = (b: Building) => {
    setWorkspace((w) => ({ ...w, selectedId: b.id }));
    const naver = (window as any).naver;
    if (map && naver) map.panTo(new naver.maps.LatLng(b.center.lat, b.center.lng));
  };

  // 레이어 전환/데이터 변경 → 오버레이 다시 그림 (form follows data)
  useEffect(() => {
    if (!ready || !map) return;
    const naver = (window as any).naver;
    clearOverlays();

    if (layer === "vacancy" && pinMode) {
      // 멀리서 볼 때: **공실의심(empty)만** 점으로. 만실·부분공실·고공실은 숨긴다 —
      // 이 축척에서 답해야 하는 질문은 "어디가 비었나" 하나이고, 840~1,443동을 전부
      // 칠하면 그 답이 색에 묻힌다. 점 클릭은 폴리곤과 같은 상세를 연다.
      const size = 13;
      const anchor = vacancyDotAnchor(size);
      filtered.forEach((b) => {
        if (b.status !== "empty") return;
        const dot = new naver.maps.Marker({
          map, position: new naver.maps.LatLng(b.center.lat, b.center.lng), zIndex: 60,
          icon: {
            content: vacancyDotHTML(STATUS[b.status].color, size),
            anchor: new naver.maps.Point(anchor, anchor),
          },
        });
        listenersRef.current.push(naver.maps.Event.addListener(dot, "click", () => focus(b)));
        overlaysRef.current.push(dot);
      });
    } else if (layer === "vacancy") {
      // 가까이서 볼 때: 건물 footprint 폴리곤을 상태색으로 채움 + 클릭 상세.
      // 여기서는 4상태를 다 그린다 — 건물 형상이 보이는 축척이라 색이 서로를 덮지 않는다.
      filtered.forEach((b) => {
        const poly = new naver.maps.Polygon({
          map,
          paths: b.ring.map(([lng, lat]) => new naver.maps.LatLng(lat, lng)),
          fillColor: STATUS[b.status].color, fillOpacity: 0.6,
          strokeColor: STATUS[b.status].color, strokeWeight: 2, strokeOpacity: 0.95,
          clickable: true,
        });
        listenersRef.current.push(naver.maps.Event.addListener(poly, "click", () => focus(b)));
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
  }, [layer, pinMode, ready, map, filtered, rentHm, footHm, densHm, center.lat, center.lng]);

  const toggleSaved = (id: string) => setWorkspace((w) => {
    const ids = w.savedIds[districtId] ?? [];
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : ids.length < 3 ? [...ids, id] : ids;
    return { ...w, savedIds: { ...w.savedIds, [districtId]: next } };
  });
  const review = (b: Building) => {
    if (src !== "api") return;
    setCompareOpen(false);
    onReview?.({ districtId, buildingId: b.id, buildingName: b.name });
  };

  return (
    <div className="mapshell">
      {/* 지도 캔버스와 인증 실패 안내는 MapHost 가 그린다 — 여기는 오버레이만. */}

      {/* 상단: 거점 선택 + 검색 + 레이어 토글 */}
      <div className="overlay overlay-top">
        {hubs.length > 0 && (
          <>
            <DistrictPicker className="hub-select" districts={hubs}
              ariaLabel="상권 선택"
              value={districtId} onChange={setDistrictId} />
            <CaveatNote district={hubs.find((h) => h.id === districtId)} />
          </>
        )}
        <input className="search" aria-label="건물 검색" placeholder={`건물 검색 (${hub?.name ?? "가로수길"})`} value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg" role="group" aria-label="지도 데이터 레이어">
          {LAYERS.map((l) => (
            <button key={l.key} aria-pressed={layer === l.key} className={layer === l.key ? "active" : ""} onClick={() => setLayer(l.key)}>{l.label}</button>
          ))}
        </div>
      </div>

      {/* 좌측 리스트 패널 (모바일: 하단 시트) */}
      <div className={"overlay side-panel" + (selected ? " has-selection" : "")}>
        <div className="sp-head">
          {/* PPPP: Product ▶ Page — 이 platform 안에 어떤 page 가 놓일 자리인지를 본다.
              가격대 판단은 Posting(Price ▶ Posting) 의 몫이라 여기서 답하지 않는다. */}
          <div className="sp-track">PRODUCT ▶ PAGE</div>
          <div className="sp-title">{hub?.name ?? "가로수길"} · 건물 공실</div>
          <div className="sp-sub">
            {hub ? `${hub.gu} · ` : ""}{currentInventory ? <>{filtered.length.toLocaleString()}동 · {src === "api" ? "실측" : "샘플"}(추정)</> : "건물 불러오는 중…"}
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
        <div className="building-filters">
          <label>공실 상태<select aria-label="공실 상태 필터" value={workspace.status}
            onChange={(e) => setWorkspace((w) => ({ ...w, status: e.target.value as VacancyFilter }))}>
            <option value="all">전체 상태</option>
            {(Object.keys(STATUS) as VacStatus[]).map((key) => <option key={key} value={key}>{STATUS[key].label}</option>)}
          </select></label>
          <button type="button" aria-pressed={savedOnly} onClick={() => setSavedOnly((value) => !value)}>저장한 후보 {saved.length}</button>
          {(q || workspace.status !== "all" || savedOnly) && <button type="button" onClick={() => {
            setWorkspace((w) => ({ ...w, query: "", status: "all" })); setSavedOnly(false);
          }}>조건 초기화</button>}
        </div>
        <div className="sp-list" aria-label="건물 목록" aria-busy={!currentInventory}>
          {currentInventory && filtered.length === 0 && <div className="building-empty">
            <strong>{buildings.length === 0 ? "제공된 건물이 없습니다" : "조건에 맞는 건물이 없습니다"}</strong>
            <p>{buildings.length === 0 ? "다른 상권을 선택해 주세요." : "검색어·공실 상태를 바꾸거나 저장한 후보 조건을 해제해 주세요."}</p>
          </div>}
          {filtered.map((b) => (
            <div key={b.id} className="building-card">
            <button
              className={"b-item" + (selected?.id === b.id ? " active" : "")}
              aria-pressed={selected?.id === b.id}
              onClick={() => { if (layer !== "vacancy") setLayer("vacancy"); focus(b); }}
            >
              <span className="b-dot" style={{ background: STATUS[b.status].color }} />
              <span>
                <div className="b-name">{b.name}</div>
                <div className="b-meta">{b.industry} · {STATUS[b.status].label}</div>
                <div className="b-meta">수용 {b.capacity}호 · 영업 {b.active}호{b.floors ? ` · 지상 ${b.floors}층` : " · 층수 미상"}</div>
              </span>
              <span className="b-vac" style={{ color: STATUS[b.status].color }}>{vacRate(b)}%</span>
            </button>
            <button className="save-candidate" type="button" aria-label={`${b.name} 후보 ${savedIds.includes(b.id) ? "해제" : "저장"}`}
              aria-pressed={savedIds.includes(b.id)} disabled={src !== "api" || (!savedIds.includes(b.id) && savedIds.length >= 3)}
              onClick={() => toggleSaved(b.id)}>{savedIds.includes(b.id) ? "✓ 저장됨" : "+ 후보 저장"}</button>
            </div>
          ))}
        </div>

        {selected && (
          <div className="b-detail">
            <button className="building-back" type="button" onClick={() => setWorkspace((w) => ({ ...w, selectedId: null }))}>← 건물 목록</button>
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
            <button className="save-candidate detail-save" type="button" aria-pressed={savedIds.includes(selected.id)}
              disabled={src !== "api" || (!savedIds.includes(selected.id) && savedIds.length >= 3)}
              onClick={() => toggleSaved(selected.id)}>{savedIds.includes(selected.id) ? "✓ 후보 저장됨" : "+ 이 건물 후보 저장"}</button>
            {onReview && <button className="building-review" disabled={src !== "api"} onClick={() => review(selected)}>이 건물로 입점 검토 →</button>}
            {src !== "api" && <p className="building-hint">샘플 자료는 후보 저장과 입점 계산에 사용할 수 없습니다.</p>}
          </div>
        )}
        <div className="candidate-tray">
          <div><strong>저장한 후보 {saved.length}/3</strong><span>현재 상권 · 이번 작업 동안 유지</span></div>
          <button type="button" disabled={saved.length === 0} onClick={() => setCompareOpen(true)}>후보 비교</button>
        </div>
      </div>

      {compareOpen && <CandidateCompare districtName={hub?.name ?? districtId}
        candidates={saved.map((b) => ({ ...b, statusLabel: STATUS[b.status].label, vacancyRate: b.capacity > 0 ? vacRate(b) : null }))}
        notes={Object.fromEntries(saved.map((b) => [b.id, workspace.notes[`${districtId}:${b.id}`] ?? ""]))}
        onNote={(id, value) => setWorkspace((w) => ({ ...w, notes: { ...w.notes, [`${districtId}:${id}`]: value } }))}
        onRemove={toggleSaved} onClose={() => setCompareOpen(false)}
        onReview={onReview ? (id) => { const b = saved.find((item) => item.id === id); if (b) review(b); } : undefined} />}

      {/* 유동인구 레이어 전용 시간 슬라이더 = 흐름 축 */}
      {layer === "footfall" && (
        <div className="overlay time-bar">
          <span className="t">{String(hour).padStart(2, "0")}:00</span>
          <input type="range" min={0} max={23} value={hour} onChange={(e) => setHour(+e.target.value)} />
        </div>
      )}

      {/* 범례 */}
      <div className="overlay legend">
        {/* 범례는 **지금 화면에 그려진 것만** 말한다. 점 모드에서 만실·부분공실 칩을
            띄우면 "그 색도 어딘가 있다"는 거짓말이 된다(줌을 당겨야 나온다). */}
        {layer === "vacancy" && (pinMode ? ["empty"] : (Object.keys(STATUS) as VacStatus[])).map((k) => (
          <span key={k} className="chip">
            <span className={"sw" + (pinMode ? " dot" : "")} style={{ background: STATUS[k as VacStatus].color }} />
            {STATUS[k as VacStatus].label}
          </span>
        ))}
        {layer === "vacancy" && pinMode && (
          <span className="note">공실의심만 표시 · 확대하면 건물별 상태</span>
        )}
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
        {layer === "rent" && <span className="note">평당 임대시세 · {rentHm?.unit ?? "만원/평"} <span style={{ color: "#0f7a55", background: "#e3f5ee", border: "1px solid #b7e3d2", borderRadius: 5, padding: "1px 5px", fontSize: 10, fontWeight: 700 }}>R-ONE</span></span>}
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
