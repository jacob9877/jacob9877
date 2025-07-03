import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import mysql.connector
import bcrypt

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(user: LoginRequest):
    try:
        # Connects to the database using environment variables
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME"),
        )
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

        return{
            "message": "Login successful",
            "user": {
                "id": user_data["id"],
                "username": user_data["username"],
                "email": user.email
            }
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
