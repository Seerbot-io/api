from typing import List, Optional

from pydantic import Field

from app.schemas.my_base_model import CustomBaseModel


class VaultListItem(CustomBaseModel):
    """Vault list item for /vaults/{status} endpoint"""
    id: str = ""  # uuid
    state: str = ""  # accepting_deposits, trading, settled, closed
    icon_url: Optional[str] = None
    vault_name: str = ""
    summary: Optional[str] = None
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

    icon_url: Optional[str] = None
    vault_name: str = ""
    vault_type: str = "seerbot_vault_v1"
    blockchain: str = "cardano"
    address: str = ""
    summary: Optional[str] = None
    description: Optional[str] = None  # HTML text


class VaultValuesResponse(CustomBaseModel):
    """Vault values response for /vaults/{id}/values endpoint (TradingView format)"""

    s: str = "ok"  # Status code: ok, error, or no_data
    t: List[int] = Field(default_factory=list)  # Array of bar timestamps (Unix timestamp UTC)
    c: List[float] = Field(default_factory=list)  # Closing price


class VaultStats(CustomBaseModel):
    """Vault statistics for /vaults/{id}/stats endpoint"""

    state: str = ""  # accepting_deposits, trading, settled, closed
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
    avg_trade_duration: float = 0.0
    total_fees_paid: float = 0.0


class VaultPosition(CustomBaseModel):
    """Vault position for /vaults/{id}/positions endpoint"""

    pair: str = ""  # e.g., "ADA/USDM"
    direction: str = ""  # buy | sell
    return_percent: float = 0.0
    status: str = ""  # open | closed
    spend_amount: float = 0.0
    value_usd: float = 0.0
    open_price: float = 0.0
    close_price: Optional[float] = None
    start_time: int = 0
    update_time: int = 0
    open_order_txn: str = ""
    close_order_txn: Optional[str] = None


class VaultPositionsResponse(CustomBaseModel):
    """Response model for vault positions list"""

    total: int = 0
    page: int = 1
    limit: int = 20
    positions: List[VaultPosition] = Field(default_factory=list)
