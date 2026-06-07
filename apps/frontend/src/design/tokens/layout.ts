// 디자인 토큰 — 간격·반경·그림자 (4px 베이스)
export const space = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48 } as const;
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const; // 한국형 앱 = 둥근 모서리
export const shadow = {
  card: "0 1px 3px rgba(11,27,51,.08), 0 4px 12px rgba(11,27,51,.06)",
  sheet: "0 -4px 24px rgba(11,27,51,.12)", // 바텀시트 상단 그림자
  marker: "0 2px 6px rgba(0,0,0,.25)",
} as const;
