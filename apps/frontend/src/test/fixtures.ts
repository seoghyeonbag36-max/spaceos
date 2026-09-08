/**
 * 테스트 픽스처 — 백엔드 응답의 **최소 형태**.
 *
 * 전부 `@/lib/api` 의 실제 타입으로 못 박는다. 백엔드 스키마가 바뀌어 `api.ts` 의 타입이
 * 따라 바뀌면 여기서 먼저 컴파일이 깨진다(`npm run build` 의 `tsc -b` 가 src 를 본다) —
 * 그게 이 파일이 타입을 다는 이유다. 값을 대충 넣되 **타입은 대충 넣지 않는다**.
 *
 * ⚠ 값의 성격을 흉내낼 것: 감성은 66거점 전부 `null`(미측정)이고, 그 자리에 0 을 넣으면
 *   "쟀더니 0" 을 테스트가 정상으로 굳혀 버린다(AGENTS.md §0).
 */
import type {
  DistrictSummary, GeoJSONFC, HeatCell, Posting, RentHeatmap,
  SimulateResult, TierScenario, VacancyHeatmap,
} from "@/lib/api";

export function district(id: string, over: Partial<DistrictSummary> = {}): DistrictSummary {
  return {
    id, name: id, gu: "강남구", type: "패션", city: "seoul", city_name: "서울",
    center: [37.5205, 127.023], note: "", rec_top: "카페",
    sentiment: null, reviews: null, risk_zones: null,   // 미측정 — 0 이 아니다
    vacancy_rate: 12.3, vacancy_withheld: false, inventory_coverage_pct: 61.2,
    vacant_units: 42, cell_count: 4, store_count: 310,
    tier_mix: { premium: 1, value: 1, factory: 1 },
    vacancy_source: "gold",
    building_count: 120, precision_pct: 88.5,
    anchor_pct: 9.9, anchor_gap_pp: 2.4,
    predicted_rate: null, predicted_delta: null, predicted_direction: null,
    ...over,
  };
}

/** 100m 격자 셀 — `lat/lng` 는 남서 모서리, `c_*` 는 중심(hubBoundary 가 이 규약을 읽는다). */
export function cell(i: number, j: number, over: Partial<HeatCell> = {}): HeatCell {
  const dlat = 0.0009, dlng = 0.00113;
  const lat = 37.52 + j * dlat, lng = 127.02 + i * dlng;
  return {
    i, j, lat, lng, c_lat: lat + dlat / 2, c_lng: lng + dlng / 2,
    v: 10, stores: 20, vac_n: 2, dlat, dlng, capacity: 30, buildings: 5, ...over,
  };
}

/** `cells` 를 안 주면 2×2 한 덩어리 — 경계가 **1조각**으로 떨어진다. */
export function vacancyHeatmap(id: string, cells?: HeatCell[]): VacancyHeatmap {
  const cs = cells ?? [cell(0, 0), cell(1, 0), cell(0, 1), cell(1, 1)];
  return {
    district_id: id, resolution_m: 100, cells: cs,
    sum_stores: 80, sum_vac: 8, avg_vacancy: 12.3, vacancy_withheld: false,
    inventory_coverage_pct: 61.2, vacancy_source: "gold",
    capacity: 120, buildings: 40, buildings_total: 45, precision_pct: 88.5,
    excluded_mall: 1, anchor_pct: 9.9, anchor_gap_pp: 2.4,
    predicted_rate: null, predicted_delta: null, predicted_direction: null,
  };
}

export function rentHeatmap(id: string): RentHeatmap {
  return {
    district: id, rent_source: "rone", unit: "만원/평",
    cells: [{
      i: 0, j: 0, lat: 37.52, lng: 127.02, c_lat: 37.5204, c_lng: 127.0206,
      dlat: 0.0009, dlng: 0.00113, v: 18, rent_per_pyeong: 18,
    }],
  };
}

/** 건물 공실 GeoJSON — 건물 하나가 폴리곤 하나다. 오버레이 개수를 여기서 정한다. */
export function buildings(
  rows: Array<{ id: string; name: string; status: "full" | "partial" | "high" | "empty" }>,
): GeoJSONFC {
  return {
    type: "FeatureCollection",
    features: rows.map((r, n) => {
      const lat = 37.52 + n * 0.0002, lng = 127.02 + n * 0.0002;
      const d = 0.0001;
      return {
        type: "Feature" as const,
        geometry: {
          type: "Polygon" as const,
          coordinates: [[
            [lng - d, lat - d], [lng + d, lat - d],
            [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d],
          ]],
        },
        properties: {
          id: r.id, name: r.name, status: r.status,
          capacity: 10, active: r.status === "empty" ? 0 : 6,
          industry: "카페", vacancy_rate: r.status === "empty" ? 100 : 40, floors: 5,
        },
      };
    }),
  };
}

function tier(key: string, over: Partial<TierScenario> = {}): TierScenario {
  return {
    tier: key, name: key, sub: "", invest_mn: 8000, month_cost: 1200,
    month_rev: 1800, month_net: 600, roi_months: 14, recommended: key === "value",
    viable: true, basis: "kosis-opex+measured-revenue", ...over,
  };
}

export function postings(id: string, n = 2): Posting[] {
  return Array.from({ length: n }, (_, k) => ({
    id: `${id}-u${k + 1}`, n: `${id} ${k + 1}번 자리`, grp: "A",
    lat: 37.52 + k * 0.0003, lng: 127.02 + k * 0.0003,
    area: 20 + k, rent: 450, prem: 0, floor: "1F", was: "카페", foot: "상",
    rec: null, persona: null, note: null,
    inputs_source: { area: "bldg", rent: "rone", prem: "absent", foot: "flpop+jipgyegu", floor: "flr_ouln" },
    scenarios: { premium: tier("premium"), value: tier("value"), factory: tier("factory") },
  }));
}

export function simulateResult(districtId: string, unitId: string): SimulateResult {
  return {
    district_id: districtId, unit_id: unitId, industry_type: "카페",
    scenarios: { premium: tier("premium"), value: tier("value"), factory: tier("factory") },
    source: "fallback-3tier", source_note: null,
    inputs_source: { area: "bldg", rent: "rone", prem: "absent", foot: "flpop+jipgyegu", floor: "flr_ouln" },
    inputs_quarter: "2026Q2", unviable_note: null,
  };
}
