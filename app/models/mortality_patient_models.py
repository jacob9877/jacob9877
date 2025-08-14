from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class MortalityPatientFeatures(BaseModel):
    # Demographic features
    age: float = Field(
        ...,
        description="Patient's age in years",
        gt=0,
        example=53,
    )
    height: float = Field(
        ...,
        description="Patient's height in centimeters",
        gt=0,
        example=177.6,
    )
    weight: float = Field(
        ...,
        description="Patient's weight in kilograms",
        gt=0,
        example=80.4,
    )

    # Apache scores
    ventilated_apache: Literal[0, 1] = Field(
        ...,
        description="Mechanical ventilation status in first 24h per APACHE (0 = no, 1 = yes)",
        example=1,
    )
    apache_4a_icu_death_prob: float = Field(
        ...,
        description="APACHE IVa predicted ICU mortality probability",
        example=0.03,
    )
    apache_3j_diagnosis: float = Field(
        ...,
        description="APACHE III (3J) primary diagnosis code (numeric category)",
        gt=0,
        example=501.05,
    )

    # Vital signs
    d1_heartrate_min: float = Field(
        ...,
        description="Minimum heart rate during ICU day 1 (beats/min)",
        gt=0,
        example=72,
    )
    d1_resprate_min: float = Field(
        ...,
        description="Minimum respiratory rate during ICU day 1 (breaths/min)",
        gt=0,
        example=12,
    )
    d1_resprate_max: float = Field(
        ...,
        description="Maximum respiratory rate during ICU day 1 (breaths/min)",
        gt=0,
        example=27,
    )

    # Lab results
    d1_bun_min: float = Field(
        ...,
        description="Minimum blood urea nitrogen during ICU day 1 (mg/dL)",
        gt=0,
        example=23.8,
    )
    d1_hemaglobin_min: float = Field(
        ...,
        description="Minimum hemoglobin during ICU day 1 (g/dL)",
        gt=0,
        example=10.4,
    )
    d1_sodium_max: float = Field(
        ...,
        description="Maximum serum sodium during ICU day 1 (mEq/L)",
        gt=0,
        example=137,
    )


class AddMortalityPatientsRequest(BaseModel):
    user_id: int = Field(
        ..., description="ID of the user adding the patients", example=1
    )
    patients: list[MortalityPatientFeatures] = Field(
        ..., min_items=1, description="List of mortality patients to add"
    )


# Should be identical to the schema of the database
class MortalityPatient(MortalityPatientFeatures):
    id: int = Field(..., description="ID of the mortality patient", example=1)
    user_id: int = Field(
        ..., description="ID of the user who owns this patient record", example=1
    )
    hospital_death: Literal[0, 1] = Field(
        ..., description="Hospital death: 0 for won't die, 1 for will die", example=1
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
        example="weight",
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
        description="The classification threshold used to determine the final classification",
        example=0.34157,
        ge=0,
        le=1,
    )
    diagnosis: Literal[0, 1] = Field(
        ...,
        description="Final binary classification: 1 if probability >= threshold, else 0. 0 for won't die, 1 for will die",
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


class UpdateMortalityPatientRequest(BaseModel):
    # Demographic features
    age: Optional[float] = Field(
        None,
        gt=0,
        le=120,
        example=53,
    )
    height: Optional[float] = Field(
        None,
        gt=30,
        le=250,
        example=177.6,
    )
    weight: Optional[float] = Field(
        None,
        gt=1,
        le=400,
        example=80.4,
    )

    # Apache scores
    ventilated_apache: Optional[Literal[0, 1]] = Field(
        None,
        example=1,
    )
    apache_4a_icu_death_prob: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        example=0.03,
    )
    apache_3j_diagnosis: Optional[float] = Field(
        None,
        gt=0,
        example=501.05,
    )

    # Vital signs
    d1_heartrate_min: Optional[float] = Field(
        None,
        gt=0,
        le=300,
        example=72,
    )
    d1_resprate_min: Optional[float] = Field(
        None,
        ge=0,
        le=80,
        example=12,
    )
    d1_resprate_max: Optional[float] = Field(
        None,
        ge=0,
        le=120,
        example=27,
    )

    # Lab results
    d1_bun_min: Optional[float] = Field(
        None,
        ge=0,
        le=200,
        example=18.0,
    )
    d1_hemaglobin_min: Optional[float] = Field(
        None,
        ge=0,
        le=25,
        example=10.4,
    )
    d1_sodium_max: Optional[float] = Field(
        None,
        ge=100,
        le=200,
        example=144.0,
    )
