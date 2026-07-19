"""AI 추론 엔드포인트 — LSTM 공실 예측 / GNN 업종 추천 / 매출 시뮬레이션."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.posting import SimulateRequest, SimulateResult
from app.services import posting as posting_svc
from app.services import vacancy_forecast as vacancy_svc

router = APIRouter()


class VacancyRequest(BaseModel):
    district_id: str
    horizon_months: int = 1


class IndustryRequest(BaseModel):
    building_id: str


@router.post("/predict-vacancy")
async def predict_vacancy(req: VacancyRequest) -> dict[str, object]:
    """LSTM 공실 예측 — gold/platform_vacancy_forecast.json 서빙 (홀드아웃 방향정확도 84.6%).

    horizon_months(1~12)는 분기로 환산(올림, 최대 4분기)해 재귀 예측 horizon 을 고른다.
    forecast json 부재 시(신규 클론 등) 스텁 응답으로 폴백, 미지원 거점은 404.
    """
    if not vacancy_svc.is_available():
        return {"district_id": req.district_id, "predicted_vacancy_rate": None, "model": "lstm-stub"}
    quarters = max(1, min(-(-req.horizon_months // 3), 4))  # ceil(months/3), 1~4 클램프
    out = vacancy_svc.get_forecast(req.district_id, quarters=quarters)
    if out is None:
        raise HTTPException(status_code=404, detail=f"no forecast for district: {req.district_id}")
    return out


@router.post("/recommend-industry")
async def recommend_industry(req: IndustryRequest) -> dict[str, object]:
    """GNN 기반 업종 추천. TODO: ml.inference 모듈 연동 (정확도 20% 향상 목표)."""
    return {"building_id": req.building_id, "recommendations": [], "model": "gnn-stub"}


@router.post("/simulate-revenue", response_model=SimulateResult)
async def simulate_revenue(req: SimulateRequest) -> dict:
    """입점 시뮬레이션(Posting) — 외부 AI 창업 코파일럿 어댑터 경유.

    코파일럿(settings.posting_copilot_url) 미설정 시 내부 3-Tier 폴백으로 응답한다.
    """
    result = posting_svc.simulate(req.district_id, req.unit_id, req.industry_type, req.strategy)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {req.district_id}")
    return result
