from fastapi import APIRouter, Depends, HTTPException, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.clinical_notes_models import ClinicalNoteBase
from app.models.common_models import ResponseModel
from app.models.patient_portal_models import (
    ClinicianInfo,
    GetPediatricAppendicitisPatientPortalResponse,
)
from app.models.pediatric_appendicitis_models import (
    FEATURE_NAMES,
    PediatricAppendicitisPatient,
)
from app.models.user_models import Condition, User
from app.utils.db import get_db_cursor
from app.utils.dependencies import get_current_user, patients_with, require_access

router = APIRouter(
    prefix="/patient-portal/pediatric-appendicitis",
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
    dependencies=[
        Security(require_access(patients_with({Condition.PEDIATRIC_APPENDICITIS})))
    ],
)


def get_patient_info_for_user(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
) -> PediatricAppendicitisPatient:

    operation = """
        SELECT *
        FROM pediatric_appendicitis_patients
        WHERE user_id = %s
    """
    params = (current_user.id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No patient info found"
        )
    patient = PediatricAppendicitisPatient(**row)
    return patient


@router.get(
    "",
    summary="Get pediatric appendicitis patient info",
    description="Get feature and other information about the currently logged-in pediatric appendicitis patient",
    response_model=ResponseModel[GetPediatricAppendicitisPatientPortalResponse],
    response_description="The patient info plus some clinician information",
    status_code=status.HTTP_200_OK,
)
def get_current_patient_info(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    patient: PediatricAppendicitisPatient = Depends(get_patient_info_for_user),
):
    operation = """
        SELECT email
        FROM users
        WHERE id = %s
    """
    params = (patient.clinician_user_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()

    features = {
        feature_name: getattr(patient, feature_name) for feature_name in FEATURE_NAMES
    }
    response = GetPediatricAppendicitisPatientPortalResponse(
        **features,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        clinician=ClinicianInfo(email=row["email"]),
        # Only include predictions if approved by clinician
        diagnosis=(
            patient.diagnosis
            if patient.diagnosis_approval_status == "approved"
            else None
        ),
        management=(
            patient.management
            if patient.management_approval_status == "approved"
            else None
        ),
        length_of_stay_pred=(
            patient.length_of_stay_pred
            if patient.length_of_stay_approval_status == "approved"
            else None
        ),
        length_of_stay_pi_lower=(
            patient.length_of_stay_pi_lower
            if patient.length_of_stay_approval_status == "approved"
            else None
        ),
        length_of_stay_pi_upper=(
            patient.length_of_stay_pi_upper
            if patient.length_of_stay_approval_status == "approved"
            else None
        ),
    )
    return ResponseModel[GetPediatricAppendicitisPatientPortalResponse](
        data=response, detail="Patient info retrieved successfully"
    )


@router.get(
    "/clinical-notes",
    summary="Get pediatric appendicitis patient clinical notes",
    description="Get clinical notes for the currently logged-in pediatric appendicitis patient",
    response_model=ResponseModel[list[ClinicalNoteBase]],
    response_description="Clinical notes sorted descending by updated_at",
    status_code=status.HTTP_200_OK,
)
def get_current_patient_clinical_notes(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    patient: PediatricAppendicitisPatient = Depends(get_patient_info_for_user),
):
    operation = """
        SELECT id, content, created_at, updated_at
        FROM pediatric_appendicitis_clinical_notes
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
