import traceback

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection

from app.models.chat_models import Message
from app.models.common_models import ResponseModel
from app.utils.db import conversation_exists, get_db_connection
from app.utils.llm import get_conversation_history

router = APIRouter(prefix="/conversations", tags=["conversations"])


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
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def get_conversation(
    conversation_id: int = Path(
        description="ID of the conversation to return", example=1
    ),
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not conversation_exists(cursor, conversation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation with ID {conversation_id} not found",
            )

        messages = get_conversation_history(conversation_id)

        return ResponseModel[list[Message]](
            data=messages, detail="Conversation fetched successfully"
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(e)).model_dump(),
        )
    finally:
        if cursor:
            cursor.close()
