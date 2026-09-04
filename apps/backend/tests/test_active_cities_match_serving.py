"""`page_hubs.ACTIVE_CITIES` 와 `measured_pages.SERVED_CITIES` 가 어긋나지 않게 지킨다.

두 집합은 서로 다른 것을 정한다:
  · `SERVED_CITIES`  — 지금 **화면에 올릴** 도시 (제품 판단)
  · `ACTIVE_CITIES`  — 지금 **산출물을 만들** 도시 (파이프라인 기본 순회 집합)

어긋나면 두 방향 모두 조용히 나쁘다.
  · 서빙 ⊃ 액티브 → 화면에는 뜨는데 Platform·Posting·Program 산출물이 안 만들어진다.
    2026-09-03 에 실제로 이 상태였다 — 서울 2차 12거점이 Page 만 있고 나머지 트랙은
    0/12 였는데, 진행률 분모가 54 라 세 트랙이 100% 로 찍혔다.
  · 액티브 ⊃ 서빙 → 안 띄우는 거점에 수집·쿼터를 태운다.

어느 쪽을 바꾸든 **둘 다** 바꾼다. 이 테스트는 그걸 잊었을 때 울리는 것이다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app.data.measured_pages import SERVED_CITIES

_PAGE_HUBS = Path(__file__).resolve().parents[3] / "data" / "config" / "page_hubs.py"


def _page_hubs():
    spec = importlib.util.spec_from_file_location("_test_page_hubs", _PAGE_HUBS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_test_page_hubs"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_active_cities_equal_served_cities():
    mod = _page_hubs()
    assert set(mod.ACTIVE_CITIES) == set(SERVED_CITIES), (
        f"ACTIVE_CITIES={sorted(mod.ACTIVE_CITIES)} vs "
        f"SERVED_CITIES={sorted(SERVED_CITIES)} — 둘 다 바꿔야 한다"
    )


def test_active_hubs_is_the_served_subset_of_all_hubs():
    mod = _page_hubs()
    expected = {s for s, h in mod.ALL_HUBS.items() if h.city in SERVED_CITIES}
    assert set(mod.ACTIVE_HUBS) == expected
    # 시드 54 는 전부 들어 있어야 한다 — 빠지면 기존 산출물이 재빌드에서 사라진다.
    assert set(mod.HUBS) <= set(mod.ACTIVE_HUBS)
