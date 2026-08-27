"""비밀번호 해싱 + JWT 발급/검증 + API 키 발급/검증."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.auth import Membership, Org, User

_bearer = HTTPBearer(auto_error=False)

# B2B 연동이 헤더에 실어 보내는 키의 접두사 — 로그·유출 스캐너가 알아보게 한다.
API_KEY_PREFIX = "sk_spaceos_"


def _bytes72(raw: str) -> bytes:
    # bcrypt 는 72바이트를 넘으면 예외를 던진다(4.x). 한글 비밀번호(멀티바이트)가
    # 200자 제한(schemas/auth.py) 안에서도 넘을 수 있어 여기서 안전하게 자른다.
    return raw.encode("utf-8")[:72]


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_bytes72(raw), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_bytes72(raw), hashed.encode("utf-8"))
    except ValueError:
        return False  # 해시 형식이 깨진 경우 — 위조된 값일 수 있으니 그냥 거절


def generate_api_key() -> tuple[str, str]:
    """(원문, 해시) — 원문은 발급 응답에서 한 번만 노출하고 저장하지 않는다.

    ⚠ **비밀번호와 달리 bcrypt 를 쓰지 않는다.** 이유는 보안을 낮춘 게 아니라 위협이
    다르기 때문이다: 비밀번호는 사람이 고른 저엔트로피 값이라 사전공격을 늦출 느린
    해시가 필요하지만, 이 키는 `secrets.token_hex(32)` = **256비트 난수**라 사전공격
    대상이 아니다. 반대로 이 해시는 **요청마다** 돌아가므로(비밀번호는 로그인 때만)
    bcrypt 를 쓰면 p95 <200ms 목표를 API 키 경로에서 혼자 깎아먹는다.
    같은 이유로 조회도 해시 컬럼 인덱스 동등검색 한 번이다(전수 스캔 아님).
    """
    raw = API_KEY_PREFIX + secrets.token_hex(32)
    return raw, hash_api_key(raw)


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, org_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "org_id": org_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


class CurrentUser:
    """인증된 요청 컨텍스트 — 사용자 + 그 요청이 어느 조직으로 스코프됐는지."""

    def __init__(self, user: User, org: Org, role: str):
        self.user = user
        self.org = org
        self.role = role


class Principal:
    """분석 API 를 부른 주체. 사람(JWT)일 수도 시스템(API 키)일 수도 있다.

    `CurrentUser` 와 나눠 둔 이유: 계정층 API 는 **사람**이어야 하지만(멤버십·역할이
    필요하다), 분석 API 는 조직만 알면 된다. API 키에는 사람이 없으므로 `user` 가 None
    일 수 있고, 그 차이를 타입으로 드러내지 않으면 호출부가 `principal.user.email` 로
    터진다.
    """

    def __init__(self, org: Org, user: User | None, via: str, api_key_id: str | None = None):
        self.org = org
        self.user = user
        self.via = via                  # "jwt" | "api_key"
        self.api_key_id = api_key_id


def get_optional_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Principal | None:
    """자격증명이 **있으면** 신원을 밝히고, 없으면 None 을 준다(익명 허용).

    분석 API 를 인증 뒤로 숨기지 않는 이유: 공개 데모가 파일럿 영업의 입구이고,
    지금 프론트는 로그인을 하지 않는다. 전부 잠그면 제품이 안 보인다.
    대신 **누가 불렀는지 알 수 있을 때는 기록**해서, 파일럿 사용량(KPI② 의 원천
    데이터)을 셀 수 있게 한다.

    ⚠ 익명 요청은 **DB 를 건드리지 않는다.** `get_db` 가 만드는 Session 은 지연 연결이라
    (core/db.py) 질의를 하지 않는 한 커넥션이 안 열린다 — 분석 API 가 DB 없이 도는
    현재 동작이 그대로 유지된다. 자격증명이 실제로 올 때만 조회가 일어난다.

    ⚠ 잘못된 자격증명은 **거절한다**(401). 조용히 익명으로 강등하면, 키가 만료된 파일럿이
    계속 200 을 받으면서 사용량 집계에서는 사라진다 — 고장이 지표로 안 보이는 모양이다.
    """
    if x_api_key:
        # 지역 임포트로 순환을 피한다(auth_service 가 이 모듈을 임포트한다). 키 해석을
        # 여기 다시 구현하지 않는 이유: 두 곳에서 따로 판정하면 한쪽만 고쳐졌을 때
        # "발급 화면에선 폐기됐는데 API 는 계속 통과" 같은 모순이 조용히 생긴다.
        from app.services.auth_service import resolve_api_key  # noqa: PLC0415

        found = resolve_api_key(db, x_api_key)
        if found is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API 키가 유효하지 않습니다")
        org, rec = found
        return Principal(org=org, user=None, via="api_key", api_key_id=rec.id)

    if creds is None:
        return None                     # 익명 — 여기서 끝난다(DB 접근 없음)

    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret,
                              algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 유효하지 않습니다")
    user = db.get(User, payload.get("sub"))
    org = db.get(Org, payload.get("org_id"))
    if user is None or org is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰의 계정이 존재하지 않습니다")
    return Principal(org=org, user=user, via="jwt")


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "인증 토큰이 필요합니다")
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret,
                              algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 유효하지 않습니다")

    user = db.get(User, payload.get("sub"))
    org = db.get(Org, payload.get("org_id"))
    if user is None or org is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰의 계정이 존재하지 않습니다")
    membership = db.query(Membership).filter_by(user_id=user.id, org_id=org.id).first()
    if membership is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이 조직에 대한 멤버십이 없습니다")
    return CurrentUser(user=user, org=org, role=membership.role)
