"""거점 API 테스트 — 서울 27 Page 시드(app/data/seoul_pages.py) 기준."""
from fastapi.testclient import TestClient

from app.data.seoul_pages import DISTRICTS
from app.main import app

client = TestClient(app)
V1 = "/api/v1"

SEOUL_DISTRICT_IDS = {
    "garosugil", "apgujeong-rodeo", "hongdae", "yeonnam", "ikseon", "seochon",
    "myeongdong", "euljiro", "seongsu", "seoulsup", "itaewon", "hannam", "songridan",
    # 2026-07-22 Phase 1 자치구 미커버 상권 확장분
    "gangnam", "hapjeong", "mangwon", "samcheong", "gwangjang", "dongdaemun",
    # 2026-07-22 Phase 2 자치구 확장분 (용산은 itaewon/hannam 이 이미 커버)
    "jamsil", "konkuk", "yeouido", "mullae", "banpo", "sinchon", "yeonhui", "cheongnyangni",
}


def test_list_districts():
    r = client.get(f"{V1}/commercial-districts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == len(DISTRICTS) == 27
    assert {d["id"] for d in data} == SEOUL_DISTRICT_IDS
    for d in data:
        assert 0 <= d["sentiment"] <= 100
        assert 0 <= d["vacancy_rate"] <= 100
        assert d["tier_mix"]["premium"] + d["tier_mix"]["value"] + d["tier_mix"]["factory"] == 5


def test_district_summary_and_detail():
    r = client.get(f"{V1}/commercial-districts/garosugil/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "신사동 가로수길"
    assert body["gu"] == "강남구"

    r = client.get(f"{V1}/commercial-districts/garosugil")
    assert r.status_code == 200
    assert len(r.json()["zones"]) == 6
    assert len(r.json()["units"]) == 5


def test_sentiment_and_heatmap():
    r = client.get(f"{V1}/commercial-districts/seongsu/sentiment")
    assert r.status_code == 200 and len(r.json()) == 6

    r = client.get(f"{V1}/heatmap/vacancy", params={"district": "seongsu"})
    assert r.status_code == 200
    hm = r.json()
    assert hm["resolution_m"] == 100
    assert hm["cells"] and hm["sum_stores"] > 0


def test_all_districts_have_heatmap_cells():
    """전 거점 그리드 합성 셀이 비어 있지 않아야 한다 (hot 스팟 정합 검증)."""
    for d in DISTRICTS:
        r = client.get(f"{V1}/heatmap/vacancy", params={"district": d["id"]})
        assert r.status_code == 200, d["id"]
        hm = r.json()
        assert hm["cells"], f"{d['id']} 그리드 셀 없음"
        assert hm["sum_stores"] > 0, d["id"]


def test_postings_and_marketing():
    r = client.get(f"{V1}/commercial-districts/hongdae/postings")
    assert r.status_code == 200
    postings = r.json()
    assert len(postings) == 5
    sc = postings[0]["scenarios"]
    assert set(sc.keys()) == {"premium", "value", "factory"}
    assert any(v["recommended"] for v in sc.values())

    r = client.get(f"{V1}/marketing/hongdae")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 3


def test_unknown_district_404():
    assert client.get(f"{V1}/commercial-districts/nope/summary").status_code == 404
    assert client.get(f"{V1}/heatmap/vacancy", params={"district": "nope"}).status_code == 404
