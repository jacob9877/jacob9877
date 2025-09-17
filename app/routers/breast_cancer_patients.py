import json
import os
import traceback
from datetime import datetime
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import (
    FEATURE_NAMES,
    AddBreastCancerPatientsRequest,
    BreastCancerPatient,
    BreastCancerPatientFeatures,
    PaginatedBreastCancerPatients,
    UpdateBreastCancerPatientRequest,
)
from app.models.common_models import ResponseModel
from app.utils.aws import bulk_send_message_to_sqs, get_predictions
from app.utils.db import get_breast_cancer_patient_by_id, get_db_connection
from app.utils.file_parser import parse_csv
from app.utils.jwt import get_and_validate_current_user_id
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
)

SAGEMAKER_ENDPOINT_NAME = "breast-cancer-classifier"
EXPLAINER_LAMBDA_NAME = "breast-cancer-classifier-explainer"
EXPLANATION_QUEUE_URL = os.environ["BREAST_CANCER_EXPLANATION_QUEUE_URL"]


# We went with a inserting a single patient at a time because cursor.execute() returns the newly created ID whereas cursor.executemany() does not
def _insert_patient(
    cursor: MySQLCursorDict,
    user_id: int,
    patient: BreastCancerPatientFeatures,
    diagnosis: Literal[0, 1],
) -> int:
    column_names = ["user_id", *FEATURE_NAMES, "diagnosis"]
    placeholders = ", ".join(["%s"] * len(column_names))
    operation = f"""
        INSERT INTO breast_cancer_patients ({", ".join(column_names)})
        VALUES ({placeholders})
    """
    params = tuple(
        [user_id]
        + [getattr(patient, feature_name) for feature_name in FEATURE_NAMES]
        + [diagnosis]
    )
    cursor.execute(operation, params)
    return cursor.lastrowid


def _add_patients(
    cursor: MySQLCursorDict,
    user_id: int,
    add_patients_request: AddBreastCancerPatientsRequest,
) -> list[int]:
    instances = [
        list(patient.model_dump(exclude={"user_id"}).values())
        for patient in add_patients_request.patients
    ]
    diagnoses = get_predictions({"instances": instances}, SAGEMAKER_ENDPOINT_NAME)

    assert len(diagnoses) == len(
        add_patients_request.patients
    ), "Mismatch between number of patients and diagnoses"

    inserted_ids = []
    for patient, diagnosis in zip(add_patients_request.patients, diagnoses):
        pid = _insert_patient(cursor, user_id, patient, diagnosis)
        inserted_ids.append(pid)

    return inserted_ids


