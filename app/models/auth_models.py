from enum import Enum

from pydantic import BaseModel, EmailStr, Field

from app.models.user_models import Condition, Role, RoleAndCondition, UserSummary


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(RoleAndCondition):
    sub: str  # int user id as a string
    type: TokenType
    iat: int
    exp: int


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="user@example.com")
    password: str = Field(..., example="password123")


class LoginResponse(BaseModel):
    access_token: str


class RefreshResponse(BaseModel):
    access_token: str


class MeResponse(UserSummary, RoleAndCondition, extra="ignore"): ...
