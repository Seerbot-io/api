import re
from pydantic import BaseModel, field_validator
from app.schemas.my_base_model import CustormBaseModel
from typing import Union

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
    