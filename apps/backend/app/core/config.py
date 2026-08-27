"""애플리케이션 설정. 환경변수 기반 (pydantic-settings)."""
import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 카카오·네이버 수집 키는 예전부터 `data/.env` 에 산다 — 수집기(data/collectors)가 거기서 읽는다.
# 백엔드도 같은 키를 쓰게 되면서(가게 반자동 조회, 2026-08-03) 키를 복사해 두 벌로 관리하면
# 반드시 어긋나므로 원본 파일을 그대로 읽는다.
# 경로는 **파일 기준 절대경로**다 — 예전의 상대 ".env" 는 cwd 가 apps/backend 일 때만 맞았다.
_BACKEND_DIR = Path(__file__).resolve().parents[2]   # apps/backend
_REPO_ROOT = _BACKEND_DIR.parents[1]                 # 저장소 루트(spaceos/)

# 이 값 그대로 배포되면 누구나 토큰을 위조할 수 있다. 아래 _guard_prod_secrets 가 막는다.
DEV_JWT_SECRET = "dev-only-change-me"


def _detect_env() -> str:
    """배포 환경 자동 판정 — 사람이 APP_ENV 를 안 넣어도 프로덕션을 알아본다.

    ⚠ 기본값을 `dev` 로 두고 "배포할 때 APP_ENV 를 넣어라"로만 적으면, 안 넣는 순간
    가드가 조용히 통과한다. 이 저장소가 반복해 잡아 온 실패 양식(설정은 있는데 안 읽는다ㆍ
    폴백이 고장을 가린다)과 같은 모양이라, 플랫폼이 스스로 심는 표식을 먼저 본다.
    Vercel 은 `VERCEL=1` 을 자동으로 넣는다(deploy-vercel.md 참조).
    """
    explicit = os.getenv("APP_ENV", "").strip().lower()
    if explicit:
        return explicit
    if os.getenv("VERCEL"):
        return "prod"
    return "dev"


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
    # dev | prod. 미지정 시 _detect_env() 가 플랫폼 표식(VERCEL)으로 판정한다.
    app_env: str = ""
    # 계정층 JWT — 기본값은 로컬 개발용이다. 배포 환경은 .env 로 반드시 덮어쓸 것
    # (기본값 그대로 배포하면 누구나 토큰을 위조할 수 있다). prod 에서는 기동이 실패한다.
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7   # 7일
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

    @model_validator(mode="after")
    def _guard_prod_secrets(self) -> "Settings":
        """프로덕션에서 개발용 비밀값이 남아 있으면 **기동을 실패시킨다.**

        경고 로그로 두지 않는 이유: 로그는 아무도 안 보고, 그 사이 발급된 토큰은 전부
        위조 가능하다. 뜨지 않는 편이 안전하다(fail closed).
        """
        if self.app_env == "":
            self.app_env = _detect_env()
        if self.app_env != "dev" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError(
                f"JWT_SECRET 이 개발 기본값 그대로다 (APP_ENV={self.app_env}). "
                f"배포 환경변수에 JWT_SECRET 을 설정할 것 — "
                f"기본값으로 뜨면 누구나 토큰을 위조할 수 있다.")
        return self

    @property
    def is_prod(self) -> bool:
        return self.app_env != "dev"


settings = Settings()
