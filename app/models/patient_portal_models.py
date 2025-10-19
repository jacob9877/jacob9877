from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.breast_cancer_patient_models import Features as BreastCancerFeatures
from app.models.pediatric_appendicitis_patient_models import (
    Features as PediatricAppendicitisFeatures,
)
from app.models.common_models import Timestamps
from app.models.user_models import UserSummary


class GetPatientPortalResponseBase(Timestamps):
    clinician_user_info: UserSummary


class GetBreastCancerPatientPortalResponse(
    GetPatientPortalResponseBase, BreastCancerFeatures
):
    diagnosis: Literal[0, 1] | None = None


class GetPediatricAppendicitisPatientPortalResponse(
    GetPatientPortalResponseBase, PediatricAppendicitisFeatures
):
    diagnosis: Literal["no appendicitis", "appendicitis"] | None = None
    management: Literal["conservative", "surgical"] | None = None
    length_of_stay_pred: float | None = None
    length_of_stay_pi_lower: float | None = None
    length_of_stay_pi_upper: float | None = None
