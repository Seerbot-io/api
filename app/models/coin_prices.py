from sqlalchemy import BigInteger, Column, Float, String

from app.db.base import Base


class CoinPrice(Base):
    """Model for coin_prices table (default schema)
    Example:
    {
        "update_time": 1763451898,
        "close_time": 1763415600,
        "symbol": "USDM/ADA",
        "open": 2.21714584594061,
        "high": 2.24268527493512,
        "low": 2.21714584594061,
        "close": 2.24268527493512,
        "volume": 11858.201102,
        "open_time": 1763415300
    }
    """

    update_time = Column(BigInteger)
    close_time = Column(BigInteger)
    symbol = Column(String(225))
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    open_time = Column(BigInteger)


class CoinPrice5m(CoinPrice):
    """Model for coin_prices_5m table in proddb schema"""

    __tablename__ = "coin_prices_5m"


class CoinPrice1h(CoinPrice):
    """Model for coin_prices_1h table in proddb schema"""

    __tablename__ = "coin_prices_1h"
