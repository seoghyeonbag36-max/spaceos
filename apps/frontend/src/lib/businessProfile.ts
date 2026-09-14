/**
 * 「내 사업」 — 네 트랙이 공유하는 사업자 설정(화면설계서 3판 공통 프레임).
 *
 * ## 왜 (2026-09-13 주요 고객 재정의)
 *
 * 3판의 주요 고객은 업종이 정해진 창업자와, 지금 상권에서 업종을 바꾸거나 같은 업종으로
 * 상권을 옮기려는 사업자다. 이들은 상권이 아니라 **업종·지금 가게**에서 출발한다. 그래서
 * 상권 선택과 같은 급의 공유 값으로 둔다 — 한 번 정하면 트랙마다 다시 묻지 않는다.
 *
 * ## 저장
 *
 * 이 브라우저에만 남긴다(localStorage). 서버로 보내지 않는다 — 계정 화면이 서면 옮긴다.
 * 읽기·쓰기가 막히면(사생활 보호 창 등) 처음 방문으로 보고 화면은 그대로 돈다.
 */
import type { DistrictSummary, IndustryOption } from "@/lib/api";

export type BusinessGoal = "start" | "pivot" | "move";

export interface BusinessProfile {
  goal: BusinessGoal;
  /** `GET /ai/industries` 의 key. 바꾸기면 **지금** 업종, 창업·옮기기면 할 업종 */
  industryKey: string;
  /** 지금 가게 상권 — 바꾸기·옮기기만. 창업이면 null */
  homeDistrictId: string | null;
}

/** unset = 처음 방문(카드를 편다) · browsing = 「그냥 둘러보기」 · set = 설정됨 */
export type BusinessState =
  | { status: "unset" }
  | { status: "browsing" }
  | { status: "set"; profile: BusinessProfile };

export const STORAGE_KEY = "placeos.business.v1";

export const GOALS: { key: BusinessGoal; label: string; hint: string }[] = [
  { key: "start", label: "새로 창업", hint: "업종은 정했고, 어느 상권이 좋을지 찾는다" },
  { key: "pivot", label: "지금 상권에서 업종 바꾸기", hint: "가게 자리는 그대로, 무엇으로 바꿀지" },
  { key: "move", label: "같은 업종으로 상권 옮기기", hint: "하던 장사를 어느 상권에서 할지" },
];

const isGoal = (v: unknown): v is BusinessGoal => v === "start" || v === "pivot" || v === "move";

export function loadBusiness(): BusinessState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { status: "unset" };
    const v = JSON.parse(raw);
    if (v?.status === "browsing") return { status: "browsing" };
    const p = v?.profile;
    if (v?.status === "set" && p && isGoal(p.goal) && typeof p.industryKey === "string" && p.industryKey) {
      const home = typeof p.homeDistrictId === "string" && p.homeDistrictId ? p.homeDistrictId : null;
      // 바꾸기·옮기기인데 지금 상권이 없으면 깨진 값이다 — 처음 방문으로 되돌려 다시 묻는다.
      if (p.goal !== "start" && !home) return { status: "unset" };
      return { status: "set", profile: { goal: p.goal, industryKey: p.industryKey, homeDistrictId: p.goal === "start" ? null : home } };
    }
  } catch {
    // 읽기가 막히거나 JSON 이 깨졌다 — 처음 방문으로 본다.
  }
  return { status: "unset" };
}

export function saveBusiness(state: BusinessState): void {
  try {
    if (state.status === "unset") window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // 저장이 막혀도 이번 방문 동안은 메모리 값으로 돈다.
  }
}

export const findIndustry = (industries: IndustryOption[] | null | undefined, key: string | null | undefined) =>
  (key && industries?.find((i) => i.key === key)) || null;

/** 칩 문구 — 목적과 업종(·지금 상권)을 한 줄로. 업종 목록이 아직 없으면 key 를 그대로 쓰지 않고 「내 사업」. */
export function businessChipText(state: BusinessState, industries: IndustryOption[] | null | undefined,
  districts: DistrictSummary[] | null | undefined): string {
  if (state.status !== "set") return "내 사업 설정";
  const { goal, industryKey, homeDistrictId } = state.profile;
  const ind = findIndustry(industries, industryKey);
  if (!ind) return "내 사업";
  const home = districts?.find((d) => d.id === homeDistrictId)?.name ?? "지금 상권";
  if (goal === "start") return `${ind.label} 창업`;
  if (goal === "pivot") return `${home} · ${ind.label}에서 업종 바꾸기`;
  return `${ind.label} · ${home}에서 옮기기`;
}

/** 주제 조사(은/는) — 업종 이름이 문장 속에 들어가므로 받침으로 가른다("음식점은" · "카페는").
 *  마지막 한글 음절 기준이다. 한글이 없으면 "는". */
export function topic(word: string): string {
  const last = [...word].reverse().find((ch) => ch >= "가" && ch <= "힣");
  if (!last) return `${word}는`;
  return `${word}${(last.charCodeAt(0) - 0xac00) % 28 ? "은" : "는"}`;
}

/** 방향 조사(으로/로) — 받침이 없거나 ㄹ 받침이면 "로"("카페로" · "음식점으로" · "호텔로"). */
export function toward(word: string): string {
  const last = [...word].reverse().find((ch) => ch >= "가" && ch <= "힣");
  if (!last) return `${word}로`;
  const jong = (last.charCodeAt(0) - 0xac00) % 28;
  return `${word}${jong === 0 || jong === 8 ? "로" : "으로"}`;
}
