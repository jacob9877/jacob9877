import traceback
from typing import Literal

import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection
from pydantic import BaseModel

from app.models.common_models import ResponseModel
from app.utils.db import conversation_exists, get_db_connection

router = APIRouter(prefix="/conversations", tags=["conversations"])


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


@router.get(
    "/{conversation_id}",
    response_model=ResponseModel[list[Message]],
    summary="Get all messages in a conversation",
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

        cursor.execute(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = %s ORDER BY message_order ASC
            """,
            (conversation_id,),
        )

        rows = cursor.fetchall()
        messages = [Message(**row) for row in rows]
        return ResponseModel[list[Message]](
            data=messages, detail="Conversation fetched successfully"
        )

    except HTTPException as http_error:
        return JSONResponse(
            status_code=http_error.status_code,
            content=ResponseModel[None](detail=http_error.detail).model_dump(),
        )
    except mysql.connector.Error as db_error:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseModel[None](detail=str(db_error)).model_dump(),
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
