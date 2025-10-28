import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self

from app.models.common_models import EmailConstrained, StrStripWhitespace, Timestamps
from app.models.user_models import UserSummary


class PatientBase(Timestamps):
    """Fields that all patient db records share"""

    id: int
    clinician_user_id: int
    user_id: int | None = None
    pending_email: EmailConstrained | None = Field(
        default=None, example="user@example.com"
    )
    name: StrStripWhitespace | None = Field(default=None, example="John Doe")

    @model_validator(mode="after")
    def at_most_one_nonnull(self) -> Self:
        """Ensure at most one of user_id and pending_email are non-null"""
        if self.user_id and self.pending_email:
            raise ValueError("user_id and pending_email cannot both be non-null")
        return self


class PatientUserInfo(BaseModel):
    patient_user_info: UserSummary | None = None

    @field_validator("patient_user_info", mode="before")
    @classmethod
    def load_json_object(cls, value: Any) -> Any:
        """If patient_user_info comes in as stringified JSON, parse it first."""
        if isinstance(value, str):
            return json.loads(value)
        return value


class SetPatientEmailRequest(BaseModel):
    email: EmailConstrained = Field(..., example="user@example.com")
