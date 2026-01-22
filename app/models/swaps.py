from sqlalchemy import BigInteger, Column, Float, String

from app.db.base import Base


class Swap(Base):
    """Model for swaps table in proddb schema
    Example:
    {
        "transaction_id": "4c6ff99c8328...c8d053659",
        "wallet_address": "addr1qxy99g3k...useraddress",
        "from_token": "USDM",
        "to_token": "ADA",
        "from_amount": 0.1,
        "to_amount": 5000.00,
        "price": 50000.00,
        "value_ada": 0.1,
        "timestamp": 1697123456,
        "extend_data": {
            "order_tx_id": "ab79c2bdc3890c1...767a43a1a68f3",
            "execution_tx_id": "4c6ff99c83285...22c8d053659"
        },
        "status": "completed",
    }
    """

    __tablename__ = "swap_transactions"
    __table_args__ = {"schema": "proddb"}  # change to 'proddb' in production

    transaction_id = Column(String(255), primary_key=True)
    wallet_address = Column(String(255))
    from_token = Column(String(255))
    to_token = Column(String(255))
    from_amount = Column(Float)
    to_amount = Column(Float)
    price = Column(Float)
    value_ada = Column(Float)
    timestamp = Column(BigInteger, nullable=False)
    fee = Column(Float)
    price_ada = Column(Float)
    extend_data = Column(String(255))
    status = Column(String(50), default="pending")  # 'pending', 'completed', 'failed'

    def __init__(self, **kwargs):
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        super().__init__(**kwargs)
