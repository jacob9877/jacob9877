from datetime import datetime

from pydantic import BaseModel


class ClinicalNoteBase(BaseModel):
    id: int
    content: str
    created_at: datetime
    updated_at: datetime


class ClinicalNote(ClinicalNoteBase):
    patient_id: int


class UpsertClinicalNoteRequest(BaseModel):
    content: str
