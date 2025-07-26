import traceback
from datetime import datetime

import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from app.models.chat_models import (
    ChatRequest,
    ChatResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from app.models.common_models import ResponseModel
from app.utils.db import conversation_exists, get_db_connection, user_exists
from app.utils.gemini_utils import get_gemini_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/start",
    summary="Start a conversation",
    description="Starts a conversation by creating a new conversation and adding a pre-seeded assistant message to it",
    response_model=ResponseModel[StartConversationResponse],
    response_description="ID of the newly created conversation, and the pre-seeded assistant message that should be presented to the user",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "No user exists with the provided ID",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ResponseModel[None],
            "description": "An error occurred on our end",
        },
    },
)
def start_conversation(
    request: StartConversationRequest,
    conn: MySQLConnection = Depends(get_db_connection),
):
    try:
        cursor = conn.cursor(dictionary=True)

        if not user_exists(cursor, request.user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {request.user_id} not found",
            )

        # CHANGE THIS LATER
        title = f"Convo that began at {datetime.now().isoformat()}"

        # Insert with user_id (aligned with schema)
        cursor.execute(
            """
            INSERT INTO conversations (user_id, title) 
            VALUES (%s, %s)
            """,
            (request.user_id, title),
        )

        conversation_id = cursor.lastrowid

        assistant_message = "Hi, I'm Barry! How can I help you?"
        cursor.execute(
            """
            INSERT INTO messages (conversation_id, role, content, message_order)
            VALUES (%s, 'assistant', %s, 1)""",
            (conversation_id, assistant_message),
        )
        conn.commit()

        return ResponseModel[StartConversationResponse](
            data=StartConversationResponse(
                conversation_id=conversation_id,
                title=title,
                assistant_message=assistant_message,
            ),
            detail="Conversation created successfully with initial message",
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
        if conn:
            conn.close()


def get_conversation_history(cursor: MySQLCursor, conversation_id: int) -> list[dict]:
    cursor.execute(
        """
        SELECT role, content FROM messages
        WHERE conversation_id = %s ORDER BY message_order
        """,
        (conversation_id,),
    )
    rows = cursor.fetchall()

    # Format for Gemini API
    return [{"role": row["role"], "parts": [row["content"]]} for row in rows]


def insert_message(cursor: MySQLCursor, conversation_id: int, role: str, content: str):

    cursor.execute(
        """SELECT MAX(message_order) FROM messages WHERE conversation_id = %s""",
        (conversation_id,),
    )
    result = cursor.fetchone()
    next_order = (
        result["MAX(message_order)"] or 0
    ) + 1  # Assuming cursor has dictionary=True

    cursor.execute(
        """
        INSERT INTO messages (conversation_id, role, content, message_order)
        VALUES (%s, %s, %s, %s)
        """,
        (conversation_id, role, content, next_order),
    )


@router.post(
    "/",
    summary="Send a message to get a reply",
    description="Take in a message from the user, and given this message plus the previous conversation history, send a reply back to the user using Gemini",
    response_model=ResponseModel[ChatResponse],
    response_description="Returns the assistant reply",
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
def chat(request: ChatRequest, conn: MySQLConnection = Depends(get_db_connection)):
    try:
        cursor = conn.cursor(dictionary=True)

        if not conversation_exists(cursor, request.conversation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation with ID {request.conversation_id} not found",
            )

        insert_message(cursor, request.conversation_id, "user", request.user_message)

        history = get_conversation_history(cursor, request.conversation_id)
        history.append({"role": "user", "parts": [request.user_message]})

        assistant_reply = get_gemini_response(history)

        insert_message(cursor, request.conversation_id, "assistant", assistant_reply)
        conn.commit()

        return ResponseModel[ChatResponse](
            data=ChatResponse(assistant_reply=assistant_reply),
            detail="Reply generated successfully",
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
        if conn:
            conn.close()
