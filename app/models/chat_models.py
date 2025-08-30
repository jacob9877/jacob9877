from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: int = Field(
        ..., description="ID of the conversation the user message belongs to."
    )
    user_message: str = Field(
        ...,
        description="Message the user sent",
        example="What are common struggles during recovery?",
    )


class ChatResponse(BaseModel):
    assistant_reply: str = Field(
        ...,
        description="AI's reply to the message",
        example="As requested, here are some common struggles...",
    )


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
