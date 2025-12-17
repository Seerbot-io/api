from sqlalchemy import Column, Float, Integer, String

from app.db.base import Base


class Token(Base):
    """Model for tokens table in proddb schema
    Example:
    {
                "id" : "a0028f350aaabe0545fd...",
                "name" : "HOSKY Token",
                "policy_id" : "a0028f350aaabe0545...",
                "asset_name" : "484f534b59",
                "symbol" : "HOSKY",
    "logo_url" : "https://asset-logos.org/images/assets/fe7c786ab321f41c654ef6c1af7b3250a613c24e4213e0425a7ae45655534441",
    "decimals" : 8,
    "total_supply" : 1000000
        }
    """

    __tablename__ = "tokens"
    __table_args__ = {"schema": "proddb"}

    id = Column(String(255), primary_key=True)
    name = Column(String(255))
    symbol = Column(String(255))
    policy_id = Column(String(255))
    asset_name = Column(String(255))
    logo_url = Column(String(255))
    decimals = Column(Integer, default=18)
    total_supply = Column(Float, default=0)
