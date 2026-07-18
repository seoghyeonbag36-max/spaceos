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
