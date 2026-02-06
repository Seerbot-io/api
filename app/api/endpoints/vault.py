from datetime import datetime
from typing import List, Optional
import json
import uuid

from fastapi import Depends, HTTPException, Query
from fastapi import status as http_status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.router_decorated import APIRouter
from app.core.cache import cache
from app.db.session import get_db
from app.schemas.vault import (
    VaultInfo,
    VaultListResponse,
    VaultListItem,
    VaultPosition,
    VaultPositionsResponse,
    VaultStats,
    VaultUserEarning,
    VaultValuesResponse,
    VaultWithdrawRequest,
    VaultWithdrawResponse,
)
from app.services import price_cache
from app.services.vault_withdraw import perform_vault_withdraw

router = APIRouter()
group_tags: List[str] = ["vault"]


@cache("in-5m", key_prefix="vaults")
def _get_vaults(
    db: Session,
    *,
    vault_id: Optional[str] = None,
    status: str = "active",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Shared vault fetcher with caching.
    Supports:
    - vault_id: fetch single vault
    - status + pagination: fetch list of vaults
    Returns: {"items": [dict...], "total": int}
    """
    vid = vault_id.strip().lower() if vault_id else None
    status_norm = (status or "active").lower().strip()
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))

    # Build state filter SQL based on status
    if status_norm == "all":
        state_filter = ""
    elif status_norm == "inactive":
        state_filter = "where state in ('closed')"
    else:  # default active
        state_filter = "where state in ('open', 'trading', 'withdrawable')"
    id_filter = f"AND v.id = '{vid}'" if vid else ""
    limit_sql = "LIMIT 1" if vid else f"LIMIT {limit} OFFSET {offset}"

    query_sql = text(
        f"""
        SELECT
            v.id,
            CASE
                WHEN vs.state IS NOT NULL THEN vs.state
                WHEN extract(epoch from now()) < v.trading_time THEN 'open'
                WHEN extract(epoch from now()) < v.withdrawal_time THEN 'trading'
                WHEN extract(epoch from now()) < v.closed_time THEN 'withdrawable'
                ELSE 'closed'
            END AS state,
            v.name AS vault_name,
            v.summary,
            v.description,
            v.address,
            v.pool_id,
            vs.tvl_usd,
            vs.max_drawdown,
            v.depositing_time AS start_time,
            vs.return_percent,
            v.logo_url AS icon_url,
            COUNT(*) OVER() AS total_count
        FROM (
            SELECT vault_id, state, tvl_usd, max_drawdown, return_percent
            FROM proddb.vault_state
            {state_filter}
        ) vs
        LEFT JOIN proddb.vault v ON vs.vault_id = v.id
        WHERE 1=1
            {id_filter}
        ORDER BY v.depositing_time DESC
        {limit_sql}
        """
    )

    results = db.execute(query_sql).fetchall()
    items: list[dict] = []
    for row in results:
        annual_return = float(row.return_percent) if row.return_percent else 0.0
        items.append(
            {
                "id": str(row.id) if row.id else "",
                "state": str(row.state) if row.state else "",
                "icon_url": str(row.icon_url) if row.icon_url else None,
                "vault_name": str(row.vault_name) if row.vault_name else "",
                "summary": str(row.summary) if row.summary else None,
                "description": str(row.description) if row.description else None,
                "address": str(row.address) if row.address else "",
                "pool_id": str(row.pool_id) if row.pool_id else "",
                "annual_return": round(annual_return, 2),
                "tvl_usd": float(row.tvl_usd) if row.tvl_usd else 0.0,
                "max_drawdown": float(row.max_drawdown) if row.max_drawdown else 0.0,
                "start_time": int(row.start_time)
                if row.start_time
                else int(datetime.now().timestamp()),
            }
        )

    total = int(results[0].total_count) if results else 0
    payload = {"items": items, "total": total}
    return payload


@cache("in-5m", key_prefix="vault_stats")
def _get_vault_stats_data(
    db: Session,
    vault_id: str,
) -> dict:
    """
    Get vault stats data
    Returns a dict with stats fields.
    """
    vid = vault_id.strip().lower()

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
            vs.trade_per_month,
            vs.total_fees_paid,
            ts.decision_cycle,
            v.depositing_time AS depositing_time
        FROM proddb.vault_state vs
        LEFT JOIN proddb.vault v ON vs.vault_id = v.id
        LEFT JOIN proddb.trade_strategies ts ON (
            ts.quote_token_id = v.token_id 
            OR ts.base_token_id = v.token_id
        )
        WHERE vs.vault_id = '{vid}'
        LIMIT 1
        """
    )

    result = None
    try:
        result = db.execute(query_sql).fetchone()
    except Exception as e:
        print(f"Database error: {str(e)}")
        return {}

    if not result:
        return {}

    annual_return = float(result.return_percent) if result.return_percent else 0.0
    start_time = (
        result.depositing_time if result.depositing_time else result.trade_start_time
    )
    dc_map = {
        "1h": "1 hour",
        "4h": "4 hours",
        "1d": "1 day",
        "1w": "1 week",
        "1m": "1 month",
        "1y": "1 year",
    }
    decision_cycle = (
        dc_map.get(str(result.decision_cycle), str(result.decision_cycle))
        if str(result.decision_cycle)
        else None
    )
    return {
        "state": str(result.state) if result.state else "",
        "tvl_usd": float(result.tvl_usd) if result.tvl_usd else 0.0,
        "max_drawdown": float(result.max_drawdown) if result.max_drawdown else 0.0,
        "trade_start_time": int(result.trade_start_time)
        if result.trade_start_time
        else None,
        "trade_end_time": int(result.trade_end_time) if result.trade_end_time else None,
        "start_value": float(result.start_value) if result.start_value else 0.0,
        "current_value": float(result.current_value) if result.current_value else 0.0,
        "return_percent": float(result.return_percent)
        if result.return_percent
        else 0.0,
        "annual_return": round(annual_return, 2),
        "total_trades": int(result.total_trades) if result.total_trades else 0,
        "winning_trades": int(result.winning_trades) if result.winning_trades else 0,
        "losing_trades": int(result.losing_trades) if result.losing_trades else 0,
        "win_rate": float(result.win_rate) if result.win_rate else 0.0,
        "avg_profit_per_winning_trade_pct": float(
            result.avg_profit_per_winning_trade_pct
        )
        if result.avg_profit_per_winning_trade_pct
        else 0.0,
        "avg_loss_per_losing_trade_pct": float(result.avg_loss_per_losing_trade_pct)
        if result.avg_loss_per_losing_trade_pct
        else 0.0,
        "total_fees_paid": float(result.total_fees_paid)
        if result.total_fees_paid
        else 0.0,
        "decision_cycle": decision_cycle,
        "trade_per_month": float(result.trade_per_month)
        if result.trade_per_month
        else 0.0,
        "start_time": int(start_time) if start_time else None,
    }


