/** Page의 탐색 조건과 후보는 앱 메모리에서만 유지한다. 서버 자료를 별도로 저장하지 않는다. */
export type VacancyFilter = "all" | "full" | "partial" | "high" | "empty";

export interface PageWorkspace {
  districtId: string;
  query: string;
  status: VacancyFilter;
  selectedId: string | null;
  savedIds: Record<string, string[]>;
  notes: Record<string, string>;
}

export const createPageWorkspace = (): PageWorkspace => ({
  districtId: "garosugil", query: "", status: "all", selectedId: null,
  savedIds: {}, notes: {},
});

/** 건물 식별자만 인계한다. 층 표본·클라이언트 수치를 시뮬레이션 입력으로 바꾸지 않는다. */
export interface BuildingSelection {
  districtId: string;
  buildingId: string;
  buildingName: string;
}

/**
 * Posting → Program 인계(화면설계서 2판 인계 표).
 *
 * Program 은 이 값으로 **보이는 입력칸**(거점·카테고리·주소)만 채우고 「입점 예정 자리」 안내·지도
 * 핀을 띄운다. 가게명·리뷰는 입점할 기업이 넣는다 — 여기 없는 값을 지어 채우지 않는다.
 * 금액·전략명은 안내 문구에만 쓰고 생성 요청에는 싣지 않는다(StoreProfile 에 그 필드가 없다).
 */
export interface ProgramHandoff {
  districtId: string;
  unitId: string;
  unitName: string;
  lat: number;
  lng: number;
  /** 평 */
  area: number;
  floor: string;
  /** 만원/월 — Posting 자리의 R-ONE 추정 임대료 */
  rent: number;
  /** 계산에 쓴 업종, 없으면 직전 업종. 둘 다 없으면 null(카테고리를 비운다) */
  industry: string | null;
  /** 회수되는 전략 중 추천(없으면 가장 빠른 것)의 이름. 계산 전·전부 회수 불가면 null */
  strategy: string | null;
}
