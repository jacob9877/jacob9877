from app.models.conversation_models import AssistantSlug
from app.models.user_models import Condition, Role


def has_access_to_assistant(
    role: Role, condition: Condition | None, assistant: AssistantSlug
) -> bool:
    if role == Role.CLINICIAN and assistant not in [
        "clinician-breast-cancer",
        "clinician-pediatric-appendicitis",
    ]:
        return False

    if role == Role.PATIENT:
        if (
            condition == Condition.BREAST_CANCER
            and assistant != "patient-breast-cancer"
        ):
            return False

        elif (
            condition == Condition.PEDIATRIC_APPENDICITIS
            and assistant != "patient-pediatric-appendicitis"
        ):
            return False

    return True
