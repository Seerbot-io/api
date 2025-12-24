from sqlalchemy import Column, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class Notice(Base):
    """Model for notice table in chatbot schema

    Example:
    {
        "id": 1,
        "type": "info",
        "icon": "https://seerbot.io/icon.png",
        "title": "Welcome",
        "message": "Welcome to SeerBot",
        "created_at": "2024-01-01T12:00:00",
        "updated_at": "2024-01-01T12:00:00",
        "meta_data": { "indicatorType": "signal", "token": "ADA"}
    }
    """

    __tablename__ = "notice"
    __table_args__ = {"schema": "chatbot"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Text, nullable=False, index=True)  # "info", "account", "signal"
    icon = Column(Text, nullable=True)  # Icon URL (e.g., "https://seerbot.io/icon.png")
    title = Column(Text, nullable=False)  # Notice title
    message = Column(Text, nullable=False)  # Notice message/content
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    meta_data = Column(
        JSONB, nullable=True
    )
