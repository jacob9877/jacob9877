from datetime import datetime

from pydantic import BaseModel, Field

from app.models.breast_cancer_patient_models import BreastCancerPatientFeatures


class ClinicianInfo(BaseModel):
    email: str


class GetBreastCancerPatientPortalResponse(BreastCancerPatientFeatures):
    created_at: datetime = Field(
        ..., description="Timestamp when the patient info was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the patient info was last updated"
    )
    clinician: ClinicianInfo
