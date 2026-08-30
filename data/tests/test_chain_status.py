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
