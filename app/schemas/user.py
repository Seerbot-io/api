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


class VaultHolding(CustomBaseModel):
    """Vault holding information"""

    token_pair: str = ""
    deposit_token: str = ""  # Token deposited into vault
    base_token: str = ""  # Deprecated, use deposit_token
    amount: Optional[float] = None  # For single token holdings
    value_usd: float = 0.0
    apy: Optional[float] = None
    return_percentage: Optional[float] = None
    logo_url: Optional[str] = None  # For single token holdings


class VaultHoldingsResponse(CustomBaseModel):
    """Response model for vault holdings"""

    holdings: List[VaultHolding] = []
    total: int = 0
    page: int = 1
    limit: int = 20


class VaultSummaryResponse(CustomBaseModel):
    """Response model for vault summary"""

    total_value_usd: float = 0.0
    total_holdings: int = 0
    total_apy: Optional[float] = None
    total_return_24h: Optional[float] = None
    total_return_percentage: Optional[float] = None


class TokenInfo(CustomBaseModel):
    """Token information for swap response"""

    symbol: str = ""
    name: str = ""
    decimals: int = 0
    address: str = ""
    logo_url: Optional[str] = None


class SwapToken(CustomBaseModel):
    """Token information with amount for swap"""

    tokenInfo: TokenInfo = Field(default_factory=TokenInfo)
    amount: str = "0"


class UserSwap(CustomBaseModel):
    """User swap transaction data"""

    fromToken: SwapToken = Field(default_factory=SwapToken)
    toToken: SwapToken = Field(default_factory=SwapToken)
    txn: str = ""
    timestamp: int = 0


class UserSwapListResponse(CustomBaseModel):
    """Response model for user swaps list"""

    data: List[UserSwap] = Field(default_factory=list)
    total: int = 0
    page: int = 1


# ============================================
# Vault-related Schemas
# ============================================


class Vault(CustomBaseModel):
    """Vault information"""

    id: int = 0
    name: str = ""
    algorithm: str = ""
    address: str = ""
    token_id: str = ""
    total_fund: float = 0.0
    run_time: int = 0
    stop_time: Optional[int] = None
    status: str = "active"
    description: Optional[str] = None
    token_symbol: Optional[str] = None
    token_name: Optional[str] = None
    token_logo_url: Optional[str] = None


class VaultListResponse(CustomBaseModel):
    """Response model for vault list"""

    vaults: List[Vault] = Field(default_factory=list)
    total: int = 0


class VaultState(CustomBaseModel):
    """Vault state at a point in time"""

    timestamp: int = 0
    total_value: float = 0.0
    total_value_ada: float = 0.0


class VaultStateResponse(CustomBaseModel):
    """Response model for vault state history"""

    vault_id: int = 0
    vault_name: str = ""
    states: List[VaultState] = Field(default_factory=list)
    total: int = 0


class VaultTransaction(CustomBaseModel):
    """Vault transaction entry"""

    id: int = 0
    vault_id: int = 0
    vault_name: Optional[str] = None
    wallet_address: str = ""
    action: str = ""  # 'deposit', 'withdrawal', 'claim', 'reinvest'
    amount: float = 0.0
    token_id: str = ""
    token_symbol: Optional[str] = None
    txn: str = ""
    timestamp: int = 0
    status: str = "pending"
    fee: float = 0.0


class VaultTransactionListResponse(CustomBaseModel):
    """Response model for vault transactions list"""

    transactions: List[VaultTransaction] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


class UserEarning(CustomBaseModel):
    """User earnings for a vault"""

    vault_id: int = 0
    vault_name: str = ""
    algorithm: str = ""
    vault_address: str = ""
    token_id: str = ""
    token_symbol: Optional[str] = None
    total_deposit: float = 0.0
    total_withdrawal: float = 0.0
    current_value: float = 0.0
    earnings: float = 0.0  # Calculated: current_value + total_withdrawal - total_deposit
    last_updated_timestamp: int = 0


class UserEarningsResponse(CustomBaseModel):
    """Response model for user earnings"""

    earnings: List[UserEarning] = Field(default_factory=list)
    total: int = 0
    total_deposit: float = 0.0
    total_withdrawal: float = 0.0
    total_current_value: float = 0.0
    total_earnings: float = 0.0
