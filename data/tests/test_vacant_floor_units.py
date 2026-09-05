"""[Page·Posting] 층 단위 공실 매물 인벤토리의 성질을 고정한다.

`build_vacant_floor_units` 는 §0-Q 가 되돌린 자리 바로 옆에 선다. 그때 되돌린 이유는
데이터가 아니라 ROI 트립와이어였고, 이 산출물은 그 표본을 대체하지 않는 **별도 목록**
이라는 전제 위에 있다. 그 전제와 세는 규칙이 조용히 어긋나는 것을 막는다.

고정하는 것 여섯:
  1. 유닛은 **(지번, 층)** 단위다 — 한 지번에 동이 여럿이어도 층이 복제되지 않는다
     (실측 회귀: 가로수길 중앙엠앤비사옥 1F 156평이 두 번 나왔었다)
  2. 점포가 확인된 층(`occ_floors`)은 매물이 되지 않는다
  3. 층 미상 점포는 **낮은 층부터** 앉힌다 — `build_page_master._aggregate` 와 같은
     규칙이라야 Page 와 이 목록이 같은 건물에서 같은 층을 비었다고 말한다
  4. 그 배정에서 살아남은 층만 `confirmed`, 먹힌 층은 `probable` 이다
  5. 만실(`full`) 건물은 목록에 없다 — 우리 자신의 status 와 어긋나기 때문
  6. 면적은 그 층의 층별개요 실측이다 (균등분할이 아니다)

실행: (레포 루트에서) python -m pytest data/tests/test_vacant_floor_units.py -q
"""
from __future__ import annotations

import json

from data.pipelines import build_vacant_floor_units as bvfu


def _feat(pnu: str, *, bid: str, com: list[int], occ: list[int], unknown: int,
          status: str = "partial", floors: int = 5) -> dict:
    """Page 마스터 feature 한 장 — 층 근거가 실린 최소 형태."""
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [[[127.0, 37.5], [127.001, 37.5],
                                      [127.001, 37.501], [127.0, 37.5]]]},
        "properties": {
            "id": bid, "pnu": pnu, "name": "테스트빌딩",
            "capacity_method": "floor_ouln", "source": "stores+ledger",
            "status": status, "floors": floors, "vacancy_rate": 50.0,
            "com_floors": com, "occ_floors": occ, "unknown_n": unknown,
            "industry": "소매",
        },
    }


def _flr_rows(pnu: str, floors: dict[int, float]) -> dict[str, list[dict]]:
    """층별개요 원본 — 층마다 면적(㎡)과 상업 주용도."""
    return {pnu: [{"flrGbCdNm": "지상", "flrNo": no, "area": area,
                   "mainPurpsCdNm": "소매점"} for no, area in floors.items()]}


