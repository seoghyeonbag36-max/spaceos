# PlaceOS 프론트엔드 코드 해설

분석 기준: 2026-09-11, 현재 작업 브랜치 `fix/benchmark-ux-flow-20260909`의 로컬 코드.

이 문서는 프론트엔드의 구조, 구현 이유, HTML 태그·React 문법·실행 명령어를 설명한다. 반복되는 문법은 한 번 설명하고, 파일별 역할과 연결한다. 모든 소스 행을 주석으로 다시 옮긴 문서는 아니다. 작성 이유는 코드 주석에 명시된 이유와 실제 동작으로 확인한 역할을 우선했으며, 최초 기술 선정 동기는 코드만으로 확정하지 않는다.

앱 소스는 수정하지 않았다. 검사 결과는 `npm run build` 통과, `npm run lint` 오류 0개·경고 50개, `npm run test` 7개 파일·59개 테스트 통과다. 테스트의 API·지도 SDK는 모의 구현이므로 실제 서버·지도·LLM의 정상 작동까지 증명하지 않는다.

## 1. 어떤 구조로 이루어져 있는가?

### 1.1 네 가지 언어·기술의 역할

PlaceOS는 HTML 문서를 진입점으로 삼고, React가 TypeScript/TSX로 작성한 화면을 브라우저에 표시하는 웹 앱이다. Vite는 개발 중 코드를 제공하고 배포할 파일을 만든다.

| 용어 | 쉬운 뜻 | PlaceOS에서 맡은 일 |
|---|---|---|
| 프론트엔드 | 사용자가 보는 화면과 조작 처리 | 지도, 목록, 입력란, 비교표, 생성 결과 표시 |
| HTML | 화면 요소의 구조 | 제목, 버튼, 폼, 표, 지도 컨테이너 |
| CSS | 요소를 배치하고 꾸미는 규칙 | 전체화면 지도, 패널, 색, 글자, 모바일 배치 |
| JavaScript | 브라우저에서 동작하는 프로그램 | 클릭 처리, 서버 요청, 지도 SDK 제어 |
| TypeScript | JavaScript에 자료형 검사를 더한 언어 | 건물·거점·생성 결과의 필드와 허용값 검사 |
| JSX | JavaScript 안에 화면 구조를 적는 문법 | `<button>{label}</button>` 같은 표현 |
| TSX | TypeScript에서 JSX를 사용하는 파일 형식 | `App.tsx`, 각 화면·컴포넌트 |
| React | 상태에 맞춰 UI를 구성하는 라이브러리 | 거점이나 입력이 바뀌면 관련 화면 갱신 |
| React DOM | React와 브라우저 DOM을 연결하는 라이브러리 | `createRoot(...).render(...)` 실행 |
| DOM | 브라우저가 문서를 메모리에 표현한 요소 트리 | 버튼 찾기, 지도 영역에 SDK 화면 붙이기 |
| Vite | 개발 서버와 빌드 도구 | 개발 서버, React 변환, API 프록시, 배포 번들 |
| SPA | 한 문서 안에서 화면을 바꾸는 앱 방식 | `App`의 `view` 상태로 여섯 화면 전환 |
| 컴포넌트 | 이름을 붙여 재사용하는 화면 부품 | `DistrictPicker`, `Button`, `BuildingViewer` |
| API | 프로그램 사이의 요청·응답 창구 | 백엔드에 공실·추천·계산·생성 요청 |
| SDK | 외부 기능을 호출하는 개발 도구 묶음 | 네이버 지도·마커·거리뷰 |
| JSON | 이름과 값으로 구성한 데이터 교환 형식 | 백엔드 응답과 생성 요청 본문 |
| GeoJSON | 지리 도형을 표현하는 JSON 형식 | 건물 외곽선과 공실 속성을 함께 전달 |
| 모듈 | 다른 파일과 가져오기·내보내기로 연결하는 코드 단위 | `import`와 `export` 사용 |
| 번들 | 배포용으로 묶고 변환한 코드 파일 | `dist/assets/*.js`, `*.css` |
| 런타임 | 프로그램이 실제로 실행되는 시점·환경 | 브라우저에서 지도 생성·API 호출 |
| 의존성 | 앱이 가져다 쓰는 외부 패키지 | React, `@visx/shape` 등 |

`package.json`에는 React `^18.3.1`, TypeScript `^5.6.2`, Vite `^5.4.8`, `@visx/shape` `4.0.0` 등이 선언돼 있다. 선언 버전 범위와 설치 버전은 다를 수 있다. 이번 빌드에서 실행된 Vite는 `5.4.21`이었다.

### 1.2 브라우저가 화면을 여는 순서

```text
index.html
  └─ <div id="root">: 앱을 붙일 자리
      └─ src/main.tsx: React 시작 + 전역 CSS
          └─ App.tsx: 내비게이션·화면 선택·공유 상태
              ├─ SeoulDashboard: 서울 진입 로드맵
              ├─ PlatformConsole: 상권 정체성과 업종 추천
              ├─ PostingConsole: 비용·회수기간 비교
              ├─ ProgramStudio: 홍보 초안 생성·편집
              └─ MapHost: 거점/Page가 공유하는 지도
                  ├─ HubExplorer: 거점 선택·실측 범위
                  └─ MapShell: 건물·레이어·후보 탐색
                      ├─ CandidateCompare: 후보 비교
                      └─ BuildingViewer: 층 스택·거리뷰

별도 진입
  #board → PageDashboard: 기존 보드와 거점 심층 화면
  #admin → AdminCoverage: 관리자 커버리지 조회
```

`App.tsx`는 현재 `react-router`를 사용하지 않는다. `useState<View>("seoul")`로 시작하고 버튼을 누르면 `setView(...)`로 화면을 고른다. 따라서 `/platform`, `/posting` 같은 독립 주소 체계가 이미 구현됐다고 해석하면 안 된다. 코드에는 라우터 도입 TODO가 남아 있다.

`HubExplorer`는 `#hub=거점ID`를 선택값으로 읽고 쓴다. 다만 `App`은 이 해시를 보고 거점 탭을 자동으로 열지는 않는다. 해시 선택 복원과 앱 전체 화면 라우팅은 서로 다른 기능이다.

### 1.3 PPPP와 화면 이름

| 전통 4P | PlaceOS 기능 | 화면이 답하는 질문 | 주 화면 |
|---|---|---|---|
| Place | Platform | 이 상권은 어떤 성격을 가졌는가? | `PlatformConsole.tsx` |
| Product | Page | 이 상권의 어떤 자리를 검토할까? | `MapShell.tsx` |
| Price | Posting | 어떤 가격대·비용 전략으로 들어갈까? | `PostingConsole.tsx` |
| Promotion | Program | 어떤 홍보 콘텐츠를 만들까? | `ProgramStudio.tsx` |

여기서 Page는 서비스 이름이다. `src/pages/`의 page는 화면 파일이라는 개발 용어다. `PageDashboard.tsx`라는 이름도 현재 Page 탭의 진입 컴포넌트를 뜻하지 않는다. 실제 Page 탭은 `MapShell`이다.

### 1.4 폴더별 역할

