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

    class Config:
        schema_extra = {
                            "example": {
                                            "user_id": 11,
                                            "patients": [
                                                {
                                                    "mean_radius": 12.1,
                                                    "mean_texture": 14.2,
                                                    "mean_perimeter": 85.1,
                                                    "mean_area": 600.0,
                                                    "mean_smoothness": 0.08,
                                                },
                                                {
                                                    "mean_radius": 15.3,
                                                    "mean_texture": 20.5,
                                                    "mean_perimeter": 100.1,
                                                    "mean_area": 700.3,
                                                    "mean_smoothness": 0.09,
                                                },
                                            ],
                                        }
                        }
