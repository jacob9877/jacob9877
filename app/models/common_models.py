from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")  # Generic type for data models


class ResponseModel(BaseModel, Generic[T]):
    detail: str = ""
    data: Optional[T] = None