| 위치 | 역할 |
|---|---|
| `src/pages/` | 각 화면의 입력·로딩·데이터·결과를 구성 |
| `src/components/` | 여러 화면에서 쓰는 지도·선택기·비교표·요약 부품 |
| `src/lib/` | API 요청, 네이버 SDK 연결, 경계 계산, 작업 상태의 타입 |
| `src/lib/seoul/` | 서울 로드맵용 자동 생성 정적 데이터 |
| `src/design/components/` | 버튼·카드·지도 마커 등 디자인 부품 |
| `src/design/tokens/` | TypeScript에서 사용하는 색·간격·글자 규격 |
| `src/styles/tokens.css` | 브라우저에 적용되는 전역 CSS 변수·폰트·기본 스타일 |
| `src/test/` | 테스트용 API·지도 대역, 데이터, 공통 설정 |
| `public/` | 경로 그대로 제공되는 폰트·아이콘·진단 HTML·고지문 |
| `harness/` | 앱의 복잡한 진입 절차를 거치지 않고 부품을 확인하는 개발 화면 |
| `scripts/` | JSX 텍스트 노드 수를 세는 개발 보조 스크립트 |
| `dist/` | 빌드가 생성한 배포 파일. 원본 편집 대상이 아님 |
| `node_modules/` | npm으로 설치한 라이브러리. 앱 자체 소스가 아님 |

## 2. HTML 코드를 하나씩 읽기

### 2.1 실제 앱 진입 HTML

원본: [index.html](index.html). 아래는 주석만 생략한 실제 구조다.

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <title>PlaceOS — 상권 디지털 트윈</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

| 코드 | 의미와 역할 | 사용 이유 |
|---|---|---|
| `<!doctype html>` | HTML 문서 형식 선언 | 브라우저가 표준 모드로 해석하도록 함 |
| `<html lang="ko">` | 문서 전체와 주 언어 지정 | 한국어 문서임을 브라우저·보조기기에 전달 |
| `<head>` | 문서 설정 영역 시작 | 문자 인코딩·제목·아이콘 등을 묶음 |
| `<meta charset="UTF-8" />` | 문자 인코딩 지정 | 한글·영문·기호를 올바르게 해석 |
| `name="viewport"` | 화면 크기 관련 설정 | 모바일에서도 기기 폭을 기준으로 표시 |
| `width=device-width` | 표시 폭을 기기 화면 폭에 맞춤 | 데스크톱 폭을 축소한 화면처럼 보이지 않게 함 |
| `initial-scale=1.0` | 초기 확대 비율 1배 | 기본 배율 지정 |
| `<link rel="icon" ...>` | 탭 아이콘 연결 | 원본 주석상 `/favicon.ico` 자동 조회 404를 없애기 위해 추가 |
| `type="image/svg+xml"` | 아이콘이 SVG 형식임을 명시 | 파일 형식 전달 |
| `href="/favicon.svg"` | 사이트 루트 기준 파일 경로 | `public/favicon.svg`를 가리킴 |
| `<title>...</title>` | 브라우저 탭·문서 제목 | 어떤 서비스인지 표시 |
| `</head>` | 설정 영역 종료 | 이후 본문과 구분 |
| `<body>` | 화면에 표시할 문서 본문 | 앱의 실제 요소가 들어감 |
| `<div id="root"></div>` | React 앱을 붙일 빈 컨테이너 | 화면 전체를 이 요소 아래 구성 |
| `<script type="module" ...>` | JavaScript 모듈 진입점 연결 | `import`·`export`로 나뉜 코드를 시작 |
| `src="/src/main.tsx"` | 개발 원본 진입 파일 | Vite가 TSX를 브라우저가 실행할 JavaScript로 변환 |
| `</body>`, `</html>` | 본문·문서 종료 | 열린 요소를 닫음 |

브라우저가 TypeScript/TSX를 직접 이해하는 것은 아니다. 개발 중에는 Vite가 변환해 제공하고, 빌드 후에는 `dist/index.html`이 변환된 JavaScript·CSS 파일을 가리킨다.

HTML의 `<meta>`, `<link>`, `<input>`, `<img>`, `<br>`는 자식을 갖지 않는 요소다. React JSX에서는 `<input />`처럼 닫힌 모양으로 적는다. `<!-- ... -->`는 HTML 주석, `{/* ... */}`는 JSX 안의 주석이다.

### 2.2 나머지 HTML 두 파일

| 파일 | 내용과 목적 | 앱 진입 HTML과 다른 점 |
|---|---|---|
| [harness/building-viewer.html](harness/building-viewer.html) | 건물 층 스택과 범례의 개발 검증 진입점 | 제목이 하네스이며 스크립트는 `./building-viewer.tsx` |
| [public/maptest.html](public/maptest.html) | 네이버 지도 스크립트·인증·타일 로딩 진단 | React 없이 HTML과 일반 JavaScript만으로 지도 생성 |

하네스 HTML의 `doctype`, `lang`, `meta`, `link`, `head`, `body`, `root`, 모듈 스크립트는 위와 같은 의미다. 하네스 TSX는 실제 건물 API 응답에서 층 근거가 있는 건물과 없는 건물을 골라 `BuildingViewer`에 전달한다. 샘플 수치를 새로 만드는 하네스가 아니다. 현재 기본 Vite 빌드의 진입점에는 포함되지 않는다.

`maptest.html`의 내부 JavaScript는 다음 순서로 작동한다.

| 코드·표현 | 의미 |
|---|---|
| `<div id="log">` | 진행 메시지를 화면에 출력할 자리 |
| `white-space: pre-line` | 로그 문자열의 줄바꿈을 화면에도 반영 |
| `<div id="map">` | 800×500px 지도 표시 영역 |
| `const log = (m) => ...` | 메시지 `m`을 화면과 개발자 콘솔에 기록하는 함수 |
| `textContent += m + '\n'` | 기존 텍스트 뒤에 메시지와 줄바꿈 추가 |
| `console.log(...)` | 브라우저 개발자 도구에 진단 로그 출력 |
| `window.navermap_authFailure = ...` | 지도 인증 실패 때 실행할 콜백 등록 |
| `document.createElement('script')` | 코드로 스크립트 요소 생성 |
| `s.src = ...` | 네이버 SDK를 받을 주소 지정 |
| `s.onload = ...` | 스크립트 로드 완료 후 실행할 함수 지정 |
| `typeof window.naver` | 네이버 전역 객체가 어떤 자료형인지 확인 |
| `new naver.maps.Map(...)` | 지도 인스턴스 생성 |
| `new naver.maps.LatLng(...)` | 위도·경도 좌표 객체 생성 |
| `setTimeout(..., 3000)` | 3초 뒤 후속 진단 실행 |
| `document.querySelectorAll('#map img').length` | 지도 안 이미지 요소 개수 확인. 전체 기능 정상의 증명은 아님 |
| `try / catch` | 지도 생성 중 예외를 잡아 로그로 표시 |
| `s.onerror = ...` | 스크립트 네트워크 로드 실패 처리 |
| `document.head.appendChild(s)` | 생성한 스크립트를 실제 문서에 붙여 로딩 시작 |

`public/maptest.html`은 `public/`에 있어 기본 빌드 시 정적 파일로 복사된다. 개발 하네스 HTML과 배포 포함 방식이 다르다. 진단 파일의 SDK 주소에는 클라이언트 ID가 직접 적혀 있고, 앱의 `naverMap.ts`는 환경변수를 읽는다.

### 2.3 화면 TSX에 나오는 HTML·SVG 태그