def _run(tmp_path, monkeypatch, feats: list[dict], flr: dict) -> list[dict]:
    """파이프라인을 임시 gold/bronze 위에서 돌리고 유닛 목록을 돌려준다."""
    slug = "testhub"
    gold = tmp_path / "gold" / slug
    gold.mkdir(parents=True)
    (gold / "page_building_master.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    monkeypatch.setattr(bvfu, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(bvfu, "_load_floor_rows", lambda _s: flr)
    return bvfu._units_for(slug)


# 200㎡ ≈ 61평 — _MIN_PYEONG~_MAX_PYEONG 안에 드는 값
_AREA = {1: 200.0, 2: 200.0, 3: 200.0, 4: 200.0, 5: 200.0}


def test_one_unit_per_floor_not_per_building(tmp_path, monkeypatch):
    """한 지번에 동이 둘이어도 층은 한 번만 나온다.

    층 근거(com_floors·occ_floors)는 Page 마스터가 지번당 산출하므로 같은 지번의
    모든 동이 같은 층 집합을 들고 있다. 동마다 유닛을 내면 같은 층이 동 수만큼
    복제되고, 목록은 있지도 않은 매물을 두 배로 세게 된다.
    """
    pnu = "1168010700100010001"
    feats = [_feat(pnu, bid=f"{pnu}-1", com=[1, 2, 3], occ=[3], unknown=0),
             _feat(pnu, bid=f"{pnu}-2", com=[1, 2, 3], occ=[3], unknown=0, floors=3)]
    units = _run(tmp_path, monkeypatch, feats, _flr_rows(pnu, _AREA))

    assert [u["floor"] for u in units] == [1, 2]
    assert len({u["id"] for u in units}) == 2
    # 접었다는 사실을 숨기지 않는다
    assert all(u["bldgs_on_pnu"] == 2 for u in units)
    # 대표는 지상층수가 큰 동 — 0/누락 동이 대표가 되면 bld_floors 가 0 으로 나간다
    assert all(u["bld_floors"] == 5 for u in units)


def test_occupied_floors_are_never_listed(tmp_path, monkeypatch):
    """점포·인허가로 영업이 확인된 층은 매물이 아니다."""
    pnu = "1168010700100010002"
    units = _run(tmp_path, monkeypatch,
                 [_feat(pnu, bid=f"{pnu}-1", com=[1, 2, 3, 4], occ=[1, 3], unknown=0)],
                 _flr_rows(pnu, _AREA))
    assert sorted(u["floor"] for u in units) == [2, 4]
    assert all(u["floor"] not in u["occ_floors"] for u in units)


def test_unknown_floor_stores_are_seated_from_the_bottom(tmp_path, monkeypatch):
    """층 미상 점포는 낮은 층부터 앉고, 살아남은 층만 확정이다.

    이 규칙이 `build_page_master._aggregate` 의 상한 계산과 갈라지면 Page 와 이
    목록이 같은 건물을 두고 서로 다른 층을 비었다고 말한다.
    """
    pnu = "1168010700100010003"
    # 상업층 1~5, 5층만 점유 확인, 층 미상 점포 2 → 빈 후보 [1,2,3,4] 중 1·2 가 먹힌다
    units = _run(tmp_path, monkeypatch,
                 [_feat(pnu, bid=f"{pnu}-1", com=[1, 2, 3, 4, 5], occ=[5], unknown=2)],
                 _flr_rows(pnu, _AREA))
    got = {u["floor"]: u["certainty"] for u in units}
    assert got == {1: "probable", 2: "probable", 3: "confirmed", 4: "confirmed"}
    # 확정이 먼저 오고, 그 안에서 낮은 층이 먼저다 (입점 검토 순서)
    assert [u["floor"] for u in units] == [3, 4, 1, 2]


def test_full_buildings_are_excluded(tmp_path, monkeypatch):
    """만실 판정 건물은 '추정 공실층'을 갖고 있어도 목록에 없다.

    상한 배정에서 상업층이 전부 찬 것으로 판정된 건물이다. 여기에 매물을 실으면
    목록이 우리 자신의 status 와 어긋난 말을 한다.
    """
    pnu = "1168010700100010004"
    units = _run(tmp_path, monkeypatch,
                 [_feat(pnu, bid=f"{pnu}-1", com=[1, 2, 3], occ=[2, 3], unknown=1,
                        status="full")],
                 _flr_rows(pnu, _AREA))
    assert units == []


def test_area_is_measured_per_floor_not_split_evenly(tmp_path, monkeypatch):
    """면적은 그 층의 층별개요 실측이다 — 같은 건물의 두 유닛이 달라야 한다.

    `vacant_units.json` 의 `area` 는 상업면적 ÷ 호실 수라 같은 건물이면 항상 같았다
    (그래서 '유닛 면적 입도' 게이트가 0.5 에 묶였다). 이 산출물은 그 자리를 층별
    실측으로 채운다.
    """
    pnu = "1168010700100010005"
    units = _run(tmp_path, monkeypatch,
                 [_feat(pnu, bid=f"{pnu}-1", com=[1, 2], occ=[], unknown=0)],
                 _flr_rows(pnu, {1: 330.58, 2: 165.29}))
    by_floor = {u["floor"]: u["area"] for u in units}
    assert by_floor == {1: 100, 2: 50}
    # 용도는 업종 후보를 거르는 근거라 반드시 실린다
    assert all(u["purps"] == "소매점" for u in units)


def test_floor_without_ledger_area_is_dropped_not_assumed(tmp_path, monkeypatch):
    """그 층의 대장 면적이 없으면 유닛을 만들지 않는다.

    면적을 가정하면 그 위에 얹히는 투자비·매출이 전부 가정이 된다 —
    `build_vacant_units` 가 건물 단위에서 세운 것과 같은 규칙이다.
    """
    pnu = "1168010700100010006"
    units = _run(tmp_path, monkeypatch,
                 [_feat(pnu, bid=f"{pnu}-1", com=[1, 2, 3], occ=[], unknown=0)],
                 _flr_rows(pnu, {1: 200.0, 3: 200.0}))   # 2층 면적 없음
    assert sorted(u["floor"] for u in units) == [1, 3]
