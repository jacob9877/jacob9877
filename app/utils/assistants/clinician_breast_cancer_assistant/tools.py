import json

from fastapi import HTTPException, status
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.utils.db import get_breast_cancer_patient_by_id, get_db_cursor_cm


class GetPatientInfoInput(BaseModel):

    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the breast cancer patient to retrieve information for",
        example=123,
    )


@tool(
    description="Retrieve detailed information about a breast cancer patient given their patient ID. Call this tool when asked about any patient info not having to do with reasoning for the diagnosis.",
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
        patient = get_breast_cancer_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with ID {patient_id} not found",
        )

    if patient.user_id != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

    return patient.model_dump()


class GetPatientExplanationInput(BaseModel):

    patient_id: int = Field(
        ...,
        description="The integer ID (MySQL PK) of the breast cancer patient to retrieve explanation for",
        example=123,
    )


@tool(
    description="Explain a breast cancer patient's diagnosis using SHAP analysis based on their patient ID. Call this tool when asked for any reasoning behind the diagnosis.",
    args_schema=GetPatientExplanationInput,
)
def explain_diagnosis(patient_id: int, *, config: RunnableConfig) -> dict:

    # If the conversation is about a patient, make ture this tool call is about the same patient
    if config["configurable"].get("patient_id") and patient_id != config[
        "configurable"
    ].get("patient_id"):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool input patient_id does not match the patient_id of the conversation scope.",
        )

    with get_db_cursor_cm() as cursor:

        operation = """
            SELECT bce.explanation,
                bcp.user_id
            FROM breast_cancer_explanations AS bce
            JOIN breast_cancer_patients AS bcp
            ON bce.patient_id = bcp.id
            WHERE bce.patient_id = %s
        """
        params = (patient_id,)
        cursor.execute(operation, params)
        row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No explanation for patient with ID {patient_id} found",
        )

    if row["user_id"] != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

    return json.loads(row["explanation"])