다음은 현재 `src/`의 JSX를 구문 분석해 확인한 태그들이다. 이름이 비슷해도 HTML 태그와 React 컴포넌트는 구분해야 한다. `<button>`은 HTML 요소이고, `<Button>`은 프로젝트가 정의한 함수형 컴포넌트다.

| 태그 | 의미 | 실제 사용 맥락 |
|---|---|---|
| `div` | 일반 블록 컨테이너 | 앱·지도·패널·카드 영역 |
| `span` | 문장 안 작은 묶음 | 수치·배지·라벨 |
| `nav` | 내비게이션 | 왼쪽 화면 전환 레일 |
| `main` | 주요 본문 | 서울·Platform·Posting·Program 화면 |
| `header` | 머리말 | 결론·근거 블록, 비교창 제목 |
| `section` | 주제별 구역 | 예측, 추천, 비교, 초안 편집 영역 |
| `h1`, `h2`, `h3`, `h4` | 제목의 계층 | 화면·섹션·카드·차트 제목 |
| `p` | 문단 | 안내, 출처, 빈 결과 설명 |
| `strong` | 중요한 내용 강조 | 오류·한계·핵심 안내 |
| `b` | 주의를 끌기 위한 강조 | 핵심 수치·라벨 |
| `em` | 강조 의미 | 보조 설명·상태. 실제 시각 스타일은 CSS에 따름 |
| `i` | 별도 어조의 텍스트 요소 | 이 코드에서는 색점·막대·표식에도 사용 |
| `small` | 부가 설명 | 단위·각주·보조 문구 |
| `br` | 줄바꿈 | 출처와 설명 줄 구분 |
| `code` | 코드·식별자 표현 | 출처 코드, 토큰명, 오류 내용 |
| `a` | 링크 | 행사 공식 안내 연결 |
| `button` | 실행 버튼 | 탭 전환·검색·계산·복사 |
| `form` | 제출 가능한 입력 묶음 | Posting 시뮬레이션·Program 생성 |
| `label` | 입력 컨트롤 설명 | 상권·권리금·리뷰 입력 이름 |
| `input` | 한 줄 입력·체크박스·슬라이더 등 | 검색, 권리금, 동의, 시간대 |
| `textarea` | 여러 줄 텍스트 입력 | 리뷰·메뉴·메모·초안 본문 |
| `select` | 드롭다운 | 상권·자리·전략 선택 |
| `option` | 드롭다운 선택 항목 | 거점 하나, 전략 하나 |
| `optgroup` | 선택 항목 그룹 | 도시별 거점 묶음 |
| `datalist` | 자유 입력의 자동완성 힌트 | Program 카테고리 후보 |
| `fieldset`, `legend` | 관련 입력 묶음과 이름 | Platform 비교 후보 선택 |
| `ul`, `ol`, `li` | 순서 없는/있는 목록과 항목 | 추천 목록·근거 목록·경고 목록 |
| `dl`, `dt`, `dd` | 항목명과 값의 목록 | 거점 요약의 지표와 수치 |
| `table` | 표 | 건물·자리·관리자 데이터 비교 |
| `caption` | 표 전체 설명 | 비교표가 무엇을 비교하는지 전달 |
| `thead`, `tbody` | 표의 머리와 본문 | 열 이름과 실제 데이터 분리 |
| `tr`, `th`, `td` | 행·제목 셀·값 셀 | 비교 항목과 각 후보의 값 |
| `details`, `summary` | 펼치고 접는 상세와 요약줄 | `Fold`, 근거·입력 규칙·모델 설명 |
| `dialog` | 대화상자 | Page 후보 비교창. `showModal()`로 열음 |
| `img` | 이미지 | Program 사진 미리보기 |
| `svg` | 벡터 그림 영역 | 레일 아이콘·추세선·비교 차트 |
| `rect` | SVG 사각형 | 격자 아이콘 등 |
| `circle` | SVG 원 | 노드·핀 아이콘 |
| `line` | SVG 직선 | 비교 차트의 0 기준선 |
| `polyline` | 여러 점을 연결한 선 | 검색 추세 미니 차트 |
| `path` | 좌표 명령으로 만든 도형 | 핀·열쇠·메가폰 등의 아이콘 |

## 3. React 코드를 읽는 방법

### 3.1 앱을 실제로 붙이는 명령

원본: [src/main.tsx](src/main.tsx).

```tsx
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

1. `document.getElementById("root")`: HTML에서 `id="root"` 요소를 찾는다.
2. 뒤의 `!`: TypeScript에 이 값이 `null`이 아니라고 단언한다. 런타임에 요소를 만들어주는 기능은 아니다.
3. `ReactDOM.createRoot(...)`: 해당 요소에 React 루트를 만든다.
4. `.render(...)`: React 화면을 루트에 렌더링한다.
5. `<App />`: `App` 컴포넌트를 사용한다.
6. `<React.StrictMode>`: 개발 중 문제를 발견하도록 추가 검사를 한다. Effect의 설정·정리 과정이 추가로 실행될 수 있어 지도와 거리뷰의 중복 생성 방지가 필요하다.

`import "@/styles/tokens.css"`는 전역 스타일을 불러온다. 원본 주석에는 이 스타일이 특정 화면에서만 로딩돼 `body` 기본 여백과 이중 스크롤 문제가 생겼고, 진입점으로 올렸다고 기록돼 있다.

### 3.2 상태와 화면 전환

원본: [src/App.tsx](src/App.tsx).

```tsx
const [view, setView] = useState<View>("seoul");
```

| 부분 | 뜻 |
|---|---|
| `const` | 변수 이름을 다른 값으로 재할당하지 않도록 선언 |
| `[view, setView]` | 반환된 배열에서 두 값을 꺼내 이름을 붙임: 구조 분해 |
| `view` | 현재 선택된 화면 상태 |
| `setView` | 상태 변경을 요청하는 함수 |
| `useState` | React에서 컴포넌트 상태를 기억하는 훅 |
| `<View>` | 저장할 수 있는 상태의 TypeScript 타입 |
| `"seoul"` | 처음 화면의 값 |

`setView("posting")`은 다음 렌더에서 Posting 화면을 선택하도록 한다. `setView`를 부른 직후 현재 실행 중인 함수의 `view` 변수가 즉시 바뀌는 것은 아니다.

```tsx
{view === "posting" && <PostingConsole selection={postingSelection} />}
```

`{...}` 안에서는 JavaScript 표현식을 쓴다. `===`는 값과 자료형을 엄격히 비교한다. `&&`는 왼쪽이 참일 때 오른쪽을 평가하므로 이 조건에서는 Posting 화면만 표시한다. `selection`은 부모가 자식에 전달하는 props다.

### 3.3 버튼 한 개를 읽기

`App.tsx`의 내비게이션 버튼에서 아이콘 부분만 생략한 예다.

```tsx
<button
  key={n.key}
  className={"rail-btn" + (view === n.key ? " active" : "")}
  data-track={n.track}
  aria-current={view === n.key ? "page" : undefined}
  onClick={() => setView(n.key)}
>
  <span>{n.label}</span>
