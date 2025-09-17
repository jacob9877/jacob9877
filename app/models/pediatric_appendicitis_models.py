from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.common_models import PaginatedResults


class CreateImagesRequest(BaseModel):
    file_types: list[
        Literal["bmp", "png", "jpg", "jpeg"]
    ]  # List of accepted image file types


class PresignedUpload(BaseModel):
    upload_id: str
    url: str
    fields: dict


class PediatricAppendicitisPatientFeatures(BaseModel):
    # Demographic
    Age: float | None = Field(default=None, gt=0)
    BMI: float | None = Field(default=None, gt=0)
    Sex: Literal["male", "female"] | None
    Height: float | None = Field(default=None, gt=0)
    Weight: float | None = Field(default=None, gt=0)

    # Scoring
    Alvarado_Score: int | None = Field(default=None, gte=0)
    Paedriatic_Appendicitis_Score: int | None = Field(default=None, gte=0)

    # Clinical
    Peritonitis: Literal["yes", "no"] | None = None
    Migratory_Pain: Literal["yes", "no"] | None = None
    Lower_Right_Abd_Pain: Literal["yes", "no"] | None = None
    Contralateral_Rebound_Tenderness: Literal["yes", "no"] | None = None
    Coughing_Pain: Literal["yes", "no"] | None = None
    Nausea: Literal["yes", "no"] | None = None
    Loss_of_Appetite: Literal["yes", "no"] | None = None
    Body_Temperature: float | None = Field(default=None, gte=0)

    # Laboratory
    WBC_Count: float | None = Field(default=None, gte=0)
    Neutrophil_Percentage: float | None = Field(default=None, gte=0)
    CRP: int | None = Field(default=None, gte=0)
    RBC_in_Urine: Literal["no", "+", "++", "+++"] | None = None

    # Ultrasound
    US_Performed: Literal["yes", "no"] | None = None
    Appendix_on_US: Literal["yes", "no"] | None = None
    Appendix_Diameter: float | None = Field(default=None, gte=0)
    Appendix_Wall_Layers: Literal["intact", "partially raised", "raised"] | None = None
    Target_Sign: Literal["yes", "no"] | None = None
    Perfusion: Literal["hypoperfused", "hyperperfused", "no"] | None = None
    Surrounding_Tissue_Reaction: Literal["yes", "no"] | None = None
    Bowel_Wall_Thickening: Literal["yes", "no"] | None = None
    Ileus: Literal["yes", "no"] | None = None
    Enteritis: Literal["yes", "no"] | None = None


class PediatricAppendicitisPatient(PediatricAppendicitisPatientFeatures):
    id: int
    diagnosis: Literal["appendicitis", "no appendicitis"]
    management: Literal["conservative", "surgical"]
    severity: Literal["complicated", "uncomplicated"]
    length_of_stay: float
    length_of_stay_lower: float
    length_of_stay_upper: float
    created_at: datetime
    updated_at: datetime


class PediatricAppendicitisPatientWithImages(PediatricAppendicitisPatient):
    image_urls: list[str] = []


class AddPediatricAppendicitisPatientRequest(BaseModel):
    features: PediatricAppendicitisPatientFeatures
    image_upload_ids: list[str] | None = []


class S3Uri(BaseModel):
    bucket: str
    key: str


class PaginatedPediatricAppendicitisPatients(PaginatedResults):
    results: list[PediatricAppendicitisPatient]
