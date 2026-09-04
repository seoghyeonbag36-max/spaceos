"""거점 체인 상태의 계획상가 예외 판정 테스트.

실행: (레포 루트에서) python -m pytest -q data/tests/test_chain_status.py
"""
from __future__ import annotations

import json

from data.config.page_hubs import PageHub
from scripts import chain_status as chain


def _store_ratio_report(tmp_path, monkeypatch, *, caveat: str) -> dict:
    """건물당 점포 11개인 가상 거점의 체인 보고서를 만든다."""
    slug = "store-ratio-probe"
    hub = PageHub(slug, "점포 비율 검증 거점", 127.0, 37.5, caveat=caveat)
    stores = [{"bldMngNo": "same-building", "store_id": i} for i in range(11)]
    store_path = tmp_path / "bronze" / slug / "2026-08-30" / "stores_raw.json"
    store_path.parent.mkdir(parents=True)
    store_path.write_text(json.dumps(stores), encoding="utf-8")

    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: ("seoul", "seoul"))
    monkeypatch.setattr(chain, "_served_ids", lambda: {slug})
    return chain.summarize(slug)


def _store_stage(report: dict) -> dict:
    return next(stage for stage in report["stages"] if stage["stage"] == "점포")


def test_caveat_hub_is_not_blocked_on_store_ratio(tmp_path, monkeypatch):
    report = _store_ratio_report(tmp_path, monkeypatch, caveat="제품 판단으로 서빙 승인")
    store = _store_stage(report)

    assert store["status"] != chain.BLOCKED
    assert "예외" in store["evidence"]
    assert "점포" not in report["blocked"]


def test_caveat_absent_hub_still_blocks_on_store_ratio(tmp_path, monkeypatch):
    report = _store_ratio_report(tmp_path, monkeypatch, caveat="")
    store = _store_stage(report)

    assert store["status"] == chain.BLOCKED
    assert "점포" in report["blocked"]


# ── 서빙등재: 제품 판단(SERVED_CITIES)과 배선 결손을 가른다 ────────────────────────
#
# 2026-09-05 에 geumchon·tanhyeon·yadang 셋이 "Gold 가 섰는데 목록에 없다 —
# `_is_measured` 조건 확인" 으로 보고됐다. 그런데 `_is_measured` 는 통과하고 있었고,
# 실제로 거르는 것은 그 다음 줄의 `SERVED_CITIES={"seoul"}` 였다. 즉 프로버가 **멀쩡한
# 배선을 디버깅하라고** 시킨 것이다. 아래 둘이 그 갈림을 고정한다.

def _serving_report(tmp_path, monkeypatch, *, city: str, served: frozenset) -> dict:
    """Gold(건물마스터)까지 선 거점이 서빙 목록에 없을 때의 보고서."""
    slug = "serving-probe"
    hub = PageHub(slug, "서빙 판정 검증 거점", 127.0, 37.5, city=city)
    gold = tmp_path / "gold" / slug
    gold.mkdir(parents=True)
    # Gold 가 **선** 상태를 만든다 — 서빙등재의 `ready` 는 Page마스터·앵커를 보므로,
    # 건물마스터만 두면 "Gold 가 서기 전" 가지로 빠져 이 테스트가 다른 것을 재게 된다.
    gold.joinpath("page_building_master.geojson").write_text("{}", encoding="utf-8")
    gold.joinpath("coverage.json").write_text(
        json.dumps({"tier": "Tier1", "shown": 120, "reference_coverage_pct": 95.0}),
        encoding="utf-8")

    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: (city, city))
    monkeypatch.setattr(chain, "_served_ids", lambda: set())     # 목록에 없다
    monkeypatch.setattr(chain, "_served_cities", lambda: served)
    return chain.summarize(slug)


def _serving_stage(report: dict) -> dict:
    return next(s for s in report["stages"] if s["stage"] == "서빙등재")


def test_unserved_city_is_paused_not_a_wiring_defect(tmp_path, monkeypatch):
    report = _serving_report(tmp_path, monkeypatch, city="paju", served=frozenset({"seoul"}))
    stage = _serving_stage(report)

    assert stage["status"] == chain.PAUSED
    assert "제품 판단" in stage["evidence"]
    # 다음 한 수로 뽑히면 안 된다 — 고칠 코드가 없기 때문이다.
    assert stage["next"] == ""
    assert report["next_stage"] != "서빙등재"
    assert report["serving_paused"] is True


def test_served_city_still_reports_missing_listing(tmp_path, monkeypatch):
    """서빙 대상 도시인데 목록에 없으면 그것은 진짜 결손이다 — 보류로 삼키지 않는다."""
    report = _serving_report(tmp_path, monkeypatch, city="seoul", served=frozenset({"seoul"}))
    stage = _serving_stage(report)

    assert stage["status"] == chain.TODO
    assert "_is_measured" in stage["next"]
    assert report["serving_paused"] is False


def test_unreadable_decision_does_not_become_paused(tmp_path, monkeypatch):
    """판단을 못 읽었을 때(None) '보류'라고 단정하면 진짜 결손이 조용히 묻힌다."""
    report = _serving_report(tmp_path, monkeypatch, city="paju", served=None)
    stage = _serving_stage(report)

    assert stage["status"] == chain.TODO
    assert report["serving_paused"] is False


# ── 보류 도시는 수집 명령도 내지 않는다 (2026-09-05 결정) ──────────────────────────
#
# 서빙을 09-03 에 껐는데 프로버는 경기 17거점의 대장·공실유닛을 계속 "다음 한 수"로
# 냈다. 그걸 집으면 화면에 닿지 않을 데이터에 하루치 쿼터가 사라진다(쿼터는 회수되지
# 않는다). 명령은 **지우는 것이 아니라 가린다** — 재개할 때 다시 찾아야 하므로.

def _uncollected_paused_report(monkeypatch, tmp_path, *, include_paused: bool) -> dict:
    slug = "paused-collect-probe"
    hub = PageHub(slug, "보류 도시 미수집 거점", 126.8, 37.7, city="paju")
    monkeypatch.setattr(chain, "BRONZE", tmp_path / "bronze")   # 아무것도 수집 안 됨
    monkeypatch.setattr(chain, "GOLD", tmp_path / "gold")
    monkeypatch.setattr(chain, "_hubs", lambda: {slug: hub})
    monkeypatch.setattr(chain, "_city_of", lambda _hub: ("paju", "paju"))
    monkeypatch.setattr(chain, "_served_ids", lambda: set())
    monkeypatch.setattr(chain, "_served_cities", lambda: frozenset({"seoul"}))
    return chain.summarize(slug, include_paused=include_paused)


def test_paused_city_yields_no_next_move(tmp_path, monkeypatch):
    report = _uncollected_paused_report(monkeypatch, tmp_path, include_paused=False)

    assert report["serving_paused"] is True
    assert report["next"] == ""          # 쿼터를 태우라고 시키지 않는다
    assert report["next_stage"] == ""


def test_include_paused_restores_the_next_move(tmp_path, monkeypatch):
    """재개할 때 명령을 다시 찾을 수 있어야 한다 — 가린 것이지 지운 것이 아니다."""
    report = _uncollected_paused_report(monkeypatch, tmp_path, include_paused=True)

    assert report["serving_paused"] is True
    assert report["next"] != ""
    # 단계 목록에는 보류 여부와 무관하게 늘 남아 있다.
    assert any(s["next"] for s in report["stages"])
