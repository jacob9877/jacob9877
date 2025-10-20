from enum import Enum

from pydantic import BaseModel, EmailStr, Field, model_validator
from typing_extensions import Self


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
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class UserSummary(BaseModel):
    first_name: str = Field(..., example="John")
    last_name: str = Field(..., example="Doe")
    email: EmailStr = Field(..., example="user@example.com")


class RegisterRequest(UserSummary, RoleAndCondition):
    password: str = Field(..., example="password123")


class User(UserSummary, RoleAndCondition):
    """Database model for users table"""

    id: int
    password_hash: str
