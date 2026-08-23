"""공실 히트맵 엔드포인트 — 100m 그리드 + 건물 폴리곤(Page)."""
from fastapi import APIRouter, HTTPException

from app.schemas.district import VacancyHeatmap
from app.services import building_vacancy as bv
from app.services import districts as svc
from app.services import footfall_layer, rent_layer

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


@router.get("/footfall")
async def footfall_heatmap(district: str, hour: int = 12) -> dict:
    """시간대별 유동인구 히트맵 — 공실/임대와 같은 100m 격자. 쿼리: ?district=..&hour=0~23

    2026-08-23 이전에는 이 엔드포인트가 없었고 프론트가 `Math.random()` 으로 점 120개를
    만들어 그렸다(슬라이더가 입력을 보지 않아 장식이었다). 실데이터는 TRDAR 상권 190곳
    — services/footfall_layer 참조.

    ⚠ 값은 **상권 단위 집계**를 격자에 얹은 것이다. 응답의 `resolution`·`note` 를 화면에
    함께 노출할 것 — 빼면 격자 단위 실측처럼 읽힌다.
    """
    hm = footfall_layer.footfall_heatmap(district, hour)
    if hm is None:
        raise HTTPException(status_code=404, detail=f"footfall unavailable: {district}")
    return hm


@router.get("/density")
async def density_heatmap(district: str, metric: str = "flpop") -> dict:
    """상권 밀도 히트맵. 쿼리: ?district=..&metric=flpop|stor

    `flpop` 은 **유동인구** 밀도다(상주인구가 아니다 — 화면 라벨이 '인구밀도'였지만
    우리가 가진 것은 유동인구다). `stor` 는 점포 밀도.
    """
    hm = footfall_layer.density_heatmap(district, metric)
    if hm is None:
        raise HTTPException(status_code=404, detail=f"density unavailable: {district}")
    return hm
