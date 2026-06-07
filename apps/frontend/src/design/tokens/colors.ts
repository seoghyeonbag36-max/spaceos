// SpaceOS 디자인 토큰 — 색상 (단일 출처)
// 네이버 호환: green은 네이버 연동 맥락에만, brand(teal)는 SpaceOS 고유 기능.
export const colors = {
  naver: { green: "#03C75A", greenPressed: "#02B350", greenSoft: "#E6F8EE" },
  brand: { primary: "#0EA5B7", primaryPressed: "#0B8294", soft: "#E6F7F9" },
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
