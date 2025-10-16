from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.chat_models import ChatRequest, ChatResponse
from app.models.common_models import ResponseModel
from app.models.conversation_models import AssistantSlug
from app.models.user_models import User
from app.utils.assistants.access import has_access_to_assistant
from app.utils.assistants.mapping import assistant_mapping
from app.utils.db import get_db_cursor
from app.utils.dependencies import (
    all_registered_users,
    get_current_user,
    require_access,
    validate_conversation_id,
)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
    dependencies=[Security(require_access(all_registered_users()))],
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
    description="Take in a message from the user, and given this message plus the previous conversation history, send a reply back to the user using LLM. May also include a new conversation title if this is the first user message of the conversation",
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
def chat(
    request: ChatRequest,
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):

    conversation = validate_conversation_id(
        request.conversation_id, cursor, current_user
    )

    assistant = assistant_mapping[conversation.assistant](conversation)
    assistant_reply = assistant.invoke(request.user_message)

    _insert_message(cursor, request.conversation_id, "user", request.user_message)
    _insert_message(cursor, request.conversation_id, "assistant", assistant_reply)

    return ResponseModel[ChatResponse](
        data=ChatResponse(
            assistant_reply=assistant_reply, conversation_id=request.conversation_id
        ),
        detail="Reply and title generated successfully",
    )


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
    cursor: MySQLCursorDict = Depends(get_db_cursor),
    current_user: User = Depends(get_current_user),
):

    # Verify access to the requested assistant
    if not has_access_to_assistant(
        current_user.role, current_user.condition, assistant
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to chat with the requested assistant",
        )

    suggestions: list[str] = []
    if assistant == "clinician-breast-cancer":
        operation = """
            SELECT p.id
            FROM breast_cancer_patients AS p
            JOIN breast_cancer_explanations AS e
            ON e.patient_id = p.id
            WHERE p.clinician_user_id = %s
            ORDER BY p.updated_at DESC
            LIMIT 1;
        """
        params = (current_user.id,)
        cursor.execute(operation, params)
        row = cursor.fetchone()
        if row is not None:
            patient_id = row["id"]
            suggestion = f"Can you explain patient {patient_id}'s diagnosis?"
            suggestions.append(suggestion)

        suggestions.append("What are some recruiting breast cancer clinical trials?")

    elif assistant == "clinician-pediatric-appendicitis":
        operation = """
            SELECT p.id, p.diagnosis, p.management
            FROM pediatric_appendicitis_patients AS p
            JOIN pediatric_appendicitis_explanations AS e
            ON e.patient_id = p.id
            WHERE p.clinician_user_id = %s
            ORDER BY p.updated_at DESC
            LIMIT 1;
        """
        params = (current_user.id,)
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

        suggestions.append(
            "Are there any recruiting clinical trials for pediatric appendicitis?"
        )

    elif assistant == "patient-breast-cancer":
        suggestions.append("What are some common breast cancer recovery struggles?")

    elif assistant == "patient-pediatric-appendicitis":
        suggestions.append(
            "What are some common recovery struggles with appendicitis in kids?"
        )

    return ResponseModel[list[str]](
        detail="No suggestions available" if len(suggestions) == 0 else "",
        data=suggestions,
    )
