"""거점 API 테스트."""
from fastapi.testclient import TestClient

from app.main import app
from app.data.goyang_districts import DISTRICTS

client = TestClient(app)
V1 = "/api/v1"


def test_list_districts():
    r = client.get(f"{V1}/commercial-districts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == len(DISTRICTS) == 39
    ids = {d["id"] for d in data}
    assert {"lafesta", "starfield", "hwajeong", "bamridan", "baekseok",
            "haengsin", "juyeop", "deokyang", "madu",
            "tanhyeon", "gajwa", "kintexone", "pungdong", "jungsan",
            "hyangdong", "jichuk", "neunggok", "deokeun", "haengju", "hwajeon"} <= ids
    for d in data:
        assert 0 <= d["sentiment"] <= 100
        assert 0 <= d["vacancy_rate"] <= 100
        assert d["tier_mix"]["premium"] + d["tier_mix"]["value"] + d["tier_mix"]["factory"] == 5


def test_district_summary_and_detail():
    r = client.get(f"{V1}/commercial-districts/lafesta/summary")
    assert r.status_code == 200
    assert r.json()["name"].startswith("일산 라페스타")

    r = client.get(f"{V1}/commercial-districts/lafesta")
    assert r.status_code == 200
    assert len(r.json()["zones"]) == 6
    assert len(r.json()["units"]) == 5


def test_sentiment_and_heatmap():
    r = client.get(f"{V1}/commercial-districts/hwajeong/sentiment")
    assert r.status_code == 200 and len(r.json()) == 6

    r = client.get(f"{V1}/heatmap/vacancy", params={"district": "hwajeong"})
    assert r.status_code == 200
    hm = r.json()
    assert hm["resolution_m"] == 100
    assert hm["cells"] and hm["sum_stores"] > 0


def test_postings_and_marketing():
    r = client.get(f"{V1}/commercial-districts/starfield/postings")
    assert r.status_code == 200
    postings = r.json()
    assert len(postings) == 5
    sc = postings[0]["scenarios"]
    assert set(sc.keys()) == {"premium", "value", "factory"}
    assert any(v["recommended"] for v in sc.values())

    r = client.get(f"{V1}/marketing/starfield")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 3


def test_unknown_district_404():
    assert client.get(f"{V1}/commercial-districts/nope/summary").status_code == 404
    assert client.get(f"{V1}/heatmap/vacancy", params={"district": "nope"}).status_code == 404
