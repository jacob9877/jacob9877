import json
import os
import traceback

import boto3
import mysql.connector
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/breast-cancer-patients", tags=["breast-cancer-patients"])


class AddPatientRequest(BaseModel):
    user_id: int
    mean_radius: float
    mean_texture: float
    mean_perimeter: float
    mean_area: float
    mean_smoothness: float


@router.post("/add-patient")
def add_patient(add_patient: AddPatientRequest):
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME"),
        )
        cursor = conn.cursor(dictionary=True)

        # Check if user exists before creating patient record
        cursor.execute("SELECT id FROM users WHERE id = %s", (add_patient.user_id,))
        user_exists = cursor.fetchone()

        if not user_exists:
            raise HTTPException(
                status_code=404, detail=f"User with ID {add_patient.user_id} not found"
            )

        sagemaker_client = boto3.client("sagemaker-runtime")

        patient_data = add_patient.model_dump(exclude=["user_id"])
        patient_values = list(patient_data.values())

        sagemaker_payload = {"instances": [patient_values]}

        sagemaker_response = sagemaker_client.invoke_endpoint(
            EndpointName="breast-cancer-endpoint",
            ContentType="application/json",
            Body=json.dumps(sagemaker_payload),
        )

        result = sagemaker_response["Body"].read().decode("utf-8")

        prediction = json.loads(result)["predictions"][0][0]

        diagnosis = round(prediction)

        cursor.execute(
            """
            INSERT INTO breast_cancer_patients (user_id, mean_radius, mean_texture, mean_perimeter, mean_area, mean_smoothness, diagnosis)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                add_patient.user_id,
                add_patient.mean_radius,
                add_patient.mean_texture,
                add_patient.mean_perimeter,
                add_patient.mean_area,
                add_patient.mean_smoothness,
                diagnosis,
            ),
        )

        conn.commit()

        # Get the newly created patient
        patient_id = cursor.lastrowid
        cursor.execute(
            "SELECT * FROM breast_cancer_patients WHERE id = %s", (patient_id,)
        )
        new_patient = cursor.fetchone()

        return new_patient

    except mysql.connector.IntegrityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
