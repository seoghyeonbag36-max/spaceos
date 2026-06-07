"""건물 관련 Pydantic 스키마."""
from pydantic import BaseModel


class HistoryItem(BaseModel):
    start_date: str
    end_date: str | None = None
    industry_type: str
    business_name: str
    closure_reason_summary: str | None = None


class BuildingHistory(BaseModel):
    building_id: str
    history: list[HistoryItem]
