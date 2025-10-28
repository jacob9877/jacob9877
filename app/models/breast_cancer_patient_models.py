from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.common_models import (
    ApprovalStatus,
    EmailConstrained,
    PaginatedResults,
    StrStripWhitespace,
)
from app.models.patient_models import PatientBase, PatientUserInfo
from app.utils.medical import calculate_bmi


class Features(BaseModel):
    mean_radius: float = Field(
        ...,
        gt=0,
        example=13.54,
        description="The radius of an individual nucleus is measured by averaging the length of the radial line segments defined by the centroid of the snake and the individual snake points around the nucleus. Measured in pixels.",
    )
    mean_texture: float = Field(
        ...,
        gt=0,
        example=14.36,
        description="The texture of cell nucleus is measured by finding the variance of the gray scale intensities in the component pixels. Measured in gray-level intensity.",
    )
    mean_perimeter: float = Field(
        ...,
        gt=0,
        example=87.46,
        description="The nuclear perimeter of a cell nucleus is the total distance between the snake points. Measured in pixels.",
    )
    mean_area: float = Field(
        ...,
        gt=0,
        example=566.3,
        description="Nuclear area is measured simply by counting the number of pixels on the interior of the snake and adding one-half of the pixels in the perimeter. Measured in pixels squared.",
    )
    mean_smoothness: float = Field(
        ...,
        gt=0,
        example=0.09779,
        description="The smoothness of a nuclear contour is quantified by measuring the difference between the length of the radial line and the mean length of the lines surrounding it. Dimensionless quantity.",
    )


FEATURE_NAMES = list(Features.model_fields.keys())


class Demographics(BaseModel):
    """Other attributes that do not feed into the breast cancer diagnosis prediction"""

    Age: float | None = Field(default=None, gt=0, example=45)
    Sex: Literal["male", "female"] | None = Field(default=None, example="female")
    Height: float | None = Field(
        default=None, example=165.7, description="Height in centimeters (cm)"
    )
    Weight: float | None = Field(
        default=None, example=60.3, description="Weight in kilograms (kg)"
    )
    BMI: float | None = Field(
        default=None,
        example=36.391,
        description="Weight in kilograms (kg) / Height in meters (m)",
    )

    @model_validator(mode="before")
    @classmethod
    def calculate_bmi(cls, data: Any) -> Any:
        if data.get("Height") and data.get("Weight"):
            data["BMI"] = calculate_bmi(data["Height"], data["Weight"])
        return data


DEMOGRAPHICS_NAMES = list(Demographics.model_fields.keys())


class FeaturesAndDemographics(Features, Demographics):
    pass


class UpsertPatientRequest(FeaturesAndDemographics):
    name: StrStripWhitespace | None = Field(
        default=None,
        example="John Doe",
        description="Optionally set a name/nickname for the patient, this will be overriden if the patient has an account",
    )
    email: EmailConstrained | None = Field(default=None, example="user@example.com")


class AddPatientsRequest(BaseModel):
    patients: list[UpsertPatientRequest] = Field(
        ..., min_items=1, description="List of breast cancer patients to add"
    )


class Predictions(BaseModel):
    diagnosis: Literal[0, 1] = Field(
        ..., description="Diagnosis: 0 for benign, 1 for malignant", example=1
    )

    def get_diagnosis_text(self):
        if self.diagnosis == 0:
            return "benign"
        return "malignant"


class Approvals(BaseModel):
    diagnosis_approval_status: ApprovalStatus | None = None


# Should be identical to the schema of the database
class Patient(PatientBase, FeaturesAndDemographics, Predictions, Approvals):
    """Database model for breast_cancer_patients table"""


class GetPatientResponse(Patient, PatientUserInfo): ...


class PaginatedPatients(PaginatedResults):
    patients: list[GetPatientResponse]
