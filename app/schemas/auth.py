from pydantic import BaseModel, Field

from app.schemas.my_base_model import CustomBaseModel


class NonceRequest(BaseModel):
    """Request model for nonce generation - input validation"""

    address: str = Field(..., description="Wallet address")


class NonceResponse(CustomBaseModel):
    """Response model for nonce generation - output"""

    nonce: str = ""


class VerifyRequest(BaseModel):
    """Request model for wallet verification - input validation"""

    address: str = Field(..., description="Wallet address")
    nonce: str = Field(..., description="Nonce to verify")
    signature: str = Field(..., description="Signature of the nonce")
    key: str = Field(..., description="Public key")


class AuthResponse(CustomBaseModel):
    """Response model for authentication - output"""

    access_token: str
    token_type: str = "bearer"
    wallet_address: str
