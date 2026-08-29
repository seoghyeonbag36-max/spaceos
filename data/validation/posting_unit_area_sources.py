"""Posting 공실 유닛 면적 해상도를 올릴 수 있는 공식 소스의 적격성 판정.

현재 ``vacant_units.json`` 의 528행은 일반건축물·폴리곤 단위의 공실 후보이고, ``area`` 는
건축물대장 상업면적을 capacity 로 나눈 호실당 평균이다. 이 값을 호실 실측으로
승격하려면 아래 네 조건을 **모두** 만족해야 한다.

1. 호실 단위 면적이 있다.
2. 현재 공실·임대가능 상태를 식별한다.
3. 현재 54거점의 528 거점-feature 후보행(450 거점/PNU 쌍·407 고유 PNU)을 같은
   민간 일반건축물 모집단으로 덮는다.
4. 기존 유닛에 붙일 안정적인 키(PNU+호 또는 동등한 키)가 있다.

공식 데이터라는 이유만으로 일부 조건을 면제하지 않는다. 하나라도 빠지면 런타임에
배선하지 않는 fail-closed 계약이다. 판정 근거는
``docs/finding-posting-unit-area-sources-2026-08-29.md`` 에 기록한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AreaSourceCandidate:
    """공식 면적 소스 하나와 현재 인벤토리 계약에 대한 판정."""

    source_id: str
    provider: str
    primary_url: str
    has_unit_area: bool
    has_current_vacancy: bool
    covers_existing_private_units: bool
    has_stable_join_key: bool
    update_cycle: str
    rejection_reason: str

    @property
    def eligible(self) -> bool:
        """현재 528개 거점-feature 후보행의 ``area`` 를 실측으로 승격할 수 있는가."""
        return all((
            self.has_unit_area,
            self.has_current_vacancy,
            self.covers_existing_private_units,
            self.has_stable_join_key,
        ))

    @property
    def missing_requirements(self) -> tuple[str, ...]:
        """적격 계약에서 빠진 조건을 기계 판독 가능한 이름으로 돌려준다."""
        checks = {
            "unit_area": self.has_unit_area,
            "current_vacancy": self.has_current_vacancy,
            "existing_private_inventory_scope": self.covers_existing_private_units,
            "stable_join_key": self.has_stable_join_key,
        }
        return tuple(name for name, present in checks.items() if not present)


CANDIDATES: tuple[AreaSourceCandidate, ...] = (
    AreaSourceCandidate(
        source_id="molit-building-ledger-exclusive-area",
        provider="국토교통부 건축HUB",
        primary_url="https://www.data.go.kr/data/15134735/openapi.do",
        has_unit_area=True,
        has_current_vacancy=False,
        covers_existing_private_units=False,
        has_stable_join_key=True,
        update_cycle="수시",
        rejection_reason=(
            "전유부 호실 면적은 집합건물에만 존재하고 공실 상태가 없다. 현재 인벤토리는 "
            "일반건축물만 집계하며, 기존 실측에서도 450 PNU와 전유부 교집합이 0이었다."
        ),
    ),
    AreaSourceCandidate(
        source_id="seoul-metro-retail-rental",
        provider="서울교통공사",
        primary_url="https://www.data.go.kr/data/15071329/fileData.do",
        has_unit_area=True,
        has_current_vacancy=True,
        covers_existing_private_units=False,
        has_stable_join_key=False,
        update_cycle="분기",
        rejection_reason=(
            "상가번호·면적·공실/임대진행 상태는 있으나 지하철 역사 내부 공공상가라는 별도 "
            "모집단이다. 기존 민간 건물 PNU·유닛 ID에 붙일 키도 제공하지 않는다."
        ),
    ),
    AreaSourceCandidate(
        source_id="lh-retail-supply",
        provider="한국토지주택공사",
        primary_url="https://www.data.go.kr/dataset/15038398/openapi.do",
        has_unit_area=True,
        has_current_vacancy=True,
        covers_existing_private_units=False,
        has_stable_join_key=False,
        update_cycle="공고별",
        rejection_reason=(
            "공급 공고의 상가 호·층·면적은 실측이지만 LH 공급분만 다룬다. 현재 54거점의 "
            "민간 일반건축물 공실 후보와 같은 모집단도, 같은 식별키도 아니다."
        ),
    ),
    AreaSourceCandidate(
        source_id="onbid-public-rental",
        provider="한국자산관리공사 온비드",
        primary_url="https://www.data.go.kr/data/15000849/openapi.do",
        has_unit_area=False,
        has_current_vacancy=True,
        covers_existing_private_units=False,
        has_stable_join_key=False,
        update_cycle="공고별",
        rejection_reason=(
            "공공자산 임대공고이며 물건 건물면적과 공고 식별자는 있어도 기존 민간 공실의 "
            "호실 실면적·PNU+호 조인 계약을 제공하지 않는다."
        ),
    ),
)


def eligible_sources() -> tuple[AreaSourceCandidate, ...]:
    """현재 인벤토리에 배선 가능한 후보만 반환한다."""
    return tuple(candidate for candidate in CANDIDATES if candidate.eligible)
