import json
from typing import Literal

from fastapi import HTTPException, status
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.utils.assistants.common_tools import (
    GetPatientsForAttributesInput,
    get_patients_for_attributes,
    get_patients_for_attributes_description,
)
from app.utils.db import get_db_cursor_cm, get_pediatric_appendicitis_patient_by_id

EXPLAIN_DIAGNOSIS_PROMPT = """
You are a clinical AI assistant explaining **why the model predicted this diagnosis**
for a pediatric appendicitis patient.

### Your Task
You will receive model explanation data (e.g., SHAP feature importances) and a list of feature names and meanings.  
Use these to summarize **which clinical features most strongly influenced the model's diagnosis**.

### Model Output
- Prediction type: **Diagnosis -> "Appendicitis" or "No Appendicitis"**

### Instructions
1. Identify the top positive (risk-increasing) and negative (risk-decreasing) features.
2. Use the provided **feature descriptions** to clarify what each feature represents clinically.
3. Format your output in **Markdown**:
   - Start with a concise summary (2-4 bullet points).
   - Follow with a Markdown table showing top features and their effects.
4. If data is missing or unclear, acknowledge that politely.
"""

EXPLAIN_MANAGEMENT_PROMPT = """
You are a clinical AI assistant explaining the **management recommendation**
(conservative vs surgical) for a pediatric appendicitis patient.

### Model Output
- Prediction type: **Management -> "Conservative" or "Surgical"**

### Instructions
1. Identify which features most strongly contributed to the management recommendation.
2. Clarify the clinical meaning of those features using the provided feature descriptions.
3. Present your explanation in **Markdown**:
   - A short summary (2-4 bullet points)
   - A Markdown table of key features and their directional influence.
"""

EXPLAIN_LOS_PROMPT = """
You are explaining the **predicted length of hospital stay (LOS)** for a pediatric appendicitis patient.

### Model Output
- LOS prediction: e.g., **3.2 days (80% CI: 2.5-4.1 days)**

### Instructions
1. Summarize which features contribute to increasing or decreasing LOS.
2. Use **Markdown** format with clear, concise bullet points and tables when helpful.
3. Always provide interpretable, clinician-friendly language.
"""


class GetPatientInfoInput(BaseModel):
    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the pediatric appendicitis patient to retrieve information for",
        example=123,
    )


@tool(
    description="Retrieve detailed information about a pediatric appendicitis patient given their patient ID. Call this tool when asked about any patient info not having to do with reasoning for the diagnosis.",
    args_schema=GetPatientInfoInput,
)
def get_patient_info(patient_id: int, *, config: RunnableConfig) -> dict:
    if config["configurable"].get("patient_id") and patient_id != config[
        "configurable"
    ].get("patient_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
        )

    with get_db_cursor_cm() as cursor:
        patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    if patient.clinician_user_id != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

    return patient.model_dump()


class GetPatientExplanationInput(BaseModel):
    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the pediatric appendicitis patient to retrieve explanation for",
        example=123,
    )
    prediction: Literal["diagnosis", "management", "length_of_stay"] = Field(
        ...,
        description="The prediction to get an explanation for",
        example="diagnosis",
    )


@tool(
    description="Explain a pediatric appendicitis patient's prediction using SHAP analysis based on their patient ID. Call this tool when asked for any reasoning behind the predictions/diagnoses.",
    args_schema=GetPatientExplanationInput,
)
def explain_diagnosis(
    patient_id: int,
    prediction: Literal["diagnosis", "management", "length_of_stay"],
    *,
    config: RunnableConfig,
) -> dict:
    # If the conversation is about a patient, make ture this tool call is about the same patient
    if config["configurable"].get("patient_id") and patient_id != config[
        "configurable"
    ].get("patient_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
        )

    explanation_column = f"{prediction}_explanation"
    if prediction == "length_of_stay":
        prediction_columns = [
            "pap.length_of_stay_pred",
            "pap.length_of_stay_pi_lower",
            "pap.length_of_stay_pi_upper",
        ]
    else:
        prediction_columns = [f"pap.{prediction}"]

    with get_db_cursor_cm() as cursor:
        operation = f"""
            SELECT pae.{explanation_column},
                pap.clinician_user_id,
                {", ".join(prediction_columns)}
            FROM pediatric_appendicitis_explanations AS pae
            JOIN pediatric_appendicitis_patients AS pap
            ON pae.patient_id = pap.id
            WHERE pae.patient_id = %s
        """
        params = (patient_id,)
        cursor.execute(operation, params)
        row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation for patient with ID {patient_id} found",
        )

    if row["clinician_user_id"] != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

    row.pop("clinician_user_id")
    row[explanation_column] = json.loads(row[explanation_column])
    return row


@tool(
    description=get_patients_for_attributes_description,
    args_schema=GetPatientsForAttributesInput,
)
def get_pediatric_appendicitis_patients_for_attributes(
    name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    *,
    config: RunnableConfig,
) -> list[dict]:
    clinician_user_id = config["configurable"]["user_id"]

    return get_patients_for_attributes(
        clinician_user_id,
        "pediatric_appendicitis_patients",
        name,
        first_name,
        last_name,
        email,
    )
