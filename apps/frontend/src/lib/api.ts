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
 * 백엔드(app/api/v1)가 단일 소스로 제공하는 서울 54 Page 거점 데이터.
 * 공실 수치는 Gold 실측 우선(13거점) · 나머지는 합성 폴백 — vacancy_source 로 구분한다.
 * 감성·입점 유닛·행사는 아직 시드(app/data/seoul_pages.py).
 */

/** 공실 수치의 출처 — 합성값을 실측처럼 표시하지 않기 위한 구분자 */
export type VacancySource = "gold" | "synthetic";
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
  /** 공실 수치 출처. "gold"면 실측 건물 집계, "synthetic"이면 합성 그리드 */
  vacancy_source: VacancySource;
  /** Gold 경로에서만 — 집계에 쓰인 건물 수 / 마스터 전체 대비 비율(%) */
  building_count: number | null;
  precision_pct: number | null;
  /** 앵커 대조 — 거점별 R-ONE 중대형상가 공실률과 격차(%p).
   *  모집단·단위가 달라(우리는 호실·전수, R-ONE 은 면적·표본) 격차 0 이 정상은 아니다.
   *  절대값이 아니라 거점 간 비교·추세 감시용. */
  anchor_pct: number | null;
  anchor_gap_pp: number | null;
  /** Platform·LSTM 다음 분기 예측 — forecast 미배포 시 null */
  predicted_rate: number | null;
  predicted_delta: number | null;
  predicted_direction: "up" | "down" | null;
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

/** 입력 필드별 출처 — 프록시를 실측으로 오독하지 않기 위한 구분자.
 *  "rone" R-ONE 임대료 · "flpop+seed" 유동인구+거점 내 서열 · "seed" 손으로 적은 프록시 */
export type PostingInputSource = Record<"area" | "rent" | "prem" | "foot", string>;

export interface PostingUnit {
  id: string; n: string; grp: string; lat: number; lng: number;
  area: number; rent: number; prem: number; floor: string; was: string;
  rec: string; foot: string; persona: string; note: string;
  /** rent·foot 은 실데이터, area·prem 은 소스가 없어 시드로 남아 있다 */
  inputs_source?: PostingInputSource | null;
}

/** 공실 유닛 + 3-Tier 시나리오 — GET /commercial-districts/{id}/postings */
export interface Posting extends PostingUnit {
  scenarios: Record<string, TierScenario>;
}

/** 상권 행사. 실데이터(서울 문화행사)와 시드가 같은 타입으로 흐른다.
 *  시드에만 있던 k2(효과 지표)·roles·ha 는 근거가 없어 실데이터로 승계하지 않았다. */
export interface MarketingEvent {
  id: string; n: string; lat: number; lng: number; ic: string; when: string;
  /** 시드 전용 — 실데이터에서는 null */
  k2?: string | null; desc?: string | null; roles?: string[] | null; ha?: string | null;
  /** 실데이터 전용 — 시드에서는 null */
  category?: string | null; place?: string | null; org?: string | null;
  fee?: string | null; target?: string | null; link?: string | null;
  distance_m?: number | null;
}

/** 상권 마케팅 — GET /marketing/{id} */
export interface Marketing {
  district_id: string; events: MarketingEvent[]; online_contents: string[];
  /** 온라인 콘텐츠 출처 — "llm"(Gold 컨텍스트 기반 생성) | "seed"(폴백) */
  source?: string;
  /** 행사 출처 — "seoul-open-data"(실데이터) | "seed". 실데이터인데 0건이면
   *  그 거점에 예정된 공공 문화행사가 없다는 뜻이다(시드로 채우지 않는다). */
  events_source?: string;
}

/** 100m 그리드 공실 셀 — lat/lng 는 셀 남서(SW) 모서리, dlat/dlng 는 셀 크기 */
export interface HeatCell {
  i: number; j: number; lat: number; lng: number;
  c_lat: number; c_lng: number; v: number; stores: number; vac_n: number;
  dlat: number; dlng: number;
  /** Gold 경로에서만 — 셀의 총 호실 수(공실률 분모)와 집계된 건물 수 */
  capacity?: number | null; buildings?: number | null;
}

