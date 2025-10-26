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

    if patient.clinician_user_id != config["configurable"].get("user_id"):
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
                bcp.clinician_user_id,
                bcp.diagnosis
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

    if row["clinician_user_id"] != config["configurable"].get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to access this patient's data",
        )

    row.pop("clinician_user_id")
    row["explanation"] = json.loads(row["explanation"])
    return row


class GetPatientsForAttributes(BaseModel):
    name: str | None = Field(
        default=None,
        description="Patient nickname",
        example="John Doe",
    )

    first_name: str | None = Field(
        default=None, description="Patient's first name", example="John"
    )

    last_name: str | None = Field(
        default=None, description="Patient's first name", example="Doe"
    )

    email: str | None = Field(default=None, description="johndoe@example.com")


@tool(
    description=(
        "Get a subset of information about patients that satisfy the attributes. "
        "Use to retrieve patient IDs a clinician is looking for. All attributes are optional. "
        "If none are provided however, raises an error."
    ),
    args_schema=GetPatientsForAttributes,
)
def get_patients_for_attributes(
    name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    *,
    config: RunnableConfig,
) -> list[dict]:
    clinician_user_id = config["configurable"]["user_id"]

    # If name isn't provided, fall back to concatenation of first/last (searches p.name)
    if not name:
        parts: list[str] = []
        if first_name:
            parts.append(first_name)
        if last_name:
            parts.append(last_name)
        name = " ".join(parts) if parts else None

    # BOOLEAN MODE query allowing prefix matches (no + => tokens are optional, improves recall)
    def to_boolean_prefix_query(s: str) -> str:
        tokens = [t for t in s.split() if t]
        return " ".join(f"{t}*" for t in tokens)

    ors: list[str] = []
    params: tuple = (clinician_user_id,)

    operation = """
        SELECT
            p.id,
            p.name,
            CASE
                WHEN p.user_id IS NULL THEN NULL
                ELSE CAST(JSON_OBJECT(
                    'first_name', u.first_name,
                    'last_name',  u.last_name,
                    'email',      u.email
                ) AS JSON)
            END AS patient_user_info
        FROM breast_cancer_patients AS p
        LEFT JOIN users AS u
            ON u.id = p.user_id
        WHERE p.clinician_user_id = %s
    """

    # --- PATIENTS combined FULLTEXT index (name, pending_email) ---
    if name:
        ors.append("MATCH(p.name, p.pending_email) AGAINST (%s IN BOOLEAN MODE)")
        params += (to_boolean_prefix_query(name),)

    if email:
        # Use the same combined index to match pending_email by passing the email terms
        ors.append("MATCH(p.name, p.pending_email) AGAINST (%s IN BOOLEAN MODE)")
        params += (to_boolean_prefix_query(email),)

    # --- USERS combined FULLTEXT index (first_name, last_name, email) ---
    # Keep the same OR semantics you had before, but each term hits the combined index.
    if first_name:
        ors.append(
            "(p.user_id IS NOT NULL AND "
            " MATCH(u.first_name, u.last_name, u.email) AGAINST (%s IN BOOLEAN MODE))"
        )
        params += (to_boolean_prefix_query(first_name),)

    if last_name:
        ors.append(
            "(p.user_id IS NOT NULL AND "
            " MATCH(u.first_name, u.last_name, u.email) AGAINST (%s IN BOOLEAN MODE))"
        )
        params += (to_boolean_prefix_query(last_name),)

    if email:
        ors.append(
            "(p.user_id IS NOT NULL AND "
            " MATCH(u.first_name, u.last_name, u.email) AGAINST (%s IN BOOLEAN MODE))"
        )
        params += (to_boolean_prefix_query(email),)

    # Enforce that at least one search attribute is provided
    if not ors:
        raise ValueError(
            "At least one of name, first_name, last_name, or email is required."
        )

    operation += " AND (" + " OR ".join(ors) + ")"
    operation += " ORDER BY p.id"

    with get_db_cursor_cm() as cursor:
        cursor.execute(operation, params)
        rows = cursor.fetchall()

    return rows
