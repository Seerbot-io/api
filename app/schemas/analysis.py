from typing import List, Optional, Union

from pydantic import Field, field_validator

from app.schemas.my_base_model import CustomBaseModel


class Prediction(CustomBaseModel):
    icon: str = ""
    pair: str = ""
    # update_time: str = ""
    # target_time: str = ""
    current_price: float = 0
    predict_price: float = 0
    change_rate: float = 0

    @field_validator("change_rate")
    def round_pc(cls, v: float) -> float:
        return round(v, 6)


class Validate(CustomBaseModel):
    mae: float = 0
    avg_err_rate: float = 0
    max_profit_rate: float = 0
    max_loss_rate: float = 0
    avg_profit_rate: float = 0
    accuracy: float = 0
    n_trade: int = 0
    true_pred: int = 0
    false_pred: int = 0

    @field_validator("mae")
    def round_mae(cls, v: float) -> float:
        return round(v, 8)

    @field_validator(
        "avg_err_rate",
        "max_profit_rate",
        "max_loss_rate",
        "avg_profit_rate",
        "accuracy",
    )
    def round_err_rate(cls, v: float) -> float:
        return round(v, 4)


class BackTest(CustomBaseModel):
    symbol: str = ""
    open_time: str = ""
    close_time: str = ""
    close_predict: float = 0
    open: float = 0
    close: float = 0
    high: float = 0
    low: float = 0

    @field_validator("open", "close", "high", "low", "close_predict")
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class BackTestV2(CustomBaseModel):
    open_time: str = ""
    close_time: str = ""
    close_predict: Union[float, str] = "null"
    open: float = 0
    close: float = 0
    high: float = 0
    low: float = 0
    pred_trend: str = "flat"
    trend: str = "flat"

    @field_validator("open", "close", "high", "low")
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class IndicatorData(CustomBaseModel):
    timestamp: int = 0
    open: float = 0
    high: float = 0
    low: float = 0
    close: float = 0
    volume: float = 0
    rsi7: float = 0
    rsi14: float = 0
    adx14: float = 0
    psar: float = 0

    @field_validator(
        "open", "high", "low", "close", "volume", "rsi7", "rsi14", "adx14", "psar"
    )
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class IndicatorsResponse(CustomBaseModel):
    pair: str = ""
    timeframe: str = ""
    data: List[IndicatorData] = []


class Token(CustomBaseModel):
    id: str = ""
    name: str = ""
    symbol: str = ""
    logo_url: str = ""


class TokenMarketInfo(CustomBaseModel):
    id: str = ""
    name: str = ""
    symbol: str = ""
    logo_url: str = ""
    price: float = 0.0
    change_24h: float = 0.0  # change_24h
    low_24h: float = 0.0  # low_24h
    high_24h: float = 0.0  # high_24h
    volume_24h: float = 0.0  # volume_24h
    market_cap: float = 0.0  # market_cap

    @field_validator(
        "price", "change_24h", "low_24h", "high_24h", "volume_24h", "market_cap"
    )
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class TokenList(CustomBaseModel):
    total: int = 0
    page: int = 1
    tokens: List[TokenMarketInfo] = []


class SwapCreate(CustomBaseModel):
    order_tx_id: str = ""
    execution_tx_id: Optional[str] = None
    from_token: Optional[str] = None
    to_token: Optional[str] = None

    @field_validator("order_tx_id")
    def validate_tx_id(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("Transaction ID must be 64 characters long")
        return v


class MessageResponse(CustomBaseModel):
    message: str = "oke"


class SwapTransaction(CustomBaseModel):
    transaction_id: str = ""
    side: str = "unknown"
    pair: str = ""
    from_token: str = ""
    to_token: str = ""
    from_amount: float = 0.0
    to_amount: float = 0.0
    price: float = 0.0
    timestamp: int = 0
    status: str = "pending"

    @field_validator("from_amount", "to_amount", "price")
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class SwapListResponse(CustomBaseModel):
    transactions: List[SwapTransaction] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20


class Trader(CustomBaseModel):
    user_id: str = ""
    total_volume: float = 0.0
    total_trades: int = 0
    rank: int = 0

    @field_validator("total_volume")
    def round_value(cls, v: float) -> float:
        return round(v, 2)


class TraderList(CustomBaseModel):
    total: int = 0
    page: int = 1
    traders: List[Trader] = []


class TrendPair(CustomBaseModel):
    """Trend data for a single trading pair"""

    pair: str = ""
    confidence: float = 0.0  # 0-100
    price: float = 0.0
    change_24h: float = 0.0
    volume_24h: float = 0.0
    market_cap: float = 0.0
    logo_url: str = ""

    @field_validator("confidence")
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)

    @field_validator("price", "change_24h", "volume_24h", "market_cap")
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class TrendPair_V2(CustomBaseModel):
    """Trend data for a single trading pair"""

    pair: str = ""
    timestamp: int = 0
    confidence: float = 0.0  # 0-100
    price: float = 0.0
    change_24h: float = 0.0
    volume_24h: float = 0.0
    market_cap: float = 0.0
    logo_url: str = ""

    @field_validator("confidence")
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)

    @field_validator("price", "change_24h", "volume_24h", "market_cap")
    def round_value(cls, v: float) -> float:
        return round(v, 6)


class TrendResponse(CustomBaseModel):
    """Response containing all pairs grouped by trend"""

    uptrend: List[TrendPair_V2] = Field(default_factory=list)
    downtrend: List[TrendPair_V2] = Field(default_factory=list)


class SignalResponse(CustomBaseModel):
    indicator: str = ""  # rsi7, rsi14, adx14, psar
    signal: str = ""  # up, down
    data: List[TrendPair_V2] = Field(default_factory=list)
