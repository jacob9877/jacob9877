from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.common_models import (
    ApprovalStatus,
    EmailConstrained,
    PaginatedResults,
    StrStripWhitespace,
)
from app.models.patient_models import PatientBase, PatientUserInfo
from app.utils.medical import (
    calculate_alvarado_score,
    calculate_bmi,
    calculate_neutrophilia,
    calculate_pediatric_appendicits_score,
)

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


class DemographicFeatures(BaseModel):
    Age: float = Field(gt=0, example=12.68)
    Sex: Literal["male", "female"] = Field(example="female")
    Height: float = Field(gt=0, example=148.0, description="Height in centimeters (cm)")
    Weight: float = Field(gt=0, example=37.0, description="Weight in kilograms (kg)")
    BMI: float = Field(
        gt=0,
        example=16.90,
        description="Weight in kilograms (kg) / Height in meters (m)",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_bmi(cls, data: Any) -> Any:
        # Check for truthy height and weight because this executes before validating height and weight were actually provided
        if data.get("Height") and data.get("Weight"):
            data["BMI"] = calculate_bmi(data["Height"], data["Weight"])
        return data


class ScoringFeatures(BaseModel):
    Alvarado_Score: int = Field(
        gte=0,
        lte=10,
        example=4,
        description="Clinical scoring system, value from 0 to 10",
    )
    Paedriatic_Appendicitis_Score: int = Field(
        gte=0,
        lte=10,
        example=3,
        description="Clinical scoring system, value from 0 to 10",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_scores(cls, data: Any) -> Any:
        data["Alvarado_Score"] = calculate_alvarado_score(data)
        data["Paedriatic_Appendicitis_Score"] = calculate_pediatric_appendicits_score(
            data
        )
        return data


class ClinicalFeatures(BaseModel):
    Peritonitis: Literal["no", "local", "generalized"] = Field(
        example="no",
        description="Spasm of abdominal wall muscles detected on palpation, usually a result of inflammation",
    )
    Migratory_Pain: Literal["yes", "no"] = Field(
        example="no",
        description="Abdominal pain; usually starts in epigastrium and moves to the right lower quadrant",
    )
    Lower_Right_Abd_Pain: Literal["yes", "no"] = Field(
        example="yes",
        description="Tenderness in right lower quadrant (RLQ); Right iliac fossa pain detected on palpation",
    )
    Contralateral_Rebound_Tenderness: Literal["yes", "no"] = Field(
        example="yes",
        description="A state in which pain of the contralateral side (usually, the right lower quadrant) is felt on the release of pressure (usually, in the left lower quadrant) over the abdomen",
    )
    Ipsilateral_Rebound_Tenderness: Literal["yes", "no"] = Field(
        example="no",
        description="A state in which pain of the ipsilateral side is felt on the release of pressure over the abdomen",
    )
    Coughing_Pain: Literal["yes", "no"] = Field(
        example="no", description="Cough tenderness: Abdominal pain by forced cough"
    )
    Psoas_Sign: Literal["yes", "no"] = Field(
        example="yes", description="Abdominal pain produced by extension of the hip"
    )
    Nausea: Literal["yes", "no"] = Field(
        example="no",
        description="Feeling of sickness/ejection of contents from stomach through the mouth",
    )
    Loss_of_Appetite: Literal["yes", "no"] = Field(
        example="yes", description="Anorexia: Loss of appetite"
    )
    Body_Temperature: float = Field(
        gte=0,
        example=37.00,
        description="Measured by a thermometer placed in the rectum or in the auditory canal",
    )
    Dysuria: Literal["yes", "no"] = Field(
        example="no", description="Pain or other difficulty during urination"
    )
    Stool: Literal["normal", "diarrhea", "constipation"] = Field(
        example="normal", description="Characteristics of bowel movements"
    )


class LaboratoryFeatures(BaseModel):
    WBC_Count: float = Field(
        gte=0,
        example=7.70,
        description="White blood cell count, 10^3/µl: The number of leucocytes in a unit volume of blood; inflammation parameter",
    )
    RBC_Count: float = Field(
        gte=0,
        example=5.27,
        description="Red blood cell count, /pl: The number of erythrocytes in a unit volume of bood",
    )
    Hemoglobin: float = Field(
        gte=0,
        example=14.80,
        description="Hemoglobin, g/dl: Hemoglobin level; a red protein in the red blood cells that contains iron and is responsible for transporting oxygen",
    )
    RDW: float = Field(
        gte=0,
        example=12.20,
        description="Red cell distribution width, %: A blood test that measures the differences in the volume and size of the erythrocytes",
    )
    Thrombocyte_Count: int = Field(
        gte=0,
        example=254.00,
        description="Thrombocyte count, /nl: The number of platelets in a unit volume of blood",
    )
    Neutrophil_Percentage: float = Field(
        gte=0, example=68.20, description="Mature WBC in the granulocytic series"
    )
    Neutrophilia: Literal["yes", "no"] = Field(
        example="no",
        description="Neutrophilia, >= 75%: Relative neutrophilic leucocytosis, often a result of a bacterial infection",
    )
    Segmented_Neutrophils: float | None = Field(
        default=None,
        gte=0,
        example=None,
        description="Segmented neutrophils, %: Most mature neutrophilic granulocytes present in circulating blood, increased during an inflammatory disorder",
    )
    CRP: int = Field(
        gte=0,
        example=0,
        description="C-reactive protein (CRP), mg/l: Protein produced by the liver, elevated in case of inflammation, infection, or injury",
    )
    Ketones_in_Urine: Literal["no", "+", "++", "+++"] = Field(
        example="++",
        description="Presence of ketone bodies in urine, e.g. in case of anorexia",
    )
    RBC_in_Urine: Literal["no", "+", "++", "+++"] = Field(
        example="+", description="Erythrocytes in urine; Blood in urine"
    )
    WBC_in_Urine: Literal["no", "+", "++", "+++"] = Field(
        example="no",
        description="White blood cells in urine; Leucocytes in urine, e.g., in case of infection",
    )

    @model_validator(mode="before")
    @classmethod
    def fill_neutrophilia(cls, data: Any) -> Any:
        if data.get("Neutrophil_Percentage", None) is not None:
            data["Neutrophilia"] = calculate_neutrophilia(data["Neutrophil_Percentage"])
        return data


class UltrasoundFeatures(BaseModel):
    US_Performed: Literal["yes", "no"] = Field(
        example="yes",
        description="If an abdominal ultrasonography was performed or not",
    )  # Required
    Appendix_on_US: Literal["yes", "no"] | None = Field(
        default=None,
        example="yes",
        description="Visibility of appendix: Detectability of the vermiform appendix during sonographic examination",
    )
    Appendix_Diameter: float | None = Field(
        default=None,
        gte=0,
        example=7.10,
        description="Maximal outer diameter of the appendix in mm",
    )
    Free_Fluids: Literal["yes", "no"] | None = Field(
        default=None,
        example="no",
        description="Free intraperitoneal fluid inside abdomen",
    )
    Appendix_Wall_Layers: Literal["intact", "partially raised", "raised"] | None = (
        Field(
            default=None,
            example="intact",
            description="Appendix layer structure: Distribution and characteristics of appendix layers, e.g., irregular in case of an increasing inflammation",
        )
    )
    Target_Sign: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Axial image of appendix with a fluid-filled center surrounded by echogenic mucosa and submucosa and hypoechoic muscularis",
    )
    Perfusion: Literal["hypoperfused", "hyperperfused", "no"] | None = Field(
        default=None,
        example=None,
        description="Appendix perfusion: Blood flow to the appendix wall",
    )
    Surrounding_Tissue_Reaction: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Inflammation signs in tissue (i.a. in omentum/fat tissue) surrounding appendix",
    )
    Pathological_Lymph_Nodes: Literal["yes", "no"] | None = Field(
        default=None,
        example="yes",
        description="Enlarged and inflamed intra-abdominal lymph nodes",
    )
    # Lymph_Node_Location not accepted due to it having no restrictions on its value
    Bowel_Wall_Thickening: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Edema of the intestinal wall, > 2-3 mm for small bowel wall thickening",
    )
    Ileus: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Sonographic signs of paralytic ileus (e.g., dilated intestinal loops, pendulum peristalsis or absence of peristalsis)",
    )
    Coprostasis: Literal["yes", "no"] | None = Field(
        default=None, example=None, description="Fecal impaction in the colon"
    )
    Meteorism: Literal["yes", "no"] | None = Field(
        default=None, example=None, description="Accumulation of gas in the intestine"
    )
    Enteritis: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Sonographic features of gastroenteritis, e.g. wall thickening of ileum, increased peristalsis",
    )
    Appendicolith: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Presence of fecalith in the appendix, e.g. acoustic shadow",
    )
    Perforation: Literal["yes", "no"] | None = Field(
        default=None, example="no", description="Signs of appendix perforation in US"
    )
    Appendicular_Abscess: Literal["yes", "no"] | None = Field(
        default=None, example="no", description="Appendiceal mass"
    )
    # Abscess_Location not accepted due to it having no restrictions on its value
    Conglomerate_of_Bowel_Loops: Literal["yes", "no"] | None = Field(
        default=None,
        example=None,
        description="Small intestine conglomerate as sign of intraperitoneal inflammation",
    )
    # Gynecological_Findings not accepted due to it having no restrictions on its value


