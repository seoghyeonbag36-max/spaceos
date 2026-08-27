"""분석 API 사용량 계측 — KPI② (PMF) 의 원천 데이터가 실제로 쌓이는지.

여기서 고정하는 계약 둘:
  ① **익명 요청은 DB 를 건드리지 않는다.** 분석 API 는 Gold 파일 직독이라 DB 없이
     돌아야 하고, 계측을 붙였다고 그게 깨지면 안 된다. 이 테스트는 연결 자체가
     불가능한 DB 를 물려 놓고 익명 요청이 200 인지 본다 — 지연 연결에 기대는 설계라
     누가 track_access 에 질의를 하나 넣으면 여기서 터진다.
  ② **자격증명이 오면 기록된다.** 안 그러면 /admin/usage 가 영원히 0 이고,
     "파일럿이 안 쓴다"와 "계측이 고장났다"를 구분할 수 없다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.auth import AuditLog
from app.services.usage import ACCESS_PREFIX

_engine = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

# 연결이 불가능한 DB — ①번 계약(익명은 DB 를 안 건드린다)을 재는 데 쓴다.
_dead_engine = create_engine("postgresql://nobody@127.0.0.1:1/nonexistent")
_DeadSession = sessionmaker(bind=_dead_engine, autoflush=False, autocommit=False)

_ANALYSIS_PATH = "/api/v1/commercial-districts"


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


def _override_dead_db():
    db = _DeadSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=_engine)


client = TestClient(app)


def _signup(email, org_name="Acme"):
    return client.post("/api/v1/auth/signup", json={
        "org_name": org_name, "email": email, "password": "hunter2hunter"}).json()


def _accesses() -> list[AuditLog]:
    db = _TestSession()
    try:
        return [r for r in db.query(AuditLog).all()
                if r.action.startswith(ACCESS_PREFIX)]
    finally:
        db.close()


# ── ① 익명은 DB 를 건드리지 않는다 ─────────────────────────────────────────────


def test_anonymous_analysis_request_works_without_database():
    """DB 가 아예 없어도 분석 API 는 돈다 — 계측이 그 성질을 깨뜨리면 안 된다."""
    app.dependency_overrides[get_db] = _override_dead_db
    try:
        resp = client.get(_ANALYSIS_PATH)
        assert resp.status_code == 200, (
            "익명 요청이 DB 연결을 시도했다 — track_access 가 자격증명 없이도 "
            "질의를 하고 있다는 뜻이고, DB 없는 배포에서 분석 API 가 통째로 죽는다")
    finally:
        app.dependency_overrides[get_db] = _override_get_db


def test_anonymous_request_records_nothing():
    assert client.get(_ANALYSIS_PATH).status_code == 200
    assert _accesses() == [], "익명 트래픽까지 세면 파일럿 사용량이 데모 트래픽에 묻힌다"


# ── ② 자격증명이 오면 기록된다 ─────────────────────────────────────────────────


def test_jwt_authenticated_request_is_recorded():
    token = _signup("jwt@acme.com")["access_token"]
    assert client.get(_ANALYSIS_PATH,
                       headers={"Authorization": f"Bearer {token}"}).status_code == 200

    rows = _accesses()
    assert len(rows) == 1
    assert rows[0].action == f"{ACCESS_PREFIX}jwt"
    assert rows[0].detail == _ANALYSIS_PATH
    assert rows[0].user_id is not None


def test_api_key_authenticated_request_is_recorded():
    token = _signup("key@acme.com")["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    raw = client.post("/api/v1/auth/api-keys", json={"name": "k"}, headers=h).json()["key"]

    assert client.get(_ANALYSIS_PATH, headers={"X-API-Key": raw}).status_code == 200
    rows = _accesses()
    assert len(rows) == 1
    assert rows[0].action == f"{ACCESS_PREFIX}api_key"
    assert rows[0].user_id is None, "API 키에는 사람이 없다 — org 만 기록된다"


def test_invalid_api_key_is_rejected_not_downgraded():
    """조용히 익명으로 강등하면, 키가 죽은 파일럿이 200 을 받으면서 집계에서 사라진다."""
    resp = client.get(_ANALYSIS_PATH, headers={"X-API-Key": "sk_spaceos_bogus"})
    assert resp.status_code == 401


def test_revoked_api_key_is_rejected():
    token = _signup("revoked@acme.com")["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/v1/auth/api-keys", json={"name": "k"}, headers=h).json()
    client.delete(f"/api/v1/auth/api-keys/{created['id']}", headers=h)

    assert client.get(_ANALYSIS_PATH,
                       headers={"X-API-Key": created["key"]}).status_code == 401


def test_usage_summary_counts_orgs_not_requests(monkeypatch):
    """active_orgs 가 '살아 있는 파일럿 수'의 하한이다 — 요청 수와 구분돼야 한다."""
    from app.services import usage

    t1 = _signup("org1@a.com", org_name="A사")["access_token"]
    t2 = _signup("org2@b.com", org_name="B사")["access_token"]
    for token in (t1, t1, t1, t2):
        client.get(_ANALYSIS_PATH, headers={"Authorization": f"Bearer {token}"})

    db = _TestSession()
    try:
        summary = usage.usage_summary(db, days=30)
    finally:
        db.close()

    assert summary["active_orgs"] == 2
    assert summary["total_accesses"] == 4
    assert sorted(summary["by_org"].values()) == [1, 3]
