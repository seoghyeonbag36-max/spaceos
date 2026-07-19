"""거점(commercial district) 응답 스키마."""
from __future__ import annotations

from pydantic import BaseModel


class DistrictSummary(BaseModel):
    id: str
    name: str
    gu: str
    type: str
    center: list[float]
    note: str
    rec_top: str
    sentiment: float
    reviews: int
    risk_zones: int
    vacancy_rate: float
    vacant_units: int
    cell_count: int
    store_count: int
    tier_mix: dict[str, int]
    # Platform·LSTM 다음 분기 예측 (forecast json 부재 시 None)
    predicted_rate: float | None = None
    predicted_delta: float | None = None
    predicted_direction: str | None = None


class Zone(BaseModel):
    id: str
    n: str
    grp: str
    lat: float
    lng: float
    s: float
    d: float
    r: int
    f: list[list[str]]


class Cell(BaseModel):
    i: int
    j: int
    lat: float
    lng: float
    c_lat: float
    c_lng: float
    v: float
    stores: int
    vac_n: int
    dlat: float
    dlng: float


class VacancyHeatmap(BaseModel):
    district_id: str
    resolution_m: int
    cells: list[Cell]
    sum_stores: int
    sum_vac: int
    avg_vacancy: float
    # Platform·LSTM 다음 분기 예측 (거점 단위, forecast json 부재 시 None)
    predicted_rate: float | None = None
    predicted_delta: float | None = None
    predicted_direction: str | None = None


class TierScenario(BaseModel):
    tier: str
    name: str
    sub: str
    invest_mn: int
    month_cost: int
    month_rev: int
    month_net: int
    roi_months: float
    recommended: bool


class Posting(BaseModel):
    id: str
    n: str
    grp: str
    lat: float
    lng: float
    area: int
    rent: int
    prem: int
    floor: str
    was: str
    rec: str
    foot: str
    persona: str
    note: str
    scenarios: dict[str, TierScenario]


class MarketingEvent(BaseModel):
    id: str
    n: str
    lat: float
    lng: float
    ic: str
    when: str
    k2: str
    desc: str
    roles: list[str]
    ha: str


class Marketing(BaseModel):
    district_id: str
    events: list[MarketingEvent]
    online_contents: list[str]
