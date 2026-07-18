/** SpaceOS 백엔드 API 클라이언트 (골격). */

const BASE = "/api/v1";

export interface Health {
  status: string;
  version: string;
}

export async function getHealth(): Promise<Health> {
  const res = await fetch("/health");
  if (!res.ok) throw new Error("health check failed");
  return res.json();
}

export async function getBuildingHistory(buildingId: string) {
  const res = await fetch(`${BASE}/buildings/${buildingId}/history`);
  if (!res.ok) throw new Error("failed to load history");
  return res.json();
}

/* ===== 거점(commercial district) API =====
 * 백엔드(app/api/v1)가 단일 소스로 제공하는 서울 13 Page 거점 데이터
 * (시드: app/data/seoul_pages.py — Gold 교체 TODO).
 */
async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

/** 거점 요약 — GET /commercial-districts (backend DistrictSummary 스키마) */
export interface DistrictSummary {
  id: string; name: string; gu: string; type: string;
  center: [number, number]; note: string; rec_top: string;
  sentiment: number; reviews: number; risk_zones: number;
  vacancy_rate: number; vacant_units: number; cell_count: number; store_count: number;
  tier_mix: { premium: number; value: number; factory: number };
}

/** 감성 구역(Zone) — f: [키워드, 증감, 방향(up|dn)][] */
export interface Zone {
  id: string; n: string; grp: string; lat: number; lng: number;
  s: number; d: number; r: number; f: [string, string, string][];
}

/** 거점 전체 원천 데이터 — GET /commercial-districts/{id} */
export interface DistrictDetail {
  id: string; name: string; sub: string; gu: string; type: string;
  center: [number, number]; zoom: number;
  poi: [number, number, string, string][];
  zones: Zone[];
  units: PostingUnit[];
  events: MarketingEvent[];
  insta: string[];
}

export interface TierScenario {
  tier: string; name: string; sub: string;
  invest_mn: number; month_cost: number; month_rev: number; month_net: number;
  roi_months: number; recommended: boolean;
}

export interface PostingUnit {
  id: string; n: string; grp: string; lat: number; lng: number;
  area: number; rent: number; prem: number; floor: string; was: string;
  rec: string; foot: string; persona: string; note: string;
}

/** 공실 유닛 + 3-Tier 시나리오 — GET /commercial-districts/{id}/postings */
export interface Posting extends PostingUnit {
  scenarios: Record<string, TierScenario>;
}

export interface MarketingEvent {
  id: string; n: string; lat: number; lng: number; ic: string; when: string;
  k2: string; desc: string; roles: string[]; ha: string;
}

/** 상권 마케팅 — GET /marketing/{id} */
export interface Marketing {
  district_id: string; events: MarketingEvent[]; online_contents: string[];
}

/** 100m 그리드 공실 셀 — lat/lng 는 셀 남서(SW) 모서리, dlat/dlng 는 셀 크기 */
export interface HeatCell {
  i: number; j: number; lat: number; lng: number;
  c_lat: number; c_lng: number; v: number; stores: number; vac_n: number;
  dlat: number; dlng: number;
}

/** 거점 공실 히트맵 — GET /heatmap/vacancy?district={id} */
export interface VacancyHeatmap {
  district_id: string; resolution_m: number;
  cells: HeatCell[]; sum_stores: number; sum_vac: number; avg_vacancy: number;
}

/** 서울 13 Page 거점 요약(감성·공실·리뷰·Tier) — 거점 대시보드 */
export const listDistricts = () => getJSON<DistrictSummary[]>("/commercial-districts");
/** 거점 전체 원천 데이터(zones/units/events/poi/grid) */
export const getDistrict = (id: string) => getJSON<DistrictDetail>(`/commercial-districts/${id}`);
/** 거점 감성 구역(Platform) */
export const getSentiment = (id: string) => getJSON<Zone[]>(`/commercial-districts/${id}/sentiment`);
/** 거점 100m 공실 히트맵(Page) */
export const getVacancyHeatmap = (id: string) => getJSON<VacancyHeatmap>(`/heatmap/vacancy?district=${id}`);
/** 건물 단위 공실 GeoJSON(FeatureCollection) — Page 공실 폴리곤 레이어 */
export const getBuildingVacancy = (district: string) =>
  getJSON<GeoJSONFC>(`/heatmap/buildings?district=${district}`);

/** 건물 공실 GeoJSON 최소 타입 */
export interface BuildingProps {
  id: string; name: string; status: "full" | "partial" | "high" | "empty";
  capacity: number; active: number; industry: string; vacancy_rate: number;
}
export interface GeoJSONFC {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Polygon"; coordinates: number[][][] };
    properties: BuildingProps;
  }>;
}
/** 거점 공실 유닛 + 3-Tier 시나리오(Posting) */
export const getPostings = (id: string) => getJSON<Posting[]>(`/commercial-districts/${id}/postings`);
/** 거점(상권) 마케팅 — TODO: Platform 수집 정보(Gold) 기반 생성으로 교체(Program) */
export const getMarketing = (id: string) => getJSON<Marketing>(`/marketing/${id}`);

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

/** 입점 시뮬레이션(Posting) — 외부 AI 창업 코파일럿 어댑터 경유(미설정 시 3-Tier 폴백) */
export const simulateRevenue = (req: {
  district_id: string; unit_id?: string; industry_type?: string; strategy?: string;
}) => postJSON<unknown>("/ai/simulate-revenue", req);

/** 가게 단위 마케팅 광고 솔루션 자동 생성(Program) — 상가 사진·정보·리뷰 기반 */
export const generateStoreMarketing = (profile: {
  name: string; category: string; district_id?: string; address?: string;
  reviews?: string[]; image_urls?: string[]; keywords?: string[];
}) => postJSON<unknown>("/marketing/generate", profile);
