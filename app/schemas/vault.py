from typing import List, Literal, Optional

from pydantic import Field, field_validator

from app.core.config import settings
from app.schemas.my_base_model import CustomBaseModel


class VaultListItem(CustomBaseModel):
    """Vault list item for /vaults/{status} endpoint"""

    id: str = ""  # uuid
    state: str = ""  # open, trading, withdrawable, closed
    icon_url: Optional[str] = None
    vault_name: str = ""
    summary: Optional[str] = None
    address: str = ""
    pool_id: str = ""
    annual_return: float = 0.0
    tvl_usd: float = 0.0
    max_drawdown: float = 0.0
    start_time: Optional[int] = None


class VaultListResponse(CustomBaseModel):
    """Response model for vault list"""

    vaults: List[VaultListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


class VaultInfo(CustomBaseModel):
    """Vault info for /vaults/{id}/info endpoint"""

    id: str = ""  # uuid
    state: str = ""  # open, trading, withdrawable, closed
    icon_url: Optional[str] = None
    vault_name: str = ""
    vault_type: str = "Seerbot Vault"
    vault_type_logo: str = settings.HOST + "/static/images/Seerbot.png"
    blockchain: str = "Cardano"
    blockchain_logo: str = settings.HOST + "/static/images/Cardano_icon.png"
    address: str = ""
    pool_id: str = ""
    summary: Optional[str] = None
    annual_return: float = 0.0
    tvl_usd: float = 0.0
    max_drawdown: float = 0.0
    start_time: Optional[int] = None
    trade_per_month: float = 0.0  # Average transactions per month f:.2
    decision_cycle: Optional[str] = None  # Decision cycle from trade strategy
    description: Optional[str] = None  # HTML text


class VaultValuesResponse(CustomBaseModel):
    """Vault values response for /vaults/{id}/values endpoint (TradingView format)"""

    s: str = "ok"  # Status code: ok, error, or no_data
    t: List[int] = Field(
        default_factory=list
    )  # Array of bar timestamps (Unix timestamp UTC)
    c: List[float] = Field(default_factory=list)  # Closing price


class VaultStats(CustomBaseModel):
    """Vault statistics for /vaults/{id}/stats endpoint"""

    state: str = ""  # open, trading, withdrawable, closed
    tvl_usd: float = 0.0
    max_drawdown: float = 0.0
    trade_start_time: Optional[int] = None
    trade_end_time: Optional[int] = None
    start_value: float = 0.0
    current_value: float = 0.0
    return_percent: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_profit_per_winning_trade_pct: float = 0.0
    avg_loss_per_losing_trade_pct: float = 0.0
    total_fees_paid: float = 0.0
    decision_cycle: Optional[str] = None  # Decision cycle from trade strategy
    trade_per_month: float = 0.0  # Average transactions per month f:.2

    @field_validator("trade_per_month")
    def round_fields(cls, v: float) -> float:
        return round(v, 2)


class VaultPosition(CustomBaseModel):
    """Vault position for /vaults/{id}/positions endpoint"""

    pair: str = ""  # e.g., "ADA/USDM"
    spend: float = 0.0  # spend amount
    value: float = 0.0  # current value (return_amount if closed, estimated from current prices if open)
    open_time: int = 0  # position start_time
    close_time: Optional[int] = None  # position close_time
    status: str = ""  # "open" or "closed"
    profit: float = 0.0  # profit percentage: (value - spend) / spend * 100

    @field_validator("spend", "value", "profit")
    def round_fields(cls, v: float) -> float:
        return round(v, 2)


class VaultPositionsResponse(CustomBaseModel):
    """Response model for vault positions list"""

    total: int = 0
    page: int = 1
    limit: int = 20
    positions: List[VaultPosition] = Field(default_factory=list)


class VaultWithdrawRequest(CustomBaseModel):
    """Request body for `POST /vaults/withdraw`."""

    vault_id: str
    wallet_address: str
    # amount_ada: Optional[float] = None


class VaultWithdrawResponse(CustomBaseModel):
    """Response for vault withdraw attempt."""

    status: Literal["ok", "invalid"]
    tx_id: Optional[str] = None
    message: Optional[str] = None


class VaultContributeResponse(CustomBaseModel):
    """User earning info for a specific vault"""

    total_deposit: float = 0.0
    total_withdrawal: float = 0.0
    profit_rate: float = 0.0
    is_redeemed: bool = False
