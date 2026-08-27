"""프로덕션 비밀값 가드 — 개발 기본값으로는 prod 기동이 실패해야 한다.

왜 테스트로 고정하나: 이 가드가 없으면 `JWT_SECRET` 미설정 배포가 **조용히 성공**하고,
그동안 발급된 토큰은 전부 위조 가능하다. 그리고 그 상태는 로그를 보지 않는 한
드러나지 않는다 — 이 저장소가 반복해 잡아 온 실패 양식(설정은 있는데 안 읽는다 ·
폴백이 고장을 가린다)과 같은 모양이라 실패를 시끄럽게 만들어 둔다.
"""
from __future__ import annotations

import pytest

from app.core.config import DEV_JWT_SECRET, Settings, _detect_env


def test_dev_allows_default_secret():
    s = Settings(app_env="dev", jwt_secret=DEV_JWT_SECRET)
    assert s.is_prod is False


def test_prod_rejects_default_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(app_env="prod", jwt_secret=DEV_JWT_SECRET)


def test_prod_accepts_real_secret():
    s = Settings(app_env="prod", jwt_secret="a-real-random-secret-value")
    assert s.is_prod is True


def test_env_autodetected_from_vercel_marker(monkeypatch):
    """APP_ENV 를 안 넣어도 Vercel 배포는 prod 로 판정돼야 한다 — 안 그러면
    '넣는 걸 잊으면 가드가 통과'라는 구멍이 그대로 남는다."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    assert _detect_env() == "prod"

    monkeypatch.delenv("VERCEL", raising=False)
    assert _detect_env() == "dev"


def test_explicit_app_env_wins_over_marker(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("VERCEL", "1")
    assert _detect_env() == "dev"
