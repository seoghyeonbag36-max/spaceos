"""관리자 전용 API — 운영 지표. 공개 지도에 노출하지 않는 정보만 다룬다.

배경(2026-07-26): Page 공실 레이어는 건축물대장에서 capacity 를 얻은 건물만 그린다.
대장 미확인 건물은 지도에서 빠지는데(연남동 433동), 이 사실이 공개 화면에는 드러나지
않는다. Tier2 근사로 채워 넣으면 근거가 다른 데이터가 한 지도에 섞여 "대장 기반 실측"
논증이 무너지므로, 채우는 대신 **제외 사실을 관리자만 볼 수 있게** 분리한다.

인증: ADMIN_TOKEN 환경변수와 X-Admin-Token 헤더 일치. 미설정이면 라우터 전체가 403 —
토큰을 깜빡한 배포에서 운영 지표가 공개되는 것보다 안 열리는 편이 안전하다(fail-closed).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import usage as usage_service

router = APIRouter()

# repo/data/gold  (v1 → api → app → backend → apps → repo)
_GOLD_DIR = Path(__file__).resolve().parents[5] / "data" / "gold"


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """관리자 토큰 검증. 토큰 미설정 시에도 통과시키지 않는다."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=403,
                            detail="ADMIN_TOKEN 미설정 — 관리자 API 가 비활성화되어 있습니다")
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="관리자 토큰이 올바르지 않습니다")


@router.get("/coverage", dependencies=[Depends(require_admin)])
def coverage() -> dict:
    """거점별 지도 커버리지 — 표시 동수와 제외 동수(대장 미확인/비상업).

    build_page_master 가 남긴 gold/{slug}/coverage.json 을 모아서 돌려준다.
    """
    hubs = []
    for path in sorted(_GOLD_DIR.glob("*/coverage.json")):
        try:
            hubs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    shown = sum(h.get("shown") or 0 for h in hubs)
    unknown = sum(h.get("excluded_unknown") or 0 for h in hubs)
    non_comm = sum(h.get("excluded_non_commercial") or 0 for h in hubs)
    total = shown + unknown + non_comm
    return {
        "hubs": sorted(hubs, key=lambda h: -(h.get("excluded_unknown") or 0)),
        "totals": {
            "hubs": len(hubs),
            "shown": shown,
            "excluded_unknown": unknown,
            "excluded_non_commercial": non_comm,
            "coverage_pct": round(shown / total * 100, 1) if total else None,
        },
    }


@router.get("/usage", dependencies=[Depends(require_admin)])
def usage(days: int = 30, db: Session = Depends(get_db)) -> dict:
    """조직별 분석 API 사용량 — KPI② (B2B 파일럿) 를 재는 유일한 관측 지점.

    `active_orgs` 가 목표 5~10건에 대응한다. 값이 0 인데 파일럿이 있다고 알고 있다면
    둘 중 하나다: ① 파일럿이 자격증명 없이(익명으로) 쓰고 있다 ② 기록이 실패하고 있다
    (`services/usage.record_access` 의 경고 로그를 볼 것). **둘 다 조용히 0 으로
    보이므로** 이 엔드포인트가 그 구분을 드러내는 자리다.
    """
    return usage_service.usage_summary(db, days=days)
