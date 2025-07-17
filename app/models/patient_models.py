from typing import List
from pydantic import BaseModel, Field


class AddPatient(BaseModel):
    mean_radius: float = Field(..., gt=0)
    mean_texture: float = Field(..., gt=0)
    mean_perimeter: float = Field(..., gt=0)
    mean_area: float = Field(..., gt=0)
    mean_smoothness: float = Field(..., gt=0)


class AddPatientRequest(AddPatient):
    user_id: int


class AddPatientPayload(BaseModel):
    user_id: int
    patients: List[AddPatient]

