from app.models.conversation_models import AssistantSlug
from app.utils.assistants.base_assistant import Assistant
from app.utils.assistants.clinician_breast_cancer_assistant.assistant import (
    ClinicianBreastCancerAssistant,
)
from app.utils.assistants.clinician_pediatric_appendicitis_assistant.assistant import (
    ClinicianPediatricAppendicitisAssistant,
)

assistant_mapping: dict[AssistantSlug, type[Assistant]] = {
    "clinician-breast-cancer": ClinicianBreastCancerAssistant,
    "clinician-pediatric-appendicitis": ClinicianPediatricAppendicitisAssistant,
}
