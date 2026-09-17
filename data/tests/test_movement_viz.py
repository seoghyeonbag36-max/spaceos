"""이동 동선 시각화 판정을 고정한다 — docs/finding-movement-viz-2026-09-17.md.

고정하는 것은 둘뿐이다. 나머지 프로브(P1 취득·P3 복원·P4 해상도·P5 SNS)는
`scripts/probe_movement_viz.py` 가 매번 다시 재므로 테스트로 박지 않는다.

  1. **원천 스키마에 개인 축이 없다**(P2) — 생기면 결론이 뒤집히므로 먼저 알아야 한다.
  2. **수집기→Gold 체인이 돈다**(P6) — 데이터가 없을 뿐 능력은 있다는 주장의 근거.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_movement_viz import p2_identifier, p6_visualization  # noqa: E402


def test_migration_schema_has_no_person_axis():
    """생활이동 스키마에 사람/트립을 잇는 열이 없다 → 동선은 원천에 존재하지 않는다.

    ⚠ 이 테스트가 깨지면 반가운 일이다 — 배포분에 개인 축이 생겼다는 뜻이고,
    그때는 finding 문서의 §0-1 과 §2 P2 를 고칠 것.
    """
    r = p2_identifier()
    m = r["measured"]
    assert m["columns"] >= 10, "헤더 매핑표가 줄었다 — _COLS 를 확인할 것"
    assert m["identifier_columns"] == 0, (
        f"개인 축이 생겼다: {[c for c in m['detail'] if c['is_identifier']]}")
    assert m["person_axis_present"] is False
    assert "공간" in m["axes_present"] and "시간" in m["axes_present"]


def test_migration_chain_builds_flow_axes():
    """배포분과 같은 헤더의 합성 입력이 들어오면 유입 흐름 축이 채워진다.

    '동선은 못 그리지만 유입 흐름은 그릴 수 있다'는 결론의 실행 근거다.
    """
    r = p6_visualization()
    m = r["measured"]
    assert m["chain_ran"] is True, f"체인이 깨졌다: {m['chain_error']}"
    assert m["hubs_built"] >= 1
    assert m["hours_filled"] == 24, "도착시간 24구간이 다 채워져야 한다"
    assert m["origin_dongs_in_output"] > 0, "출발지 구성이 비었다"
    for axis in ("by_hour", "purpose_share", "sex_age_share", "origin_top"):
        assert axis in m["axes_in_gold"], f"{axis} 축이 Gold 에서 빠졌다"
    # 합성값이 서빙 산출물로 새면 P1(실데이터 0건) 결론이 거짓처럼 보인다.
    assert m["wrote_to_repo"] is False
    assert not (ROOT / "data" / "gold" / "platform_page_migration.json").exists(), (
        "프로브가 진짜 Gold 를 덮어썼다 — 합성값이 서빙으로 샌다")


@pytest.mark.parametrize("term", ["이동 동선", "동선 추적", "궤적"])
def test_finding_doc_forbids_trajectory_wording(term):
    """표기 규칙이 문서에 실제로 적혀 있는지 — 규칙이 사라지면 표기가 되돌아간다."""
    doc = (ROOT / "docs" / "finding-movement-viz-2026-09-17.md").read_text(encoding="utf-8")
    assert "유입 흐름" in doc
    assert term in doc, f"금지 표기 목록에서 '{term}' 이 빠졌다"
