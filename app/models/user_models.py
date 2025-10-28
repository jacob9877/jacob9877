from enum import Enum

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

from app.models.common_models import EmailConstrained, StrStripWhitespace


class Role(Enum):
    CLINICIAN = "clinician"
    PATIENT = "patient"


class Condition(Enum):
    BREAST_CANCER = "breast-cancer"
    PEDIATRIC_APPENDICITIS = "pediatric-appendicitis"


class RoleAndCondition(BaseModel):
    role: Role = Field(example=Role.PATIENT)
    condition: Condition | None = Field(default=None, example=Condition.BREAST_CANCER)

    @model_validator(mode="after")
    def validate_role_condition(self) -> Self:
        if self.role == Role.CLINICIAN and self.condition is not None:
            raise ValueError("condition must be None/NULL when role is clinician")
        if self.role == Role.PATIENT and self.condition is None:
            raise ValueError("condition must not be None/NULL when role is patient")
        return self


class PasswordResetRequest(BaseModel):
    email: EmailConstrained


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class UserSummary(BaseModel):
    first_name: StrStripWhitespace = Field(..., example="John")
    last_name: StrStripWhitespace = Field(..., example="Doe")
    email: EmailConstrained = Field(..., example="user@example.com")


ASCII_NO_SPACE = (
    r"^[\x21-\x7E]+$"  # Password policy: Restrict to printable ASCII, no spaces
)


class RegisterRequest(UserSummary, RoleAndCondition):
    password: str = Field(
        ...,
        example="password123",
        min_length=3,
        max_length=128,
        pattern=ASCII_NO_SPACE,
    )


class User(UserSummary, RoleAndCondition):
    """Database model for users table"""

    id: int
    password_hash: str
