import os
from contextlib import contextmanager
from typing import Any, Generator

import mysql.connector
from dotenv import find_dotenv, load_dotenv
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import BreastCancerPatient
from app.models.conversation_models import Conversation
from app.models.mortality_patient_models import MortalityPatient
from app.models.pediatric_appendicitis_models import PediatricAppendicitisPatient
from app.models.user_models import User

load_dotenv(find_dotenv())

DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]


@contextmanager
def db_connection_cm():
    """
    Context manager for database connection.

    Usage: `with db_connection_cm() as conn:`
    """
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        database=DB_NAME,
    )
    try:
        yield conn
    finally:
        conn.close()


def get_db_connection() -> Generator[MySQLConnection, None, None]:
    """
    DB connection generator for use with FastAPI dependency injection.

    Usage: `conn = Depends(get_db_connection)`"""
    with db_connection_cm() as conn:
        yield conn


def get_db_connection_string() -> str:
    return f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_user_by_id(cursor: MySQLCursorDict, user_id: int) -> User | None:
    operation = """
        SELECT *
        FROM users
        WHERE id = %s
    """
    params = (user_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return User(**row)


def user_exists(cursor: MySQLCursorDict, user_id: int) -> bool:
    return get_user_by_id(cursor, user_id) is not None


def get_conversation_by_id(
    cursor: MySQLCursorDict, conversation_id: int
) -> Conversation | None:
    operation = """
        SELECT *
        FROM conversations
        WHERE id = %s
    """
    params = (conversation_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return Conversation(**row)


def conversation_exists(cursor: MySQLCursorDict, conversation_id: int) -> bool:
    return get_conversation_by_id(cursor, conversation_id) is not None


def get_breast_cancer_patient_by_id(
    cursor: MySQLCursorDict, patient_id: int
) -> BreastCancerPatient | None:
    operation = """
        SELECT *
        FROM breast_cancer_patients
        WHERE id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return BreastCancerPatient(**row)


def get_mortality_patient_by_id(
    cursor: MySQLCursorDict, patient_id: int
) -> MortalityPatient | None:
    operation = """
        SELECT *
        FROM mortality_patients
        WHERE id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return MortalityPatient(**row)


def get_pediatric_appendicitis_patient_by_id(
    cursor: MySQLCursorDict, patient_id: int
) -> PediatricAppendicitisPatient | None:
    operation = """
        SELECT *
        FROM pediatric_appendicitis_patients
        WHERE id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return PediatricAppendicitisPatient(**row)
