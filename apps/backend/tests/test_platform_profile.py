"""Platform 정체성·자리 제안 API 테스트 — GET /commercial-districts/{id}/platform.

이 엔드포인트가 답하는 것은 두 가지다: "이 상권은 어떤 플랫폼인가"와
"어느 자리에 어떤 업소가 들어오면 좋은가". 테스트도 그 둘을 센다.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import marketing, platform_profile, vacant_inventory
from tests.test_districts import SEOUL_DISTRICT_IDS

client = TestClient(app)
V1 = "/api/v1"


def test_platform_profile_all_districts_have_identity_and_sites():
    """54/54거점이 정체성과 자리를 둘 다 갖는다 — 한쪽만 있으면 화면 절반이 빈다."""
    for did in SEOUL_DISTRICT_IDS:
        r = client.get(f"{V1}/commercial-districts/{did}/platform")
        assert r.status_code == 200, did
        body = r.json()
        assert body["identity"] is not None, did
        assert body["identity"]["archetype"], did
        assert body["openings"]["sites"], did


def test_unknown_district_404():
    assert client.get(f"{V1}/commercial-districts/nope/platform").status_code == 404


def test_archetype_follows_the_stated_rule():
    """유형 라벨은 규칙대로 나와야 한다 — 화면에 규칙을 적어 두고 다른 값을 내면 안 된다."""
    for did in SEOUL_DISTRICT_IDS:
        ident = client.get(f"{V1}/commercial-districts/{did}/platform").json()["identity"]
        groups = ident["categories"]["groups"]
        top = groups[0]
        if top["share"] >= platform_profile._DOMINANT_SHARE or len(groups) == 1:
            assert ident["archetype"] == f"{top['group']} 중심형", did
        else:
            assert ident["archetype"] == f"{top['group']}·{groups[1]['group']} 복합형", did


def test_category_grouping_loses_nothing():
    """군 합계 + 미분류 == 원본 합계. 묶는 과정에서 점포가 사라지면 비중이 거짓이 된다."""
    for did in SEOUL_DISTRICT_IDS:
        cats = client.get(f"{V1}/commercial-districts/{did}/platform").json()["identity"]["categories"]
        grouped = sum(g["n"] for g in cats["groups"])
        ungrouped = sum(u["n"] for u in cats["ungrouped"])
        # 각 라벨 값은 정수(카운트)라 반올림 오차가 없다
        assert grouped + ungrouped == cats["total"], did
        # 미분류를 숨기지 않는다 — 분류 규칙이 놓친 라벨은 화면에 그대로 나온다
        for g in cats["groups"]:
            assert sum(m["n"] for m in g["members"]) == g["n"], (did, g["group"])


def test_display_stopwords_are_disclosed_not_hidden():
    """표시용 불용어를 걸렀으면 **몇 개 걸렀는지** 응답이 밝혀야 한다."""
    ident = client.get(f"{V1}/commercial-districts/garosugil/platform").json()["identity"]
    kw = ident["keywords"]
    raw = [k for kd, k, _ in marketing.context_rows("garosugil") if kd == "blog_keyword"]
    assert kw["scanned"] == len(raw)
    assert kw["dropped"] == len([k for k in raw if k in platform_profile._DISPLAY_STOP])
    assert kw["dropped"] > 0, "이 거점은 실제로 일반어가 남아 있어 0 이면 필터가 죽은 것이다"
    words = {w["word"] for w in kw["words"]}
    assert not (words & platform_profile._DISPLAY_STOP)
    # 지역·업종 어휘는 절대 걸러지면 안 된다(그 자체가 정체성 신호다)
    assert not ({"신사", "디저트", "감성", "카페"} & platform_profile._DISPLAY_STOP)


def test_trend_direction_matches_marketing_summary():
    """같은 계열을 두고 Platform 과 Program 이 다른 방향을 말하면 안 된다."""
    label = {"up": "상승", "down": "하락", "flat": "보합"}
    for did in ("garosugil", "hongdae", "seongsu"):
        ident = client.get(f"{V1}/commercial-districts/{did}/platform").json()["identity"]
        rows = marketing.context_rows(did)
        series: dict[str, list[tuple[str, float]]] = {}
        for kd, k, v in rows:
            if kd.startswith("trend:"):
                series.setdefault(kd.split(":", 1)[1], []).append((k, v))
        for t in ident["trends"]:
            summary = marketing._trend_summary(t["keyword"], series[t["keyword"]])
            assert summary is not None
            assert label[t["direction"]] in summary, (did, t["keyword"], summary)


def test_sites_come_from_the_measured_vacancy_inventory():
    """자리는 실측 공실 인벤토리 그대로여야 한다 — 화면용으로 새로 만들지 않는다."""
    for did in ("garosugil", "hongdae", "seongsu"):
        body = client.get(f"{V1}/commercial-districts/{did}/platform").json()
        units = vacant_inventory.units(did)
        sites = body["openings"]["sites"]
        assert body["openings"]["unit_count"] == len(units), did
        assert {s["unit_id"] for s in sites} <= {u["id"] for u in units}, did


def test_site_recommendation_is_from_a_nearby_node_or_absent():
    """추천이 붙었으면 400m 안 노드에서 온 것이어야 한다.

    멀리 있는 노드나 거점 평균으로 자리를 채우면, 그 자리의 답이 아닌 값이
    그 자리의 답처럼 읽힌다.
    """
    radius = platform_profile.industry_recommend._MAX_MATCH_M
    for did in SEOUL_DISTRICT_IDS:
        body = client.get(f"{V1}/commercial-districts/{did}/platform").json()
        for s in body["openings"]["sites"]:
            if s["recommendations"]:
                assert s["matched_distance_m"] is not None, (did, s["unit_id"])
                assert s["matched_distance_m"] <= radius, (did, s["unit_id"])
                assert 0 < s["recommendations"][0]["score"] <= 1
            else:
                assert s["matched_distance_m"] is None, (did, s["unit_id"])


def test_distinct_is_the_site_signal_minus_the_district_average():
    """자리마다 '상권 평균 대비 두드러지는 업종'이 붙고, 그 값이 실제 최대여야 한다.

    이게 없으면 사전확률에 눌려 모든 자리가 같은 답("음식점")을 내고, 화면이
    "어느 자리에 무엇"이 아니라 "모든 자리에 같은 것"이 된다.
    """
    for did in ("garosugil", "hongdae", "seongsu"):
        body = client.get(f"{V1}/commercial-districts/{did}/platform").json()
        means = platform_profile._district_means(did)
        assert means, did
        for s in body["openings"]["sites"]:
            if not s["recommendations"]:
                assert s["distinct"] is None, (did, s["unit_id"])
                continue
            d = s["distinct"]
            assert d is not None, (did, s["unit_id"])
            # 추천 안에 있는 업종이어야 한다 — 없는 업종을 지목하면 근거가 없다
            assert d["industry"] in {r["industry"] for r in s["recommendations"]}
            best = max(r["score"] - means.get(r["industry"], 0.0) for r in s["recommendations"])
            assert abs(d["delta_pp"] - round(best * 100, 1)) < 0.05, (did, s["unit_id"])


def test_sites_are_ordered_by_distinctness_not_raw_confidence():
    """가장 두드러지는 자리부터 나와야 한다 — 1위 확률 순은 사전확률 순이라 정보가 없다."""
    sites = client.get(f"{V1}/commercial-districts/garosugil/platform").json()["openings"]["sites"]
    deltas = [s["distinct"]["delta_pp"] for s in sites if s["distinct"]]
    assert deltas == sorted(deltas, reverse=True)


def test_sentiment_is_not_part_of_the_identity():
    """감성은 전부 시드다 — 정체성 근거에 섞이면 지어낸 성격을 상권에 붙이게 된다."""
    body = client.get(f"{V1}/commercial-districts/garosugil/platform").json()
    assert "sentiment" not in body["identity"]
    assert "zones" not in body["identity"]
