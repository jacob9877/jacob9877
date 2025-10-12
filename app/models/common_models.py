from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")  # Generic type for data models


class ResponseModel(BaseModel, Generic[T]):
    detail: str = ""
    data: T | None = None


class PaginatedResults(BaseModel):
    next_cursor: str | None = Field(default=None, description="...")
    total_count: int
