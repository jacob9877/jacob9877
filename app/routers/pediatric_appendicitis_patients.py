import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.common_models import ResponseModel
from app.models.patient_models import SetPatientEmailRequest
from app.models.pediatric_appendicitis_patient_models import (
    FEATURE_NAMES,
    Approvals,
    Features,
    GetPatientResponse,
    GetPatientResponseWithImages,
    ImageResponse,
    PaginatedPatients,
    PostImagesRequest,
    Predictions,
    PresignedUpload,
    S3Uri,
    UpsertPatientRequest,
)
from app.models.user_models import User, UserSummary
from app.utils.aws import (
    bulk_send_message_to_sqs,
    create_presigned_post_for_image,
    create_presigned_url,
    get_predictions,
    s3_file_exists,
)
from app.utils.db import (
    get_db_cursor,
    get_pediatric_appendicitis_patient_by_id,
    insert_pending_email,
)
from app.utils.dependencies import (
    clinicians_only,
    get_current_user,
    require_access,
    validate_pediatric_appendicitis_patient_id,
)
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
    dependencies=[Security(require_access(clinicians_only()))],
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
    response_description="List of: upload id, pre-signed POST URL, and fields (these should be included as form data in the POST request to S3)",
)
def create_presigned_uploads(
    request: PostImagesRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    presigned_uploads: list[PresignedUpload] = []
    for file_type in request.file_types:
        upload_id = str(uuid.uuid4())
        presigned_post_url = create_presigned_post_for_image(
            bucket=IMAGES_BUCKET,
            key=build_s3_image_key(current_user.id, upload_id, file_type),
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
        params = (upload_id, current_user.id, file_type)
        cursor.execute(operation, params)

    return presigned_uploads


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
    name: str | None,
    features: Features,
    predictions: Predictions,
) -> GetPatientResponse:
    predictions_keys = list(Predictions.model_fields.keys())
    columns = [
        "clinician_user_id",
        "name",
        *FEATURE_NAMES,
        *predictions_keys,
    ]
    placeholders = ", ".join(["%s"] * len(columns))
    operation = f"""
        INSERT INTO pediatric_appendicitis_patients ({", ".join(columns)})
        VALUES ({placeholders})
    """
    params = tuple(
        [clinician_user_id, name]
        + [getattr(features, feature_name) for feature_name in FEATURE_NAMES]
        + [getattr(predictions, prediction_key) for prediction_key in predictions_keys]
    )
    cursor.execute(operation, params)
    patient_id = cursor.lastrowid

    patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

    return patient


def package_patient_with_images(
    cursor: MySQLCursorDict, get_patient_response: GetPatientResponse
) -> GetPatientResponseWithImages:
    # Fetch any images associated with the patient
    operation = """
        SELECT upload_id, file_type, name, created_at
        FROM pediatric_appendicitis_images
        WHERE patient_id=%s
    """
    params = (get_patient_response.id,)
    cursor.execute(operation, params)
    rows = cursor.fetchall()

    # Build upload_id, pre-signed url pairs for each image
    images: list[ImageResponse] = []
    for row in rows:
        s3_key = build_s3_image_key(
            get_patient_response.clinician_user_id, row["upload_id"], row["file_type"]
        )
        presigned_url = create_presigned_url(IMAGES_BUCKET, s3_key)
        images.append(ImageResponse(**row, url=presigned_url))

    patient_with_images = GetPatientResponseWithImages(
        **get_patient_response.model_dump(), images=images
    )

    return patient_with_images


@router.post(
    "",
    summary="Add pediatric appendicitis patient",
    description="Given the features and upload_ids of any associated images, add and predict for a new pediatric appendicitis patient.",
    response_model=ResponseModel[GetPatientResponseWithImages],
    response_description="The new pediatric appendicitis patient plus pre-signed URLs for associated images",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "Email is invalid due to data circumstances",
        }
    },
)
async def add_patient(
    add_patient_request: UpsertPatientRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    image_s3_uris = [
        _get_s3_uri_for_upload_id(cursor, image_upload.upload_id, current_user.id)
        for image_upload in add_patient_request.image_uploads
    ]

    body = {
        "features": add_patient_request.features.model_dump(),
        "image_s3_uris": [uri.model_dump() for uri in image_s3_uris],
    }
    result = get_predictions(body, SAGEMAKER_ENDPOINT_NAME)
    predictions = Predictions(**result)
    new_patient = _insert_patient(
        cursor=cursor,
        clinician_user_id=current_user.id,
        name=add_patient_request.name,
        features=add_patient_request.features,
        predictions=predictions,
    )

    for image_upload in add_patient_request.image_uploads:
        # Update the images to link them to the new patient
        operation = """
            UPDATE pediatric_appendicitis_images
            SET patient_id = %s, name = %s
            WHERE upload_id = %s AND user_id = %s
        """
        params = (
            new_patient.id,
            image_upload.name,
            image_upload.upload_id,
            current_user.id,
        )
        cursor.execute(operation, params)

    if add_patient_request.email:
        await insert_pending_email(
            cursor=cursor,
            email=add_patient_request.email,
            target_patient_id=new_patient.id,
            target_patient_table="pediatric_appendicitis_patients",
            clinician_first_name=current_user.first_name,
            clinician_last_name=current_user.last_name,
        )

    # Package the images nicely to return
    patient_with_images = package_patient_with_images(cursor, new_patient)

    # Send the new patient info to SQS for explanation processing
    features = {
        "Diagnosis": predictions.diagnosis,
        "Management": predictions.management,
    } | patient_with_images.model_dump(include=FEATURE_NAMES)
    messages = [
        {
            "patient_id": new_patient.id,
            "features": features,
            "image_uris": [image_uri.model_dump() for image_uri in image_s3_uris],
        }
    ]
    bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

    return ResponseModel[GetPatientResponseWithImages](
        data=patient_with_images,
        detail="Patient added, predictions obtained, and URLs created successfully",
    )


@router.get(
    "/{patient_id}",
    summary="Get pediatric appendicitis patient",
    response_model=ResponseModel[GetPatientResponseWithImages],
    response_description="The requested pediatric appendicitis patient plus pre-signed URLs for associated images",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to access the requested patient",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
    },
)
def get_patient(
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    patient: GetPatientResponse = Depends(validate_pediatric_appendicitis_patient_id),
):
    patient_with_images = package_patient_with_images(cursor, patient)

    return ResponseModel[GetPatientResponseWithImages](
        data=patient_with_images,
        detail="Patient fetched and URLs created successfully",
    )


