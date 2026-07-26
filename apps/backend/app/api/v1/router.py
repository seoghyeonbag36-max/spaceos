"""v1 API 라우터 집계."""
from fastapi import APIRouter

from app.api.v1 import admin, ai, buildings, districts, heatmap, marketing

api_router = APIRouter()
api_router.include_router(buildings.router, prefix="/buildings", tags=["buildings"])
api_router.include_router(districts.router, prefix="/commercial-districts", tags=["districts"])
api_router.include_router(heatmap.router, prefix="/heatmap", tags=["heatmap"])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
# 관리자 전용 — X-Admin-Token 헤더 필수. 공개 지도에 노출하지 않는 운영 지표.
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