@router.get(
    "",
    tags=group_tags,
    response_model=VaultListResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vaults_by_status(
    status: str = Query(
        "active",
        description="Filter by status: active, inactive, or all (default: active)",
    ),
    page: int = Query(1, ge=1, description="Page number (default: 1)"),
    limit: int = Query(
        20, ge=1, le=100, description="Items per page (default: 20, max: 100)"
    ),
    offset: Optional[int] = Query(
        None, description="Number of items to skip (alternative to page)"
    ),
    db: Session = Depends(get_db),
) -> VaultListResponse:
    """
    Get list of vaults filtered by status.

    Query Parameters:
    - status: active, inactive, or all (default: active)
      - active: returns vaults with state 'open', 'trading', or 'withdrawable'
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
      - address: Vault script address
      - pool_id: Vault pool id (policy_id.asset_name)
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

    data = _get_vaults(db, status=status, limit=limit, offset=offset)
    vaults = []
    for item in data["items"]:
        vaults.append(
            VaultListItem(
                id=item.get("id", ""),
                state=item.get("state", ""),
                icon_url=item.get("icon_url"),
                vault_name=item.get("vault_name", ""),
                summary=item.get("summary"),
                address=item.get("address", ""),
                pool_id=item.get("pool_id", ""),
                annual_return=float(item.get("annual_return", 0.0) or 0.0),
                tvl_usd=float(item.get("tvl_usd", 0.0) or 0.0),
                max_drawdown=float(item.get("max_drawdown", 0.0) or 0.0),
                start_time=int(
                    item.get("start_time") or int(datetime.now().timestamp())
                ),
            )
        )
    total = int(data.get("total", 0) or 0)
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
    - id: Vault UUID
    - state: Vault state
    - icon_url: Vault icon URL (optional)
    - vault_name: Vault name
    - vault_type: Vault type
    - vault_type_logo: Vault type logo URL (optional)
    - blockchain: Blockchain
    - blockchain_logo: Blockchain logo URL (optional)
    - address: Vault address
    - pool_id: Vault pool id (policy_id.asset_name)
    - summary: Vault summary (optional)
    - description: Vault description (optional)
    - annual_return: Vault annual return
    - tvl_usd: Vault TVL in USD
    - max_drawdown: Vault max drawdown
    - start_time: Vault start time
    - trade_per_month: Average transactions per month
    - decision_cycle: Decision cycle from trade strategy

    *Sample vault ID:* eadbf7f3-944d-4d14-bef9-5549d9b26c8b
    """
    id = id.strip()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")

    # Get basic vault info
    data = _get_vaults(db, vault_id=id, status="all", limit=1, offset=0)
    if not data["items"]:
        raise HTTPException(status_code=404, detail="Vault not found")
    item = data["items"][0]

    # Get stats data
    stats_data = _get_vault_stats_data(db, vault_id=id)

    # Merge the data (stats_data takes precedence for overlapping fields)
    item.update(
        {
            "state": stats_data.get("state", item.get("state", "")),
            "annual_return": stats_data.get(
                "annual_return", item.get("annual_return", 0.0)
            ),
            "tvl_usd": stats_data.get("tvl_usd", item.get("tvl_usd", 0.0)),
            "max_drawdown": stats_data.get(
                "max_drawdown", item.get("max_drawdown", 0.0)
            ),
            "start_time": stats_data.get("start_time", item.get("start_time")),
            "trade_per_month": stats_data.get(
                "trade_per_month", item.get("trade_per_month", 0.0)
            ),
            "decision_cycle": stats_data.get(
                "decision_cycle", item.get("decision_cycle", None)
            ),
        }
    )

    return VaultInfo(**item)


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
      - total_fees_paid: Total fees paid
      - trade_per_month: Average transactions per month
      - decision_cycle: Decision cycle from trade strategy
      - start_time: Vault start time
    """
    id = id.lower().strip()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")

    # Get stats data using shared function
    stats_data = _get_vault_stats_data(db, vault_id=id)

    if not stats_data:
        raise HTTPException(status_code=404, detail="Vault not found")

    return VaultStats(**stats_data)


@router.get(
    "/{id}/values",
    tags=group_tags,
    response_model=VaultValuesResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_values(
    id: str,
    currency: Optional[str] = Query(
        "usd", description="Currency to use for closing price (usd, ada)"
    ),
    resolution: Optional[str] = Query(
        None, description="Time resolution (e.g., 1d, 1w, 1m)"
    ),
    # start_time: Optional[int] = Query(None, description="Start timestamp (Unix timestamp)"),
    # end_time: Optional[int] = Query(None, description="End timestamp (Unix timestamp)"),
    count_back: Optional[int] = Query(
        None, description="Number of bars to return from end"
    ),
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
    if currency == "ada":
        closing_price_column = "total_value_ada"
    else:
        closing_price_column = "total_value_usd"
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
    limit: int = Query(
        20, ge=1, le=100, description="Items per page (default: 20, max: 100)"
    ),
    offset: Optional[int] = Query(
        None, description="Number of items to skip (alternative to page)"
    ),
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
      - spend: Spend amount
      - value: Current value (value if closed, estimated from current prices if open)
      - profit: Profit percentage: (value - spend) / spend * 100
      - open_time: Position start_time
      - close_time: Position close_time
      - status: Position status ("open" or "closed")

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

    # Query positions with current_asset and quote_token_id, join tokens to get quote_token symbol
    positions_query = text(
        f"""
        SELECT 
            vtp.id,
            vtp.start_time,
            vtp.update_time,
            vtp.pair,
            vtp.spend,
            vtp.return_amount,
            vtp.quote_token_id,
            vtp.current_asset,
            quote_token.symbol as quote_token_symbol,
            COUNT(*) OVER() AS total_count
        FROM proddb.vault_positions vtp
        LEFT JOIN proddb.tokens quote_token ON vtp.quote_token_id = quote_token.id
        WHERE vtp.vault_id = '{id}' {status_filter}
        ORDER BY vtp.start_time DESC
        LIMIT {limit} OFFSET {offset}
        """
    )

    results = db.execute(positions_query).fetchall()
    total = int(results[0].total_count) if results and len(results) > 0 else 0

    positions = []
    for row in results:
        # Get pair (use pair field from position)
        pair = str(row.pair) if row.pair else ""

        # Get spend and return amounts
        spend = float(row.spend) if row.spend else 0.0

        # Calculate value
        value = spend
        if row.return_amount is not None:
            # Closed position: use return_amount directly, no calculation needed
            value = row.return_amount
            position_status = "closed"
        else:
            position_status = "open"
            # Open position only: calculate value from current_asset using prices
            # Get quote token symbol from SQL join result
            quote_token_symbol = None
            if row.quote_token_symbol:
                quote_token_symbol = str(row.quote_token_symbol)
                # Parse current_asset JSON
                current_assets = (
                    json.loads(str(row.current_asset)) if row.current_asset else "{}"
                )

            if quote_token_symbol and isinstance(current_assets, dict):
                # Calculate total value in quote asset terms
                total_value_in_quote = 0.0
                for asset_token, asset_amount in current_assets.items():
                    price = price_cache.get_pair_price(
                        f"{asset_token}/{quote_token_symbol}"
                    )
                    if price is None:
                        continue
                    asset_value = float(asset_amount) * price
                    total_value_in_quote += asset_value
                value = total_value_in_quote
                # print(f"Total value in quote: {value}")

        profit = 0.0
        if spend > 0:
            profit = ((value - spend) / spend) * 100
        positions.append(
            VaultPosition(
                pair=pair,
                spend=spend,
                value=value,
                profit=profit,
                open_time=int(row.start_time) if row.start_time else 0,
                close_time=int(row.update_time)
                if position_status == "closed"
                else None,
                status=position_status,
            )
        )

    return VaultPositionsResponse(
        total=total,
        page=page,
        limit=limit,
        positions=positions,
    )


@router.post(
    "/withdraw",
    tags=group_tags,
    response_model=VaultWithdrawResponse,
    status_code=http_status.HTTP_200_OK,
)
def withdraw_from_vault(
    payload: VaultWithdrawRequest,
    db: Session = Depends(get_db),
) -> VaultWithdrawResponse:
    """
    Trigger a vault withdraw if the user still has withdrawable capital.
    Payload:
    - vault_id: Vault UUID
    - wallet_address: Wallet address
    - amount_ada: Amount of ADA to withdraw (optional, default: all withdrawable amount)

    Returns:
    - status: "ok" if successful, "invalid" if failed
    - tx_id: Transaction hash if successful, None if failed
    - reason: Error message if failed

    *Sample request body:*
    {
        "vault_id": "eadbf7f3-944d-4d14-bef9-5549d9b26c8b",
        "wallet_address": "addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm",
        "amount_ada": 100.0
    }
    """
    outcome = perform_vault_withdraw(
        db=db,
        vault_id=payload.vault_id,
        wallet_address=payload.wallet_address,
        requested_amount_ada=payload.amount_ada,
    )
    if outcome.error:
        return VaultWithdrawResponse(status="invalid", reason=outcome.error)
    return VaultWithdrawResponse(status="ok", tx_id=outcome.tx_hash)


@router.get(
    "/{id}/contribute",
    tags=group_tags,
    response_model=VaultUserEarning,
    status_code=http_status.HTTP_200_OK,
)
def get_vault_user_earning(
    id: str,
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
    db: Session = Depends(get_db),
) -> VaultUserEarning:
    """
    Get user's earning info for a specific vault.

    Path Parameters:
    - id: Vault UUID

    Query Parameters:
    - wallet_address: Wallet address of the user (required)

    Returns:
    - total_deposit: Total amount deposited by the user
    - is_redeemed: Whether the user has redeemed their position (one-time withdrawal)

    *Sample vault ID:* eadbf7f3-944d-4d14-bef9-5549d9b26c8b
    *Sample wallet address:* addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm
    """
    id = id.strip().lower()
    # check if id is a valid uuid
    try:
        uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vault ID")
    
    wallet_address = wallet_address.strip().lower()
    
    # Query user earning for this specific vault
    data_sql = text(
        f"""
        SELECT 
            ue.total_deposit,
            ue.is_redeemed
        FROM proddb.user_earnings ue
        WHERE ue.vault_id = '{id}' AND ue.wallet_address = '{wallet_address}'
        LIMIT 1
        """
    )
    result = db.execute(data_sql).fetchone()
    
    if not result:
        # Return default values if no record found
        return VaultUserEarning(
            total_deposit=0.0,
            is_redeemed=False,
        )
    
    return VaultUserEarning(
        total_deposit=round(float(result.total_deposit), 2) if result.total_deposit else 0.0,
        is_redeemed=bool(result.is_redeemed) if result.is_redeemed is not None else False,
    )
