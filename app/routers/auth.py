import bcrypt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    Security,
    status,
)
from mysql.connector.cursor import MySQLCursorDict

from app.models.auth_models import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshResponse,
    TokenType,
)
from app.models.common_models import ResponseModel
from app.models.user_models import User
from app.utils.db import get_db_cursor, get_user_by_email, user_exists
from app.utils.dependencies import (
    all_registered_users,
    get_current_user,
    require_access,
)
from app.utils.jwt import (
    clear_refresh_cookie,
    create_jwt,
    decode_and_validate_jwt,
    get_refresh_token_from_cookie,
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
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    user = get_user_by_email(cursor, login_request.email)

    # Checks if the user exists
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Checks password
    if not bcrypt.checkpw(login_request.password.encode(), user.password_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password"
        )

    access_token = create_jwt(
        user_id=user.id,
        role=user.role,
        condition=user.condition,
        token_type=TokenType.ACCESS,
    )
    refresh_token = create_jwt(
        user_id=user.id,
        role=user.role,
        condition=user.condition,
        token_type=TokenType.REFRESH,
    )
    set_refresh_cookie(response, refresh_token)

    return ResponseModel[LoginResponse](
        data=LoginResponse(access_token=access_token),
        detail="Login successful",
    )


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
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    refresh_token = get_refresh_token_from_cookie(request)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    payload = decode_and_validate_jwt(
        refresh_token, expected_token_type=TokenType.REFRESH
    )
    user_id = payload.sub
    if not user_exists(cursor, user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    # Issue a new access token; keep the same refresh token
    access_token = create_jwt(
        user_id=user_id,
        role=payload.role,
        condition=payload.condition,
        token_type=TokenType.ACCESS,
    )
    set_refresh_cookie(response, refresh_token)
    return ResponseModel[RefreshResponse](
        data=RefreshResponse(access_token=access_token),
        detail="New access token generated successfully",
    )


@router.post(
    "/logout",
    summary="Log a user out",
    description="Log a user out by clearing their refresh cookie",
    response_description="Nothing",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(response: Response):
    clear_refresh_cookie(response)
    return


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
    dependencies=[Security(require_access(all_registered_users()))],
)
def me(
    current_user: User = Depends(get_current_user),
):
    return ResponseModel[MeResponse](
        data=MeResponse.model_validate(current_user, from_attributes=True),
        detail="Info retrieved successfully",
    )
