import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection

from app.models.chat_models import ChatRequest, ChatResponse
from app.models.common_models import ResponseModel
from app.utils.db import conversation_exists, get_db_connection
from app.utils.llm import get_chat_response, get_gemini_title

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    summary="Send a message to get a reply",
    description="Take in a message from the user, and given this message plus the previous conversation history, send a reply back to the user using Gemini. May also include a new conversation title if this is the first user message of the conversation",
    response_model=ResponseModel[ChatResponse],
    response_description='Returns the assistant reply and potentially a new conversation title (will be "" if not created)',
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "No conversation exists with the provided ID",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def chat_agent(
    request: ChatRequest, conn: MySQLConnection = Depends(get_db_connection)
):
    try:
        cursor = conn.cursor(dictionary=True)

        conversation_id = request.conversation_id
        conversation_title = ""

        # Later we should do some validation to see if the conversation actually belongs to the user
        if request.conversation_id and not conversation_exists(
            cursor, request.conversation_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation with ID {request.conversation_id} not found",
            )
        elif request.conversation_id is None:
            conversation_title = get_gemini_title(request.user_message)
            operation = """
                INSERT INTO conversations (user_id, title) 
                VALUES (%s, %s)
            """
            params = (request.user_id, conversation_title)
            cursor.execute(operation, params)
            conversation_id = cursor.lastrowid
            conn.commit()

        assistant_reply = get_chat_response(
            conversation_id, request.user_id, request.user_message
        )

        return ResponseModel[ChatResponse](
            data=ChatResponse(
                assistant_reply=assistant_reply,
                conversation_title=conversation_title,
                conversation_id=conversation_id,
            ),
            detail="Reply and title generated successfully",
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()
