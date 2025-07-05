import json
import os
import traceback

import boto3
import mysql.connector
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from pydantic import BaseModel, Field

from app.utils.db import get_db_connection, user_exists

router = APIRouter(prefix="/breast-cancer-patients", tags=["breast-cancer-patients"])

ENDPOINT_NAME = "breast-cancer-endpoint"


class AddPatientRequest(BaseModel):
    user_id: int = Field(gt=0, description="ID of the user to add the patient for")
    mean_radius: float = Field(gt=0)
    mean_texture: float = Field(gt=0)
    mean_perimeter: float = Field(gt=0)
    mean_area: float = Field(gt=0)
    mean_smoothness: float = Field(gt=0)


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
    "/add-patient",
    response_description="Add a new breast cancer patient with prediction",
)
def add_patient(
    add_patient_request: AddPatientRequest,
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        # Check if user exists
        cursor.execute(
            "SELECT id FROM users WHERE id = %s", (add_patient_request.user_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {add_patient_request.user_id} not found",
            )

        feature_values = list(
            add_patient_request.model_dump(exclude={"user_id"}).values()
        )
        diagnosis = get_prediction(feature_values)

        patient_id = insert_patient(cursor, add_patient_request, diagnosis)
        conn.commit()

        cursor.execute(
            "SELECT * FROM breast_cancer_patients WHERE id = %s", (patient_id,)
        )
        return cursor.fetchone()

    except HTTPException as e:
        raise e
    except mysql.connector.IntegrityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An internal error occurred.")
