"""비밀번호 해싱 + JWT 발급/검증. 계정층 전용 — 분석 API 인증과는 무관하다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.auth import Membership, Org, User

_bearer = HTTPBearer(auto_error=False)


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
