from pydantic import BaseModel, field_validator, Field
from app.schemas.my_base_model import CustormBaseModel
from typing import Union, List, Optional

class Prediction(CustormBaseModel):
    symbol: str = ''
    date: str = ''
    price: float = 0
    prediction: float = 0
    price_change: float = 0

    @field_validator("price")
    def round_price(cls, v:float) -> float:
        return round(v, 6)
    
    @field_validator("prediction")
    def round_prediction(cls, v:float) -> float:
        return round(v, 6)

    @field_validator("price_change")
    def round_pc(cls, v: float) -> float:
        return round(v, 6)
    
class PredictionV2(CustormBaseModel):
    symbol: str = ''
    update_time: str = ''
    target_time: str = ''
    price: float = 0
    prediction: float = 0
    price_change: float = 0

    @field_validator("price")
    def round_price(cls, v:float) -> float:
        return round(v, 6)
    
    @field_validator("prediction")
    def round_prediction(cls, v:float) -> float:
        return round(v, 6)

    @field_validator("price_change")
    def round_pc(cls, v: float) -> float:
        return round(v, 6)

class Validate(CustormBaseModel):
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
    def round_mae(cls, v:float) -> float:
        return round(v, 8)
    
    @field_validator("avg_err_rate", "max_profit_rate", "max_loss_rate", "avg_profit_rate", "accuracy")
    def round_err_rate(cls, v:float) -> float:
        return round(v, 4)

class BackTest(CustormBaseModel):
    symbol: str = ''
    open_time: str = ''
    close_time: str = ''
    close_predict: float = 0
    open: float = 0
    close: float = 0
    high: float = 0
    low: float = 0

    @field_validator("open", "close", "high", "low", "close_predict")
    def round_value(cls, v:float) -> float:
        return round(v, 6)
    

class BackTestV2(CustormBaseModel):
    open_time: str = ''
    close_time: str = ''
    close_predict: Union[float, str] = 'null'
    open: float = 0
    close: float = 0
    high: float = 0
    low: float = 0
    pred_trend: str = 'flat'
    trend: str = 'flat'

    @field_validator("open", "close", "high", "low")
    def round_value(cls, v:float) -> float:
        return round(v, 6)

class IndicatorData(CustormBaseModel):
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

    @field_validator("open", "high", "low", "close", "volume", "rsi7", "rsi14", "adx14", "psar")
    def round_value(cls, v:float) -> float:
        return round(v, 6)

class IndicatorsResponse(CustormBaseModel):
    pair: str = ''
    timeframe: str = ''
    data: List[IndicatorData] = []

class Token(CustormBaseModel):
    id: str = ''
    name: str = ''
    symbol: str = ''
    logo_url: str = ''

class TokenList(CustormBaseModel):
    total: int = 0
    page: int = 1
    tokens: List[Token] = []


class TokenMarketInfo(CustormBaseModel):
    id: str = ''
    name: str = ''
    symbol: str = ''
    logo_url: str = ''
    price: float = 0.0
    change_24h: float = 0.0  # change_24h
    low_24h: float = 0.0  # low_24h
    high_24h: float = 0.0  # high_24h
    volume_24h: float = 0.0  # volume_24h

    @field_validator("price", "change_24h", "low_24h", "high_24h", "volume_24h")
    def round_value(cls, v: float) -> float:
        return round(v, 6)
        
class SwapCreate(BaseModel):
    transaction_id: str = Field(..., description="On chain transaction ID")
    from_token: str = Field(..., description="Source token symbol")
    to_token: str = Field(..., description="Destination token symbol")
    from_amount: float = Field(..., description="Amount of source token", gt=0)
    to_amount: float = Field(..., description="Amount of destination token", gt=0)
    price: float = Field(..., description="Exchange rate", gt=0)
    timestamp: Optional[int] = Field(None, description="Transaction timestamp in seconds (optional)")

    @field_validator("from_amount", "to_amount", "price")
    def round_value(cls, v: float) -> float:
        return round(v, 6)

class SwapResponse(CustormBaseModel):
    transaction_id: str = ''
    status: str = 'pending'  # 'pending', 'completed', 'failed'

class SwapTransaction(CustormBaseModel):
    transaction_id: str = ''
    from_token: str = ''
    from_amount: float = 0.0
    to_token: str = ''
    to_amount: float = 0.0
    price: float = 0.0
    timestamp: int = 0
    status: str = 'pending'

    @field_validator("from_amount", "to_amount", "price")
    def round_value(cls, v: float) -> float:
        return round(v, 6)

class SwapListResponse(CustormBaseModel):
    transactions: List[SwapTransaction] = []
    total: int = 0
    page: int = 1
    limit: int = 20

class Trader(CustormBaseModel):
    user_id: str = ''
    total_volume: float = 0.0
    total_trades: int = 0
    rank: int = 0

    @field_validator("total_volume")
    def round_value(cls, v: float) -> float:
        return round(v, 2)

class TraderList(CustormBaseModel):
    total: int = 0
    page: int = 1
    traders: List[Trader] = []

class TrendPair(CustormBaseModel):
    """Trend data for a single trading pair"""
    pair: str = ''
    confidence: float = 0.0  # 0-100
    price: float = 0.0
    change_24h: float = 0.0
    volume_24h: float = 0.0

    @field_validator("confidence")
    def round_confidence(cls, v: float) -> float:
        return round(v, 2)

    @field_validator("price", "change_24h", "volume_24h")
    def round_value(cls, v: float) -> float:
        return round(v, 6)

class TrendResponse(CustormBaseModel):
    """Response containing all pairs grouped by trend"""
    uptrend: List[TrendPair] = Field(default_factory=list)
    downtrend: List[TrendPair] = Field(default_factory=list)
        