"""마케팅 엔드포인트 — 가게 단위 생성 + 상권 단위 조회(Program)."""
from fastapi import APIRouter, HTTPException

from app.schemas.district import Marketing
from app.schemas.marketing import StoreMarketing, StoreProfile
from app.services import marketing as mkt

router = APIRouter()


@router.post("/generate", response_model=StoreMarketing)
async def generate_store_marketing(profile: StoreProfile) -> dict:
    """가게 단위 온/오프라인 마케팅 광고 솔루션 자동 생성.

    입력(StoreProfile)은 상가 사진·정보·리뷰의 정규화 계약 — 수집 채널 무관.
    LLM 키 미설정 시 규칙 기반 스텁으로 응답한다 (source 필드로 구분).
    """
    return mkt.generate_store_marketing(profile.model_dump())


@router.get("/{district_id}", response_model=Marketing)
async def get_marketing(district_id: str) -> dict:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠).

    TODO: Platform 수집 정보(gold/program_content_context) 기반 생성으로 교체.
    """
    m = mkt.get_district_marketing(district_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return m
