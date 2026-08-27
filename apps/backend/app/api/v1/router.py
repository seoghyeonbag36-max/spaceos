"""v1 API 라우터 집계."""
from fastapi import APIRouter, Depends

from app.api.deps import track_access
from app.api.v1 import admin, ai, auth, buildings, districts, heatmap, marketing

# 분석 API 공통 — 자격증명이 오면 신원을 밝히고 사용량을 남긴다(익명은 그대로 통과).
# 여기 한 곳에 걸어야 새 엔드포인트가 계측에서 조용히 빠지지 않는다.
_tracked = [Depends(track_access)]

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(buildings.router, prefix="/buildings", tags=["buildings"],
                          dependencies=_tracked)
api_router.include_router(districts.router, prefix="/commercial-districts", tags=["districts"],
                          dependencies=_tracked)
api_router.include_router(heatmap.router, prefix="/heatmap", tags=["heatmap"],
                          dependencies=_tracked)
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"],
                          dependencies=_tracked)
api_router.include_router(ai.router, prefix="/ai", tags=["ai"], dependencies=_tracked)
# 관리자 전용 — X-Admin-Token 헤더 필수. 공개 지도에 노출하지 않는 운영 지표.
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
