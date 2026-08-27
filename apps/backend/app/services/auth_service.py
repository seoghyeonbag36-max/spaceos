"""가입/로그인/API 키 비즈니스 로직. 가입 = 조직 생성 + 관리자 멤버십 1건(트랜잭션 단위)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token, generate_api_key, hash_api_key, hash_password, verify_password,
)
from app.models.auth import ApiKey, AuditLog, Membership, Org, User


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class ApiKeyNotFound(Exception):
    pass


def signup(db: Session, org_name: str, email: str, password: str) -> tuple[User, Org]:
    email = email.lower()
    if db.execute(select(User).filter_by(email=email)).scalar_one_or_none():
        raise EmailAlreadyRegistered(email)

    org = Org(name=org_name)
    user = User(email=email, hashed_password=hash_password(password))
    db.add_all([org, user])
    db.flush()  # id 채번 — Membership 이 org.id/user.id 를 참조하기 전에 필요

    membership = Membership(org_id=org.id, user_id=user.id, role="admin")
    db.add(membership)
    db.add(AuditLog(org_id=org.id, user_id=user.id, action="signup", detail=email))
    db.commit()
    db.refresh(user)
    db.refresh(org)
    return user, org


def login(db: Session, email: str, password: str) -> tuple[str, User, Org, str]:
    """반환: (access_token, user, org, role). 조직이 여럿이면 첫 멤버십을 쓴다."""
    email = email.lower()
    user = db.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentials(email)

    membership = db.execute(
        select(Membership).filter_by(user_id=user.id)
    ).scalars().first()
    if membership is None:
        raise InvalidCredentials(email)  # 조직 없는 사용자 — 정상 가입 경로로는 안 생긴다

    org = db.get(Org, membership.org_id)
    token = create_access_token(user_id=user.id, org_id=org.id)
    db.add(AuditLog(org_id=org.id, user_id=user.id, action="login", detail=email))
    db.commit()
    return token, user, org, membership.role


# ── API 키 ─────────────────────────────────────────────────────────────────────
# B2B 파일럿은 사람이 브라우저로 들어오는 경로(JWT)와 상대 시스템이 서버에서 부르는
# 경로(API 키) 둘 다 쓴다. 키는 **조직 단위**다 — 담당자가 퇴사해도 연동이 안 끊긴다.


def issue_api_key(db: Session, org_id: str, user_id: str, name: str) -> tuple[ApiKey, str]:
    """반환: (레코드, **원문**). 원문은 이 순간 이후 어디에도 없다."""
    raw, key_hash = generate_api_key()
    rec = ApiKey(org_id=org_id, name=name, key_hash=key_hash)
    db.add(rec)
    db.add(AuditLog(org_id=org_id, user_id=user_id,
                    action="api_key.issue", detail=name))
    db.commit()
    db.refresh(rec)
    return rec, raw


def list_api_keys(db: Session, org_id: str) -> list[ApiKey]:
    return list(db.execute(
        select(ApiKey).filter_by(org_id=org_id).order_by(ApiKey.created_at.desc())
    ).scalars())


def revoke_api_key(db: Session, org_id: str, user_id: str, key_id: str) -> ApiKey:
    """폐기는 삭제가 아니라 `revoked_at` 기록이다 — 감사추적에서 키가 사라지면
    '언제까지 유효했나'를 답할 수 없다(실사 항목 2)."""
    rec = db.execute(
        select(ApiKey).filter_by(id=key_id, org_id=org_id)
    ).scalar_one_or_none()
    if rec is None:
        raise ApiKeyNotFound(key_id)     # 다른 조직의 키도 여기로 떨어진다(존재 여부를 안 흘린다)
    if rec.revoked_at is None:
        rec.revoked_at = datetime.now(timezone.utc)
        db.add(AuditLog(org_id=org_id, user_id=user_id,
                        action="api_key.revoke", detail=rec.name))
        db.commit()
        db.refresh(rec)
    return rec


def resolve_api_key(db: Session, raw: str) -> tuple[Org, ApiKey] | None:
    """원문 키 → (조직, 키). 없거나 폐기됐으면 None.

    해시 컬럼은 unique 인덱스라 동등검색 한 번이다.
    """
    rec = db.execute(
        select(ApiKey).filter_by(key_hash=hash_api_key(raw))
    ).scalar_one_or_none()
    if rec is None or rec.revoked_at is not None:
        return None
    org = db.get(Org, rec.org_id)
    return (org, rec) if org is not None else None
