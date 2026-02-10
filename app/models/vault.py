from sqlalchemy import (
    Boolean,
    Column,
    String,
    Float,
    BigInteger,
    Text,
    ForeignKey,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text

from app.core.config import settings
from app.db.base import Base

SCHEMA = settings.SCHEMA_2

class Vault(Base):
    """Model for vault table in {SCHEMA} schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "USDM Vault",
        "algorithm": "RSI over bought over sold",
        "contract": "vault_v1",
        "address": "addr1...",
        "token_id": "lovelace",
        "total_fund": 1000000.0,
        "run_time": 1697123456,
        "stop_time": null,
        "status": "active",
        "summary": "USDM trading vault"
        "withdrawal_time": 1697123456,
        "closed_time": 1697123456,
    }
    """

    __tablename__ = "vault"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=False),  # Stores as string in Python
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()"),
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
    withdrawal_time = Column(BigInteger, nullable=True)
    closed_time = Column(BigInteger, nullable=True)
    summary = Column(String(255), nullable=True)
    pool_id = Column(String(255), nullable=True)  # "policy_id.asset_name" hex
    manager_pkh = Column(String(255), nullable=True)
    contract = Column(String(255), nullable=True)
    max_users = Column(Integer, default=50, nullable=True)
    post_money_val = Column(BigInteger, default=0, nullable=True)


class VaultPosition(Base):
    """Model for vault_positions table in {SCHEMA} schema
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

    __tablename__ = "vault_positions"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()"),
    )
    vault_id = Column(
        UUID(as_uuid=False), ForeignKey(f"{SCHEMA}.vault.id"), nullable=False, index=True
    )
    start_time = Column(BigInteger, nullable=False, index=True)
    update_time = Column(BigInteger, nullable=False)
    pair = Column(String(255), nullable=True)
    spend = Column(Float, nullable=True, default=0.0)
    current_asset = Column(Text, nullable=True, default="{}")
    return_amount = Column(Float, nullable=True, default=0.0)
    quote_token_id = Column(String(255), nullable=True)
    # base_token_id = Column(String(255), nullable=True)


class VaultPositionTxn(Base):
    """Model for vault_pos_txn table in {SCHEMA} schema
    Junction table linking vault_positions to vault_pos_txn
    Example:
    {
        "position_id": "550e8400-e29b-41d4-a716-446655440000",
        "trade_id": "txn123...",
        "base_quantity": 100.0,
        "quote_quantity": -1000.0,
        "created_at": 1697123456
    }
    """

    __tablename__ = "vault_pos_txn"
    __table_args__ = {"schema": SCHEMA}

    position_id = Column(
        UUID(as_uuid=False),
        ForeignKey(f"{SCHEMA}.vault_positions.id"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    trade_id = Column(
        String(255),
        ForeignKey(f"{SCHEMA}.swap_transactions.txn"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    base_quantity = Column(Float, nullable=False)
    quote_quantity = Column(Float, nullable=False)
    created_at = Column(BigInteger, nullable=False, index=True)


class TradeStrategy(Base):
    """Model for trade_strategies table in {SCHEMA} schema
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
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()"),
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    decision_cycle = Column(String(50), nullable=False)
    quote_token_id = Column(String(255), nullable=False)
    base_token_id = Column(String(255), nullable=False)
    source_script = Column(Text, nullable=True)


class VaultBalanceSnapshot(Base):
    """Model for vault_balance_snapshots table in {SCHEMA} schema
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
    __table_args__ = {"schema": SCHEMA}

    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey(f"{SCHEMA}.vault.id"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    timestamp = Column(BigInteger, primary_key=True, nullable=False, index=True)
    asset = Column(JSONB, nullable=False)  # JSON data about token amount, price in USD
    total_value_ada = Column(Float, nullable=False)
    total_value_usd = Column(Float, nullable=False)


class VaultState(Base):
    """Model for vault_state table in {SCHEMA} schema (recreated)
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
        "total_fees_paid": 50.0
    }
    """

    __tablename__ = "vault_state"
    __table_args__ = {"schema": SCHEMA}

    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey(f"{SCHEMA}.vault.id"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    vault_address = Column(String(255), nullable=False)
    update_time = Column(BigInteger, nullable=False, index=True)
    state = Column(String(50), nullable=False)  # open, trading, withdrawable, closed
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
    total_fees_paid = Column(Float, default=0.0)
    pool_id = Column(String(255), nullable=True)


class VaultConfigUtxo(Base):
    """Config/reference UTXO for a vault (tx_hash + utxo_id = reference script UTXO)."""

    __tablename__ = "vault_config_utxo"
    __table_args__ = {"schema": SCHEMA}

    vault_id = Column(
        UUID(as_uuid=False),
        ForeignKey(f"{SCHEMA}.vault.id"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    vault_address = Column(String(255), nullable=False)
    update_time = Column(BigInteger, nullable=False, default=0)
    pool_id = Column(String(255), nullable=True)
    tx_hash = Column(String(255), nullable=True)
    utxo_id = Column(Integer, default=0, nullable=True)


class VaultLog(Base):
    """Model for vault_logs table in {SCHEMA} schema
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
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()"),
    )
    vault_id = Column(
        UUID(as_uuid=False), ForeignKey(f"{SCHEMA}.vault.id"), nullable=False, index=True
    )
    wallet_address = Column(String(255), nullable=False, index=True)
    action = Column(
        String(50), nullable=False
    )  # 'deposit', 'withdrawal', 'claim', 'reinvest'
    amount = Column(Float, nullable=False)
    token_id = Column(String(255))
    txn = Column(String(255))
    timestamp = Column(BigInteger, nullable=False)
    status = Column(String(50), default="pending")
    fee = Column(Float, default=0.0)
    extra = Column("metadata", JSONB, nullable=True)  # DB column 'metadata'; 'extra' avoids SQLAlchemy reserved name


class UserEarning(Base):
    """Model for user_earnings table in {SCHEMA} schema
    Example:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "vault_id": "550e8400-e29b-41d4-a716-446655440001",
        "wallet_address": "addr1...",
        "total_deposit": 10000.0,
        "total_withdrawal": 2000.0,
        "is_redeemed": true,
        "current_value": 9000.0,
        "last_updated_timestamp": 1697123456
    }
    """

    __tablename__ = "user_earnings"
    __table_args__ = {"schema": SCHEMA}

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("chatbot.uuid_generate_v4()"),
    )
    vault_id = Column(
        UUID(as_uuid=False), ForeignKey(f"{SCHEMA}.vault.id"), nullable=False, index=True
    )
    wallet_address = Column(String(255), nullable=False, index=True)
    total_deposit = Column(Float, default=0.0)
    total_withdrawal = Column(Float, default=0.0)
    current_value = Column(Float, default=0.0)
    is_redeemed = Column(Boolean, default=False)
    last_updated_timestamp = Column(BigInteger)
