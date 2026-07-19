"""Vercel Python 서버리스 진입점 — FastAPI(ASGI) 앱 노출.

vercel.json 의 rewrites 가 /api/*, /health 요청을 이 함수로 보낸다.
함수는 원본 경로 그대로 ASGI 앱에 전달하므로 백엔드 라우트(/api/v1/...)가 그대로 동작한다.
로컬 개발은 기존과 동일: cd apps/backend && uvicorn app.main:app --reload
"""
import sys
from pathlib import Path

# 백엔드 패키지(apps/backend/app)를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend"))

from app.main import app  # noqa: E402, F401  (Vercel 이 ASGI `app` 을 감지)