@router.get(
    "",
    summary="Get pediatric appendicitis patients",
    description=(
        "Retrieves pediatric appendicitis patients for the current user (by the provided access token) using cursor-based pagination, "
        "sorted by most recently updated."
    ),
    response_model=ResponseModel[PaginatedPatients],
    response_description="A page of patients of max size `limit` plus a `next_cursor` if more data exists",
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
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    # Order is (updated_at DESC, id DESC).
    # For "next page", fetch rows strictly "after" the cursor in that order:
    # updated_at < cursor_ts OR (updated_at = cursor_ts AND id < cursor_id)
    user_summary_query = ",\n".join(
        f"'{field}', u.{field}\n" for field in UserSummary.model_fields.keys()
    )
    operation = f"""
        SELECT
            p.*,
            CASE
                WHEN p.user_id IS NULL THEN NULL
                ELSE JSON_OBJECT(
                    {user_summary_query}
                )
            END AS patient_user_info
        FROM pediatric_appendicitis_patients AS p
        LEFT JOIN users AS u
            ON u.id = p.user_id
        WHERE p.clinician_user_id = %s
    """

    params = [current_user.id]

    if cursor_token:
        try:
            last_timestamp, last_id = decode_cursor(cursor_token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
            ) from e
        operation += """
            AND (
                updated_at < %s
                OR (updated_at = %s AND p.id < %s)
            )
        """
        params.extend([last_timestamp, last_timestamp, last_id])

    # Apply ORDER BY and LIMIT + 1 (to see if there's another page)
    operation += " ORDER BY p.updated_at DESC, p.id DESC LIMIT %s"
    params.append(limit + 1)

    cursor.execute(operation, tuple(params))
    rows = cursor.fetchall()

    # Get the total count while we have the cursor
    operation = """
        SELECT COUNT(*) AS count
        FROM pediatric_appendicitis_patients
        WHERE clinician_user_id = %s
    """
    params = (current_user.id,)
    cursor.execute(operation, params)
    result = cursor.fetchone()
    total_count = result["count"]

    # Build response items and next cursor (if we fetched limit+1)
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]  # only return 'limit' items

    patients = [GetPatientResponse(**row) for row in rows]

    next_cursor: str | None = None
    if has_more and rows:
        last_row = rows[-1]
        last_updated_at: datetime = last_row["updated_at"]
        last_row_id: int = last_row["id"]
        next_cursor = encode_cursor(last_updated_at, last_row_id)

    paginated_patients = PaginatedPatients(
        next_cursor=next_cursor,
        total_count=total_count,
        patients=patients,
    )
    return ResponseModel[PaginatedPatients](
        data=paginated_patients,
        detail="Patients retrieved successfully",
    )


