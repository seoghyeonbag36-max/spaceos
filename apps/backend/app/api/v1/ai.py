"""AI 추론 엔드포인트 — LSTM 공실 예측 / GNN 업종 추천 / 매출 시뮬레이션."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class VacancyRequest(BaseModel):
    district_id: str
    horizon_months: int = 1


class IndustryRequest(BaseModel):
    building_id: str


@router.post("/predict-vacancy")
async def predict_vacancy(req: VacancyRequest) -> dict[str, object]:
    """LSTM 기반 공실률 예측. TODO: ml.inference 모듈 연동 (목표 정확도 70%+)."""
    return {"district_id": req.district_id, "predicted_vacancy_rate": None, "model": "lstm-stub"}


@router.post("/recommend-industry")
async def recommend_industry(req: IndustryRequest) -> dict[str, object]:
    """GNN 기반 업종 추천. TODO: ml.inference 모듈 연동 (정확도 20% 향상 목표)."""
    return {"building_id": req.building_id, "recommendations": [], "model": "gnn-stub"}
