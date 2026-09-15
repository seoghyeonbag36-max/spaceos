"""루트에서 백엔드 ASGI 앱을 노출하는 얇은 진입점.

⚠ **더 이상 프로덕션 진입점이 아니다.** 원래는 Vercel Python 서버리스 함수였고
(`vercel.json` 의 rewrites 가 /api/*, /health 를 여기로 보냈다), 2026-08-28 에
프로덕션이 Cloud Run 으로 옮기면서 실제 기동은 `Dockerfile` → `app.main:app` 이 맡는다.

그래도 지우지 않고 남기는 이유는 **CI 의 최소 의존성 계약** 때문이다:
`.github/workflows/ci.yml` 의 `최소 의존성 임포트` 잡이 루트 `requirements.txt` 만
깔고 이 파일을 import 해, 익명 분석 경로가 pandas·torch·DB 드라이버 없이 도는지를 본다.
서비스 코드가 무거운 의존성을 새로 끌어오면 여기서 먼저 터진다.

로컬 개발은 기존과 동일: cd apps/backend && uvicorn app.main:app --reload
"""
import sys
from pathlib import Path

# 백엔드 패키지(apps/backend/app)를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend"))

from app.main import app  # noqa: E402, F401  (진입점이 ASGI `app` 을 그대로 노출한다)
