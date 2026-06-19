"""SpaceOS Backend — FastAPI 진입점.

물리적 상권의 디지털 트윈 플랫폼 API 서버.
- 공실 히스토리 / 3D 모델 / 상권 데이터 제공
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
