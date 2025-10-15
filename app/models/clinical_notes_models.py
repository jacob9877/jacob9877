from datetime import datetime

from pydantic import BaseModel


class ClinicalNote(BaseModel):
    id: int
    patient_id: int
    content: str
    created_at: datetime
    updated_at: datetime


class UpsertClinicalNoteRequest(BaseModel):
    content: str
