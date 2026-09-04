"""쿼터 프리플라이트의 서빙 보류 제외 판정.

실행: (레포 루트에서) python -m pytest -q data/tests/test_quota_preflight.py

이 스크립트가 찍는 실행줄은 그대로 복사돼 돌아간다. 그래서 **대상을 고르는 판정**이
곧 하루치 쿼터의 행선지다 — 쿼터는 하루가 지나면 회수되지 않으므로, 서빙하지 않기로
한 도시가 그 줄에 섞이면 그날의 수집이 통째로 화면에 닿지 않는다(2026-09-05 결정).
"""
from __future__ import annotations

import sys

from scripts import quota_preflight as qp


def test_paused_excludes_exactly_the_unserved_cities(monkeypatch):
    """`SERVED_CITIES` 한 곳이 단일 출처다 — 슬러그를 손으로 적지 않는다."""
    import app.data.measured_pages as mp

    monkeypatch.setattr(mp, "SERVED_CITIES", frozenset({"seoul"}))
    paused = qp._paused()

    expected = {slug for slug, hub in qp.ALL_HUBS.items()
                if getattr(hub, "city", "seoul") != "seoul"}
    assert paused == expected
    assert paused, "경기 거점이 등재돼 있으므로 비면 판정이 안 돈 것이다"
    # 서울 거점은 한 곳도 빠지지 않는다 — 빠지면 있는 일이 없는 것처럼 보인다.
    assert not any(getattr(qp.ALL_HUBS[s], "city", "seoul") == "seoul" for s in paused)


def test_resuming_a_city_puts_its_hubs_back(monkeypatch):
    """재개는 `SERVED_CITIES` 에 도시 id 를 되넣는 것 하나로 끝나야 한다."""
    import app.data.measured_pages as mp

    monkeypatch.setattr(mp, "SERVED_CITIES", frozenset({"seoul", "paju"}))
    paused = qp._paused()

    assert not any(getattr(qp.ALL_HUBS[s], "city", "") == "paju" for s in paused)
    assert any(getattr(qp.ALL_HUBS[s], "city", "") == "goyang" for s in paused)


def test_unreadable_decision_excludes_nothing(monkeypatch):
    """판단을 못 읽으면 아무것도 빼지 않는다 — 서울 잔여까지 조용히 사라지면 안 된다."""
    monkeypatch.setitem(sys.modules, "app.data.measured_pages", None)

    assert qp._paused() == set()
