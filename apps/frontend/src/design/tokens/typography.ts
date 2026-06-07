// 디자인 토큰 — 타이포그래피 (Pretendard 기준)
export const typography = {
  fontFamily: "'Pretendard', -apple-system, 'Apple SD Gothic Neo', system-ui, sans-serif",
  // px / lineHeight
  scale: {
    display: { size: 32, lh: 1.25, weight: 700 },
    h1: { size: 24, lh: 1.3, weight: 700 },
    h2: { size: 20, lh: 1.35, weight: 700 },
    h3: { size: 17, lh: 1.4, weight: 600 },
    body: { size: 15, lh: 1.5, weight: 400 },
    bodyStrong: { size: 15, lh: 1.5, weight: 600 },
    caption: { size: 13, lh: 1.45, weight: 400 },
    micro: { size: 11, lh: 1.4, weight: 500 },
  },
} as const;
