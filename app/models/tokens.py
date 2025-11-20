from sqlalchemy import Column, String
from app.db.base import Base


class Token(Base):
    """Model for tokens table in proddb schema
    Example:
    {
		"id" : "a0028f350aaabe0545fd...",
		"name" : "HOSKY Token",
		"policy_id" : "a0028f350aaabe0545...",
		"asset_name" : "484f534b59",
		"symbol" : "HOSKY"
	}
    """
    __tablename__ = "tokens"
    __table_args__ = {"schema": "proddb"}

    id = Column(String(255), primary_key=True)
    name = Column(String(255))
    symbol = Column(String(255))
    policy_id = Column(String(255))
    asset_name = Column(String(255))

