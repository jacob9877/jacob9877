import os
import traceback
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from mysql.connector.cursor import MySQLCursorDict

from app.models.common_models import ResponseModel
from app.models.user_models import (
    Condition,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    Role,
)
from app.utils.db import get_db_cursor
from app.utils.email_utils import send_reset_email

SECRET_KEY = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ["JWT_ALGORITHM"]

router = APIRouter(prefix="/users", tags=["Users"])


def register_clinician(
    cursor: MySQLCursorDict, register_request: RegisterRequest
) -> int:
    # Hash password
    hashed_pw = bcrypt.hashpw(
        register_request.password.encode(), bcrypt.gensalt()
    ).decode()

    # Insert user into database
    operation = """
        INSERT INTO users (first_name, last_name, email, password_hash, role, `condition`)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (
        register_request.first_name,
        register_request.last_name,
        register_request.email,
        hashed_pw,
        Role.CLINICIAN.value,
        None,
    )
    cursor.execute(operation, params)
    return cursor.lastrowid


def register_patient(cursor: MySQLCursorDict, register_request: RegisterRequest):
    # Hash password
    hashed_pw = bcrypt.hashpw(
        register_request.password.encode(), bcrypt.gensalt()
    ).decode()

    # RULE (subject to change): force the link with a doctor if their email is pending
    operation = """
        SELECT id
        FROM breast_cancer_patients
        WHERE pending_email = %s
    """
    params = (register_request.email,)
    cursor.execute(operation, params)
    bc_row = cursor.fetchone()

    operation = """
        SELECT id 
        FROM pediatric_appendicitis_patients
        WHERE pending_email = %s
    """
    params = (register_request.email,)
    cursor.execute(operation, params)
    pa_row = cursor.fetchone()

    patient_id = None
    new_condition = register_request.condition
    if not bc_row and not pa_row:
        pass
        # Register them as independent of a doctor and with the requested discipline
    elif bc_row and register_request.condition == Condition.BREAST_CANCER:
        # Register them as breast cancer linked
        patient_id = bc_row["id"]

    elif pa_row and register_request.condition == Condition.PEDIATRIC_APPENDICITIS:
        # Register them as pediatric appendicitis linked
        patient_id = pa_row["id"]
    # Register them as the condition where their email is pending and linked to that patient record, ignore requested discipline
    else:
        if bc_row:
            patient_id = bc_row["id"]
            new_condition = Condition.BREAST_CANCER
        else:
            patient_id = pa_row["id"]
            new_condition = Condition.PEDIATRIC_APPENDICITIS

    # Insert user into database
    operation = """
        INSERT INTO users (first_name, last_name, email, password_hash, role, `condition`)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (
        register_request.first_name,
        register_request.last_name,
        register_request.email,
        hashed_pw,
        Role.PATIENT.value,
        new_condition.value,
    )
    cursor.execute(operation, params)
    new_user_id = cursor.lastrowid

    if patient_id:
        if new_condition == Condition.BREAST_CANCER:
            table = "breast_cancer_patients"
        else:
            table = "pediatric_appendicitis_patients"

        operation = f"""
            UPDATE {table}
            SET pending_email = NULL, user_id = %s, name = NULL
            WHERE id = %s
        """
        params = (new_user_id, patient_id)
        cursor.execute(operation, params)

    return new_user_id


@router.post(
    "/register",
    summary="Register a new user",
    description="Creates a new user account with a unique email. Returns nothing upon success. Must log in separately to get an access token.",
    response_model=ResponseModel[None],
    response_description="Returns nothing on success",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "User with the provided email already exists",
        },
    },
)
def register(
    register_request: RegisterRequest = Body(...),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    # Check if user exists with provided email
    operation = """
        SELECT id
        FROM users
        WHERE email = %s
    """
    params = (register_request.email,)
    cursor.execute(operation, params)
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is taken"
        )

    if register_request.role == Role.CLINICIAN:
        register_clinician(cursor, register_request)

    else:
        register_patient(cursor, register_request)

    return ResponseModel[None](
        detail="User registered successfully",
    )


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
    data: PasswordResetRequest = Body(...),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
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
    data: PasswordResetConfirm = Body(...),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
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

        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (hashed_pw, user_id),
        )

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
