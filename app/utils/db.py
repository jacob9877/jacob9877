import os
import traceback
from contextlib import contextmanager
from typing import Generator, Literal

from fastapi import HTTPException, status
from mysql.connector import pooling
from mysql.connector.cursor import MySQLCursorDict

from app.models.breast_cancer_patient_models import (
    GetPatientResponse as GetBreastCancerPatientResponse,
)
from app.models.clinical_notes_models import ClinicalNote
from app.models.conversation_models import Conversation
from app.models.pediatric_appendicitis_patient_models import (
    GetPatientResponse as GetPediatricAppendicitisPatientResponse,
)
from app.models.user_models import Condition, Role, RoleAndCondition, User
from app.utils.email_utils import send_registration_email

DB_HOST = os.environ["DB_HOST"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = int(os.environ["DB_PORT"])
DB_NAME = os.environ["DB_NAME"]

POOL_NAME = os.getenv("DB_POOL_NAME", "main_pool")
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "3"))
POOL_RESET = os.getenv("DB_POOL_RESET_SESSION", "True").lower() == "true"

# Singleton, process-wide connection pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name=POOL_NAME,
    pool_size=POOL_SIZE,
    pool_reset_session=POOL_RESET,  # resets session state when the connection is returned
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    port=DB_PORT,
    database=DB_NAME,
    autocommit=False,  # we control transactions explicitly
)


def get_db_cursor() -> Generator[MySQLCursorDict, None, None]:
    """
    FastAPI dependency that yields a dict cursor from a pooled connection.
    - Commits the transaction if the endpoint completes successfully.
    - On exception: rolls back, prints traceback, and re-raises.
    - Always closes cursor and returns the connection to the pool.
    """
    conn = None
    cursor: MySQLCursorDict | None = None
    try:
        conn = connection_pool.get_connection()

        conn.autocommit = False

        cursor = conn.cursor(dictionary=True)

        yield cursor

        # Endpoint finished successfully - commit
        conn.commit()

    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        traceback.print_exc()
        raise

    finally:
        # Clean up in reverse order
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()  # returns to pool
            except Exception:
                pass


@contextmanager
def get_db_cursor_cm() -> Generator[MySQLCursorDict, None, None]:
    conn = connection_pool.get_connection()
    conn.autocommit = False
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        traceback.print_exc()
        raise
    finally:
        cursor.close()
        conn.close()


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


def get_user_by_email(cursor: MySQLCursorDict, email: str) -> User | None:
    operation = """
        SELECT *
        FROM users
        WHERE email = %s
    """
    params = (email,)
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
) -> GetBreastCancerPatientResponse | None:
    operation = """
        SELECT
        p.*,
        CASE
            WHEN p.user_id IS NULL THEN NULL
            ELSE CAST(JSON_OBJECT(
            'first_name', u.first_name,
            'last_name', u.last_name,
            'email',    u.email
            ) AS JSON)
        END AS patient_user_info
        FROM breast_cancer_patients AS p
        LEFT JOIN users AS u
        ON u.id = p.user_id
        WHERE p.id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return GetBreastCancerPatientResponse(**row)


def get_pediatric_appendicitis_patient_by_id(
    cursor: MySQLCursorDict, patient_id: int
) -> GetPediatricAppendicitisPatientResponse | None:
    operation = """
        SELECT
        p.*,
        CASE
            WHEN p.user_id IS NULL THEN NULL
            ELSE CAST(JSON_OBJECT(
            'first_name', u.first_name,
            'last_name', u.last_name,
            'email',    u.email
            ) AS JSON)
        END AS patient_user_info
        FROM pediatric_appendicitis_patients AS p
        LEFT JOIN users AS u
        ON u.id = p.user_id
        WHERE p.id = %s
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return GetPediatricAppendicitisPatientResponse(**row)


