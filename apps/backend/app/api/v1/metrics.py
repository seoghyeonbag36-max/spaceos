"""클라이언트 타이밍 수집 — KPI② 의 화면 쪽(`지도·건물 상세 로딩 3초`).

## 왜 서버가 받나

백엔드 미들웨어는 **서버 처리시간**만 잰다. 사용자가 체감하는 "지도가 뜨기까지"는
SDK 내려받기·렌더까지 포함하므로 브라우저에서만 잴 수 있다. 그 값을 어딘가 모아야
KPI 가 되고, 이 저장소에는 분석 백엔드가 없으니 여기로 받는다.

## 신뢰 경계 — 서버 지연과 **같은 등급이 아니다**

이 값은 **클라이언트가 스스로 보고한 수치**다. 인증이 없고(공개 앱이 보낸다) 얼마든지
위조할 수 있다. 그래서:

- 이름은 **고정 목록**에서만 받는다. 카디널리티도 막고, 임의 문자열이 관리자 화면에
  찍히는 것도 막는다.
- 값은 클램프한다. 음수·NaN·터무니없이 큰 값은 통계를 통째로 흔든다.
- 저장 키에 `client:` 접두사를 붙여 서버 실측과 **한 화면에서 구분**되게 한다.

즉 이건 제품 신호이지 감사 가능한 지표가 아니다. `/admin/latency` 응답이 그 사실을
`note` 로 밝힌다. 이 구분을 지우지 말 것 — 지우는 순간 자가신고가 실측으로 읽힌다
(`ha_guard` 가 LLM 자기신고를 근거로 안 치는 것과 같은 이유).
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.services import latency as latency_service

router = APIRouter()

# 받는 이름 — 늘릴 때는 화면의 어느 구간인지 한 줄로 적는다.
ALLOWED = {
    "map_ready": "지도 탭을 연 시점 → 네이버 지도 인스턴스 준비 완료",
    "building_detail": "건물 클릭 → 상세 패널 렌더 완료",
}
MAX_MS = 120_000.0     # 2분. 이보다 크면 탭을 방치한 것이지 로딩이 아니다


class ClientTiming(BaseModel):
    metric: str = Field(description=f"고정 목록: {', '.join(ALLOWED)}")
    ms: float = Field(ge=0.0)


# `response_class=Response` 가 필요하다 — 기본 JSONResponse 는 본문을 만들려 하는데
# 204 는 본문을 가질 수 없어 FastAPI 가 등록 단계에서 거부한다.
@router.post("/client", status_code=204, response_class=Response)
def client_timing(body: ClientTiming) -> Response:
    """브라우저가 잰 구간 시간 1건. 모르는 이름은 **조용히 버린다.**

    400 을 돌려주지 않는 이유: 이건 화면 동작과 무관한 비콘이라, 실패를 알려 봐야
    프론트가 할 일이 없고 콘솔만 더럽힌다. 대신 받아들이지도 않는다.
    """
    if body.metric in ALLOWED:
        latency_service.record(f"client:{body.metric}", min(body.ms, MAX_MS))
    return Response(status_code=204)
