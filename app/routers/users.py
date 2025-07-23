import os
import traceback

import bcrypt
import secrets
import smtplib
import mysql.connector
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from pydantic import BaseModel

from app.utils.db import get_db_connection, user_exists

router = APIRouter(prefix="/users", tags=["users"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class PasswordResetRequest(BaseModel):
    email: str
    new_password: str
    token: str

@router.post("/login")
def login(user: LoginRequest, conn: MySQLConnection = Depends(get_db_connection)):
    try:
        cursor = conn.cursor(dictionary=True)

        # Looks up user by email
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE email = %s",
            (user.email,),
        )
        user_data = cursor.fetchone()

        # Checks if the user exists
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Checks password
        if not bcrypt.checkpw(
            user.password.encode(), user_data["password_hash"].encode()
        ):
            raise HTTPException(status_code=401, detail="Incorrect password")

        return {
            "message": "Login successful",
            "user": {
                "id": user_data["id"],
                "username": user_data["username"],
                "email": user.email,
            },
        }

    except mysql.connector.Error as db_error:
        raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.post("/register")
def register(user: RegisterRequest, conn: MySQLConnection = Depends(get_db_connection)):
    try:
        cursor = conn.cursor()

        # Checks if email or username already exists
        cursor.execute(
            "SELECT id FROM users WHERE email = %s OR username = %s",
            (user.email, user.username),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="User with that email or username already exists",
            )

        # Hashed the password
        hashed_pw = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()

        # Inserts user into the database
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (%s, %s, %s)
            """,
            (user.username, user.email, hashed_pw),
        )
        conn.commit()
        return {"message": "User registered successfully"}

    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.get(
    "/{user_id}/patients",
    response_description="Get all patients for a user, sorted by most recently updated",
)
def get_user_patients(user_id: int, conn: MySQLConnection = Depends(get_db_connection)):
    try:
        cursor = conn.cursor(dictionary=True)

        # Check if user exists
        if not user_exists(cursor, user_id):
            raise HTTPException(
                status_code=404,
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

        return cursor.fetchall()

    except HTTPException as e:
        raise e
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@router.post("/reset-password", response_description="Reset password for a user")
def reset_password(
    user: PasswordResetRequest, conn: MySQLConnection = Depends(get_db_connection)
):  
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        user_data = cursor.fetchone()

        if not user_data:
            raise HTTPException(status_code=404, detail="Account with that email does not exist")
        
        # user.token = secrets.token_urlsafe(16)
        hashed_pw = bcrypt.hashpw()(user.new_password.encode(), bcrypt.gensalt()).decode()

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
        
