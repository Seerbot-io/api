from datetime import datetime
from typing import List, Optional
import uuid

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
    "",
    tags=group_tags,
    response_model=VaultListResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vaults_by_status(
    status: str = Query("active", description="Filter by status: active, inactive, or all (default: active)"),
    page: int = Query(1, ge=1, description="Page number (default: 1)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (default: 20, max: 100)"),
    offset: Optional[int] = Query(None, description="Number of items to skip (alternative to page)"),
    db: Session = Depends(get_db),
) -> VaultListResponse:
    """
    Get list of vaults filtered by status.

    Query Parameters:
    - status: active, inactive, or all (default: active)
      - active: returns vaults with state 'accepting_deposits', 'trading', or 'settled'
      - inactive: returns vaults with state 'closed'
      - all: returns all vaults

    Returns:
    - page: Page number
    - limit: Items per page
    - offset: Number of items to skip
    - vaults: List of vault items:
      - id: Vault UUID
      - state: Vault state
      - icon_url: Vault icon URL (optional)
      - vault_name: Vault name
      - summary: Vault summary (optional)
      - annual_return: Vault annual return
      - tvl_usd: Vault TVL in USD
      - max_drawdown: Vault max drawdown (optional)
      - start_time: Vault start time

      *Sample vault ID:* e13d48c8-9725-4405-8746-b84be7acc5c2
    """
    # Validate and adjust pagination parameters
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    status = status.lower().strip()
    # Map status to state values
    if status == "all":
        state_filter = ""
    elif status == "inactive":
        state_filter = "where state in ('closed')"
    else:
        state_filter = "where state in ('accepting_deposits', 'trading', 'settled')"
    # Query vault_state joined with vault and tokens table
    query_sql = text(
        f"""
        SELECT 
            v.id,
            case 
                when vs.state is not null then vs.state 
                when extract(epoch from now()) < v.trading_time then 'accepting_deposits' 
                when extract(epoch from now()) < v.settled_time then 'trading' 
                when extract(epoch from now()) < v.closed_time then 'settled'
                else 'closed' 
            end as state,
            v.name as vault_name,
            v.summary,
            vs.tvl_usd,
            vs.max_drawdown,
            v.depositing_time as start_time,
            vs.return_percent,
            v.logo_url as icon_url
        from(
            select vault_id, state, tvl_usd, max_drawdown, return_percent
            FROM proddb.vault_state
            {state_filter}
        ) vs
        left JOIN proddb.vault v ON vs.vault_id = v.id
        ORDER BY v.depositing_time DESC
        LIMIT {limit} OFFSET {offset}
        """
    )

    results = db.execute(query_sql).fetchall()

    vaults = []
    for row in results:
        # Calculate annual_return from return_percent and trade duration
        annual_return = 0.0
        if row.start_time:
            # If we have start_time, we can calculate annualized return
            # For now, use return_percent as annual_return (can be improved with actual time calculation)
            annual_return = float(row.return_percent) if row.return_percent else 0.0

        # Get icon_url from joined tokens table
        icon_url = str(row.icon_url) if row.icon_url else None

        vaults.append(
            VaultListItem(
                id=str(row.id),
                state=str(row.state),
                icon_url=icon_url,
                vault_name=str(row.vault_name) if row.vault_name else "",
                summary=str(row.summary) if row.summary else None,
                annual_return=round(annual_return, 2),
                tvl_usd=float(row.tvl_usd) if row.tvl_usd else 0.0,
                max_drawdown=float(row.max_drawdown) if row.max_drawdown else 0.0,
                start_time=int(row.start_time) if row.start_time else int(datetime.now().timestamp()),
            )
        )
    total = len(vaults) + offset*limit
    return VaultListResponse(vaults=vaults, total=total, page=page, limit=limit)


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
    - icon_url: Vault icon URL (optional)
    - vault_name: Vault name
    - vault_type: Vault type
    - blockchain: Blockchain
    - address: Vault address
    - summary: Vault summary (optional)
    - description: Vault description (optional)

    *Sample vault ID:* e13d48c8-9725-4405-8746-b84be7acc5c2
    """
    id = id.strip()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")
    # Query vault table joined with trade_strategies if available
    query_sql = text(
        f"""
        SELECT 
            v.name as vault_name,
            v.address,
            v.summary,
            v.description,
            v.token_id,
            v.logo_url,
            v.id as vault_id
        FROM proddb.vault v
        WHERE v.id = '{id}'
        LIMIT 1
        """
    )
    result = None
    result = db.execute(query_sql).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Vault not found")
    return VaultInfo(**result._asdict())


@router.get(
    "/{id}/values",
    tags=group_tags,
    response_model=VaultValuesResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_values(
    id: str,
    resolution: Optional[str] = Query(None, description="Time resolution (e.g., 1d, 1w, 1m)"),
    # start_time: Optional[int] = Query(None, description="Start timestamp (Unix timestamp)"),
    # end_time: Optional[int] = Query(None, description="End timestamp (Unix timestamp)"),
    count_back: Optional[int] = Query(None, description="Number of bars to return from end"),
    db: Session = Depends(get_db),
) -> VaultValuesResponse:
    """
    Get vault values in TradingView format.

    Path Parameters:
    - id: Vault UUID

    Query Parameters:
    - resolution: Time resolution (e.g., 1d, 1w, 1m, default: 1d)
    - start_time: Start timestamp (Unix timestamp, optional)
    - end_time: End timestamp (Unix timestamp, optional)
    - count_back: Number of bars to return from end (default: 20)

    Returns: TradingView format with:
    - s (status): "ok" or "no_data"
    - t (timestamps): List of timestamps
    - c (closing prices): List of closing prices

    *Sample vault ID:* e13d48c8-9725-4405-8746-b84be7acc5c2
    """
    id = id.lower().strip()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")
    resolution = resolution.lower().strip() if resolution else "1d"
    if resolution == "1w":
        resolution_seconds = 604800
    elif resolution == "1m":
        resolution_seconds = 2592000
    else:  # default to 1d
        resolution_seconds = 86400
    count_back = count_back if count_back else 20

    # Build query for vault_balance_snapshots
    base_query = f"""
        select vbs.timestamp, vbs.total_value_usd as closing_price 
        from (
        select case when closed_time is not null and closed_time < EXTRACT(EPOCH FROM now())::BIGINT then closed_time
                else EXTRACT(EPOCH FROM now())::BIGINT
            end end_time
        from proddb.vault
        where id =  '{id}'
        ) v
        JOIN proddb.vault_balance_snapshots vbs on vbs.vault_id = '{id}'
            and vbs.timestamp < v.end_time
            and vbs.timestamp > v.end_time - {count_back} * {resolution_seconds}
            and vbs.timestamp % {resolution_seconds} = 0
        ORDER BY timestamp ASC    
    """

    query_sql = text(base_query)
    results = []
    try:
        results = db.execute(query_sql).fetchall()
    except Exception as e:
        print(f"Database error: {str(e)}")
    if not results:
        return VaultValuesResponse(s="no_data", t=[], c=[])

    timestamps = [int(row.timestamp) for row in results]
    closing_prices = [float(row.closing_price) for row in results]

    return VaultValuesResponse(s="ok", t=timestamps, c=closing_prices)

# todo: fix open_trade.value does not exist
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
    - total: Total number of positions
    - page: Page number
    - limit: Items per page
    - offset: Number of items to skip
    - positions: List of positions with:
      - pair: Pair string (e.g., "ADA/USDM")
      - direction: Direction (buy or sell)
      - return_percent: Return percentage
      - status: Status (open or closed)

    *Sample vault ID:* e13d48c8-9725-4405-8746-b84be7acc5c2
    """
    id = id.lower().strip()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")
    # Calculate offset from page if not provided
    if offset is None:
        offset = (page - 1) * limit

    # Build status filter
    status_filter = ""
    if status:
        status = status.lower().strip()
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
      - state: Vault state
      - tvl_usd: TVL in USD
      - max_drawdown: Max drawdown
      - trade_start_time: Trade start time
      - trade_end_time: Trade end time
      - start_value: Start value
      - current_value: Current value
      - return_percent: Return percentage
      - update_time: Update time
      - total_trades: Total trades
      - winning_trades: Winning trades
      - losing_trades: Losing trades
      - win_rate: Win rate
      - avg_profit_per_winning_trade_pct: Average profit per winning trade percentage
      - avg_loss_per_losing_trade_pct: Average loss per losing trade percentage
      - avg_trade_duration: Average trade duration
      - total_fees_paid: Total fees paid
    """
    id = id.lower().strip()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")
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

    result = None
    try:
        result = db.execute(query_sql).fetchone()
    except Exception as e:
        print(f"Database error: {str(e)}")

    if not result:
        raise HTTPException(status_code=404, detail="Vault not found")

    return VaultStats(**result._asdict())
