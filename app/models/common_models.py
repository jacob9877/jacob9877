from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")  # Generic type for data models


class ResponseModel(BaseModel, Generic[T]):
    detail: str = ""
    data: Optional[T] = None


class PaginatedResults(BaseModel):
    next_cursor: Optional[str] = Field(default=None, description="...")
