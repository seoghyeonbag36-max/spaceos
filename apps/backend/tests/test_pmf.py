"""PMF 계측 잠금 — KPI③ 의 `NPS 30+` · `유료 전환 의향 30%+`.

2026-09-16 이전에는 이 두 목표를 담을 표도 계산기도 없었다. `usage.record_access` 가
세던 것은 `active_orgs`(파일럿이 살아 있나) 하나뿐이다.

잠그는 것은 숫자가 아니라 성질이다:
1. **익명은 못 낸다** — 공개 데모 만족도가 B2B PMF 로 둔갑하지 않게.
2. **표본 단위는 조직** — 한 조직이 열 번 답해도 한 표다.
3. **표본이 적으면 판정하지 않는다**(KPI 규칙 2).
4. **NPS 는 표준 정의** — 추천자% − 비추천자%. 평균 점수로 바꾸면 벤치마크가 끊긴다.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.services import pmf

V1 = "/api/v1"

_engine = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
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
    return client.post(f"{V1}/auth/signup", json={
        "org_name": org_name, "email": email, "password": "hunter2hunter"}).json()


def _auth(email, org_name="Acme"):
    return {"Authorization": f"Bearer {_signup(email, org_name)['access_token']}"}


def _send(headers, score, pay="yes"):
    return client.post(f"{V1}/feedback",
                       json={"nps_score": score, "would_pay": pay}, headers=headers)


@pytest.fixture()
def admin(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    return {"X-Admin-Token": "t"}


def _summary(admin):
    return client.get(f"{V1}/admin/pmf", headers=admin).json()


# ── 입력 계약 ───────────────────────────────────────────────────────────────

def test_anonymous_cannot_submit_feedback() -> None:
    """**핵심 잠금.** 익명 응답을 받으면 공개 데모 만족도가 PMF 로 둔갑한다."""
    r = client.post(f"{V1}/feedback", json={"nps_score": 10, "would_pay": "yes"})
    assert r.status_code in (401, 403), r.status_code


def test_score_outside_the_nps_scale_is_rejected() -> None:
    h = _auth("a@a.com")
    assert _send(h, 11).status_code == 422
    assert _send(h, -1).status_code == 422


def test_would_pay_is_a_closed_set() -> None:
    h = _auth("b@b.com")
    assert client.post(f"{V1}/feedback",
                       json={"nps_score": 9, "would_pay": "아마도"}, headers=h).status_code == 422


def test_submission_is_stored_and_echoed() -> None:
    h = _auth("c@c.com")
    r = _send(h, 9)
    assert r.status_code == 201
    body = r.json()
    assert body["nps_score"] == 9 and body["would_pay"] == "yes" and body["org_id"]


# ── 계산 ────────────────────────────────────────────────────────────────────

def test_nps_follows_the_standard_definition(admin) -> None:
    """추천자% − 비추천자%. 중립(7~8)은 분모에만 들어간다."""
    for i, score in enumerate([10, 9, 8, 6, 0]):          # 추천 2 · 중립 1 · 비추천 2
        _send(_auth(f"n{i}@x.com", org_name=f"O{i}"), score)
    s = _summary(admin)
    assert s["promoters"] == 2 and s["passives"] == 1 and s["detractors"] == 2
    assert s["nps"] == pytest.approx(0.0)                  # (2-2)/5 * 100


def test_sample_unit_is_the_org_not_the_response(admin) -> None:
    """한 조직이 여러 번 답해도 한 표다 — 최신 것만 센다."""
    h = _auth("rep@x.com")
    _send(h, 0)
    _send(h, 10)                                           # 마음이 바뀌었다
    s = _summary(admin)
    assert s["n_orgs"] == 1
    assert s["promoters"] == 1 and s["detractors"] == 0, "옛 응답이 아직 세어진다"


def test_small_sample_is_not_judged(admin) -> None:
    """파일럿 목표가 5~10건이라 n 은 애초에 작다 — 적으면 판정하지 않는다."""
    for i in range(pmf.MIN_RESPONSES - 1):
        _send(_auth(f"s{i}@x.com", org_name=f"S{i}"), 10)
    s = _summary(admin)
    assert s["n_orgs"] < pmf.MIN_RESPONSES
    assert s["verdict"] == "표본부족", "표본이 적은데 달성으로 찍었다"


def test_verdict_appears_with_enough_responses(admin) -> None:
    for i in range(pmf.MIN_RESPONSES):
        _send(_auth(f"e{i}@x.com", org_name=f"E{i}"), 10, pay="yes")
    s = _summary(admin)
    assert s["n_orgs"] == pmf.MIN_RESPONSES
    assert s["nps"] == 100.0 and s["would_pay_pct"] == 100.0
    assert s["verdict"] == "충족"


def test_high_nps_with_low_pay_intent_is_not_enough(admin) -> None:
    """두 목표를 **함께** 넘겨야 한다 — 좋아하는 것과 돈을 내는 것은 다르다."""
    for i in range(pmf.MIN_RESPONSES):
        _send(_auth(f"p{i}@x.com", org_name=f"P{i}"), 10, pay="maybe")
    s = _summary(admin)
    assert s["nps"] == 100.0 and s["would_pay_pct"] == 0.0
    assert s["verdict"] == "미달"


def test_swing_shows_how_fragile_a_small_sample_is(admin) -> None:
    """n 이 작을 때 한 응답이 NPS 를 몇 포인트 흔드는지 드러내야 한다."""
    for i in range(5):
        _send(_auth(f"w{i}@x.com", org_name=f"W{i}"), 10)
    assert _summary(admin)["one_response_swing_nps"] == pytest.approx(40.0)


# ── 관측 창구 ───────────────────────────────────────────────────────────────

def test_pmf_endpoint_requires_admin_token() -> None:
    import os
    os.environ.pop("ADMIN_TOKEN", None)
    assert client.get(f"{V1}/admin/pmf").status_code == 403


def test_empty_state_says_wiring_is_not_evidence(admin) -> None:
    """응답 0건에서 '배선 100% 는 파일럿 0건과 양립한다'가 드러나야 한다."""
    s = _summary(admin)
    assert s["n_orgs"] == 0 and s["nps"] is None
    assert s["verdict"] == "표본부족"
    assert "파일럿 0건" in s["note"]
