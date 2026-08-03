"""애플리케이션 설정. 환경변수 기반 (pydantic-settings)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 카카오·네이버 수집 키는 예전부터 `data/.env` 에 산다 — 수집기(data/collectors)가 거기서 읽는다.
# 백엔드도 같은 키를 쓰게 되면서(가게 반자동 조회, 2026-08-03) 키를 복사해 두 벌로 관리하면
# 반드시 어긋나므로 원본 파일을 그대로 읽는다.
# 경로는 **파일 기준 절대경로**다 — 예전의 상대 ".env" 는 cwd 가 apps/backend 일 때만 맞았다.
_BACKEND_DIR = Path(__file__).resolve().parents[2]   # apps/backend
_REPO_ROOT = _BACKEND_DIR.parents[1]                 # 저장소 루트(spaceos/)


class Settings(BaseSettings):
    # 뒤에 오는 파일이 우선한다 — 백엔드 전용 .env 가 data/.env 를 덮는다.
    # 없는 파일은 조용히 건너뛴다(배포판에는 data/.env 가 올라가지 않는다).
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / "data" / ".env", _BACKEND_DIR / ".env"),
        extra="ignore",
    )

    # PostgreSQL + PostGIS
    database_url: str = "postgresql://spaceos:spaceos@localhost:5432/spaceos"
    # Redis (캐싱 / Celery 브로커)
    redis_url: str = "redis://localhost:6379/0"
    # CORS 허용 오리진
    cors_origins: list[str] = ["http://localhost:5173"]
    # LLM API (PPPP 마케팅 콘텐츠 생성)
    llm_api_key: str = ""
    # Program 은 가게 단위로 대량 생성하는 워크로드라 Sonnet 이 기본이다
    # (docs/api-keys-and-specs.md·.env.example 과 동일 기준 — 2026-08-01 정합).
    # 품질이 더 필요한 거점 시연에서는 .env 의 LLM_MODEL 로 claude-opus-5 를 덮어쓴다.
    llm_model: str = "claude-sonnet-5"
    # 외부 AI 창업 코파일럿 (Posting) — 미설정 시 내부 3-Tier 폴백
    posting_copilot_url: str = ""
    posting_copilot_key: str = ""
    # 가게 반자동 조회(Program) — 미설정 시 조회 엔드포인트가 source="unavailable" 로 응답한다.
    # 플레이스 리뷰·사진에는 공식 API 가 없어(docs/feature-program.md §0) 이 둘로 대신한다:
    #   카카오 로컬  = 상호·카테고리·주소·좌표    네이버 블로그 검색 = 리뷰성 텍스트(스니펫)
    kakao_rest_api_key: str = ""
    naver_client_id: str = ""
    naver_client_secret: str = ""


settings = Settings()
