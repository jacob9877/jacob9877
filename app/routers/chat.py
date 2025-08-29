import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from mysql.connector import MySQLConnection

from app.models.chat_models import ChatRequest, ChatResponse
from app.models.common_models import ResponseModel
from app.utils.db import get_conversation_by_id, get_db_connection
from app.utils.jwt import get_and_validate_current_user_id
from app.utils.llm import get_chat_response, get_gemini_title

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
)


@router.post(
    "",
    summary="Send a message to get a reply",
    description="Take in a message from the user, and given this message plus the previous conversation history, send a reply back to the user using Gemini. May also include a new conversation title if this is the first user message of the conversation",
    response_model=ResponseModel[ChatResponse],
    response_description='Returns the assistant reply and potentially a new conversation title (will be "" if not created)',
    status_code=status.HTTP_201_CREATED,
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

            conversation_id = request.conversation_id
            conversation_title = ""
            conversation = get_conversation_by_id(cursor, conversation_id)

            # User provided a conversation ID but it doesn't exist
            if request.conversation_id and not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Conversation with ID {request.conversation_id} not found",
                )
            # User provided a conversation ID but it doesn't belong to them
            elif request.conversation_id and conversation.user_id != current_user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to access conversation {request.conversation_id}",
                )
            # User did not provide a conversation ID
            elif request.conversation_id is None:
                conversation_title = get_gemini_title(request.user_message)
                operation = """
                    INSERT INTO conversations (user_id, title) 
                    VALUES (%s, %s)
                """
                params = (current_user_id, conversation_title)
                cursor.execute(operation, params)
                conversation_id = cursor.lastrowid
                conn.commit()

        assistant_reply = get_chat_response(
            conversation_id, current_user_id, request.user_message
        )

        return ResponseModel[ChatResponse](
            data=ChatResponse(
                assistant_reply=assistant_reply,
                conversation_title=conversation_title,
                conversation_id=conversation_id,
            ),
            detail="Reply and title generated successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e
