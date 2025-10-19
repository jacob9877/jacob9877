from pydantic import BaseModel, Field

from app.models.common_models import Timestamps


class UpsertClinicalNoteRequest(BaseModel):
    content: str = Field(..., example="Patient is very cool.")


class GetClinicalNoteResponse(UpsertClinicalNoteRequest, Timestamps):
    id: int


class ClinicalNote(GetClinicalNoteResponse):
    """Database model for *_clinical_notes tables"""

    patient_id: int
