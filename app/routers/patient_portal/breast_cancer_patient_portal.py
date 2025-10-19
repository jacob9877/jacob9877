from fastapi import APIRouter, Depends, HTTPException, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import (
    FEATURE_NAMES,
    Patient,
    DEMOGRAPHICS_NAMES,
)
from app.models.clinical_notes_models import GetClinicalNoteResponse
from app.models.common_models import ResponseModel
from app.models.patient_portal_models import (
    GetBreastCancerPatientPortalResponse,
)
from app.models.user_models import Condition, User, UserSummary
from app.utils.db import get_db_cursor
from app.utils.dependencies import get_current_user, patients_with, require_access

router = APIRouter(
    prefix="/patient-portal/breast-cancer",
    tags=["Patient Portal"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to access the requested resource",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Requested resource doesn't exist",
        },
    },
    dependencies=[Security(require_access(patients_with({Condition.BREAST_CANCER})))],
)


def get_patient_info_for_user(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
) -> Patient:

    operation = """
        SELECT *
        FROM breast_cancer_patients
        WHERE user_id = %s
    """
    params = (current_user.id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No patient info found"
        )
    patient = Patient(**row)
    return patient


@router.get(
    "",
    summary="Get breast cancer patient info",
    description="Get feature and other information about the currently logged-in breast cancer patient",
    response_model=ResponseModel[GetBreastCancerPatientPortalResponse],
    response_description="The patient info plus some clinician information",
    status_code=status.HTTP_200_OK,
)
def get_current_patient_info(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    patient: Patient = Depends(get_patient_info_for_user),
):
    columns = list(UserSummary.model_fields.keys())
    operation = f"""
        SELECT {" ,".join(columns)}
        FROM users
        WHERE id = %s
    """
    params = (patient.clinician_user_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()

    patient_fields_to_include = (
        FEATURE_NAMES + DEMOGRAPHICS_NAMES + ["created_at", "updated_at"]
    )
    if patient.diagnosis_approval_status == "approved":
        patient_fields_to_include.append("diagnosis")

    response = GetBreastCancerPatientPortalResponse(
        **patient.model_dump(include=set(patient_fields_to_include)),
        clinician_user_info=row,
    )
    return ResponseModel[GetBreastCancerPatientPortalResponse](
        data=response, detail="Patient info retrieved successfully"
    )


@router.get(
    "/clinical-notes",
    summary="Get breast cancer patient clinical notes",
    description="Get clinical notes for the currently logged-in breast cancer patient",
    response_model=ResponseModel[list[GetClinicalNoteResponse]],
    response_description="Clinical notes sorted descending by updated_at",
    status_code=status.HTTP_200_OK,
)
def get_current_patient_clinical_notes(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    patient: Patient = Depends(get_patient_info_for_user),
):
    columns = list(GetClinicalNoteResponse.model_fields.keys())
    operation = f"""
        SELECT {" ,".join(columns)}
        FROM breast_cancer_clinical_notes
        WHERE patient_id = %s
        ORDER BY updated_at DESC, id DESC
    """
    params = (patient.id,)
    cursor.execute(operation, params)
    rows = cursor.fetchall()

    clinical_notes = [GetClinicalNoteResponse(**row) for row in rows]

    return ResponseModel[list[GetClinicalNoteResponse]](
        data=clinical_notes, detail="Successfully retrieved clinical notes"
    )
