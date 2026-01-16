from sqlalchemy import Column, String, Float, BigInteger, Text, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
        "summary": "USDM trading vault"
        settled_time": 1697123456,
        "closed_time": 1697123456,
    }
    """

    __tablename__ = "vault"
    __table_args__ = {"schema": "proddb"}

    id = Column(
        UUID(as_uuid=False),  # Stores as string in Python
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()")
    )
    logo_url = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    algorithm = Column(String(255))
    address = Column(String(255))
    token_id = Column(String(255))
    total_fund = Column(Float, default=0.0)
    depositing_time = Column(BigInteger)
    trading_time = Column(BigInteger, nullable=True)
    status = Column(String(50), default="active")
    description = Column(Text, nullable=True)
    settled_time = Column(BigInteger, nullable=True)
    closed_time = Column(BigInteger, nullable=True)
    summary = Column(String(255), nullable=True)

class VaultTradePosition(Base):
    """Model for vault_trade_positions table in proddb schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "start_time": 1697123456,
        "update_time": 1697123500,
        "pair": "USDM/ADA",
        "spend": 1000.0,
        "return_amount": 1050.0,
        "quote_token_id": "lovelace",
        "base_token_id": "c48cbb3d5e57ed5...5553444d",
    }
    """

    __tablename__ = "vault_trade_positions"
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
    start_time = Column(BigInteger, nullable=False, index=True)
    update_time = Column(BigInteger, nullable=False)
    pair = Column(String(255), nullable=True)
    spend = Column(Float, nullable=True, default=0.0)
    return_amount = Column(Float, nullable=True, default=0.0)
    quote_token_id = Column(String(255), nullable=True)
    base_token_id = Column(String(255), nullable=True)


class VaultTrade(Base):
    """Model for vault_trades table in proddb schema
    Example:
    {
        "txn": "txn123...",
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "sender": "addr1...",
        "receiver": "addr2...",
        "from_token": "lovelace",
        "to_token": "a0028f350aaabe0545fd...",
        "from_amount": 1000.0,
        "to_amount": 500.0,
        "value_ada": 1000.0,
        "timestamp": 1697123456,
        "status": "completed",
        "price": 2.0,
        "extend_data": {"key": "value"},
        "fee": 2.5,
        "price_ada": 0.5
    }
    """

    __tablename__ = "vault_trades"
    __table_args__ = {"schema": "proddb"}

    txn = Column(String(255), primary_key=True)
    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault.id"),
        nullable=False,
        index=True
    )
    sender = Column(String(255), nullable=False)
    receiver = Column(String(255), nullable=False)
    from_token = Column(String(255), nullable=False)
    to_token = Column(String(255), nullable=False)
    from_amount = Column(Float, nullable=False)
    to_amount = Column(Float, nullable=False)
    value_ada = Column(Float, nullable=False)
    timestamp = Column(BigInteger, nullable=False, index=True)
    status = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    extend_data = Column(JSONB, nullable=True)
    fee = Column(Float, default=0.0)
    price_ada = Column(Float, nullable=False)
    


class PositionTrade(Base):
    """Model for position_trades table in proddb schema
    Junction table linking vault_trade_positions to vault_trades
    Example:
    {
        "position_id": "550e8400-e29b-41d4-a716-446655440000",
        "trade_id": "txn123...",
        "base_quantity": 100.0,
        "quote_quantity": -1000.0,
        "created_at": 1697123456
    }
    """

    __tablename__ = "position_trades"
    __table_args__ = {"schema": "proddb"}

    position_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault_trade_positions.id"),
        primary_key=True,
        nullable=False,
        index=True
    )
    trade_id = Column(
        String(255),
        ForeignKey("proddb.vault_trades.txn"),
        primary_key=True,
        nullable=False,
        index=True
    )
    base_quantity = Column(Float, nullable=False)
    quote_quantity = Column(Float, nullable=False)
    created_at = Column(BigInteger, nullable=False, index=True)


class TradeStrategy(Base):
    """Model for trade_strategies table in proddb schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "RSI Strategy",
        "description": "RSI over bought over sold",
        "decision_cycle": "1h",
        "quote_token_id": "lovelace",
        "base_token_id": "a0028f350aaabe0545fd...",
        "source_script": "function strategy() {...}"
    }
    """

    __tablename__ = "trade_strategies"
    __table_args__ = {"schema": "proddb"}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()")
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    decision_cycle = Column(String(50), nullable=False)
    quote_token_id = Column(String(255), nullable=False)
    base_token_id = Column(String(255), nullable=False)
    source_script = Column(Text, nullable=True)
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


class VaultBalanceSnapshot(Base):
    """Model for vault_balance_snapshots table in proddb schema
    (Renamed from vault_state)
    Example:
    {
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": 1697123456,
        "asset": {"token": "lovelace", "amount": 1000.0, "price_usd": 0.5},
        "total_value": 1050000.0,
        "total_value_usd": 525000.0
    }
    """

    __tablename__ = "vault_balance_snapshots"
    __table_args__ = {"schema": "proddb"}

    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault.id"),
        primary_key=True,
        nullable=False,
        index=True
    )
    timestamp = Column(BigInteger, primary_key=True, nullable=False, index=True)
    asset = Column(JSONB, nullable=False)  # JSON data about token amount, price in USD
    total_value = Column(Float, nullable=False)
    total_value_usd = Column(Float, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class VaultState(Base):
    """Model for vault_state table in proddb schema (recreated)
    Example:
    {
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "vault_address": "addr1...",
        "update_time": 1697123456,
        "state": "trading",
        "tvl_usd": 100000.0,
        "max_drawdown": 5.0,
        "trade_start_time": 1697123000,
        "start_value": 100000.0,
        "current_value": 105000.0,
        "trade_end_time": null,
        "return_percent": 5.0,
        "total_trades": 10,
        "winning_trades": 7,
        "losing_trades": 3,
        "win_rate": 70.0,
        "avg_profit_per_winning_trade_pct": 2.5,
        "avg_loss_per_losing_trade_pct": -1.0,
        "avg_trade_duration": 3600.0,
        "total_fees_paid": 50.0
    }
    """

    __tablename__ = "vault_state"
    __table_args__ = {"schema": "proddb"}

    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey("proddb.vault.id"),
        primary_key=True,
        nullable=False,
        index=True
    )
    vault_address = Column(String(255), nullable=False)
    update_time = Column(BigInteger, nullable=False, index=True)
    state = Column(String(50), nullable=False)  # accepting_deposits, trading, settled, closed
    tvl_usd = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    trade_start_time = Column(BigInteger, nullable=True)
    start_value = Column(Float, default=0.0)
    current_value = Column(Float, default=0.0)
    trade_end_time = Column(BigInteger, nullable=True)
    return_percent = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    avg_profit_per_winning_trade_pct = Column(Float, default=0.0)
    avg_loss_per_losing_trade_pct = Column(Float, default=0.0)
    avg_trade_duration = Column(Float, default=0.0)
    total_fees_paid = Column(Float, default=0.0)


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
