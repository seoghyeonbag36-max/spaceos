"""건물 관련 엔드포인트 — 공실 히스토리."""
from fastapi import APIRouter, HTTPException

from app.schemas.building import BuildingHistory
from app.services.building_history import get_history

router = APIRouter()


@router.get("/{building_id}/history", response_model=BuildingHistory)
async def get_building_history(building_id: str) -> BuildingHistory:
    """Return LocalData licensing history for a building."""
    if not building_id:
        raise HTTPException(status_code=404, detail="Building not found")
    history, history_source, lot_buildings = get_history(building_id)
    return BuildingHistory(
        building_id=building_id,
        history_source=history_source,
        lot_buildings=lot_buildings,
        history=history,
    )


@router.get("/{building_id}/model")
async def get_building_model(building_id: str) -> dict[str, str]:
    """glTF 경로를 만들어 돌려주는 **죽은 stub** — 부르는 곳이 없다.

    ⚠ 2026-09-05 에 3D 트윈이 폐기되면서 이 엔드포인트의 소비자가 사라졌다. 프론트도
    테스트도 부르지 않고, `/static/models/*.glb` 는 **한 번도 존재한 적이 없다**(경로를
    문자열로 조립해 돌려줄 뿐 파일 유무를 확인하지 않는다).

    남겨 둔 이유는 지우는 것이 공개 API 표면 변경이기 때문이다. 3D 를 되살릴 계획이
    없다면 **삭제가 맞다** — 낡은 선언을 남겨 두는 것이 이 저장소의 주된 실패 양식이다.
    """
    return {"building_id": building_id, "model_url": f"/static/models/{building_id}.glb"}
