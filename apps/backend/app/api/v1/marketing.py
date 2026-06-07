"""마케팅 엔드포인트 — 온·오프라인 솔루션(Program)."""
from fastapi import APIRouter, HTTPException

from app.schemas.district import Marketing
from app.services import districts as svc

router = APIRouter()


@router.get("/{district_id}", response_model=Marketing)
async def get_marketing(district_id: str) -> dict:
    """거점 마케팅(행사 + LLM 온라인 콘텐츠). TODO: LangChain 콘텐츠 생성 연동."""
    m = svc.get_marketing(district_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return m
