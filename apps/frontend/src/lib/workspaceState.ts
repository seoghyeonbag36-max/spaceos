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
