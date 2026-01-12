from typing import List, Optional

from pydantic import Field

from app.schemas.my_base_model import CustomBaseModel


class TokenBalance(CustomBaseModel):
    """Token balance information"""

    token: str = ""
    amount: float = 0.0
    value_usd: float = 0.0
    logo_url: Optional[str] = None


class WalletBalanceResponse(CustomBaseModel):
    """Response model for wallet balance"""

    wallet_address: str = ""
    balances: List[TokenBalance] = []
    total_value_usd: float = 0.0


class ProfileResponse(CustomBaseModel):
    """Response model for user profile"""

    wallet_address: str = ""
    chain: str = "cardano"


class PortfolioHolding(CustomBaseModel):
    """Portfolio holding information"""

    token_pair: str = ""
    base_token: str = ""
    quote_token: Optional[str] = None
    base_amount: Optional[float] = None
    quote_amount: Optional[float] = None
    amount: Optional[float] = None  # For single token holdings
    value_usd: float = 0.0
    apy: Optional[float] = None
    return_percentage: Optional[float] = None
    base_logo_url: Optional[str] = None
    quote_logo_url: Optional[str] = None
    logo_url: Optional[str] = None  # For single token holdings


class PortfolioHoldingsResponse(CustomBaseModel):
    """Response model for portfolio holdings"""

    holdings: List[PortfolioHolding] = []
    total: int = 0
    page: int = 1
    limit: int = 20


class PortfolioSummaryResponse(CustomBaseModel):
    """Response model for portfolio summary"""

    total_value_usd: float = 0.0
    total_holdings: int = 0
    total_apy: Optional[float] = None
    total_return_24h: Optional[float] = None
    total_return_percentage: Optional[float] = None
