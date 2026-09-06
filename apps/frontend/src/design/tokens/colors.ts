// SpaceOS 디자인 토큰 — 색상 (단일 출처)
// 네이버 호환: green은 네이버 연동 맥락에만, brand(teal)는 SpaceOS 고유 기능.
export const colors = {
  naver: { green: "#03C75A", greenPressed: "#02B350", greenSoft: "#E6F8EE" },
  brand: { primary: "#0EA5B7", primaryPressed: "#0B8294", soft: "#E6F7F9" },
  // PPPP 네 트랙 색 (2026-09-06) — 레일·헤더·범례가 "지금 어느 트랙인지"를 색으로 말한다.
  // 색상각 242·272·302·332 도. 그 밖은 이미 임자가 있다 — 공실 축 3~160도, 네이버 147도,
  // brand teal 186도, UI 남색 #3A5A98 220도. 채도는 전부 S46% 로 teal(S86%)의 절반이라
  // 주색을 이기지 않고, 명도는 색맹·흑백 구분을 위해 일부러 어긋냈다.
  // base 넷 모두 bg(#F4F7FB)·surface(#FFFFFF)·자기 soft 위에서 AA 4.5:1 통과.
  // ⚠ 값은 styles/tokens.css · design/tokens/tokens.json 과 같아야 한다.
  track: {
    platform: { base: "#6460C4", pressed: "#4945B9", soft: "#F0F0FB" },
    page:     { base: "#753DA6", pressed: "#61338A", soft: "#F6F0FB" },
    posting:  { base: "#A23C9F", pressed: "#863284", soft: "#FBF0FB" },
    program:  { base: "#7E2F53", pressed: "#622541", soft: "#FBF0F5" },
  },
  ink: "#1C2533",
  muted: "#6B7280",
  line: "#E3E9F2",
  surface: "#FFFFFF",
  bg: "#F4F7FB",
  // 공실 히트맵 색계열 (저위험→고위험)
  vacancy: ["#22B07D", "#9CCB3B", "#EFA50F", "#F2682C", "#E03E36"],
  semantic: { success: "#22B07D", warning: "#EFA50F", danger: "#E03E36", info: "#0EA5B7" },
} as const;
export type Colors = typeof colors;
// PPPP 트랙 키 — CLAUDE.md 의 프레임워크 순서와 같다(Platform → Page → Posting → Program).
export type TrackKey = keyof typeof colors.track;
