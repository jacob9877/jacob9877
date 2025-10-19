from typing import Literal

from pydantic import BaseModel, model_validator
from typing_extensions import Self

from app.models.chat_models import Message
from app.models.common_models import Timestamps

AssistantSlug = Literal[
    "clinician-breast-cancer",
    "clinician-pediatric-appendicitis",
    "patient-breast-cancer",
    "patient-pediatric-appendicitis",
]


class ConversationSummary(BaseModel):
    id: int
    title: str
    patient_id: int | None = None  # If the conversation is patient-specific


class Conversation(ConversationSummary, Timestamps):
    """Database model for conversations table"""

    user_id: int
    assistant: AssistantSlug


class StartConversationRequest(BaseModel):
    user_message: str
    patient_id: int | None = None  # If the conversation is to be patient-specific
    assistant: AssistantSlug

    @model_validator(mode="after")
    def ensure_assistant_accepts_patient_id(self) -> Self:
        if (
            self.assistant
            in ["patient-breast-cancer", "patient-pediatric-appendicitis"]
            and self.patient_id is not None
        ):
            raise ValueError(
                "Providing a patient_id is not accepted for the requested assistant"
            )
        return self


class StartConversationResponse(BaseModel):
    conversation_id: int
    conversation_title: str


class GetConversationResponse(BaseModel):
    messages: list[Message]
    patient_id: int | None = None
