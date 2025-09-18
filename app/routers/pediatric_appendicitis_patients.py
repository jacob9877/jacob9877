import traceback
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.common_models import ResponseModel
from app.models.pediatric_appendicitis_models import (
    FEATURE_NAMES,
    AddPediatricAppendicitisPatientRequest,
    CreateImagesRequest,
    PaginatedPediatricAppendicitisPatients,
    PediatricAppendicitisPatient,
    PediatricAppendicitisPatientFeatures,
    PediatricAppendicitisPatientWithImages,
    PresignedUpload,
    S3Uri,
)
from app.utils.aws import (
    create_presigned_post,
    create_presigned_url,
    get_predictions,
    s3_file_exists,
)
from app.utils.db import get_db_connection, get_pediatric_appendicitis_patient_by_id
from app.utils.jwt import get_and_validate_current_user_id
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(
    prefix="/pediatric-appendicitis-patients",
    tags=["Pediatric Appendicitis Patients"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)

IMAGES_BUCKET = "pediatric-appendicitis-images"


def build_s3_image_key(user_id: int, upload_id: str, file_type: str) -> str:
    return f"{user_id}/{upload_id}.{file_type}"


@router.post(
    "/images",
    summary="Get pre-signed upload URLs",
    description="Given a list of file extensions of images to be uploaded, returns a pre-signed URL with additional data for each of them",
    status_code=status.HTTP_201_CREATED,
    response_model=list[PresignedUpload],
)
def create_presigned_uploads(
    request: CreateImagesRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:
            presigned_uploads: list[PresignedUpload] = []
            for file_type in request.file_types:
                upload_id = str(uuid.uuid4())
                presigned_url = create_presigned_post(
                    bucket=IMAGES_BUCKET,
                    key=build_s3_image_key(current_user_id, upload_id, file_type),
                    file_type=file_type,
                    max_size_in_bytes=5 * 1024 * 1024,  # 5 MB limit
                    expires_in_sec=300,  # URL valid for 5 minutes
                )
                presigned_uploads.append(
                    PresignedUpload(
                        upload_id=upload_id,
                        url=presigned_url["url"],
                        fields=presigned_url["fields"],
                    )
                )

                operation = """
                    INSERT INTO pediatric_appendicitis_images (upload_id, user_id, file_type)
                    VALUES (%s, %s, %s)
                """
                params = (upload_id, current_user_id, file_type)
                cursor.execute(operation, params)

        conn.commit()

        return presigned_uploads

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


def _get_image_uri(
    cursor: MySQLCursorDict, upload_id: str, current_user_id: int
) -> S3Uri:
    operation = """
        SELECT user_id, file_type FROM pediatric_appendicitis_images
        WHERE upload_id = %s
    """
    params = (upload_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload ID {upload_id} not found",
        )
    if row["user_id"] != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Upload ID {upload_id} does not belong to the current user",
        )
    file_type = row["file_type"]
    s3_key = build_s3_image_key(current_user_id, upload_id, file_type)
    if not s3_file_exists(IMAGES_BUCKET, s3_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File for upload ID {upload_id} does not exist in S3",
        )
    return S3Uri(bucket=IMAGES_BUCKET, key=s3_key)


def _insert_patient(
    cursor: MySQLCursorDict,
    user_id: int,
    patient: PediatricAppendicitisPatientFeatures,
    predictions: dict,
) -> PediatricAppendicitisPatient:
    column_names = [
        "user_id",
        *FEATURE_NAMES,
        "diagnosis",
        "management",
        "severity",
        "length_of_stay_pred",
        "length_of_stay_pi_lower",
        "length_of_stay_pi_upper",
    ]
    placeholders = ", ".join(["%s"] * len(column_names))
    operation = f"""
        INSERT INTO pediatric_appendicitis_patients ({", ".join(column_names)})
        VALUES ({placeholders})
    """
    params = tuple(
        [user_id]
        + [getattr(patient, feature_name) for feature_name in FEATURE_NAMES]
        + [
            predictions["diagnosis"],
            predictions["management"],
            predictions["severity"],
            predictions["length_of_stay"]["pred"],
            predictions["length_of_stay"]["pi_lower"],
            predictions["length_of_stay"]["pi_upper"],
        ]
    )
    cursor.execute(operation, params)
    patient_id = cursor.lastrowid

    operation = """
        SELECT *
        FROM pediatric_appendicitis_patients
        WHERE id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()

    return PediatricAppendicitisPatient(**row)


@router.post("")
def add_patient(
    add_patient_request: AddPediatricAppendicitisPatientRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):

    try:
        with conn.cursor(dictionary=True) as cursor:

            image_s3_uris = [
                _get_image_uri(cursor, upload_id, current_user_id)
                for upload_id in add_patient_request.image_upload_ids
            ]

            body = {
                "features": add_patient_request.features.model_dump(),
                "image_s3_uris": [uri.model_dump() for uri in image_s3_uris],
            }
            predictions = get_predictions(body, "pediatric-appendicitis")

            new_patient = _insert_patient(
                cursor,
                current_user_id,
                add_patient_request.features,
                predictions,
            )

            if add_patient_request.image_upload_ids:
                # Update the images to link them to the new patient
                placeholders = ", ".join(
                    ["%s"] * len(add_patient_request.image_upload_ids)
                )
                operation = f"""
                    UPDATE pediatric_appendicitis_images
                    SET patient_id = %s
                    WHERE upload_id IN ({placeholders}) AND user_id = %s
                """
                params = (
                    new_patient.id,
                    *add_patient_request.image_upload_ids,
                    current_user_id,
                )
                cursor.execute(operation, params)

        presigned_urls = [
            create_presigned_url(uri.bucket, uri.key) for uri in image_s3_uris
        ]

        patient_with_images = PediatricAppendicitisPatientWithImages(
            **new_patient.model_dump(), image_urls=presigned_urls
        )

        conn.commit()

        return ResponseModel[PediatricAppendicitisPatientWithImages](
            data=patient_with_images,
            detail="Patient added, predictions obtained, and URLs created successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.get(
    "/{patient_id}",
    summary="Get a patient by ID",
    response_model=ResponseModel[PediatricAppendicitisPatientWithImages],
    response_description="Returns the pediatric appendicitis patient with the provided ID, with pre-signed URLs for any images associated with the patient",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to perform the requested action",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
    },
)
def get_patient(
    patient_id: int = Path(..., description="ID of the patient to get"),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

            if patient is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Pediatric appendicitis patient with ID {patient_id} not found",
                )

            if patient.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to access this patient",
                )

            operation = """
                SELECT upload_id, file_type
                FROM pediatric_appendicitis_images
                WHERE patient_id=%s
            """
            params = (patient_id,)
            cursor.execute(operation, params)
            rows = cursor.fetchall()

        presigned_urls = []
        for row in rows:
            s3_key = build_s3_image_key(
                current_user_id, row["upload_id"], row["file_type"]
            )
            presigned_url = create_presigned_url(IMAGES_BUCKET, s3_key)
            presigned_urls.append(presigned_url)

        patient_with_images = PediatricAppendicitisPatientWithImages(
            **patient.model_dump(), image_urls=presigned_urls
        )

        return ResponseModel[PediatricAppendicitisPatientWithImages](
            data=patient_with_images,
            detail="Patient fetched and URLs created successfully",
        )

    except Exception as e:
        traceback.print_exc()
        raise e


@router.get(
    "",
    summary="Get pediatric appendicitis patients for the logged-in user (cursor-based pagination)",
    description=(
        "Retrieves pediatric appendicitis patients for the current user (by the provided access token) using cursor-based pagination, "
        "sorted by most recently updated."
    ),
    response_model=ResponseModel[PaginatedPediatricAppendicitisPatients],
    response_description="Returns a page of patients plus a next_cursor if more data exists",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Cursor is invalid",
        }
    },
)
def get_pediatric_appendicitis_patients_paginated(
    # Optional cursor from previous response
    cursor_token: Optional[str] = Query(
        default=None,
        alias="cursor",
        description="Opaque cursor returned from the previous page (base64url)",
    ),
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
        description="Max number of patients to return (1–100)",
    ),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        # Order is (updated_at DESC, id DESC).
        # For "next page", fetch rows strictly "after" the cursor in that order:
        # updated_at < cursor_ts OR (updated_at = cursor_ts AND id < cursor_id)
        operation = """
            SELECT *
            FROM pediatric_appendicitis_patients
            WHERE user_id = %s
        """

        params = [current_user_id]

        if cursor_token:
            try:
                last_timestamp, last_id = decode_cursor(cursor_token)
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
                )
            operation += """
                AND (
                    updated_at < %s
                    OR (updated_at = %s AND id < %s)
                )
            """
            params.extend([last_timestamp, last_timestamp, last_id])

        # Apply ORDER BY and LIMIT + 1 (to see if there's another page)
        operation += " ORDER BY updated_at DESC, id DESC LIMIT %s"
        params.append(limit + 1)

        with conn.cursor(dictionary=True) as cursor:

            cursor.execute(operation, tuple(params))
            rows = cursor.fetchall()

        # Build response items and next cursor (if we fetched limit+1)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]  # only return 'limit' items

        patients = [PediatricAppendicitisPatient(**row) for row in rows]

        next_cursor: Optional[str] = None
        if has_more and rows:
            last_row = rows[-1]
            last_updated_at: datetime = last_row["updated_at"]
            last_row_id: int = last_row["id"]
            next_cursor = encode_cursor(last_updated_at, last_row_id)

        paginated_patients = PaginatedPediatricAppendicitisPatients(
            next_cursor=next_cursor,
            patients=patients,
        )
        return ResponseModel[PaginatedPediatricAppendicitisPatients](
            data=paginated_patients,
            detail="Patients retrieved successfully",
        )

    except Exception as e:
        traceback.print_exc()
        raise e
