"""계정층 — 가입(조직 생성)·로그인·/me. SQLite 인메모리로 돈다(Postgres 불필요).

docs/decision-infra-layer-2026-08-25.md §6 결정 A 의 첫 배선 검증. 여기서 도는 DB 는
분석 Gold 파이프라인과 무관한 별도 스토어다 — 기존 서빙 테스트에 영향 없다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_schema():
    """테스트마다 스키마를 새로 만든다 — 이메일 unique 제약이 테스트 간 안 새게."""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


def _signup(email="owner@acme.com", password="hunter2hunter", org_name="Acme Corp"):
    return client.post("/api/v1/auth/signup",
                        json={"org_name": org_name, "email": email, "password": password})


def test_signup_creates_org_and_returns_token():
    resp = _signup()
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_signup_duplicate_email_rejected():
    _signup(email="dup@acme.com")
    resp = _signup(email="dup@acme.com")
    assert resp.status_code == 409


def test_login_with_correct_password():
    _signup(email="login@acme.com", password="correct-horse")
    resp = client.post("/api/v1/auth/login",
                        json={"email": "login@acme.com", "password": "correct-horse"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_with_wrong_password_rejected():
    _signup(email="wrong@acme.com", password="correct-horse")
    resp = client.post("/api/v1/auth/login",
                        json={"email": "wrong@acme.com", "password": "not-it"})
    assert resp.status_code == 401


def test_login_unknown_email_rejected():
    resp = client.post("/api/v1/auth/login",
                        json={"email": "nobody@acme.com", "password": "whatever123"})
    assert resp.status_code == 401


def test_me_requires_token():
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_org_and_role_for_valid_token():
    signup = _signup(email="me@acme.com", org_name="Acme Corp")
    token = signup.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "me@acme.com"
    assert body["org"]["name"] == "Acme Corp"
    assert body["role"] == "admin"   # 가입자는 자기 조직의 admin 이다


def test_me_rejects_tampered_token():
    signup = _signup(email="tamper@acme.com")
    token = signup.json()["access_token"] + "x"
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
