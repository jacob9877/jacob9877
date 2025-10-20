import os
from datetime import datetime
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Security,
    UploadFile,
    status,
)
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import (
    FEATURE_NAMES,
    AddPatientsRequest,
    GetPatientResponse,
    PaginatedPatients,
    UpsertPatientRequest,
)
from app.models.common_models import ResponseModel, SetPatientEmailRequest
from app.models.user_models import User, UserSummary
from app.utils.aws import bulk_send_message_to_sqs, get_predictions
from app.utils.db import (
    get_breast_cancer_patient_by_id,
    get_db_cursor,
    insert_pending_email,
)
from app.utils.dependencies import (
    clinicians_only,
    get_current_user,
    require_access,
    validate_breast_cancer_patient_id,
)
from app.utils.file_parser import parse_csv
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(
    prefix="/breast-cancer-patients",
    tags=["Breast Cancer Patients"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
    dependencies=[Security(require_access(clinicians_only()))],
)


SAGEMAKER_ENDPOINT_NAME = "breast-cancer-classifier"
EXPLAINER_LAMBDA_NAME = "breast-cancer-classifier-explainer"
EXPLANATION_QUEUE_URL = os.environ["BREAST_CANCER_EXPLANATION_QUEUE_URL"]


# We went with a inserting a single patient at a time because cursor.execute() returns the newly created ID whereas cursor.executemany() does not
def _insert_patient(
    cursor: MySQLCursorDict,
    clinician_user_id: int,
    upsert_patient_request: UpsertPatientRequest,
    diagnosis: Literal[0, 1],
) -> int:
    # Explicitly exclude email because this is not a db field, it has separate behavior
    upsert_patient_request_json = upsert_patient_request.model_dump(exclude={"email"})
    columns = ["clinician_user_id", "diagnosis"] + list(
        upsert_patient_request_json.keys()
    )
    placeholders = ", ".join(["%s"] * len(columns))
    operation = f"""
        INSERT INTO breast_cancer_patients ({", ".join(columns)})
        VALUES ({placeholders})
    """
    params = tuple(
        [clinician_user_id, diagnosis] + list(upsert_patient_request_json.values())
    )
    cursor.execute(operation, params)
    return cursor.lastrowid


def _add_patients(
    cursor: MySQLCursorDict,
    clinician_user_id: int,
    upsert_patient_requests: list[UpsertPatientRequest],
) -> list[GetPatientResponse]:
    instances = [
        [
            getattr(upsert_patient_request, feature_name)
            for feature_name in FEATURE_NAMES
        ]
        for upsert_patient_request in upsert_patient_requests
    ]
    result = get_predictions({"instances": instances}, SAGEMAKER_ENDPOINT_NAME)
    # Expect output to have key 'predictions' with value a list of singleton list predictions
    diagnoses = [prediction[0] for prediction in result["predictions"]]

    assert len(diagnoses) == len(upsert_patient_requests), (
        "Mismatch between number of patients and received diagnoses"
    )

    inserted_ids = []
    for upsert_patient_request, diagnosis in zip(upsert_patient_requests, diagnoses):
        pid = _insert_patient(
            cursor=cursor,
            clinician_user_id=clinician_user_id,
            upsert_patient_request=upsert_patient_request,
            diagnosis=diagnosis,
        )
        inserted_ids.append(pid)

    placeholders = ",".join(["%s"] * len(inserted_ids))
    operation = f"""
        SELECT
        p.*,
        CASE
            WHEN p.user_id IS NULL THEN NULL
            ELSE CAST(JSON_OBJECT(
            'first_name', u.first_name,
            'last_name', u.last_name,
            'email',    u.email
            ) AS JSON)
        END AS patient_user_info
        FROM breast_cancer_patients AS p
        LEFT JOIN users AS u
        ON u.id = p.user_id
        WHERE p.id IN ({placeholders})
        ORDER BY FIELD(p.id, {placeholders})
    """
    params = tuple(inserted_ids) + tuple(inserted_ids)
    cursor.execute(operation, params)
    rows = cursor.fetchall()

    return [GetPatientResponse(**row) for row in rows]


@router.post(
    "/single",
    summary="Add breast cancer patient",
    description="Add a breast cancer patient with the patient's email.",
    response_model=ResponseModel[GetPatientResponse],
    response_description="Returns the newly created breast cancer patient",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "Email is invalid",
        }
    },
)
def add_patient(
    add_patient_request: UpsertPatientRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    new_patient = _add_patients(
        cursor=cursor,
        clinician_user_id=current_user.id,
        upsert_patient_requests=[add_patient_request],
    )[0]

    if add_patient_request.email:
        insert_pending_email(
            cursor,
            add_patient_request.email,
            new_patient.id,
            "breast_cancer_patients",
        )

    # Re-fetch the patient to get it with the updated email and potentially user information
    inserted_patient = get_breast_cancer_patient_by_id(
        cursor=cursor, patient_id=new_patient.id
    )

    # Send the new patient info to SQS for explanation processing
    messages = [
        inserted_patient.model_dump(include=FEATURE_NAMES)
        | {"patient_id": inserted_patient.id}
    ]
    bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

    return ResponseModel[GetPatientResponse](
        data=inserted_patient, detail="Patients added successfully"
    )


@router.post(
    "",
    summary="Add multiple breast cancer patients",
    description="Add multiple breast cancer patients with their features and user ID. When trying to add 1 patient send a list with 1 element",
    response_model=ResponseModel[list[GetPatientResponse]],
    response_description="Returns the newly created breast cancer patients",
    status_code=status.HTTP_201_CREATED,
)
def add_patients_json(
    add_patients_request: AddPatientsRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    upsert_patient_requests = [
        UpsertPatientRequest.model_validate(patient_features)
        for patient_features in add_patients_request.patients
    ]
    inserted_patients = _add_patients(
        cursor=cursor,
        clinician_user_id=current_user.id,
        upsert_patient_requests=upsert_patient_requests,
    )

    for upsert_patient_request, inserted_patient in zip(
        upsert_patient_requests, inserted_patients
    ):
        insert_pending_email(
            cursor=cursor,
            email=upsert_patient_request.email,
            target_patient_id=inserted_patient.id,
            target_patient_table="breast_cancer_patients",
        )

    # Send the new patient info to SQS for explanation processing
    messages = [
        patient.model_dump(include=FEATURE_NAMES) | {"patient_id": patient.id}
        for patient in inserted_patients
    ]
    bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

    return ResponseModel[list[GetPatientResponse]](
        data=inserted_patients, detail="Patients added successfully"
    )


@router.post(
    "/csv",
    summary="Add multiple breast cancer patients via CSV upload",
    description="Add multiple breast cancer patients with their features and user ID",
    response_model=ResponseModel[list[GetPatientResponse]],
    response_description="Returns the newly created breast cancer patients",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "CSV is invalid",
        }
    },
)
def add_patients_csv(
    file: UploadFile | None = File(None),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    file.file.seek(0)
    content = file.file.read().decode("utf-8")
    upsert_patient_requests: list[UpsertPatientRequest] = parse_csv(
        content=content, output_model=UpsertPatientRequest
    )

    inserted_patients = _add_patients(
        cursor=cursor,
        clinician_user_id=current_user.id,
        upsert_patient_requests=upsert_patient_requests,
    )

    for upsert_patient_request, inserted_patient in zip(
        upsert_patient_requests, inserted_patients
    ):
        insert_pending_email(
            cursor=cursor,
            email=upsert_patient_request.email,
            target_patient_id=inserted_patient.id,
            target_patient_table="breast_cancer_patients",
        )

    # Send the new patient info to SQS for explanation processing
    messages = [
        patient.model_dump(include=FEATURE_NAMES) | {"patient_id": patient.id}
        for patient in inserted_patients
    ]
    bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

    return ResponseModel[list[GetPatientResponse]](
        data=inserted_patients, detail="Patients added successfully"
    )


@router.get(
    "/{patient_id}",
    summary="Get a patient by ID",
    response_model=ResponseModel[GetPatientResponse],
    response_description="Returns the breast cancer patient with the provided ID",
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
    patient: GetPatientResponse = Depends(validate_breast_cancer_patient_id),
):
    return ResponseModel[GetPatientResponse](
        data=patient, detail="Patient fetched successfully"
    )


@router.get(
    "",
    summary="Get breast cancer patients for the logged-in user (cursor-based pagination)",
    description=(
        "Retrieves breast cancer patients for the current user (by the provided access token) using cursor-based pagination, "
        "sorted by most recently updated."
    ),
    response_model=ResponseModel[PaginatedPatients],
    response_description="Returns a page of patients plus a next_cursor if more data exists",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Cursor is invalid",
        }
    },
)
def get_breast_cancer_patients_paginated(
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
        FROM breast_cancer_patients AS p
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
        FROM breast_cancer_patients AS p
        WHERE p.clinician_user_id = %s
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


def _update_and_repredict(
    *,
    cursor: MySQLCursorDict,
    patient_id: int,
    upsert_patient_request: UpsertPatientRequest,
) -> GetPatientResponse:
    # Re-predict
    instance = [
        getattr(upsert_patient_request, feature_name) for feature_name in FEATURE_NAMES
    ]
    result = get_predictions({"instances": [instance]}, SAGEMAKER_ENDPOINT_NAME)

    new_diagnosis = result["predictions"][0][0]

    upsert_patient_request_json = upsert_patient_request.model_dump(exclude={"email"})
    columns = ["diagnosis"] + list(upsert_patient_request_json.keys())
    set_clause = ", ".join(f"{column}=%s" for column in columns)
    operation = f"""
        UPDATE breast_cancer_patients
        SET {set_clause}
        WHERE id=%s
    """
    params = tuple(
        [new_diagnosis] + list(upsert_patient_request_json.values()) + [patient_id]
    )
    cursor.execute(operation, params)

    updated_patient = get_breast_cancer_patient_by_id(
        cursor=cursor, patient_id=patient_id
    )
    return updated_patient


# @router.post(
#     "/{patient_id}/repredict",
#     summary="Re-predict a patient's diagnosis",
#     description="Re-predicts and saves the patient's diagnosis using the latest model. **No request body.**",
#     response_model=ResponseModel[GetPatientResponse],
#     response_description="Returns the updated patient with the new diagnosis",
#     status_code=status.HTTP_200_OK,
#     responses={
#         status.HTTP_403_FORBIDDEN: {
#             "model": ResponseModel[None],
#             "description": "Not authorized to perform the requested action",
#         },
#         status.HTTP_404_NOT_FOUND: {
#             "model": ResponseModel[None],
#             "description": "Patient not found",
#         },
#     },
#     dependencies=[
#         Depends(validate_breast_cancer_patient_id),
#     ],
# )
# def repredict_patient(
#     patient_id: int = Path(..., description="ID of the patient to re-predict"),
#     cursor: MySQLCursorDict = Depends(get_db_cursor),
# ):
#     updated_patient = _update_and_repredict(
#         cursor=cursor,
#         patient_id=patient_id,
#     )

#     # Send the new patient info to SQS for explanation processing
#     messages = [
#         updated_patient.model_dump(include=set(FEATURE_NAMES))
#         | {"patient_id": updated_patient.id}
#     ]
#     bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

#     return ResponseModel[GetBreastCancerPatientResponse](
#         data=updated_patient, detail="Re-predicted successfully"
#     )


@router.put(
    "/{patient_id}",
    summary="Update a patient (and re-predict)",
    description="Provide any subset of features to update; the diagnosis is always re-predicted and saved.",
    response_model=ResponseModel[GetPatientResponse],
    response_description="Returns the updated patient",
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
    dependencies=[
        Depends(validate_breast_cancer_patient_id),
    ],
)
def update_patient(
    patient_id: int,
    update_patient_request: UpsertPatientRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    updated_patient = _update_and_repredict(
        cursor=cursor,
        patient_id=patient_id,
        upsert_patient_request=update_patient_request,
    )

    if update_patient_request.email:
        insert_pending_email(
            cursor=cursor,
            email=update_patient_request.email,
            target_patient_id=patient_id,
            target_patient_table="breast_cancer_patients",
        )

    # Send the new patient info to SQS for explanation processing
    messages = [
        updated_patient.model_dump(include=set(FEATURE_NAMES))
        | {"patient_id": updated_patient.id}
    ]
    bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

    return ResponseModel[GetPatientResponse](
        data=updated_patient, detail="Patient updated successfully"
    )


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
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):
    # Verify all IDs exist
    placeholders = ",".join(["%s"] * len(patient_ids))
    operation = f"""
        SELECT id, clinician_user_id
        FROM breast_cancer_patients
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
        DELETE FROM breast_cancer_patients
        WHERE id IN ({placeholders})
    """
    params = tuple(patient_ids)
    cursor.execute(operation, params)

    return ResponseModel[list[int]](
        data=patient_ids,
        detail=f"Deleted {len(patient_ids)} patients successfully",
    )


@router.post(
    "/{patient_id}/email",
    summary="Set a patient's email",
    description="Set a patient's email. This will either set it as pending in the patient record or actually link the patient user account to it",
    response_model=ResponseModel[GetPatientResponse],
    response_description="The updated patient info",
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
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "Conflict when linking email",
        },
    },
    dependencies=[
        Depends(validate_breast_cancer_patient_id),
    ],
)
def set_patient_email(
    patient_id: int,
    set_patient_email_request: SetPatientEmailRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    insert_pending_email(
        cursor=cursor,
        email=set_patient_email_request.email,
        target_patient_id=patient_id,
        target_patient_table="breast_cancer_patients",
    )

    # Re-fetch the patient to get it with the updated email and potentially user information
    inserted_patient = get_breast_cancer_patient_by_id(
        cursor=cursor, patient_id=patient_id
    )

    return ResponseModel[GetPatientResponse](
        data=inserted_patient, detail="Successfully assigned email"
    )
