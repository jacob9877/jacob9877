from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: int | None = Field(
        default=None,
        description="ID of the conversation the user message belongs to. If None, will create a new conversation.",
        example=6,
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
    conversation_title: str = Field(
        description='Newly created title of the conversation. This is (currently) only created and sent back to the caller if this is the user\'s first message of the conversation. Otherwise, this will be ""',
        example="Inquiries about breast cancer",
    )
    conversation_id: int = Field(
        description="ID of the conversation the sent message belongs to. This may be old news to the caller, but will be useful if the message sent was the first of the conversation",
        example=5,
    )


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
