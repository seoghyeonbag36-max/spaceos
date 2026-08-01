"""애플리케이션 설정. 환경변수 기반 (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


settings = Settings()
