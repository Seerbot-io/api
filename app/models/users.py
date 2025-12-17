from sqlalchemy import Column, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func, text

from app.db.base import Base


class User(Base):
    """Model for users table in chatbot schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "wallet_address": "addr1qxy99g3k...useraddress",
        "created_at": "2024-01-01T12:00:00",
        "last_active_at": "2024-01-01T12:00:00"
    }
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "chatbot"}

    id = Column(
        UUID(as_uuid=False), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    wallet_address = Column(Text, nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_active_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
