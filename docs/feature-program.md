# Program — 마케팅 광고 솔루션 자동 생성 (가게 단위 → 상권 단위)

> PPPP: **Promotion → Program**. Humanistic Authority(균형·공생·공감)를 윤리 기준으로 적용.
> **2026-07-18 개정 — 2단계 구조**:
> 1. **가게 단위(우선)**: 네이버 지도에 노출되는 상가의 **사진·정보·이미지·리뷰** 데이터를 활용해 해당 가게의 온/오프라인 마케팅 광고 솔루션을 자동 생성한다.
> 2. **상권 단위(후속)**: **Platform에서 수집한 정보**(상권분석 시계열·감성·리뷰 키워드)를 바탕으로 상권 마케팅 솔루션을 생성한다.

## 0. 타당성 검증 (2026-07-18) — 데이터 채널별 가능 여부

| 데이터 | 채널 | 판단 | 비고 |
|---|---|---|---|
| 상가 기본정보(이름·카테고리·좌표·주소) | 네이버 지역검색 API + 카카오 로컬 API | **가능(공식)** | `NAVER_CLIENT_ID/SECRET`, `KAKAO_REST_API_KEY` (§8-E) |
| 리뷰성 텍스트 | 네이버 **블로그 검색 API** | **가능(공식)** | `data/collectors/naver_blog.py` 이미 구현 |
| 검색 트렌드 | 네이버 데이터랩 | **가능(공식)** | 동일 수집기 |
| **플레이스 리뷰·사진** | 공식 API **없음** | **조건부** | PoC 내부 검증 한정 크롤러(`data/crawlers/review_crawler.py`, 약관·저작권 리스크) → **상용은 점주 제공 데이터(B2B 온보딩 동의) 원칙**. 크롤링 원본(특히 사진)을 고객 화면에 직접 서빙 금지 |
| 이미지 분석 | Claude(vision 내장) | **가능** | 별도 Vision API 불필요 (§8-D) |
| 상권 단위 컨텍스트 | Platform Gold (`gold/program_content_context`, 8-A 상권분석·감성) | **가능** | 기존 Gold 매핑 설계(§9)와 일치 |

**결론: 가능.** 단, 플레이스 리뷰·사진은 위 조건을 지침으로 강제한다 (`.claude/commands/program.md`에도 명시).

## 0-1. 컨텍스트 품질 결함 2건 — 해소 (2026-08-01)

LLM 입력이 되는 `gold/{거점}/program_content_context` 와 그 서빙 경로에서 두 결함을 고쳤다.
둘 다 **생성물이 이미 틀린 말을 하고 있던** 건이라 우선 처리했다.

### ① 동명이지(同名異地) 오염 — 7.3% → 상위 키워드 0건

거점명만으로 블로그를 질의해 같은 이름의 타 시도 상권 글이 섞였다. 54거점 전수 17,653건 중
1,295건(7.3%)이 타 지역이었고 8개 거점이 10% 이상(jangan 43.6% ← 수원·평택 장안동,
cityhall 33.5%, garosugil 31.8% ← 창원 가로수길, nonhyeon 23.1% ← 인천 논현동).
가로수길은 `창원`이 2번째로 큰 키워드였다.

| 층위 | 조치 | 효과 |
|---|---|---|
| 수집(1차) | 질의를 `서울 {거점명} 맛집/카페` 로 한정 (`collectors/naver_blog.py`) | 7.3% → **0.9%** (가로수길 25.2% → 1.3%) |
| Gold(2차) | 타지명 단독 글 제외 + **타지명·거점명 인접**("평택시 장안동") 제외 (`build_gold._is_offsite`) | 잔여분 제거 |
| Gold(3차) | 블로거당 3건 상한 (`_MAX_POSTS_PER_BLOGGER`) | nambu 386건 중 154건(40%) 도배 무력화 |
| Gold(4차) | 불용어에 후기·추천·주소·영업시간 등 상투어 추가 | 상위 5가 정보 항목명으로 낭비되던 것 해소 |

검증: 54거점 **상위 5·10위 안에 타지명 토큰 0개**. 서울 상호에 지명이 든 경우
(시청역 진주회관, 여의도 진주집, 안암 제주고깃집)는 의도적으로 살렸다.

**남는 한계**: 체험단처럼 여러 계정에 분산 발행된 광고는 못 잡는다 — cheongdam `조재범`
37건이 서로 다른 블로거 36명이라 문서빈도(11.3%)로도 블로거 상한으로도 걸러지지 않는다.
자동 규칙을 만들면 진짜 상호명까지 죽으므로 남겨 뒀다.

### ② 검색 트렌드 방향 오독 — 원인은 절단 아티팩트 + 해석 위임

