from sqlalchemy import Column, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.db.base import Base


class ChatMessage(Base):
    """Model for chat_messages table in chatbot schema
    Example:
    {
        "id": "msg_123",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "content": "Hello, how can I help?",
        "role": "assistant",
        "created_at": "2024-01-01T12:00:00",
        "tool_invocations": {"tool": "search", "args": {...}}
    }
    """

    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "chatbot"}

    id = Column(Text, primary_key=True)
    user_id = Column(
        UUID(as_uuid=False), ForeignKey("chatbot.users.id"), nullable=False, index=True
    )
    content = Column(Text, nullable=False)
    role = Column(Text, nullable=False)  # 'user', 'assistant', 'system', 'tool'
    tool_invocations = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
