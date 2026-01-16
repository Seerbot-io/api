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
from app.services.token_price_cache import TokenPriceCacheManager

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

      *Sample vault ID:* eadbf7f3-944d-4d14-bef9-5549d9b26c8b
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
            v.logo_url as icon_url,
            COUNT(*) OVER() AS total_count
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
    total = int(results[0].total_count) if results else 0
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

    *Sample vault ID:* eadbf7f3-944d-4d14-bef9-5549d9b26c8b
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
    currency: Optional[str] = Query('usd', description="Currency to use for closing price (usd, ada)"),
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
    - currency: Currency to use for closing price (usd, ada, default: usd)
    - start_time: Start timestamp (Unix timestamp, optional)
    - end_time: End timestamp (Unix timestamp, optional)
    - count_back: Number of bars to return from end (default: 20)

    Returns: TradingView format with:
    - s (status): "ok" or "no_data"
    - t (timestamps): List of timestamps
    - c (closing prices): List of closing prices

    *Sample vault ID:* eadbf7f3-944d-4d14-bef9-5549d9b26c8b
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
    if currency == 'ada':
        closing_price_column = 'total_value_ada'
    else:
        closing_price_column = 'total_value_usd'
    # Build query for vault_balance_snapshots
    base_query = f"""
        select vbs.timestamp, vbs.{closing_price_column} as closing_price 
        from (
        select case when closed_time is not null and closed_time < EXTRACT(EPOCH FROM now())::BIGINT then closed_time
                else EXTRACT(EPOCH FROM now())::BIGINT
            end end_time
        from proddb.vault
        where id = '{id}'
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
    - positions: List of positions with:
      - pair: Pair string (e.g., "ADA/USDM")
      - value: Current value (return_amount if closed, estimated from current prices if open)
      - profit: Profit percentage ((return_amount - spend) / spend * 100)
      - open_time: Position start_time

    *Sample vault ID:* eadbf7f3-944d-4d14-bef9-5549d9b26c8b
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

    # Build status filter based on return_amount
    status_filter = ""
    if status:
        status = status.lower().strip()
        if status == "open":
            status_filter = "AND vtp.return_amount IS NULL"
        elif status == "closed":
            status_filter = "AND vtp.return_amount IS NOT NULL"
        else:
            raise HTTPException(
                status_code=400, detail="Status must be 'open' or 'closed'"
            )

    # Query positions with aggregated trade quantities and total count using window function
    positions_query = text(
        f"""
        SELECT 
            vtp.id,
            vtp.start_time,
            vtp.pair,
            vtp.spend,
            vtp.return_amount,
            vtp.base_token_id,
            vtp.quote_token_id,
            -- Aggregate quantities from position_trades
            COALESCE(SUM(pt.base_quantity), 0) as net_base_quantity,
            COALESCE(SUM(pt.quote_quantity), 0) as net_quote_quantity,
            -- Get token symbols
            base_token.symbol as base_token_symbol,
            quote_token.symbol as quote_token_symbol,
            COUNT(*) OVER() AS total_count
        FROM proddb.vault_trade_positions vtp
        LEFT JOIN proddb.position_trades pt ON vtp.id = pt.position_id
        LEFT JOIN proddb.tokens base_token ON vtp.base_token_id = base_token.id
        LEFT JOIN proddb.tokens quote_token ON vtp.quote_token_id = quote_token.id
        WHERE vtp.vault_id = '{id}' {status_filter}
        GROUP BY vtp.id, vtp.start_time, vtp.pair, vtp.spend, vtp.return_amount, 
                 vtp.base_token_id, vtp.quote_token_id, base_token.symbol, quote_token.symbol
        ORDER BY vtp.start_time DESC
        LIMIT {limit} OFFSET {offset}
        """
    )

    results = db.execute(positions_query).fetchall()
    total = int(results[0].total_count) if results else 0

    # Initialize token price cache manager
    price_cache = TokenPriceCacheManager()

    positions = []
    for row in results:
        # Get pair (use pair field from position, or construct from token symbols)
        pair = str(row.pair) if row.pair else ""
        if not pair and row.base_token_symbol and row.quote_token_symbol:
            pair = f"{row.base_token_symbol}/{row.quote_token_symbol}"
        elif not pair and row.base_token_id and row.quote_token_id:
            # Fallback to token IDs if symbols not available
            pair = f"{row.base_token_id}/{row.quote_token_id}"

        # Get spend and return amounts
        spend = float(row.spend) if row.spend else 0.0
        return_amount = float(row.return_amount) if row.return_amount else None

        # Calculate value
        value = 0.0
        if return_amount is not None:
            # Closed position: use return_amount
            value = return_amount
        else:
            # Open position: estimate value from current prices
            net_base_qty = float(row.net_base_quantity) if row.net_base_quantity else 0.0
            net_quote_qty = float(row.net_quote_quantity) if row.net_quote_quantity else 0.0
            
            base_symbol = str(row.base_token_symbol) if row.base_token_symbol else None
            quote_symbol = str(row.quote_token_symbol) if row.quote_token_symbol else None
            
            # Get current prices
            base_price = None
            quote_price = None
            
            if base_symbol:
                base_price_data = price_cache.get_token_price(base_symbol)
                if base_price_data:
                    base_price = base_price_data.price
            
            if quote_symbol:
                quote_price_data = price_cache.get_token_price(quote_symbol)
                if quote_price_data:
                    quote_price = quote_price_data.price
            
            # Calculate value: base_quantity * base_price + quote_quantity * quote_price
            if base_price is not None:
                value += net_base_qty * base_price
            if quote_price is not None:
                value += net_quote_qty * quote_price
            
            # If we couldn't get prices, fall back to spend amount
            if value == 0.0 and (base_price is None or quote_price is None):
                value = spend

        # Calculate profit percentage: (return_amount - spend) / spend * 100
        profit = 0.0
        if spend > 0:
            if return_amount is not None:
                # Closed position: use return_amount
                profit = ((return_amount - spend) / spend) * 100
            else:
                # Open position: use estimated value
                profit = ((value - spend) / spend) * 100

        positions.append(
            VaultPosition(
                pair=pair,
                value=round(value, 2),
                profit=round(profit, 2),
                open_time=int(row.start_time) if row.start_time else 0,
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
