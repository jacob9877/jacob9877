import traceback

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from mysql.connector import MySQLConnection

from app.models.auth_models import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshResponse,
    TokenType,
)
from app.models.common_models import ResponseModel
from app.models.user_models import Condition
from app.utils.db import get_db_connection, get_user_by_id, user_exists
from app.utils.jwt import (
    clear_refresh_cookie,
    clinicians_or_patients_with,
    create_jwt,
    decode_and_validate_jwt,
    get_refresh_token_from_cookie,
    require_access,
    set_refresh_cookie,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    summary="Log a user in",
    description="Logs a user in by verifying their email and password. Returns an access token and sets a refresh token cookie upon success.",
    response_model=ResponseModel[LoginResponse],
    response_description="Returns an access token",
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
    },
)
def login(
    login_request: LoginRequest,
    response: Response,
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

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

        access_token = create_jwt(user_id=user["id"], token_type=TokenType.ACCESS)
        refresh_token = create_jwt(user_id=user["id"], token_type=TokenType.REFRESH)
        set_refresh_cookie(response, refresh_token)

        return ResponseModel[LoginResponse](
            data=LoginResponse(access_token=access_token),
            detail="Login successful",
        )

    except Exception as e:
        conn.rollback()  # Keep rollback here in case we decide to log login requests later
        traceback.print_exc()
        raise e


@router.get(
    "/refresh",
    summary="Refresh an access token",
    description="Given a refresh token returns a new access token",
    response_model=ResponseModel[RefreshResponse],
    response_description="Returns a new access token",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Provided refresh token is invalid",
        },
    },
)
def refresh(
    request: Request,
    response: Response,
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        refresh_token = get_refresh_token_from_cookie(request)
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
            )

        payload = decode_and_validate_jwt(
            refresh_token, expected_token_type=TokenType.REFRESH
        )
        user_id = payload.sub
        with conn.cursor(dictionary=True) as cursor:
            if not user_exists(cursor, user_id):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
                )

        # Issue a new access token; keep the same refresh token
        access_token = create_jwt(
            user_id=user_id,
            token_type=TokenType.ACCESS,
        )
        set_refresh_cookie(response, refresh_token)
        return ResponseModel[RefreshResponse](
            data=RefreshResponse(access_token=access_token),
            detail="New access token generated successfully",
        )

    except Exception as e:
        conn.rollback()  # Keep rollback here in case we decide to log login requests later
        traceback.print_exc()
        raise e


@router.post(
    "/logout",
    summary="Log a user out",
    description="Log a user out by clearing their refresh cookie",
    response_model=ResponseModel[None],
    response_description="Nothing much to see here",
    status_code=status.HTTP_200_OK,
)
def logout(response: Response):
    clear_refresh_cookie(response)
    return ResponseModel[None](detail="Logout successful")


@router.get(
    "/me",
    summary="Get current user info",
    description="Get info about the current user using their access token",
    response_model=ResponseModel[MeResponse],
    response_description="Returns some information about the current user",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)
def me(
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(
        require_access(
            clinicians_or_patients_with(
                {Condition.BREAST_CANCER, Condition.PEDIATRIC_APPENDICITIS}
            )
        )
    ),
):

    with conn.cursor(dictionary=True) as cursor:
        current_user = get_user_by_id(cursor, current_user_id)
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
    return ResponseModel[MeResponse](
        data=MeResponse(
            username=current_user.username,
            email=current_user.email,
            role=current_user.role,
            condition=current_user.condition,
        ),
        detail="Info retrieved successfully",
    )
