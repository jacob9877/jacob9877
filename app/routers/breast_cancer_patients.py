import json
import traceback
from typing import List, Optional

import boto3
from fastapi import APIRouter, Path, Depends, File, Form, HTTPException, UploadFile, Body
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from app.models.patient_models import AddPatientRequest, AddPatientPayload, AddPatient
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

@router.post("/add-patients-csv", summary="Add multiple patients via CSV upload")
def add_patients_csv(
    user_id: int = Form(...),
    file: Optional[UploadFile] = File(None),    
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, user_id):
            raise HTTPException(status_code=404, detail=f"User with ID {user_id} not found")

        file.file.seek(0)
        content = file.file.read().decode("utf-8")
        parsed_patients = parse_csv(content, user_id)
        print(f"Parsed {len(parsed_patients)} patients from CSV.")


        inserted_ids = []
        for patient in parsed_patients:
            features = list(patient.model_dump(exclude={"user_id"}).values())
            diagnosis = get_prediction(features)
            pid = insert_patient(cursor, patient, diagnosis)
            inserted_ids.append(pid)

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
    
    except HTTPException as e:
        raise e

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process CSV.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.post("/add-patients-json", summary="Add multiple patients via JSON body")
def add_patients_json(
    payload: AddPatientPayload,
    conn: MySQLConnection = Depends(get_db_connection),
):
    cursor = conn.cursor(dictionary=True)
    try:
        if not user_exists(cursor, payload.user_id):
            raise HTTPException(status_code=404, detail=f"User with ID {payload.user_id} not found")

        inserted_ids = []
        for patient_data in payload.patients:
            patient = AddPatientRequest(user_id=payload.user_id, **patient_data.dict())
            features = list(patient.model_dump(exclude={"user_id"}).values())
            diagnosis = get_prediction(features)
            pid = insert_patient(cursor, patient, diagnosis)
            inserted_ids.append(pid)

        conn.commit()

        if inserted_ids:
            query = f"""
                SELECT * FROM breast_cancer_patients
                WHERE id IN ({','.join(['%s'] * len(inserted_ids))})
                ORDER BY FIELD(id, {','.join(['%s'] * len(inserted_ids))})
            """
            cursor.execute(query, inserted_ids * 2)
            return cursor.fetchall()
        return {"message": "No patients added."}
    
    except HTTPException as e:
        raise e

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process JSON.")
    finally:
        cursor.close()
        conn.close()

@router.put("/{patient_id}", summary="Update patient data")
def update_patient(
    patient_id: int = Path(..., description="ID of the patient to update"),
    updated_data: AddPatient = ...,  # user_id is not editable
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
        conn.close()


@router.delete("/batch-delete", summary="Delete multiple patients by ID")
def delete_patients(
    patient_ids: List[int] = Body(..., embed=True, description="List of patient IDs to delete"),
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
            conn.close()
        except:
            pass
