from datetime import datetime

from pydantic import BaseModel, Field


class ClinicalNoteBase(BaseModel):
    id: int
    content: str = Field(..., example="Patient is very cool.")
    created_at: datetime
    updated_at: datetime


class ClinicalNote(ClinicalNoteBase):
    patient_id: int


class UpsertClinicalNoteRequest(BaseModel):
    content: str = Field(..., example="Patient is very cool.")
