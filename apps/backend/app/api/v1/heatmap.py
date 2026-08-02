"""공실 히트맵 엔드포인트 — 100m 그리드 + 건물 폴리곤(Page)."""
from fastapi import APIRouter, HTTPException

from app.schemas.district import VacancyHeatmap
from app.services import building_vacancy as bv
from app.services import districts as svc
from app.services import rent_layer

router = APIRouter()


@router.get("/buildings")
async def building_vacancy(district: str) -> dict:
    """건물 단위 공실 GeoJSON(FeatureCollection). 쿼리: ?district=gangnam-garosugil

    MapShell 공실 레이어가 naver.maps.Polygon 으로 렌더한다.
    실데이터: Gold page_building_master.geojson (없으면 샘플 폴백) — services/building_vacancy.py.
    """
    fc = bv.building_vacancy_geojson(district)
    if fc is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district}")
    return fc


@router.get("/vacancy", response_model=VacancyHeatmap)
async def vacancy_heatmap(district: str) -> dict:
    """거점 100m 그리드 공실률 히트맵. 쿼리: ?district=<거점 id>

    Gold 건물 마스터가 있는 거점은 실측 집계(`vacancy_source == "gold"`),
    없으면 합성 그리드 폴백(`"synthetic"`) — services/gold_vacancy 참조.
    """
    hm = svc.get_vacancy_heatmap(district)
    if hm is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district}")
    return hm


@router.get("/rent")
async def rent_heatmap(district: str) -> dict:
    """R-ONE rent heatmap on the same 100m grid as /heatmap/vacancy."""
    hm = rent_layer.rent_heatmap(district)
    if hm is None:
        raise HTTPException(status_code=404, detail=f"rent unavailable: {district}")
    return hm
