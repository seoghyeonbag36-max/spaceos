"""층 단위 공실 매물 목록(Page) 스키마.

`Posting`(건물 단위 유닛 + 3-Tier 시나리오)과 **다른 것을 싣는다** — 여기는 "몇 층이
비었고 그 층이 몇 평이며 대장이 무슨 용도를 허용하는가"라는 목록이다. 시나리오·임대료
·ROI 는 들어오지 않는다. 그 계산의 표본은 종전대로 `vacant_units.json` 이다
(docs/feature-posting.md §0-Q·§0-T).
"""
from __future__ import annotations

from pydantic import BaseModel


class IndustryFitEntry(BaseModel):
    industry: str
    share: float          # 그 칸에서 이 업종이 차지한 **관측 비중**(확률이 아니다)
    n: int


class IndustryFit(BaseModel):
    """이 매물과 같은 조건(대장 용도·층)의 자리에서 실제 영업 중인 업종 분포.

    ⚠ **추천이 아니라 관측이다.** 그 자리에서 잘 된다는 뜻이 아니며(매출·생존은 안 봤다),
       GNN 업종 추천과도 다른 축이다(저쪽은 좌표 기준 7종 라벨).
    """
    # "purps_floor" 용도+층으로 좁힌 관측 · "floor" 용도 표본이 얇아 층만 본 폴백
    basis: str
    n: int                # 이 칸의 표본 수 — 없으면 비중을 못 읽는다
    top: list[IndustryFitEntry]
    note: str


class FloorVacancyUnit(BaseModel):
    id: str
    building_id: str | None = None
    pnu: str | None = None
    # 한 지번에 동이 여럿이면 층 근거를 동으로 나눌 수 없어 하나로 접는다.
    # 1 이면 건물 하나가 곧 이 유닛이다. 2 이상이면 "어느 동인지는 모른다"는 뜻이다.
    bldgs_on_pnu: int = 1
    n: str
    lat: float
    lng: float
    floor: int
    floor_label: str
    # "confirmed" 비었음이 확정 · "probable" 층 미상 점포가 다른 층이면 빈다.
    # 화면에서 같은 것으로 그리면 안 된다 — 추정이 실측처럼 읽힌다.
    certainty: str
    area: int          # 평 — 그 **층의** 건축물대장 실측(균등분할이 아니다)
    area_m2: float
    # 건축물대장이 그 층에 허용한 용도. 업종 후보를 거르는 근거이며,
    # **현재 영업 중인 업종이 아니다.**
    purps: str = ""
    bld_status: str | None = None
    bld_floors: int = 0
    bld_vacancy_rate: float | None = None
    com_floors: list[int] = []
    occ_floors: list[int] = []
    unknown_n: int = 0
    was: str = ""
    # 근거가 없으면 **키가 없다**. 빈 목록을 주면 "들어갈 업종이 없다"로 읽힌다.
    fit: IndustryFit | None = None


class FloorVacancyList(BaseModel):
    district_id: str
    total: int                      # 필터 적용 뒤 유닛 수
    counts: dict[str, int]          # 필터 적용 뒤 confirmed/probable
    counts_all: dict[str, int]      # 필터 **전** 거점 전체 — 목록의 분모
    by_floor: dict[str, int]        # 층 히스토그램(필터 적용 뒤)
    built_at: str | None = None
    source: str | None = None
    note: str | None = None
    # 적합도 표 자체의 근거·한계(조인율 약 30% 등). 유닛마다 반복하지 않는다.
    fit_meta: dict | None = None
    units: list[FloorVacancyUnit]
