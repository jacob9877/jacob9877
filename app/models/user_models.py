from enum import Enum
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator
from typing_extensions import Self


class Role(Enum):
    CLINICIAN = "clinician"
    PATIENT = "patient"


class Condition(Enum):
    BREAST_CANCER = "breast-cancer"
    PEDIATRIC_APPENDICITIS = "pediatric-appendicitis"


class RoleAndCondition(BaseModel):
    role: Role = Field(example="patient")
    condition: Condition | None = Field(default=None, example="breast-cancer")

    @model_validator(mode="after")
    def validate_role_condition(self) -> Self:
        if self.role == "clinician" and self.condition is not None:
            raise ValueError("condition must be None/NULL when role is clinician")
        if self.role == "patient" and self.condition is None:
            raise ValueError("condition must not be None/NULL when role is patient")
        return self


class RegisterRequest(RoleAndCondition):
    first_name: str
    last_name: str
    username: str = Field(..., description="User's username", example="johndoe")
    email: EmailStr = Field(
        ..., description="User's email address", example="johndoe@gmail.com"
    )
    password: str = Field(..., description="User's password", example="password123")


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class User(RoleAndCondition):
    id: int
    first_name: str
    last_name: str
    username: str
    email: str
    password_hash: str


class PatientUserInfo(BaseModel):
    first_name: str
    last_name: str
    email: str
