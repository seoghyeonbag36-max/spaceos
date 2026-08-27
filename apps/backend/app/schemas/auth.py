"""계정층 요청/응답 스키마 — 가입은 곧 조직 생성이다(개인 계정 없음)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrgOut(BaseModel):
    id: str
    name: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    org: OrgOut
    role: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100,
                      description="용도 식별용 이름 — 어디에 쓴 키인지 나중에 알아보려면 필요하다")


class ApiKeyOut(BaseModel):
    """목록·폐기 응답. **원문(key)은 없다** — 발급 응답에만 한 번 실린다."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    created_at: datetime
    revoked_at: datetime | None = None


class ApiKeyCreatedResponse(ApiKeyOut):
    key: str = Field(description="원문 키. 이 응답에서만 볼 수 있고 서버에 저장되지 않는다")
