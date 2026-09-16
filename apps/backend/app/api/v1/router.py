"""v1 API 라우터 집계."""
from fastapi import APIRouter, Depends

from app.api.deps import track_access
from app.api.v1 import admin, ai, auth, buildings, districts, heatmap, marketing, metrics

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
# 클라이언트 타이밍 비콘 — 공개 앱이 보내므로 인증이 없다. 받는 이름이 고정 목록이고
# 저장 키에 `client:` 가 붙어 서버 실측과 구분된다(metrics.py 독스트링 §신뢰 경계).
# 사용량 계측(_tracked)은 걸지 않는다 — 비콘은 분석 API 사용이 아니다.
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
