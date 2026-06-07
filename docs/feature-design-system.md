# SpaceOS 디자인 시스템 (네이버 호환)

> 바이브 코딩으로 UX/UI를 만든다. 디자인도 코드처럼 토큰→컴포넌트→Storybook 순서로 단일 출처를 둔다.
> 목표: "네이버 지도/네이버페이와 한 화면에 있어도 자연스러운" 한국형 앱 디자인.

## 1. 담당 폴더
```
design/                              디자인 원천 데이터(브랜드·에셋·참조·토큰 export)
apps/frontend/tailwind.config.ts     토큰 → Tailwind 매핑
apps/frontend/src/styles/tokens.css  CSS 변수(지도 오버레이용) + Pretendard @font-face
apps/frontend/src/design/tokens/     colors·typography·layout (TS 단일 출처)
apps/frontend/src/design/components/ Button·Card·BottomSheet·MapMarkerPin·VacancyLegend·NaverPayButton
apps/frontend/.storybook/            Storybook(문서화·a11y 대비검사·공유)
```

## 2. 네이버 연동 디자인 모델 (핵심 규칙)
1. **네이버 그린(#03C75A)은 네이버 연동 맥락에만** — 지도 길찾기, 네이버페이 영역 강조. 남발 금지.
2. **SpaceOS 고유 기능(AI 추천·공실 히트맵)은 brand teal(#0EA5B7)** — 그린과 보색으로 역할 분리.
3. **네이버페이 버튼은 공식 디자인 고정** — 색·모양·문구 변경 시 패널티. `NaverPayButton`은 공식 에셋 슬롯, 주변 여백/정렬만 우리 토큰으로 맞춘다.
4. **지도 위 UI는 한국형 패턴** — 바텀시트(BottomSheet)로 상권/상가 정보 노출, 커스텀 마커(MapMarkerPin)는 공실 위험도 색계열.
5. **한글 가독성 최우선** — Pretendard, 본문 15px/줄간격 1.5, 대비 WCAG AA.

## 3. 디자인 데이터 — 출처·저장 (상세는 design/README.md)
| 데이터 | 출처 | 저장 |
|--------|------|------|
| 네이버 브랜드/컬러 | NAVER Corp 브랜드 가이드 | design/brand/naver-brand.md |
| 네이버페이 공식 버튼 | 네이버페이 가맹점/개발자센터 | design/assets/naverpay/(원본) |
| 네이버 지도 스타일·마커 | NCP Maps 콘솔/문서 | design/assets/navermap/ |
| Pretendard 폰트 | npm pretendard | apps/frontend/public/fonts/ |
| 참조 UI 패턴 | 네이버지도·당근·배민 캡처 | design/references/ |

## 4. 산출물 저장·기록·공유
- 토큰 변경 → `src/design/tokens` + `tailwind.config.ts` 수정 → `design/tokens/tokens.json` 동기화.
- 컴포넌트는 `*.stories.tsx` 로 Storybook에 기록. `npm run build-storybook` → `storybook-static/`.
- 공유: Storybook 정적 빌드를 GitHub Pages/사내 링크 배포, 화면 캡처는 docs/ 또는 Notion/Drive.
- 코드는 GitHub PR. 디자인 토큰/컴포넌트 변경은 PR 설명에 Before/After 캡처 첨부.
