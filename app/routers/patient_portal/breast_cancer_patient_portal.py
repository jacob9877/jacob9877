from fastapi import APIRouter, Depends, HTTPException, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import FEATURE_NAMES, BreastCancerPatient
from app.models.clinical_notes_models import ClinicalNoteBase
from app.models.common_models import ResponseModel
from app.models.patient_portal_models import (
    ClinicianInfo,
    GetBreastCancerPatientPortalResponse,
)
from app.models.user_models import Condition, User
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
) -> BreastCancerPatient:

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
    patient = BreastCancerPatient(**row)
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
    patient: BreastCancerPatient = Depends(get_patient_info_for_user),
):
    operation = """
        SELECT first_name, last_name, email
        FROM users
        WHERE id = %s
    """
    params = (patient.clinician_user_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()

    features = {
        feature_name: getattr(patient, feature_name) for feature_name in FEATURE_NAMES
    }
    response = GetBreastCancerPatientPortalResponse(
        **features,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        clinician=ClinicianInfo(**row),
        # Only include predictions if approved by clinician
        diagnosis=(
            patient.diagnosis
            if patient.diagnosis_approval_status == "approved"
            else None
        )
    )
    return ResponseModel[GetBreastCancerPatientPortalResponse](
        data=response, detail="Patient info retrieved successfully"
    )


@router.get(
    "/clinical-notes",
    summary="Get breast cancer patient clinical notes",
    description="Get clinical notes for the currently logged-in breast cancer patient",
    response_model=ResponseModel[list[ClinicalNoteBase]],
    response_description="Clinical notes sorted descending by updated_at",
    status_code=status.HTTP_200_OK,
)
def get_current_patient_clinical_notes(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    patient: BreastCancerPatient = Depends(get_patient_info_for_user),
):
    operation = """
        SELECT id, content, created_at, updated_at
        FROM breast_cancer_clinical_notes
        WHERE patient_id = %s
        ORDER BY updated_at DESC, id DESC
    """
    params = (patient.id,)
    cursor.execute(operation, params)
    rows = cursor.fetchall()

    clinical_notes = [ClinicalNoteBase(**row) for row in rows]

    return ResponseModel[list[ClinicalNoteBase]](
        data=clinical_notes, detail="Successfully retrieved clinical notes"
    )
