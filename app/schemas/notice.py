from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field, field_validator

from app.schemas.my_base_model import CustomBaseModel


class NoticeCreate(CustomBaseModel):
    """Request model for creating notices - used internally by create_notice() function"""

    type: str = Field(..., description="Notice type: 'info', 'account', or 'signal'")
    icon: Optional[str] = Field(
        None, description="Optional icon URL (e.g., 'https://seerbot.io/icon.png')"
    )
    title: str = Field(..., description="Notice title")
    message: str = Field(..., description="Notice message/content")
    meta_data: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata (indicatorType, token, etc.)"
    )

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate that type is one of the allowed values"""
        allowed_types = ["info", "account", "signal"]
        if v not in allowed_types:
            raise ValueError(f"type must be one of {allowed_types}")
        return v


class NoticeResponse(CustomBaseModel):
    """Response model for a single notice"""

    model_config = ConfigDict(
        populate_by_name=True, json_encoders={datetime: lambda v: v.isoformat()}
    )

    id: int = 0
    type: str = ""
    icon: Optional[str] = None
    title: str = ""
    message: str = ""
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    meta_data: Optional[Dict[str, Any]] = None


class NoticeListResponse(CustomBaseModel):
    """Response model for a list of notices with pagination"""

    notices: List[NoticeResponse] = []
    total: int = 0
    limit: int = 10
    offset: int = 0
