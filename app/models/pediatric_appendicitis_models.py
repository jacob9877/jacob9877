from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.common_models import PaginatedResults

ACCEPTED_IMAGE_TYPES = Literal["jpg", "jpeg", "png", "bmp"]
MIME_TYPE_MAPPINGS = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
}


class CreateImagesRequest(BaseModel):
    file_types: list[ACCEPTED_IMAGE_TYPES]  # List of accepted image file types


class PresignedPostFields(BaseModel):
    key: str
    content_type: str = Field(example="image/bmp", alias="Content-Type")
    algorithm: str = Field(example="AWS4-HMAC-SHA256", alias="x-amz-algorithm")
    credential: str = Field(alias="x-amz-credential")
    date: str = Field(alias="x-amz-date")
    policy: str
    signature: str = Field(alias="x-amz-signature")
    security_token: str | None = Field(alias="x-amz-security-token")

    class Config:
        extra = "ignore"


class PresignedUpload(BaseModel):
    upload_id: str = Field(example="f47ac10b-58cc-4372-a567-0e02b2c3d479")
    url: str = Field(
        example="https://pediatric-appendicitis-images.s3.us-east-1.amazonaws.com/"
    )
    fields: PresignedPostFields


class PediatricAppendicitisPatientFeatures(BaseModel):
    # Demographic
    Age: float = Field(gt=0, example=12.68)
    Sex: Literal["male", "female"] = Field(example="female")
    Height: float = Field(gt=0, example=148.0)
    Weight: float = Field(gt=0, example=37.0)
    BMI: float = Field(gt=0, example=16.90)

    # Scoring
    Alvarado_Score: int = Field(gte=0, example=4)
    Paedriatic_Appendicitis_Score: int = Field(gte=0, example=3)

    # Clinical
    Peritonitis: Literal["yes", "no"] = Field(example="no")
    Migratory_Pain: Literal["yes", "no"] = Field(example="no")
    Lower_Right_Abd_Pain: Literal["yes", "no"] = Field(example="yes")
    Contralateral_Rebound_Tenderness: Literal["yes", "no"] = Field(example="yes")
    Ipsilateral_Rebound_Tenderness: Literal["yes", "no"] = Field(example="no")
    Coughing_Pain: Literal["yes", "no"] = Field(example="no")
    Psoas_Sign: Literal["yes", "no"] = Field(example="yes")
    Nausea: Literal["yes", "no"] = Field(example="no")
    Loss_of_Appetite: Literal["yes", "no"] = Field(example="yes")
    Body_Temperature: float = Field(gte=0, example=37.00)
    Dysuria: Literal["yes", "no"] = Field(example="no")
    Stool: Literal["normal", "diarrhea", "constipation"] = Field(example="normal")

    # Laboratory
    WBC_Count: float = Field(gte=0, example=7.70)
    RBC_Count: float = Field(gte=0, example=5.27)
    Hemoglobin: float = Field(gte=0, example=14.80)
    RDW: float = Field(gte=0, example=12.20)
    Thrombocyte_Count: int = Field(gte=0, example=254.00)
    Neutrophil_Percentage: float = Field(gte=0, example=68.20)
    Neutrophilia: Literal["yes", "no"] = Field(example="no")
    Segmented_Neutrophils: float | None = Field(default=None, gte=0, example=None)
    CRP: int = Field(gte=0, example=0)
    Ketones_in_Urine: Literal["no", "+", "++", "+++"] = Field(example="++")
    RBC_in_Urine: Literal["no", "+", "++", "+++"] = Field(example="+")
    WBC_in_Urine: Literal["no", "+", "++", "+++"] = Field(example="no")

    # Ultrasound (none required except US_Performed)
    US_Performed: Literal["yes", "no"] = Field(example="yes")  # Required
    Appendix_on_US: Literal["yes", "no"] | None = Field(default=None, example="yes")
    Appendix_Diameter: float | None = Field(default=None, gte=0, example=7.10)
    Free_Fluids: Literal["yes", "no"] | None = Field(default=None, example="no")
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
    Pathological_Lymph_Nodes: Literal["yes", "no"] | None = Field(
        default=None, example="yes"
    )
    # Lymph_Node_Location not accepted due to it having no restrictions on its value
    Bowel_Wall_Thickening: Literal["yes", "no"] | None = Field(
        default=None, example=None
    )
    Ileus: Literal["yes", "no"] | None = Field(default=None, example=None)
    Coprostasis: Literal["yes", "no"] | None = Field(default=None, example=None)
    Meteorism: Literal["yes", "no"] | None = Field(default=None, example=None)
    Enteritis: Literal["yes", "no"] | None = Field(default=None, example=None)
    Appendicolith: Literal["yes", "no"] | None = Field(default=None, example=None)
    Perforation: Literal["yes", "no"] | None = Field(default=None, example="no")
    Appendicular_Abscess: Literal["yes", "no"] | None = Field(
        default=None, example="no"
    )
    # Abscess_Location not accepted due to it having no restrictions on its value
    Conglomerate_of_Bowel_Loops: Literal["yes", "no"] | None = Field(
        default=None, example=None
    )
    # Gynecological_Findings not accepted due to it having no restrictions on its value


FEATURE_NAMES = list(PediatricAppendicitisPatientFeatures.model_fields.keys())


class PediatricAppendicitisPredictions(BaseModel):
    diagnosis: Literal["appendicitis", "no appendicitis"]
    management: Literal["conservative", "surgical"]
    severity: Literal["complicated", "uncomplicated"]
    length_of_stay_pred: float
    length_of_stay_pi_lower: float
    length_of_stay_pi_upper: float


class PediatricAppendicitisPatient(
    PediatricAppendicitisPatientFeatures, PediatricAppendicitisPredictions
):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class ImageResponse(BaseModel):
    upload_id: str = Field(example="f47ac10b-58cc-4372-a567-0e02b2c3d479")
    url: str = Field(
        example="https://pediatric-appendicitis-images.s3.us-east-1.amazonaws.com/key?..."
    )


class PediatricAppendicitisPatientWithImages(PediatricAppendicitisPatient):
    images: list[ImageResponse]


class UpsertPediatricAppendicitisPatientRequest(BaseModel):
    features: PediatricAppendicitisPatientFeatures
    image_upload_ids: list[str] | None = []


class S3Uri(BaseModel):
    bucket: str
    key: str


class PaginatedPediatricAppendicitisPatients(PaginatedResults):
    patients: list[PediatricAppendicitisPatient]

