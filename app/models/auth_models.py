from enum import Enum

from pydantic import BaseModel, Field

from app.models.common_models import EmailConstrained, StrStripWhitespace
from app.models.user_models import RoleAndCondition, UserSummary


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(RoleAndCondition):
    sub: str  # int user id as a string
    type: TokenType
    iat: int
    exp: int


class LoginRequest(BaseModel):
    email: EmailConstrained = Field(
        ..., example=""
    )  # Explicitly set empty string because it makes it easier to log in on the OpenAPI docs
    password: StrStripWhitespace  # Policy: trim leading and trailing whitespace before checking user's password


class LoginResponse(BaseModel):
    access_token: str


class RefreshResponse(BaseModel):
    access_token: str


class MeResponse(UserSummary, RoleAndCondition, extra="ignore"): ...
