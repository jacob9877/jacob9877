import json
import os
import traceback
from typing import Literal, Optional

import boto3
import mysql.connector
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from pydantic import BaseModel

from app.models.breast_cancer_patient_models import (
    AddBreastCancerPatientsRequest,
    BreastCancerPatient,
    BreastCancerPatientFeatures,
    Explanation,
)
from app.models.common_models import ResponseModel
from app.utils.db import get_db_connection, user_exists
from app.utils.file_parser import parse_csv

router = APIRouter(prefix="/breast-cancer-patients", tags=["breast-cancer-patients"])

SAGEMAKER_ENDPOINT_NAME = "breast-cancer-classifier"
EXPLAINER_LAMBDA_NAME = "breast-cancer-classifier-explainer"


def get_predictions(instances: list[list[float]]) -> list[Literal[0, 1]]:
    sagemaker_client = boto3.client("sagemaker-runtime")
    response = sagemaker_client.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps({"instances": instances}),
    )
    result_raw = response["Body"].read().decode("utf-8")
    result = json.loads(result_raw)
    predictions = [
        prediction[0] if isinstance(prediction, list) else prediction
        for prediction in result["predictions"]
    ]
    return predictions


# We went with a inserting a single patient at a time because cursor.execute() returns the newly created ID whereas cursor.executemany() does not
def insert_patient(
    cursor: MySQLCursor,
    user_id: int,
    patient: BreastCancerPatientFeatures,
    diagnosis: Literal[0, 1],
) -> int:
    cursor.execute(
        """
        INSERT INTO breast_cancer_patients (
            user_id, mean_radius, mean_texture, mean_perimeter,
            mean_area, mean_smoothness, diagnosis
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            patient.mean_radius,
            patient.mean_texture,
            patient.mean_perimeter,
            patient.mean_area,
            patient.mean_smoothness,
            diagnosis,
        ),
    )
    return cursor.lastrowid


def add_patients(
    cursor: MySQLCursor,
    add_patients_request: AddBreastCancerPatientsRequest,
) -> list[str]:
    instances = [
        list(patient.model_dump(exclude={"user_id"}).values())
        for patient in add_patients_request.patients
    ]
    diagnoses = get_predictions(instances)

    assert len(diagnoses) == len(
        add_patients_request.patients
    ), "Mismatch between number of patients and diagnoses"

    inserted_ids = []
    for patient, diagnosis in zip(add_patients_request.patients, diagnoses):
        pid = insert_patient(cursor, add_patients_request.user_id, patient, diagnosis)
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

        inserted_ids = add_patients(cursor, add_patients_request)
        conn.commit()

        query = f"""
            SELECT * FROM breast_cancer_patients
            WHERE id IN ({','.join(['%s'] * len(inserted_ids))})
            ORDER BY FIELD(id, {','.join(['%s'] * len(inserted_ids))})
        """
        cursor.execute(query, inserted_ids * 2)
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
    except mysql.connector.Error as db_error:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(db_error)).model_dump(),
        )
    except Exception as e:
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

        inserted_ids = add_patients(cursor, add_patients_request)
        conn.commit()

        query = f"""
            SELECT * FROM breast_cancer_patients
            WHERE id IN ({','.join(['%s'] * len(inserted_ids))})
            ORDER BY FIELD(id, {','.join(['%s'] * len(inserted_ids))})
        """
        cursor.execute(query, inserted_ids * 2)
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
    except mysql.connector.Error as db_error:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(db_error)).model_dump(),
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


@router.put("/{patient_id}", summary="Update patient data")
def update_patient(
    patient_id: int = Path(..., description="ID of the patient to update"),
    updated_data: BreastCancerPatientFeatures = ...,  # user_id is not editable
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        # Check if patient exists
        cursor.execute(
            "SELECT * FROM breast_cancer_patients WHERE id = %s", (patient_id,)
        )
        patient = cursor.fetchone()
        if not patient:
            raise HTTPException(
                status_code=404, detail=f"Patient ID {patient_id} not found"
            )

        # Update the patient
        cursor.execute(
            """
            UPDATE breast_cancer_patients SET
                mean_radius=%s, mean_texture=%s, mean_perimeter=%s,
                mean_area=%s, mean_smoothness=%s, updated_at=NOW()
            WHERE id=%s
            """,
            (
                updated_data.mean_radius,
                updated_data.mean_texture,
                updated_data.mean_perimeter,
                updated_data.mean_area,
                updated_data.mean_smoothness,
                patient_id,
            ),
        )
        conn.commit()

        # Return the updated row
        cursor.execute(
            "SELECT * FROM breast_cancer_patients WHERE id = %s", (patient_id,)
        )
        return cursor.fetchone()

    except HTTPException as e:
        raise e

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Server error while updating patient"
        )

    finally:
        cursor.close()


@router.delete("", summary="Delete multiple patients by IDs")
def delete_patients(
    patient_ids: list[int] = Body(
        ..., embed=True, description="List of patient IDs to delete"
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        if len(patient_ids) == 0:
            raise HTTPException(status_code=400, detail="No patient IDs provided")

        cursor = conn.cursor(dictionary=True)

        # Check if all patient IDs exist
        format_ids = ",".join(["%s"] * len(patient_ids))
        cursor.execute(
            f"SELECT id FROM breast_cancer_patients WHERE id IN ({format_ids})",
            tuple(patient_ids),
        )
        found_ids = [row["id"] for row in cursor.fetchall()]

        missing_ids = list(set(patient_ids) - set(found_ids))
        if missing_ids:
            raise HTTPException(
                status_code=404, detail=f"Patient IDs not found: {missing_ids}"
            )

        # Delete patients
        cursor.execute(
            f"DELETE FROM breast_cancer_patients WHERE id IN ({format_ids})",
            tuple(patient_ids),
        )
        conn.commit()

        return {
            "message": f"Deleted {len(patient_ids)} patients successfully",
            "deleted_ids": patient_ids,
        }

    except HTTPException as e:
        raise e

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Server error while deleting patients"
        )

    finally:
        try:
            cursor.close()
        except:
            pass


def explain(
    patient_id: int,
    conn: MySQLConnection = Depends(get_db_connection),
) -> Explanation:
    """Be warned that this function may take a long time if it's a cold start for the Lambda function"""

    cursor = conn.cursor(dictionary=True)

    # Retrieve the patient's features
    cursor.execute(
        """
        SELECT mean_radius, mean_texture, mean_perimeter, mean_area, mean_smoothness
        FROM breast_cancer_patients WHERE id = %s
        """,
        patient_id,
    )
    patient_features = cursor.fetchone()

    # Invoke the explainer Lambda with the features
    lambda_client = boto3.client("lambda", region_name=os.environ["AWS_DEFAULT_REGION"])
    response = lambda_client.invoke(
        FunctionName=EXPLAINER_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(patient_features),
    )

    raw = response.get("Payload").read().decode("utf-8")
    explanation_json = json.loads(raw)
    explanation = Explanation(**explanation_json)

    # Update the patient's diagnosis in case their old diagnosis was on an earlier version of the model so maybe it will change
    cursor.execute(
        """
        UPDATE breast_cancer_patients
        SET diagnosis = %s
        WHERE id = %s
        """,
        (
            explanation.diagnosis,
            patient_id,
        ),
    )
    conn.commit()

    return explanation
