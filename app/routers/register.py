import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import mysql.connector  # Corrected import
import bcrypt
import traceback

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


@router.post("/register")
def register(user: RegisterRequest):
    try:
        # Connects to the database
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME"),
        )
        cursor = conn.cursor()

        # Checks if email or username already exists
        cursor.execute("SELECT id FROM users WHERE email = %s OR username = %s",(user.email, user.username))
        if cursor.fetchone():
            raise HTTPException(status_code=400,detail="User with that email or username already exists")

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
