

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat_messages import ChatMessage
from app.models.users import User
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
    wallet_address: str,
    db: Session = Depends(get_db)
) -> List[schemas.ChatMessage]:
    """
    Load all chat messages for a user based on their wallet address.

    This endpoint:
    - Finds the user using the provided wallet address.
    - Retrieves all chat messages associated with the user.
    - Returns messages ordered by creation time (ascending).

    Query Parameters:
    - wallet_address (str): The wallet address of the user.

    Responses:
    - 200: List of chat messages.
    - 404: User not found.
    - 500: Internal server error.
    """
    try:
        # Query chat messages using join
        sql = f"""
        select cm.id, cm.content, cm.role, cm.created_at, cm.tool_invocations
        from (
            SELECT u.id FROM chatbot.users u where u.wallet_address = '{wallet_address}'
        ) u
        inner JOIN chatbot.chat_messages cm ON cm.user_id = u.id
        ORDER BY cm.created_at ASC
        """
        messages = db.execute(text(sql)).fetchall()

        # Convert database models to schema
        message_list = [
            schemas.ChatMessage(
                id=msg.id or '',
                content=msg.content or '',
                role=msg.role or 'user',
                createdAt=msg.created_at or datetime.now(),
                toolInvocations= msg.tool_invocations or {}
            )
            for msg in messages
        ]
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
    Save or update chat messages using a wallet address.

    This endpoint:
    - Looks up a user by wallet address.
    - Automatically creates the user if they do not exist.
    - Upserts (inserts or updates) all provided chat messages.

    Request Body:
    - walletAddress (str): The user’s wallet address.
    - messages (List): List of chat messages to save.

    Behavior:
    - If a message ID already exists → it is updated.
    - If a message ID is new → it is inserted.

    Responses:
    - 204: Messages saved successfully.
    - 500: Error during save operation.
    """
    try:
        # 1. Find user by wallet address
        user = db.query(User).filter(User.wallet_address == request.wallet_address).first()

        # 2. Auto-create user if not found
        if not user:
            user = User(wallet_address=request.wallet_address)
            db.add(user)
            db.commit()     # Need commit so user.id becomes available
            db.refresh(user)
        # 3. Save or update messages (upsert)
        for msg in request.messages:
            msg_data = {
                'id': msg.id,
                'user_id': user.id,
                'content': msg.content,
                'role': msg.role,
                'created_at': (
                    msg.created_at if isinstance(msg.created_at, datetime)
                    else datetime.fromisoformat(msg.created_at)
                ),
                'tool_invocations': msg.tool_invocations or {}
            }

            existing_msg = (
                db.query(ChatMessage)
                .filter(ChatMessage.id == msg_data['id'])
                .filter(ChatMessage.user_id == user.id)
                .first()
            )
            if existing_msg:
                existing_msg.content = msg_data['content']
                existing_msg.role = msg_data['role']
                existing_msg.created_at = msg_data['created_at']
                existing_msg.tool_invocations = msg_data['tool_invocations']
            else:
                new_msg = ChatMessage(**msg_data)
                db.add(new_msg)

        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        print("Error in save_chat:", str(e))
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving chat messages: {str(e)}"
        )
