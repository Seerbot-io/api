from sqlalchemy import Column, String
from app.db.base import Base


class Pool(Base):
    """Model for pools table in proddb schema
    Example:
	{
		"id" : "f5808c2c990d86da54bfc...",
		"name" : "ADA-USDM LP-V2",
		"pair" : "USDM/ADA",
		"policy_id" : "f5808c2c990d86da...",
		"asset_name" : "7dd6988c5a86693..."
	}
    """
    __tablename__ = "pools"
    __table_args__ = {"schema": "proddb"}

    id = Column(String(255), primary_key=True)
    name = Column(String(255))
    pair = Column(String(255))  # ADA-USDM in ada, out usdm
    policy_id = Column(String(255))
    asset_name = Column(String(255))

