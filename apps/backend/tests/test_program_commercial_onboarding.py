"""Program 상용 입력 온보딩 — 조직 인증·명시 동의·원문 비저장 계약."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.auth import AuditLog
from app.services.program_onboarding import AUDIT_ACTION

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _fresh_schema():
    app.dependency_overrides[get_db] = _override_get_db
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)
    app.dependency_overrides.pop(get_db, None)


client = TestClient(app)


def _api_key(email: str = "pilot@example.com", org_name: str = "파일럿 상점") -> str:
    signup = client.post("/api/v1/auth/signup", json={
        "org_name": org_name,
        "email": email,
        "password": "merchant-password",
    })
    token = signup.json()["access_token"]
    issued = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "Program 온보딩"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return issued.json()["key"]


def _body() -> dict:
    return {
        "profile": {
            "name": "점주 제공 테스트 카페",
            "category": "카페",
            "district_id": "garosugil",
            "address": "서울 강남구 테스트로 1",
            "reviews": ["산미 있는 원두를 직접 골라 제공합니다."],
            "image_urls": ["https://merchant.example/store.jpg"],
            "menu": ["오늘의 드립 6,000원"],
            "keywords": ["산미", "조용함"],
        },
        "consent": {
            "contract_version": "spaceos.program-onboarding/1",
            "data_origin": "merchant-provided",
            "processing_purpose": "program-marketing-generation",
            "consent_to_process": True,
            "rights_confirmed": True,
            "allow_external_model_processing": True,
            "raw_input_retention": "request-only",
        },
    }


def test_commercial_onboarding_requires_org_auth() -> None:
    response = client.post("/api/v1/marketing/onboarding/generate", json=_body())
    assert response.status_code == 401
    assert response.json()["detail"] == "조직 인증이 필요합니다"


def test_commercial_onboarding_rejects_incomplete_consent() -> None:
    key = _api_key()
    body = _body()
    del body["consent"]["rights_confirmed"]
    response = client.post(
        "/api/v1/marketing/onboarding/generate",
        json=body,
        headers={"X-API-Key": key},
    )
    assert response.status_code == 422


def test_commercial_onboarding_rejects_empty_merchant_content() -> None:
    key = _api_key(email="empty@example.com")
    body = _body()
    for field in ("reviews", "image_urls", "menu", "keywords"):
        body["profile"][field] = []
    response = client.post(
        "/api/v1/marketing/onboarding/generate",
        json=body,
        headers={"X-API-Key": key},
    )
    assert response.status_code == 422


def test_commercial_onboarding_returns_receipt_without_persisting_raw_input() -> None:
    key = _api_key(email="receipt@example.com")
    body = _body()
    response = client.post(
        "/api/v1/marketing/onboarding/generate",
        json=body,
        headers={"X-API-Key": key},
    )
    assert response.status_code == 201, response.text
    out = response.json()
    assert out["onboarding_id"]
    assert out["contract_version"] == "spaceos.program-onboarding/1"
    assert out["input_source"] == "merchant-provided"
    assert out["raw_input_persisted"] is False
    assert out["marketing"]["store_name"] == body["profile"]["name"]
    assert "profile" not in out and "consent" not in out

    raw_fragments = [
        body["profile"]["name"],
        body["profile"]["address"],
        body["profile"]["reviews"][0],
        body["profile"]["image_urls"][0],
        body["profile"]["menu"][0],
    ]
    with _Session() as db:
        receipt = db.execute(
            select(AuditLog).where(AuditLog.action == AUDIT_ACTION)
        ).scalar_one()
        detail = json.loads(receipt.detail)
        assert detail["counts"] == {
            "reviews": 1, "image_urls": 1, "menu": 1, "keywords": 2, "venture": 0,
        }
        assert detail["processing_purpose"] == "program-marketing-generation"
        assert detail["raw_input_retention"] == "request-only"
        assert detail["consents"] == {
            "process": True, "rights": True, "external_model": True,
        }
        assert detail["raw_input_persisted"] is False
        assert all(fragment not in receipt.detail for fragment in raw_fragments)


def test_commercial_onboarding_is_scoped_to_authenticated_org() -> None:
    key_a = _api_key(email="a@example.com", org_name="A상점")
    key_b = _api_key(email="b@example.com", org_name="B상점")

    a = client.post(
        "/api/v1/marketing/onboarding/generate",
        json=_body(), headers={"X-API-Key": key_a},
    ).json()
    b = client.post(
        "/api/v1/marketing/onboarding/generate",
        json=_body(), headers={"X-API-Key": key_b},
    ).json()
    assert a["org_id"] != b["org_id"]

    with _Session() as db:
        receipts = db.execute(
            select(AuditLog).where(AuditLog.action == AUDIT_ACTION)
        ).scalars().all()
        assert {receipt.org_id for receipt in receipts} == {a["org_id"], b["org_id"]}


def test_commercial_onboarding_accepts_jwt_as_well_as_api_key() -> None:
    signup = client.post("/api/v1/auth/signup", json={
        "org_name": "브라우저 점주",
        "email": "browser@example.com",
        "password": "merchant-password",
    })
    response = client.post(
        "/api/v1/marketing/onboarding/generate",
        json=_body(),
        headers={"Authorization": f"Bearer {signup.json()['access_token']}"},
    )
    assert response.status_code == 201
    assert response.json()["org_id"]
