from fastapi import APIRouter, Body, Depends, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.approvals_models import PostPediatricAppendicitisApproval
from app.models.common_models import ResponseModel
from app.models.pediatric_appendicitis_patient_models import (
    Patient,
)
from app.utils.db import get_db_cursor
from app.utils.dependencies import (
    clinicians_only,
    require_access,
    validate_pediatric_appendicitis_patient_id,
)

router = APIRouter(
    prefix="/pediatric-appendicitis-patients/{patient_id}/approvals",
    tags=["Pediatric Appendicitis Approvals"],
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
    summary="Set prediction approval status",
    description="Set or reset the status of a prediction approval. Only provide a value for the approvals you actually wish to modify. Setting an approval as null in the request body will actually reset the approval status to NULL. Valid values are 'approved', 'rejected', and null.",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Nothing",
)
def post_approval(
    approval_request: PostPediatricAppendicitisApproval = Body(...),
    patient: Patient = Depends(validate_pediatric_appendicitis_patient_id),
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
        UPDATE pediatric_appendicitis_patients
        SET {set_clause}
        WHERE id=%s
    """
    params.append(patient.id)
    cursor.execute(operation, tuple(params))

    return
