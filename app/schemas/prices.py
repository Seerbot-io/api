from typing import List
from pydantic import BaseModel, field_validator
from app.schemas.my_base_model import CustormBaseModel

class LatestPrice(CustormBaseModel):
    coin: str = ''
    price: float = 0
    price_change: float = 0

    @field_validator("price")
    def round_price(cls, v:float) -> float:
        return round(v, 6)

    @field_validator("price_change")
    def round_pc(cls, v: float) -> float:
        return round(v, 2)


class LatestPriceV2(CustormBaseModel):
    coin: str = ''
    time: str = ''
    price: float = 0
    price_change: float = 0
    price_change_percent: float = 0

    @field_validator("price", "price_change")
    def round_price(cls, v:float) -> float:
        return round(v, 6)

    @field_validator("price_change_percent")
    def round_pc(cls, v: float) -> float:
        return round(v, 2)


class Prices(CustormBaseModel):
    price: float = 0
    time: int = 0
    
class CoinPrice(CustormBaseModel):
    symbol: str = ''
    price: float = 0
    price_change: float = 0
    list_prices: List[float] = [0]

    @field_validator("price_change")
    def round_pc(cls, v: float) -> float:
        return round(v, 2)
    
class Indicators(CustormBaseModel):
    timestamp: int = 0
    open: float = 0
    high: float = 0
    low: float = 0
    close: float = 0
    volume: float = 0
    trades: int = 0
    trend1: str = 0
    trend3: str = 0
    trend7: str = 0
    trend14: str = 0
    rsi7: float = 0
    rsi14: float = 0
    rsi7_epl: int = 0
    rsi7_eph: int = 0
    rsi14_epl: int = 0
    rsi14_eph: int = 0
    adx: float = 0
    adx_ep: int = 0
    di_cross: int = 0
    psar: float = 0
    psar_trend: str = 0