</button>
```

| 표현 | 의미와 사용 이유 |
|---|---|
| `key={n.key}` | 목록 항목의 React 식별자. 재정렬·갱신 시 같은 항목을 구분 |
| `className` | JSX에서 CSS 클래스 지정. HTML 문자열에서는 `class` |
| `조건 ? A : B` | 참이면 A, 거짓이면 B를 선택하는 삼항 연산자 |
| `" active"` | 현재 선택됐을 때 추가하는 클래스. CSS가 활성색을 적용 |
| `data-track` | HTML 사용자 정의 속성. CSS가 PPPP별 색상을 고르는 데 사용 |
| `aria-current` | 보조기기에 현재 화면 항목임을 전달 |
| `undefined` | 여기서는 속성을 지정하지 않는 효과 |
| `onClick` | 클릭했을 때 실행할 함수를 등록 |
| `() => setView(n.key)` | 클릭될 때 실행하는 화살표 함수 |
| `{n.label}` | 객체에서 읽은 버튼 이름을 표시 |

`onClick={setView(n.key)}`라고 쓰면 클릭 전에 렌더 과정에서 함수를 실행하므로 위 코드와 다르다. `key`는 React의 특별한 속성이며 일반 HTML 속성이나 자식의 일반 props로 전달되지 않는다.

### 3.4 입력 → 상태 → 요청 → 결과

원본: [src/pages/PostingConsole.tsx](src/pages/PostingConsole.tsx).

```tsx
<input
  value={industry}
  onChange={(e) => setIndustry(e.target.value)}
  placeholder="예: 카페 (비우면 자리 기본값)"