@router.post(
    "",
    summary="Add multiple breast cancer patients",
    description="Add multiple breast cancer patients with their features and user ID. When trying to add 1 patient send a list with 1 element",
    response_model=ResponseModel[list[BreastCancerPatient]],
    response_description="Returns the newly created breast cancer patients",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "CSV is invalid",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User not found",
        },
    },
)
def add_patients_json(
    add_patients_request: AddBreastCancerPatientsRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            inserted_ids = _add_patients(cursor, current_user_id, add_patients_request)
            conn.commit()
            # We can't put all this fetching of the patients logic inside the _add_patients function because we need the connection to commit the new patients beforehand
            placeholders = ",".join(["%s"] * len(inserted_ids))
            operation = f"""
                SELECT * 
                FROM breast_cancer_patients
                WHERE id IN ({placeholders})
                ORDER BY FIELD(id, {placeholders})
            """
            params = tuple(inserted_ids) * 2
            cursor.execute(operation, params)
            rows = cursor.fetchall()

        inserted_patients = [BreastCancerPatient(**row) for row in rows]

        # Send the new patient info to SQS for explanation processing
        messages = [
            patient.model_dump(include=set(FEATURE_NAMES)) | {"patient_id": patient.id}
            for patient in inserted_patients
        ]
        bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

        return ResponseModel[list[BreastCancerPatient]](
            data=inserted_patients, detail="Patients added successfully"
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.post(
    "/csv",
    summary="Add multiple breast cancer patients via CSV upload",
    description="Add multiple breast cancer patients with their features and user ID",
    response_model=ResponseModel[list[BreastCancerPatient]],
    response_description="Returns the newly created breast cancer patients",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "CSV is invalid",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User not found",
        },
    },
)
def add_patients_csv(
    file: Optional[UploadFile] = File(None),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:

        file.file.seek(0)
        content = file.file.read().decode("utf-8")
        parsed_patients = parse_csv(content)
        print(f"Parsed {len(parsed_patients)} patients from CSV.")

        # Load into request class to validate there's at least 1 patient
        add_patients_request = AddBreastCancerPatientsRequest(patients=parsed_patients)

        with conn.cursor(dictionary=True) as cursor:
            inserted_ids = _add_patients(cursor, current_user_id, add_patients_request)
            conn.commit()
            # We can't put all this fetching of the patients logic inside the _add_patients function because we need the connection to commit the new patients beforehand
            placeholders = ",".join(["%s"] * len(inserted_ids))
            operation = f"""
                SELECT *
                FROM breast_cancer_patients
                WHERE id IN ({placeholders})
                ORDER BY FIELD(id, {placeholders})
            """
            params = tuple(inserted_ids) * 2
            cursor.execute(operation, params)
            rows = cursor.fetchall()

        inserted_patients = [BreastCancerPatient(**row) for row in rows]

        # Send the new patient info to SQS for explanation processing
        messages = [
            patient.model_dump(include=set(FEATURE_NAMES)) | {"patient_id": patient.id}
            for patient in inserted_patients
        ]
        bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

        return ResponseModel[list[BreastCancerPatient]](
            data=inserted_patients, detail="Patients added successfully"
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.get(
    "/{patient_id}",
    summary="Get a patient by ID",
    response_model=ResponseModel[BreastCancerPatient],
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
    patient_id: int = Path(..., description="ID of the patient to get"),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_breast_cancer_patient_by_id(cursor, patient_id)

        if patient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Breast cancer patient with ID {patient_id} not found",
            )

        if patient.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized to access this patient",
            )

        return ResponseModel[BreastCancerPatient](
            data=patient, detail="Patient fetched successfully"
        )

    except Exception as e:
        traceback.print_exc()
        raise e


@router.get(
    "",
    summary="Get breast cancer patients for the logged-in user (cursor-based pagination)",
    description=(
        "Retrieves breast cancer patients for the current user (by the provided access token) using cursor-based pagination, "
        "sorted by most recently updated."
    ),
    response_model=ResponseModel[PaginatedBreastCancerPatients],
    response_description="Returns a page of patients plus a next_cursor if more data exists",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Cursor is invalid",
        }
    },
)
def get_user_breast_cancer_patients_paginated(
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
            FROM breast_cancer_patients
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

        patients = [BreastCancerPatient(**row) for row in rows]

        next_cursor: Optional[str] = None
        if has_more and rows:
            last_row = rows[-1]
            last_updated_at: datetime = last_row["updated_at"]
            last_row_id: int = last_row["id"]
            next_cursor = encode_cursor(last_updated_at, last_row_id)

        paginated_patients = PaginatedBreastCancerPatients(
            next_cursor=next_cursor,
            patients=patients,
        )
        return ResponseModel[PaginatedBreastCancerPatients](
            data=paginated_patients,
            detail="Patients retrieved successfully",
        )

    except Exception as e:
        traceback.print_exc()
        raise e


def _update_and_repredict(
    *,
    cursor: MySQLCursorDict,
    patient_id: int,
    partial_update: Optional[
        UpdateBreastCancerPatientRequest
    ] = UpdateBreastCancerPatientRequest(),  # None -> repredict-only
) -> BreastCancerPatient:

    # Fetch current features
    operation = f"""
        SELECT {', '.join(FEATURE_NAMES)}
        FROM breast_cancer_patients
        WHERE id=%s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()

    current_features = BreastCancerPatientFeatures(**row)

    # Merge features
    incoming = partial_update.model_dump(exclude_unset=True)
    combined_features = current_features.model_copy(update=incoming)

    # Re-predict
    instance = [
        getattr(combined_features, feature_name) for feature_name in FEATURE_NAMES
    ]
    new_diagnosis = get_predictions([instance], SAGEMAKER_ENDPOINT_NAME)[0]

    # Figure out which columns truly changed
    changed_features = [
        feature_name
        for feature_name in FEATURE_NAMES
        if getattr(combined_features, feature_name)
        != getattr(current_features, feature_name)
    ]

    # Build the SQL update query dynamically based on which features actually changed (update the diagnosis no matter what)
    column_names = changed_features + ["diagnosis"]
    set_clause = ", ".join(f"{column_name}=%s" for column_name in column_names)
    operation = f"""
        UPDATE breast_cancer_patients
        SET {set_clause}
        WHERE id=%s
    """
    params = tuple(
        [getattr(combined_features, feature_name) for feature_name in changed_features]
        + [
            new_diagnosis,
            patient_id,
        ]
    )
    cursor.execute(operation, params)

    # Return full row
    operation = """
        SELECT *
        FROM breast_cancer_patients
        WHERE id=%s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    return BreastCancerPatient(**row)


@router.post(
    "/{patient_id}/repredict",
    summary="Re-predict a patient's diagnosis",
    description="Re-predicts and saves the patient's diagnosis using the latest model. **No request body.**",
    response_model=ResponseModel[BreastCancerPatient],
    response_description="Returns the updated patient with the new diagnosis",
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
def repredict_patient(
    patient_id: int = Path(..., description="ID of the patient to re-predict"),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_breast_cancer_patient_by_id(cursor, patient_id)

            if patient is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Breast cancer patient with ID {patient_id} not found",
                )

            if patient.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to modify this patient",
                )

            updated_patient = _update_and_repredict(
                cursor=cursor,
                patient_id=patient_id,
            )

        conn.commit()

        # Send the new patient info to SQS for explanation processing
        messages = [
            updated_patient.model_dump(include=set(FEATURE_NAMES))
            | {"patient_id": updated_patient.id}
        ]
        bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

        return ResponseModel[BreastCancerPatient](
            data=updated_patient, detail="Re-predicted successfully"
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.patch(
    "/{patient_id}",
    summary="Update a patient (and re-predict)",
    description="Provide any subset of features to update; the diagnosis is always re-predicted and saved.",
    response_model=ResponseModel[BreastCancerPatient],
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
)
def update_patient(
    patient_id: int = Path(..., description="ID of the patient to update"),
    new_patient_data: UpdateBreastCancerPatientRequest = Body(
        ..., description="Fields to update (at least one)"
    ),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            patient = get_breast_cancer_patient_by_id(cursor, patient_id)

            if patient is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Breast cancer patient with ID {patient_id} not found",
                )

            if patient.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to modify this patient",
                )

            updated_patient = _update_and_repredict(
                cursor=cursor,
                patient_id=patient_id,
                partial_update=new_patient_data,
            )

        conn.commit()

        # Send the new patient info to SQS for explanation processing
        messages = [
            updated_patient.model_dump(include=set(FEATURE_NAMES))
            | {"patient_id": updated_patient.id}
        ]
        bulk_send_message_to_sqs(queue_url=EXPLANATION_QUEUE_URL, messages=messages)

        return ResponseModel[BreastCancerPatient](
            data=updated_patient, detail="Patient updated successfully"
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
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            # Verify all IDs exist
            placeholders = ",".join(["%s"] * len(patient_ids))
            operation = f"""
                SELECT id, user_id
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
                row["id"] for row in rows if row["user_id"] != current_user_id
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

        conn.commit()

        return ResponseModel[list[int]](
            data=patient_ids,
            detail=f"Deleted {len(patient_ids)} patients successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e
