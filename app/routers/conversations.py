import traceback

from fastapi import APIRouter, Depends, HTTPException, Path, status
from mysql.connector import MySQLConnection

from app.models.chat_models import Message
from app.models.common_models import ResponseModel
from app.models.conversation_models import ConversationSummary
from app.models.user_models import User
from app.utils.db import get_conversation_by_id, get_db_connection
from app.utils.jwt import get_and_validate_current_user_id
from app.utils.llm import get_conversation_history

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)


@router.get(
    "/{conversation_id}",
    summary="Get all messages in a conversation",
    description="Get all messages for the conversation with the provided ID",
    response_model=ResponseModel[list[Message]],
    response_description="Messages in the conversation sorted by timestamp",
    status_code=status.HTTP_200_OK,
    responses={
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

            conversation = get_conversation_by_id(cursor, conversation_id)
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

        messages = get_conversation_history(conversation_id)

        return ResponseModel[list[Message]](
            data=messages, detail="Conversation fetched successfully"
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
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            operation = """
                SELECT id, title
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC, id DESC
            """
            params = (current_user_id,)
            cursor.execute(operation, params)

            rows = cursor.fetchall()

        conversations = [ConversationSummary(**row) for row in rows]
        return ResponseModel[list[ConversationSummary]](
            data=conversations, detail="Fetched conversations successfully"
        )

    except Exception as e:
        traceback.print_exc()
        raise e
