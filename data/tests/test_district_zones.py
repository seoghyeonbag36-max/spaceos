"""행정동 실측 구역(`gold/{거점}/district_zones.json`)이 지켜야 할 것.

가장 중요한 것은 **구역 합계가 거점 대표값과 맞는다**는 것이다. 구역 공실률은
`gold_vacancy.build_cells` 와 같은 규칙으로 세는데, 두 규칙이 갈라지면 같은 건물을
두고 히트맵과 구역 카드가 서로 다른 말을 한다. 그 드리프트를 여기서 고정한다.

두 번째는 **감성이 조용히 되살아나지 않는 것**이다. 2026-08-25 에 못 잰다고 판정한
값이라(feature-platform §0-K), 누가 공실률이나 활력 지표를 `s` 에 옮겨 담으면
"실측처럼 보이는 추정치"가 된다 — AGENTS.md 가 금지한 바로 그 대체다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))
sys.path.insert(0, str(ROOT / "data" / "config"))

from app.services.districts import PAGES_BY_ID, cells_for  # noqa: E402
from page_hubs import ACTIVE_HUBS  # noqa: E402


def _zone_file(slug: str) -> dict | None:
    p = ROOT / "data" / "gold" / slug / "district_zones.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


SLUGS = sorted(ACTIVE_HUBS)


def test_every_served_hub_has_zones() -> None:
    """서빙 66거점 전부에 구역 산출물이 있어야 한다.

    2026-09-05 이전에는 시드 54거점만 구역을 갖고 2차 12거점은 빈 목록이라, 같은
    화면이 거점에 따라 다른 종류의 값을 그렸다. 그 비대칭을 여기서 막는다.
    """
    missing = [s for s in SLUGS if _zone_file(s) is None]
    assert not missing, f"구역 산출물 없는 거점: {missing} — python -m data.pipelines.build_district_zones"


@pytest.mark.parametrize("slug", SLUGS)
def test_zone_totals_match_the_hub_denominator(slug: str) -> None:
    """`sum(zones) + residual == 거점 대표 분모/분자`.

    구역에서 뺀 스필오버(작은 행정동)를 그냥 버리면 이 항등식이 깨진다. 깨진 채로 두면
    구역 카드를 다 더해도 거점 값이 안 나오는데, 그건 둘 중 하나가 틀렸다는 뜻이다.
    """
    data = _zone_file(slug)
    assert data is not None
    zones, residual = data["zones"], data["residual"]
    ci = cells_for(PAGES_BY_ID[slug])

    cap = sum(z["capacity"] for z in zones) + residual["capacity"]
    act = sum(z["active"] for z in zones) + residual["active"]
    assert cap == ci["capacity"], f"{slug}: 구역 분모 합 {cap} != 거점 분모 {ci['capacity']}"
    assert act == ci["sum_stores"], f"{slug}: 구역 분자 합 {act} != 거점 분자 {ci['sum_stores']}"


@pytest.mark.parametrize("slug", SLUGS)
def test_sentiment_stays_absent(slug: str) -> None:
    """감성은 **비어 있어야 한다** — 0 이 아니라 null 이다.

    ⚠ 이 테스트가 빨개졌다면 먼저 물을 것: 좌표를 가진 점포 리뷰 채널이 실제로
    생겼는가? 아니라면 누군가 공실률·활력 지표를 감성 자리에 옮겨 담은 것이고,
    그건 측정이 아니라 이름 바꾸기다(AGENTS.md · feature-platform §0-K).
    """
    data = _zone_file(slug)
    assert data is not None
    for z in data["zones"]:
        assert z["s"] is None, f"{slug}/{z['id']}: 감성이 채워졌다 — 채널이 생긴 게 맞나?"
        assert z["d"] is None
        assert z["r"] is None
        assert z["f"] == []


@pytest.mark.parametrize("slug", SLUGS)
def test_zone_fields_are_measured_and_consistent(slug: str) -> None:
    """구역이 들고 있는 실측값이 자기모순이 없어야 한다."""
    data = _zone_file(slug)
    assert data is not None
    assert data["zones"], f"{slug}: 구역이 0개 — 거점에 대표 집계 대상 건물이 없다는 뜻이라 확인 필요"
    ids = [z["id"] for z in data["zones"]]
    assert ids == [f"z{i}" for i in range(1, len(ids) + 1)], f"{slug}: 구역 id 가 연속이 아니다"
    for z in data["zones"]:
        assert z["active"] <= z["capacity"], f"{slug}/{z['id']}: 영업이 분모를 넘는다"
        assert z["buildings"] >= 1
        expected = round((z["capacity"] - z["active"]) / z["capacity"] * 100, 2)
        assert z["vacancy_rate"] == expected, f"{slug}/{z['id']}: 공실률이 분모·분자와 안 맞는다"


def test_the_seed_no_longer_carries_hand_written_zones() -> None:
    """시드에 손으로 적은 감성 구역이 되살아나지 않는다.

    54거점 × 6구역 = 324개가 전부 사람이 쓴 값이었다(감성 76.8 · 리뷰 2,140건).
    2026-09-05 에 걷어냈고, 서비스는 Gold 로만 구역을 채운다.
    """
    from app.data.seoul_pages import DISTRICTS

    with_zones = [d["id"] for d in DISTRICTS if d.get("zones")]
    assert not with_zones, f"시드에 구역이 다시 적혔다: {with_zones}"
