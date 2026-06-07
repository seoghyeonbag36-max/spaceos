"""상권(commercial district) 엔드포인트 — 요약/상세/감성/입점.

거점별 데이터를 백엔드 단일 소스(app/data + app/services/districts)로 제공한다.
프론트엔드는 이 엔드포인트로 정적 임베드를 대체할 수 있다.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.district import DistrictSummary, Posting, Zone
from app.services import districts as svc

router = APIRouter()


@router.get("", response_model=list[DistrictSummary])
async def list_districts() -> list[dict]:
    """9거점 요약(감성·공실·리뷰·Tier 구성) — City Dashboard 용."""
    return svc.list_summaries()


@router.get("/{district_id}/summary", response_model=DistrictSummary)
async def get_district_summary(district_id: str) -> dict:
    s = svc.get_summary(district_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return s


@router.get("/{district_id}")
async def get_district(district_id: str) -> dict:
    """거점 전체 원천 데이터(zones/units/events/poi/grid)."""
    d = svc.get_district(district_id)
    if d is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return d


@router.get("/{district_id}/sentiment", response_model=list[Zone])
async def get_sentiment(district_id: str) -> list[dict]:
    """상권 감성 구역(Platform). TODO: SNS 크롤링+감성분석 Gold 연동."""
    zones = svc.get_sentiment(district_id)
    if zones is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return zones


@router.get("/{district_id}/postings", response_model=list[Posting])
async def get_postings(district_id: str) -> list[dict]:
    """공실 유닛 + 3-Tier 비용-효용 시나리오(Posting)."""
    p = svc.get_postings(district_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return p
