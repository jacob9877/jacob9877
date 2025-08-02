from typing import Literal

from pydantic import BaseModel, Field


class StartConversationRequest(BaseModel):
    user_id: int = Field(
        ..., description="ID of the user who the conversation will belong to", example=1
    )


class StartConversationResponse(BaseModel):
    conversation_id: int = Field(..., description="ID of the created conversation")
    title: str = Field(
        ...,
        description="Created title of the conversation (logic around this is subject to change)",
    )
    assistant_message: str = Field(
        ...,
        description="Initial conversation message to be displayed to the user",
        example="Hi, I'm your AI assistant. How can I help?",
    )


class ChatRequest(BaseModel):
    conversation_id: int = Field(
        ..., description="ID of the conversation the message belongs to", example=1
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


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
