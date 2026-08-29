"""Posting 유닛 면적 소스는 네 조건을 모두 만족할 때만 런타임에 승격한다."""
from __future__ import annotations

from data.validation.posting_unit_area_sources import CANDIDATES, eligible_sources


def test_no_public_source_is_eligible_for_existing_private_units() -> None:
    """2026-08-29 공식 소스 탐색 결과: 현재 528 후보행을 대체할 소스는 없다."""
    assert eligible_sources() == ()
    assert all(candidate.missing_requirements for candidate in CANDIDATES)


def test_area_source_candidates_have_primary_evidence_and_rejection_reason() -> None:
    """기각은 출처 URL과 기계 판독 가능한 결손 조건을 반드시 남긴다."""
    assert len(CANDIDATES) >= 4
    for candidate in CANDIDATES:
        assert candidate.primary_url.startswith("https://www.data.go.kr/")
        assert candidate.provider.strip()
        assert candidate.update_cycle.strip()
        assert candidate.rejection_reason.strip()
        assert candidate.missing_requirements


def test_partial_public_stock_cannot_promote_the_existing_area_contract() -> None:
    """면적·공실 두 필드가 있어도 별도 공공자산이면 기존 area 승격 근거가 아니다."""
    partial = [
        candidate for candidate in CANDIDATES
        if candidate.has_unit_area and candidate.has_current_vacancy
    ]
    assert partial, "호실 면적+공실을 함께 주는 부분 후보가 탐색 목록에서 사라졌다"
    assert all(not candidate.covers_existing_private_units for candidate in partial)
    assert all(not candidate.eligible for candidate in partial)
