"""PPPP 진행 문서가 2026-08-29 구현 계약과 함께 움직이는지 검증한다."""

import json
import subprocess
import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_canonical_progress_names_current_state_and_remaining_work() -> None:
    """정본은 완료된 작업을 다시 '다음 작업'으로 만들지 않아야 한다."""
    doc = _read("docs/spaceos-vibe-build-sequence.md")

    assert "현재 위치 요약 (2026-09-04)" in doc
    assert "Posting" in doc and "97.6%" in doc
    assert "Platform" in doc and "관측 전용" in doc
    assert "상용 입력 온보딩" in doc
    assert "B2B 파일럿" in doc
    assert "다음 작업 (2026-08-20 기준)" not in doc


def test_feature_docs_name_source_contracts_targets_and_tests() -> None:
    """Posting·Program 기능 문서는 소스/대상 파일/통과 테스트를 명시해야 한다."""
    posting = _read("docs/feature-posting.md")
    program = _read("docs/feature-program.md")

    assert "finding-posting-unit-area-sources-2026-08-29.md" in posting
    assert "data/validation/posting_unit_area_sources.py" in posting
    assert "test_no_public_source_is_eligible_for_existing_private_units" in posting
    assert "test_partial_public_stock_cannot_promote_the_existing_area_contract" in posting

    assert "ProgramCommercialOnboardingRequest" in program
    assert "apps/backend/app/services/program_onboarding.py" in program
    assert "test_commercial_onboarding_requires_org_auth" in program
    assert "test_commercial_onboarding_returns_receipt_without_persisting_raw_input" in program
    assert "npm run build" in program


def test_status_and_index_link_to_the_new_evidence() -> None:
    """상태 계산기와 문서 인덱스에서도 신규 근거에 도달할 수 있어야 한다."""
    status = _read("scripts/pppp_status.py")
    index = _read("docs/README.md")

    assert "공식 공개 소스를 다시 탐색했지만 적격 후보는 0건" in status
    assert "상용 입력 온보딩 계약" in status
    assert "finding-posting-unit-area-sources-2026-08-29.md" in index
    assert "기술 계약 통과와 KPI②" in index

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pppp_status.py"), "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    scores = {track["name"]: track["pct"] for track in json.loads(result.stdout)["tracks"]}
    # 2026-09-04 서울 2차 12거점이 분모에 들어오면서 Page 가 100.0 → 99.7 이 됐다.
    # 회귀가 아니라 **새 거점의 실측**이다: `대표 집계 커버리지 ≥90%` 가 65/66 이고
    # 미달은 doksan 83.5% 한 곳인데, 그 결손은 회수 불가다 — 건축HUB 층별개요
    # 프리플라이트가 doksan 의 floor_approx 13동을 전부 **판정완료(상업층 0 확정)**
    # 로 분류한다(재호출해도 안 바뀐다). 그래서 수집 과제로 적지 않고 값으로 고정한다.
    assert scores == {"Page": 99.7, "Platform": 100.0, "Posting": 97.6, "Program": 100.0}
