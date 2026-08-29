"""상권(commercial district) 엔드포인트 — 요약/상세/감성/입점.

거점별 데이터를 백엔드 단일 소스(app/data + app/services/districts)로 제공한다.
프론트엔드는 이 엔드포인트로 정적 임베드를 대체할 수 있다.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.district import DistrictSummary, Posting, Zone
from app.services import districts as svc
from app.services import platform_profile

router = APIRouter()


@router.get("", response_model=list[DistrictSummary])
async def list_districts() -> list[dict]:
    """서울 13 Page 거점 요약(감성·공실·리뷰·Tier 구성) — City Dashboard 용."""
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
    """상권 감성 구역(Platform) — **전 필드가 추정치다**.

    점수(s)·표본수(r)·증감(d)·키워드(f) 모두 app/data/seoul_pages.py 의 시드값이며
    실제로 리뷰를 센 적이 없다. 구역 단위 감성을 만들려면 리뷰 원문 수집이 먼저다:
      - data/crawlers/review_crawler.py 는 NotImplementedError (골격만)
      - 네이버 블로그 코퍼스(17,653건)는 **거점 단위 광고성 스니펫**이라
        324개 구역으로 내릴 수 없고, 감성분석을 돌리면 광고 톤을 재게 된다
    자세한 판단 근거는 docs/spaceos-vibe-build-sequence.md 의 5번 항목 참조.
    """
    zones = svc.get_sentiment(district_id)
    if zones is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return zones


@router.get("/{district_id}/platform")
async def get_platform_profile(district_id: str) -> dict:
    """Platform — "이 상권은 어떤 플랫폼인가" + "어느 자리에 어떤 업소가 들어와야 하나".

    정체성(업종 구성·블로그 키워드·검색 트렌드·수요신호)과 자리 제안(실측 공실 유닛 ×
    GNN 최근접 노드 추천)을 한 응답으로 낸다. 둘 다 없는 거점은 404 —
    "이 거점을 모른다"가 아니라 "이 거점에 Platform 산출물이 없다"는 뜻이며,
    `identity: null` 로 오는 경우(자리는 있는데 컨텍스트만 없다)와 구분된다.

    감성은 여기 없다 — 전부 시드라 정체성의 근거로 쓸 수 없다(`/{거점}/sentiment` 참조).
    """
    p = platform_profile.profile(district_id)
    if p is None:
        raise HTTPException(status_code=404,
                            detail=f"no platform profile for district: {district_id}")
    return p


@router.get("/{district_id}/postings", response_model=list[Posting])
async def get_postings(district_id: str) -> list[dict]:
    """공실 유닛 + 3-Tier 비용-효용 시나리오(Posting)."""
    p = svc.get_postings(district_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return p
