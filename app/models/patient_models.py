from pydantic import BaseModel, Field


class AddPatientRequest(BaseModel):
    user_id: int = Field(gt=0, description="ID of the user to add the patient for")
    mean_radius: float = Field(gt=0)
    mean_texture: float = Field(gt=0)
    mean_perimeter: float = Field(gt=0)
    mean_area: float = Field(gt=0)
    mean_smoothness: float = Field(gt=0)