/>
```

`value`가 입력창에 표시할 현재 값이고, `onChange`는 사용자가 입력을 바꿀 때 실행된다. `e`는 이벤트, `e.target.value`는 입력한 문자열이다. 상태가 입력창의 값을 관리하는 방식을 제어 컴포넌트라고 부른다.

`placeholder`는 빈 입력칸의 안내이지 실제 입력 데이터가 아니다. 체크박스는 `value` 대신 주로 `checked`와 `e.target.checked`로 선택 여부를 연결한다.

`<form onSubmit={...}>`에서는 `e.preventDefault()`로 브라우저의 기본 폼 제출·페이지 이동을 막고 API를 호출한다. `type="button"`은 폼 안에서 제출 없이 다른 동작을 하는 버튼이고, `type="submit"`은 폼 제출 버튼이다. `disabled={busy || !unitId}`는 계산 중이거나 선택 유닛이 없으면 실행을 막는다.

### 3.5 훅과 비동기 처리

| 용어·코드 | 역할 | 사용 사례 |
|---|---|---|
| props | 부모가 자식에게 전달하는 입력 | `BuildingViewer`의 `b`, 선택기의 `districts` |
| state | 컴포넌트가 기억하는 값 | 선택 거점·검색어·결과·로딩 상태 |
| 훅(Hook) | React의 상태·수명주기 등을 사용하는 함수 | `useState`, `useEffect` |
| `useEffect` | 렌더 후 외부 시스템과 동기화 | API 조회·지도 생성·이벤트 등록 |
| 의존성 배열 | Effect를 다시 실행할 기준 | `[districtId, hour, layer]` |
| cleanup | Effect가 교체되거나 컴포넌트가 사라질 때 정리 | 지도 오버레이·리스너 제거 |
| `useRef` | 렌더 사이에 유지하지만 변경만으로 재렌더하지 않는 저장소 | 지도 객체·요청 번호·타이머 |
| `useMemo` | 의존값이 같으면 계산 결과 재사용 | 필터 목록·선택 거점·입력 문자열 분리 |
| `useCallback` | 의존값이 같으면 함수 참조 재사용 | `HubExplorer`의 거점 선택 함수 |
| `useId` | 접근성 연결에 쓸 고유 ID 생성 | 비교표 제목·설명 연결 |
| `createContext` / `useContext` | 여러 하위 부품에 공유값 전달 | `useMapHost()`로 지도·준비 상태 전달 |
| `lazy(() => import(...))` | 필요한 시점에 컴포넌트 모듈 로딩 | 지도 화면·건물 상세 |
| `Suspense` / `fallback` | 지연 로딩 중 대체 UI 표시 | “지도 화면 불러오는 중…” |
| 마운트 / 언마운트 | 컴포넌트가 화면 트리에 들어옴 / 빠짐 | 탭 전환과 패널 수명 |
| 렌더 / 재렌더 | 현재 상태로 표시할 UI 계산 / 다시 계산 | 검색어·선택값 변경 |
| 이벤트 리스너 | 특정 사건 발생 시 실행할 함수 | 지도 클릭·확대·해시 변경 |
| Promise | 나중에 성공값 또는 실패 이유가 정해질 비동기 결과 | 서버 응답·SDK 로딩 |
| `async` / `await` | 비동기 함수 / 해당 결과를 기다려 이어서 실행 | 계산·마케팅 생성 요청 |
| `.then` / `.catch` | 비동기 성공 / 실패 처리 | 목록 조회 후 state 변경 |
| `try` / `catch` / `finally` | 시도 / 예외 처리 / 성공·실패 뒤 마무리 | 계산 후 로딩 해제 |
| `Promise.all` | 여러 비동기 결과를 함께 기다림 | 기존 거점 심층의 상세·유닛·행사 조회 |

여러 화면에서 다음 패턴을 쓴다. 실제 목록 요청 코드의 구조를 줄인 예다.

```tsx
useEffect(() => {
  let alive = true;
  getBuildingVacancy(districtId).then((result) => {
    if (alive) {
      // 현재 화면에 해당하는 결과만 반영
    }
  });
  return () => { alive = false; };
}, [districtId]);
```

사용자가 A 거점에서 B 거점으로 이동했는데 A 응답이 늦게 도착할 수 있다. 정리 함수가 A 요청의 `alive`를 거짓으로 바꾸면 A 응답이 B 화면을 덮어쓰지 못한다. 네트워크 요청 자체를 취소하는 코드는 아니다.

Posting과 Program은 요청 번호·버전도 사용한다. 현재 번호와 응답의 번호가 다르면 결과를 반영하지 않는다. 이를 지연 응답 또는 오래된 응답 무효화라고 설명할 수 있다.

### 3.6 TypeScript·JavaScript 기호 사전

| 문법 | 뜻과 예 |
|---|---|
| `import ... from ...` | 다른 모듈의 함수·컴포넌트 가져오기 |
| `import type` | 실행값 없이 타입만 가져오기 |
| `export` / `export default` | 다른 파일에서 쓸 이름 / 기본 내보내기 |
| `@/lib/api` | `src/lib/api`로 연결되는 프로젝트 경로 별칭 |
| `function 이름(...)` | 재사용 가능한 처리 정의 |
| `return` | 함수 결과 반환. 컴포넌트에서는 JSX나 `null` 등 반환 |
| `let` | 이후 다시 대입할 수 있는 변수 선언 |
| `interface` | 객체가 가져야 할 필드의 형태 선언 |
| `type` | 타입에 이름 부여. 예: 화면 이름의 허용 목록 |
| `string`, `number`, `boolean` | 문자열·숫자·참거짓 자료형 |
| `T[]` | T 형식 값의 배열 |
| `[number, number]` | 숫자 두 개로 이루어진 튜플. 좌표 등에 사용 |
| `A \| B` | A 또는 B를 허용하는 유니온 타입 |
| `A & B` | A와 B의 요구사항을 함께 갖는 교차 타입 |
| `field?: T` | 생략할 수 있는 필드 |
| `T \| null` | T 또는 명시적으로 비어 있는 값 |
| `<T>` | 자료형을 매개변수로 받는 제네릭 |
| `Record<K, V>` | K를 키, V를 값으로 갖는 객체 타입 |
| `Pick<T, K>` | T에서 지정한 필드만 고름 |
| `Exclude<A, B>` | A 타입에서 B에 해당하는 경우 제거 |
| `NonNullable<T>` | T에서 `null`, `undefined` 제외 |
| `keyof T` | T 객체 타입의 키 이름들 |
| `typeof value` | 타입 자리에서는 해당 값의 타입을 얻음. 실행 코드에서는 자료형 문자열 검사 |
| `as T` | TypeScript에 특정 타입이라고 단언. 실제 데이터 변환·검증은 아님 |
| `as const` | 문자열 등 값을 넓은 타입 대신 구체적인 리터럴로 유지 |
| `unknown` | 아직 형식을 모르는 값. 사용 전에 확인 필요 |
| `any` | 타입 검사를 크게 완화. 지도 SDK 주변에 남아 린트 경고 대상 |
| `obj?.field` | 객체가 `null`·`undefined`이면 중단하고 `undefined` 반환 |
| `value ?? fallback` | `null`·`undefined`일 때만 대체값 사용. 숫자 0은 보존 |
| `value || fallback` | 0·빈 문자열·false 등 거짓으로 평가되는 값에서도 대체값 사용 |
| `!value` / `!!value` | 참거짓 반전 / 참거짓으로 변환 |
| `!==` | 엄격하게 같지 않은지 비교 |
| `...obj` | 객체 필드를 펼침. state 복사 후 일부 변경에 사용 |
| `{ ...old, query: "" }` | 다른 필드는 유지하고 검색어만 비움 |
| `[...a, ...b]` | 두 배열을 새 배열로 결합 |
| `[key]: value` | 변수의 값을 객체 키로 사용 |
| `` `거점 ${id}` `` | 템플릿 문자열. 값 삽입 |
| `.map(...)` | 각 항목을 다른 값이나 JSX로 변환 |
| `.filter(...)` | 조건에 맞는 항목만 남김 |
| `.find(...)` | 조건에 맞는 첫 항목 검색 |
| `.some(...)` / `.every(...)` | 하나 이상 조건 충족 / 모두 조건 충족 |
| `.includes(...)` | 값 포함 여부 확인 |
| `.reduce(...)` | 배열을 합계·대표값 등 하나로 누적 |
| `.flatMap(...)` | 각 항목의 결과 배열을 한 단계 펼침 |
| `.slice(...)` | 일부 구간 복사. 후보 더보기·근거 세 줄 등에 사용 |
| `.sort(...)` | 정렬. 원본을 바꾸므로 복사 후 정렬하는 코드도 있음 |
| `Object.keys/values/entries` | 객체의 키 / 값 / 키·값 쌍을 배열로 얻음 |
| `new Map()` / `new Set()` | 키·값 목록 / 중복 없는 값 집합 |
| `.trim()` / `.split()` / `.join()` | 양끝 공백 제거 / 문자열 분리 / 문자열 결합 |
| `Number.isFinite(...)` | 유한한 숫자인지 검사. `NaN`·무한대 배제 |
| `.toFixed(n)` | 소수 n자리로 표시할 문자열 생성 |
| `.toLocaleString()` | 환경의 숫자 표기 방식에 맞춰 문자열 생성 |
| `Math.min/max/round/abs` | 최솟값 / 최댓값 / 반올림 / 절댓값 |
| 정규식 `/.../` | 문자열 형식 검색·검사. 해시·숫자 입력·URL 검사 등에 사용 |

`??`와 `||`는 데이터 화면에서 특히 다르다. `0 ?? "없음"`은 0이지만 `0 || "없음"`은 “없음”이다. 측정값 0을 결측으로 바꾸지 않으려면 의도에 맞게 골라야 한다.

## 4. 파일별로 무엇을 하고, 왜 이 코드를 썼는가?

### 4.1 앱과 여덟 화면

| 파일 | 주요 함수·처리 | 현재 역할과 구현 이유 |
|---|---|---|
| [src/main.tsx](src/main.tsx) | `createRoot`, `render` | React 시작과 전역 CSS 로딩을 한 진입점에서 수행 |
| [src/App.tsx](src/App.tsx) | `App`, `reviewBuilding`, 아이콘 함수들 | 여섯 화면 전환, Page 작업 상태 보존, Page→Posting 식별자 전달. 레일 아이콘은 직접 SVG로 작성해 아이콘 패키지 추가를 피함 |
| [src/pages/SeoulDashboard.tsx](src/pages/SeoulDashboard.tsx) | `SeoulDashboard`, `shade`, `Bar` | 25개 자치구 진입 계획을 Phase·B2C·B2B 점수로 표시. 이 화면은 API 실시간 조회가 아니라 생성된 정적 TypeScript 데이터를 사용 |
| [src/pages/HubExplorer.tsx](src/pages/HubExplorer.tsx) | `hubFromHash`, `pick`, `fitPadding`, `Row` | 거점을 고르면 지도 이동·실측 범위·요약을 같은 화면에 표시. 지도와 목록을 따로 이동하지 않아 탐색 맥락 유지 |
| [src/pages/MapShell.tsx](src/pages/MapShell.tsx) | `fromGeoJSON`, `focus`, `clearOverlays`, `toggleSaved`, `review` | 공실·유동·임대·밀도 레이어, 건물 검색·상태 필터·후보 최대 3개·메모·입점 검토. 지도와 목록에 같은 필터 결과를 사용 |
| [src/pages/PlatformConsole.tsx](src/pages/PlatformConsole.tsx) | `headline`, `IdentitySection`, `OpeningsSection`, `SiteCard`, `ForecastCard`, `RecommendCard`, `SentimentSection` | 상권 정체성·수요·검색 추세와 공실 자리 추천을 설명. 모델 성능은 근거 영역에 두고, 후보 2~3곳을 비교할 수 있게 함 |
| [src/pages/PostingConsole.tsx](src/pages/PostingConsole.tsx) | `PostingSession`, `run`, `TierCard`, `srcLabel`, `srcClass` | 건물 유닛·업종·권리금·전략을 서버에 보내 세 전략의 비용·순익·회수기간 표시. 계산 입력과 응답의 거점·유닛이 같은지도 검사 |
| [src/pages/ProgramStudio.tsx](src/pages/ProgramStudio.tsx) | `searchPlaces`, `applyPlace`, `submit`, `headline`, `Result`, `DraftWorkspace`, `Field`, `Thumb` | 프로필 검색·입력 → 온라인/오프라인 홍보안 생성 → 본문 편집·미리보기·복사. 생성 원본과 편집본의 검증 상태를 구분 |
| [src/pages/PageDashboard.tsx](src/pages/PageDashboard.tsx) | `Board`, `DistrictDeep`, `VacancyMap`, `FloorVacancies`, `FloorVacancyCard` | `#board`로 남아 있는 기존 거점 보드·심층 화면. 층별 매물·기존 3-Tier·행사 섹션을 보유. 별도 지도 생성 코드도 이 안에 남아 있음 |
| [src/pages/AdminCoverage.tsx](src/pages/AdminCoverage.tsx) | `load`, `Tile` | `#admin`에서 관리자 토큰으로 커버리지·제외 건물 조회. 토큰은 `sessionStorage`에 저장. 화면에서 직접 `fetch`하는 현재 예외 |

