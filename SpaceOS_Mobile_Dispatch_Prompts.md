# SpaceOS 모바일 Dispatch 프롬프트 모음 (서울 25구 기준)

> 폰의 Claude 앱 → **Dispatch 탭**에 아래 블록을 그대로 붙여넣으면, 켜져 있는 데스크톱의 Claude가 SpaceOS 저장소에서 작업하고 결과를 알림으로 보냅니다.
> 데스크톱이 `SpaceOS` 폴더에서 작업하면 `CLAUDE.md`가 자동 로드되어 기술 스택·코딩 규칙·거점 우선순위를 인식합니다.

**라우팅 요약**

| # | PPPP | 결과물 성격 | 실행 세션 |
|---|------|-----------|----------|
| 1 | **Platform** — 상권 AI 추천 엔진 | 코드 (백엔드 API) | Claude Code |
| 2 | **Page** — 공실 히트맵 + 3D 트윈 | 코드 (프론트엔드) | Claude Code |
| 3 | **Posting** — 입점 솔루션 비용-효용 | 분석 보고서 (docx) | Cowork |
| 4 | **Program** — 마케팅 자동화 | 콘텐츠 패키지 (docx) | Cowork |
| 5 | **디자인** — PPPP UX/UI 시스템 | UI 표준화 + HTML 목업 | Claude Code |

---

## 1. Platform — 서울 25구 상권 AI 추천 엔진 (Claude Code)

```
SpaceOS 저장소에서 Claude Code 세션으로 작업해줘.

목표: 서울 25구 "상권 AI 추천 엔진"을 백엔드 API로 완성한다.

1. data/pipelines/district_score.py 가 만든 Gold 산출물(구별 점수·phase·phaseSeq·deployOrder, 유동인구·공실·임대료 피처)을 읽는 로더를 app/services/ 에 만든다.
2. ml/models/gnn/industry_gnn.py(업종 추천)와 ml/models/lstm/vacancy_lstm.py(공실 예측) 골격을 연결해, 구 코드를 입력하면 ①공실 위험도 ②추천 업종 Top5 ③업종 간 시너지/잠식 근거를 반환하는 추천 서비스를 app/services/recommend.py 로 작성.
3. app/api/v1/ai.py 에 GET /api/v1/ai/recommend?district=강남구 라우터를 추가하고, 응답 스키마는 app/schemas/ 에 둔다.
4. 실데이터 미연동 구간은 더미 + TODO 주석으로 연동 지점을 명시(프로젝트 규칙).
5. tests/ 에 라우터 스모크 테스트 1개를 추가하고 pytest 통과를 확인.

완료되면 변경 파일 목록, curl 호출 예시, 테스트 결과를 알려줘.
```

---

## 2. Page — 서울 25구 공실 히트맵 + 3D 디지털 트윈 (Claude Code)

```
SpaceOS 저장소에서 Claude Code 세션으로 작업해줘.

목표: apps/frontend 의 서울 화면(src/pages/SeoulDashboard.tsx)에 25구 공실 히트맵 "Page"를 완성한다. 지도는 네이버지도(src/lib/naverMap.ts, ncpKeyId 9nbzrvj8qj) 기준.

1. 25구 폴리곤(src/lib/seoul/districts.ts) 위에 공실률을 색으로 칠하는 히트맵 레이어를 올리고, 기존 VacancyLegend 컴포넌트(src/design/components/VacancyLegend.tsx)로 deployOrder 구간 범례를 단다(서울 Phase 계획 색 구간과 동일하게).
2. 구 클릭 시 우측/하단 패널에 해당 구 요약(공실률·phase·추천 업종 Top3)을 표시. 데이터는 src/lib/api.ts 경유 /api/v1/heatmap·/api/v1/ai 에서 가져오되, 미구현 엔드포인트는 mock + TODO 주석.
3. 선택한 구의 대표 블록을 @react-three/fiber로 가볍게 3D 렌더(로딩 3초 이내 목표). 미설치면 설치 여부부터 확인하고, 무거우면 토글로 분리.
4. mapbox 잔존 코드는 건드리지 말고 네이버지도 경로만 사용. Tailwind 대신 기존 design/tokens·styles/tokens.css 유지.

npm run build(타입체크 통과)까지 확인하고, 변경 파일과 스크린샷을 알려줘.
```

---

