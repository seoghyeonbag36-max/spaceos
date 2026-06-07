# SpaceOS 디자인 데이터 레이어 (Design Source of Truth)

UX/UI 디자인도 코드처럼 한 곳에서 관리한다. "네이버와 잘 어울리는" 디자인을 만들기 위한 원천 데이터를 모으고 정리하는 폴더.

```
design/
├── brand/            네이버·SpaceOS 브랜드 규칙 (컬러·로고 사용·금지사항)
├── assets/
│   ├── naverpay/     ⚠ 네이버페이 공식 버튼 에셋 (임의 변경 금지 — 원본 그대로 보관)
│   └── navermap/     네이버 지도 마커·지도 스타일(style JSON)·컨트롤 캡처
├── references/       잘 만든 한국형 앱 UI 패턴 캡처 (바텀시트·지도오버레이 등)
├── tokens/           디자인 토큰 export (tokens.json — 색·타이포·간격의 단일 출처)
└── README.md
```

## 디자인 관련 데이터 — 어디서 얻고, 어디에 저장하나
| 데이터 | 출처 | 저장 위치 | 형식 |
|--------|------|----------|------|
| 네이버 브랜드 컬러(#03C75A)·로고 규칙 | NAVER Corp 브랜드 가이드 | design/brand/naver-brand.md | md + 색상값 |
| 네이버페이 공식 결제 버튼 에셋 | 네이버페이 개발자센터/가맹점 | design/assets/naverpay/ | png·svg(원본) |
| 네이버 지도 스타일·마커 규격 | NCP Maps 콘솔/문서 | design/assets/navermap/ | style.json·png |
| 한글 폰트(Pretendard) | npm pretendard | apps/frontend public/fonts | woff2·ttf |
| 아이콘 | lucide / react-icons | 코드 import | svg |
| 경쟁/참조 UI 패턴 | 네이버지도·당근·배민 등 캡처 | design/references/ | png(주석 포함) |
| 접근성 대비 기준 | WCAG 2.1 AA | design/brand/a11y.md | md |

## ⚠ 네이버페이 버튼 핵심 규칙
네이버페이 결제 버튼은 **공식 디자인으로만** 사용한다. 색·모양·문구 임의 변경 시 패널티 대상이다.
→ 디자인 시스템에서 네이버페이 버튼은 "고정 슬롯"으로 취급하고, 주변 레이아웃만 우리 토큰으로 맞춘다.

## 저장·기록·공유 규칙
- 토큰의 단일 출처는 `apps/frontend/tailwind.config.ts` + `src/design/tokens/`. export 본은 `design/tokens/tokens.json`.
- 컴포넌트 산출물은 **Storybook**으로 기록 → `npm run build-storybook` → 정적 사이트(`storybook-static/`).
- 공유: Storybook 정적 빌드를 GitHub Pages/사내 링크로 배포, 캡처는 docs/ 또는 Notion/Drive.
- 원본 브랜드 에셋(naverpay 등)은 git 포함 가능하나 **수정본은 만들지 않는다**.