상권 카피가 *"신사동을 찾는 발걸음이 다시 늘고 있는 요즘"* 이라고 썼는데 입력은 하락이었다.
원인이 두 겹이었다.

- **미완성 달**: 데이터랩 월 버킷의 마지막 달은 수집 시점까지의 부분합이다. 2026-07-18
  수집분의 7월이 신사동 63.4→35.6(56%)·가로수길 19.1→9.9(52%)로 찍혔는데 18/31일=58%
  라는 절단 비율과 거의 같았다. **급락이 아니라 집계 아티팩트였다** — 재수집으로 확인한
  7월 실제값은 63.9·19.2 다. → `build_gold._complete_trend_points` 가 잘라낸다.
- **해석 위임**: 프롬프트에 원시 수치만 실어 방향 판단을 LLM 에 맡겼다.
  → `marketing._trend_summary` 가 **최근 3개월 평균 vs 직전 3개월 평균**을 비교해
  ±5% 밖이면 상승/하락, 안이면 보합으로 **확정**한 문장을 넘긴다(6개 점 미만이면 트렌드 생략).
  시스템 프롬프트에도 "데이터가 말하지 않는 방향을 주장하지 않는다"를 명시했다.

실호출 검증(2026-08-01): 입력 `가로수길 하락(26.3→21.4, -18.6%); 신사동 보합(67.4→65.0, -3.6%)`
→ 생성 카피 4건 모두 유입 증가를 주장하지 않았고, `ha_check` 가 하락·보합 판정을 인용했다.

회귀 방지: `data/tests/test_program_context.py`(8건) + `tests/test_posting_marketing.py`
의 방향 판정 2건.

## 1. 담당 코드 영역

```
apps/backend/app/services/marketing.py    가게/상권 마케팅 솔루션 생성 서비스 (현존)
apps/backend/app/schemas/marketing.py     StoreProfile / StoreMarketing 스키마 (현존)
apps/backend/app/api/v1/marketing.py      GET /{id}(상권) + POST /generate(가게) (현존)
apps/backend/app/core/config.py           llm_api_key (이미 존재)
data/collectors/naver_blog.py             블로그 리뷰·트렌드 수집 (공식 API)
data/crawlers/review_crawler.py           플레이스 리뷰 크롤러 골격 (PoC 한정)
```

## 2. 환경 설정

```bash
cd apps/backend && source .venv/bin/activate
pip install anthropic langchain-anthropic   # requirements.txt 에도 추가
echo "LLM_API_KEY=sk-ant-..." >> .env        # .gitignore 로 보호됨
```

## 3. 작업 순서

1. **가게 프로필 입력 계약** (`schemas/marketing.py`) — `StoreProfile`(이름·카테고리·주소·리뷰 텍스트·이미지 URL/설명). 수집 채널이 무엇이든 이 스키마로 정규화해 서비스에 전달.
2. **가게 단위 생성** (`services/marketing.py::generate_store_marketing`) — 리뷰 키워드·이미지 분석(vision)으로 강점/톤을 추출해 온라인(채널 믹스·SNS 문구)과 오프라인(전단·팝업·행사 참여) 솔루션 생성. LLM 미설정 시 규칙 기반 스텁 + `TODO: 실제 연동`.
3. **상권 단위 생성** — `GET /marketing/{id}`의 시드 데이터를 Platform Gold(`program_content_context`: 상권분석 시계열 + 감성 + 리뷰 키워드) 기반 생성으로 교체.
4. **Humanistic Authority 가드레일** — 생성 콘텐츠의 과장·허위·특정 자본 편중을 프롬프트 + 후처리로 검증.
5. **폐업 사유 요약(연계)** — 건물 히스토리(Page)의 closure_reason LLM 요약은 기존 계획 유지.

## 4. Claude Code 작업 예시

```
/clear
/program 가로수길 카페 1곳의 StoreProfile(블로그 리뷰 20건 + 이미지 3장)로
  generate_store_marketing 을 LLM(Claude vision) 실호출로 전환.
  Humanistic Authority 후처리 검증 포함. 실패 시 규칙 기반 스텁 폴백 유지.
```

## 5. 검증

- `cd apps/backend && pytest` — LLM은 mock, `POST /marketing/generate` 응답 스키마 검증
- 생성 콘텐츠 샘플을 균형·공생·공감 기준으로 정성 평가
- 크롤링 산출물이 고객 노출 경로에 직접 서빙되지 않는지 확인 (PoC 내부 검증 한정)
- API 키는 `.env`(`.gitignore` 보호)에만 — `.claude/settings.json`이 `.env` 읽기를 차단함
