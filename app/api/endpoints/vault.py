from typing import List, Optional

from fastapi import Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.router_decorated import APIRouter
from app.db.session import get_db
from app.schemas.vault import (
    VaultInfo,
    VaultListResponse,
    VaultListItem,
    VaultPosition,
    VaultPositionsResponse,
    VaultStats,
    VaultValuesResponse,
)

router = APIRouter()
group_tags: List[str] = ["vault"]


@router.get(
    "/{status}",
    tags=group_tags,
    response_model=VaultListResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vaults_by_status(
    status: str,
    db: Session = Depends(get_db),
) -> VaultListResponse:
    """
    Get list of vaults filtered by status.

    Path Parameters:
    - status: active or inactive
      - active: returns vaults with state 'accepting_deposits' or 'trading'
      - inactive: returns vaults with state 'settled' or 'closed'

    Returns:
    - List of vaults with state, icon_url, vault_name, description, annual_return, tvl_usd, max_drawdown, trade_start_time
    """
    if status not in ["active", "inactive"]:
        raise HTTPException(
            status_code=400, detail="Status must be 'active' or 'inactive'"
        )

    # Map status to state values
    if status == "active":
        state_filter = "('accepting_deposits', 'trading')"
    else:
        state_filter = "('settled', 'closed')"

    # Query vault_state joined with vault and tokens table
    query_sql = text(
        f"""
        SELECT 
            vs.state,
            v.name as vault_name,
            v.description,
            vs.tvl_usd,
            vs.max_drawdown,
            vs.trade_start_time,
            vs.return_percent,
            t.logo_url as icon_url
        FROM proddb.vault_state vs
        JOIN proddb.vault v ON vs.vault_id = v.id
        LEFT JOIN proddb.tokens t ON v.token_id = t.id
        WHERE vs.state IN {state_filter}
        ORDER BY vs.tvl_usd DESC
        """
    )

    results = db.execute(query_sql).fetchall()

    vaults = []
    for row in results:
        # Calculate annual_return from return_percent and trade duration
        annual_return = 0.0
        if row.trade_start_time:
            # If we have trade_start_time, we can calculate annualized return
            # For now, use return_percent as annual_return (can be improved with actual time calculation)
            annual_return = float(row.return_percent) if row.return_percent else 0.0

        # Get icon_url from joined tokens table
        icon_url = str(row.icon_url) if row.icon_url else None

        vaults.append(
            VaultListItem(
                state=str(row.state),
                icon_url=icon_url,
                vault_name=str(row.vault_name) if row.vault_name else "",
                description=str(row.description) if row.description else None,
                annual_return=round(annual_return, 2),
                tvl_usd=float(row.tvl_usd) if row.tvl_usd else 0.0,
                max_drawdown=float(row.max_drawdown) if row.max_drawdown else 0.0,
                trade_start_time=int(row.trade_start_time) if row.trade_start_time else None,
            )
        )

    return VaultListResponse(vaults=vaults, total=len(vaults))


@router.get(
    "/{id}/info",
    tags=group_tags,
    response_model=VaultInfo,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_info(
    id: str,
    db: Session = Depends(get_db),
) -> VaultInfo:
    """
    Get vault information.

    Path Parameters:
    - id: Vault UUID

    Returns:
    - icon_url, vault_name, vault_type, blockchain, address, description, trade_strategy_id
    """
    # Query vault table joined with trade_strategies if available
    query_sql = text(
        f"""
        SELECT 
            v.name as vault_name,
            v.address,
            v.description,
            v.token_id,
            v.id as vault_id
        FROM proddb.vault v
        WHERE v.id = '{id}'
        LIMIT 1
        """
    )

    result = db.execute(query_sql).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Vault not found")

    # Get icon_url from tokens table
    icon_url = None
    if result.token_id:
        token_query = text(
            f"""
            SELECT logo_url 
            FROM proddb.tokens 
            WHERE id = '{result.token_id}'
            LIMIT 1
            """
        )
        token_result = db.execute(token_query).fetchone()
        if token_result and token_result.logo_url:
            icon_url = str(token_result.logo_url)

    # Get trade_strategy_id if available (assuming vault has a reference to trade_strategy)
    # For now, we'll need to check if there's a relationship or add it to vault table
    # Since the design doesn't specify how vault links to trade_strategy, we'll return None for now
    trade_strategy_id = None

    return VaultInfo(
        icon_url=icon_url,
        vault_name=str(result.vault_name) if result.vault_name else "",
        vault_type="seerbot_vault_v1",
        blockchain="cardano",
        address=str(result.address) if result.address else "",
        description=str(result.description) if result.description else None,
        trade_strategy_id=trade_strategy_id,
    )


@router.get(
    "/{id}/values",
    tags=group_tags,
    response_model=VaultValuesResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_values(
    id: str,
    resolution: Optional[str] = Query(None, description="Time resolution (e.g., 1h, 1d)"),
    start_time: Optional[int] = Query(None, description="Start timestamp (Unix timestamp)"),
    end_time: Optional[int] = Query(None, description="End timestamp (Unix timestamp)"),
    count_back: Optional[int] = Query(None, description="Number of bars to return from end"),
    db: Session = Depends(get_db),
) -> VaultValuesResponse:
    """
    Get vault values in TradingView format.

    Path Parameters:
    - id: Vault UUID

    Query Parameters:
    - resolution: Time resolution (optional)
    - start_time: Start timestamp (Unix timestamp, optional)
    - end_time: End timestamp (Unix timestamp, optional)
    - count_back: Number of bars to return from end (optional)

    Returns:
    - TradingView format with s (status), t (timestamps), c (closing prices)
    """
    # Build query for vault_balance_snapshots
    base_query = f"""
        SELECT timestamp, total_value_usd as closing_price
        FROM proddb.vault_balance_snapshots
        WHERE vault_id = '{id}'
    """

    # Add time filters
    if start_time:
        base_query += f" AND timestamp >= {start_time}"
    if end_time:
        base_query += f" AND timestamp <= {end_time}"

    # Order by timestamp
    base_query += " ORDER BY timestamp ASC"

    # Add limit if count_back is specified
    if count_back:
        base_query += f" LIMIT {count_back}"

    query_sql = text(base_query)
    results = db.execute(query_sql).fetchall()

    if not results:
        return VaultValuesResponse(s="no_data", t=[], c=[])

    timestamps = [int(row.timestamp) for row in results]
    closing_prices = [float(row.closing_price) for row in results]

    return VaultValuesResponse(s="ok", t=timestamps, c=closing_prices)


@router.get(
    "/{id}/positions",
    tags=group_tags,
    response_model=VaultPositionsResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_positions(
    id: str,
    status: Optional[str] = Query(None, description="Filter by status: open or closed"),
    page: int = Query(1, ge=1, description="Page number (default: 1)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (default: 20, max: 100)"),
    offset: Optional[int] = Query(None, description="Number of items to skip (alternative to page)"),
    db: Session = Depends(get_db),
) -> VaultPositionsResponse:
    """
    Get vault trade positions.

    Path Parameters:
    - id: Vault UUID

    Query Parameters:
    - status: Filter by status (open or closed, optional)
    - page: Page number (default: 1)
    - limit: Items per page (default: 20, max: 100)
    - offset: Number of items to skip (alternative to page, optional)

    Returns:
    - List of positions with pair, direction, return_percent, status, prices, etc.
    """
    # Calculate offset from page if not provided
    if offset is None:
        offset = (page - 1) * limit

    # Build status filter
    status_filter = ""
    if status:
        if status == "open":
            status_filter = "AND vtp.close_order_txn IS NULL"
        elif status == "closed":
            status_filter = "AND vtp.close_order_txn IS NOT NULL"
        else:
            raise HTTPException(
                status_code=400, detail="Status must be 'open' or 'closed'"
            )

    # Query to get total count
    count_query = text(
        f"""
        SELECT COUNT(*) as total
        FROM proddb.vault_trade_positions vtp
        WHERE vtp.vault_id = '{id}' {status_filter}
        """
    )
    count_result = db.execute(count_query).fetchone()
    total = int(count_result.total) if count_result else 0

    # Query positions with trade details
    # Join with vault_trades to get pair info, direction, and prices
    positions_query = text(
        f"""
        SELECT 
            vtp.id,
            vtp.start_time,
            vtp.update_time,
            vtp.open_order_txn,
            vtp.close_order_txn,
            vtp.spend as spend_amount,
            vtp.return_amount,
            -- Open trade details
            open_trade.from_token as open_from_token,
            open_trade.to_token as open_to_token,
            open_trade.price as open_price,
            open_trade.value as open_value,
            open_trade.from_amount as open_from_amount,
            open_trade.to_amount as open_to_amount,
            -- Close trade details (if exists)
            close_trade.price as close_price,
            close_trade.value as close_value,
            -- Token symbols for pair
            from_token.symbol as from_token_symbol,
            to_token.symbol as to_token_symbol
        FROM proddb.vault_trade_positions vtp
        LEFT JOIN proddb.vault_trades open_trade ON vtp.open_order_txn = open_trade.txn
        LEFT JOIN proddb.vault_trades close_trade ON vtp.close_order_txn = close_trade.txn
        LEFT JOIN proddb.tokens from_token ON open_trade.from_token = from_token.id
        LEFT JOIN proddb.tokens to_token ON open_trade.to_token = to_token.id
        WHERE vtp.vault_id = '{id}' {status_filter}
        ORDER BY vtp.start_time DESC
        LIMIT {limit} OFFSET {offset}
        """
    )

    results = db.execute(positions_query).fetchall()

    positions = []
    for row in results:
        # Determine status
        position_status = "closed" if row.close_order_txn else "open"

        # Build pair string (e.g., "ADA/USDM")
        pair = ""
        if row.from_token_symbol and row.to_token_symbol:
            pair = f"{row.to_token_symbol}/{row.from_token_symbol}"
        elif row.open_from_token and row.open_to_token:
            # Fallback to token IDs if symbols not available
            pair = f"{row.open_to_token}/{row.open_from_token}"

        # Determine direction (buy if from_token is base, sell if to_token is base)
        # For simplicity, we'll use the trade direction from the open trade
        direction = "buy"  # Default, can be determined from trade logic

        # Calculate return_percent
        return_percent = 0.0
        spend_amount = float(row.spend_amount) if row.spend_amount else 0.0
        return_amount = float(row.return_amount) if row.return_amount else 0.0
        if spend_amount > 0:
            return_percent = ((return_amount - spend_amount) / spend_amount) * 100

        # Get prices
        open_price = float(row.open_price) if row.open_price else 0.0
        close_price = float(row.close_price) if row.close_price else None

        # Calculate value_usd (use return_amount or current value)
        value_usd = return_amount  # Can be improved with actual USD conversion

        positions.append(
            VaultPosition(
                pair=pair,
                direction=direction,
                return_percent=round(return_percent, 2),
                status=position_status,
                spend_amount=round(spend_amount, 2),
                value_usd=round(value_usd, 2),
                open_price=round(open_price, 6),
                close_price=round(close_price, 6) if close_price else None,
                start_time=int(row.start_time) if row.start_time else 0,
                update_time=int(row.update_time) if row.update_time else 0,
                open_order_txn=str(row.open_order_txn) if row.open_order_txn else "",
                close_order_txn=str(row.close_order_txn) if row.close_order_txn else None,
            )
        )

    return VaultPositionsResponse(
        total=total,
        page=page,
        limit=limit,
        positions=positions,
    )


@router.get(
    "/{id}/stats",
    tags=group_tags,
    response_model=VaultStats,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_stats(
    id: str,
    db: Session = Depends(get_db),
) -> VaultStats:
    """
    Get complete vault statistics.

    Path Parameters:
    - id: Vault UUID

    Returns:
    - Complete vault statistics from vault_state table including:
      state, tvl_usd, max_drawdown, trade stats, win rate, etc.
    """
    # Query vault_state table
    query_sql = text(
        f"""
        SELECT 
            vs.state,
            vs.tvl_usd,
            vs.max_drawdown,
            vs.trade_start_time,
            vs.trade_end_time,
            vs.start_value,
            vs.current_value,
            vs.return_percent,
            vs.update_time,
            vs.total_trades,
            vs.winning_trades,
            vs.losing_trades,
            vs.win_rate,
            vs.avg_profit_per_winning_trade_pct,
            vs.avg_loss_per_losing_trade_pct,
            vs.avg_trade_duration,
            vs.total_fees_paid
        FROM proddb.vault_state vs
        WHERE vs.vault_id = '{id}'
        LIMIT 1
        """
    )

    result = db.execute(query_sql).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Vault not found")

    return VaultStats(
        state=str(result.state) if result.state else "",
        tvl_usd=float(result.tvl_usd) if result.tvl_usd else 0.0,
        max_drawdown=float(result.max_drawdown) if result.max_drawdown else 0.0,
        trade_start_time=int(result.trade_start_time) if result.trade_start_time else None,
        trade_end_time=int(result.trade_end_time) if result.trade_end_time else None,
        start_value=float(result.start_value) if result.start_value else 0.0,
        current_value=float(result.current_value) if result.current_value else 0.0,
        return_percent=float(result.return_percent) if result.return_percent else 0.0,
        update_time=int(result.update_time) if result.update_time else 0,
        total_trades=int(result.total_trades) if result.total_trades else 0,
        winning_trades=int(result.winning_trades) if result.winning_trades else 0,
        losing_trades=int(result.losing_trades) if result.losing_trades else 0,
        win_rate=float(result.win_rate) if result.win_rate else 0.0,
        avg_profit_per_winning_trade_pct=float(result.avg_profit_per_winning_trade_pct)
        if result.avg_profit_per_winning_trade_pct
        else 0.0,
        avg_loss_per_losing_trade_pct=float(result.avg_loss_per_losing_trade_pct)
        if result.avg_loss_per_losing_trade_pct
        else 0.0,
        avg_trade_duration=float(result.avg_trade_duration) if result.avg_trade_duration else 0.0,
        total_fees_paid=float(result.total_fees_paid) if result.total_fees_paid else 0.0,
    )
