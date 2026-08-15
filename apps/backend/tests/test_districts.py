"""거점 API 테스트 — 서울 54 Page 시드(app/data/seoul_pages.py) 기준.

공실 수치는 Gold 실측(data/gold/{slug}/page_building_master.geojson)이 있으면 실측,
없으면 합성 폴백이다 — 아래 Gold 배선 테스트는 파일 존재를 기준으로 기대값을 정한다.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data import seoul_pages
from app.data.seoul_pages import DISTRICTS
from app.main import app

client = TestClient(app)
V1 = "/api/v1"

# 시드 주석의 개·폐업률 검증 기준 — gold 점포수 가중 분기율(build_gold 의 opbiz_rt/clsbiz_rt)
GOLD_TIMESERIES = (Path(__file__).resolve().parents[3]
                   / "data" / "gold" / "platform13" / "platform_district_timeseries.parquet")
GOLD_QUARTER = "20252"  # 2025Q2 — 주석이 인용하는 분기

SEOUL_DISTRICT_IDS = {
    "garosugil", "apgujeong-rodeo", "hongdae", "yeonnam", "ikseon", "seochon",
    "myeongdong", "euljiro", "seongsu", "seoulsup", "itaewon", "hannam", "songridan",
    # 2026-07-22 Phase 1 자치구 미커버 상권 확장분
    "gangnam", "hapjeong", "mangwon", "samcheong", "gwangjang", "dongdaemun",
    # 2026-07-22 Phase 2 자치구 확장분 (용산은 itaewon/hannam 이 이미 커버)
    "jamsil", "konkuk", "yeouido", "mullae", "banpo", "sinchon", "yeonhui", "cheongnyangni",
    # 2026-07-24 Phase 3(관악·동작) + Phase 4(성북) 확장분
    "sharosugil", "nokdu", "sillim", "noryangjin", "sungshin", "anam",
    # 2026-07-24 Phase 1 자치구(강남) 내 미커버 상권 확장분
    "cheongdam", "dosan", "nonhyeon", "teheran", "seolleung",
    # 2026-07-24 Phase 1·2 자치구 내 미커버 상권 2차 확장분
    "yongsan", "namdaemun", "cityhall", "jamsilsaenae", "garak",
    # 2026-07-25 Phase 1·2 자치구 내 미커버 상권 3차 확장분
    "jangan", "gongdeok", "gunja", "chungmuro", "nambu", "kyunghee", "wangsimni",
    # 2026-07-25 Phase 1·2 자치구 내 미커버 상권 4차 확장분 (R-ONE 21분기 표본 소진)
    "sadang", "sukmyung", "hyehwa", "dangsan",
}

# 1~13번 초기 거점은 개·폐업률 주석 자체가 없다(Phase 1·2 확장분에만 병기).
# 여기에 주석을 추가하면 이 집합에서 빼야 gold 대조 대상에 들어간다.
IDS_WITHOUT_RATE_COMMENT = {
    "garosugil", "apgujeong-rodeo", "hongdae", "yeonnam", "ikseon", "seochon",
    "myeongdong", "euljiro", "seongsu", "seoulsup", "itaewon", "hannam", "songridan",
}


def test_list_districts():
    r = client.get(f"{V1}/commercial-districts")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == len(DISTRICTS) == 54
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


def test_building_vacancy_geojson():
    """건물 공실 GeoJSON(Page 폴리곤 레이어) — 실데이터/샘플/별칭/미지원 거점."""
    # garosugil: gold 산출물(839동) 또는 최소 샘플 8동 — 어느 쪽이든 유효한 FC
    r = client.get(f"{V1}/heatmap/buildings", params={"district": "garosugil"})
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert fc["district"] == "garosugil"
    assert fc["features"], "garosugil 건물 피처 없음"
    props = fc["features"][0]["properties"]
    for k in ("id", "name", "status", "capacity", "active", "industry", "vacancy_rate"):
        assert k in props, f"건물 속성 누락: {k}"
    assert props["status"] in {"full", "partial", "high", "empty"}

    # 별칭(gangnam-garosugil/sinsa)도 같은 거점으로 해석
    r2 = client.get(f"{V1}/heatmap/buildings", params={"district": "gangnam-garosugil"})
    assert r2.status_code == 200 and r2.json()["features"]

    # 미지원 거점 → 404
    assert client.get(f"{V1}/heatmap/buildings", params={"district": "nope"}).status_code == 404


def test_all_districts_have_heatmap_cells():
    """전 거점 그리드 셀이 비어 있지 않아야 한다 (Gold 실측·합성 폴백 무관)."""
    for d in DISTRICTS:
        r = client.get(f"{V1}/heatmap/vacancy", params={"district": d["id"]})
        assert r.status_code == 200, d["id"]
        hm = r.json()
        assert hm["cells"], f"{d['id']} 그리드 셀 없음"
        assert hm["sum_stores"] > 0, d["id"]


# ── Gold 실데이터 배선 (2026-08-01) ────────────────────────────────────────────
GOLD_DIR = Path(__file__).resolve().parents[3] / "data" / "gold"
# services/gold_vacancy 의 집계 규칙과 동일하게 유지 (분모 근거 · 집합 제외 · 분자 근거)
COUNTED_METHODS = {"floor_ouln"}
MALL_METHOD = "expos_units"
EXCLUDED_SOURCES = {"polygon_only"}


def _by_lot(props) -> dict:
    """지번(pnu) → 첫 폴리곤. 서비스의 지번 중복 제거와 같은 규칙(첫 등장 우선)."""
    out: dict = {}
    for p in props:
        out.setdefault(p.get("pnu") or p.get("id"), p)
    return out


def _counted(props: dict) -> bool:
    """대표 집계에 들어가는 건물인가 — gold_vacancy.build_cells 의 필터와 같은 조건."""
    return (props.get("capacity_method") in COUNTED_METHODS
            and bool(props.get("capacity"))
            and props.get("source") not in EXCLUDED_SOURCES)


@lru_cache(maxsize=None)
def _gold_master(slug: str):
    """거점 Gold 건물 마스터 로드 (없으면 None).

    캐시하는 이유: 54거점 마스터는 합계 수십 MB 이고 아래 테스트들이 거점마다 여러 번
    읽는다. 캐시 없이는 스위트가 분 단위로 늘어진다(2026-08-08 실측: 120초 초과).
    테스트 도중 Gold 를 다시 쓰지 않으므로 캐시가 낡을 일은 없다.
    """
    path = GOLD_DIR / slug / "page_building_master.geojson"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _gold_slugs() -> tuple[str, ...]:
    """대표 집계가 **실제로 산출되는** 거점 — 응답이 `vacancy_source="gold"` 가 되는 조건.

    2026-08-08 정정: 예전에는 `page_building_master.geojson` 존재만 봤다. 그때는 Gold 를
    가진 거점이 곧 대장 수집을 마친 13거점이라 파일 존재가 실측의 대리지표로 성립했다.
    Tier2(폴리곤근사) 41거점이 들어오면서 그 등식이 깨졌다 — 마스터는 있지만 전 건물이
    `floor_approx` 라 배제 규칙에 모두 걸려 `build_cells` 가 None 을 돌려주고, 응답은
    합성으로 폴백한다(파이프라인도 거점마다 "정밀 분모 건물 0동" 을 경고한다).
    파일 존재를 계속 기준으로 두면 그 거점들이 통째로 오탐이 된다(2026-08-15 현재
    실측 40 / 합성 14 — 대장 수집이 진행되며 계속 바뀌므로 헬퍼는 매번 다시 센다).

    아래 호출자 전부가 "앵커가 붙어 있다 · capacity>0 · 셀이 있다" 를 전제하므로,
    헬퍼 자체를 집계 가능 여부로 정의한다.
    """
    out: list[str] = []
    for d in DISTRICTS:
        fc = _gold_master(d["id"])
        if fc and any(_counted(f["properties"]) for f in fc["features"]):
            out.append(d["id"])
    return tuple(out)


def test_vacancy_source_matches_gold_presence():
    """대표 집계가 산출되는 거점만 실측("gold"), 나머지는 합성("synthetic")으로 표기돼야 한다.

    합성값이 실측처럼 읽히면 안 되므로 출처 표기는 두 엔드포인트에서 일치해야 한다.
    """
    gold = set(_gold_slugs())
    assert gold, "Gold 산출물이 하나도 없다 — data/pipelines/build_page_master.py 먼저 실행"

    for s in client.get(f"{V1}/commercial-districts").json():
        expected = "gold" if s["id"] in gold else "synthetic"
        assert s["vacancy_source"] == expected, f"{s['id']} 요약 출처 표기"
        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": s["id"]}).json()
        assert hm["vacancy_source"] == expected, f"{s['id']} 히트맵 출처 표기"


def test_tier2_master_does_not_claim_measured():
    """Tier2(대장 미수집) 거점은 Gold 마스터가 있어도 실측을 주장하면 안 된다.

    Tier2 는 폴리곤 지상층수 근사라 분모 근거가 `floor_approx` 뿐이다. 이걸 집계에
    넣으면 "실측" 배지를 달고 근거 없는 공실률이 나간다 — 실측처럼 보이는 추정치가
    가장 나쁜 산출물이라는 원칙(AGENTS.md §0)에 정면으로 걸린다.
    분모 규칙이 느슨해져 floor_approx 가 집계에 새어 들어오면 여기서 걸린다.
    """
    aggregatable = set(_gold_slugs())
    tier2 = [d["id"] for d in DISTRICTS
             if _gold_master(d["id"]) is not None and d["id"] not in aggregatable]
    if not tier2:
        pytest.skip("Tier2 거점 없음 — 전 거점이 대장 수집을 마쳤다면 정상")

    for slug in tier2:
        props = [f["properties"] for f in _gold_master(slug)["features"]]
        assert props, f"{slug}: 마스터가 비었다"
        assert not any(_counted(p) for p in props), f"{slug}: 집계 대상이 생겼는데 Tier2 로 분류됐다"
        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["vacancy_source"] == "synthetic", f"{slug}: 대장 없이 실측을 주장했다"


def test_gold_cells_are_internally_consistent():
    """Gold 거점의 셀 집계가 자기모순이 없어야 한다 — 합이 맞고 공실률이 분모와 정합."""
    for slug in _gold_slugs():
        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["capacity"] > 0 and hm["buildings"] > 0, slug
        assert hm["buildings"] <= hm["buildings_total"], slug

        cap = sum(c["capacity"] for c in hm["cells"])
        act = sum(c["stores"] for c in hm["cells"])
        bld = sum(c["buildings"] for c in hm["cells"])
        assert cap == hm["capacity"] and act == hm["sum_stores"] and bld == hm["buildings"], slug
        assert hm["sum_vac"] == cap - act, slug
        assert hm["avg_vacancy"] == pytest.approx((cap - act) / cap * 100, abs=0.01), slug
        # 공실 호실 수가 음수인 셀은 active > capacity 를 뜻한다(파이프라인 규칙 위반)
        assert all(c["vac_n"] >= 0 for c in hm["cells"]), slug


def test_gold_aggregate_excludes_weak_evidence():
    """거점 대표 공실률은 근거가 약한 건물을 뺀 표본만 집계해야 한다.

    - 분모: floor_approx(지상 전체 층수 근사)를 섞으면 과대추정 — 가로수길 전수 33.1% vs 24.2%.
    - 집합: expos_units 는 분자가 구조적으로 비어 공실률 78~86% 로 나온다.
    - 분자: polygon_only(점포 미매칭)는 active=0 이라 공실률 100% 로 고정된다.
    Gold 파일에서 직접 계산해 API 와 대조한다.
    """
    for slug in _gold_slugs():
        props = [f["properties"] for f in _gold_master(slug)["features"]]
        # 지번당 첫 폴리곤만 — 서비스와 같은 단위로 센다(모듈 gold_vacancy "집계 단위" 참조).
        counted = list(_by_lot(p for p in props if _counted(p)).values())
        cap = sum(p["capacity"] for p in counted)
        act = sum(min(p.get("active") or 0, p["capacity"]) for p in counted)

        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["buildings"] == len(counted), f"{slug} 집계 지번 수"
        assert hm["buildings_total"] == len(_by_lot(props)), f"{slug} 전체 지번 수"
        assert hm["polygons_total"] == len(props), f"{slug} 전체 폴리곤 수"
        assert hm["avg_vacancy"] == pytest.approx((cap - act) / cap * 100, abs=0.01), slug

        # 제외된 건물이 실제로 있어야 하고(현 산출물 기준), 전수 집계와 값이 달라야 한다.
        assert len(counted) < len(props), f"{slug} 제외 규칙이 아무것도 걸러내지 않았다"
        all_cap = sum(p.get("capacity") or 0 for p in props)
        all_act = sum(p.get("active") or 0 for p in props)
        assert hm["avg_vacancy"] != pytest.approx((all_cap - all_act) / all_cap * 100, abs=0.01), slug


def test_lot_polygons_counted_once():
    """한 지번에 폴리곤이 여럿이어도 집계에는 한 번만 들어가야 한다.

    마스터는 각 폴리곤에 **그 지번 전체의** active·capacity 를 물려준다. 그대로 합산하면
    그 지번이 폴리곤 수만큼 가중된다 — garak(가락시장)은 지번 1개가 폴리곤 225개라
    거점 공실률이 3.87% 대신 0.03% 로 나왔다(2026-08-08).
    """
    checked = 0
    for slug in _gold_slugs():
        props = [p for p in (f["properties"] for f in _gold_master(slug)["features"])
                 if _counted(p)]
        lots = _by_lot(props)
        if len(lots) == len(props):
            continue                                  # 이 거점에는 복수 폴리곤 지번이 없다
        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["buildings"] == len(lots), f"{slug}: 폴리곤을 세고 있다({len(props)} vs 지번 {len(lots)})"
        assert hm["capacity"] == sum(p["capacity"] for p in lots.values()), f"{slug} 분모"
        checked += 1
    assert checked, "복수 폴리곤 지번을 가진 Gold 거점이 없다 — 산출물 구조 확인"


def test_mall_buildings_never_counted():
    """집합건물(expos_units)은 집계에서 빠지고, 뺀 개수를 응답에 밝혀야 한다.

    분자가 구조적으로 비어 있다 — 상가정보가 대형 집합상가 내부 점포를 그 건물의
    bdMgtSn 으로 귀속시키지 못한다. 건물 수로는 소수인데 호실이 많아 분모의 52~82% 를
    차지하는 거점이 있어, 섞으면 거점 대표값이 무너진다(seoulsup 19.8% → 67.0%).
    """
    for slug in _gold_slugs():
        props = [f["properties"] for f in _gold_master(slug)["features"]]
        malls = [p for p in props if p.get("capacity_method") == MALL_METHOD]
        assert malls, f"{slug}: 집합건물이 하나도 없다 — 산출물 구조가 바뀌었는지 확인"
        assert not any(_counted(p) for p in malls), f"{slug}: 집합건물이 집계에 들어갔다"

        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["excluded_mall"] == len(malls), f"{slug} 집합 제외 건물 수"


def test_gold_anchor_comparison_attached():
    """Gold 거점은 R-ONE 앵커와 그 격차를 함께 내려보내야 한다.

    격차가 0 이 되는 것이 정상은 아니다(우리는 호실·전수, R-ONE 은 면적·표본).
    다만 부호와 크기가 비상식적이면 집계가 깨진 것이므로 느슨한 범위로 가둔다.
    """
    for slug in _gold_slugs():
        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["anchor_pct"] is not None, f"{slug}: calibration.json 없음 — calibrate_vacancy 실행 필요"
        assert 0 < hm["anchor_pct"] < 60, f"{slug} 앵커 범위"
        assert hm["anchor_gap_pp"] == pytest.approx(hm["avg_vacancy"] - hm["anchor_pct"], abs=0.01), slug
        # 집합건물을 섞던 시절 격차가 +63%p 까지 벌어졌다. 그 회귀를 막는 상한이다.
        assert -20 < hm["anchor_gap_pp"] < 30, f"{slug} 앵커 격차 이상 — 집계 규칙 회귀 의심"

        s = client.get(f"{V1}/commercial-districts/{slug}/summary").json()
        assert s["anchor_pct"] == hm["anchor_pct"] and s["anchor_gap_pp"] == hm["anchor_gap_pp"], slug


def test_polygon_only_never_counted():
    """polygon_only(점포 미매칭·공실률 100% 고정)는 집계에 들어가면 안 된다.

    현 산출물에서는 polygon_only 가 전부 floor_approx 라 분모 규칙만으로도 걸러지지만,
    두 규칙은 독립이라 재빌드가 조합을 바꿔도 배제되는지 여기서 못 박는다.
    """
    seen_polygon_only = False
    for slug in _gold_slugs():
        for p in (f["properties"] for f in _gold_master(slug)["features"]):
            if p.get("source") != "polygon_only":
                continue
            seen_polygon_only = True
            assert not _counted(p), f"{slug}: polygon_only 가 집계 대상에 들어갔다 — {p.get('id')}"
    assert seen_polygon_only, "polygon_only 건물이 하나도 없다 — 산출물 구조가 바뀌었는지 확인"


def test_gold_summary_and_heatmap_agree():
    """같은 거점의 요약·히트맵 공실 수치가 어긋나면 안 된다 (두 엔드포인트 동일 집계원)."""
    for slug in _gold_slugs():
        s = client.get(f"{V1}/commercial-districts/{slug}/summary").json()
        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert s["vacancy_rate"] == hm["avg_vacancy"], slug
        assert s["vacant_units"] == hm["sum_vac"], slug
        assert s["store_count"] == hm["sum_stores"], slug
        assert s["cell_count"] == len(hm["cells"]), slug
        assert s["building_count"] == hm["buildings"], slug


def test_gold_cells_may_extend_beyond_seed_bbox():
    """수집 반경이 시드 bb 를 벗어난 건물도 버리지 않아야 한다.

    셀 격자 원점·크기는 시드 grid 를 그대로 쓰되 인덱스는 bb 밖으로 나갈 수 있다
    (services/gold_vacancy 모듈 주석). 실제로 가로수길은 bb 서쪽 밖 건물이 있다.
    """
    grid = seoul_pages.DISTRICTS_BY_ID["garosugil"]["grid"]
    bb, dlat, dlng = grid["bb"], grid["dlat"], grid["dlng"]
    ni = int((bb["n"] - bb["s"]) / dlat)
    nj = int((bb["e"] - bb["w"]) / dlng)

    hm = client.get(f"{V1}/heatmap/vacancy", params={"district": "garosugil"}).json()
    outside = [c for c in hm["cells"] if not (0 <= c["i"] < ni and 0 <= c["j"] < nj)]
    assert outside, "bb 밖 셀이 하나도 없다 — 격자 확장이 동작하지 않거나 데이터가 바뀌었다"
    # 셀 좌표는 여전히 같은 격자 위에 정렬돼 있어야 한다
    for c in hm["cells"]:
        assert c["lat"] == pytest.approx(bb["s"] + c["i"] * dlat, abs=1e-6)
        assert c["lng"] == pytest.approx(bb["w"] + c["j"] * dlng, abs=1e-6)


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
    body = r.json()
    # 행사는 서울 문화행사 실데이터다 — 건수는 수집 시점에 따라 변하므로 고정하지 않는다.
    # 실데이터일 때 0건은 정상(그 거점에 예정 공공 문화행사가 없을 수 있다).
    assert body["events_source"] in {"seoul-open-data", "seed"}
    if body["events_source"] == "seed":
        assert len(body["events"]) == 3      # 시드 폴백은 거점당 3건 고정


def test_seed_comment_rates_match_gold():
    """시드 주석의 점포수·개폐업률이 gold 2025Q2 값과 일치해야 한다.

    주석 기준이 두 가지로 갈렸던 회귀 방지용(2026-07-23 재산출). 과거 14~19번 주석은
    analyze_district_signals.py 의 '0 제외 단순평균'이라 gold 가중값보다 3~8배 높았다.
    데이터 레이어(pandas·parquet)가 없는 환경에서는 건너뛴다.
    """
    pd = pytest.importorskip("pandas", reason="데이터 레이어 미설치 — gold 대조 생략")
    if not GOLD_TIMESERIES.exists():
        pytest.skip(f"gold 산출물 없음: {GOLD_TIMESERIES}")

    df = pd.read_parquet(GOLD_TIMESERIES)
    rows = df[df["quarter"].astype(str) == GOLD_QUARTER]
    gold = {r.district_id: (r.clsbiz_rt, r.opbiz_rt, int(r.stor_co)) for r in rows.itertuples()}

    src = Path(seoul_pages.__file__).read_text(encoding="utf-8")
    # 거점 블록 단위로 잘라 주석 수치를 해당 거점 gold 와 대조
    blocks = re.split(r'\n(?=\{"id": )', src)
    covered: set[str] = set()
    for block in blocks:
        m = re.match(r'\{"id": "([a-z0-9-]+)"', block)
        if not m:
            continue  # 모듈 헤더(재산출 이력에 옛 수치를 인용)는 대조 대상이 아니다
        did = m.group(1)
        assert did in gold, f"{did}: gold {GOLD_QUARTER} 행 없음 — 신규 거점은 gold 재빌드 필요"
        gold_cls, gold_op, gold_stor = gold[did]

        for cls, op in re.findall(r"폐업률 ([\d.]+)% (?:vs |· )개업률 ([\d.]+)%", block):
            assert float(cls) == pytest.approx(gold_cls, abs=0.005), f"{did} 폐업률 주석"
            assert float(op) == pytest.approx(gold_op, abs=0.005), f"{did} 개업률 주석"
            covered.add(did)
        for stor in re.findall(r"점포 ([\d,]+) ", block):
            assert int(stor.replace(",", "")) == gold_stor, f"{did} 점포수 주석"
            covered.add(did)

    # 정규식이 조용히 빗나가면 0건 통과가 되므로 커버리지 하한을 둔다. 건수가 아니라 거점 수로
    # 세는 이유: 한 거점의 주석 줄이 늘거나 줄 때마다(예 samcheong 재보정) 매직넘버를 고쳐야 하는
    # 반면, "주석을 가진 거점은 모두 대조됐다"는 불변식은 형식 변경에 흔들리지 않는다.
    # 현재 개·폐업률 주석은 14~54번 41거점에만 있다(1~13번은 원래 없음 — 모듈 상단 ⚠️ 참조).
    expected = {d["id"] for d in DISTRICTS} - IDS_WITHOUT_RATE_COMMENT
    assert covered == expected, f"주석 대조 누락/초과: {covered ^ expected}"


def test_unknown_district_404():
    assert client.get(f"{V1}/commercial-districts/nope/summary").status_code == 404
    assert client.get(f"{V1}/heatmap/vacancy", params={"district": "nope"}).status_code == 404
