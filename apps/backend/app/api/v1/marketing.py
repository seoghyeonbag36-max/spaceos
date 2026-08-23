"""마케팅 엔드포인트 — 가게 단위 생성·조회 + 상권 단위 조회(Program).

⚠ 라우트 등록 순서 주의: 아래 `/{district_id}` 가 아무 문자열이나 삼키므로,
정적 경로(`/generate`·`/places`·`/reviews`)는 **반드시 그보다 먼저** 선언한다.
"""
from fastapi import APIRouter, HTTPException, Query

from app.schemas.district import Marketing
from app.schemas.marketing import (
    StoreMarketing, StorePlaceLookup, StoreProfile, StoreReviewLookup, VacantSiteList,
)
from app.services import marketing as mkt
from app.services import program_site, store_lookup

router = APIRouter()


@router.post("/generate", response_model=StoreMarketing)
async def generate_store_marketing(profile: StoreProfile) -> dict:
    """가게 단위 온/오프라인 마케팅 광고 솔루션 자동 생성.

    입력(StoreProfile)은 상가 사진·정보·리뷰·메뉴의 정규화 계약 — 수집 채널 무관.
    LLM 키 미설정 시 규칙 기반 스텁으로 응답한다 (source 필드로 구분).
    """
    return mkt.generate_store_marketing(profile.model_dump())


@router.get("/places", response_model=StorePlaceLookup)
async def find_places(
    query: str = Query(..., min_length=1, max_length=60, description="가게 상호"),
    district_id: str | None = Query(None, description="거점 — 주면 그 반경을 우선 검색"),
    limit: int = Query(10, ge=1, le=15),
) -> dict:
    """상호로 가게 후보를 찾는다 (카카오 로컬 키워드 검색, 공식 API).

    후보를 그대로 프로필에 넣지 않고 **사람이 고르게** 하는 것이 요점이다 — 같은 상호가
    전국에 있어 자동 선택은 엉뚱한 가게를 집는다. 키 미설정 시 source="unavailable".
    """
    return store_lookup.find_places(query, district_id, limit)


@router.get("/reviews", response_model=StoreReviewLookup)
async def find_reviews(
    name: str = Query(..., min_length=1, max_length=60, description="가게 상호"),
    address: str | None = Query(None, max_length=120, description="선택한 후보의 주소(동 추출용)"),
    limit: int = Query(15, ge=1, le=30),
) -> dict:
    """가게를 언급한 블로그 글의 스니펫을 모은다 (네이버 블로그 검색, 공식 API).

    ⚠ 플레이스 방문자 리뷰가 아니다 — 공식 API 가 없어 블로그로 대신한다.
    address 를 주면 그 동(洞)으로 질의를 좁혀 동명이지 오염을 줄인다.
    """
    return store_lookup.find_reviews(name, address, limit)


@router.get("/sites", response_model=VacantSiteList)
async def list_vacant_sites(
    district_id: str = Query(..., min_length=1, max_length=40, description="거점 id"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """거점의 공실 유닛 목록 — Program 입력 계약 ①층(자리)의 후보다.

    영업 중인 가게를 고르는 `/places` 와 목적이 정반대다: 저기는 이미 있는 가게를
    특정하고, 여기는 **아직 아무도 없는 자리**를 고른다. 대상이 '공실에 창업할 기업'
    으로 재정의되면서(docs/feature-program.md §0-B) 필요해진 표면이다.

    Gold 미적재면 `site_source == "unavailable"` 로 빈 목록을 준다 — 404 가 아니다.
    "이 거점을 모른다"와 "이 거점에 공실 산출물이 없다"는 다른 상태다.
    """
    sites = program_site.units(district_id)[:limit]
    return {"district_id": district_id, "sites": sites,
            **program_site.provenance(district_id)}


@router.get("/{district_id}", response_model=Marketing)
async def get_marketing(district_id: str) -> dict:
    """상권 단위 마케팅(행사 + 온라인 콘텐츠).

    온라인 콘텐츠는 Platform 수집 정보(gold/program_content_context) 기반 생성이며
    LLM 키 미설정·Gold 미적재 시 시드로 폴백한다(source 필드로 구분).
    행사(events)는 서울열린데이터광장 문화행사 실데이터 — events_source 로 출처를 밝힌다.
    """
    m = mkt.get_district_marketing(district_id)
    if m is None:
        raise HTTPException(status_code=404, detail=f"unknown district: {district_id}")
    return m
