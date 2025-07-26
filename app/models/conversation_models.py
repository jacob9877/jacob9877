from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: int
    title: str