@router.delete(
    "/{patient_id}",
    summary="Delete pediatric appendicitis patient",
    description="Delete the patient with the provided ID",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="Nothing",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to delete the requested patient",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
    },
    dependencies=[
        Depends(validate_pediatric_appendicitis_patient_id),
    ],
)
def delete_patient(
    patient_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    # Delete the patient record
    operation = """
        DELETE FROM pediatric_appendicitis_patients
        WHERE id=%s
    """
    params = (patient_id,)
    cursor.execute(operation, params)

    # Images will delete automatically by CASCADE

    return


def _update_patient(
    cursor: MySQLCursorDict,
    patient_id: int,
    name: str | None,
    features: Features,
    predictions: Predictions,
) -> GetPatientResponse:
    predictions_keys = list(Predictions.model_fields.keys())
    approvals_keys = list(Approvals.model_fields.keys())
    columns = ["name", *FEATURE_NAMES, *predictions_keys, *approvals_keys]
    set_clause = ", ".join(f"{column}=%s" for column in columns)
    operation = f"""
        UPDATE pediatric_appendicitis_patients
        SET {set_clause}
        WHERE id=%s
    """
    params = tuple(
        [name]
        + [getattr(features, name) for name in FEATURE_NAMES]
        + [getattr(predictions, prediction_key) for prediction_key in predictions_keys]
        + ([None] * len(approvals_keys))
        + [patient_id]
    )
    cursor.execute(operation, params)

    updated_patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

    return updated_patient


@router.put(
    "/{patient_id}",
    summary="Update pediatric appendicitis patient",
    description="Provide the new patient info; the predictions are always re-predicted and saved.",
    response_model=ResponseModel[GetPatientResponseWithImages],
    response_description="The updated pediatric appendicitis patient plus pre-signed URLs for associated images",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to update the requested patient",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "Email is invalid due to data circumstances",
        },
    },
)
async def update_patient(
    patient_id: int,
    update_patient_request: UpsertPatientRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
    patient: GetPatientResponse = Depends(validate_pediatric_appendicitis_patient_id),
):
    # Deal with the email first in case there is a conflict we can return quickly
    if update_patient_request.email:
        await insert_pending_email(
            cursor=cursor,
            email=update_patient_request.email,
            target_patient_id=patient_id,
            target_patient_table="pediatric_appendicitis_patients",
            clinician_first_name=current_user.first_name,
            clinician_last_name=current_user.last_name,
        )

    patient_with_images = package_patient_with_images(cursor, patient)
    repredict: bool = False
    # If any feature value has changed, re-predict
    if any(
        getattr(patient_with_images, feature)
        != getattr(update_patient_request.features, feature)
        for feature in FEATURE_NAMES
    ):
        repredict = True
    # If the new upload ids are not the same as the existing ones, re-predict.
    if set(image.upload_id for image in patient_with_images.images) != set(
        image.upload_id for image in update_patient_request.image_uploads
    ):
        repredict = True

    # If the user provided images
    if update_patient_request.image_uploads:
        image_upload_ids = [
            image_upload.upload_id
            for image_upload in update_patient_request.image_uploads
        ]
        # Delete all images except those images
        placeholders = ",".join(["%s"] * len(image_upload_ids))
        operation = f"""
            DELETE FROM pediatric_appendicitis_images
            WHERE patient_id=%s AND user_id=%s AND upload_id NOT IN ({placeholders})
        """
        params = (patient_id, current_user.id, *image_upload_ids)
        cursor.execute(operation, params)
    # If the user provided no images
    else:
        # This means the patient should have no images associated with it. This else block is necessary to prevent SQL syntax error
        operation = """
            DELETE FROM pediatric_appendicitis_images
            WHERE patient_id=%s AND user_id=%s
        """
        params = (patient_id, current_user.id)
        cursor.execute(operation, params)

    if repredict:
        image_s3_uris = [
            _get_s3_uri_for_upload_id(cursor, image_upload.upload_id, current_user.id)
            for image_upload in update_patient_request.image_uploads
        ]

        body = {
            "features": update_patient_request.features.model_dump(),
            "image_s3_uris": [uri.model_dump() for uri in image_s3_uris],
        }
        result = get_predictions(body, SAGEMAKER_ENDPOINT_NAME)
        predictions = Predictions(**result)
    else:
        predictions = Predictions.model_validate(
            patient_with_images, from_attributes=True
        )

    updated_patient = _update_patient(
        cursor=cursor,
        patient_id=patient_id,
        name=update_patient_request.name,
        features=update_patient_request.features,
        predictions=predictions,
    )

    for image_upload in update_patient_request.image_uploads:
        # Update the images to link them to the new patient
        operation = """
            UPDATE pediatric_appendicitis_images
            SET patient_id = %s, name = %s
            WHERE upload_id = %s AND user_id = %s
        """
        params = (
            patient_id,
            image_upload.name,
            image_upload.upload_id,
            current_user.id,
        )
        cursor.execute(operation, params)

    patient_with_images = package_patient_with_images(cursor, updated_patient)

    return ResponseModel[GetPatientResponseWithImages](
        data=patient_with_images,
        detail="Patient updated, predictions obtained, and URLs created successfully",
    )


