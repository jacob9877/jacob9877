from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, EmailStr, Field, StringConstraints
from typing_extensions import Annotated

T = TypeVar("T")  # Generic type for data models


class ResponseModel(BaseModel, Generic[T]):
    detail: str = ""
    data: T | None = None


class PaginatedResults(BaseModel):
    next_cursor: str | None = Field(default=None, description="...")
    total_count: int


ApprovalStatus = Literal["approved", "rejected"]


EmailConstrained = Annotated[
    EmailStr, StringConstraints(strip_whitespace=True, to_lower=True)
]
StrStripWhitespace = Annotated[str, StringConstraints(strip_whitespace=True)]


class Timestamps(BaseModel):
    created_at: datetime
    updated_at: datetime
