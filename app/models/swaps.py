from sqlalchemy import Column, String, BigInteger, Float, Integer
from app.db.base import Base


class Swap(Base):
    """Model for swaps table in proddb schema
    Example:
    {
        "transaction_id": "998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb",
        "user_id": "addr1qxy99g3k...useraddress",
        "from_token": "USDM",
        "to_token": "ADA",
        "from_amount": 0.1,
        "to_amount": 5000.00,
        "price": 50000.00,
        "timestamp": 1697123456,
        "status": "completed",
    }
    """
    __tablename__ = "swap_transactions"
    __table_args__ = {"schema": "proddb"}

    transaction_id = Column(String(255), primary_key=True)
    user_id = Column(String(255), nullable=False)
    from_token = Column(String(255), nullable=False)
    to_token = Column(String(255), nullable=False)
    from_amount = Column(Float, nullable=False)
    to_amount = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    value = Column(Float, nullable=False)
    timestamp = Column(BigInteger, nullable=False)
    status = Column(String(50), default='pending', nullable=False)  # 'pending', 'completed', 'failed'

