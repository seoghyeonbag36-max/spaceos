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


# ── API 키 ─────────────────────────────────────────────────────────────────────


def _auth(email="key@acme.com", org_name="Acme Corp"):
    token = _signup(email=email, org_name=org_name).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_api_key_issue_returns_plaintext_once():
    h = _auth()
    resp = client.post("/api/v1/auth/api-keys", json={"name": "ERP 연동"}, headers=h)
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"].startswith("sk_spaceos_")
    assert body["name"] == "ERP 연동"
    assert body["revoked_at"] is None

    # 목록에는 원문이 없다 — 발급 응답이 유일한 노출 지점이다
    listed = client.get("/api/v1/auth/api-keys", headers=h).json()
    assert len(listed) == 1
    assert "key" not in listed[0]
    assert listed[0]["id"] == body["id"]


def test_api_key_plaintext_is_not_stored():
    """DB 에 원문이 남으면 유출 시 그대로 쓰인다 — 해시만 있어야 한다."""
    h = _auth(email="hash@acme.com")
    raw = client.post("/api/v1/auth/api-keys", json={"name": "k"}, headers=h).json()["key"]

    from app.models.auth import ApiKey
    db = _TestSession()
    try:
        rows = db.query(ApiKey).all()
        assert len(rows) == 1
        assert raw not in rows[0].key_hash
        assert rows[0].key_hash != raw
    finally:
        db.close()


def test_api_key_requires_auth():
    assert client.post("/api/v1/auth/api-keys", json={"name": "x"}).status_code == 401
    assert client.get("/api/v1/auth/api-keys").status_code == 401


def test_api_key_revoke_marks_instead_of_deleting():
    """폐기가 삭제면 '언제까지 유효했나'를 못 답한다(실사 항목 2)."""
    h = _auth(email="revoke@acme.com")
    key_id = client.post("/api/v1/auth/api-keys", json={"name": "old"},
                          headers=h).json()["id"]

    resp = client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["revoked_at"] is not None

    listed = client.get("/api/v1/auth/api-keys", headers=h).json()
    assert len(listed) == 1, "폐기된 키가 목록에서 사라지면 감사추적이 끊긴다"
    assert listed[0]["revoked_at"] is not None


def test_api_key_revoke_unknown_id_is_404():
    h = _auth(email="unknown@acme.com")
    assert client.delete("/api/v1/auth/api-keys/nope", headers=h).status_code == 404


def test_api_key_is_scoped_to_own_org():
    """다른 조직 키는 존재 여부조차 흘리지 않는다 — 404 로 같이 떨어진다."""
    h_a = _auth(email="a@acme.com", org_name="A사")
    h_b = _auth(email="b@beta.com", org_name="B사")
    key_a = client.post("/api/v1/auth/api-keys", json={"name": "a-key"},
                         headers=h_a).json()["id"]

    assert client.delete(f"/api/v1/auth/api-keys/{key_a}", headers=h_b).status_code == 404
    assert client.get("/api/v1/auth/api-keys", headers=h_b).json() == []


def test_api_key_resolves_to_org_and_stops_after_revoke():
    from app.services import auth_service
    h = _auth(email="resolve@acme.com", org_name="Resolve사")
    created = client.post("/api/v1/auth/api-keys", json={"name": "r"}, headers=h).json()

    db = _TestSession()
    try:
        found = auth_service.resolve_api_key(db, created["key"])
        assert found is not None
        org, rec = found
        assert org.name == "Resolve사"
        assert rec.id == created["id"]
        assert auth_service.resolve_api_key(db, "sk_spaceos_deadbeef") is None
    finally:
        db.close()

    client.delete(f"/api/v1/auth/api-keys/{created['id']}", headers=h)
    db = _TestSession()
    try:
        assert auth_service.resolve_api_key(db, created["key"]) is None, \
            "폐기된 키가 계속 통과하면 폐기가 의미 없다"
    finally:
        db.close()
