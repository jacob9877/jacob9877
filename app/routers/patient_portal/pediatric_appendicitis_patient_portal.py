import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.common_models import ResponseModel
from app.models.pediatric_appendicitis_models import (
    FEATURE_NAMES,
    CreateImagesRequest,
    ImageResponse,
    PaginatedPediatricAppendicitisPatients,
    PediatricAppendicitisPatient,
    PediatricAppendicitisPatientFeatures,
    PediatricAppendicitisPatientWithImages,
    PediatricAppendicitisPredictions,
    PresignedUpload,
    S3Uri,
    UpsertPediatricAppendicitisPatientRequest,
)
from app.models.user_models import Condition, User
from app.utils.aws import (
    bulk_send_message_to_sqs,
    create_presigned_post_for_image,
    create_presigned_url,
    get_predictions,
    s3_file_exists,
)
from app.utils.db import get_db_cursor, insert_pending_email
from app.utils.dependencies import (
    clinicians_only,
    get_current_user,
    patients_with,
    require_access,
    validate_pediatric_appendicitis_patient_id,
)
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(
    prefix="/patient-portal/pediatric-appendicitis",
    dependencies=[
        Security(require_access(patients_with({Condition.PEDIATRIC_APPENDICITIS})))
    ],
)


@router.get("")
def get_current_patient_info(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    return
