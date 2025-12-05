from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import Field, ConfigDict
from app.schemas.my_base_model import CustormBaseModel


class ChatMessage(CustormBaseModel):
    """Chat message schema matching the AI SDK Message type"""
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    id: str
    content: str
    role: str  # 'user', 'assistant', 'system', 'tool'
    created_at: datetime = Field(alias="created_at")
    tool_invocations: Optional[Dict[str, Any]] = Field(default=None, alias="tool_invocations")


class SaveChatRequest(CustormBaseModel):
    """Request model for saving chat messages - matches TypeScript saveChat input"""
    wallet_address: str
    messages: List[ChatMessage]

