

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat_messages import ChatMessage as ChatMessageModel
import app.schemas.chat as schemas

router = APIRouter()
SCHEMAS = 'chatbot'
group_tags = ["AI Assistant"]


@router.get(
    "/chat",
    tags=group_tags,
    response_model=List[schemas.ChatMessage]
)
def load_chat(
    userId: str,
    db: Session = Depends(get_db)
) -> List[schemas.ChatMessage]:
    """
    Load chat messages for the specified user.
    Returns messages ordered by creation time (ascending).
    Matches TypeScript: loadChat(userId: string): Promise<Message[]>
    
    - userId: UUID of the user to load messages for
    """
    try:
        messages = db.query(ChatMessageModel)\
            .filter(ChatMessageModel.user_id == userId)\
            .order_by(ChatMessageModel.created_at.asc())\
            .all()
        
        # Convert database models to schema models - return array directly
        message_list = []
        for msg in messages:
            message_list.append(schemas.ChatMessage(
                id=msg.id,
                content=msg.content,
                role=msg.role,
                createdAt=msg.created_at,
                toolInvocations=msg.tool_invocations
            ))
        
        return message_list
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading chat messages: {str(e)}"
        )


@router.post(
    "/chat",
    tags=group_tags,
    status_code=status.HTTP_204_NO_CONTENT
)
def save_chat(
    request: schemas.SaveChatRequest,
    db: Session = Depends(get_db)
) -> Response:
    """
    Save or update chat messages for the specified user.
    Uses upsert operation to insert new messages or update existing ones.
    Matches TypeScript: saveChat({ userId, messages }): Promise<void>
    
    - request: Contains userId and messages to save
    """
    try:
        # Prepare messages for upsert
        messages_to_upsert = []
        for msg in request.messages:
            messages_to_upsert.append({
                'id': msg.id,
                'user_id': request.userId,
                'content': msg.content,
                'role': msg.role,
                'created_at': msg.createdAt if isinstance(msg.createdAt, datetime) else datetime.fromisoformat(msg.createdAt) if isinstance(msg.createdAt, str) else datetime.now(),
                'tool_invocations': msg.toolInvocations or None
            })
        
        # Perform upsert operation
        for msg_data in messages_to_upsert:
            # Check if message exists
            existing_msg = db.query(ChatMessageModel)\
                .filter(ChatMessageModel.id == msg_data['id'])\
                .filter(ChatMessageModel.user_id == request.userId)\
                .first()
            
            if existing_msg:
                # Update existing message
                existing_msg.content = msg_data['content']
                existing_msg.role = msg_data['role']
                existing_msg.created_at = msg_data['created_at']
                existing_msg.tool_invocations = msg_data['tool_invocations']
            else:
                # Insert new message
                new_msg = ChatMessageModel(**msg_data)
                db.add(new_msg)
        
        db.commit()
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving chat messages: {str(e)}"
        )
