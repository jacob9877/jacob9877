import os

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor


def get_db_connection() -> MySQLConnection:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )
    try:
        yield conn
    finally:
        conn.close()


def user_exists(cursor: MySQLCursor, user_id: int) -> bool:
    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone() is not None


def conversation_exists(cursor: MySQLCursor, conversation_id: int) -> bool:
    cursor.execute("SELECT id FROM conversations WHERE id = %s", (conversation_id,))
    return cursor.fetchone() is not None


def breast_cancer_patient_exists(cursor: MySQLCursor, patient_id: int) -> bool:
    cursor.execute("SELECT id FROM breast-cancer-patients WHERE id = %s", (patient_id,))
    return cursor.fetchone() is not None
