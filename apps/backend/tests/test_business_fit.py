"""내 업종으로 본 상권(화면설계서 3판) — 창업자·업종 바꾸기·상권 옮기기 사업자용 비교.

이 그물이 잡는 회귀:
  - 모델 7종 밖 업종에 **순위나 적합도가 지어져** 나가는 것(가까운 업종 점수로 채우기)
  - 순위가 적합도 순이 아니거나, 적합도 없는 상권이 0 으로 순위에 섞이는 것
  - 업종 key 가 바뀌어 브라우저에 저장된 「내 사업」이 조용히 깨지는 것
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import business_fit

client = TestClient(app)


def test_industry_list_is_the_stable_twelve():
    body = client.get("/api/v1/ai/industries").json()
    keys = [i["key"] for i in body["industries"]]
    # key 는 저장값이다 — 바꾸거나 지우면 이미 설정한 사용자의 「내 사업」이 사라진다.
    assert keys == ["cafe", "restaurant", "bar", "beauty", "clinic", "pharmacy",
                    "convenience", "fashion", "education", "fitness", "lodging", "culture"]
    labels = {i["model_label"] for i in body["industries"]} - {None}
    assert labels == {"카페", "음식점", "병원", "약국", "편의점", "숙박", "문화시설"}
    # 규칙(needles)은 응답에 싣지 않는다
    assert all(set(i) == {"key", "label", "input", "model_label"} for i in body["industries"])


def test_fit_ranks_districts_by_model_fit():
    resp = client.get("/api/v1/ai/industry-fit", params={"industry": "cafe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_covered"] is True
    ranked = [d for d in body["districts"] if d["fit_rank"] is not None]
    assert ranked, "카페는 모델 7종 안이라 순위가 있어야 한다"
    assert body["ranked_n"] == len(ranked)
    assert [d["fit_rank"] for d in ranked] == list(range(1, len(ranked) + 1))
    fits = [d["fit"] for d in ranked]
    assert fits == sorted(fits, reverse=True)
    # 순위 없는 상권은 순위 있는 상권 뒤에만 온다(0 으로 섞이지 않는다)
    first_unranked = next((i for i, d in enumerate(body["districts"]) if d["fit_rank"] is None), None)
    if first_unranked is not None:
        assert all(d["fit_rank"] is None for d in body["districts"][first_unranked:])
    assert 0 < body["seoul_fit"] < 1
    assert "매출·생존율이 아니다" in body["note"]


def test_fit_rows_carry_sample_share_and_rent_without_vacancy():
    body = client.get("/api/v1/ai/industry-fit", params={"industry": "cafe"}).json()
    row = next(d for d in body["districts"] if d["same_n"] is not None)
    assert row["sample_n"] >= row["same_n"] >= 0
    assert abs(row["same_share"] - row["same_n"] / row["sample_n"]) < 1e-3
    # 공실률은 화면이 상권 목록에서 합친다 — 두 엔드포인트가 같은 값을 따로 만들지 않는다
    assert "vacancy_rate" not in row


def test_uncovered_industry_gets_no_rank_or_fit():
    body = client.get("/api/v1/ai/industry-fit", params={"industry": "bar"}).json()
    assert body["model_covered"] is False
    assert body["seoul_fit"] is None
    assert body["ranked_n"] == 0
    assert all(d["fit"] is None and d["fit_rank"] is None for d in body["districts"])
    # 순위가 없으면 가나다순 — 어떤 기준으로도 줄 세운 것처럼 보이지 않게
    names = [d["name"] for d in body["districts"]]
    assert names == sorted(names)
    # 같은 업종 비중은 그대로 준다
    assert any((d["same_n"] or 0) > 0 for d in body["districts"])


def test_district_industries_ranks_covered_first_and_marks_uncovered():
    resp = client.get("/api/v1/ai/district-industries/yeonnam")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == len(business_fit.INDUSTRIES)
    covered = [r for r in rows if r["model_label"]]
    assert [r["fit_rank"] for r in covered] == list(range(1, len(covered) + 1))
    assert [r["fit"] for r in covered] == sorted((r["fit"] for r in covered), reverse=True)
    uncovered = rows[len(covered):]
    assert uncovered and all(r["model_label"] is None and r["fit"] is None for r in uncovered)


def test_unknown_industry_and_district_are_404():
    assert client.get("/api/v1/ai/industry-fit", params={"industry": "nope"}).status_code == 404
    assert client.get("/api/v1/ai/district-industries/nowhere").status_code == 404


def test_same_counts_follow_needles(monkeypatch):
    rows = [("category", "카페", 22.0), ("category", "커피전문점", 10.0), ("category", "호프,요리주점", 5.0),
            ("category", "성형외과", 18.0), ("category", "CU", 3.0), ("demand", "stor_co", 100.0)]
    monkeypatch.setattr(business_fit.marketing, "context_rows", lambda _id: rows)
    counts, total = business_fit._same_counts("any")
    assert total == 58
    assert counts["cafe"] == 32 and counts["bar"] == 5 and counts["clinic"] == 18
    assert counts["convenience"] == 3 and counts["beauty"] == 0
