from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(
        ..., description="User's email address", example="user@example.com"
    )
    password: str = Field(..., description="User's password", example="password123")


class RegisterRequest(BaseModel):
    username: str = Field(..., description="User's username", example="johndoe")
    email: EmailStr = Field(
        ..., description="User's email address", example="johndoe@gmail.com"
    )
    password: str = Field(..., description="User's password", example="password123")


class UserResponse(BaseModel):
    id: int = Field(..., description="User ID", example=1)
    username: str = Field(..., description="User's username", example="johndoe")
    email: EmailStr = Field(
        ..., description="User's email address", example="johndoe@gmail.com"
    )
