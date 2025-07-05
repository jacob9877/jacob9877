import os
import traceback

import bcrypt
import mysql.connector
from fastapi import APIRouter, Depends, HTTPException
from mysql.connector import MySQLConnection
from pydantic import BaseModel

from app.utils.db import get_db_connection

router = APIRouter(prefix="/users", tags=["users"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


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

        # Hashes the password
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
