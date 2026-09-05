"""SpaceOS Backend — FastAPI 진입점.

물리적 상권의 디지털 트윈 플랫폼 API 서버.
- 공실 히스토리 / 상권 데이터 제공
- AI 추론 API (LSTM 공실 예측, GNN 업종 추천)
- /maps 에서 지구별 HTML 대시보드 서빙 (StaticFiles)
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title="SpaceOS API",
    description="물리적 상권의 디지털 트윈 플랫폼 (Place → Platform)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# HTML 대시보드 정적 파일 서빙
# Docker: HTML_DIR=/app/html 환경변수로 주입
# 로컬: main.py 기준 상대 경로 ../../../../html
_html_dir = Path(os.getenv("HTML_DIR", Path(__file__).parent.parent.parent.parent / "html"))
if _html_dir.exists():
    app.mount("/maps", StaticFiles(directory=str(_html_dir), html=True), name="maps")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """헬스체크 엔드포인트."""
    return {"status": "ok", "service": "spaceos-backend", "version": "0.1.0"}


# ── 프론트 정적 서빙 (Cloud Run 단일 컨테이너용, 2026-08-28) ──────────────────
# Vercel 에서는 프론트를 플랫폼이 따로 서빙하고 `/api/*` 만 이 함수로 rewrite 했다.
# Cloud Run 은 컨테이너 하나뿐이라 프론트도 여기서 낸다. 그래야 **같은 오리진**이
# 유지되는데, 그게 중요한 이유는 `apps/frontend/src/lib/api.ts` 가 `/api/v1` 을
# **상대경로로 하드코딩**하기 때문이다 — 오리진이 갈리면 프론트가 통째로 깨지고
# CORS 설정까지 따라붙는다. 한 컨테이너로 두면 그 문제가 아예 생기지 않는다.
#
# ⚠ **이 마운트는 반드시 파일 맨 끝**이어야 한다. `"/"` 마운트는 앞에서 안 잡힌
#   경로를 전부 삼키므로, API 라우터·/health·/maps 보다 먼저 등록되면 그것들이
#   가려진다. 라우트는 등록 순서대로 매칭된다.
#
# FRONTEND_DIR 이 없거나 폴더가 없으면 **조용히 건너뛴다** — 로컬 개발은 Vite
# 개발서버(5173)가 프론트를 내고 백엔드는 API 만 내는 구성이라 그게 정상이다.
_frontend_dir_env = os.getenv("FRONTEND_DIR")
if _frontend_dir_env:
    _frontend_dir = Path(_frontend_dir_env)
    if _frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
