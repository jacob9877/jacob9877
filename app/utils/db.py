import os

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor


def get_db_connection() -> MySQLConnection:
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
    )


def user_exists(cursor: MySQLCursor, user_id: int) -> bool:
    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone() is not None
