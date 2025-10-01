import os
from typing import Any, Generator

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import BreastCancerPatient
from app.models.conversation_models import Conversation
from app.models.mortality_patient_models import MortalityPatient
from app.models.pediatric_appendicitis_models import PediatricAppendicitisPatient
from app.models.user_models import User


def get_db_connection() -> Generator[MySQLConnection, Any, Any]:
    conn = mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    )
    try:
        yield conn
    finally:
        conn.close()


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