@router.delete(
    "",
    summary="Delete pediatric appendicitis patients",
    description="Delete the patients with the provided IDs",
    response_description="Nothing",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to delete one or more specified patients",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "One or more patients not found",
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
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    # Verify all IDs exist
    placeholders = ",".join(["%s"] * len(patient_ids))
    operation = f"""
        SELECT id, clinician_user_id
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
        row["id"] for row in rows if row["clinician_user_id"] != current_user.id
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

    return


@router.post(
    "/{patient_id}/email",
    summary="Set pediatric appendicitis patient's email",
    description="Set a patient's email. This will either set it as pending in the patient record or actually link the patient user account to it",
    response_model=ResponseModel[GetPatientResponseWithImages],
    response_description="The updated patient info with images",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to edit the requested patient's email",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "Email is invalid due to data circumstances",
        },
    },
    dependencies=[
        Depends(validate_pediatric_appendicitis_patient_id),
    ],
)
async def set_patient_email(
    patient_id: int,
    set_patient_email_request: SetPatientEmailRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    await insert_pending_email(
        cursor=cursor,
        email=set_patient_email_request.email,
        target_patient_id=patient_id,
        target_patient_table="pediatric_appendicitis_patients",
        clinician_first_name=current_user.first_name,
        clinician_last_name=current_user.last_name,
    )

    # Re-fetch the patient to get it with the updated email and potentially user information
    updated_patient = get_pediatric_appendicitis_patient_by_id(
        cursor=cursor, patient_id=patient_id
    )

    patient_with_images = package_patient_with_images(cursor, updated_patient)

    return ResponseModel[GetPatientResponseWithImages](
        data=patient_with_images, detail="Successfully assigned email"
    )
