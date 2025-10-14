import os
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from mysql.connector import MySQLConnection
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
from app.utils.aws import (
    bulk_send_message_to_sqs,
    create_presigned_post_for_image,
    create_presigned_url,
    get_predictions,
    s3_file_exists,
)
from app.utils.db import (
    get_db_connection,
    get_pediatric_appendicitis_patient_by_id,
    insert_pending_email,
)
from app.utils.jwt import clinicians_only, require_access
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
SAGEMAKER_ENDPOINT_NAME = "pediatric-appendicitis"
EXPLANATION_QUEUE_URL = os.environ["PEDIATRIC_APPENDICITIS_EXPLANATION_QUEUE_URL"]


def build_s3_image_key(user_id: int, upload_id: str, file_type: str) -> str:
    return f"{user_id}/{upload_id}.{file_type}"


@router.post(
    "/images",
    summary="Get pre-signed upload URLs",
    description="Given a list of file extensions of images to be uploaded, returns a pre-signed URL with additional data for each of them",
    status_code=status.HTTP_201_CREATED,
    response_model=list[PresignedUpload],
    response_model_by_alias=True,
    response_description="List of: upload id, pre-signed POST URL, and fields (these should be included as form data in the POST request)",
)
def create_presigned_uploads(
    request: CreateImagesRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(require_access(clinicians_only())),
):
    try:
        with conn.cursor(dictionary=True) as cursor:
            presigned_uploads: list[PresignedUpload] = []
            for file_type in request.file_types:
                upload_id = str(uuid.uuid4())
                presigned_post_url = create_presigned_post_for_image(
                    bucket=IMAGES_BUCKET,
                    key=build_s3_image_key(current_user_id, upload_id, file_type),
                    file_type=file_type,
                    max_size_in_bytes=5 * 1024 * 1024,  # 5 MB limit
                    expires_in_sec=300,  # URL valid for 5 minutes
                )
                presigned_uploads.append(
                    PresignedUpload(
                        upload_id=upload_id,
                        url=presigned_post_url["url"],
                        fields=presigned_post_url["fields"],
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


def _get_s3_uri_for_upload_id(
    cursor: MySQLCursorDict, upload_id: str, current_user_id: int
) -> S3Uri:
    operation = """
        SELECT user_id, file_type FROM pediatric_appendicitis_images
        WHERE upload_id = %s
    """
    params = (upload_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    # Provided upload_id doesn't actually exist
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload ID {upload_id} not found",
        )
    # Check that the provided upload_id actually belongs to the logged-in user
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
    clinician_user_id: int,
    features: PediatricAppendicitisPatientFeatures,
    predictions: PediatricAppendicitisPredictions,
) -> PediatricAppendicitisPatient:
    column_names = [
        "clinician_user_id",
        *FEATURE_NAMES,
        *list(PediatricAppendicitisPredictions.model_fields.keys()),
    ]
    placeholders = ", ".join(["%s"] * len(column_names))
    operation = f"""
        INSERT INTO pediatric_appendicitis_patients ({", ".join(column_names)})
        VALUES ({placeholders})
    """
    params = tuple(
        [clinician_user_id]
        + [getattr(features, feature_name) for feature_name in FEATURE_NAMES]
        + list(predictions.model_dump().values())
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


@router.post(
    "",
    summary="Add a pediatric appendicitis patient",
    description="Given the features and upload_ids of any associated images, add and predict for a new pediatric appendicitis patient.",
    response_model=ResponseModel[PediatricAppendicitisPatientWithImages],
    response_description="Patient information along with pre-signed URLs for any associated images",
    status_code=status.HTTP_201_CREATED,
)
def add_patient(
    add_patient_request: UpsertPediatricAppendicitisPatientRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(require_access(clinicians_only())),
):

    try:
        with conn.cursor(dictionary=True) as cursor:

            image_s3_uris = [
                _get_s3_uri_for_upload_id(cursor, upload_id, current_user_id)
                for upload_id in add_patient_request.image_upload_ids
            ]

            body = {
                "features": add_patient_request.features.model_dump(),
                "image_s3_uris": [uri.model_dump() for uri in image_s3_uris],
            }
            predictions = get_predictions(body, SAGEMAKER_ENDPOINT_NAME)
            predictions_validated = PediatricAppendicitisPredictions(**predictions)
            new_patient = _insert_patient(
                cursor,
                current_user_id,
                add_patient_request.features,
                predictions_validated,
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

            if add_patient_request.email:
                insert_pending_email(
                    cursor,
                    add_patient_request.email,
                    new_patient.id,
                    "pediatric_appendicitis_patients",
                )

        images: list[ImageResponse] = []
        for upload_id, image_s3_uri in zip(
            add_patient_request.image_upload_ids, image_s3_uris
        ):
            presigned_url = create_presigned_url(image_s3_uri.bucket, image_s3_uri.key)
            images.append(ImageResponse(upload_id=upload_id, url=presigned_url))

        patient_with_images = PediatricAppendicitisPatientWithImages(
            **new_patient.model_dump(), images=images
        )

        conn.commit()

        # Send the new patient info to SQS for explanation processing
        features = {
            "Diagnosis": predictions_validated.diagnosis,
            "Management": predictions_validated.management,
            "Severity": predictions_validated.severity,
        } | patient_with_images.model_dump(include=set(FEATURE_NAMES))
        messages = [
            {
                "patient_id": new_patient.id,
                "features": features,
                "image_uris": [image_uri.model_dump() for image_uri in image_s3_uris],
            }
        ]
        bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

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
    current_user_id: int = Depends(require_access(clinicians_only())),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

            if patient is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Pediatric appendicitis patient with ID {patient_id} not found",
                )

            if patient.clinician_user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to access this patient",
                )

            # Fetch any images associated with the patient
            operation = """
                SELECT upload_id, file_type
                FROM pediatric_appendicitis_images
                WHERE patient_id=%s
            """
            params = (patient_id,)
            cursor.execute(operation, params)
            rows = cursor.fetchall()

        # Build upload_id, pre-signed url pairs for each image
        images: list[ImageResponse] = []
        for row in rows:
            s3_key = build_s3_image_key(
                current_user_id, row["upload_id"], row["file_type"]
            )
            presigned_url = create_presigned_url(IMAGES_BUCKET, s3_key)
            images.append(ImageResponse(upload_id=row["upload_id"], url=presigned_url))

        patient_with_images = PediatricAppendicitisPatientWithImages(
            **patient.model_dump(), images=images
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
    cursor_token: str | None = Query(
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
    current_user_id: int = Depends(require_access(clinicians_only())),
):
    try:
        # Order is (updated_at DESC, id DESC).
        # For "next page", fetch rows strictly "after" the cursor in that order:
        # updated_at < cursor_ts OR (updated_at = cursor_ts AND id < cursor_id)
        operation = """
            SELECT *
            FROM pediatric_appendicitis_patients
            WHERE clinician_user_id = %s
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

            # Get the total count while we have the cursor
            operation = """
                SELECT COUNT(*) 
                AS count
                FROM pediatric_appendicitis_patients
                WHERE clinician_user_id = %s
            """
            params = (current_user_id,)
            cursor.execute(operation, params)
            result = cursor.fetchone()
            total_count = result["count"]

        # Build response items and next cursor (if we fetched limit+1)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]  # only return 'limit' items

        patients = [PediatricAppendicitisPatient(**row) for row in rows]

        next_cursor: str | None = None
        if has_more and rows:
            last_row = rows[-1]
            last_updated_at: datetime = last_row["updated_at"]
            last_row_id: int = last_row["id"]
            next_cursor = encode_cursor(last_updated_at, last_row_id)

        paginated_patients = PaginatedPediatricAppendicitisPatients(
            next_cursor=next_cursor,
            total_count=total_count,
            patients=patients,
        )
        return ResponseModel[PaginatedPediatricAppendicitisPatients](
            data=paginated_patients,
            detail="Patients retrieved successfully",
        )

    except Exception as e:
        traceback.print_exc()
        raise e


@router.delete(
    "/{patient_id}",
    summary="Delete a patient by ID",
    description="Delete the patient with the provided patient ID",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Nothing important. A status code of 204 on the response indicates success.",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to perform the requested action",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient with provided ID not found",
        },
    },
)
def delete_patient(
    patient_id: int,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(require_access(clinicians_only())),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

            if patient is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Patient with ID {patient_id} not found",
                )

            if patient.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to delete this patient",
                )

            # Delete the patient record
            operation = """
                DELETE FROM pediatric_appendicitis_patients
                WHERE id=%s
            """
            params = (patient_id,)
            cursor.execute(operation, params)

        conn.commit()

        return

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


def _update_patient(
    cursor: MySQLCursorDict,
    patient_id: int,
    features: PediatricAppendicitisPatientFeatures,
    predictions: PediatricAppendicitisPredictions,
) -> PediatricAppendicitisPatient:
    column_names = [
        *FEATURE_NAMES,
        *list(PediatricAppendicitisPredictions.model_fields.keys()),
    ]
    set_clause = ", ".join(f"{column_name}=%s" for column_name in column_names)
    operation = f"""
        UPDATE pediatric_appendicitis_patients
        SET {set_clause}
        WHERE id=%s
    """
    params = (
        tuple(getattr(features, name) for name in FEATURE_NAMES)
        + tuple(predictions.model_dump().values())
        + (patient_id,)
    )
    cursor.execute(operation, params)

    operation = """
        SELECT *
        FROM pediatric_appendicitis_patients
        WHERE id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()

    return PediatricAppendicitisPatient(**row)


@router.put(
    "/{patient_id}",
    summary="Update a patient (and re-predict)",
    description="Provide the new patient info; the predictions are always re-predicted and saved.",
    response_model=ResponseModel[PediatricAppendicitisPatientWithImages],
    response_description="Returns the updated patient with pre-signed URLs for any images",
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
def update_patient(
    patient_id: int,
    update_patient_request: UpsertPediatricAppendicitisPatientRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(require_access(clinicians_only())),
):
    try:
        with conn.cursor(dictionary=True) as cursor:
            patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

            if patient is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Patient with ID {patient_id} not found",
                )

            if patient.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to access this patient",
                )

            image_upload_ids = update_patient_request.image_upload_ids or []

            # If the user provided images
            if image_upload_ids:
                # Delete all images except those images
                placeholders = ",".join(["%s"] * len(image_upload_ids))
                operation = f"""
                    DELETE FROM pediatric_appendicitis_images
                    WHERE patient_id=%s AND user_id=%s AND upload_id NOT IN ({placeholders})
                """
                params = (patient_id, current_user_id, *image_upload_ids)
                cursor.execute(operation, params)
            # If the user provided no images
            else:
                # This means the patient should have no images associated with it. This else block is necessary to prevent SQL syntax error
                operation = """
                    DELETE FROM pediatric_appendicitis_images
                    WHERE patient_id=%s AND user_id=%s
                """
                params = (patient_id, current_user_id)
                cursor.execute(operation, params)

            image_s3_uris = [
                _get_s3_uri_for_upload_id(cursor, upload_id, current_user_id)
                for upload_id in image_upload_ids
            ]

            body = {
                "features": update_patient_request.features.model_dump(),
                "image_s3_uris": [uri.model_dump() for uri in image_s3_uris],
            }
            predictions = get_predictions(body, SAGEMAKER_ENDPOINT_NAME)
            predictions_validated = PediatricAppendicitisPredictions(**predictions)
            new_patient = _update_patient(
                cursor,
                patient_id,
                update_patient_request.features,
                predictions_validated,
            )

            if update_patient_request.email:
                insert_pending_email(
                    cursor,
                    update_patient_request.email,
                    new_patient.id,
                    target_patient_table="pediatric_appendicitis_patients",
                )

            if image_upload_ids:
                # Update the images to link them to the new patient
                placeholders = ", ".join(["%s"] * len(image_upload_ids))
                operation = f"""
                    UPDATE pediatric_appendicitis_images
                    SET patient_id = %s
                    WHERE upload_id IN ({placeholders}) AND user_id = %s
                """
                params = (
                    new_patient.id,
                    *image_upload_ids,
                    current_user_id,
                )
                cursor.execute(operation, params)

        images: list[ImageResponse] = []
        for upload_id, image_s3_uri in zip(image_upload_ids, image_s3_uris):
            presigned_url = create_presigned_url(image_s3_uri.bucket, image_s3_uri.key)
            images.append(ImageResponse(upload_id=upload_id, url=presigned_url))

        patient_with_images = PediatricAppendicitisPatientWithImages(
            **new_patient.model_dump(), images=images
        )

        conn.commit()

        return ResponseModel[PediatricAppendicitisPatientWithImages](
            data=patient_with_images,
            detail="Patient updated, predictions obtained, and URLs created successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.delete(
    "",
    summary="Delete multiple patients by IDs",
    description="Deletes the patients whose IDs are provided",
    response_model=ResponseModel[list[int]],
    response_description="Returns the list of IDs that were deleted",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to perform the requested action",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "One or more patient IDs not found",
        },
    },
)
def delete_patients(
    patient_ids: list[int] = Query(
        ...,
        min_items=1,
        description="List of patient IDs to delete",
        example="ids=1&ids=2&ids=3",
    ),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(require_access(clinicians_only())),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            # Verify all IDs exist
            placeholders = ",".join(["%s"] * len(patient_ids))
            operation = f"""
                SELECT id, user_id
                FROM pediatric_appendicitis_patients
                WHERE id IN ({placeholders})
            """
            params = tuple(patient_ids)
            cursor.execute(operation, params)

            rows = cursor.fetchall()

            found_ids = [row["id"] for row in rows]
            missing_ids = [pid for pid in patient_ids if pid not in found_ids]
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Patient IDs not found: {missing_ids}",
                )

            forbidden_ids = [
                row["id"] for row in rows if row["user_id"] != current_user_id
            ]
            if forbidden_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to delete these patients {forbidden_ids}",
                )

            # Perform delete
            operation = f"""
                DELETE FROM pediatric_appendicitis_patients
                WHERE id IN ({placeholders})
            """
            params = tuple(patient_ids)
            cursor.execute(operation, params)

        conn.commit()

        return ResponseModel[list[int]](
            data=patient_ids,
            detail=f"Deleted {len(patient_ids)} patients successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e
