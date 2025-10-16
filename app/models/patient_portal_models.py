from datetime import datetime

from pydantic import BaseModel, Field

from app.models.breast_cancer_patient_models import BreastCancerPatientFeatures
from app.models.pediatric_appendicitis_models import (
    PediatricAppendicitisPatientFeatures,
)


class ClinicianInfo(BaseModel):
    email: str


class GetPatientPortalResponseBase(BaseModel):
    created_at: datetime = Field(
        ..., description="Timestamp when the patient info was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the patient info was last updated"
    )
    clinician: ClinicianInfo


class GetBreastCancerPatientPortalResponse(
    GetPatientPortalResponseBase, BreastCancerPatientFeatures
): ...


class GetPediatricAppendicitisPatientPortalResponse(
    GetPatientPortalResponseBase, PediatricAppendicitisPatientFeatures
): ...
