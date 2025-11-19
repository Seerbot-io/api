from pydantic import BaseModel, field_validator
from app.schemas.my_base_model import CustormBaseModel
from typing import List


class OriSymbol(CustormBaseModel):
    symbol: str = ''
    discoveredOn: str = ''


class RefSymbol(CustormBaseModel):
    originalSymbol: str = ''
    originalStartDate: str = ''
    originalEndDate: str = ''
    originalPrices: List[float] = ['']
    originalFibonacci: List[float] = ['']
    similarSymbols: List[str] = ['']
    similarStartDates: List[str] = ['']
    similarEndDates: List[str] = ['']
    similarPrices: List[List[float]] = [[0]]
    similarFibonacci: List[List[float]] = [[0]]


class HeatMap(CustormBaseModel):
    symbol: str = ''
    rsi: float = 0
    close: float = 0
    high: float = 0
    low: float = 0
    dateCreated: str = ''
 
    @field_validator("rsi")
    def round_rsi(cls, v:float) -> float:
        return round(v, 2)

    @field_validator("close", "high", "low")
    def round_price(cls, v:float) -> float:
        return round(v, 9)

class RSIHeatMap(CustormBaseModel):
    symbol: str = ''
    rsi: float = 0
    close: float = 0
    high: float = 0
    low: float = 0
    rsi_bottom: float = 0
    rsi_top: float = 0
    dateCreated: str = ''
 
    @field_validator("rsi")
    def round_rsi(cls, v:float) -> float:
        return round(v, 2)

    @field_validator("close", "high", "low")
    def round_price(cls, v:float) -> float:
        return round(v, 9)

class ChartData(CustormBaseModel):
    symbol: str = ''
    rsi: float = 0
    percentage_change: float = 0

    @field_validator("rsi", "percentage_change")
    def round_value(cls, v: float) -> float:
        return round(v, 2)
    

class PredictedTrend(CustormBaseModel):
    open_time: int 
    symbol: str = ''
    predicted_trend: str = ''    


class Candle(CustormBaseModel):
    time: int = 0
    open: float = 0
    close: float = 0
    high: float = 0
    low: float = 0

    @field_validator("time")
    def convert_time(cls, v:any) -> int:
        return int(v)

    @field_validator("open", "close", "high", "low")
    def round_price(cls, v:float) -> float:
        return round(v, 9)

class CandleADX(Candle):
    volume: float = 0
    adx: float = 0
    predicted_trend: str = ''

    @field_validator("adx")
    def round_adx(cls, v:float) -> float:
        return round(v, 2)

class CandlePSAR(Candle):
    volume: float = 0
    psar: float = 0
    predicted_trend: str = ''

    @field_validator("psar")
    def round_psar(cls, v:float) -> float:
        return round(v, 9)

class TradeReport(CustormBaseModel):
    pair: str = ''
    revalue: float = 0
    total_volumn: float = 0
    num_order: int = 0
    roi:float = 0
    win_rate: float  


class ValIndicator(CustormBaseModel):
    indicator: str = ''
    revalue: float = 0
    total_volumn: float = 0
    num_order: int = 0
    roi:float = 0
    win_rate: float  

class ValDetail(CustormBaseModel):
    pair: str = ''
    indicators: List[ValIndicator] = []
