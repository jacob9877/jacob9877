from fastapi import APIRouter, Depends, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.approvals_models import PostBreastCancerApproval
from app.models.breast_cancer_patient_models import Patient
from app.models.common_models import ResponseModel
from app.utils.db import get_db_cursor
from app.utils.dependencies import (
    clinicians_only,
    require_access,
    validate_breast_cancer_patient_id,
)

router = APIRouter(
    prefix="/breast-cancer-patients/{patient_id}/approvals",
    tags=["Breast Cancer Approvals"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to access the requested patient",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Requested patient doesn't exist",
        },
    },
    dependencies=[Security(require_access(clinicians_only()))],
)


@router.post(
    "",
    summary="Set diagnosis approval status",
    description="Set or reset the status of the diagnosis approval. Only provide a value for the approvals you actually wish to modify. Setting an approval as null in the request body will actually reset the approval status to NULL",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Nothing",
)
def post_approval(
    approval_request: PostBreastCancerApproval,
    patient: Patient = Depends(validate_breast_cancer_patient_id),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    # Determine if diagnosis was actually set
    if not approval_request.model_dump(exclude_unset=True):
        return

    operation = """
        UPDATE breast_cancer_patients
        SET diagnosis_approval_status=%s
        WHERE id=%s
    """
    params = (approval_request.diagnosis, patient.id)
    cursor.execute(operation, tuple(params))

    return