/** 거점 공실 히트맵 — GET /heatmap/vacancy?district={id} */
export interface VacancyHeatmap {
  district_id: string; resolution_m: number;
  cells: HeatCell[]; sum_stores: number; sum_vac: number; avg_vacancy: number;
  /** 공실 수치 출처 — "gold"면 실측 건물 집계, "synthetic"이면 합성 그리드 */
  vacancy_source: VacancySource;
  /** Gold 경로에서만 — 총 호실 수, 집계 건물 수, 마스터 전체 건물 수, 정밀 표본 비율(%),
   *  집합건물로 제외된 건물 수(분자 미매칭이라 대표 집계에서 뺀다) */
  capacity: number | null; buildings: number | null;
  buildings_total: number | null; precision_pct: number | null;
  excluded_mall: number | null;
  /** 앵커 대조 — R-ONE 중대형상가 공실률과 격차(%p). DistrictSummary 와 동일 의미 */
  anchor_pct: number | null; anchor_gap_pp: number | null;
  /** Platform·LSTM 다음 분기 예측 (거점 단위) — forecast 미배포 시 null */
  predicted_rate: number | null;
  predicted_delta: number | null;
  predicted_direction: "up" | "down" | null;
}

export interface RentCell {
  i: number; j: number; lat: number; lng: number;
  c_lat: number; c_lng: number; dlat: number; dlng: number;
  v: number; rent_per_pyeong: number;
}

export interface RentHeatmap {
  district: string;
  rent_source: "rone";
  unit: "만원/평";
  cells: RentCell[];
}

/** 서울 13 Page 거점 요약(감성·공실·리뷰·Tier) — 거점 대시보드 */
export const listDistricts = () => getJSON<DistrictSummary[]>("/commercial-districts");
/** 거점 전체 원천 데이터(zones/units/events/poi/grid) */
export const getDistrict = (id: string) => getJSON<DistrictDetail>(`/commercial-districts/${id}`);
/** 거점 감성 구역(Platform) */
export const getSentiment = (id: string) => getJSON<Zone[]>(`/commercial-districts/${id}/sentiment`);
/** 거점 100m 공실 히트맵(Page) */
export const getVacancyHeatmap = (id: string) => getJSON<VacancyHeatmap>(`/heatmap/vacancy?district=${id}`);
/** 거점 100m 임대시세 레이어(Page) */
export const getRentHeatmap = (id: string) => getJSON<RentHeatmap>(`/heatmap/rent?district=${id}`);
/** 건물 단위 공실 GeoJSON(FeatureCollection) — Page 공실 폴리곤 레이어 */
export const getBuildingVacancy = (district: string) =>
  getJSON<GeoJSONFC>(`/heatmap/buildings?district=${district}`);

/** 건물 공실 GeoJSON 최소 타입 */
export interface BuildingProps {
  id: string; name: string; status: "full" | "partial" | "high" | "empty";
  capacity: number; active: number; industry: string; vacancy_rate: number;
  /** 건축물대장 지상 층수(V-World). 0 또는 누락 가능 — 3D 트윈 층 스택의 근거.
   *  capacity(호 수)와 단위가 다르므로 층 수가 필요한 곳에서 capacity 를 대신 쓰지 말 것. */
  floors?: number;
  /** 건물 높이(m). 미사용 시 무시 가능. */
  height?: number;
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
/** 거점(상권) 마케팅 — 온라인 콘텐츠는 Gold 기반 생성(Program), 행사는 시드 */
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

/* ===== 가게 단위 마케팅 솔루션(Program 1단계) — POST /marketing/generate ===== */

/** 가게 프로필. 수집 채널(점주 제공·네이버 지역검색·카카오 로컬)에 무관한 정규화 입력 계약.
 *  백엔드 schemas/marketing.py::StoreProfile 와 1:1 대응한다. */
export interface StoreProfileInput {
  name: string; category: string; district_id?: string; address?: string;
  reviews?: string[]; image_urls?: string[]; keywords?: string[];
}

/** 제안 1건 — 채널·실행안·근거. 근거 없는 제안은 만들지 않는 것이 Program 의 원칙이다. */
export interface ChannelPlan {
  channel: string; kind: "online" | "offline"; content: string; rationale: string;
}

/** 생성 결과. `source` 가 "rule-stub" 이면 LLM 을 못 탄 폴백이라 내용이 일반론이다 —
 *  화면에서 반드시 구분해 보여준다(실호출 결과처럼 읽히면 안 된다). */
export interface StoreMarketing {
  store_name: string; category: string; tone_keywords: string[];
  online: ChannelPlan[]; offline: ChannelPlan[]; ha_check: string;
  source: "llm" | "rule-stub" | string;
}

/** 가게 단위 마케팅 광고 솔루션 자동 생성(Program) — 상가 사진·정보·리뷰 기반 */
export const generateStoreMarketing = (profile: StoreProfileInput) =>
  postJSON<StoreMarketing>("/marketing/generate", profile);
