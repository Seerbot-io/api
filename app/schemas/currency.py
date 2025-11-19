from pydantic import BaseModel, field_validator
from app.schemas.my_base_model import CustormBaseModel


class Currency(CustormBaseModel):
    id: int = 0
    symbol: str = ''
    name:str = ''
    price:float = 0
    volume_24h:float = 0
    percent_change_24h:float = 0
    market_cap:float = 0

    @field_validator("price")
    def round_8(cls, v: float) -> float:
        return round(v, 8)

    @field_validator("volume_24h" ,"percent_change_24h", "market_cap")
    def round_2(cls, v:float) -> float:
        return round(v, 2)

