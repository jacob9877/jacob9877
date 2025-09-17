from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.common_models import PaginatedResults

MIME_TYPE_MAPPINGS = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
}


class CreateImagesRequest(BaseModel):
    file_types: list[
        Literal["jpg", "jpeg", "png", "bmp"]
    ]  # List of accepted image file types


class PresignedUpload(BaseModel):
    upload_id: str
    url: str
    fields: dict


class PediatricAppendicitisPatientFeatures(BaseModel):
    # Demographic
    Age: float | None = Field(default=None, gt=0, example=12.68)
    BMI: float | None = Field(default=None, gt=0, example=16.90)
    Sex: Literal["male", "female"] | None = Field(example="female")
    Height: float | None = Field(default=None, gt=0, example=148.0)
    Weight: float | None = Field(default=None, gt=0, example=37.0)

    # Scoring
    Alvarado_Score: int | None = Field(default=None, gte=0, example=4)
    Paedriatic_Appendicitis_Score: int | None = Field(default=None, gte=0, example=3)

    # Clinical
    Peritonitis: Literal["yes", "no"] | None = Field(default=None, example="no")
    Migratory_Pain: Literal["yes", "no"] | None = Field(default=None, example="no")
    Lower_Right_Abd_Pain: Literal["yes", "no"] | None = Field(
        default=None, example="yes"
    )
    Contralateral_Rebound_Tenderness: Literal["yes", "no"] | None = Field(
        default=None, example="yes"
    )
    Coughing_Pain: Literal["yes", "no"] | None = Field(default=None, example="no")
    Nausea: Literal["yes", "no"] | None = Field(default=None, example="no")
    Loss_of_Appetite: Literal["yes", "no"] | None = Field(default=None, example="yes")
    Body_Temperature: float | None = Field(default=None, gte=0, example=37.00)

    # Laboratory
    WBC_Count: float | None = Field(default=None, gte=0, example=7.70)
    Neutrophil_Percentage: float | None = Field(default=None, gte=0, example=68.20)
    CRP: int | None = Field(default=None, gte=0, example=0)
    RBC_in_Urine: Literal["no", "+", "++", "+++"] | None = Field(
        default=None, example="+"
    )

    # Ultrasound
    US_Performed: Literal["yes", "no"] | None = Field(default=None, example="yes")
    Appendix_on_US: Literal["yes", "no"] | None = Field(default=None, example="yes")
    Appendix_Diameter: float | None = Field(default=None, gte=0, example=7.10)
    Appendix_Wall_Layers: Literal["intact", "partially raised", "raised"] | None = (
        Field(default=None, example="intact")
    )
    Target_Sign: Literal["yes", "no"] | None = Field(default=None, example=None)
    Perfusion: Literal["hypoperfused", "hyperperfused", "no"] | None = Field(
        default=None, example=None
    )
    Surrounding_Tissue_Reaction: Literal["yes", "no"] | None = Field(
        default=None, example=None
    )
    Bowel_Wall_Thickening: Literal["yes", "no"] | None = Field(
        default=None, example=None
    )
    Ileus: Literal["yes", "no"] | None = Field(default=None, example=None)
    Enteritis: Literal["yes", "no"] | None = Field(default=None, example=None)


FEATURE_NAMES = list(PediatricAppendicitisPatientFeatures.model_fields.keys())


class PediatricAppendicitisPatient(PediatricAppendicitisPatientFeatures):
    id: int
    user_id: int
    diagnosis: Literal["appendicitis", "no appendicitis"]
    management: Literal["conservative", "surgical"]
    severity: Literal["complicated", "uncomplicated"]
    length_of_stay_pred: float
    length_of_stay_pi_lower: float
    length_of_stay_pi_upper: float
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
