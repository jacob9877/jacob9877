# tests/test_users_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

from app.app import app
from app.models.user_models import (
    LoginRequest,
    RegisterRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.models.common_models import ResponseModel

SECRET_KEY = "testsecret"
ALGORITHM = "HS256"

client = TestClient(app)


# ------------------------
# Fixtures & Mocks
# ------------------------
@pytest.fixture
def mock_conn():
    """Fixture for a fake DB connection + cursor"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


# ------------------------
# Login Tests
# ------------------------
@patch("app.routers.users.get_db_connection")
def test_login_success(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": bcrypt.hashpw(b"password", bcrypt.gensalt()).decode(),
    }
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/beta/users/login", json={"email": "test@test.com", "password": "password"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["username"] == "testuser"


@patch("app.routers.users.get_db_connection")
def test_login_user_not_found(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/login", json={"email": "missing@test.com", "password": "password"}
    )
    assert response.status_code == 404


@patch("app.routers.users.get_db_connection")
def test_login_incorrect_password(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.return_value = {
        "id": 1,
        "username": "testuser",
        "password_hash": bcrypt.hashpw(b"otherpassword", bcrypt.gensalt()).decode(),
    }
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/login", json={"email": "test@test.com", "password": "wrong"}
    )
    assert response.status_code == 400


# ------------------------
# Register Tests
# ------------------------
@patch("app.utils.db.get_db_connection")
def test_register_success(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.side_effect = [None, None]  # username and email both free
    cursor.lastrowid = 123
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/register",
        json={"username": "newuser", "email": "new@test.com", "password": "pass123"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["id"] == 123


@patch("app.routers.users.get_db_connection")
def test_register_username_taken(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.side_effect = [{"id": 1}, None]  # username taken
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/register",
        json={"username": "taken", "email": "new@test.com", "password": "pass123"},
    )
    assert response.status_code == 409
    assert "Username is taken" in response.text


@patch("app.routers.users.get_db_connection")
def test_register_email_taken(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.side_effect = [None, {"id": 1}]  # email taken
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/register",
        json={"username": "newuser", "email": "taken@test.com", "password": "pass123"},
    )
    assert response.status_code == 409
    assert "Email is taken" in response.text


# ------------------------
# Get Patients Tests
# ------------------------
# @patch("app.routers.users.user_exists", return_value=True)
# @patch("app.routers.users.get_db_connection")
# def test_get_user_patients_success(mock_db, mock_user_exists):
#     conn, cursor = MagicMock(), MagicMock()
#     cursor.fetchall.return_value = [
#         {"id": 1, "name": "Patient1", "user_id": 1, "updated_at": datetime.now()}
#     ]
#     conn.cursor.return_value = cursor
#     mock_db.return_value = conn

#     response = client.get("/users/1/patients")
#     assert response.status_code == 200
#     assert len(response.json()["data"]) == 1


# @patch("app.routers.users.user_exists", return_value=False)
# @patch("app.routers.users.get_db_connection")
# def test_get_user_patients_user_not_found(mock_db, mock_user_exists):
#     conn, cursor = MagicMock(), MagicMock()
#     conn.cursor.return_value = cursor
#     mock_db.return_value = conn

#     response = client.get("/users/99/patients")
#     assert response.status_code == 404


# ------------------------
# Get Conversations Tests
# ------------------------
# @patch("app.routers.users.user_exists", return_value=True)
# @patch("app.routers.users.get_db_connection")
# def test_get_user_conversations_success(mock_db, mock_user_exists):
#     conn, cursor = MagicMock(), MagicMock()
#     cursor.fetchall.return_value = [{"id": 1, "title": "Conversation 1"}]
#     conn.cursor.return_value = cursor
#     mock_db.return_value = conn

#     response = client.get("/users/1/conversations")
#     assert response.status_code == 200
#     assert response.json()["data"][0]["title"] == "Conversation 1"


# @patch("app.routers.users.user_exists", return_value=False)
# @patch("app.routers.users.get_db_connection")
# def test_get_user_conversations_user_not_found(mock_db, mock_user_exists):
#     conn, cursor = MagicMock(), MagicMock()
#     conn.cursor.return_value = cursor
#     mock_db.return_value = conn

#     response = client.get("/users/99/conversations")
#     assert response.status_code == 404


# ------------------------
# Request Password Reset Tests
# ------------------------
@patch("app.routers.users.send_reset_email", new_callable=MagicMock)
@patch("app.routers.users.get_db_connection")
def test_request_password_reset_success(mock_db, mock_send_email):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.return_value = {"id": 1}
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/request-password-reset", json={"email": "test@test.com"}
    )
    assert response.status_code == 200
    assert "Password reset link sent" in response.text
    mock_send_email.assert_called_once()


@patch("app.routers.users.get_db_connection")
def test_request_password_reset_user_not_found(mock_db):
    conn, cursor = MagicMock(), MagicMock()
    cursor.fetchone.return_value = None
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    response = client.post(
        "/users/request-password-reset", json={"email": "missing@test.com"}
    )
    assert response.status_code == 404


# ------------------------
# Reset Password Tests
# ------------------------
@patch("app.routers.users.get_db_connection")
def test_reset_password_success(mock_db):
    token = jwt.encode(
        {
            "sub": "1",
            "purpose": "password_reset",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    conn, cursor = MagicMock(), MagicMock()
    conn.cursor.return_value = cursor
    mock_db.return_value = conn

    with patch("app.routers.users.SECRET_KEY", SECRET_KEY), patch(
        "app.routers.users.ALGORITHM", ALGORITHM
    ):
        response = client.post(
            "/users/reset-password", json={"token": token, "new_password": "newpass"}
        )
    assert response.status_code == 200
    assert "Password reset successfully" in response.text


@patch("app.routers.users.get_db_connection")
def test_reset_password_expired_token(mock_db):
    token = jwt.encode(
        {
            "sub": "1",
            "purpose": "password_reset",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with patch("app.routers.users.SECRET_KEY", SECRET_KEY), patch(
        "app.routers.users.ALGORITHM", ALGORITHM
    ):
        response = client.post(
            "/users/reset-password", json={"token": token, "new_password": "newpass"}
        )
    assert response.status_code == 400
    assert "Token expired" in response.text


@patch("app.routers.users.get_db_connection")
def test_reset_password_invalid_token(mock_db):
    token = "invalid.token.string"

    with patch("app.routers.users.SECRET_KEY", SECRET_KEY), patch(
        "app.routers.users.ALGORITHM", ALGORITHM
    ):
        response = client.post(
            "/users/reset-password", json={"token": token, "new_password": "newpass"}
        )
    assert response.status_code == 400
    assert "Invalid token" in response.text