서울 로드맵 데이터의 생성 시각은 `src/lib/seoul/districts.ts`에 기록된 2026-06-07이다. 이 파일의 Phase는 진입 계획이지 현재 거점별 수집 완료율이 아니다. 진행률은 루트 지침대로 상태 스크립트에서 확인해야 한다.

### 4.2 공용 컴포넌트

| 파일 | 핵심 역할 | 왜 필요한가 |
|---|---|---|
| [src/components/MapHost.tsx](src/components/MapHost.tsx) | 지도 생성·공유 컨텍스트·숨김 | 거점/Page 사이에서 같은 지도 인스턴스를 유지해 SDK 재초기화와 카메라 상태 손실을 줄임 |
| [src/components/BuildingViewer.tsx](src/components/BuildingViewer.tsx) | `placeFloors`, `approxFloors`, `stackBasis`, `FloorStack`, `StreetView` | 층 상태와 실제 거리뷰를 나란히 표시. 층 근거가 없을 때의 근사 표시도 따로 밝힘 |
| [src/components/DistrictPicker.tsx](src/components/DistrictPicker.tsx) | 거점 선택기·`CaveatNote`·`MeasuredValue` | 여러 화면이 도시·예외·결측을 같은 방식으로 표시 |
| [src/components/CandidateCompare.tsx](src/components/CandidateCompare.tsx) | 같은 거점 건물 후보의 비교표·메모 | 조건을 나란히 비교하고 선택 이유를 기록. 대화상자를 닫으면 이전 포커스로 복귀 |
| [src/components/PlatformComparison.tsx](src/components/PlatformComparison.tsx) | 자리 조건표·공통 눈금 차트 | 서버가 준 점수·상권 평균·차이의 값과 정밀도를 유지해 비교. 차트 막대는 `@visx/shape`의 `Bar` 사용 |
| [src/components/Verdict.tsx](src/components/Verdict.tsx) | `Verdict`, `Fold` | 질문→결론→근거 세 줄→출처의 순서를 재사용. 네 번째 근거부터 접고 출처는 펼쳐둠 |

`MapHost`는 지도 탭을 처음 열 때 SDK와 지도를 준비한다. 다른 일반 탭으로 이동하면 `visibility: hidden`으로 숨기고, Page·거점의 오버레이는 제거한다. 공유 지도가 살아 있다고 모든 화면이 카메라를 전혀 건드리지 않는 것은 아니다. 거점 선택·목록 로딩에 따른 중심 이동이나 경계 맞춤은 각 화면의 Effect가 따로 수행한다. `#admin`·`#board`는 `App`의 별도 반환 경로여서 일반 탭 공유 구조와도 다르다.

`BuildingViewer`의 층 배열은 다음처럼 만들어진다.

1. `comFloors`: 상업 용도 층 번호를 확인한다.
2. `occFloors`: 영업이 확인된 층을 구분한다.
3. `unknownN`: 층을 모르는 점포로 인해 불확실한 층을 구분한다.
4. 영업·층 미상·공실·비상업을 다른 색과 라벨로 표시한다.
5. 층 근거가 없으면 점유율을 아래 층부터 채운 근사로 보여주고 “실제 공실 층과 다를 수 있다”고 명시한다.

렌더 상한은 20개 층이다. 스택은 건축물의 정확한 3차원 외형을 복원한 것이 아니다. 거리뷰의 촬영일과 건물까지의 거리도 함께 표시한다. 과거 거리뷰 사진을 현재 공실 여부의 판정 자료로 취급하지 않기 위해서다.

### 4.3 디자인 부품·토큰

| 파일 | 역할과 연결 상태 |
|---|---|
| [src/design/components/Button.tsx](src/design/components/Button.tsx) | `brand`, `naver`, `ghost` 변형과 공통 버튼 스타일. 전달받은 `className`을 자체 클래스와 병합 |
| [src/design/components/Card.tsx](src/design/components/Card.tsx) | 공통 카드 배경·테두리·여백을 적용하며 자식 콘텐츠를 감쌈 |
| [src/design/components/design.css](src/design/components/design.css) | 위 버튼·카드의 실제 CSS. hover·disabled 상태 포함 |
| [src/design/components/MapMarkerPin.tsx](src/design/components/MapMarkerPin.tsx) | `vacancyDotHTML`은 실제 지도 점의 HTML 문자열, `vacancyDotAnchor`는 점 중심 오프셋. `MapMarkerPin` 컴포넌트도 정의돼 있으나 현재 앱의 사용처는 확인되지 않음 |
| [src/design/components/BottomSheet.tsx](src/design/components/BottomSheet.tsx) | 하단 시트 부품. 현재 소스의 호출·import 연결은 확인되지 않음 |
| [src/design/components/VacancyLegend.tsx](src/design/components/VacancyLegend.tsx) | 공실 색 범례 부품. 현재 소스의 호출·import 연결은 확인되지 않음 |
| [src/design/components/NaverPayButton.tsx](src/design/components/NaverPayButton.tsx) | 공식 버튼 교체 TODO가 있는 자리표시자. 현재 결제 기능이 연결됐다는 증거가 아님 |
| [src/design/tokens/colors.ts](src/design/tokens/colors.ts) | 브랜드·네이버·공실 상태·PPPP 트랙 색과 `TrackKey` 타입 |
| [src/design/tokens/layout.ts](src/design/tokens/layout.ts) | 간격·모서리·그림자 상수. 현재 소스에서 import 사용은 확인되지 않음 |
| [src/design/tokens/typography.ts](src/design/tokens/typography.ts) | 글자 크기·줄 간격·굵기 표와 `typeStyle`. 현재 소스에서 import 사용은 확인되지 않음 |
| [src/styles/tokens.css](src/styles/tokens.css) | 실제 전역 토큰·자체 호스팅 폰트·기본 여백·출처/예외 스타일 |

디자인 토큰은 “자주 쓰는 시각 규격에 이름을 붙인 값”이다. 예를 들어 내비게이션 폭을 `--rail-w`로 관리하면 레일과 지도·본문이 같은 폭을 사용한다.

현재 토큰 체계의 의도와 실제 적용은 구분해야 한다. 여러 화면에는 직접 적은 색·글자 크기가 남아 있고, `layout.ts`의 `space[5]`는 20인 반면 CSS의 `--sp-5`는 24px다. 두 간격 체계를 인덱스만 보고 동일한 값으로 취급하면 안 된다. 정의된 디자인 부품이 모두 사용 중인 것도 아니다.

네이버 지도 SDK의 `icon.content`가 HTML 문자열을 받는 자리에서는 다음처럼 문자열을 만든다.

```ts
`<div style="width:${size}px;height:${size}px;border-radius:50%;...">
</div>`
```

이것은 JSX가 아니다. JavaScript가 HTML 문자열을 만들고 지도 SDK가 이를 사용한다. JSX는 React가 텍스트 삽입을 처리하지만 HTML 문자열 조립은 그 경로를 거치지 않는다. 두 방식을 같은 것으로 읽지 않아야 한다. 기존 `PageDashboard`에는 마커·정보창 HTML을 직접 조립하는 코드도 남아 있다.

### 4.4 API·지도·경계·데이터 보조 파일

