from sqlalchemy import BigInteger, Column, String

from app.db.base import Base


class AuthNonce(Base):
    """Model for storing wallet authentication nonces."""

    __tablename__ = "auth_nonce"
    __table_args__ = {"schema": "proddb"}

    nonce = Column(String(128), primary_key=True)
    address = Column(String(255), nullable=False)
    created_at = Column(BigInteger, nullable=False)
    expires_at = Column(BigInteger, nullable=False)


class WalletUser(Base):
    """Optional wallet user record."""

    __tablename__ = "wallet_users"
    __table_args__ = {"schema": "proddb"}

    wallet_address = Column(String(255), primary_key=True)
    created_at = Column(BigInteger, nullable=False)
    last_login = Column(BigInteger, nullable=False)

