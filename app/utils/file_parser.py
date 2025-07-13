import csv
import io
from app.models.patient_models import AddPatientRequest
from fastapi import HTTPException

def parse_csv(content: str, user_id: int) -> list[AddPatientRequest]:
    patients =[]
    csv_reader = csv.DictReader(io.StringIO(content))
    for row in csv_reader:
        try:
            patient = AddPatientRequest(
                user_id=user_id,
                mean_radius=float(row["mean_radius"]),
                mean_texture=float(row["mean_texture"]),
                mean_perimeter=float(row["mean_perimeter"]),
                mean_area=float(row["mean_area"]),
                mean_smoothness=float(row["mean_smoothness"]),
            )
            patients.append(patient)
        except (ValueError, KeyError) as e:
            print("Error row:", row)
            raise HTTPException(
                status_code=400,
                detail="Invalid CSV format or missing fields",
            )
    return patients
