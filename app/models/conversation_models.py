from datetime import datetime

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: int
    title: str


class Conversation(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
