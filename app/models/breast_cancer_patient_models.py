from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.common_models import ApprovalStatus, PaginatedResults


class BreastCancerPatientFeatures(BaseModel):
    mean_radius: float = Field(..., gt=0, example=13.54)
    mean_texture: float = Field(..., gt=0, example=14.36)
    mean_perimeter: float = Field(..., gt=0, example=87.46)
    mean_area: float = Field(..., gt=0, example=566.3)
    mean_smoothness: float = Field(..., gt=0, example=0.09779)


FEATURE_NAMES = list(BreastCancerPatientFeatures.model_fields.keys())


class AddBreastCancerPatientsRequest(BaseModel):
    patients: list[BreastCancerPatientFeatures] = Field(
        ..., min_items=1, description="List of breast cancer patients to add"
    )


class AddBreastCancerPatientRequest(BreastCancerPatientFeatures):
    email: EmailStr | None = None


class BreastCancerApprovals(BaseModel):
    diagnosis_approval_status: ApprovalStatus | None = None


# Should be identical to the schema of the database
class BreastCancerPatient(BreastCancerPatientFeatures, BreastCancerApprovals):
    id: int = Field(..., description="ID of the breast cancer patient", example=1)
    clinician_user_id: int = Field(
        ...,
        description="user ID of the clinician who this patient belongs to",
        example=1,
    )
    user_id: int | None = None
    pending_email: str | None = None
    diagnosis: Literal[0, 1] = Field(
        ..., description="Diagnosis: 0 for benign, 1 for malignant", example=1
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the patient was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the patient was last updated"
    )


class UpdateBreastCancerPatientRequest(BaseModel):
    mean_radius: float | None = Field(default=None, gt=0, example=13.54)
    mean_texture: float | None = Field(default=None, gt=0, example=14.36)
    mean_perimeter: float | None = Field(default=None, gt=0, example=87.46)
    mean_area: float | None = Field(default=None, gt=0, example=566.3)
    mean_smoothness: float | None = Field(default=None, gt=0, example=0.09779)
    email: EmailStr | None = None


class PaginatedBreastCancerPatients(PaginatedResults):
    patients: list[BreastCancerPatient]