def get_breast_cancer_clinical_note_by_id(
    cursor: MySQLCursorDict, note_id: int
) -> ClinicalNote | None:
    operation = """
        SELECT *
        FROM breast_cancer_clinical_notes
        WHERE id = %s
    """
    params = (note_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return ClinicalNote(**row)


def get_pediatric_appendicitis_clinical_note_by_id(
    cursor: MySQLCursorDict, note_id: int
) -> ClinicalNote | None:
    operation = """
        SELECT *
        FROM pediatric_appendicitis_clinical_notes
        WHERE id = %s
    """
    params = (note_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row is None:
        return None
    return ClinicalNote(**row)


async def insert_pending_email(
    cursor: MySQLCursorDict,
    email: str,
    target_patient_id: int,
    target_patient_table: Literal[
        "breast_cancer_patients", "pediatric_appendicitis_patients"
    ],
    clinician_first_name: str,
    clinician_last_name: str,
):
    """
    Core functionality for logic surrounding linking of patient user accounts to patient records.

    Either sets `email` as pending_email in the record in `target_patient_table` with id `target_patient_id`
        OR if a *valid* user account exists with `email` then sets the user account id as user_id in the record in `target_patient_table` with id `target_patient_id`

    Args:
        cursor (MySQLCursorDict):
        email (str): email to either set as pending in the patient record or it's the email of the patient user account to link to the target patient record.
        target_patient_id (int): id of the patient record in the desired patient table.
        target_patient_table (Literal["breast_cancer_patients", "pediatric_appendicitis_patients"]): name of patient table that target_patient_id is the PK for (i.e. table to insert pending_email into).

    Raises:
        HTTPException: with status code 409 conflict if there is a data conflict given the arguments
    """

    # Search for if the patient record already has a patient user associated with it
    operation = f"""
        SELECT user_id
        FROM {target_patient_table}
        WHERE id = %s
    """
    params = (target_patient_id,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    if row and row["user_id"]:
        # Policy: don't disrupt or override the currently linked patient user account
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient record already has a user account tied to it",
        )

    if target_patient_table == "breast_cancer_patients":
        condition = Condition.BREAST_CANCER
    elif target_patient_table == "pediatric_appendicitis_patients":
        condition = Condition.PEDIATRIC_APPENDICITIS
    else:
        raise ValueError("Invalid target_patient_table")

    # Search for if a patient user account exists with this email,
    #   is of the right discipline, and is not already linked to a doctor
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
    params = (condition.value, email)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    # If there is a user account that satisfies this
    if row is not None:
        # Link right away
        operation = f"""
            UPDATE {target_patient_table}
            SET user_id = %s, pending_email = NULL, name = NULL
            WHERE id = %s
        """
        params = (row["id"], target_patient_id)
        cursor.execute(operation, params)
        return

    # Check if email is pending in either patients table
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

    # If the email is pending in a patient record different than the target one, error
    if (
        bc_row
        and target_patient_table == "breast_cancer_patients"
        and bc_row["id"] != target_patient_id
    ) or (
        pa_row
        and target_patient_table == "pediatric_appendicitis_patients"
        and pa_row["id"] != target_patient_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already pending in another patient",
        )
    # Otherwise the email is pending in the same patient record and this is a re-insert - keep going

    # Check if a user account exists with this email:
    #   - Check for a user with the email
    #   - If a user account comes back, if its condition is:
    #       - breast cancer -> search for a breast cancer patient record linked to this user account
    #       - pediatric appendicitis -> search for a pediatric appendicitis patient record linked to this user account
    operation = f"""
        SELECT
            u.id            AS user_id,
            u.email,
            u.`condition`,
            CASE
                WHEN u.`condition` = '{Condition.BREAST_CANCER.value}'           THEN bcp.id
                WHEN u.`condition` = '{Condition.PEDIATRIC_APPENDICITIS.value}'  THEN pap.id
                ELSE NULL
            END            AS patient_id
        FROM users u
        LEFT JOIN breast_cancer_patients bcp
          ON bcp.user_id = u.id
         AND u.`condition` = '{Condition.BREAST_CANCER.value}'
        LEFT JOIN pediatric_appendicitis_patients pap
          ON pap.user_id = u.id
         AND u.`condition` = '{Condition.PEDIATRIC_APPENDICITIS.value}'
        WHERE u.email = %s;
    """
    params = (email,)
    cursor.execute(operation, params)
    row = cursor.fetchone()
    # If a user already exists with this email
    if row is not None:
        # If the pre-existing user account has a different condition or is a clinician (has no condition)
        if (
            target_patient_table == "breast_cancer_patients"
            and row["condition"] != Condition.BREAST_CANCER.value
        ) or (
            target_patient_table == "pediatric_appendicitis_patients"
            and row["condition"] != Condition.PEDIATRIC_APPENDICITIS.value
        ):
            # Policy: we won't force-link across conditions
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already taken by a user with a different condition",
            )

        # Otherwise, the existing user account has the same discipline.
        # If the existing user account is already linked to a different patient record
        if row["patient_id"] != target_patient_id:
            # There's nothing we can do
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already exists with this email and is already linked to a different patient record",
            )
        # Otherwise, it's the same patient record
        else:
            # So the email is already linked
            print("returning")
            return

    # Now we should be good to go
    operation = f"""
        UPDATE {target_patient_table}
        SET pending_email = %s
        WHERE id = %s
    """
    params = (email, target_patient_id)
    cursor.execute(operation, params)

    await send_registration_email(
        email,
        clinician_first_name,
        clinician_last_name,
        RoleAndCondition(role=Role.PATIENT, condition=condition),
    )