| 파일 | 주요 역할과 이유 |
|---|---|
| [src/lib/api.ts](src/lib/api.ts) | API 주소·GET/POST 요청과 데이터 타입을 모음. 화면마다 주소·직렬화·오류 처리를 반복하지 않도록 함 |
| [src/lib/naverMap.ts](src/lib/naverMap.ts) | `loadNaverMaps`로 SDK 중복 로딩 방지, `describeNaverMapError`로 인증 오류 설명, `renderStreetView`로 거리뷰 생성·정리. `renderDistrictMap` 보조 함수는 정의돼 있으나 현재 앱 호출은 확인되지 않음 |
| [src/lib/hubBoundary.ts](src/lib/hubBoundary.ts) | 실측 격자 셀을 이어 측정 범위의 외곽·구멍·조각을 계산 |
| [src/lib/workspaceState.ts](src/lib/workspaceState.ts) | Page 검색·상태 필터·선택 건물·후보·메모의 타입과 초기값, Posting 인계 타입 |
| [src/lib/seoul/districts.ts](src/lib/seoul/districts.ts) | Gold 점수 자료 등을 바탕으로 생성된 서울 진입 로드맵 상수. 자동 생성 주석과 생성 시각 보유 |
| [src/vite-env.d.ts](src/vite-env.d.ts) | Vite 클라이언트 타입 선언을 참조하는 파일. 실행 화면 코드는 아님 |

`hubBoundary.ts`의 주요 함수는 다음과 같다.

| 함수 | 의미 |
|---|---|
| `computeHubBoundary` | 셀 전체를 입력받아 경계 조각·셀 수·외접 범위를 생성 |
| `ringsOf` | 셀 네 변 중 이웃이 없는 변을 이어 경계 고리 생성 |
| `shoelace` | 다각형 면적 부호로 외곽과 구멍의 방향 구분 |
| `bboxOf`, `bboxContains` | 도형을 감싸는 사각 범위와 포함 여부 계산 |
| `toLatLng` | 격자 좌표를 위도·경도로 변환 |
| `boundaryBadge` | 조각 수와 최대 조각 비중에 맞는 범례 문구 작성 |

네 방향으로 붙은 셀을 한 조각으로 묶는다. 공실 0인 셀도 측정된 셀이므로 포함한다. 떨어진 조각 사이를 채우지 않고 구멍도 보존한다. 그래서 그 선의 뜻은 “상권의 법적·공식 경계”가 아니라 “응답 셀에 근거한 측정 범위”다.

## 5. 데이터가 화면까지 오는 과정

```text
사용자가 거점·건물·입력 조건 선택
  → React 이벤트 함수 실행
  → 상태 변경 또는 API 호출
  → src/lib/api.ts의 요청 함수
  → /api/v1/... 주소로 HTTP 요청
  → 개발 중에는 Vite의 /api 프록시가 백엔드로 전달
  → 백엔드 JSON 응답
  → React state에 결과 반영
  → 조건부 렌더·목록·표·지도 오버레이 갱신
```

프론트엔드는 주로 서버의 모델·계산 결과를 받아 표현한다. 이 폴더에 LSTM·GNN 학습 코드가 들어 있는 구조는 아니다. 다만 화면용 필터·집계·좌표 계산·비교 차이·공실률 환산 같은 클라이언트 계산은 있다.

### 5.1 실제 GET 요청 함수

원본: `src/lib/api.ts`.

```ts
const BASE = "/api/v1";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}
```

| 코드 | 의미 |
|---|---|
| `BASE` | 공통 API 경로 앞부분 |
| `path: string` | 추가 경로를 문자열로 받음 |
| `Promise<T>` | 나중에 T 형식의 결과를 반환하는 비동기 함수 |
| `fetch(...)` | 브라우저에서 HTTP 요청. 별도 method가 없으면 GET |
| `await` | 응답이 올 때까지 이 함수의 다음 진행을 기다림 |
| `res.ok` | HTTP 상태가 성공 범위인지 확인 |
| `throw new Error(...)` | 실패를 예외로 전달해 화면이 오류를 처리하게 함 |
| `res.status` | HTTP 상태 코드 |
| `res.json()` | 응답 본문을 JSON으로 해석 |
| `as Promise<T>` | 타입 단언. 서버 응답의 필드가 실제로 맞는지 런타임 검증하지는 않음 |

POST 공통 함수는 `method: "POST"`, JSON 형식을 나타내는 `Content-Type`, `JSON.stringify(body)`를 추가한다. `extraHeaders`는 상용 Program의 조직 API 키 등 추가 헤더를 받는다.

### 5.2 API 요청 목록

아래 상대 경로 앞에는 보통 `/api/v1`이 붙는다. 함수명은 실제 코드 기준이다.

| 함수 | 메서드·경로 | 역할 |
|---|---|---|
| `getHealth` | GET `/health` | 상태 조회 보조 함수. 공통 `/api/v1` 바깥이며 현재 화면 호출은 확인되지 않음 |
| `getBuildingHistory` | GET `/buildings/{id}/history` | 건물 이력 조회 보조 함수. 현재 화면 호출은 확인되지 않음 |
| `listDistricts` | GET `/commercial-districts` | 거점 목록·요약 |
| `getDistrict` | GET `/commercial-districts/{id}` | 기존 거점 심층 상세 |
| `getSentiment` | GET `/commercial-districts/{id}/sentiment` | 이름은 과거 감성 API지만 현재 타입은 행정동 구역·결측 감성도 표현 |
| `getVacancyHeatmap` | GET `/heatmap/vacancy?district=...` | 공실 격자·출처·앵커 등 |
| `getBuildingVacancy` | GET `/heatmap/buildings?district=...` | 건물 GeoJSON |
| `getRentHeatmap` | GET `/heatmap/rent?district=...` | 임대시세 격자 |
| `getFootfallHeatmap` | GET `/heatmap/footfall?district=...&hour=...&daytype=...` | 시간대·평일/주말 유동인구 |
| `getDensityHeatmap` | GET `/heatmap/density?district=...&metric=...` | 유동인구 또는 점포 밀도 |
| `getPostings` | GET `/commercial-districts/{id}/postings` | 계산 가능한 공실 유닛과 시나리오 |
| `getFloorVacancies` | GET `/commercial-districts/{id}/floor-vacancies?...` | 층별 매물. 계산 유닛과 구분 |
| `getMarketing` | GET `/marketing/{id}` | 상권 행사·온라인 콘텐츠 |
| `getPlatformProfile` | GET `/commercial-districts/{id}/platform` | 상권 정체성과 자리별 제안 |
| `predictVacancy` | POST `/ai/predict-vacancy` | 공실 프록시 예측 요청 |
| `recommendIndustry` | POST `/ai/recommend-industry` | 거점 또는 좌표 기준 업종 추천 |
| `simulateRevenue` | POST `/ai/simulate-revenue` | 입점 비용·회수기간 시뮬레이션 |
| `lookupStorePlaces` | GET `/marketing/places?...` | 상호 검색 후보 |
| `lookupStoreReviews` | GET `/marketing/reviews?...` | 가게 언급 블로그 스니펫 |
| `generateStoreMarketing` | POST `/marketing/generate` | 공개 데모 마케팅 생성 |
| `generateCommercialStoreMarketing` | POST `/marketing/onboarding/generate` | 조직 API 키·동의 계약을 포함한 상용 생성 |
| `AdminCoverage.load` | GET `/api/v1/admin/coverage` | 관리자 화면의 직접 요청. `X-Admin-Token` 사용 |

