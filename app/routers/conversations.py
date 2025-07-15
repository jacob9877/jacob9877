import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any

import mysql.connector
from fastapi import APIRouter, Depends, HTTPException, Query
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor
from pydantic import BaseModel, Field

from app.utils.db import get_db_connection

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    user_id: Optional[int] = Field(None, description="ID of the user")
    title: Optional[str] = Field(None, description="Title of the conversation")


class SaveMessageRequest(BaseModel):
    role: str = Field(..., description="Role of the message sender (user/assistant)")
    content: str = Field(..., description="Content of the message")
    message_order: int = Field(..., description="Order of the message in conversation")


class UpdateTitleRequest(BaseModel):
    title: str = Field(..., description="New title for the conversation")


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime
    message_order: int


class ConversationResponse(BaseModel):
    id: int
    user_id: Optional[int]
    title: Optional[str]
    messages: List[MessageResponse]
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=Dict[str, Any])
def create_conversation(
    request: CreateConversationRequest,
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Create a new conversation"""
    try:
        cursor = conn.cursor()
        
        # Insert with user_id (aligned with schema)
        query = """
            INSERT INTO conversations (user_id, title, created_at, updated_at) 
            VALUES (%s, %s, NOW(), NOW())
        """
        
        cursor.execute(query, (request.user_id, request.title))
        conversation_id = cursor.lastrowid
        conn.commit()
        
        return {"success": True, "conversationId": conversation_id}
        
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to create conversation")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.post("/{conversation_id}/messages", response_model=Dict[str, Any])
def save_message(
    conversation_id: int,
    request: SaveMessageRequest,
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Save a message to a conversation"""
    try:
        cursor = conn.cursor()
        
        # Insert message without specifying ID (let MySQL auto-generate it)
        message_query = """
            INSERT INTO messages (conversation_id, role, content, message_order, created_at) 
            VALUES (%s, %s, %s, %s, NOW())
        """
        cursor.execute(message_query, (
            conversation_id, 
            request.role, 
            request.content, 
            request.message_order
        ))
        message_id = cursor.lastrowid
        
        # Update conversation timestamp
        cursor.execute(
            "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
            (conversation_id,)
        )
        
        conn.commit()
        
        return {"success": True, "messageId": message_id}
        
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to save message")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.put("/{conversation_id}/title", response_model=Dict[str, Any])
def update_conversation_title(
    conversation_id: int,
    request: UpdateTitleRequest,
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Update conversation title"""
    try:
        cursor = conn.cursor()
        
        query = """
            UPDATE conversations 
            SET title = %s, updated_at = NOW() 
            WHERE id = %s
        """
        
        cursor.execute(query, (request.title, conversation_id))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"success": True}
        
    except HTTPException as e:
        raise e
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to update conversation title")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.get("/", response_model=Dict[str, Any])
def get_all_conversations(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Get all conversations with optional user filter"""
    try:
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                   m.id as message_id, m.role, m.content, m.message_order, m.created_at as message_created_at
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
        """
        params = []
        
        if user_id:
            query += " WHERE c.user_id = %s"
            params.append(user_id)
        
        query += " ORDER BY c.updated_at DESC, m.message_order ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Group messages by conversation
        conversation_map = {}
        
        for row in rows:
            conv_id = row['id']
            if conv_id not in conversation_map:
                conversation_map[conv_id] = {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'title': row['title'],
                    'messages': [],
                    'createdAt': row['created_at'],
                    'updatedAt': row['updated_at']
                }
            
            if row['message_id']:
                conversation_map[conv_id]['messages'].append({
                    'id': row['message_id'],
                    'role': row['role'],
                    'content': row['content'],
                    'timestamp': row['message_created_at'],
                    'message_order': row['message_order']
                })
        
        conversations = list(conversation_map.values())
        return {"success": True, "conversations": conversations}
        
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to retrieve conversations")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.get("/{conversation_id}", response_model=Dict[str, Any])
def get_conversation(
    conversation_id: int,
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Get a specific conversation with messages"""
    try:
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                   m.id as message_id, m.role, m.content, m.message_order, m.created_at as message_created_at
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.id = %s
            ORDER BY m.message_order ASC
        """
        
        cursor.execute(query, (conversation_id,))
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        first_row = rows[0]
        conversation = {
            'id': first_row['id'],
            'user_id': first_row['user_id'],
            'title': first_row['title'],
            'messages': [],
            'createdAt': first_row['created_at'],
            'updatedAt': first_row['updated_at']
        }
        
        for row in rows:
            if row['message_id']:
                conversation['messages'].append({
                    'id': row['message_id'],
                    'role': row['role'],
                    'content': row['content'],
                    'timestamp': row['message_created_at'],
                    'message_order': row['message_order']
                })
        
        return {"success": True, "conversation": conversation}
        
    except HTTPException as e:
        raise e
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.delete("/{conversation_id}", response_model=Dict[str, Any])
def delete_conversation(
    conversation_id: int,
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Delete a specific conversation"""
    try:
        cursor = conn.cursor()
        
        query = "DELETE FROM conversations WHERE id = %s"
        cursor.execute(query, (conversation_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {"success": True}
        
    except HTTPException as e:
        raise e
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@router.delete("/", response_model=Dict[str, Any])
def clear_all_conversations(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    conn: MySQLConnection = Depends(get_db_connection)
):
    """Clear all conversations with optional user filter"""
    try:
        cursor = conn.cursor()
        
        query = "DELETE FROM conversations"
        params = []
        
        if user_id:
            query += " WHERE user_id = %s"
            params.append(user_id)
        
        cursor.execute(query, params)
        conn.commit()
        
        return {"success": True}
        
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to clear conversations")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()