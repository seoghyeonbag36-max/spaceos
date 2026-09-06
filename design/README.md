# SpaceOS 디자인 데이터 레이어 (Design Source of Truth)

UX/UI 디자인도 코드처럼 한 곳에서 관리한다. "네이버와 잘 어울리는" 디자인을 만들기 위한 원천 데이터를 모으고 정리하는 폴더.

```
design/
├── brand/            네이버·SpaceOS 브랜드 규칙 (컬러·로고 사용·금지사항)
├── assets/
│   ├── naverpay/     ⚠ 네이버페이 공식 버튼 에셋 (임의 변경 금지 — 원본 그대로 보관)
│   └── navermap/     네이버 지도 마커·지도 스타일(style JSON)·컨트롤 캡처
├── references/       잘 만든 한국형 앱 UI 패턴 캡처 (바텀시트·지도오버레이 등)
├── tokens/           디자인 토큰 export (tokens.json — 색·타이포·간격). 코드 쪽 두 곳과 동기화
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
- **토큰 동기화는 세 곳이다** — 한 곳을 고치면 나머지 두 곳을 같은 커밋에서 맞춘다.
  `design/tokens/tokens.json` ⇄ `apps/frontend/src/design/tokens/*.ts` ⇄ `apps/frontend/src/styles/tokens.css`
  (export 본 ⇄ 코드가 읽는 TS 단일 출처 ⇄ 화면에 먹는 CSS 변수).
  ⚠ Tailwind 는 쓰지 않는다 — `tailwind.config.ts` 는 설치되지 않은 라이브러리의 죽은 설정이라 2026-09-06 에 삭제했다.
- 컴포넌트 산출물의 단일 출처는 **코드 자체**다 — `apps/frontend/src/design/components/`.
  ⚠ Storybook 은 **설치된 적이 없다**. `.storybook/main.ts` 와 `Button.stories.tsx` 만
  남아 있었고 `build-storybook` 스크립트도 없어서, 문서가 안내하던 명령이 존재하지
  않았다 → 2026-09-06 삭제. 되살리려면 설치부터 하고 문서를 같이 고칠 것.
- 공유: 화면 캡처는 docs/ 또는 Notion/Drive. 대비(AA)는 자동 게이트가 없으므로
  토큰 색 조합을 바꿀 때 직접 확인한다(design/brand/a11y.md).
- 원본 브랜드 에셋(naverpay 등)은 git 포함 가능하나 **수정본은 만들지 않는다**.
