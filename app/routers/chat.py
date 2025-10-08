import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, status
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict

from app.models.chat_models import ChatRequest, ChatResponse
from app.models.common_models import ResponseModel
from app.models.conversation_models import AssistantSlug
from app.utils.assistants.mapping import assistant_mapping
from app.utils.db import get_conversation_by_id, get_db_connection
from app.utils.jwt import get_and_validate_current_user_id

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
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
        INSERT INTO messages (conversation_id, role, content, message_order)
        SELECT %s, %s, %s, COALESCE(MAX(message_order), 0) + 1
        FROM messages
        WHERE conversation_id = %s
    """
    params = (conversation_id, role, content, conversation_id)
    cursor.execute(operation, params)


@router.post(
    "",
    summary="Send a message to get a reply",
    description="Take in a message from the user, and given this message plus the previous conversation history, send a reply back to the user using Gemini. May also include a new conversation title if this is the first user message of the conversation",
    response_model=ResponseModel[ChatResponse],
    response_description='Returns the assistant reply and potentially a new conversation title (will be "" if not created)',
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

            conversation = get_conversation_by_id(cursor, request.conversation_id)

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

            assistant = assistant_mapping[conversation.assistant](conversation)
            assistant_reply = assistant.invoke(request.user_message)

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
            detail="Reply and title generated successfully",
        )

    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        raise e


@router.get(
    "/suggestions",
    summary="Get chat suggestions",
    description="Generate chat suggestions given the discipline/assistant. Uses a programmatic approach to recommend potentially useful questions",
    response_model=ResponseModel[list[str]],
    response_description="Returns a list of suggestions (str)",
    status_code=status.HTTP_200_OK,
)
def get_chat_suggestions(
    assistant: AssistantSlug = Query(...),
    conn: MySQLConnection = Depends(get_db_connection),
    current_user_id: int = Depends(get_and_validate_current_user_id),
):

    suggestions: list[str] = []
    with conn.cursor(dictionary=True) as cursor:

        if assistant == "clinician-breast-cancer":
            operation = """
                SELECT p.id
                FROM breast_cancer_patients AS p
                JOIN breast_cancer_explanations AS e
                ON e.patient_id = p.id
                WHERE p.user_id = %s
                ORDER BY p.updated_at DESC
                LIMIT 1;
            """
            params = (current_user_id,)
            cursor.execute(operation, params)
            row = cursor.fetchone()
            if row is not None:
                patient_id = row["id"]
                suggestion = f"Can you explain patient {patient_id}'s diagnosis?"
                suggestions.append(suggestion)

        else:
            operation = """
                SELECT p.id, p.diagnosis, p.management
                FROM pediatric_appendicitis_patients AS p
                JOIN pediatric_appendicitis_explanations AS e
                ON e.patient_id = p.id
                WHERE p.user_id = %s
                ORDER BY p.updated_at DESC
                LIMIT 1;
            """
            params = (current_user_id,)
            cursor.execute(operation, params)
            row = cursor.fetchone()
            if row is not None:
                patient_id = row["id"]
                # If one of the patient's outcomes is the positive class, tell them to ask for explanation
                if row["diagnosis"] == "appendicitis":
                    suggestion = f"Can you explain patient {patient_id}'s diagnosis?"
                elif row["management"] == "surgical":
                    suggestion = f"Can you explain patient {patient_id}'s management?"
                # If both diagnosis and management are negative class, default to diagnosis explanation
                else:
                    suggestion = f"Can you explain patient {patient_id}'s diagnosis?"
                suggestions.append(suggestion)

    return ResponseModel[list[str]](
        detail="No suggestions available" if len(suggestions) == 0 else "",
        data=suggestions,
    )
