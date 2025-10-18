from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.breast_cancer_patient_models import BreastCancerPatientFeatures
from app.models.pediatric_appendicitis_patient_models import (
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
):
    diagnosis: Literal[0, 1] | None = None


class GetPediatricAppendicitisPatientPortalResponse(
    GetPatientPortalResponseBase, PediatricAppendicitisPatientFeatures
):
    diagnosis: Literal["no appendicitis", "appendicitis"] | None = None
    management: Literal["conservative", "surgical"] | None = None
    length_of_stay_pred: float | None = None
    length_of_stay_pi_lower: float | None = None
    length_of_stay_pi_upper: float | None = None
