from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BreastCancerPatientFeatures(BaseModel):
    mean_radius: float = Field(..., gt=0, example=13.54)
    mean_texture: float = Field(..., gt=0, example=14.36)
    mean_perimeter: float = Field(..., gt=0, example=87.46)
    mean_area: float = Field(..., gt=0, example=566.3)
    mean_smoothness: float = Field(..., gt=0, example=0.09779)


class AddBreastCancerPatientsRequest(BaseModel):
    user_id: int = Field(
        ..., description="ID of the user adding the patients", example=1
    )
    patients: list[BreastCancerPatientFeatures] = Field(
        ..., min_items=1, description="List of breast cancer patients to add"
    )


# Should be identical to the schema of the database
class BreastCancerPatient(BreastCancerPatientFeatures):
    id: int = Field(..., description="ID of the breast cancer patient", example=1)
    user_id: int = Field(
        ..., description="ID of the user who owns this patient record", example=1
    )
    diagnosis: Literal[0, 1] = Field(
        ..., description="Diagnosis: 0 for benign, 1 for malignant", example=1
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the patient was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the patient was last updated"
    )
