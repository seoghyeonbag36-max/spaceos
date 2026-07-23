"""AI 추론 엔드포인트 — LSTM 공실 예측 / GNN 업종 추천 / 매출 시뮬레이션."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.posting import SimulateRequest, SimulateResult
from app.services import industry_recommend as industry_svc
from app.services import posting as posting_svc
from app.services import vacancy_forecast as vacancy_svc

router = APIRouter()


class VacancyRequest(BaseModel):
    district_id: str
    horizon_months: int = 1


class IndustryRequest(BaseModel):
    """업종 추천 요청 — 거점(+좌표)이 기본 키.

    building_id 는 초기 스텁의 계약이라 남겨 뒀다(호출부가 아직 없어 깨질 소비자는 없다).
    GNN 그래프의 노드는 카카오 점포 자리라 건물 대장 키와 join 되지 않는다 — 건물로
    물으려면 좌표를 함께 준다.
    """
    district_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    building_id: str | None = None


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
    """GNN 업종 추천 — gold/platform_industry_recommend.json 서빙.

    좌표를 주면 최근접 그래프 노드의 Top-3, 없으면 거점 단위 평균 Top-3.
    추천 json 부재 시(신규 클론·미학습) 스텁 응답으로 폴백, 미지원 거점은 404.
    """
    if not req.district_id or not industry_svc.is_available():
        return {"district_id": req.district_id, "building_id": req.building_id,
                "recommendations": [], "model": "gnn-stub"}
    out = industry_svc.recommend(req.district_id, req.lat, req.lon)
    if out is None:
        raise HTTPException(
            status_code=404,
            detail=f"no recommendation for district/좌표: {req.district_id}")
    return {**out, "building_id": req.building_id}


@router.post("/simulate-revenue", response_model=SimulateResult)
async def simulate_revenue(req: SimulateRequest) -> dict:
    """입점 시뮬레이션(Posting) — 외부 AI 창업 코파일럿 어댑터 경유.

    코파일럿(settings.posting_copilot_url) 미설정 시 내부 3-Tier 폴백으로 응답한다.
    """
    result = posting_svc.simulate(req.district_id, req.unit_id, req.industry_type, req.strategy)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {req.district_id}")
    return result
