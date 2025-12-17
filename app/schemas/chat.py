from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field

from app.schemas.my_base_model import CustormBaseModel


class ChatMessage(CustormBaseModel):
    """Chat message schema matching the AI SDK Message type"""

    model_config = ConfigDict(
        populate_by_name=True, json_encoders={datetime: lambda v: v.isoformat()}
    )

    id: str = ""
    content: str = ""
    role: str = ""  # 'user', 'assistant', 'system', 'tool'
    created_at: datetime = Field(alias="createdAt")
    tool_invocations: Optional[Dict[str, Any]] = Field(
        default=None, alias="toolInvocations"
    )

    # @field_validator("id")
    # def validate(cls, v: str) -> str:
    #     return v


class SaveChatRequest(CustormBaseModel):
    """Request model for saving chat messages - matches TypeScript saveChat input"""

    wallet_address: str = Field(default="", alias="walletAddress")
    messages: List[ChatMessage]
