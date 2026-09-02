"""계획상가 예외 판단(2026-09-02)이 **여전히 유효한지**를 산출물로 감시한다.

판단 자체는 `app/data/hub_caveats.py` 머리말에 있다. 여기서 지키는 것은 그 판단이 선
근거다 — 이 저장소의 실패 양식은 판단이 틀리는 것이 아니라 **판단이 낡는 것**이다.
재수집으로 재고 커버가 움직이면 아래 검사가 먼저 깨져서 사람이 다시 정하게 한다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data import hub_caveats as hc
from app.main import app
from app.services import districts as svc

client = TestClient(app)
V1 = "/api/v1"

# 판단이 선 근거 — 이 셋만 건물당 점포 10 을 넘고, 4위 gangnam(8.7)과 사이가 비어 있다.
# 재고 커버(호실 기준)는 서빙 집계에서 뽑는다.
_EXPECTED = {"banpo", "garak", "yeouido"}


def _summary(slug: str) -> dict:
    r = client.get(f"{V1}/commercial-districts/{slug}/summary")
    assert r.status_code == 200, slug
    return r.json()


def test_judgment_covers_exactly_the_three_hubs():
    """판단 대상이 늘거나 줄면 여기서 걸린다 — 조용히 바뀌면 안 되는 목록이다."""
    assert hc.WITHHELD | hc.DISCLOSED == _EXPECTED
    assert not (hc.WITHHELD & hc.DISCLOSED), "한 거점이 두 처리를 동시에 받을 수 없다"


def test_withheld_hub_serves_no_representative_number():
    """banpo — 대표 공실률과 그 파생값을 내려보내지 않는다.

    셋을 함께 본다. 하나라도 남으면 화면이 내린 수를 되계산할 수 있다:
    격차 = 대표값 − 앵커 · 예측 = 대표값 + delta.
    """
    for slug in hc.WITHHELD:
        s = _summary(slug)
        assert s["vacancy_withheld"] is True, slug
        assert s["vacancy_rate"] is None, slug
        assert s["anchor_gap_pp"] is None, slug
        assert s["predicted_rate"] is None and s["predicted_delta"] is None, slug
        # 앵커(R-ONE)는 외부 관측이라 남는다 — 우리 대표값과 무관하다.
        assert s["anchor_pct"] is not None, slug

        hm = client.get(f"{V1}/heatmap/vacancy", params={"district": slug}).json()
        assert hm["vacancy_withheld"] is True and hm["avg_vacancy"] is None, slug
        # 히트맵도 같은 규칙이다. 요약만 막고 여기를 열어 두면 `앵커 + 격차` 로 내린
        # 수가 그대로 되살아난다 — 실제로 그렇게 한 번 새어 나갔다.
        assert hm["anchor_gap_pp"] is None, slug
        assert hm["anchor_pct"] is not None, slug
        assert hm["predicted_rate"] is None, slug
        # 내린 것은 대표값뿐이다. 셀·건물은 그대로 서야 지도가 빈 채로 뜨지 않는다.
        assert hm["cells"] and hm["capacity"] > 0, slug


def test_disclosed_hubs_still_serve_their_number():
    """garak·yeouido — 값을 싣되 예외를 밝힌다. 내리는 것과 밝히는 것은 다른 처리다."""
    for slug in hc.DISCLOSED:
        s = _summary(slug)
        assert s["vacancy_withheld"] is False, slug
        assert s["vacancy_rate"] is not None and 0 <= s["vacancy_rate"] <= 100, slug
        assert s["caveat"].startswith("계획상가 밀집"), slug


def test_caveat_text_carries_the_live_coverage_number():
    """문구의 비율은 손으로 적은 상수가 아니라 **서빙이 쓴 집계**에서 나와야 한다.

    상수로 적어 두면 재수집 뒤 화면이 낡은 수를 계속 말한다 — 이 저장소가 반복해 당한
    실패 양식이다. 그래서 응답의 `inventory_coverage_pct` 가 문구 안에 그대로 있는지 본다.
    """
    for slug in _EXPECTED:
        s = _summary(slug)
        cov = s["inventory_coverage_pct"]
        assert cov is not None, slug
        assert f"{cov:.1f}%" in s["caveat"], f"{slug}: 문구의 비율이 집계와 다르다 — {s['caveat']}"


def test_inventory_coverage_is_measured_in_units_not_lots():
    """재고 커버는 **호실** 기준이다 — 지번 기준(`precision_pct`)과 섞으면 안 된다.

    banpo 는 지번으로는 집계가 멀쩡한데(precision_pct 60%대) 호실로는 5% 대다.
    두 값이 같은 것을 잰다고 읽히면 대표값을 내린 이유 자체가 사라진다.
    """
    s = _summary("banpo")
    assert s["inventory_coverage_pct"] < 10.0
    assert s["precision_pct"] > s["inventory_coverage_pct"] * 2, "두 지표가 같은 것을 재고 있다"


def _seoul_coverage() -> dict[str, float]:
    """서울 거점의 재고 커버(호실 기준). 판단이 선 모집단이다.

    ⚠ 경기 실측 거점은 뺀다. 2026-09-02 판단은 서울 분포 위에서 내렸고, 경기는 자기
      예외를 이미 `page_hubs.PageHub.caveat` 로 달고 있으며 커버가 더 얕은 곳도 있다
      (ilsan 2.3% · westerndom 2.5%). 같은 자에 놓으면 이 검사가 서울 판단이 아니라
      경기 상태를 감시하게 된다.
    """
    return {r["id"]: r["inventory_coverage_pct"] for r in svc.list_summaries()
            if r.get("city") == "seoul" and r.get("inventory_coverage_pct") is not None}


def test_withheld_hub_is_uniquely_shallow():
    """banpo 만 대표값을 내린 근거 — 재고 커버 10% 미만이 서울에서 이곳뿐이다.

    다른 거점이 10% 아래로 내려오면 "banpo 만 특별하다"가 더는 참이 아니다. 그때는
    자동으로 같이 내리지 않고 **사람이 다시 정한다** — 대표값을 내리는 것은 화면에서
    수를 없애는 일이라 규칙이 조용히 번지면 안 된다.
    """
    covs = _seoul_coverage()
    shallow = {s: c for s, c in covs.items() if c < 10.0}
    assert set(shallow) == set(hc.WITHHELD), (
        f"재고 커버 10% 미만이 {shallow} 다 — 내린 것은 {set(hc.WITHHELD)}. 다시 정할 것")
    # 내린 거점보다 얕은데 아무 표시가 없는 거점이 있으면 안 된다.
    floor = covs[next(iter(hc.WITHHELD))]
    below = {s: c for s, c in covs.items() if c < floor and s not in _EXPECTED}
    assert not below, f"내린 거점보다 얕은데 표시가 없다: {below}"


def test_the_two_axes_disagreement_is_bounded():
    """판단 축(건물당 점포)과 표기 축(재고 커버)이 어긋나는 자리를 고정한다.

    예외 셋은 **건물당 점포 10 초과**로 골랐다(banpo 25.2 · yeouido 27.7 · garak 14.1,
    4위 gangnam 8.7 과 사이가 비어 있다). 그런데 재고 커버로 다시 세우면 순서가 섞인다 —
    yongsan 11.0% · dongdaemun 13.1% 이 yeouido(11.2%)·garak(24.7%) 사이에 들어오는데
    둘은 건물당 점포로는 기준을 안 넘어 표시가 없다.

    이 어긋남은 **알고 남긴 것**이다. 두 축을 하나로 합치는 일(재고 커버를 판정 축으로
    승격)은 서울 전 거점을 다시 재야 하고 걸리는 거점이 늘어나므로, 2026-09-02 에
    별도 과제로 미뤘다 → docs/finding-hub-caveat-axes-2026-09-02.md

    여기서 막는 것은 그 어긋남이 **조용히 커지는 것**이다. 예외 셋 아래로 표시 없는
    거점이 새로 들어오면 미룬 과제를 다시 꺼내야 한다.
    """
    covs = _seoul_coverage()
    ceiling = max(covs[s] for s in _EXPECTED)          # garak 24.7%
    unmarked = sorted(s for s, c in covs.items() if c < ceiling and s not in _EXPECTED)
    assert unmarked == ["doksan", "dongdaemun", "gongdeok", "nambu", "yongsan"], (
        f"예외 셋 아래 표시 없는 거점 목록이 바뀌었다: {unmarked} — "
        "두 축을 합칠지 다시 판단할 것(docs/finding-hub-caveat-axes-2026-09-02.md)")


@pytest.mark.parametrize("slug", sorted(_EXPECTED))
def test_caveat_is_not_empty_and_says_not_to_compare(slug: str):
    """문구가 비어 있으면 표식만 붙고 뜻이 없다 — 화면이 이유를 못 말한다."""
    text = _summary(slug)["caveat"]
    assert len(text) > 40, slug
    assert "집합상가" in text, slug
