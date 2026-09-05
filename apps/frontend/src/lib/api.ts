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
  /** 도시 슬러그(seoul/goyang/paju) — 54거점이 전부 서울이던 동안은 암묵이었다.
   *  경기 거점이 같은 목록에 섞이면 화면이 이 값으로 가른다. */
  city: string;
  /** 화면 표기(서울/고양/파주) */
  city_name: string;
  /** 시드 없이 Gold 만으로 서는 거점(경기). 감성·예측 축이 null 이어도 정상이다. */
  measured_only?: boolean;
  /** 예외 표시 — 비어 있지 않으면 이 거점의 수치를 다른 거점과 직접 비교하면 안 된다.
   *  (예: 일산 라페스타·웨스턴돔 — 계획상가 밀집으로 공실 분모가 재고 일부만 덮는다) */
  caveat?: string;
  center: [number, number]; note: string; rec_top: string;
  sentiment: number | null; reviews: number | null; risk_zones: number | null;
  /** 거점 대표 공실률(%). **null 이 두 가지 뜻을 갖지 않게** `vacancy_withheld` 와 함께 읽는다:
   *    withheld=false + null → 재지 않았다
   *    withheld=true  + null → 쟀지만 거점을 대표하지 못해 **내렸다**(계획상가 밀집) */
  vacancy_rate: number | null;
  vacancy_withheld?: boolean;
  /** 대표 집계의 분모가 이 거점 상업 재고에서 차지하는 비율(%) — 호실 기준.
   *  `precision_pct`(지번 기준)와 다른 것을 잰다. 낮을수록 대표값을 믿을 이유가 준다. */
  inventory_coverage_pct?: number | null;
  vacant_units: number; cell_count: number; store_count: number;
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
  /** 월 순익이 0 이하면 false — 회수기간이 정의되지 않는다.
   *  "모른다"와 "안 된다"는 다른 정보다. 화면이 둘 다 "—"로 뭉개면 안 된다. */
  viable: boolean;
  /** 이 회수기간이 **어떤 비용까지** 넣고 계산됐는지.
   *  "kosis-opex+measured-revenue" = KOSIS 영업비용률 + 거점별 실측 평당매출(2026-08-23~)
   *  "rent+fitout"                 = 원가·인건비가 빠진 낡은 폴백 */
  basis: string;
}

/** basis 문자열 → 화면에 붙일 짧은 배지 라벨. 모르는 값은 그대로 노출한다. */
export const BASIS_LABEL: Record<string, string> = {
  "kosis-opex+measured-revenue": "KOSIS 실측비용",
  "rent+fitout": "비용 일부 미반영",
};

/** 입력 필드별 출처 — 프록시를 실측으로 오독하지 않기 위한 구분자.
 *  "rone" R-ONE 임대료 · "flpop+seed" 유동인구+거점 내 서열 · "seed" 손으로 적은 프록시 */
export type PostingInputSource = Record<"area" | "rent" | "prem" | "foot", string> & {
  /** 층 근거 — "flr_ouln"(층별개요 면적 비중 실측) / "assumed_1f"(폴백, 임대료 상한).
   *  rent 출처("rone")와 **다른 축**이다. 한 라벨에 뭉치면 상한과 하한이 같은
   *  이름으로 나간다 → docs/feature-posting.md §0-L */
  floor?: string;
};

