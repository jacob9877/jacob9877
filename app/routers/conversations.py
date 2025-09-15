import traceback

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.chat_models import Message
from app.models.common_models import ResponseModel
from app.models.conversation_models import (
    ConversationSummary,
    GetConversationResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from app.utils.db import (
    get_breast_cancer_conversation_by_id,
    get_breast_cancer_patient_by_id,
    get_db_connection,
)
from app.utils.jwt import get_and_validate_current_user_id
from app.utils.llm import get_gemini_title

router = APIRouter(
    prefix="/breast-cancer-conversations",
    tags=["Breast Cancer Conversations"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)


@router.post(
    "",
    summary="Create a conversation about breast cancer",
    description="",
    response_model=ResponseModel[StartConversationResponse],
    response_description="ID of the newly created conversation and the title",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to chat about the requested patient",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient not found",
        },
    },
)
def start_conversation(
    request: StartConversationRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:
            # If patient_id is provided, ensure the user has access to this patient
            if request.patient_id is not None:
                patient = get_breast_cancer_patient_by_id(cursor, request.patient_id)
                if patient is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Patient with ID {request.patient_id} not found",
                    )
                if patient.user_id != current_user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Not authorized to chat about patient with ID {request.patient_id}",
                    )

            conversation_title = get_gemini_title(request.user_message)
            operation = """
                INSERT INTO breast_cancer_conversations (user_id, patient_id, title)
                VALUES (%s, %s, %s)
            """
            params = (current_user_id, request.patient_id, conversation_title)
            cursor.execute(operation, params)
            conversation_id = cursor.lastrowid
        conn.commit()

        return ResponseModel[StartConversationResponse](
            data=StartConversationResponse(
                conversation_id=conversation_id, conversation_title=conversation_title
            ),
            detail="Conversation started successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


def _get_conversation_history(
    cursor: MySQLCursorDict, conversation_id: int
) -> list[Message]:
    operation = """
        SELECT role, content
        FROM breast_cancer_messages
        WHERE conversation_id = %s
        ORDER BY message_order ASC, id ASC
    """
    params = (conversation_id,)
    cursor.execute(operation, params)

    rows = cursor.fetchall()
    return [Message(**row) for row in rows]


@router.get(
    "/{conversation_id}",
    summary="Get all messages in a breast cancer conversation",
    description="Get all messages for the conversation with the provided ID",
    response_model=ResponseModel[GetConversationResponse],
    response_description="Messages in the conversation sorted by timestamp",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to access the requested conversation",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Conversation not found",
        },
    },
)
def get_conversation(
    conversation_id: int = Path(
        description="ID of the conversation to return", example=1
    ),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            conversation = get_breast_cancer_conversation_by_id(cursor, conversation_id)
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation with ID {conversation_id} not found",
                )
            if conversation.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to access conversation with ID {conversation_id}",
                )

            messages = _get_conversation_history(cursor, conversation_id)

        return ResponseModel[GetConversationResponse](
            data=GetConversationResponse(
                messages=messages, patient_id=conversation.patient_id
            ),
            detail="Conversation fetched successfully",
        )

    except Exception as e:
        traceback.print_exc()
        raise e


@router.get(
    "",
    summary="Get conversation summaries for the logged-in user",
    description="Retrieves all conversations for the current user (by the provided access token), sorted by the most recently updated",
    response_model=ResponseModel[list[ConversationSummary]],
    response_description="Returns all conversations, sorted by most recently updated",
    status_code=status.HTTP_200_OK,
)
def get_user_conversations(
    conn: MySQLConnection = Depends(get_db_connection),
    patient_id: int | None = Query(
        default=None, description="Patient ID to filter conversations by"
    ),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            operation = f"""
                SELECT id, title, patient_id
                FROM breast_cancer_conversations
                WHERE user_id = %s {"AND patient_id = %s" if patient_id else ""}
                ORDER BY updated_at DESC, id DESC
            """
            params = (current_user_id, patient_id) if patient_id else (current_user_id,)
            cursor.execute(operation, params)

            rows = cursor.fetchall()

        conversations = [ConversationSummary(**row) for row in rows]
        return ResponseModel[list[ConversationSummary]](
            data=conversations, detail="Fetched conversations successfully"
        )

    except Exception as e:
        traceback.print_exc()
        raise e
