from datetime import datetime

from pydantic import BaseModel, Field


class UpsertClinicalNoteRequest(BaseModel):
    content: str = Field(..., example="Patient is very cool.")


class GetClinicalNoteResponse(UpsertClinicalNoteRequest):
    id: int
    created_at: datetime
    updated_at: datetime


class ClinicalNote(GetClinicalNoteResponse):
    """Database model for *_clinical_notes tables"""

    patient_id: int
