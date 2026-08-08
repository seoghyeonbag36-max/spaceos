"""[Page] 앵커 모집단 진단 대상 거점 발견 규칙 테스트.

실행: (레포 루트에서) python -m pytest data/tests -q
"""
from __future__ import annotations

from data import analyze_anchor_population as diag
from data.config.page_hubs import HUBS


def _touch_ledger(gold, slug: str) -> None:
    path = gold / slug / "building_vacancy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")


def test_ledger_hubs_discovered_from_gold(tmp_path, monkeypatch):
    """building_vacancy.json 이 있는 거점만 진단 대상으로 찾는다."""
    monkeypatch.setattr(diag, "GOLD", tmp_path)
    _touch_ledger(tmp_path, "garosugil")
    (tmp_path / "hongdae").mkdir()

    assert diag.ledger_hubs() == ["garosugil"]


def test_ledger_hubs_excludes_tier2_master_only(tmp_path, monkeypatch):
    """Tier2 마스터만 있고 건축물대장이 없으면 제외한다."""
    monkeypatch.setattr(diag, "GOLD", tmp_path)
    master = tmp_path / "hongdae" / "page_building_master.geojson"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")

    assert "hongdae" not in diag.ledger_hubs()


def test_ledger_hubs_follows_hub_registry_order(tmp_path, monkeypatch):
    """반환 순서는 파일 시스템 순서가 아니라 HUBS 키 순서를 따른다."""
    monkeypatch.setattr(diag, "GOLD", tmp_path)
    slugs = list(HUBS)[:4]
    _touch_ledger(tmp_path, slugs[2])
    _touch_ledger(tmp_path, slugs[0])
    _touch_ledger(tmp_path, slugs[3])

    assert diag.ledger_hubs() == [slugs[0], slugs[2], slugs[3]]
