"""가입/로그인 비즈니스 로직. 가입 = 조직 생성 + 관리자 멤버십 1건(트랜잭션 단위)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth import AuditLog, Membership, Org, User


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
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
