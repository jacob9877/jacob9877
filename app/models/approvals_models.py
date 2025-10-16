from pydantic import BaseModel

from app.models.common_models import ApprovalStatus


class PostBreastCancerApproval(BaseModel):
    diagnosis: ApprovalStatus | None = None


class PostPediatricAppendicitisApproval(BaseModel):
    diagnosis: ApprovalStatus | None = None
    management: ApprovalStatus | None = None
    length_of_stay: ApprovalStatus | None = None
