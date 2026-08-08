"""건물 관련 Pydantic 스키마."""
from pydantic import BaseModel


class HistoryItem(BaseModel):
    start_date: str
    end_date: str | None = None
    industry_type: str
    business_name: str
    source: str | None = None
    closure_reason_summary: str | None = None


class BuildingHistory(BaseModel):
    building_id: str
    # "localdata"(이 건물의 이력) / "localdata_lot"(지번 단위 — 같은 대지의 여러 동이 공유) / "none"
    history_source: str = "none"
    # 같은 지번을 공유하는 동 수. 2 이상이면 이력을 이 건물의 것이라고 말할 수 없다.
    lot_buildings: int | None = None
    history: list[HistoryItem]
