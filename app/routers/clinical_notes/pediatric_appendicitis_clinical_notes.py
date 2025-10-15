import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.clinical_notes_models import ClinicalNote, UpsertClinicalNoteRequest
from app.models.common_models import ResponseModel
from app.models.user_models import Condition
from app.utils.db import (
    get_db_cursor,
    get_pediatric_appendicitis_clinical_note_by_id,
    get_pediatric_appendicitis_patient_by_id,
)
from app.utils.jwt import clinicians_only, require_access


def validate_patient_id(
    patient_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user_id: int = Depends(
        require_access(clinicians_only())
    ),  # Keep the auth here to not call it twice
) -> None:

    patient = get_pediatric_appendicitis_patient_by_id(cursor, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found"
        )

    if patient.clinician_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this patient's clinical notes",
        )


def validate_note_id(
    patient_id: int, note_id: int, cursor: MySQLCursorDict = Depends(get_db_cursor)
):

    clinical_note = get_pediatric_appendicitis_clinical_note_by_id(cursor, note_id)
    if clinical_note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    if clinical_note.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested note id does not belong to requested patient",
        )


router = APIRouter(
    prefix="/{patient_id}/clinical-notes",
    dependencies=[
        Depends(validate_patient_id),
    ],
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ResponseModel[None],
            "description": "Clinical note with requested note id does not belong to patient with requested patient id",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to access the requested resource",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Requested resource doesn't exist",
        },
    },
)


@router.get(
    "",
    summary="Get clinical notes",
    description="Get clinical notes for the requested patient, sorted by updated_at in descending order",
    response_model=ResponseModel[list[ClinicalNote]],
    response_description="List of clinical notes",
    status_code=status.HTTP_200_OK,
)
def get_clinical_notes(
    patient_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):

    operation = """
        SELECT *
        FROM pediatric_appendicitis_clinical_notes
        WHERE patient_id = %s
        ORDER BY updated_at DESC, id DESC
    """
    params = (patient_id,)
    cursor.execute(operation, params)
    rows = cursor.fetchall()

    clinical_notes = [ClinicalNote(**row) for row in rows]

    return ResponseModel[list[ClinicalNote]](
        data=clinical_notes, detail="Successfully retrieved clinical notes"
    )


@router.get(
    "/{note_id}",
    dependencies=[Depends(validate_note_id)],
    summary="Get clinical note",
    description="Get a clinical note for a patient by the note's ID",
    response_model=ResponseModel[ClinicalNote],
    response_description="The requested clinical note",
    status_code=status.HTTP_200_OK,
)
def get_clinical_note(
    patient_id: int,
    note_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):

    clinical_note = get_pediatric_appendicitis_clinical_note_by_id(cursor, note_id)

    return ResponseModel[ClinicalNote](
        data=clinical_note, detail="Successfully retrieved clinical note"
    )


@router.post(
    "",
    summary="Add clinical note",
    description="Add a clinical note for the patient",
    response_model=ResponseModel[ClinicalNote],
    response_description="The newly created clinical note",
    status_code=status.HTTP_201_CREATED,
)
def add_clinical_note(
    patient_id: int,
    add_clinical_note_request: UpsertClinicalNoteRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):

    # Insert the new note
    operation = """
        INSERT INTO pediatric_appendicitis_clinical_notes (patient_id, content)
        VALUES (%s, %s)
    """
    params = (patient_id, add_clinical_note_request.content)
    cursor.execute(operation, params)
    note_id = cursor.lastrowid

    clinical_note = get_pediatric_appendicitis_clinical_note_by_id(cursor, note_id)

    return ResponseModel[ClinicalNote](
        data=clinical_note, detail="Successfully added clinical note"
    )


@router.put(
    "/{note_id}",
    dependencies=[Depends(validate_note_id)],
    summary="Update clinical note",
    description="Update a clinical note for a patient by the note's ID",
    response_model=ResponseModel[ClinicalNote],
    response_description="The updated clinical note",
    status_code=status.HTTP_200_OK,
)
def update_clinical_note(
    patient_id: int,
    note_id: int,
    edit_clinical_note_request: UpsertClinicalNoteRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):

    # Insert the new note
    operation = """
        UPDATE pediatric_appendicitis_clinical_notes
        SET content = %s
        WHERE id = %s
    """
    params = (edit_clinical_note_request.content, note_id)
    cursor.execute(operation, params)

    clinical_note = get_pediatric_appendicitis_clinical_note_by_id(cursor, note_id)

    return ResponseModel[ClinicalNote](
        data=clinical_note, detail="Successfully edited clinical note"
    )


@router.delete(
    "/{note_id}",
    dependencies=[Depends(validate_note_id)],
    summary="Delete clinical note",
    description="Delete a clinical note for a patient by the note's ID",
    response_model=ResponseModel[None],
    response_description="Nothing really",
    status_code=status.HTTP_200_OK,
)
def delete_clinical_note(
    patient_id: int,
    note_id: int,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):

    # Insert the new note
    operation = """
        DELETE FROM pediatric_appendicitis_clinical_notes
        WHERE id = %s
    """
    params = (note_id,)
    cursor.execute(operation, params)

    return ResponseModel[None](data=None, detail="Successfully deleted clinical note")
