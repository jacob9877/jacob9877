import json
import traceback
import io
import csv
from typing import List, Optional

import boto3
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from app.models.patient_models import AddPatientRequest
from app.utils.db import get_db_connection, user_exists
from app.utils.file_parser import parse_csv

router = APIRouter(prefix="/breast-cancer-patients", tags=["breast-cancer-patients"])

ENDPOINT_NAME = "breast-cancer-endpoint"

def get_prediction(instance: list[float]) -> int:
    sagemaker_client = boto3.client("sagemaker-runtime")
    response = sagemaker_client.invoke_endpoint(
        EndpointName=ENDPOINT_NAME,
        ContentType="application/json",
        Body=json.dumps({"instances": [instance]}),
    )
    result = response["Body"].read().decode("utf-8")
    prediction = json.loads(result)["predictions"][0][0]
    return round(prediction)  # Apply the threshold of 0.5 to classify as 0 or 1


def insert_patient(
    cursor: MySQLCursor, request: AddPatientRequest, diagnosis: int
) -> int:
    cursor.execute(
        """
        INSERT INTO breast_cancer_patients (
            user_id, mean_radius, mean_texture, mean_perimeter,
            mean_area, mean_smoothness, diagnosis
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            request.user_id,
            request.mean_radius,
            request.mean_texture,
            request.mean_perimeter,
            request.mean_area,
            request.mean_smoothness,
            diagnosis,
        ),
    )
    return cursor.lastrowid


@router.post(
    "/add-patients",
    summary="Add patients multiple patients via JSON or CSV",
    description="""
This endpoint allows adding multiple breast cancer patients.

You must provide `user_id` **and either**:
- A `.csv` file (as `file`) with columns: `mean_radius`, `mean_texture`, `mean_perimeter`, `mean_area`, `mean_smoothness` in the respective order.
- OR a `patients` field (as JSON string) containing a list of patient entries in the following format:
    {
    "mean_radius": 12.7,
    "mean_texture": 18.9,
    "mean_perimeter": 87.2,
    "mean_area": 650.1,
    "mean_smoothness": 0.09
    }
- **Only one of `file` or `patients` should be provided per request.**
""",
)
def add_patients(
    user_id: int = Form(...),
    file: Optional[UploadFile] = File(None),
    patients: Optional[str] = Form(
        default=None,
        description="JSON string of patient records",
        example='[{"mean_radius":12.3,"mean_texture":14.1,"mean_perimeter":90.2,"mean_area":650.5,"mean_smoothness":0.09}]',
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, user_id):
            raise HTTPException(
                status_code=404, detail=f"User with ID {user_id} not found"
            )

        inserted_ids = []

        # CSV Upload Handling
        if file:
            try:
                file.file.seek(0)
                content = file.file.read().decode("utf-8")  # ✅ only read once
                parsed_patients = parse_csv(
                    content, user_id
                )  # ⛔ check this function separately

                for patient in parsed_patients:
                    features = list(patient.model_dump(exclude={"user_id"}).values())
                    diagnosis = get_prediction(features)
                    pid = insert_patient(cursor, patient, diagnosis)
                    inserted_ids.append(pid)
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(status_code=400, detail="Failed to parse CSV file")

        # JSON Body Handling
        elif patients:
            try:
                patient_list = json.loads(patients)
                for patient_data in patient_list:
                    patient = AddPatientRequest(user_id=user_id, **patient_data)
                    features = list(patient.model_dump(exclude={"user_id"}).values())
                    diagnosis = get_prediction(features)
                    pid = insert_patient(cursor, patient, diagnosis)
                    inserted_ids.append(pid)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON format")
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(
                    status_code=400, detail="Error processing patient JSON"
                )

        else:
            raise HTTPException(
                status_code=400, detail="Provide either a CSV file or JSON data."
            )

        conn.commit()

        if inserted_ids:
            query = f"""
                SELECT * FROM breast_cancer_patients
                WHERE id IN ({','.join(['%s'] * len(inserted_ids))})
                ORDER BY FIELD(id, {','.join(['%s'] * len(inserted_ids))})
            """
            cursor.execute(query, inserted_ids * 2)
            return cursor.fetchall()
        else:
            return {"message": "No patients added."}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Server error while adding patients."
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
