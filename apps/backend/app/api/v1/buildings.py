"""건물 관련 엔드포인트 — 공실 히스토리 / 3D 모델."""
from fastapi import APIRouter, HTTPException

from app.schemas.building import BuildingHistory
from app.services.building_history import get_history

router = APIRouter()


@router.get("/{building_id}/history", response_model=BuildingHistory)
async def get_building_history(building_id: str) -> BuildingHistory:
    """Return LocalData licensing history for a building."""
    if not building_id:
        raise HTTPException(status_code=404, detail="Building not found")
    history, history_source = get_history(building_id)
    return BuildingHistory(
        building_id=building_id,
        history_source=history_source,
        history=history,
    )


@router.get("/{building_id}/model")
async def get_building_model(building_id: str) -> dict[str, str]:
    """3D 건물 모델(glTF) 경로 반환. TODO: S3 presigned URL 연동."""
    return {"building_id": building_id, "model_url": f"/static/models/{building_id}.glb"}
