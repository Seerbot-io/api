"""
handle notice from other service and save to db
table: chatbot.notice
columns:
    id: int
    type: str (info, account, signal)
    icon: str (optional, icon URL)
    title: str (required)
    message: str (required)
    created_at: datetime
    updated_at: datetime
    meta_data: json (optional: indicatorType, token, ...)

"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.notice import Notice


def create_notice(
    db: Session,
    type: str,
    title: str,
    message: str,
    icon: Optional[str] = None,
    meta_data: Optional[Dict[str, Any]] = None,
) -> Notice:
    """
    Create a new notice and save it to the database.

    This is an internal function that can be called by other services/modules.
    It validates the input and creates a notice record in the database.
    All notices are global and sent to all users.

    Args:
        db: SQLAlchemy database session
        type: Notice type - must be "info", "account", or "signal"
        title: Notice title (required)
        message: Notice message/content (required)
        icon: Optional icon URL (e.g., "https://seerbot.io/icon.png")
        meta_data: Optional dictionary containing metadata (indicatorType, token, etc.)

    Returns:
        The created Notice object

    Raises:
        ValueError: If validation fails (invalid type)
    """
    # Validate type
    allowed_types = ["info", "account", "signal"]
    if type not in allowed_types:
        raise ValueError(f"type must be one of {allowed_types}, got: {type}")

    # Create notice object - all notices are global
    notice = Notice(
        type=type,
        icon=icon,
        title=title,
        message=message,
        meta_data=meta_data,
    )

    # Save to database
    db.add(notice)
    db.commit()
    db.refresh(notice)

    return notice
