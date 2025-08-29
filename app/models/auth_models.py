from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str  # int user id as a string
    type: TokenType
    iat: int
    exp: int


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        ..., description="User's email address", example="user@example.com"
    )
    password: str = Field(..., description="User's password", example="password123")


class LoginResponse(BaseModel):
    access_token: str


class RefreshResponse(BaseModel):
    access_token: str


class MeResponse(BaseModel):
    username: str
    email: str
