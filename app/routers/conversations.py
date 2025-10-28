from fastapi import APIRouter, Body, Depends, HTTPException, Query, Security, status
from mysql.connector.cursor import MySQLCursorDict

from app.models.chat_models import Message
from app.models.common_models import ResponseModel
from app.models.conversation_models import (
    AssistantSlug,
    Conversation,
    ConversationSummary,
    GetConversationResponse,
    StartConversationRequest,
    StartConversationResponse,
)
from app.models.user_models import User
from app.utils.assistants.access import has_access_to_assistant
from app.utils.assistants.mapping import assistant_mapping
from app.utils.db import get_db_cursor
from app.utils.dependencies import (
    all_registered_users,
    get_current_user,
    require_access,
    validate_breast_cancer_patient_id,
    validate_conversation_id,
    validate_pediatric_appendicitis_patient_id,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ResponseModel[None],
            "description": "Error with provided access token",
        },
    },
    dependencies=[Security(require_access(all_registered_users()))],
)


@router.post(
    "",
    summary="Start a conversation",
    description="Given some parameters for the conversation, initializes a conversation that messages can be sent on",
    response_model=ResponseModel[StartConversationResponse],
    response_description="The new conversation info",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ResponseModel[None],
            "description": "Not authorized to chat about the requested patient or with the requested assistant",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ResponseModel[None],
            "description": "Patient with requested ID not found",
        },
    },
)
def start_conversation(
    request: StartConversationRequest = Body(...),
    current_user: User = Depends(get_current_user),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    # Verify access to the requested assistant
    if not has_access_to_assistant(
        current_user.role, current_user.condition, request.assistant
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to chat with the requested assistant",
        )

    # If patient_id is provided, ensure the user has access to this patient
    if request.patient_id is not None:
        if request.assistant == "clinician-breast-cancer":
            validate_breast_cancer_patient_id(request.patient_id, cursor, current_user)
        elif request.assistant == "clinician-pediatric-appendicitis":
            validate_pediatric_appendicitis_patient_id(
                request.patient_id, cursor, current_user
            )

    assistant_class = assistant_mapping[request.assistant]
    conversation_title = assistant_class.get_title(request.user_message)

    operation = """
        INSERT INTO conversations (user_id, patient_id, title, assistant)
        VALUES (%s, %s, %s, %s)
    """
    params = (
        current_user.id,
        request.patient_id,
        conversation_title,
        request.assistant,
    )
    cursor.execute(operation, params)
    conversation_id = cursor.lastrowid

    return ResponseModel[StartConversationResponse](
        data=StartConversationResponse(
            conversation_id=conversation_id, conversation_title=conversation_title
        ),
        detail="Conversation started successfully",
    )


def _get_conversation_history(
    cursor: MySQLCursorDict, conversation_id: int
) -> list[Message]:
    operation = """
        SELECT role, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY message_order ASC, id ASC
    """
    params = (conversation_id,)
    cursor.execute(operation, params)

    rows = cursor.fetchall()
    return [Message(**row) for row in rows]


@router.get(
    "/{conversation_id}",
    summary="Get conversation history",
    description="Get all messages for a conversation",
    response_model=ResponseModel[GetConversationResponse],
    response_description="Messages sorted by updated_at desc",
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
    conversation: Conversation = Depends(validate_conversation_id),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    messages = _get_conversation_history(cursor, conversation.id)

    return ResponseModel[GetConversationResponse](
        data=GetConversationResponse(
            messages=messages, patient_id=conversation.patient_id
        ),
        detail="Conversation fetched successfully",
    )


@router.get(
    "",
    summary="Get conversation summaries for the logged-in user",
    description="Retrieves all conversations for the current user (by the provided access token), sorted by the most recently updated",
    response_model=ResponseModel[list[ConversationSummary]],
    response_description="Conversations sorted by updated_at descending",
    status_code=status.HTTP_200_OK,
)
def get_user_conversations(
    assistant: AssistantSlug | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    cursor: MySQLCursorDict = Depends(get_db_cursor),
):
    where_clause = "user_id=%s"
    params = (current_user.id,)
    if assistant:
        where_clause += " AND assistant=%s"
        params = params + (assistant,)

    operation = f"""
        SELECT id, title, patient_id
        FROM conversations
        WHERE {where_clause}
        ORDER BY updated_at DESC, id DESC
    """
    cursor.execute(operation, params)

    rows = cursor.fetchall()

    conversations = [ConversationSummary(**row) for row in rows]
    return ResponseModel[list[ConversationSummary]](
        data=conversations, detail="Conversations fetched successfully"
    )
