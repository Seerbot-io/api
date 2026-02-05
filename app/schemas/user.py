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


class VaultEarning(CustomBaseModel):
    """Vault earning information"""

    vault_id: str = ""  # Changed from int to str (UUID)
    vault_name: str = ""
    vault_address: str = ""
    pool_id: str = ""
    total_deposit: float = 0.0
    current_value: float = 0.0
    roi: float = 0.0  # Return on Investment percentage


class VaultEarningsResponse(CustomBaseModel):
    """Response model for vault earnings"""

    earnings: List[VaultEarning] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


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

    id: str = ""  # Changed from int to str (UUID)
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


class VaultTransaction(CustomBaseModel):
    """Vault transaction entry"""

    id: str = ""  # Changed from int to str (UUID)
    vault_id: str = ""  # Changed from int to str (UUID)
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

    vault_id: str = ""  # Changed from int to str (UUID)
    vault_name: str = ""
    algorithm: str = ""
    vault_address: str = ""
    token_id: str = ""
    token_symbol: Optional[str] = None
    total_deposit: float = 0.0
    total_withdrawal: float = 0.0
    current_value: float = 0.0
    earnings: float = (
        0.0  # Calculated: current_value + total_withdrawal - total_deposit
    )
    last_updated_timestamp: int = 0


class UserEarningsResponse(CustomBaseModel):
    """Response model for user earnings"""

    earnings: List[UserEarning] = Field(default_factory=list)
    total: int = 0
    total_deposit: float = 0.0
    total_withdrawal: float = 0.0
    total_current_value: float = 0.0
    total_earnings: float = 0.0
