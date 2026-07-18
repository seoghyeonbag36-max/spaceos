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
    llm_model: str = "claude-opus-4-8"
    # 외부 AI 창업 코파일럿 (Posting) — 미설정 시 내부 3-Tier 폴백
    posting_copilot_url: str = ""
    posting_copilot_key: str = ""


settings = Settings()
