import json
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.common_models import ApprovalStatus, PaginatedResults, PatientBase
from app.models.user_models import UserSummary

ACCEPTED_IMAGE_TYPES = Literal["jpg", "jpeg", "png", "bmp"]
MIME_TYPE_MAPPINGS = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
}


class PostImagesRequest(BaseModel):
    file_types: list[ACCEPTED_IMAGE_TYPES]  # List of accepted image file types


class PresignedPostFields(BaseModel, extra="ignore"):
    """Fields object associated with a pre-signed POST URL. Defining this class is helpful for OpenAPI docs"""

    key: str
    content_type: str = Field(example="image/bmp", alias="Content-Type")
    algorithm: str = Field(example="AWS4-HMAC-SHA256", alias="x-amz-algorithm")
    credential: str = Field(alias="x-amz-credential")
    date: str = Field(alias="x-amz-date")
    policy: str
    signature: str = Field(alias="x-amz-signature")
    security_token: str | None = Field(default=None, alias="x-amz-security-token")


class PresignedUpload(BaseModel):
    upload_id: str = Field(example="f47ac10b-58cc-4372-a567-0e02b2c3d479")
    url: str = Field(
        example="https://pediatric-appendicitis-images.s3.us-east-1.amazonaws.com/"
    )
    fields: PresignedPostFields


class Features(BaseModel):
    # Demographic
    Age: float = Field(gt=0, example=12.68)
    Sex: Literal["male", "female"] = Field(example="female")
    Height: float = Field(gt=0, example=148.0, description="Height in centimeters (cm)")
    Weight: float = Field(gt=0, example=37.0, description="Weight in kilograms (kg)")
    BMI: float = Field(
        gt=0,
        example=16.90,
        description="Weight in kilograms (kg) / Height in meters (m)",
    )

    # Scoring
    Alvarado_Score: int = Field(gte=0, example=4)
    Paedriatic_Appendicitis_Score: int = Field(gte=0, example=3)

    # Clinical
    Peritonitis: Literal["no", "local", "generalized"] = Field(example="no")
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


FEATURE_NAMES = list(Features.model_fields.keys())


class Predictions(BaseModel):
    diagnosis: Literal["no appendicitis", "appendicitis"]
    management: Literal["conservative", "surgical"]
    length_of_stay_pred: float
    length_of_stay_pi_lower: float
    length_of_stay_pi_upper: float


class Approvals(BaseModel):
    diagnosis_approval_status: ApprovalStatus | None = None
    management_approval_status: ApprovalStatus | None = None
    length_of_stay_approval_status: ApprovalStatus | None = None


class Patient(PatientBase, Features, Predictions, Approvals):
    """Database model for pediatric_appendicitis_patients"""


class ImageResponse(BaseModel):
    upload_id: str = Field(example="f47ac10b-58cc-4372-a567-0e02b2c3d479")
    url: str = Field(
        example="https://pediatric-appendicitis-images.s3.us-east-1.amazonaws.com/key?..."
    )


class GetPatientResponse(Patient):
    patient_user_info: UserSummary | None = None

    @field_validator("patient_user_info", mode="before")
    @classmethod
    def load_json_object(cls, value: Any) -> Any:
        """If patient_user_info comes in as stringified JSON, parse it first."""
        if isinstance(value, str):
            return json.loads(value)
        return value


class GetPatientResponseWithImages(GetPatientResponse):
    images: list[ImageResponse]


class UpsertPatientRequest(BaseModel):
    features: Features
    image_upload_ids: list[str] | None = Field(
        default=[],
        description="List of upload ids associated with pre-signed uploads already completed",
    )
    name: str | None = Field(
        default=None,
        example="John Doe",
        description="Optionally set a name/nickname for the patient, this will be overriden if the patient has an account",
    )
    email: EmailStr | None = Field(default=None, example="user@example.com")


class S3Uri(BaseModel):
    bucket: str
    key: str


class PaginatedPatients(PaginatedResults):
    patients: list[GetPatientResponse]
