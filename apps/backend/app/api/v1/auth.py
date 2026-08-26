"""계정층 API — 가입(조직 생성)·로그인·본인 확인.

docs/decision-infra-layer-2026-08-25.md §6 결정 A 의 첫 배선. 분석 API(buildings·
districts·ai·...)는 이 라우터와 무관하게 그대로 공개로 남는다 — 여기서 하는 건
파일럿 온보딩에 필요한 최소 계정 기능이지, 기존 서빙을 인증 뒤로 숨기는 게 아니다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, create_access_token, get_current_user
from app.schemas.auth import LoginRequest, MeResponse, OrgOut, SignupRequest, TokenResponse
from app.services import auth_service

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user, org = auth_service.signup(db, req.org_name, req.email, req.password)
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 가입된 이메일입니다")
    return TokenResponse(access_token=create_access_token(user_id=user.id, org_id=org.id))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token, _user, _org, _role = auth_service.login(db, req.email, req.password)
    except auth_service.InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(
        user_id=current.user.id,
        email=current.user.email,
        org=OrgOut(id=current.org.id, name=current.org.name),
        role=current.role,
    )
