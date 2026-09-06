// 디자인 토큰 — 타이포그래피 (Pretendard 기준)
//
// ⚠ 단일 출처는 src/styles/tokens.css 의 --fs-* / --lh-* 변수다.
//    이 파일은 그 값을 TS 에서 읽으려고 두는 거울이고, design/tokens/tokens.json
//    도 같은 값을 들고 있다. 셋 중 하나만 고치지 말 것.
//
// 스케일은 본문 15px / 줄간격 1.5 를 기준점으로 잡은 비율 1.25 모듈러 스케일이다:
// 12 → 15 → 19 → 24 → 30. 하한 12px 아래로는 한글 받침이 뭉개져 쓰지 않는다.
// 웨이트는 400 · 600 · 700 셋을 자체 호스팅한다(public/fonts). 그 밖의 값은 브라우저
// 폰트매칭이 가까운 쪽으로 떨어뜨린다 — 500→400, 800·900→700.

export const typography = {
  fontFamily: "'Pretendard', -apple-system, 'Apple SD Gothic Neo', system-ui, sans-serif",
  weight: { regular: 400, semibold: 600, bold: 700 },

  /** 5단 타입스케일 — size(px) / lh(배수) / CSS 변수명 */
  scale: {
    /** 라벨 · 각주 · 범례 */
    caption: { size: 12, lh: 1.45, weight: 400, cssVar: "--fs-caption" },
    /** 본문 — 스케일의 기준점 */
    body: { size: 15, lh: 1.5, weight: 400, cssVar: "--fs-body" },
    /** 섹션 제목 h2 · h3 */
    heading: { size: 19, lh: 1.35, weight: 700, cssVar: "--fs-heading" },
    /** 페이지 제목 h1 */
    title: { size: 24, lh: 1.3, weight: 700, cssVar: "--fs-title" },
    /** 대형 KPI 수치 */
    display: { size: 30, lh: 1.2, weight: 700, cssVar: "--fs-display" },
  },
} as const;

export type TypeStep = keyof typeof typography.scale;

/** 스케일 한 단을 인라인 스타일로 펼친다 — <div style={typeStyle("caption")}> */
export function typeStyle(step: TypeStep) {
  const s = typography.scale[step];
  return { fontSize: s.size, lineHeight: s.lh, fontWeight: s.weight } as const;
}
