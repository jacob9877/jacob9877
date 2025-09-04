import os
import traceback
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection

from app.models.common_models import ResponseModel
from app.models.user_models import (
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
)
from app.utils.db import get_db_connection
from app.utils.email_utils import send_reset_email

SECRET_KEY = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ["JWT_ALGORITHM"]

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/register",
    summary="Register a new user",
    description="Creates a new user account with a unique email and username. Returns nothing upon success. Must log in separately to get an access token.",
    response_model=ResponseModel[None],
    response_description="Returns nothing on success",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "User with the provided email or username already exists",
        },
    },
)
def register(user: RegisterRequest, conn: MySQLConnection = Depends(get_db_connection)):
    try:
        with conn.cursor(dictionary=True) as cursor:

            # Check if user exists with provided username
            operation = """
                SELECT id
                FROM users
                WHERE username = %s
            """
            params = (user.username,)
            cursor.execute(operation, params)
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Username is taken"
                )

            # Check if user exists with provided email
            operation = """
                SELECT id
                FROM users
                WHERE email = %s
            """
            params = (user.email,)
            cursor.execute(operation, params)
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email is taken"
                )

            # Hash password
            hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

            # Insert user into database
            operation = """
                INSERT INTO users (username, email, password_hash)
                VALUES (%s, %s, %s)
            """
            params = (
                user.username,
                user.email,
                hashed_pw,
            )
            cursor.execute(operation, params)

        conn.commit()

        return ResponseModel[None](
            detail="User registered successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.post(
    "/request-password-reset",
    summary="Request a password reset",
    description="""
    **Frontend Responsibilities:**
    - Provide a UI form where the user can enter their email.
    - On submit, call this endpoint with `{ "email": "<user_email>" }`.
    - Show a success notification like: "If this email exists, you’ll receive a password reset link".
    - Do not reveal whether an account exists or not.
    - No token handling needed here; the reset link will be emailed.

    **Backend Behavior:**
    - Verifies the email exists in DB.
    - Generates a reset token (valid 15 mins).
    - Sends reset link to user's email.
    """,
    response_model=ResponseModel[None],
    response_description="Returns a confirmation message as detail; not significant",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User with the provided email does not exist",
        },
    },
)
async def request_password_reset(
    data: PasswordResetRequest, conn: MySQLConnection = Depends(get_db_connection)
):
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (data.email,))
            user = cursor.fetchone()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
                )

        payload = {
            "sub": str(user["id"]),
            "purpose": "password_reset",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)

        await send_reset_email(data.email, token)
        return ResponseModel[None](
            detail="Password reset email sent",
        )
    except Exception as e:
        traceback.print_exc()
        raise e


@router.post(
    "/reset-password",
    summary="Reset password using token",
    description="""
    **Frontend Responsibilities:**
    - Build a page `/reset-password` that extracts the `token` from the query string (e.g., `/reset-password?token=XYZ`).
    - Provide a form where the user enters their **new password** and **confirm password**.
    - When submitting, call this endpoint with:
      ```json
      {
        "token": "<token_from_url>",
        "new_password": "<user_new_password>"
      }
      ```
    - On success, redirect the user to the login page with a success notification.
    - On failure (expired/invalid token), show an error and prompt user to re-request a reset.

    **Backend Behavior:**
    - Validates token (checks expiration + purpose).
    - Updates the user’s password in DB (hashed).
    - Returns confirmation on success.
    """,
    response_model=ResponseModel[None],
    response_description="Return is not meaningful; status code indicates success of password reset",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Invalid or expired token",
        },
    },
)
def reset_password(
    data: PasswordResetConfirm, conn: MySQLConnection = Depends(get_db_connection)
):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("purpose") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token purpose"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token"
            )

        hashed_pw = bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt()).decode()

        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hashed_pw, user_id),
            )
        conn.commit()

        return ResponseModel[None](
            detail="Password has been reset successfully",
        )
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseModel[None](detail="Token expired").model_dump(),
        )
    except jwt.InvalidTokenError as e:
        print("JWT decode error:", str(e))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseModel[None](detail=f"Invalid token: {str(e)}").model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        raise e
