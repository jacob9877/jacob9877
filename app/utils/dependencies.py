from typing import NamedTuple

from fastapi import Depends, HTTPException, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.auth_models import TokenPayload
from app.models.breast_cancer_patient_models import (
    GetPatientResponse as GetBreastCancerPatientResponse,
)
from app.models.breast_cancer_patient_models import Patient as BreastCancerPatient
from app.models.conversation_models import Conversation
from app.models.pediatric_appendicitis_patient_models import (
    GetPatientResponse as GetPediatricAppendicitisPatientResponse,
)
from app.models.pediatric_appendicitis_patient_models import (
    Patient as PediatricAppendicitisPatient,
)
from app.models.user_models import Condition, Role, User
from app.utils.db import (
    get_breast_cancer_patient_by_id,
    get_conversation_by_id,
    get_db_cursor,
    get_pediatric_appendicitis_patient_by_id,
    get_user_by_id,
)
from app.utils.jwt import get_token_payload


class AccessPolicy(NamedTuple):
    allow_clinicians: bool = False
    patient_conditions: set[Condition] | None = None
    # patient_conditions:
    #   - None  -> patients not allowed
    #   - set{} -> only these patient conditions allowed


def clinicians_only() -> AccessPolicy:
    return AccessPolicy(allow_clinicians=True, patient_conditions=None)


def patients_with(conditions: set[Condition]) -> AccessPolicy:
    return AccessPolicy(allow_clinicians=False, patient_conditions=conditions)


def clinicians_or_patients_with(conditions: set[Condition]) -> AccessPolicy:
    return AccessPolicy(allow_clinicians=True, patient_conditions=conditions)


ALL_CONDITIONS = {Condition.BREAST_CANCER, Condition.PEDIATRIC_APPENDICITIS}


def all_registered_users() -> AccessPolicy:
    return AccessPolicy(allow_clinicians=True, patient_conditions=ALL_CONDITIONS)


def require_access(policy: AccessPolicy):
    """
    Dependency that enforces the given access policy and returns nothing.
    """

    def _dependency(token_payload: TokenPayload = Depends(get_token_payload)) -> None:
        if token_payload.role == Role.CLINICIAN:
            if policy.allow_clinicians:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clinician access not allowed",
            )

        if token_payload.role == Role.PATIENT:
            if policy.patient_conditions is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Patient access not allowed",
                )
            if token_payload.condition in policy.patient_conditions:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Patient condition '{token_payload.condition}' not allowed",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported role"
        )

    return _dependency


def get_current_user(
    token_payload: TokenPayload = Depends(get_token_payload),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
) -> User:
    user_id = int(token_payload.sub)
    user = get_user_by_id(cursor, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def validate_breast_cancer_patient_id(
    patient_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
) -> GetBreastCancerPatientResponse:
    patient = get_breast_cancer_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    if patient.clinician_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's clinical notes",
        )

    return patient


def validate_pediatric_appendicitis_patient_id(
    patient_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
) -> GetPediatricAppendicitisPatientResponse:
    patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    if patient.clinician_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's clinical notes",
        )

    return patient


def validate_conversation_id(
    conversation_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    conversation = get_conversation_by_id(cursor, conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found",
        )
    if conversation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to access conversation with ID {conversation_id}",
        )

    return conversation
