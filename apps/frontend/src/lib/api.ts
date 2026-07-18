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
 * 백엔드(app/api/v1)로 분리된 9거점 데이터.
 * 현재 프론트 컴포넌트(CityDashboard / DistrictPPPP)는 정적 모듈을 사용 중.
 * TODO: 아래 함수로 교체해 서버 단일 소스로 전환(로딩/에러 상태 처리 추가).
 */
async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

/** 9거점 요약(감성·공실·리뷰·Tier) — City Dashboard */
export const listDistricts = () => getJSON<unknown[]>("/commercial-districts");
/** 거점 전체 원천 데이터(zones/units/events/poi/grid) — DistrictPPPP */
export const getDistrict = (id: string) => getJSON<unknown>(`/commercial-districts/${id}`);
/** 거점 감성 구역(Platform) */
export const getSentiment = (id: string) => getJSON<unknown[]>(`/commercial-districts/${id}/sentiment`);
/** 거점 100m 공실 히트맵(Page) */
export const getVacancyHeatmap = (id: string) => getJSON<unknown>(`/heatmap/vacancy?district=${id}`);
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
export const getPostings = (id: string) => getJSON<unknown[]>(`/commercial-districts/${id}/postings`);
/** 거점(상권) 마케팅 — TODO: Platform 수집 정보(Gold) 기반 생성으로 교체(Program) */
export const getMarketing = (id: string) => getJSON<unknown>(`/marketing/${id}`);

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