export interface PostingUnit {
  id: string; n: string; grp: string; lat: number; lng: number;
  area: number; rent: number; prem: number; floor: string; was: string;
  foot: string;
  /** 시드에만 있던 서술 필드 — 실 인벤토리(건축물대장 실측)에는 없다(2026-08-24 배선) */
  rec?: string | null; persona?: string | null; note?: string | null;
  /** rent·foot 은 실데이터, area 는 대장, prem 은 입력 계약(없으면 "absent") */
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
  /** HA 후처리 검증 결과. violation 이 있는데 source 가 "seed" 면 LLM 이 생성은 했으나
   *  검증에 걸려 폐기된 것이다 — 키 미설정·Gold 미적재 폴백과 구분된다. */
  ha_findings?: HAFinding[];
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
  cells: HeatCell[]; sum_stores: number; sum_vac: number;
  /** 거점 평균 — DistrictSummary.vacancy_rate 와 같은 값·같은 null 규칙.
   *  셀(`cells`)은 내려가지 않는다: 내린 것은 셀이 아니라 거점 하나로 뭉친 대표값이다. */
  avg_vacancy: number | null;
  vacancy_withheld?: boolean;
  inventory_coverage_pct?: number | null;
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
/** 유동·밀도 레이어의 셀 (공실·임대와 같은 100m 격자) */
export interface TrdarCell {
  i: number; j: number;
  lat: number; lng: number; c_lat: number; c_lng: number;
  dlat: number; dlng: number;
  v: number;
  /** 이 셀이 값을 가져온 상권 이름 — 상권 경로에서만 채워진다 */
  trdar?: string;
  /** 이 셀이 값을 가져온 집계구 코드 — 집계구 경로에서만 채워진다 */
  oa?: string;
}

/**
 * 시간대별 유동인구 레이어(Page).
 *
 * ⚠ `resolution` 은 값이 **어느 구획의 집계**인지를 뜻한다. 어느 쪽이든 셀 값은 그
 * 셀의 실측이 아니다 — 범례에 반드시 함께 노출한다.
 * - `jipgyegu` : 집계구(거점당 중앙 26곳, 면적 중앙 약 22,000㎡). 2026-08-26 부터 기본.
 * - `trdar`    : 상권(거점당 1~9곳·중앙 3). 집계구 산출물이 없을 때의 폴백.
 * 2026-08-23 이전에는 이 레이어가 `Math.random()` 이었다.
 */
export interface FootfallHeatmap {
  district: string;
  footfall_source: "flpop_jipgyegu" | "trdar";
  resolution: "jipgyegu" | "trdar";
  /** 집계구 경로에서 쓴 집계구 수. 상권 경로에서는 없다. */
  oa_count?: number;
  /** 상권 경로에서 쓴 상권 수. 집계구 경로에서는 0 이다(‘없다’가 아니라 ‘안 썼다’). */
  trdar_count: number;
  hour: number;
  band: string;
  band_label: string;
  /**
   * 2026-08-24: **시간 축**은 생활인구(행정동 x 24시간)로 갈아끼웠다.
   * `resolution`/`footfall_source` 는 여전히 공간 해상도(상권)를 뜻하고 바뀌지 않는다.
   * - `jipgyegu_hourly` : 공간·시간이 **한 표**에서 나온다. 구성비 곱셈이 없다
   *   (`share_basis: null`). 거점 내부에서 시각에 따라 셀 서열이 바뀐다.
   * - `adong_hourly` : 24시간 눈금. `daytype` 으로 평일/주말이 갈린다.
   * - `trdar_band`   : 산출물이 그 거점을 못 담을 때의 종전 6구간 폴백.
   * `share_basis` 가 다른 두 응답의 셀 값은 **눈금이 달라 직접 비교할 수 없다**.
   */
  time_source?: "jipgyegu_hourly" | "adong_hourly" | "trdar_band";
  daytype?: "weekday" | "weekend";
  share_basis?: "hour24" | "band6" | null;
  hour_share?: number | null;
  unit: string;
  min: number; max: number;
  note: string;
  cells: TrdarCell[];
}

/** 상권 밀도 레이어(Page). `metric="flpop"` 은 **유동인구** 밀도다(상주인구 아님). */
export interface DensityHeatmap {
  district: string;
  density_source: "flpop_jipgyegu" | "trdar";
  resolution: "jipgyegu" | "trdar";
  oa_count?: number;
  trdar_count: number;
  metric: "flpop" | "stor";
  /**
   * ⚠ **분자의 정의**가 경로마다 다르다 — 안 보고 값을 나란히 놓으면 안 된다.
   * - `flpop_mean24_per_1k_m2` : 집계구 24시간 평균 생활인구 ÷ 폴리곤 면적
   * - 없음(상권 경로)          : 일 총량 기준 `flpop_per_1k_m2`
   * 점포 밀도(`stor`)는 집계구 원천이 없어 **항상 상권**이다.
   */
  density_basis?: "flpop_mean24_per_1k_m2";
  unit: string;
  label: string;
  min: number; max: number;
  note: string;
  cells: TrdarCell[];
}

/** 거점 시간대별 유동인구 레이어(Page) — hour 0~23 */
export const getFootfallHeatmap = (
  id: string, hour: number, daytype: "weekday" | "weekend" = "weekday",
) =>
  getJSON<FootfallHeatmap>(
    `/heatmap/footfall?district=${id}&hour=${hour}&daytype=${daytype}`);
/** 거점 상권 밀도 레이어(Page) */
export const getDensityHeatmap = (id: string, metric: "flpop" | "stor" = "flpop") =>
  getJSON<DensityHeatmap>(`/heatmap/density?district=${id}&metric=${metric}`);
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
  /** 상업 용도 층 번호 — 공실률의 분모가 되는 층. 층 근거(건축물대장 층별개요)가
   *  있는 건물에만 실린다. 없으면 3D 트윈이 '아래부터 채우기' 근사로 폴백한다. */
  com_floors?: number[] | null;
  /** 점포(상가정보 flrNo)·인허가로 **확인된** 영업 층 번호 — 분자의 하한. */
  occ_floors?: number[] | null;
  /** 층 미상 점포로 빈 상업층에 배정된 층 수(상한 − 하한). 트윈의 '불확실' 층. */
  unknown_n?: number | null;
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

/* ===== 층 단위 공실 매물 목록(Page) — GET /commercial-districts/{id}/floor-vacancies ===== */

/** 매물 하나 = (지번, 층).
 *  ⚠ `Posting`(건물 단위 유닛 + 3-Tier 시나리오)과 **다른 것을 센다**. 여기는 목록이라
 *     임대료·ROI 가 없고, 일부 층만 빈 건물(`partial`)이 들어온다. 층으로 쪼갠 표본을
 *     ROI 계산에 쓰면 프리미엄 트립와이어가 부호를 넘는다 → feature-posting.md §0-Q·§0-T */
/** 같은 조건(대장 용도·층)의 자리에서 **실제 영업 중인** 업종 분포.
 *  ⚠ 추천이 아니라 관측이다 — 그 자리에서 잘 된다는 뜻이 아니고(매출·생존 미고려),
 *     GNN 업종 추천(`recommendIndustry`)과도 다른 축이다(저쪽은 좌표 기준 7종 라벨). */
export interface IndustryFit {
  /** "purps_floor" 용도+층 관측 · "floor" 용도 표본이 얇아 층만 본 폴백 */
  basis: "purps_floor" | "floor" | string;
  n: number;
  top: Array<{ industry: string; share: number; n: number }>;
  note: string;
}

export interface FloorVacancyUnit {
  id: string;
  building_id?: string | null;
  pnu?: string | null;
  /** 한 지번에 접힌 동 수. 2 이상이면 **어느 동인지는 모른다**(층 근거가 지번 단위). */
  bldgs_on_pnu: number;
  n: string; lat: number; lng: number;
  floor: number; floor_label: string;
  /** "confirmed" 비었음이 확정 · "probable" 층 미상 점포가 다른 층이면 빈다.
   *  둘을 같은 모양으로 그리면 추정이 실측처럼 읽힌다 — 반드시 구분할 것. */
  certainty: "confirmed" | "probable";
  /** 평 — 그 **층의** 건축물대장 실측이다(균등분할이 아니라 층마다 다르다). */
  area: number; area_m2: number;
  /** 대장이 그 층에 허용한 용도. 업종 후보를 거르는 근거이지 현재 영업 업종이 아니다. */
  purps: string;
  bld_status?: string | null;
  bld_floors: number;
  bld_vacancy_rate?: number | null;
  com_floors: number[]; occ_floors: number[]; unknown_n: number;
  was: string;
  /** 근거가 없으면 **없다**. 빈 배열이 아니라 부재로 온다 —
   *  빈 목록을 주면 "이 자리에 들어갈 업종이 없다"로 읽힌다. */
  fit?: IndustryFit | null;
}

export interface FloorVacancyList {
  district_id: string;
  /** 필터 적용 **뒤** 유닛 수 */
  total: number;
  counts: { confirmed: number; probable: number };
  /** 필터 **전** 거점 전체 — 목록이 잘린 것인지 원래 없는 것인지 가르는 분모 */
  counts_all: { units?: number; confirmed?: number; probable?: number; buildings?: number };
  by_floor: Record<string, number>;
  built_at?: string | null;
  source?: string | null;
  note?: string | null;
  /** 적합도 표 자체의 근거·한계(조인율 약 30% 등) */
  fit_meta?: { built_at?: string; note?: string; min_sample?: number;
    stats?: Record<string, number> } | null;
  units: FloorVacancyUnit[];
}

/** 층 단위 공실 매물 목록. 404 = 이 거점에 층 산출물이 없다(거점을 모른다가 아니다). */
export const getFloorVacancies = (
  id: string,
  opt: { certainty?: "confirmed" | "probable"; floor?: number; minArea?: number; maxArea?: number; limit?: number } = {},
) => {
  const q = new URLSearchParams();
  if (opt.certainty) q.set("certainty", opt.certainty);
  if (opt.floor != null) q.set("floor", String(opt.floor));
  if (opt.minArea != null) q.set("min_area", String(opt.minArea));
  if (opt.maxArea != null) q.set("max_area", String(opt.maxArea));
  q.set("limit", String(opt.limit ?? 300));
  return getJSON<FloorVacancyList>(`/commercial-districts/${id}/floor-vacancies?${q}`);
};
/** 거점(상권) 마케팅 — 온라인 콘텐츠는 Gold 기반 생성(Program), 행사는 시드 */
export const getMarketing = (id: string) => getJSON<Marketing>(`/marketing/${id}`);

async function postJSON<T>(
  path: string,
  body: unknown,
  extraHeaders: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...extraHeaders },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

/** 입점 시뮬레이션 결과 — 코파일럿·폴백이 같은 스키마로 흐른다. */
export interface SimulateResult {
  district_id: string; unit_id: string; industry_type: string | null;
  scenarios: Record<string, TierScenario>;
  /** "copilot" | "fallback-3tier" */
  source: string;
  /** 폴백으로 떨어진 **이유**. 코파일럿 미설정이면 null(폴백이 정상 동작이다),
   *  설정돼 있는데 실패했으면 사유가 온다. 둘을 섞으면 코파일럿이 죽어도 모른다. */
  source_note: string | null;
  /** 입력 필드별 출처. prem 이 "absent" 면 권리금 0 은 관측이 아니라 **전제**다. */
  inputs_source: PostingInputSource | null;
  inputs_quarter: string | null;
  /** 세 전략 모두 회수 불가일 때만 채워진다 — "추천이 없다"와 "회수가 안 된다"는 다르다. */
  unviable_note: string | null;
}

/** 입점 시뮬레이션(Posting) — 외부 AI 창업 코파일럿 어댑터 경유(미설정 시 3-Tier 폴백).
 *  `prem`(권리금, 만원)은 **입력 계약**이다 — 공개 통계가 없어 그 자리에 들어갈 기업만 안다.
 *  안 보내면 0 을 전제로 계산하고 `inputs_source.prem === "absent"` 가 그 사실을 밝힌다. */
export const simulateRevenue = (req: {
  district_id: string; unit_id?: string; industry_type?: string;
  strategy?: string; prem?: number;
}) => postJSON<SimulateResult>("/ai/simulate-revenue", req);

/* ===== Platform 정체성·자리 제안 — GET /commercial-districts/{id}/platform ===== */

/** 업종 군(카카오 플레이스 라벨을 묶은 것). members 로 근거 라벨을 펼쳐 볼 수 있다. */
export interface CategoryGroup {
  group: string; n: number; share: number;
  members: { label: string; n: number }[];
}

/** 검색 트렌드 한 계열. direction 은 최근 3개월 vs 직전 3개월(±5% 보합)로 **계산된** 값이다. */
export interface TrendSeries {
  keyword: string; prior: number; recent: number; change_pct: number;
  direction: "up" | "down" | "flat";
  points: { period: string; value: number }[];
}

/** TRDAR 수요신호 — 누가·언제 오는가. 값이 없는 거점은 필드가 비어 온다. */
export interface DemandSignal {
  bands?: { band: string; label: string; flpop: number; selng: number | null; gap: number | null }[];
  peak_band?: string | null;
  gap_band?: string | null;
  ages?: { band: string; share: number }[];
  female_share?: number; weekend_flpop?: number; weekend_selng?: number;
  store_count?: number; franchise_share?: number;
  open_rate?: number; close_rate?: number; trdar_n?: number;
}

/** "이 상권은 어떤 플랫폼인가" — 감성은 여기 없다(전부 시드라 근거로 쓰지 않는다). */
export interface PlatformIdentity {
  archetype: string | null;
  /** 유형 라벨을 만든 규칙 그대로. 화면에 같이 적어 판정을 감사할 수 있게 한다. */
  archetype_rule: string;
  categories: { groups: CategoryGroup[]; ungrouped: { label: string; n: number }[]; total: number };
  /** 표시용 불용어를 걸렀으면 dropped 로 몇 개인지 밝힌다(조용히 지우지 않는다) */
  keywords: { words: { word: string; n: number }[]; dropped: number; scanned: number };
  trends: TrendSeries[];
  demand: DemandSignal;
  source: string;
}

/** "어느 자리에 어떤 업소가 들어오면 좋은가" — 자리는 실측 공실 유닛이다.
 *  ⚠ `was`(직전 업종)는 상가정보 분류, `recommendations`는 GNN 7군이라 **눈금이 다르다**.
 *     둘을 자동으로 비교해 "업종 전환"이라고 판정하지 말 것. */
export interface OpeningSite {
  unit_id: string; name: string;
  lat: number | null; lng: number | null;
  area_py: number | null; floor: string | null;
  capacity: number | null; vacancy_rate: number | null;
  was: string | null;
  recommendations: IndustryRec[];
  matched_distance_m: number | null;
  /** 이 자리에서 **상권 평균 대비** 가장 두드러지는 업종.
   *  GNN Top-1 은 상권 사전확률에 눌려 거의 모든 자리가 같은 답을 낸다 — 평균을 빼야
   *  자리별 신호가 남는다. 노드 Top-3 밖 업종을 0 으로 보는 근사라 **자리 간 비교용**이다. */
  distinct: { industry: string; score: number; district_mean: number; delta_pp: number } | null;
}

export interface PlatformProfile {
  district_id: string;
  identity: PlatformIdentity | null;
  openings: {
    sites: OpeningSite[]; unit_count: number; matched_count: number;
    match_radius_m: number; source: string; distinct_note?: string;
  };
}

/** Platform 정체성 + 자리 제안. 산출물이 없는 거점은 404. */
export const getPlatformProfile = (id: string) =>
  getJSON<PlatformProfile>(`/commercial-districts/${id}/platform`);

/* ===== LSTM 공실 예측(Platform 5-1) — POST /ai/predict-vacancy ===== */

/** 재귀 예측 1분기. h2 부터는 외생 피처를 마지막 관측값으로 고정한 근사다. */
export interface ForecastHorizon {
  quarter: string; forecast_vac_proxy: number; delta: number; direction: "up" | "down";
}

/** 공실 예측 응답.
 *  ⚠ 단위는 **공실률(%)이 아니라 vac_proxy(공실 프록시)** 다 — R-ONE 실측은 피처로 들어간다.
 *     화면에 %로 쓰려면 `delta` 를 현재 공실률에 가산하는 근사만 허용된다
 *     (백엔드 services/districts._predicted 와 같은 식).
 *  ⚠ `model === "lstm-stub"` 은 Gold 미적재 폴백이다(HTTP 200). 실측처럼 그리면 안 된다. */
export interface VacancyForecast {
  district_id: string;
  model: string;
  forecast_vac_proxy: number;
  last_vac_proxy: number;
  delta: number;
  direction: "up" | "down";
  last_quarter: string;
  forecast_quarter?: string;
  n_quarters: number;
  horizons: ForecastHorizon[];
  horizon_quarters: number;
  trained_at: string | null;
  /** 전체 홀드아웃 지표. `holdout_direction_acc` 는 54거점 표본에서 노이즈가 커
   *  게이트에서 내렸다 — 성능 근거로 인용하지 않는다(MAE 가 주지표). */
  metrics: Record<string, number> | null;
  /** 이 거점의 홀드아웃 1점 — 전체 MAE 뒤에 거점 오차를 숨기지 않기 위해 붙는다 */
  district_holdout?: { pred: number; actual: number; prev: number; direction_hit: boolean };
  /** 지상검증 실측 앵커 (보유 거점에만 — 현재 garosugil) */
  ground_anchor?: {
    estimated_vacancy_pct: number; vacancy_band_pct: [number, number] | null;
    anchor_street_pct: number | null; buildings_used: number | null;
    as_of: string; source: string;
  };
}

/** LSTM 공실 예측 — horizon_months 는 백엔드에서 분기로 환산된다(올림, 1~4 클램프).
 *  ⚠ 미지원 거점은 404 — 호출부에서 잡아 빈 상태로 둔다. */
export const predictVacancy = (district_id: string, horizon_months = 3) =>
  postJSON<VacancyForecast>("/ai/predict-vacancy", { district_id, horizon_months });

/* ===== GNN 업종 추천(Platform 5-2) — POST /ai/recommend-industry ===== */

/** 추천 1건. score 는 그 자리에서 해당 업종일 확률(0~1) */
export interface IndustryRec { industry: string; score: number; }

/** 업종 추천 응답.
 *  ⚠ `model === "gnn-stub"` 은 Gold 미적재 폴백이다(HTTP 200 으로 온다).
 *     실측 추천처럼 그리면 안 된다 — 호출부에서 반드시 구분할 것. */
export interface IndustryRecommend {
  district_id: string;
  model: string;
  /** 학습 지표. test_top3 만 보면 과대평가된다 — baseline_district_prior_top3 와
   *  함께 봐야 한다(거점 사전확률 대비 lift 가 실제 기여분). */
  metrics: Record<string, number> | null;
  /** "node" = 최근접 점포 자리 기준 · "district" = 거점 전체 노드 평균 */
  scope: "node" | "district";
  matched_node_id?: string;
  matched_distance_m?: number;
  recommendations: IndustryRec[];
  building_id?: string | null;
}

/** GNN 업종 추천 — 좌표를 주면 최근접 노드(400m 내), 없으면 거점 평균.
 *  ⚠ 백엔드 필드는 `lon` 이다(프론트 Building.center 는 `lng`). 이름이 달라
 *     그대로 넘기면 조용히 거점 평균으로 떨어진다.
 *  ⚠ 400m 안에 그래프 노드가 없으면 404 — 호출부에서 잡아 빈 상태로 둔다. */
export const recommendIndustry = (req: {
  district_id: string; lat?: number; lon?: number; building_id?: string;
}) => postJSON<IndustryRecommend>("/ai/recommend-industry", req);

/* ===== 가게 단위 마케팅 솔루션(Program 1단계) — POST /marketing/generate ===== */

/** 가게 프로필. 수집 채널(점주 제공·네이버 지역검색·카카오 로컬)에 무관한 정규화 입력 계약.
 *  백엔드 schemas/marketing.py::StoreProfile 와 1:1 대응한다. */
export interface StoreProfileInput {
  name: string; category: string; district_id?: string; address?: string;
  reviews?: string[]; image_urls?: string[]; menu?: string[]; keywords?: string[];
}

/** 카카오 로컬 키워드 검색 후보 1건 — 같은 상호가 전국에 있어 사람이 골라야 한다 */
export interface StorePlace {
  name: string; category: string;
  address: string | null; road_address: string | null; phone: string | null;
  lat: number | null; lng: number | null;
  place_url: string | null; distance_m: number | null;
}
export interface StorePlaceLookup {
  query: string; places: StorePlace[];
  /** "kakao-local" 정상 | "unavailable" 키 미설정·조회 실패 */
  source: string; note: string | null;
}
/** ⚠ 플레이스 방문자 리뷰가 아니라 **네이버 블로그 스니펫**이다(공식 API 없음) */
export interface StoreReviewLookup {
  query: string; reviews: string[];
  source: string; note: string | null;
}

/** 상호로 가게 후보 검색(카카오 로컬) — GET /marketing/places */
export const lookupStorePlaces = (query: string, districtId?: string) =>
  getJSON<StorePlaceLookup>(`/marketing/places?query=${encodeURIComponent(query)}`
    + (districtId ? `&district_id=${encodeURIComponent(districtId)}` : ""));

/** 가게 언급 블로그 스니펫(네이버 블로그) — GET /marketing/reviews.
 *  address 를 주면 그 동(洞)으로 질의를 좁혀 동명이지 오염을 줄인다. */
export const lookupStoreReviews = (name: string, address?: string | null) =>
  getJSON<StoreReviewLookup>(`/marketing/reviews?name=${encodeURIComponent(name)}`
    + (address ? `&address=${encodeURIComponent(address)}` : ""));

/** 제안 1건 — 채널·실행안·근거. 근거 없는 제안은 만들지 않는 것이 Program 의 원칙이다. */
export interface ChannelPlan {
  channel: string; kind: "online" | "offline"; content: string; rationale: string;
}

/** Humanistic Authority 후처리 검증 결과 1건 (백엔드 services/ha_guard.py).
 *
 *  `ha_check` 가 **LLM 의 자기신고**인 것과 달리 이건 서버가 입력과 대조해 낸 판정이다.
 *  - "violation": 거짓이 확정된 것(지어낸 금액·확정 트렌드 역행) → 생성물이 폐기됐다
 *  - "warning": 사전 매칭이라 오탐이 섞인다 → 응답은 살리고 밝히기만 한다 */
export interface HAFinding {
  severity: "violation" | "warning" | string;
  code: string; message: string; evidence: string | null;
}

/** 생성 결과. `source` 가 "rule-stub" 이면 LLM 을 못 탄 폴백이라 내용이 일반론이다 —
 *  화면에서 반드시 구분해 보여준다(실호출 결과처럼 읽히면 안 된다). */
export interface StoreMarketing {
  store_name: string; category: string; tone_keywords: string[];
  online: ChannelPlan[]; offline: ChannelPlan[]; ha_check: string;
  source: "llm" | "rule-stub" | string;
  /** 서버 후처리 검증 결과. rule-stub 인데 violation 이 있으면 **키가 없어서가 아니라
   *  생성물이 검증에 걸려 폐기된 것**이다 — 화면이 두 경우를 구분해야 한다. */
  ha_findings?: HAFinding[];
}

/** 가게 단위 마케팅 광고 솔루션 자동 생성(Program) — 상가 사진·정보·리뷰 기반 */
export const generateStoreMarketing = (profile: StoreProfileInput) =>
  postJSON<StoreMarketing>("/marketing/generate", profile);

/** 점주 제공 원문을 처리하는 상용 온보딩 동의 계약. 모든 true 값은 UI에서 사용자가
 *  각각 확인한 뒤에만 전송한다. 백엔드는 누락·false 를 422로 거절한다. */
export interface ProgramCommercialConsent {
  contract_version: "spaceos.program-onboarding/1";
  data_origin: "merchant-provided";
  processing_purpose: "program-marketing-generation";
  consent_to_process: true;
  rights_confirmed: true;
  allow_external_model_processing: true;
  raw_input_retention: "request-only";
}

export interface ProgramCommercialOnboardingResponse {
  onboarding_id: string;
  org_id: string;
  accepted_at: string;
  contract_version: "spaceos.program-onboarding/1";
  input_source: "merchant-provided";
  raw_input_persisted: false;
  marketing: StoreMarketing;
}

/** 조직 API 키를 쓰는 상용 Program 경로. 키는 호출 헤더에만 쓰고 브라우저 저장소에
 *  보관하지 않는다. 공개 데모 `/marketing/generate`와 계약을 섞지 않는다. */
export const generateCommercialStoreMarketing = (
  profile: StoreProfileInput,
  consent: ProgramCommercialConsent,
  apiKey: string,
) => postJSON<ProgramCommercialOnboardingResponse>(
  "/marketing/onboarding/generate",
  { profile, consent },
  { "X-API-Key": apiKey },
);
