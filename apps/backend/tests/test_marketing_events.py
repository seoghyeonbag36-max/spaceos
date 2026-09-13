"""GET /marketing/events — Program 지도가 쓰는 **LLM 없는** 행사 조회(2026-09-13).

`/marketing/{id}` 는 행사와 함께 온라인 콘텐츠를 LLM 으로 만든다. 지도를 볼 때마다
그걸 부르면 크레딧을 쓰므로 행사만 떼어 냈다. 여기서 못 박는 것:
  1. LLM 경로를 타지 않는다(키가 있어도)
  2. 출처 규칙이 `/marketing/{id}` 와 같다(events_source)
  3. `/{district_id}` 캐치올 라우트에 먹히지 않는다(선언 순서)
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import marketing as mkt

client = TestClient(app)
V1 = "/api/v1"


def test_events_route_does_not_call_llm(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("행사 조회가 LLM 을 불렀다")

    monkeypatch.setattr(mkt.settings, "llm_api_key", "sk-test", raising=False)
    monkeypatch.setattr(mkt, "_call_district_llm", boom)
    r = client.get(f"{V1}/marketing/events", params={"district_id": "garosugil"})
    assert r.status_code == 200
    body = r.json()
    assert body["district_id"] == "garosugil"
    assert body["events_source"] in ("seoul-open-data", "seed")
    assert isinstance(body["events"], list)
    assert "online_contents" not in body


def test_events_match_full_marketing_events(monkeypatch):
    """행사 목록·출처가 `/marketing/{id}` 와 같다 — LLM 부분만 빠진다."""
    monkeypatch.setattr(mkt.settings, "llm_api_key", "", raising=False)
    events = client.get(f"{V1}/marketing/events", params={"district_id": "garosugil"}).json()
    full = client.get(f"{V1}/marketing/garosugil").json()
    assert events["events_source"] == full["events_source"]
    assert [e["id"] for e in events["events"]] == [e["id"] for e in full["events"]]


def test_unknown_district_is_404_not_catchall():
    r = client.get(f"{V1}/marketing/events", params={"district_id": "no-such-hub"})
    assert r.status_code == 404
