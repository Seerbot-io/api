from sqlalchemy import Column, String, Float, BigInteger, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func, text

from app.db.base import Base


class Vault(Base):
    """Model for vault table in proddb schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "USDM Vault",
        "algorithm": "RSI over bought over sold",
        "address": "addr1...",
        "token_id": "lovelace",
        "total_fund": 1000000.0,
        "run_time": 1697123456,
        "stop_time": null,
        "status": "active",
        "description": "USDM trading vault"
    }
    """

    __tablename__ = "vault"
    __table_args__ = {"schema": "proddb"}

    id = Column(
        UUID(as_uuid=False),  # Stores as string in Python
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()")
    )
    name = Column(String(255), nullable=False)
    algorithm = Column(String(255))
    address = Column(String(255))
    token_id = Column(String(255))
    total_fund = Column(Float, default=0.0)
    run_time = Column(BigInteger)
    stop_time = Column(BigInteger, nullable=True)
    status = Column(String(50), default="active")
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class VaultState(Base):
    """Model for vault_state table in proddb schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": 1697123456,
        "total_value": 1050000.0,
        "total_value_ada": 500000.0
    }
    """

    __tablename__ = "vault_state"
    __table_args__ = {"schema": "proddb"}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()")
    )
    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault.id"),
        nullable=False,
        index=True
    )
    timestamp = Column(BigInteger, nullable=False, index=True)
    total_value = Column(Float, nullable=False)
    total_value_ada = Column(Float, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class VaultLog(Base):
    """Model for vault_logs table in proddb schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "wallet_address": "addr1...",
        "action": "deposit",
        "amount": 1000.0,
        "token_id": "lovelace",
        "txn": "abc123...",
        "timestamp": 1697123456,
        "status": "completed",
        "fee": 2.5
    }
    """

    __tablename__ = "vault_logs"
    __table_args__ = {"schema": "proddb"}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()")
    )
    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault.id"),
        nullable=False,
        index=True
    )
    wallet_address = Column(String(255), nullable=False, index=True)
    action = Column(String(50), nullable=False)  # 'deposit', 'withdrawal', 'claim', 'reinvest'
    amount = Column(Float, nullable=False)
    token_id = Column(String(255))
    txn = Column(String(255))
    timestamp = Column(BigInteger, nullable=False)
    status = Column(String(50), default="pending")
    fee = Column(Float, default=0.0)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class UserEarning(Base):
    """Model for user_earnings table in proddb schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "wallet_address": "addr1...",
        "total_deposit": 10000.0,
        "total_withdrawal": 2000.0,
        "current_value": 9000.0,
        "last_updated_timestamp": 1697123456
    }
    """

    __tablename__ = "user_earnings"
    __table_args__ = {"schema": "proddb"}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()")
    )
    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault.id"),
        nullable=False,
        index=True
    )
    wallet_address = Column(String(255), nullable=False, index=True)
    total_deposit = Column(Float, default=0.0)
    total_withdrawal = Column(Float, default=0.0)
    current_value = Column(Float, default=0.0)
    last_updated_timestamp = Column(BigInteger)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
