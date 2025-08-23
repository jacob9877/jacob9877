import base64
import os
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection

from app.models.breast_cancer_patient_models import (
    BreastCancerPatient,
    PaginatedBreastCancerPatients,
)
from app.models.common_models import ResponseModel
from app.models.conversation_models import ConversationSummary
from app.models.mortality_patient_models import (
    MortalityPatient,
    PaginatedMortalityPatients,
)
from app.models.user_models import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
)
from app.utils.db import get_db_connection, user_exists
from app.utils.email_utils import send_reset_email

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("ALGORITHM")
router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/login",
    summary="Log a user in",
    description="Logs a user in by verifying their email and password. Returns user details if successful.",
    response_model=ResponseModel[UserResponse],
    response_description="Returns user details",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Provided password is incorrect",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "No user exists with provided email",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def login(
    login_request: LoginRequest, conn: MySQLConnection = Depends(get_db_connection)
):
    try:
        cursor = conn.cursor(dictionary=True)

        # Looks up user by email
        operation = """
            SELECT id, username, password_hash
            FROM users
            WHERE email = %s
        """
        params = (login_request.email,)
        cursor.execute(operation, params)
        user = cursor.fetchone()

        # Checks if the user exists
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Checks password
        if not bcrypt.checkpw(
            login_request.password.encode(), user["password_hash"].encode()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password"
            )

        return ResponseModel[UserResponse](
            data=UserResponse(
                id=user["id"],
                username=user["username"],
                email=login_request.email,
            ),
            detail="Login successful",
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        conn.rollback()  # Keep rollback here in case we decide to log login requests later
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


@router.post(
    "/register",
    summary="Register a new user",
    description="Creates a new user account with a unique email and username. Returns the created user's details upon success.",
    response_model=ResponseModel[UserResponse],
    response_description="Returns the newly created user's details",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ResponseModel[None],
            "description": "User with the provided email or username already exists",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def register(user: RegisterRequest, conn: MySQLConnection = Depends(get_db_connection)):
    try:
        cursor = conn.cursor(dictionary=True)

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

        user_id = cursor.lastrowid

        return ResponseModel[UserResponse](
            data=UserResponse(
                id=user_id,
                username=user.username,
                email=user.email,
            ),
            detail="User registered successfully",
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


def _encode_cursor(updated_at: datetime, row_id: int) -> str:
    # Use microsecond precision to avoid collisions; ensure ISO string is consistent
    payload = f"{updated_at.isoformat(timespec='microseconds')}|{row_id}"
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_cursor(cursor_str: str) -> tuple[datetime, int]:
    # Add missing '=' padding for base64 urlsafe
    padding = "=" * (-len(cursor_str) % 4)
    raw = base64.urlsafe_b64decode((cursor_str + padding).encode("utf-8")).decode(
        "utf-8"
    )
    ts_str, id_str = raw.split("|", 1)
    # fromisoformat handles "YYYY-MM-DDTHH:MM:SS[.ffffff]" (naive or aware)
    dt = datetime.fromisoformat(ts_str)
    return dt, int(id_str)


@router.get(
    "/{user_id}/breast-cancer-patients",
    summary="Get breast cancer patients for a user (cursor-based pagination)",
    description=(
        "Retrieves breast cancer patients for a user using cursor-based pagination, "
        "sorted by most recently updated."
    ),
    response_model=ResponseModel[PaginatedBreastCancerPatients],
    response_description="Returns a page of patients plus a next_cursor if more data exists",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Cursor is invalid",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User with the provided ID does not exist",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def get_user_breast_cancer_patients_paginated(
    user_id: int = Path(
        description="ID of the user to fetch breast cancer patients for", example=1
    ),
    # Optional cursor from previous response
    cursor_token: Optional[str] = Query(
        default=None,
        alias="cursor",
        description="Opaque cursor returned from the previous page (base64url)",
        example="MjAyNS0wOC0yM1QxNjoyMDozMC4xMjM0NTY|12345 (base64url-encoded)",
    ),
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
        description="Max number of patients to return (1–100)",
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        # Order is (updated_at DESC, id DESC).
        # For "next page", fetch rows strictly "after" the cursor in that order:
        # updated_at < cursor_ts OR (updated_at = cursor_ts AND id < cursor_id)
        operation = """
            SELECT *
            FROM breast_cancer_patients
            WHERE user_id = %s
        """

        params: list = [user_id]

        if cursor_token:
            try:
                last_timestamp, last_id = _decode_cursor(cursor_token)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
                )
            operation += """
                AND (
                    updated_at < %s
                    OR (updated_at = %s AND id < %s)
                )
            """
            params.extend([last_timestamp, last_timestamp, last_id])

        # Apply ORDER BY and LIMIT + 1 (to see if there's another page)
        operation += " ORDER BY updated_at DESC, id DESC LIMIT %s"
        params.append(limit + 1)

        cursor.execute(operation, tuple(params))
        rows = cursor.fetchall()

        # Build response items and next cursor (if we fetched limit+1)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]  # only return 'limit' items

        patients = [BreastCancerPatient(**row) for row in rows]

        next_cursor: Optional[str] = None
        if has_more and rows:
            last_row = rows[-1]
            last_updated_at: datetime = last_row["updated_at"]
            last_row_id: int = last_row["id"]
            next_cursor = _encode_cursor(last_updated_at, last_row_id)

        paginated_patients = PaginatedBreastCancerPatients(
            next_cursor=next_cursor,
            patients=patients,
        )
        return ResponseModel[PaginatedBreastCancerPatients](
            data=paginated_patients,
            detail="Patients retrieved successfully",
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


@router.get(
    "/{user_id}/mortality-patients",
    summary="Get mortality patients for a user (cursor-based pagination)",
    description=(
        "Retrieves mortality patients for a user using cursor-based pagination, "
        "sorted by most recently updated."
    ),
    response_model=ResponseModel[PaginatedMortalityPatients],
    response_description="Returns a page of patients plus a next_cursor if more data exists",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Cursor is invalid",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User with the provided ID does not exist",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def get_user_mortality_patients_paginated(
    user_id: int = Path(
        description="ID of the user to fetch mortality patients for", example=1
    ),
    # Optional cursor from previous response
    cursor_token: Optional[str] = Query(
        default=None,
        alias="cursor",
        description="Opaque cursor returned from the previous page (base64url)",
        example="MjAyNS0wOC0yM1QxNjoyMDozMC4xMjM0NTY|12345 (base64url-encoded)",
    ),
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
        description="Max number of patients to return (1–100)",
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        # Order is (updated_at DESC, id DESC).
        # For "next page", fetch rows strictly "after" the cursor in that order:
        # updated_at < cursor_ts OR (updated_at = cursor_ts AND id < cursor_id)
        operation = """
            SELECT *
            FROM mortality_patients
            WHERE user_id = %s
        """

        params: list = [user_id]

        if cursor_token:
            try:
                last_timestamp, last_id = _decode_cursor(cursor_token)
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
                )
            operation += """
                AND (
                    updated_at < %s
                    OR (updated_at = %s AND id < %s)
                )
            """
            params.extend([last_timestamp, last_timestamp, last_id])

        # Apply ORDER BY and LIMIT + 1 (to see if there's another page)
        operation += " ORDER BY updated_at DESC, id DESC LIMIT %s"
        params.append(limit + 1)

        cursor.execute(operation, tuple(params))
        rows = cursor.fetchall()

        # Build response items and next cursor (if we fetched limit+1)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]  # only return 'limit' items

        patients = [MortalityPatient(**row) for row in rows]

        next_cursor: Optional[str] = None
        if has_more and rows:
            last_row = rows[-1]
            last_updated_at: datetime = last_row["updated_at"]
            last_row_id: int = last_row["id"]
            next_cursor = _encode_cursor(last_updated_at, last_row_id)

        paginated_patients = PaginatedMortalityPatients(
            next_cursor=next_cursor,
            patients=patients,
        )
        return ResponseModel[PaginatedMortalityPatients](
            data=paginated_patients,
            detail="Patients retrieved successfully",
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


@router.get(
    "/{user_id}/conversations",
    summary="Get conversation summaries for a user",
    description="Retrieves all conversations for the given user, sorted by the most recently updated",
    response_model=ResponseModel[list[ConversationSummary]],
    response_description="Returns all conversations, sorted by most recently updated",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User with the provided ID does not exist",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def get_user_conversations(
    user_id: int = Path(
        description="ID of the user to fetch conversations for", example=1
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        # Check if user exists
        if not user_exists(cursor, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found",
            )

        operation = """
            SELECT id, title
            FROM conversations
            WHERE user_id = %s
            ORDER BY updated_at DESC, id DESC
        """
        params = (user_id,)
        cursor.execute(operation, params)

        rows = cursor.fetchall()
        conversations = [ConversationSummary(**row) for row in rows]
        return ResponseModel[list[ConversationSummary]](
            data=conversations, detail="Fetched conversations successfully"
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except mysql.connector.Error as db_error:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(db_error)).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


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
    response_model=ResponseModel[dict],
    response_description="Returns a confirmation message",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "User with the provided email does not exist",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
async def request_password_reset(
    data: PasswordResetRequest, conn: MySQLConnection = Depends(get_db_connection)
):
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
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
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        await send_reset_email(data.email, token)
        return ResponseModel[dict](
            data={"message": "Password reset link sent to your email"},
            detail="Password reset email sent",
        )
    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()


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
    response_model=ResponseModel[dict],
    response_description="Returns confirmation of password reset",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Invalid or expired token",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def reset_password(
    data: PasswordResetConfirm, conn: MySQLConnection = Depends(get_db_connection)
):
    cursor = None
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
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

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s", (hashed_pw, user_id)
        )
        conn.commit()

        return ResponseModel[dict](
            data={"message": "Password reset successfully"},
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
    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )

    finally:
        if cursor:
            cursor.close()
