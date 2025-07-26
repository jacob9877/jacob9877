import traceback

import bcrypt
import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection
from pydantic import BaseModel, EmailStr, Field

from app.models.breast_cancer_patient_models import BreastCancerPatient
from app.models.common_models import ResponseModel
from app.models.conversation_models import ConversationSummary
from app.models.user_models import LoginRequest, RegisterRequest, UserResponse
from app.utils.db import get_db_connection, user_exists

router = APIRouter(prefix="/users", tags=["users"])


class PasswordResetRequest(BaseModel):
    email: str
    new_password: str
    token: str


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
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE email = %s",
            (login_request.email,),
        )
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
        if conn:
            conn.close()


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
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (user.username,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username is taken"
            )

        # Check if user exists with provided email
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (user.email,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email is taken"
            )

        # Hash password
        hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

        # Insert user into database
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            """,
            (
                user.username,
                user.email,
                hashed_pw,
            ),
        )
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
        if conn:
            conn.close()


@router.get(
    "/{user_id}/patients",
    summary="Get all patients for a user",
    description="Retrieves all breast cancer patients associated with a specific user, sorted by the most recently updated",
    response_model=ResponseModel[list[BreastCancerPatient]],
    response_description="Returns all patients for a user, sorted by most recently updated",
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
def get_user_patients(
    user_id: int = Path(description="ID of the user to fetch patients for", example=1),
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

        # Get all patients for the user, sorted by updated_at descending
        cursor.execute(
            """
            SELECT * FROM breast_cancer_patients 
            WHERE user_id = %s 
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )

        return ResponseModel[list[BreastCancerPatient]](
            data=cursor.fetchall(), detail="Patients retrieved successfully"
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
        if conn:
            conn.close()


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

        cursor.execute(
            """
            SELECT id, title
            FROM conversations
            WHERE user_id = %s
            ORDER BY id DESC
            """,
            (user_id,),
        )

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
        if conn:
            conn.close()


@router.post("/reset-password", response_description="Reset password for a user")
def reset_password(
    user: PasswordResetRequest, conn: MySQLConnection = Depends(get_db_connection)
):
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        user_data = cursor.fetchone()

        if not user_data:
            raise HTTPException(
                status_code=404, detail="Account with that email does not exist"
            )

        # user.token = secrets.token_urlsafe(16)
        hashed_pw = bcrypt.hashpw()(
            user.new_password.encode(), bcrypt.gensalt()
        ).decode()

        cursor.execute(
            """
            UPDATE users 
            SET password_hash = %s 
            WHERE email = %s
            """,
            (hashed_pw, user.email),
        )
        conn.commit()
        return {"message": "Password has been changed successfully"}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