class Features(
    DemographicFeatures,
    ScoringFeatures,
    ClinicalFeatures,
    LaboratoryFeatures,
    UltrasoundFeatures,
): ...


FEATURE_NAMES = list(Features.model_fields.keys())


class Predictions(BaseModel):
    diagnosis: Literal["no appendicitis", "appendicitis"]
    management: Literal["conservative", "surgical"]
    length_of_stay_pred: float
    length_of_stay_pi_lower: float
    length_of_stay_pi_upper: float

    def get_diagnosis_text(self):
        if self.diagnosis == "no appendicitis":
            return "no appendicitis"
        return "appendicitis"

    def get_management_text(self):
        if self.management == "conservative":
            return "conservative"
        return "surgical"

    def get_length_of_stay_text(self, include_interval: bool = True) -> str:
        los_str = f"{self.length_of_stay_pred:.1f} days"
        if include_interval:
            los_str += (
                f", with a 95% chance the actual stay will be between {self.length_of_stay_pi_lower:.1f} and "
                f"{self.length_of_stay_pi_upper:.1f} days"
            )

        return f"Predicted hospital stay: approximately {los_str}"


class Approvals(BaseModel):
    diagnosis_approval_status: ApprovalStatus | None = None
    management_approval_status: ApprovalStatus | None = None
    length_of_stay_approval_status: ApprovalStatus | None = None


