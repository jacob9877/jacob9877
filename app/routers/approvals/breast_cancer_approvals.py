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
    },
    dependencies=[Security(require_access(clinicians_only()))],
)


@router.post(
    "",
    summary="Set diagnosis approval status",
    description="Set or reset the status of the diagnosis approval",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Nothing",
)
def post_approval(
    approval_request: PostBreastCancerApproval,
    patient: Patient = Depends(validate_breast_cancer_patient_id),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    approvals = approval_request.model_dump(exclude_unset=True)

    if not approvals:
        return

    set_parts = []
    params = []
    for field, new_approval_status in approvals.items():
        approval_status_column = f"{field}_approval_status"
        set_parts.append(f"{approval_status_column}=%s")
        params.append(new_approval_status)

    set_clause = ",".join(set_parts)
    operation = f"""
        UPDATE breast_cancer_patients
        SET {set_clause}
        WHERE id=%s
    """
    params.append(patient.id)
    cursor.execute(operation, tuple(params))

    return
