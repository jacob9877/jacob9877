import os
from typing import Any, Generator

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor


def get_db_connection() -> Generator[MySQLConnection, Any, Any]:
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
    operation = """
        SELECT id
        FROM users
        WHERE id = %s
    """
    params = (user_id,)
    cursor.execute(operation, params)

    return cursor.fetchone() is not None


def conversation_exists(cursor: MySQLCursor, conversation_id: int) -> bool:
    operation = """
        SELECT id
        FROM conversations
        WHERE id = %s
    """
    params = (conversation_id,)
    cursor.execute(operation, params)

    return cursor.fetchone() is not None
