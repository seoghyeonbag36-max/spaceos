# Program — LLM 마케팅 자동화 + 행사 추천

> PPPP: **Promotion → Program**. 상인-건물주-소비자 간 지속 가능한 관계를 만드는 참여 구조. LLM으로 마케팅 콘텐츠를 자동 생성하고 지역 행사를 기획·추천한다. Humanistic Authority(균형·공생·공감)를 윤리 기준으로 적용.

## 1. 담당 코드 영역

```
apps/backend/app/api/v1/marketing.py     /generate-content (신규 라우터)
apps/backend/app/services/llm.py         LLM 클라이언트 래퍼 (신규)
apps/backend/app/services/events.py      지역 행사 추천 로직 (신규)
apps/backend/app/core/config.py          llm_api_key (이미 존재)
```

## 2. Claude Code 설치/환경

LLM 연동 라이브러리를 backend에 추가한다.

```bash
cd apps/backend && source .venv/bin/activate
pip install langchain openai            # 또는 google-generativeai (Gemini)
# requirements.txt 에도 추가
echo "LLM_API_KEY=sk-..." >> .env        # .gitignore 로 보호됨
```

## 3. 작성해야 할 코드 (순서)

1. **LLM 래퍼** (`app/services/llm.py`) — `settings.llm_api_key`로 LLM(OpenAI/Gemini) 클라이언트 초기화. `generate(prompt, context)` 함수. 호출 실패/레이트리밋 처리.
2. **콘텐츠 생성 라우터** (`app/api/v1/marketing.py`) — `POST /api/v1/marketing/generate-content`. 입력: 상권/업종/타겟·톤. 상권 감성 지수·리뷰 키워드(Silver/Gold)를 컨텍스트로 주입해 SNS 포스팅·홍보 문구 생성. `router.py`에 등록.
3. **폐업 사유 요약** — 건물 히스토리(Page)의 closure_reason을 LLM으로 요약하는 함수. buildings API에서 호출.
4. **행사 추천** (`app/services/events.py`) — 유동인구 페르소나 + 상권 특성 기반 팝업/축제 아이디어를 생성·추천. PPPP 마케팅 대행 수익모델과 연계.
5. **Humanistic Authority 가드레일** — 생성 콘텐츠가 특정 자본/업종 편중(균형), 상생 저해, 상권 분위기 불일치(공감)를 일으키지 않도록 프롬프트·후처리 검증 추가.

## 4. Claude Code 작업 예시

```
/clear
/backend-dev PPPP 마케팅 콘텐츠 자동 생성.
  app/services/llm.py 에 settings.llm_api_key 기반 LLM 래퍼 generate() 작성.
  app/api/v1/marketing.py 에 POST /generate-content 추가,
  상권 감성 키워드(Gold)를 컨텍스트로 주입. router.py 에 등록.
  생성물이 상권 분위기와 어긋나지 않도록 Humanistic Authority 검증 후처리 포함.
```

## 5. 검증

- `cd apps/backend && pytest` — LLM 래퍼는 mock으로, 라우터 응답 스키마 검증
- 생성 콘텐츠 샘플을 균형·공생·공감 기준으로 정성 평가
- API 키는 `.env`(`.gitignore` 보호)에만 두고 코드/커밋에 노출 금지 — `.claude/settings.json`이 `.env` 읽기를 차단함
