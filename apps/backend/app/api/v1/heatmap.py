"""공실 히트맵 엔드포인트 — 100m 그리드(Page)."""
from fastapi import APIRouter, HTTPException

from app.schemas.district import VacancyHeatmap
from app.services import districts as svc

router = APIRouter()


@router.get("/vacancy", response_model=VacancyHeatmap)
async def vacancy_heatmap(district: str) -> dict:
    """거점 100m 그리드 공실률 히트맵. 쿼리: ?district=lafesta

    TODO: 건축물대장(공공데이터) + 네이버플레이스 영업상태 크롤링 정합 시
          합성값을 실측 셀로 대체.
    """
    hm = svc.get_vacancy_heatmap(district)
    if hm is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district}")
    return hm
