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
    createdAt: datetime = Field(alias="createdAt")
    toolInvocations: Optional[Dict[str, Any]] = Field(default=None, alias="toolInvocations")


class SaveChatRequest(CustormBaseModel):
    """Request model for saving chat messages - matches TypeScript saveChat input"""
    walletAddress: str = Field(default=None, alias="walletAddress")
    messages: List[ChatMessage]

