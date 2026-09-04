"""[Page·분모] '아직 못 쟀다'와 '재 봤더니 상가층이 없다'를 갈라 두는 회귀.

2026-09-04 까지 두 상태가 같은 라벨(`floor_approx`)을 썼다. 그래서 대표 집계
커버리지가 회수 불가능한 잔여를 **미수집으로** 계속 셌다 — doksan 83.5% 의 정체가
그것이었다(잔여 13동 전부 층별개요 수신·지상 상업층 0 확정. 재호출로는 1%p 도
못 오른다). 게다가 floor_approx 는 capacity 를 지상 **전체** 층수로 잡으므로,
13층짜리 오피스텔이 지도에 "공실 84.6%" 로 칠해지고 있었다(어반팰리스, active 2).

고침: 층별개요를 받았고 상업층·점포확인층이 모두 0 인 행은 `no_com_floor` 로
강등해 지도와 커버리지 분모에서 함께 뺀다. 판정이지 결손이 아니기 때문이다.

여기서 고정하는 것 넷:
  1. 강등은 **근거가 있을 때만** 일어난다 (층별개요 원본이 없으면 floor_approx 유지)
  2. 강등된 행은 capacity 를 지어내지 않는다 (None · status "n_a")
  3. 근거가 넓어지면 **되돌아온다** (편도 강등이면 필터를 고쳐도 안 돌아온다)
  4. 지도 제외 사유로 '판정'과 '미확인'이 따로 세어진다

실행: (레포 루트에서) python -m pytest data/tests/test_no_com_floor.py -q
"""
from __future__ import annotations

import json

from data.collectors.building_vacancy import NO_COM_FLOOR, classify
from data.pipelines import recalc_floor_ouln as rc


def _flr(purpose: str, floors: int = 3) -> list[dict]:
    """지상 `floors` 개 층이 전부 `purpose` 인 층별개요 응답."""
    return [{"flrGbCdNm": "지상", "flrNo": i, "mainPurpsCdNm": purpose}
            for i in range(1, floors + 1)]


def _row(lno: str = "1154510200103360006") -> dict:
    return {"lnoCd": lno, "name": "테스트", "active": 2, "capacity": 13,
            "capacity_method": "floor_approx", "occupancy": 0.154,
            "vacancy_bldg": 84.6, "status": "high"}


def _run(tmp_path, monkeypatch, flr: dict, rows: list[dict], attrs: dict | None = None):
    """gold/bronze 를 임시 디렉터리로 갈아끼우고 recalc_floor_ouln.run 을 태운다."""
    gold = tmp_path / "gold" / "slug"
    gold.mkdir(parents=True)
    (gold / "building_vacancy.json").write_text(
        json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(rc, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(rc, "_load_flr", lambda _s: flr)
    monkeypatch.setattr(rc, "load_attrs", lambda _s: attrs or {})
    stat = rc.run("slug", apply=True)
    return stat, json.loads((gold / "building_vacancy.json").read_text(encoding="utf-8"))


def test_zero_commercial_floor_is_demoted_not_left_as_approx(tmp_path, monkeypatch) -> None:
    """지상층이 전부 오피스텔 → 상가 건물이 아님이 확정. floor_approx 로 두지 않는다."""
    row = _row()
    stat, out = _run(tmp_path, monkeypatch, {row["lnoCd"]: _flr("오피스텔", 13)}, [row])

    assert stat["상업층0강등"] == 1
    assert out[0]["capacity_method"] == NO_COM_FLOOR
    # capacity 를 지어내지 않는다 — 근거 없는 분모가 지도의 공실률이 되던 것이 원인이었다.
    assert out[0]["capacity"] is None
    assert out[0]["vacancy_bldg"] is None
    assert out[0]["status"] == "n_a" == classify(None, NO_COM_FLOOR)


def test_untried_building_stays_floor_approx(tmp_path, monkeypatch) -> None:
    """층별개요를 못 받은 건물은 결손이다 — 강등하면 '수집하면 오른다'는 사실이 지워진다."""
    row = _row()
    stat, out = _run(tmp_path, monkeypatch, {"9999999999999999999": _flr("소매점")}, [row])

    assert stat["상업층0강등"] == 0
    assert out[0]["capacity_method"] == "floor_approx"
    assert out[0]["capacity"] == 13


def test_demotion_is_reversible_when_evidence_widens(tmp_path, monkeypatch) -> None:
    """근거(점포 확인 층)가 생기면 no_com_floor 는 floor_ouln 으로 되돌아온다.

    편도 강등이면 NON_CAPACITY_PURPS 나 capacity_floors 를 고쳐도 그 건물들이
    영영 안 돌아온다. bronze 원본이 남아 있는 한 되돌릴 수 있어야 한다.
    """
    row = _row() | {"capacity_method": NO_COM_FLOOR, "capacity": None,
                    "vacancy_bldg": None, "status": "n_a"}
    flr = {row["lnoCd"]: _flr("고시원", 3)}
    attrs = {row["lnoCd"]: {"store_flr_nos": [1, 2], "grnd_flr": 3}}

    _, out = _run(tmp_path, monkeypatch, flr, [row], attrs)

    assert out[0]["capacity_method"] == "floor_ouln"
    assert out[0]["capacity"] == 2          # 점포가 확인된 1·2층만 분모


def test_coverage_counts_determination_apart_from_unknown() -> None:
    """산출물 회귀 — doksan 커버리지 100%, 그 근거는 '판정' 버킷에 따로 서 있다."""
    cov = json.loads((rc.GOLD / "doksan" / "coverage.json").read_text(encoding="utf-8"))

    assert cov["reference_coverage_pct"] == 100.0
    # 커버리지가 오른 이유가 '판정 제외'라는 것이 산출물에 남아야 한다. 이 값이 없으면
    # 다음 사람은 분모가 왜 줄었는지 알 길이 없다.
    assert cov["excluded_determined"] > 0
    # 대표 공실률은 이 작업으로 움직이지 않는다 — 원래 정밀 분모만 세었기 때문이다.
    assert cov["reference_vacancy_pct"] == 9.5
    assert "floor_approx" not in cov["by_capacity_method"]
