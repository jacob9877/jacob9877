from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., description="User's username", example="johndoe")
    email: EmailStr = Field(
        ..., description="User's email address", example="johndoe@gmail.com"
    )
    password: str = Field(..., description="User's password", example="password123")


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class User(BaseModel):
    id: int
    username: str
    email: str
    password_hash: str
