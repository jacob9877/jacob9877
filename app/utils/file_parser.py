import csv
import io

from fastapi import HTTPException, status
from pydantic import BaseModel


def parse_csv(content: str, output_model: BaseModel) -> list[BaseModel]:
    patients = []
    csv_reader = csv.DictReader(io.StringIO(content))
    for row in csv_reader:
        try:
            patient = output_model(**row)
            patients.append(patient)
        except (ValueError, KeyError) as e:
            print("Error row:", row)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid CSV format or missing fields",
            ) from e

    if not patients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV has no patients",
        )
    return patients
