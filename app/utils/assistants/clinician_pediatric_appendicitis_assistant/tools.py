import json
from typing import Literal

from fastapi import HTTPException, status
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.utils.db import get_db_cursor_cm, get_pediatric_appendicitis_patient_by_id


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
    if patient_id != config["configurable"].get("patient_id"):
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

    with get_db_cursor_cm() as cursor:
        operation = f"""
            SELECT pae.{explanation_column},
                pap.clinician_user_id
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

    return json.loads(row[explanation_column])
