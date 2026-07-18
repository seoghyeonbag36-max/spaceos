"""Posting(코파일럿 어댑터) / Program(가게 단위 생성) API 테스트."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
V1 = "/api/v1"


def test_simulate_revenue_fallback():
    """코파일럿 미설정 시 3-Tier 폴백으로 응답한다 (서울 13 Page 시드)."""
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "garosugil"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback-3tier"
    assert set(body["scenarios"].keys()) == {"premium", "value", "factory"}
    for sc in body["scenarios"].values():
        assert sc["roi_months"] >= 0  # round(invest/net,1)이 0.0일 수 있음(순이익 대비 소액 투자)


def test_simulate_revenue_strategy_filter():
    r = client.post(f"{V1}/ai/simulate-revenue",
                    json={"district_id": "garosugil", "strategy": "value"})
    assert r.status_code == 200
    assert set(r.json()["scenarios"].keys()) == {"value"}


def test_simulate_revenue_unknown_district_404():
    r = client.post(f"{V1}/ai/simulate-revenue", json={"district_id": "nope"})
    assert r.status_code == 404


def test_generate_store_marketing_stub(monkeypatch):
    """LLM 키 미설정 시 규칙 기반 스텁이 StoreMarketing 스키마로 응답한다."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")
    profile = {
        "name": "가로수 카페",
        "category": "카페",
        "district_id": "gangnam-garosugil",
        "reviews": ["분위기 좋은 카페", "커피 맛집 분위기 최고", "디저트 맛집"],
    }
    r = client.post(f"{V1}/marketing/generate", json=profile)
    assert r.status_code == 200
    body = r.json()
    assert body["store_name"] == "가로수 카페"
    assert body["source"] == "rule-stub"
    assert body["tone_keywords"]  # 리뷰에서 키워드 추출됨
    assert len(body["online"]) >= 1 and len(body["offline"]) >= 1
    assert all(p["kind"] == "online" for p in body["online"])
    assert all(p["kind"] == "offline" for p in body["offline"])


_PROFILE = {
    "name": "맡기다",
    "category": "F&B",
    "district_id": "hongdae-yeonnam",
    "reviews": ["사장님 손맛이 담긴 특제 소스", "우니 사시미가 인상적"],
}


def test_generate_store_marketing_llm(monkeypatch):
    """LLM 키 설정 시 _call_llm 결과가 StoreMarketing(source=llm)으로 매핑된다."""
    from app.core.config import settings
    from app.schemas.marketing import LLMChannelPlan, LLMStoreMarketing
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    fake = LLMStoreMarketing(
        tone_keywords=["특제소스", "사시미"],
        online=[LLMChannelPlan(channel="인스타그램", content="릴스 게시", rationale="리뷰 근거")],
        offline=[LLMChannelPlan(channel="전단", content="시식 이벤트", rationale="유동객 근거")],
        ha_check="균형·공생·공감 점검 통과",
    )
    monkeypatch.setattr(mkt, "_call_llm", lambda profile, tone, ctx: fake)

    r = client.post(f"{V1}/marketing/generate", json=_PROFILE)
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "llm"
    assert body["tone_keywords"] == ["특제소스", "사시미"]
    assert body["online"][0]["kind"] == "online"
    assert body["offline"][0]["kind"] == "offline"


def test_generate_store_marketing_llm_error_falls_back(monkeypatch):
    """LLM 호출 실패 시 규칙 기반 스텁으로 폴백한다 (요청은 200 유지)."""
    from app.core.config import settings
    from app.services import marketing as mkt

    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    def boom(profile, tone, ctx):
        raise RuntimeError("api down")

    monkeypatch.setattr(mkt, "_call_llm", boom)

    r = client.post(f"{V1}/marketing/generate", json=_PROFILE)
    assert r.status_code == 200
    assert r.json()["source"] == "rule-stub"


def test_district_context_mapping():
    """gold 매핑에 있는 거점은 컨텍스트 문자열, 없는 거점은 None."""
    from app.services import marketing as mkt

    assert mkt._district_context("unknown-district") is None
    ctx = mkt._district_context("garosugil")
    # gold 적재 여부에 따라 None 또는 요약 문자열 — 적재된 경우 키워드 포함 검증
    if ctx is not None:
        assert "키워드" in ctx or "업종" in ctx or "트렌드" in ctx


def test_district_marketing_served():
    """상권 단위 GET /marketing/{id} — 서울 13 Page 시드 반환 (Gold 교체 TODO)."""
    r = client.get(f"{V1}/marketing/garosugil")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 3

    assert client.get(f"{V1}/marketing/nope").status_code == 404
