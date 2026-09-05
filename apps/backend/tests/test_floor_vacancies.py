"""[Page] 층 단위 공실 매물 목록 API — `/commercial-districts/{id}/floor-vacancies`.

이 엔드포인트가 지켜야 할 것은 "무엇을 세는가"가 `/postings` 와 **갈라져 있다**는
것이다. 둘이 조용히 같아지면 §0-Q 가 되돌린 자리로 돌아간다: 층으로 쪼갠 표본이
ROI 계산에 들어가면 프라임 프리미엄 트립와이어가 부호를 넘는다.

고정하는 것:
  1. 두 목록은 **다른 파일**을 읽고, 층 목록에는 `partial` 건물이 들어온다
  2. 층 목록에는 3-Tier 시나리오가 붙지 않는다 (ROI 표본이 아니다)
  3. `certainty` 가 확정/추정을 가르고, 기본 조회는 둘 다 준다
  4. 필터를 걸어도 **분모**(counts_all)가 같이 온다 — 잘린 것인지 원래 없는 것인지
  5. 산출물이 없는 거점은 404 이고, 슬러그가 아닌 입력도 404 다(경로 조작 차단)
  6. 면적은 같은 건물 안에서도 층마다 다르다 (균등분할이 아니다)

실행: (apps/backend 에서) python -m pytest tests/test_floor_vacancies.py -q
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import floor_vacancy

client = TestClient(app)
V1 = "/api/v1"
# 실 산출물이 있는 거점. 없으면 이 파일 전체를 건너뛴다(신규 클론·미빌드 환경).
HUB = "garosugil"


@pytest.fixture(autouse=True)
def _clear_cache():
    floor_vacancy.clear_cache()
    yield
    floor_vacancy.clear_cache()


def _skip_if_missing() -> None:
    if not floor_vacancy.path(HUB).exists():
        pytest.skip(f"{HUB} vacant_floor_units.json 미빌드 — "
                    "python -m data.pipelines.build_vacant_floor_units")


def _get(**q) -> dict:
    _skip_if_missing()
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    r = client.get(f"{V1}/commercial-districts/{HUB}/floor-vacancies?{qs}")
    assert r.status_code == 200, r.text
    return r.json()


def test_lists_floors_of_partially_vacant_buildings() -> None:
    """`partial` 건물의 빈 층이 목록에 있다 — `/postings` 에는 없는 것들이다.

    이 한 줄이 이 엔드포인트의 존재 이유다. 종전 인벤토리는 통째로 빈 건물만
    유닛으로 만들어서, 일부 층만 빈 건물은 매물이 **한 건도** 안 나왔다.
    """
    d = _get(limit=2000)
    assert d["total"] > 0
    statuses = {u["bld_status"] for u in d["units"]}
    assert "partial" in statuses
    assert "full" not in statuses          # 만실 건물은 목록에 없다

    postings = client.get(f"{V1}/commercial-districts/{HUB}/postings")
    if postings.status_code == 200:
        # 층 목록이 건물 단위 인벤토리보다 훨씬 크다(실측 411 vs 12).
        assert d["total"] > len(postings.json())


def test_floor_units_carry_no_roi_scenarios() -> None:
    """시나리오가 붙지 않는다 — 이 목록은 ROI 표본이 아니다(§0-Q·§0-T)."""
    d = _get(limit=5)
    for u in d["units"]:
        assert "scenarios" not in u
        assert "rent" not in u and "prem" not in u


def test_certainty_splits_confirmed_from_probable() -> None:
    """확정과 추정이 갈리고, 기본 조회는 둘 다 준다."""
    allu = _get(limit=2000)
    assert set(allu["counts"]) == {"confirmed", "probable"}
    assert allu["counts"]["confirmed"] + allu["counts"]["probable"] == allu["total"]

    conf = _get(certainty="confirmed", limit=2000)
    assert conf["total"] == allu["counts"]["confirmed"]
    assert {u["certainty"] for u in conf["units"]} == {"confirmed"}
    # 확정 층은 점포가 확인된 층과 겹치지 않는다
    assert all(u["floor"] not in u["occ_floors"] for u in conf["units"])


def test_filters_keep_the_denominator_visible() -> None:
    """필터를 걸어도 거점 전체 수가 같이 온다 — 목록의 분모다.

    분모가 없으면 "3건"이 잘린 것인지 원래 그것뿐인지 화면이 말할 수 없다.
    """
    d = _get(certainty="confirmed", floor=1, limit=5)
    assert d["total"] >= len(d["units"])
    assert d["counts_all"]["units"] > d["total"]
    assert all(u["floor"] == 1 for u in d["units"])
    assert set(d["by_floor"]) == {"1"}


def test_area_filter_and_per_floor_measurement() -> None:
    """면적은 그 층의 대장 실측이라 같은 건물 안에서도 층마다 다르다."""
    d = _get(min_area=30, max_area=60, limit=2000)
    assert all(30 <= u["area"] <= 60 for u in d["units"])

    every = _get(limit=2000)["units"]
    by_bldg: dict[str, set[int]] = {}
    for u in every:
        by_bldg.setdefault(u["pnu"], set()).add(u["area"])
    # 층이 여럿인 건물 중 최소 하나는 층마다 면적이 다르다(균등분할이면 전부 1개다)
    assert any(len(v) > 1 for v in by_bldg.values())


def test_unit_ids_are_unique_per_floor() -> None:
    """한 지번에 동이 여럿이어도 같은 층이 두 번 나오지 않는다.

    층 근거는 Page 마스터가 지번당 산출하므로 동마다 유닛을 내면 복제된다
    (실측 회귀: 중앙엠앤비사옥 1F 156평이 두 번 나왔었다).
    """
    d = _get(limit=2000)
    ids = [u["id"] for u in d["units"]]
    assert len(ids) == len(set(ids))
    assert all(u["bldgs_on_pnu"] >= 1 for u in d["units"])


def test_missing_inventory_and_bad_slug_are_404() -> None:
    """산출물이 없는 거점은 404 — '거점을 모른다'가 아니라 '층 산출물이 없다'."""
    assert client.get(f"{V1}/commercial-districts/nowhere/floor-vacancies").status_code == 404
    # 슬러그 모양이 아닌 입력은 파일 경로로 내려가지 않는다
    assert client.get(
        f"{V1}/commercial-districts/..%2F..%2Fetc/floor-vacancies").status_code == 404


def test_note_warns_against_using_it_as_roi_sample() -> None:
    """응답이 스스로 무엇이 아닌지 말한다.

    산출물의 note 가 소비자에게 닿아야 §0-Q 를 다시 밟지 않는다. 파일에만 적어 두면
    API 만 보는 쪽은 그 경고를 못 본다.
    """
    d = _get(limit=1)
    note = d["note"] or ""
    assert "vacant_units.json" in note and "§0-Q" in note


def test_json_shape_matches_the_gold_artifact() -> None:
    """서빙이 산출물을 그대로 낸다 — 중간에서 값을 만들지 않는다."""
    _skip_if_missing()
    raw = json.loads(floor_vacancy.path(HUB).read_text(encoding="utf-8"))
    d = _get(limit=2000)
    assert d["total"] == len(raw["units"])
    assert d["units"][0]["id"] == raw["units"][0]["id"]
    assert d["built_at"] == raw["built_at"]


def test_industry_fit_is_observation_not_recommendation() -> None:
    """매물에 붙는 업종은 **관측 분포**다 — 근거·표본·한계가 같이 온다.

    이 값이 "추천"으로 읽히면 안 된다. 그 자리에서 잘 된다는 뜻이 아니고(매출·생존
    미고려), GNN 업종 추천과도 다른 축이다(저쪽은 좌표 기준 7종 라벨).
    """
    d = _get(limit=40)
    fits = [u["fit"] for u in d["units"] if u.get("fit")]
    if not fits:
        pytest.skip("platform_industry_floor_fit.json 미빌드 — "
                    "python -m data.pipelines.build_industry_floor_fit")

    for f in fits:
        assert f["basis"] in ("purps_floor", "floor")
        # 표본 수 없이 비중만 주면 "3건 중 2건"이 67% 로 읽힌다
        assert f["n"] >= (d["fit_meta"] or {}).get("min_sample", 30)
        assert f["top"] and all(0 < t["share"] <= 1 and t["n"] > 0 for t in f["top"])
        # 응답 스스로 **한계**를 말한다 — 파일에만 적어 두면 API 만 보는 쪽은 못 본다.
        # 좁힌 관측이면 "잘 된다는 뜻이 아니다", 폴백이면 폴백이라고 밝혀야 한다.
        assert "뜻이 아니다" in f["note"] or "폴백" in f["note"]

    # 폴백은 폴백이라고 밝힌다
    for f in fits:
        if f["basis"] == "floor":
            assert "폴백" in f["note"]


def test_fit_absent_means_no_evidence_not_empty_list() -> None:
    """근거가 없으면 `fit` 키 자체가 없다.

    빈 목록을 주면 "이 자리에 들어갈 업종이 없다"로 읽힌다 — 그건 우리가 관측한
    것이 아니라 표본이 얇다는 뜻이다.
    """
    d = _get(limit=40)
    for u in d["units"]:
        assert u.get("fit") is None or u["fit"]["top"]


def test_fit_meta_discloses_the_join_rate() -> None:
    """표의 한계(조인율)가 목록에 같이 온다 — 부분 표본을 전수로 읽으면 안 된다."""
    d = _get(limit=1)
    meta = d.get("fit_meta")
    if not meta:
        pytest.skip("platform_industry_floor_fit.json 미빌드")
    st = meta.get("stats") or {}
    assert st.get("joined", 0) > 0 and st.get("stores", 0) > st.get("joined", 0)
    assert "관측" in (meta.get("note") or "")
