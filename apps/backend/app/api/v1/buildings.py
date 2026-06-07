"""건물 관련 엔드포인트 — 공실 히스토리 / 3D 모델."""
from fastapi import APIRouter, HTTPException

from app.schemas.building import BuildingHistory, HistoryItem

router = APIRouter()


@router.get("/{building_id}/history", response_model=BuildingHistory)
async def get_building_history(building_id: str) -> BuildingHistory:
    """건물의 업종 변천사 (디지털 트윈 공실 히스토리 맵).

    TODO: PostgreSQL/PostGIS의 buildings + building_history 조인 쿼리로 교체.
    현재는 골격 검증용 더미 데이터를 반환한다.
    """
    if not building_id:
        raise HTTPException(status_code=404, detail="Building not found")
    return BuildingHistory(
        building_id=building_id,
        history=[
            HistoryItem(
                start_date="2021-03-01",
                end_date="2023-06-30",
                industry_type="카페",
                business_name="예시 카페",
                closure_reason_summary="임대료 상승 및 유동인구 감소 (AI 요약 예정)",
            ),
        ],
    )


@router.get("/{building_id}/model")
async def get_building_model(building_id: str) -> dict[str, str]:
    """3D 건물 모델(glTF) 경로 반환. TODO: S3 presigned URL 연동."""
    return {"building_id": building_id, "model_url": f"/static/models/{building_id}.glb"}
