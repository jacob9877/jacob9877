import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.auth_models import TokenPayload, TokenType
from app.models.user_models import Condition, Role

JWT_ALGORITHM = os.environ["JWT_ALGORITHM"]
JWT_SECRET = os.environ["JWT_SECRET"]
ACCESS_TOKEN_TTL_SECONDS = int(os.environ["ACCESS_TOKEN_TTL_SECONDS"])
REFRESH_TOKEN_TTL_SECONDS = int(os.environ["REFRESH_TOKEN_TTL_SECONDS"])
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def create_jwt(
    user_id: int, role: Role, condition: Condition | None, token_type: TokenType
) -> str:
    if token_type == TokenType.ACCESS:
        ttl_seconds = ACCESS_TOKEN_TTL_SECONDS
    elif token_type == TokenType.REFRESH:
        ttl_seconds = REFRESH_TOKEN_TTL_SECONDS
    else:
        raise ValueError(f"Invalid token type: {token_type}")

    now = datetime.now(timezone.utc)
    payload = TokenPayload(
        sub=str(user_id),
        type=token_type,
        iat=int(now.timestamp()),
        exp=int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        role=role,
        condition=condition,
    ).model_dump(mode="json")
    return jwt.encode(payload=payload, key=JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_and_validate_jwt(token: str, expected_token_type: TokenType) -> TokenPayload:
    try:
        decoded = jwt.decode(
            jwt=token,
            key=JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp", "role"]},
            leeway=30,  # seconds
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is expired"
        ) from e
    except jwt.InvalidSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature"
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}"
        ) from e

    payload = TokenPayload(**decoded)
    if expected_token_type and payload.type != expected_token_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )
    return payload


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    expires = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=True,  # Important so that client cannot access this
        samesite="none",
        max_age=REFRESH_TOKEN_TTL_SECONDS,
        expires=expires,
        path="/",
    )


def get_refresh_token_from_cookie(request: Request) -> str | None:
    return request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )


security = HTTPBearer(
    auto_error=False
)  # Override to prevent automatic 403 response which isn't really semantically correct


def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = credentials.credentials
    return decode_and_validate_jwt(token, expected_token_type=TokenType.ACCESS)
