# SpaceOS 디자인 시스템 (네이버 호환)

> 바이브 코딩으로 UX/UI를 만든다. 디자인도 코드처럼 토큰→컴포넌트 순서로 단일 출처를 둔다.
> 목표: "네이버 지도/네이버페이와 한 화면에 있어도 자연스러운" 한국형 앱 디자인.

## 1. 담당 폴더
```
design/                              디자인 원천 데이터(브랜드·에셋·참조·토큰 export)
design/tokens/tokens.json            토큰 export 본 (색·타이포·간격)
apps/frontend/src/design/tokens/     colors·typography·layout (TS 단일 출처)
apps/frontend/src/styles/tokens.css  CSS 변수(화면 전역 · 지도 오버레이) + Pretendard @font-face
apps/frontend/src/design/components/ Button·Card·BottomSheet·MapMarkerPin·VacancyLegend·NaverPayButton
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
- **토큰 동기화는 세 곳이다.** 한 곳을 고치면 나머지 두 곳을 같은 커밋에서 맞춘다.
  `design/tokens/tokens.json` ⇄ `apps/frontend/src/design/tokens/*.ts` ⇄ `apps/frontend/src/styles/tokens.css`
  - `tokens.json` — export 본(디자인 툴·문서가 읽는 원천)
  - `src/design/tokens/*.ts` — 코드가 값으로 읽는 TS 단일 출처
  - `src/styles/tokens.css` — 실제 화면에 먹는 CSS 변수. 컴포넌트는 이 `var(--…)` 를 쓴다
  - ⚠ Tailwind 는 쓰지 않는다. `tailwind.config.ts` 는 설치도 되지 않은 라이브러리의 죽은 설정이라
    2026-09-06 에 삭제했다(`@tailwind` 지시문 0개). 다시 끌어오지 말 것
- 컴포넌트 기록의 단일 출처는 `src/design/components/` 의 코드다.
  ⚠ Storybook 은 **설치된 적이 없다**(`.storybook/main.ts` 첫 줄이 `// TODO: 설치` 였고
  `build-storybook` 스크립트도 없었다) → 2026-09-06 삭제. 다시 쓰려면 설치가 먼저다.
  대비(AA)를 강제하던 a11y 애드온도 같이 사라졌으니, 색 조합 변경 시 직접 확인한다.
- 공유: 화면 캡처는 docs/ 또는 Notion/Drive.
- 코드는 GitHub PR. 디자인 토큰/컴포넌트 변경은 PR 설명에 Before/After 캡처 첨부.
