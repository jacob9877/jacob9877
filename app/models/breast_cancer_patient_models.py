from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.common_models import PaginatedResults


class BreastCancerPatientFeatures(BaseModel):
    mean_radius: float = Field(..., gt=0, example=13.54)
    mean_texture: float = Field(..., gt=0, example=14.36)
    mean_perimeter: float = Field(..., gt=0, example=87.46)
    mean_area: float = Field(..., gt=0, example=566.3)
    mean_smoothness: float = Field(..., gt=0, example=0.09779)


FEATURE_NAMES = list(BreastCancerPatientFeatures.model_fields.keys())


class AddBreastCancerPatientsRequest(BaseModel):
    patients: list[BreastCancerPatientFeatures] = Field(
        ..., min_items=1, description="List of breast cancer patients to add"
    )


# Should be identical to the schema of the database
class BreastCancerPatient(BreastCancerPatientFeatures):
    id: int = Field(..., description="ID of the breast cancer patient", example=1)
    user_id: int = Field(
        ..., description="ID of the user who owns this patient record", example=1
    )
    diagnosis: Literal[0, 1] = Field(
        ..., description="Diagnosis: 0 for benign, 1 for malignant", example=1
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the patient was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the patient was last updated"
    )


class Contribution(BaseModel):
    feature: str = Field(
        ...,
        description="Name of the input feature whose contribution is being measured",
        example="mean_radius",
    )
    value: float = Field(
        ...,
        description="The SHAP value for this feature, i.e. how much this feature contributed (positively or negatively) to the model's predicted output relative to the expected value",
        example=-0.2433918755553244,
    )
    magnitude: float = Field(
        ...,
        description="The absolute value of the SHAP value. Indicates the strength of the feature's influence on the prediction",
        example=0.2433918755553244,
    )
    direction: Literal["up", "down"] = Field(
        ...,
        description="'up' if value > 0: the feature increased the prediction. 'down' if value < 0: the feature decreased the prediction",
        example="down",
    )


class Explanation(BaseModel):
    probability: float = Field(
        ...,
        description="The model's raw predicted probability output",
        example=0.42398,
        ge=0,
        le=1,
    )
    threshold: float = Field(
        ...,
        description="The classification threshold used to determine the final diagnosis",
        example=0.34157,
        ge=0,
        le=1,
    )
    diagnosis: Literal[0, 1] = Field(
        ...,
        description="Final binary classification: 1 if probability >= threshold, else 0. 0 for benign, 1 for malignant",
        example=1,
    )
    expected_value: float = Field(
        ...,
        description="The model's baseline output before any feature contributions (i.e., average prediction over the training set)",
        example=0.51842,
        ge=0,
        le=1,
    )
    contributions: list[Contribution] = Field(
        ...,
        description="SHAP-based breakdown of how each feature shifted the prediction from the expected value to the final probability",
    )


class UpdateBreastCancerPatientRequest(BaseModel):
    mean_radius: float | None = Field(default=None, gt=0, example=13.54)
    mean_texture: float | None = Field(default=None, gt=0, example=14.36)
    mean_perimeter: float | None = Field(default=None, gt=0, example=87.46)
    mean_area: float | None = Field(default=None, gt=0, example=566.3)
    mean_smoothness: float | None = Field(default=None, gt=0, example=0.09779)


class PaginatedBreastCancerPatients(PaginatedResults):
    patients: list[BreastCancerPatient]