class Patient(PatientBase, Features, Predictions, Approvals):
    """Database model for pediatric_appendicitis_patients"""


class ImageBase(BaseModel):
    upload_id: StrStripWhitespace = Field(
        ..., example="f47ac10b-58cc-4372-a567-0e02b2c3d479"
    )
    name: StrStripWhitespace | None = Field(default=None, example="Front view")


class ImageResponse(ImageBase):
    url: StrStripWhitespace = Field(
        ...,
        example="https://pediatric-appendicitis-images.s3.us-east-1.amazonaws.com/key?...",
    )
    created_at: datetime


class GetPatientResponse(Patient, PatientUserInfo):
    def get_patient_title(self) -> str:
        if self.patient_user_info:
            if self.patient_user_info.first_name and self.patient_user_info.last_name:
                return (
                    self.patient_user_info.first_name
                    + " "
                    + self.patient_user_info.last_name
                )
        if self.name:
            return self.name
        return f"Patient {self.id}"


class GetPatientResponseWithImages(GetPatientResponse):
    images: list[ImageResponse]


class UpsertPatientRequest(BaseModel):
    features: Features
    image_uploads: list[ImageBase] | None = Field(
        default=[],
        description="List of upload ids & names associated with pre-signed uploads already completed",
    )
    name: StrStripWhitespace | None = Field(
        default=None,
        example="John Doe",
        description="Optionally set a name/nickname for the patient, this will be overriden if the patient has an account",
    )
    email: EmailConstrained | None = Field(default=None, example="user@example.com")


class S3Uri(BaseModel):
    bucket: str
    key: str


class PaginatedPatients(PaginatedResults):
    patients: list[GetPatientResponse]