## 3. Posting — 강남구 입점 솔루션 비용-효용 분석 (Cowork → docx)

```
SpaceOS 폴더 기준 Cowork 작업.

목표: 서울 진입 1순위 강남구 대상 "Posting" 입점 솔루션 보고서를 docx로 만든다.

한 공실 입지를 가정해 입점 전략을 ①고급화 ②가성비 ③기능중심 3가지로 나누고, 각각 초기 투자비·예상 월매출·회수기간(ROI)·리스크를 비용-효용 표로 비교한다.

- 근거 데이터: data/pipelines/district_score.py Gold의 강남구 피처(유동인구·공실·임대료 추정)를 사용하고, 모든 수치 가정은 출처/근거를 명시(추측 최소화).
- 구성: 핵심 요약(1p) → 입지·상권 진단 → 3개 전략 비용-효용 비교표 → 추천안+근거 → 리스크.
- 표·그래프 포함, 한글 폰트 임베딩 필수(프리뷰 □ 깨짐 방지).

SpaceOS 폴더에 저장하고 파일 위치를 알려줘.
```

---

## 4. Program — 마포구 마케팅 자동화 패키지 (Cowork → docx)

```
SpaceOS 폴더 기준 Cowork 작업.

목표: 서울 마포구(연남·홍대 일대) 상권을 위한 "Program" 마케팅 자동화 패키지를 만든다.

1. 해당 상권 톤에 맞는 SNS 포스팅 콘텐츠 5종(인스타 캡션+해시태그) 생성.
2. 분기 지역 행사/팝업 기획 3건(목표·타깃·예산·KPI).
3. 상인-건물주-소비자 참여 구조(Program) 1개 설계.

- Humanistic Authority 3지표(균형·공생·공감)를 콘텐츠 기준으로 적용하고, 각 산출물이 어느 지표를 충족하는지 표로 표시.
- 추후 LLM 자동화 연동용 "콘텐츠 생성 프롬프트 템플릿"을 부록으로 첨부.
- 결과는 docx(핵심 요약 + 상세), 한글 폰트 임베딩 필수.

SpaceOS 폴더에 저장하고 위치를 알려줘.
```

---

## 5. 디자인 — PPPP UX/UI 시스템 + 서울 홈 화면 (Claude Code + 목업)

```
SpaceOS 저장소에서 작업해줘.

목표: SpaceOS 웹앱의 PPPP 화면을 묶는 UX/UI를 표준화하고, 서울 우선순위 홈 화면을 디자인한다.

1. apps/frontend/src/design/tokens(colors·typography·layout)와 styles/tokens.css를 점검해 색·타이포·간격 토큰을 단일 기준으로 정리하고, 불일치가 있으면 맞춘다.
2. 4개 화면(Platform·Page·Posting·Program)이 공유하는 공통 레이아웃(상단 탭 + 좌측 상권 리스트 + 본문 지도/대시보드)을 design/components 컴포넌트로 표준화. 기존 SeoulDashboard·MapShell과 일관되게.
3. 서울 25구 진입 우선순위(강남>마포>종로…)를 한눈에 보여주는 대시보드 홈 화면을 디자인한다.
4. Tailwind 대신 기존 토큰/CSS 방식 유지. Storybook(.storybook)이 있으니 주요 컴포넌트 story도 갱신.

결과물: ①바로 미리볼 수 있는 정적 HTML 목업 1개(SpaceOS 폴더) + ②적용 가이드 요약. 모바일·3초 로딩·반응형 고려. 완료 후 목업 위치와 스크린샷을 알려줘.
```

---

## 공통 사용 팁

- **한 스레드 연속성**: Dispatch는 단일 연속 스레드라 1→2→3 순서로 이어 보내면 앞 작업 맥락을 유지합니다. 새로 시작할 필요 없이 "방금 추천 API에 마포구도 추가해줘" 식으로 후속 지시 가능.
- **거점 교체**: 프롬프트의 `강남구`/`마포구`를 다른 구로 바꾸면 그대로 재사용됩니다.
- **전제 조건**: 데스크톱이 켜져 있고 Claude 데스크톱 앱이 실행 중이어야 작업이 돌아갑니다. 설정에서 절전 모드 방지·모바일 알림 ON 권장.
- **결과 회수**: 완료 알림 후 폰에서 바로 파일을 받거나, Claude가 알려준 데스크톱 경로(SpaceOS 폴더)에서 확인.
