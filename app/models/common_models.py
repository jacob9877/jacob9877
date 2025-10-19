from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, EmailStr, Field

T = TypeVar("T")  # Generic type for data models


class ResponseModel(BaseModel, Generic[T]):
    detail: str = ""
    data: T | None = None


class PaginatedResults(BaseModel):
    next_cursor: str | None = Field(default=None, description="...")
    total_count: int


ApprovalStatus = Literal["approved", "rejected"]


class Timestamps(BaseModel):
    created_at: datetime
    updated_at: datetime


class PatientBase(Timestamps):
    """Fields that all patient db records share"""

    id: int
    clinician_user_id: int
    user_id: int | None = None
    pending_email: EmailStr | None = Field(default=None, example="user@example.com")
    name: str | None = Field(default=None, example="John Doe")
