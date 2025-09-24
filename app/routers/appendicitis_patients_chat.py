import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.chat_models import ChatRequest, ChatResponse
from app.models.common_models import ResponseModel
from app.utils.db import (
    get_pediatric_appendicitis_conversation_by_id,
    get_db_connection,
)
from app.utils.jwt import get_and_validate_current_user_id
from app.utils.llm_appendicitis import get_chat_response

router = APIRouter(
    prefix="/appendicitis-chat",
    tags=["Pediatric Appendicitis Chat"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)


def _insert_message(
    cursor: MySQLCursorDict, conversation_id: int, role: str, content: str
):
    operation = """
        INSERT INTO pediatric_appendicitis_messages (conversation_id, role, content, message_order)
        SELECT %s, %s, %s, COALESCE(MAX(message_order), 0) + 1
        FROM pediatric_appendicitis_messages
        WHERE conversation_id = %s
    """
    params = (conversation_id, role, content, conversation_id)
    cursor.execute(operation, params)


@router.post(
    "",
    summary="Send a message to the Pediatric Appendicitis chatbot",
    description="Takes in a message from the user, uses the Pediatric Appendicitis model + Gemini for response generation, and returns a reply. If this is the first user message, may also create a new conversation entry.",
    response_model=ResponseModel[ChatResponse],
    response_description="Returns the assistant reply and conversation ID (title can be managed separately)",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to perform the requested action",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "No conversation exists with the provided ID",
        },
    },
)
def chat_agent(
    request: ChatRequest,
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):
    try:
        with conn.cursor(dictionary=True) as cursor:

            conversation = get_pediatric_appendicitis_conversation_by_id(
                cursor, request.conversation_id
            )

            # User provided a conversation ID but it doesn't exist
            if request.conversation_id and not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation with ID {request.conversation_id} not found",
                )
            # User provided a conversation ID but the conversation doesn't belong to them
            elif request.conversation_id and conversation.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to access conversation {request.conversation_id}",
                )

            assistant_reply = get_chat_response(
                conversation,
                request.user_message,
            )

            _insert_message(
                cursor, request.conversation_id, "user", request.user_message
            )
            _insert_message(
                cursor, request.conversation_id, "assistant", assistant_reply
            )
            conn.commit()

        return ResponseModel[ChatResponse](
            data=ChatResponse(
                assistant_reply=assistant_reply, conversation_id=request.conversation_id
            ),
            detail="Reply generated successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e
