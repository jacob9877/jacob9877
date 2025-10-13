import os
from contextlib import contextmanager
from typing import Any, Generator, Literal

import mysql.connector
from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import BreastCancerPatient
from app.models.conversation_models import Conversation
from app.models.pediatric_appendicitis_models import PediatricAppendicitisPatient
from app.models.user_models import Condition, User

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


def insert_pending_email(
    cursor: MySQLCursorDict,
    email: str,
    target_patient_id: int,
    target_patient_table: Literal[
        "breast_cancer_patients", "pediatric_appendicitis_patients"
    ],
):

    # First check if we can do the linking right away
    # If the patient is of the right discipline and not associated with a doctor
    if target_patient_table == "breast_cancer_patients":
        condition = Condition.BREAST_CANCER
    else:
        condition = Condition.PEDIATRIC_APPENDICITIS

    operation = f"""
        SELECT u.id
        FROM users AS u
        WHERE u.condition = %s AND u.email = %s
        AND NOT EXISTS (
            SELECT 1
            FROM {target_patient_table} AS p
            WHERE p.user_id = u.id
        );
    """
    params = (condition, email)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        # Link here
        operation = f"""
            UPDATE {target_patient_table}
            SET user_id = %s, pending_email = NULL
            WHERE id = %s
        """
        params = (row["id"], target_patient_id)
        cursor.execute(operation, params)
        return

    # Cases:
    # The email is pending in a patients table -> invalid
    # There is a user account of a different discipline with that email -> invalid
    # There is a user of the correct discipline with that email but they are already linked to a doctor -> invalid
    # There is a user of the correct discipline with that email and they are not linked to a doctor -> valid
    # The email is not pending and there is no user account associated with it -> valid

    operation = """
        SELECT id
        FROM breast_cancer_patients
        WHERE pending_email = %s
    """
    params = (email,)
    cursor.execute(operation, params)
    bc_row = cursor.fetchone()

    operation = """
        SELECT id
        FROM pediatric_appendicitis_patients
        WHERE pending_email = %s
    """
    params = (email,)
    cursor.execute(operation, params)
    pa_row = cursor.fetchone()

    if bc_row or pa_row:
        # This is a re-insert of the patient email: don't throw an error
        if (
            target_patient_table == "breast_cancer_patients"
            and bc_row["id"] == target_patient_id
        ):
            pass
        elif (
            target_patient_table == "pediatric_appendicitis_patients"
            and pa_row["id"] == target_patient_id
        ):
            pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already pending in another patient",
        )

    operation = """
        SELECT id, condition
        FROM users
        WHERE email = %s
    """
    params = (email,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    # If a user already exists with this email
    if row is not None:
        # There is a user account of a different discipline with that email
        if (
            target_patient_table == "breast_cancer_patients"
            and row["condition"] != Condition.BREAST_CANCER
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already taken by a user with a different condition",
            )
        elif (
            target_patient_table == "pediatric_appendicitis_patients"
            and row["condition"] != Condition.PEDIATRIC_APPENDICITIS
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already taken by a user with a different condition",
            )

        # Otherwise, the existing user account has the same discipline.
        # Are they already linked to a patient record?
        if row["condition"] == Condition.BREAST_CANCER:
            operation == """
                SELECT id
                FROM breast_cancer_patients
                WHERE user_id = %s
            """
            params = (row["user_id"],)
            cursor.execute(operation, params)
            row = cursor.fetchone()
            if row is not None and row["id"] != target_patient_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already exists with this email and is already linked to a different patient record",
                )

        elif row["condition"] == Condition.PEDIATRIC_APPENDICITIS:
            operation == """
                SELECT id
                FROM pediatric_appendicitis_patients
                WHERE user_id = %s
            """
            params = (row["user_id"],)
            cursor.execute(operation, params)
            row = cursor.fetchone()
            if row is not None and row["id"] != target_patient_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already exists with this email and is already linked to a different patient record",
                )

    # Now we should be good to go
    operation = f"""
        UPDATE {target_patient_table}
        SET pending_email = %s
        WHERE id = %s
    """
    params = (email, target_patient_id)
    cursor.execute(operation, params)
