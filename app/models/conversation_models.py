from datetime import datetime

from pydantic import BaseModel

from app.models.chat_models import Message


class ConversationSummary(BaseModel):
    id: int
    title: str
    patient_id: int | None = None  # If the conversation is patient-specific


class Conversation(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    patient_id: int | None = None  # If the conversation is patient-specific


class StartConversationRequest(BaseModel):
    user_message: str
    patient_id: int | None = None  # If the conversation is patient-specific


class StartConversationResponse(BaseModel):
    conversation_id: int
    conversation_title: str


class GetConversationResponse(BaseModel):
    messages: list[Message]
    patient_id: int | None = None
