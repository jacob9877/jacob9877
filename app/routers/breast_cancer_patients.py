import json
import os
import traceback
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from app.models.breast_cancer_patient_models import (
    FEATURE_NAMES,
    AddBreastCancerPatientsRequest,
    BreastCancerPatient,
    BreastCancerPatientFeatures,
    UpdateBreastCancerPatientRequest,
)
from app.models.common_models import ResponseModel
from app.utils.aws import get_predictions
from app.utils.db import get_db_connection, user_exists
from app.utils.file_parser import parse_csv

router = APIRouter(prefix="/breast-cancer-patients", tags=["breast-cancer-patients"])

SAGEMAKER_ENDPOINT_NAME = "breast-cancer-classifier"
EXPLAINER_LAMBDA_NAME = "breast-cancer-classifier-explainer"


# We went with a inserting a single patient at a time because cursor.execute() returns the newly created ID whereas cursor.executemany() does not
def _insert_patient(
    cursor: MySQLCursor,
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
    cursor: MySQLCursor,
    add_patients_request: AddBreastCancerPatientsRequest,
) -> list[int]:
    instances = [
        list(patient.model_dump(exclude={"user_id"}).values())
        for patient in add_patients_request.patients
    ]
    diagnoses = get_predictions(instances, SAGEMAKER_ENDPOINT_NAME)

    assert len(diagnoses) == len(
        add_patients_request.patients
    ), "Mismatch between number of patients and diagnoses"

    inserted_ids = []
    for patient, diagnosis in zip(add_patients_request.patients, diagnoses):
        pid = _insert_patient(cursor, add_patients_request.user_id, patient, diagnosis)
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
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def add_patients_json(
    add_patients_request: AddBreastCancerPatientsRequest,
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, add_patients_request.user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {add_patients_request.user_id} not found",
            )

        inserted_ids = _add_patients(cursor, add_patients_request)
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
        return ResponseModel[list[BreastCancerPatient]](
            data=inserted_patients, detail="Patients added successfully"
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        cursor.close()


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
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def add_patients_csv(
    user_id: int = Form(...),
    file: Optional[UploadFile] = File(None),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        file.file.seek(0)
        content = file.file.read().decode("utf-8")
        parsed_patients = parse_csv(content)
        print(f"Parsed {len(parsed_patients)} patients from CSV.")

        # Load into request class to validate there's at least 1 patient
        add_patients_request = AddBreastCancerPatientsRequest(
            user_id=user_id, patients=parsed_patients
        )

        inserted_ids = _add_patients(cursor, add_patients_request)
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
        return ResponseModel[list[BreastCancerPatient]](
            data=inserted_patients, detail="Patients added successfully"
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


@router.get(
    "/{patient_id}",
    summary="Get a patient by ID",
    response_model=ResponseModel[BreastCancerPatient],
    response_description="Returns the breast cancer patient with the provided ID",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def get_patient(
    patient_id: int = Path(..., description="ID of the patient to get"),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        operation = """
            SELECT *
            FROM breast_cancer_patients
            WHERE id = %s
        """
        params = (patient_id,)
        cursor.execute(operation, params)

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Breast cancer patient with ID {patient_id} not found",
            )

        return ResponseModel[BreastCancerPatient](
            data=BreastCancerPatient(**row), detail="Patient fetched successfully"
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )

    finally:
        cursor.close()


def _update_and_repredict(
    *,
    cursor,
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
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Breast cancer patient with ID {patient_id} not found",
        )

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
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def repredict_patient(
    patient_id: int = Path(..., description="ID of the patient to re-predict"),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        updated_patient = _update_and_repredict(cursor=cursor, patient_id=patient_id)
        conn.commit()
        return ResponseModel[BreastCancerPatient](
            data=updated_patient, detail="Re-predicted successfully"
        )
    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


@router.patch(
    "/{patient_id}",
    summary="Update a patient (and re-predict)",
    description="Provide any subset of features to update; the diagnosis is always re-predicted and saved.",
    response_model=ResponseModel[BreastCancerPatient],
    response_description="Returns the updated patient",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def update_patient(
    patient_id: int = Path(..., description="ID of the patient to update"),
    new_patient_data: UpdateBreastCancerPatientRequest = Body(
        ..., description="Fields to update (at least one)"
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        updated_patient = _update_and_repredict(
            cursor=cursor, patient_id=patient_id, partial_update=new_patient_data
        )
        conn.commit()
        return ResponseModel[BreastCancerPatient](
            data=updated_patient, detail="Patient updated successfully"
        )
    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


@router.delete(
    "",
    summary="Delete multiple patients by IDs",
    description="Deletes the patients whose IDs are provided",
    response_model=ResponseModel[list[int]],
    response_description="Returns the list of IDs that were deleted",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "One or more patient IDs not found",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
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
):
    try:
        cursor = conn.cursor(dictionary=True)

        # Verify all IDs exist
        placeholders = ",".join(["%s"] * len(patient_ids))
        operation = f"""
            SELECT id
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

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()
