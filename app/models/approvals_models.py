from pydantic import BaseModel, Field

from app.models.common_models import ApprovalStatus


class PostBreastCancerApproval(BaseModel):
    diagnosis: ApprovalStatus | None = None


class PostPediatricAppendicitisApproval(BaseModel):
    diagnosis: ApprovalStatus | None = Field(default=None, example="approved")
    management: ApprovalStatus | None = Field(default=None, example="rejected")
    length_of_stay: ApprovalStatus | None = Field(default=None, example=None)
