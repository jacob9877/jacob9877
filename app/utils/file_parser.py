import csv
import io

from fastapi import HTTPException, status

from app.models.breast_cancer_patient_models import BreastCancerPatientFeatures


def parse_csv(content: str) -> list[BreastCancerPatientFeatures]:
    patients = []
    csv_reader = csv.DictReader(io.StringIO(content))
    for row in csv_reader:
        try:
            patient = BreastCancerPatientFeatures(
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid CSV format or missing fields",
            )
    return patients
