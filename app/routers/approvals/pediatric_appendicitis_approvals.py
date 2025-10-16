from fastapi import APIRouter, Depends, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.approvals_models import PostPediatricAppendicitisApproval
from app.models.common_models import ResponseModel
from app.models.pediatric_appendicitis_models import PediatricAppendicitisPatient
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
    },
    dependencies=[Security(require_access(clinicians_only()))],
)


@router.post(
    "",
    summary="Set prediction approval status",
    description="Set or reset the status of a prediction approval",
    status_code=status.HTTP_200_OK,
    response_model=ResponseModel[None],
    response_description="Nothing much. 200 OK status code indicates success",
)
def post_approval(
    approval_request: PostPediatricAppendicitisApproval,
    patient: PediatricAppendicitisPatient = Depends(
        validate_pediatric_appendicitis_patient_id
    ),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):

    approvals = approval_request.model_dump(exclude_unset=True)

    if not approvals:
        return ResponseModel[None](detail="Didn't update anything")

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

    return ResponseModel[None](detail="Approval status updated successfully")