`URLSearchParams`는 검색 조건을 URL 질의 문자열로 만들고, `encodeURIComponent`는 가게명·주소의 공백·한글·특수문자가 URL 구조와 섞이지 않도록 인코딩한다. 일반적인 웹 인코딩 기능이며 암호화는 아니다.

현재 `/health`는 `vite.config.ts`의 `/api` 프록시 규칙에 포함되지 않는다. 위 표의 함수가 정의됐다는 사실과 현재 개발 서버에서 해당 함수가 정상 동작한다는 사실은 구분한다.

### 5.3 PlaceOS 데이터·모델 용어

| 용어 | 이 코드에서 읽어야 할 뜻 |
|---|---|
| 거점 / district | 탐색·서빙의 상권 단위. 일반 자치구와 같은 뜻이라고 가정하지 않음 |
| `district_id` | 거점의 식별자 |
| `building_id` | 건물 식별자 |
| 유닛 / `unit_id` | Posting 계산에 사용하는 자리 식별자 |
| 층별 매물 | 지번·층을 기준으로 한 목록. 건물 단위 ROI 유닛과 다름 |
| `capacity` / `active` | 수용 재고 / 영업 재고. 층 근거 경로 등 해당 응답 계약의 단위를 확인 |
| `lat`, `lng`, `lon` | 위도·경도. 프론트의 `lng`를 추천 API에는 `lon`으로 전달 |
| Polygon / footprint | 다각형 / 지면에서 본 건물 외곽선 |
| Heatmap | 값을 색·강도로 나타내는 지도 |
| Choropleth | 구역별 값을 구역의 색으로 표현하는 지도 |
| Overlay | 지도 위에 추가하는 마커·선·면·패널 |
| POI | 역·랜드마크 같은 관심 지점 |
| BBox | 도형 전체를 감싸는 사각 범위 |
| Gold | 가공·검증한 데이터 산출 계층. 브라우저는 대체로 이를 읽는 서버 응답을 받음 |
| Seed / synthetic | 미리 정한 예시값 / 합성값. 실측으로 표현하면 안 됨 |
| Fallback | 기본 경로를 쓰지 못할 때의 대체 경로. 항상 가짜라는 뜻은 아니며 경로별 근거 확인 필요 |
| Stub | 테스트·대체 응답용 최소 구현. 모델 실호출 결과와 구분 |
| Proxy(데이터) | 직접 측정하려는 대상 대신 사용하는 대리지표 |
| Proxy(네트워크) | 요청을 다른 서버로 전달하는 중계. 대리지표와 다른 뜻 |
| SSOT | Single Source of Truth. 특정 값의 기준 원본 |
| 입력 계약 | 어떤 입력·출처·동의를 어떤 형태로 주고받을지 정한 규칙 |
| `vacancy_source` | 공실 값이 `gold` 또는 `synthetic`인지 표시 |
| `inputs_source` | 면적·임대료·권리금·유동 등 개별 입력의 출처 |
| `absent` / `contract` | 권리금 미입력으로 0을 전제 / 기업이 입력한 값 |
| `vacancy_withheld` | 측정은 했지만 대표성이 부족해 거점 대표값을 제공하지 않는 상태 |
| `caveat` | 직접 비교·해석에 필요한 예외 설명 |
| R-ONE / 앵커 | 임대·공실 등 외부 통계 및 대조 기준. 화면의 출처·비교 단위 확인 필요 |
| TRDAR / 집계구 | 상권 자료와 더 작은 통계 구획. 표시 격자 크기와 원자료 집계 단위는 별개 |
| LSTM | 시계열 예측 모델. 프론트는 예측 응답을 표시 |
| GNN | 그래프 기반 모델. 점포 관계 등에 기반한 업종 추천 응답 표시 |
| `vac_proxy` | 공실 대리지표. 그 값 자체가 공실률 %는 아님 |
| Top-1 / Top-3 | 정답이 첫 추천 / 상위 세 추천 안에 드는 평가 지표 |
| Prior / baseline | 모델과 비교할 기존 분포·단순 기준 |
| Lift | 기준 성능 대비 개선 정도 |
| Holdout | 학습에 쓰지 않고 검증에 남겨둔 자료 |
| MAE / RMSE | 평균 절대오차 / 제곱오차 평균의 제곱근. RMSE는 큰 오차에 더 민감 |
| 3-Tier | 고급화·가성비·기능중심의 세 전략 |
| `roi_months` | 코드가 회수기간을 개월로 전달하는 필드. 일반적인 ROI 수익률 %와 다름 |
| `viable` | 해당 시나리오의 회수 가능 여부. false를 결측과 혼동하지 않음 |
| LLM / vision | 언어 생성 모델 / 이미지도 읽는 처리 경로 |
| 컨텍스트 | 생성·판단 요청에 함께 제공하는 상권·가게의 배경 자료 |
| HA | 프로젝트의 Humanistic Authority 후처리 검증. 입력과 생성 결과의 금액·표현 등을 대조한 서버 판정 |
| `ha_check` / `ha_findings` | 모델이 적은 자체점검 문장 / 서버가 반환한 검증 항목 |
| `warning` / `violation` | 경고 / 생성물 폐기 사유가 되는 위반. UI가 둘을 구분 |

GNN 점수는 입점 성공 확률로 읽으면 안 된다. LSTM의 공실률 환산도 현재 공실률에 예측 delta를 더하는 근사로 명시돼 있다. 이것은 코드의 출력 계약 설명이며 모델의 정확성을 별도로 입증한 결과는 아니다.

### 5.4 Page → Posting 인계가 엄격한 이유

Page는 선택한 건물의 `districtId`, `buildingId`, `buildingName`을 `App`에 전달한다. `App`이 Posting 화면으로 전환하면 Posting은 서버 유닛 목록에서 `vu-${buildingId}`와 정확히 일치하는 ID를 찾는다.

일치하지 않으면 이름이 비슷하거나 좌표가 가까운 유닛을 자동으로 고르지 않는다. 시뮬레이션 응답의 거점·유닛도 요청과 대조한다. 다른 건물이나 층 표본을 선택 건물의 비용 계산으로 오인하는 것을 막기 위한 코드다.

### 5.5 저장과 복사의 실제 범위

| 항목 | 보관·동작 범위 |
|---|---|
| Page 후보·메모·검색 | `App`의 React 메모리. 일반 탭 왕복 시 유지, 새로고침 시 초기화 |
| Program 입력·편집 초안 | 해당 화면의 React 메모리. 새로 생성·프로필 변경·화면 이탈 등에 따라 초기화 |
| Program 조직 API 키 | React 메모리에서 요청 헤더에 사용. 브라우저 저장소 보관 코드 없음 |
| 관리자 토큰 | `sessionStorage` 사용. 같은 탭에서 새로고침 후에도 읽을 수 있음 |
| 본문 복사 | `navigator.clipboard.writeText`로 사용자의 클립보드에 텍스트 복사 |
| 채널 발행·예약 | 현재 Program 화면에 연동 구현 없음. 초안 생성·편집·복사와 구분 |

HA 검증은 생성 원본에 관한 결과다. 사용자가 본문을 고치면 `edited` 상태가 되고 수정본은 서버 HA 검증을 거치지 않았다고 표시한다.
