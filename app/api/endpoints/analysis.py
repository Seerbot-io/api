from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
import requests
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

import app.schemas.analysis as schemas
from app.core.cache import cache
from app.core.config import settings
from app.core.router_decorated import APIRouter
from app.db.session import SessionLocal, get_db, get_tables
from app.models.pools import Pool
from app.models.tokens import Token
from app.services.onchain_process import add_swap_to_queue
from app.services import price_cache

router = APIRouter()
tables = get_tables(settings.SCHEMA_2)
group_tags: List[str | Enum] = ["Analysis"]

# Map timeframes to table keys (same as in analysis.py)
TIMEFRAME_MAP = {
    "5m": "f5m",
    "30m": "f30m",
    "1h": "f1h",
    "4h": "f4h",
    "1d": "f1d",
}

# Supported resolutions for TradingView
SUPPORTED_RESOLUTIONS = ["5m", "30m", "1h", "4h", "1d"]

# Get timeframe duration in seconds
TIMEFRAME_DURATION_MAP = {
    "5m": 300,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

TOKEN_LIST = {}


def _get_token_id(token: str) -> str | None:
    global TOKEN_LIST
    if token not in TOKEN_LIST or TOKEN_LIST is None or len(TOKEN_LIST.items()) == 0:
        db = SessionLocal()
        tokens = db.query(Token.id, Token.symbol).all()
        for t in tokens:
            TOKEN_LIST[t.symbol] = t.id
        db.close()
    return TOKEN_LIST.get(token, None)


# [not used]
@router.get("/indicators", tags=group_tags, response_model=schemas.IndicatorsResponse)
@cache("in-1m")
def get_indicators(
    pair: str,
    timeframe: str,
    limit: int = 100,
    from_time: int | None = None,
    to_time: int | None = None,
    indicators: str = "rsi7,rsi14,adx14,psar",
    db: Session = Depends(get_db),
) -> schemas.IndicatorsResponse:
    """Retrieves OHLC (Open, High, Low, Close) candlestick data and technical indicators (RSI7, RSI14, ADX14, PSAR) for a given trading pair.

    - pair: Trading pair joined by underscore "_" (e.g., 'USDM_ADA')
    - timeframe: Time interval ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w')
    - limit: Number of candles to return (default: 100, max: 1000)
    - from_time: Start timestamp in seconds (optional)
    - to_time: End timestamp in seconds (optional)
    - indicators: Comma-separated list of indicators to include (default: 'rsi7,rsi14,adx14,psar')

    OUTPUT:
    - pair: Trading pair
    - timeframe: Time interval
    - data: Array of OHLC and indicator data objects
    """
    # Convert pair from USDM_ADA to USDMADA
    symbol = pair.strip().replace("_", "/")

    timeframe_lower = timeframe.strip().lower()
    if timeframe_lower not in TIMEFRAME_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Valid values: 5m, 30m, 1h, 4h, 1d",
        )

    table_key = TIMEFRAME_MAP[timeframe_lower]
    if table_key not in tables:
        raise HTTPException(
            status_code=400, detail=f"Table not found for timeframe: {timeframe}"
        )

    f_table = tables[table_key]

    # Validate limit
    if limit < 1:
        limit = 100
    if limit > 1000:
        limit = 1000

    # Build time conditions
    time_conditions = []
    if from_time is not None:
        time_conditions.append(f"open_time >= {from_time}")
    if to_time is not None:
        time_conditions.append(f"open_time <= {to_time}")

    time_cond = ""
    if time_conditions:
        time_cond = " and " + " and ".join(time_conditions)

    # Parse indicators (default to all if not specified)
    indicator_list = (
        [ind.strip().lower() for ind in indicators.split(",")]
        if indicators
        else ["rsi7", "rsi14", "adx14", "psar"]
    )

    # Build SELECT clause for indicators
    indicator_selects = []
    if "rsi7" in indicator_list:
        indicator_selects.append("rsi7")
    else:
        indicator_selects.append("0 as rsi7")
    if "rsi14" in indicator_list:
        indicator_selects.append("rsi14")
    else:
        indicator_selects.append("0 as rsi14")
    if "adx14" in indicator_list or "adx" in indicator_list:
        indicator_selects.append("adx as adx14")
    else:
        indicator_selects.append("0 as adx14")
    if "psar" in indicator_list:
        indicator_selects.append("psar")
    else:
        indicator_selects.append("0 as psar")

    indicator_select_str = ", " + ", ".join(indicator_selects)

    # Build query
    limit_str = f" LIMIT {limit}" if limit > 0 else ""
    timeframe_duration = TIMEFRAME_DURATION_MAP.get(timeframe_lower, 3600)

    query = f"""
        SELECT 
            open_time + {timeframe_duration} as timestamp,
            open,
            high,
            low,
            close,
            volume
            {indicator_select_str}
        FROM {f_table}
        WHERE symbol = '{symbol}'
            and open is not null 
            and close is not null
            {time_cond}
        ORDER BY open_time DESC
        {limit_str}
    """

    result = db.execute(text(query)).fetchall()

    if not result or len(result) <= 0:
        raise HTTPException(status_code=404, detail="No data found")

    # Convert to response format (reverse order to get chronological)
    data = [
        schemas.IndicatorData(
            timestamp=int(row.timestamp) if row.timestamp else 0,
            open=float(row.open) if row.open is not None else 0.0,
            high=float(row.high) if row.high is not None else 0.0,
            low=float(row.low) if row.low is not None else 0.0,
            close=float(row.close) if row.close is not None else 0.0,
            volume=float(row.volume) if row.volume is not None else 0.0,
            rsi7=float(row.rsi7) if row.rsi7 is not None else 0.0,
            rsi14=float(row.rsi14) if row.rsi14 is not None else 0.0,
            adx14=float(row.adx14) if row.adx14 is not None else 0.0,
            psar=float(row.psar) if row.psar is not None else 0.0,
        )
        for row in reversed(result)  # Reverse to get chronological order
    ]

    # Format pair for response (USDM_ADA -> USDM/ADA)
    response_pair = pair.strip().replace("_", "/").upper()

    return schemas.IndicatorsResponse(
        pair=response_pair, timeframe=timeframe_lower, data=data
    )


@router.get("/tokens", tags=group_tags, response_model=schemas.TokenList)
@cache("in-1m")
def get_tokens(
    query: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> schemas.TokenList:
    """Search or list available tokens

    - query: query keyword to filter tokens by name or symbol (optional)
    - limit: Maximum number of records to return (optional)
    - offset: Number of records to skip (optional)

    OUTPUT: List of tokens with:
    - id: Onchain address
    - name: Token name
    - symbol: Token symbol
    - logo_url: Token logo URL
    """
    # Build query
    query_obj = db.query(Token)

    # Apply query filter if provided
    if query:
        query_term = f"%{query.strip()}%"
        query_obj = query_obj.filter(
            or_(Token.name.ilike(query_term), Token.symbol.ilike(query_term))
        )
    # Execute query
    tokens = query_obj.all()
    n = len(tokens)
    if n == 0:
        return schemas.TokenList(total=0, page=1, tokens=[])
    offset = (page - 1) * page_size
    if offset >= n:
        offset = n
    if offset + page_size > n:
        page_size = n - offset
    symbols: list[str] = [
        str(token.symbol) for token in tokens[offset : offset + page_size]
    ]
    # Use combined info and price data for efficient retrieval
    token_data = _get_tokens_bulk(symbols)
    # Convert to response format
    return schemas.TokenList(total=n, page=page, tokens=token_data)


@router.get("/tokens/{symbol}", tags=group_tags, response_model=schemas.TokenMarketInfo)
@cache("in-1m")
def get_token_info(
    symbol: str,
) -> schemas.TokenMarketInfo:
    """Get token Market info

    - symbol: Token symbol (e.g., 'USDM')
    OUTPUT: Token market information with:
    - id: Onchain address
    - name: Token name
    - symbol: Token symbol
    - price: Token price in USD
    - change_24h: Token price change in 24h (percentage)
    - low_24h: Token lowest price in 24h
    - high_24h: Token highest price in 24h
    - volume_24h: Token trade volume in 24h
    """
    symbol = symbol.strip()
    # Use combined info and price data for efficient retrieval
    token_data = _get_token_market_info(symbol)
    return token_data


@router.post("/swaps", tags=group_tags, response_model=schemas.MessageResponse)
async def create_swap(
    form: schemas.SwapCreate,
    db: Session = Depends(get_db),
    # user_id: str = Depends(get_current_user)
) -> schemas.MessageResponse:
    """Queue a swap transaction for background processing."""
    order_tx_id = form.order_tx_id.strip()
    user = form.user.strip().lower() if form.user is not None else None
    await add_swap_to_queue(order_tx_id, user)
    return schemas.MessageResponse(message="oke")


@router.get("/swaps", tags=group_tags, response_model=schemas.SwapListResponse)
@cache("in-1m")
def get_swaps(
    pair: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    from_time: Optional[int] = None,
    to_time: Optional[int] = None,
    wallet_address: Optional[str] = None,  # deprecated, use wallet_address instead
    db: Session = Depends(get_db),
) -> schemas.SwapListResponse:
    """Retrieves all swap transactions with pagination and filters.

    - page: Page number (default: 1)
    - limit: Number of records per page (default: 20, max: 100)
    - pair: Filter by trading pair in format BASE_QUOTE (e.g., USDM_ADA) (optional)
    - from_time: Start timestamp filter in seconds (optional)
    - to_time: End timestamp filter in seconds (optional)
    - wallet_address: Filter by wallet address (optional)

    OUTPUT:
    - transactions: Array of transaction objects
    - total: Total number of transactions
    - page: Current page number
    - limit: Records per page
    """
    # Validate and adjust pagination parameters
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    # Build dynamic SQL conditions
    where_clauses = ["status = 'completed'"]
    quote_token: Optional[str] = "ADA"

    # Apply pair filter if provided
    if pair:
        if "_" not in pair:
            raise HTTPException(
                status_code=400,
                detail="Invalid pair format. Use BASE_QUOTE (e.g., USDM_ADA)",
            )
        base_token, quote_token = [p.strip() for p in pair.split("_", 1)]
        if not base_token or not quote_token:
            raise HTTPException(
                status_code=400,
                detail="Invalid pair format. Both tokens are required (BASE_QUOTE)",
            )
        token_list_str = "('" + base_token + "', '" + quote_token + "')"
        where_clauses.append(
            f"from_token in {token_list_str} AND to_token in {token_list_str}"
        )
    if from_time:
        where_clauses.append(f"timestamp >= {from_time}")
    if to_time:
        where_clauses.append(f"timestamp <= {to_time}")
    if wallet_address:
        # Filter by wallet_address when wallet_address is provided
        where_clauses.append(f"wallet_address = '{wallet_address}'")

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
    limit_offset_sql = ""
    if limit is not None and limit > 0:
        limit_offset_sql += f"LIMIT {limit}"
    if offset is not None and offset > 0:
        limit_offset_sql += f" OFFSET {offset}"
    # Fetch paginated rows with total count in one query
    # change to proddb schema
    data_sql = text(
        f"""
        SELECT 
            transaction_id,
            case 
                when from_token = '{quote_token}' then CONCAT(to_token, '/', from_token) 
                else CONCAT(from_token, '/', to_token) 
            end as pair,
            case when from_token = '{quote_token}' then 'buy' else 'sell' end as side,
            from_token,
            to_token,
            from_amount,
            to_amount,
            case when from_token = '{quote_token}' then from_amount / to_amount else to_amount / from_amount end as price,
            -- price,
            timestamp,
            status,
            COUNT(*) OVER() AS total_count
        FROM proddb.swap_transactions
        WHERE {where_sql}
        ORDER BY timestamp DESC
        {limit_offset_sql}
        """
    )
    swaps = db.execute(data_sql).fetchall()

    total = int(swaps[0].total_count) if swaps else 0
    # Convert to response format
    transactions = [
        schemas.SwapTransaction(
            transaction_id=str(row.transaction_id),
            side=str(row.side),
            pair=str(row.pair),
            from_token=str(row.from_token),
            to_token=str(row.to_token),
            from_amount=float(row.from_amount) if row.from_amount is not None else 0.0,
            to_amount=float(row.to_amount) if row.to_amount is not None else 0.0,
            price=float(row.price) if row.price is not None else 0.0,
            timestamp=int(row.timestamp) if row.timestamp is not None else 0,
            status=str(row.status),
        )
        for row in swaps
    ]

    return schemas.SwapListResponse(
        transactions=transactions, total=total, page=page, limit=limit
    )


# @cache('in-5m')
def _fetch_top_traders_data(
    limit: int | None, offset: int | None, metric: str, period: str, pair: Optional[str]
) -> List[dict]:
    """Core logic for retrieving top trader stats."""

    metric_lower = metric.strip().lower()
    valid_metrics = ["volume", "trades"]
    if metric_lower not in valid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric: {metric}. Valid values: {', '.join(valid_metrics)}",
        )
    metric_lower = "total_" + metric_lower

    period_lower = period.strip().lower()
    valid_periods = ["24h", "7d", "30d", "all"]
    if period_lower not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period: {period}. Valid values: {', '.join(valid_periods)}",
        )

    current_time = int(datetime.now().timestamp())
    time_filters = {
        "24h": current_time - 24 * 60 * 60,
        "7d": current_time - 7 * 24 * 60 * 60,
        "30d": current_time - 30 * 24 * 60 * 60,
        "all": None,
    }
    time_threshold = time_filters.get(period_lower)

    where_conditions = ["status = 'completed'"]
    if time_threshold is not None:
        where_conditions.append(f"timestamp >= {time_threshold}")

    if pair:
        token1, token2 = token1, token2 = pair.split("_", 1)
        where_conditions.append(
            f"from_token in ('{token1}', '{token2}') "
            f"AND to_token in ('{token1}', '{token2}')"
        )

    limit_str = offset_str = ""
    if limit is not None and limit > 0:
        limit_str = f" LIMIT {limit}"
    if offset is not None and offset > 0:
        offset_str = f" OFFSET {offset}"

    where_clause = " AND ".join(where_conditions)
    query = f"""
        SELECT 
            wallet_address,
            COALESCE(SUM(value_ada*price_ada), 0) as total_volume,
            COUNT(transaction_id) as total_trades
        FROM proddb.swap_transactions
        WHERE status = 'completed' and {where_clause} 
        GROUP BY wallet_address
        ORDER BY {metric_lower} DESC
        {limit_str}
        {offset_str}
    """

    db = SessionLocal()
    try:
        results = db.execute(text(query)).fetchall()
    finally:
        db.close()

    traders = []
    for idx, row in enumerate(results, start=1):
        traders.append(
            {
                "user_id": row.wallet_address or "",
                "total_volume": float(row.total_volume) if row.total_volume else 0.0,
                "total_trades": int(row.total_trades) if row.total_trades else 0,
                "rank": idx,
                "period": period_lower,
                "timestamp": current_time,
            }
        )
    return traders


@router.get("/toptraders", tags=group_tags, response_model=schemas.TraderList)
@cache("in-5m")
def get_top_traders(
    page: int = 1,
    page_size: int = 20,
    metric: str = "volume",
    period: str = "all",
    pair: Optional[str] = None,
) -> schemas.TraderList:
    """Retrieves a list of top traders based on trading volume or number of trades."""
    raw_traders = _fetch_top_traders_data(
        limit=None, offset=None, metric=metric, period=period, pair=pair
    )
    n = len(raw_traders)

    if n == 0:
        return schemas.TraderList(traders=[], total=0, page=1)
    offset = (page - 1) * page_size
    if offset >= n:
        offset = n
    if offset + page_size > n:
        page_size = n - offset
    traders = [
        schemas.Trader(**trader) for trader in raw_traders[offset : offset + page_size]
    ]
    trader_list = schemas.TraderList(total=n, page=page, traders=traders)
    return trader_list


@cache("in-1m", key_prefix="chart_data_impl")
def get_chart_data(
    symbol: str,
    resolution: str,
    from_time: Optional[int] = None,
    to_time: Optional[int] = None,
    count_back: Optional[int] = None,
) -> list:
    """Fetch OHLCV data from database for charting.

    Creates its own database session internally. Returns dicts for proper JSON serialization.

    Args:
        symbol: Trading pair symbol (e.g., 'USDM/ADA')
        resolution: Chart resolution ('5m', '30m', '1h', '4h', '1d')
        from_time: Start timestamp in seconds (optional)
        to_time: End timestamp in seconds (optional, exclusive for TradingView)
        count_back: Required number of bars (optional, for TradingView getBars)

    Returns:
        List of dicts with keys: timestamp, open, high, low, close, volume
    """
    # Create database session
    db = SessionLocal()
    try:
        # Normalize symbol
        symbol_clean = symbol.strip().replace("_", "/")

        # Validate and convert resolution to timeframe
        if resolution not in SUPPORTED_RESOLUTIONS:
            raise ValueError(
                f"Invalid resolution: {resolution}. Supported: {SUPPORTED_RESOLUTIONS}"
            )

        timeframe = resolution

        # Map timeframe to table key
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        table_key = TIMEFRAME_MAP[timeframe]
        if table_key not in tables:
            raise ValueError(f"Table not found for timeframe: {timeframe}")

        if table_key == "f5m":
            f_table = tables["p5m"]
        elif table_key == "f1h":
            f_table = tables["p1h"]
        else:
            f_table = tables[table_key]
        timeframe_duration = TIMEFRAME_DURATION_MAP.get(timeframe, 3600)

        if to_time is not None:
            to_time = to_time - timeframe_duration
        else:
            to_time = int(datetime.now().timestamp())
        if from_time is not None:
            from_time = from_time - timeframe_duration
        else:
            rows = count_back if count_back is not None else 20
            from_time = to_time - rows * timeframe_duration

        # Build WHERE conditions
        where_conditions = [
            f"symbol = '{symbol_clean}'",
            "open IS NOT NULL",
            "close IS NOT NULL",
        ]

        if from_time is not None and to_time is not None:
            # Make to_time exclusive for TradingView: use < instead of <=
            where_conditions.append(f"open_time >= {from_time}")
            where_conditions.append(f"open_time <= {to_time}")
        elif from_time is not None:
            where_conditions.append(f"open_time >= {from_time}")
        elif to_time is not None:
            where_conditions.append(f"open_time <= {to_time}")

        where_clause = " AND ".join(where_conditions)

        # Build LIMIT clause using count_back
        limit_clause = ""
        if count_back is not None and count_back > 0:
            limit_clause = f"LIMIT {count_back}"

        # Build query
        query = f"""
            SELECT 
                open_time + {timeframe_duration} as timestamp,
                open,
                high,
                low,
                close,
                volume
            FROM {f_table}
            WHERE {where_clause}
            ORDER BY open_time DESC
            {limit_clause}
        """

        try:
            result = db.execute(text(query)).fetchall()

            return [
                {
                    "timestamp": row.timestamp,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in result
            ]

        except Exception as e:
            raise Exception(f"Database query error: {str(e)}")
    finally:
        db.close()


def format_tradingview_data(result: list) -> dict:
    """Format database result to TradingView format.

    Args:
        result: List of database rows with (timestamp, open, high, low, close, volume)

    Returns:
        Dictionary in TradingView format with arrays: t, o, h, l, c, v
    """
    if not result or len(result) == 0:
        return {"s": "no_data", "t": [], "o": [], "h": [], "l": [], "c": [], "v": []}

    # Convert to TradingView format
    timestamps = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    for row in result:
        timestamps.append(int(row["timestamp"]) if row["timestamp"] else 0)
        opens.append(float(row["open"]) if row["open"] is not None else 0.0)
        highs.append(float(row["high"]) if row["high"] is not None else 0.0)
        lows.append(float(row["low"]) if row["low"] is not None else 0.0)
        closes.append(float(row["close"]) if row["close"] is not None else 0.0)
        volumes.append(float(row["volume"]) if row["volume"] is not None else 0.0)

    return {
        "s": "ok",
        "t": timestamps,
        "o": opens,
        "h": highs,
        "l": lows,
        "c": closes,
        "v": volumes,
    }


@router.get("/charting/config", tags=group_tags)
@cache("in-1h")
def get_config():
    """TradingView charting library configuration endpoint."""
    return {
        "supports_search": True,
        "supports_time": True,
        "supports_timescale_marks": False,
        "supports_group_request": False,
        "supported_resolutions": SUPPORTED_RESOLUTIONS,
        "supports_marks": False,
        "supports_volume": True,
    }


@router.get("/charting/pairs", tags=group_tags)
@cache("in-1h")
def search_pairs(
    query: Optional[str] = None,
    exchange: Optional[str] = None,
    symbol_type: Optional[str] = None,
    limit: Optional[int] = 50,
    db: Session = Depends(get_db),
):
    """TradingView searchSymbols endpoint.
    - query: Search query string (optional)
    - exchange: Exchange filter (optional, not used currently)
    - symbol_type: Symbol type filter (optional, not used currently)
    - limit: Maximum number of results (default: 50, max: 100)
    """
    # Build query
    query_obj = db.query(Pool)

    # Apply search filter if provided
    if query and query.strip():
        query_obj = query_obj.filter(Pool.pair.ilike(f"%{query.strip()}%"))

    if limit:
        limit = max(1, min(100, limit))  # Limit between 1 and 100
        query_obj = query_obj.limit(limit)
    try:
        results = query_obj.all()
        # Format results for TradingView SearchSymbolResultItem format
        symbols = []
        for row in results:
            pair = str(row.pair) if row.pair is not None else ""
            if pair:
                pair_clean = pair.strip().replace("_", "/").upper()
                symbols.append(
                    {
                        "pair": pair_clean,
                        "description": f"{pair_clean} Trading Pair",
                        "exchange": "",
                        "ticker": pair_clean,
                        "type": "crypto",
                    }
                )

        return symbols
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/charting/pairs/{pair}", tags=group_tags)
@cache("in-1h")
def resolve_pair(pair: str, db: Session = Depends(get_db)):
    """TradingView resolveSymbol endpoint.

    - pair: Trading pair symbol (e.g., 'USDM_ADA')
    """
    # Normalize symbol format
    pair_clean = pair.strip().replace("_", "/")
    pool = db.query(Pool).filter(Pool.pair == pair_clean).first()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    return {
        "name": pair_clean,
        "ticker": pair_clean,
        "description": f"{pair_clean} Trading Pair",
        "type": "crypto",
        "session": "24x7",
        "timezone": "Etc/UTC",
        "exchange": "",
        "listed_exchange": "",
        "has_intraday": True,
        "has_weekly_and_monthly": False,
        "supported_resolutions": SUPPORTED_RESOLUTIONS,
        "pricescale": 100,
        "data_status": "streaming",
        "minmov": 1,
        "volume_precision": 2,
        "has_daily": True,
        "has_no_volume": False,
    }


@router.get("/charting/history/{pair}", tags=group_tags)
@cache("in-5m")
def get_bars(
    pair: str,
    resolution: str,
    from_: int | None = None,
    to: int | None = None,
    count_back: Optional[int] = None,
):
    """TradingView getBars endpoint (historical data).

    - pair: Trading pair symbol (e.g., 'USDM_ADA')
    - resolution: Chart resolution ('5m', '30m', '1h', '4h', '1d')
    - from_: Start timestamp in seconds
    - to: End timestamp in seconds (exclusive)
    - count_back: Required number of bars (optional, TradingView uses this)
    """
    tf = TIMEFRAME_DURATION_MAP[resolution]
    if to is None:
        to = int(datetime.now().timestamp()) // tf * tf
    if from_ is None:
        n_rows = count_back + 1 if count_back is not None else 20
        from_ = to - n_rows * tf
    try:
        result = get_chart_data(
            symbol=pair,
            resolution=resolution,
            from_time=from_,
            to_time=to,
            count_back=count_back,
        )

        return format_tradingview_data(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def generate_subscriber_id(symbol: str, resolution: str) -> str:
    """Generate subscriber_id in format: BARS_{pair}_{resolution}"""
    # Replace "/" with "_" in symbol for subscriber_id
    pair = symbol.replace("/", "_")
    return f"BARS_{pair}_{resolution}"


def _get_token_market_info(symbol: str) -> schemas.TokenMarketInfo:
    """Get complete token market info by combining cached info and price data"""
    # Get info from cache or DB (checks cache first)
    info = price_cache.get_token_info(symbol)
    # Get price from cache or DB (checks cache first)
    price = price_cache.get_token_price(symbol)

    if info and price:
        # Calculate market cap
        market_cap = price.price * info.total_supply if info.total_supply > 0 else 0.0

        return schemas.TokenMarketInfo(
            id=info.id,
            name=info.name,
            symbol=info.symbol,
            logo_url=info.logo_url,
            price=price.price,
            change_24h=price.change_24h,
            low_24h=price.low_24h,
            high_24h=price.high_24h,
            volume_24h=price.volume_24h,
            market_cap=market_cap,
        )

    # If either is missing, this should not happen with proper cache management
    raise HTTPException(status_code=404, detail="Token not found")


def _get_tokens_bulk(symbols: List[str]) -> List[schemas.TokenMarketInfo]:
    """Get multiple token market info with cache optimization"""
    if not symbols:
        return []

    # Normalize symbols and create mapping for original -> normalized
    symbol_map: Dict[str, str] = {}
    normalized_symbols: List[str] = []
    for s in symbols:
        normalized = s.strip().upper()
        if normalized:
            symbol_map[normalized] = s  # Map normalized back to original for ordering
            if normalized not in normalized_symbols:
                normalized_symbols.append(normalized)

    if not normalized_symbols:
        return []

    # Process ADA first if in the list (optimization)
    all_symbols = normalized_symbols.copy()
    if "ADA" in all_symbols:
        all_symbols.remove("ADA")
        all_symbols.insert(0, "ADA")  # Put ADA at the front

    # Get info and prices from cache or DB in single pass
    # Cache manager automatically fetches from DB if not cached
    info_dict: Dict[str, Any] = {}
    price_dict: Dict[str, Any] = {}

    for symbol in all_symbols:
        info = price_cache.get_token_info(symbol)
        price = price_cache.get_token_price(symbol)

        if info:
            info_dict[symbol] = info
        if price:
            price_dict[symbol] = price

    # Combine info and price data, build result dict
    result_dict: Dict[str, schemas.TokenMarketInfo] = {}

    for symbol in all_symbols:
        info = info_dict.get(symbol)
        price = price_dict.get(symbol)

        if info and price:
            # Calculate market cap from price * total_supply
            market_cap = (
                price.price * info.total_supply if info.total_supply > 0 else 0.0
            )

            result_dict[symbol] = schemas.TokenMarketInfo(
                id=info.id,
                name=info.name,
                symbol=info.symbol,
                logo_url=info.logo_url,
                price=price.price,
                change_24h=price.change_24h,
                low_24h=price.low_24h,
                high_24h=price.high_24h,
                volume_24h=price.volume_24h,
                market_cap=market_cap,
            )

    # Return results in the same order as requested symbols (using original case)
    return [
        result_dict.get(s.strip().upper())
        for s in symbols
        if result_dict.get(s.strip().upper())
    ]


def _generate_predict_list(
    predict_scores: dict[str, float],
) -> list[schemas.TrendPair_V2]:
    predict_list = []
    token_list = [pair.split("/")[0] for pair in predict_scores.keys()]
    # Use price cache for efficient data retrieval
    token_data = _get_tokens_bulk(token_list)
    timestamp = int(datetime.now().timestamp() // 3600 * 3600)
    token_data_dict = {}
    for token in token_data:
        token_data_dict[token.symbol] = token
    for pair, confidence in predict_scores.items():
        token = token_data_dict[pair.split("/")[0]]
        predict_list.append(
            schemas.TrendPair_V2(
                pair=pair,
                timestamp=timestamp,
                confidence=round(20 * confidence, 2),
                price=token.price,
                change_24h=token.change_24h,
                volume_24h=token.volume_24h,
                market_cap=token.market_cap,
                logo_url=token.logo_url,
            )
        )
    return predict_list


@router.get("/trend", tags=group_tags, response_model=schemas.TrendResponse)
@cache("in-5m")
def get_trend(
    timeframe: str = "1d", limit: Optional[int] = None, db: Session = Depends(get_db)
) -> schemas.TrendResponse:
    """Retrieves trend prediction data for all trading pairs, grouped by uptrend and downtrend.
    Uses technical analysis to predict market direction in about 5 candles.

    - timeframe: Time interval for analysis ('5m', '30m', '1h', '4h', '1d', default: '1d')
    - limit: Maximum number of rows to return (optional)

    OUTPUT:
    - uptrend: Array of pairs in uptrend with pair, confidence, price, change_24h, volume_24h
    - downtrend: Array of pairs in downtrend with pair, confidence, price, change_24h, volume_24h
    """
    # Validate timeframe
    timeframe_lower = timeframe.strip().lower()
    valid_timeframes = ["5m", "30m", "1h", "4h", "1d"]
    if timeframe_lower not in valid_timeframes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Valid values: {', '.join(valid_timeframes)}",
        )

    table_key = TIMEFRAME_MAP[timeframe_lower]
    if table_key not in tables:
        raise HTTPException(
            status_code=400, detail=f"Table not found for timeframe: {timeframe}"
        )

    f_table = tables[table_key]  # Will be used in SQL query below
    from_time = (
        int(datetime.now().timestamp()) - 10 * TIMEFRAME_DURATION_MAP[timeframe_lower]
    )

    query = f"""
    select symbol, 
        cast(sum(rsi14*CAST(r=1 AS int))/10 - 5 as float) rsi, 
        cast(avg(adx_reversal*trend_reversal*(7-r)) as float) adx, 
        cast(avg(psar*(6-r)) as float) psar
    from (
        select symbol, close, 
            rsi14,
            case 
                when adx = adx_1 and r <> 1 then 1 
                else 0
            end adx_reversal,
            case 
                when (CAST(open>close AS int) + CAST(high_1>high AS int) + CAST(low_1>low AS int) >= 2) then 1
                else -1 
            end trend_reversal,
            case 
                when psar_type_1 = 'UP' and psar_type = 'DOWN' then -1
                when psar_type_1 = 'DOWN' and psar_type = 'UP' then 1
                else 0
            end psar
            , open_time
            , r
        from (
            select symbol, open, close, high, low, rsi14, -- di14_n, di14_p, di14_line_cross  
                lag(high) over (
                    PARTITION BY symbol ORDER BY open_time asc) AS high_1,
                lag(low) over (
                    PARTITION BY symbol ORDER BY open_time asc) AS low_1,
                adx,
                max(adx) over (PARTITION BY symbol ORDER BY open_time asc rows BETWEEN 2 PRECEDING AND 1 FOLLOWING) AS adx_1,
                psar_type,
                lag(psar_type) over (PARTITION BY symbol ORDER BY open_time asc) AS psar_type_1,
                row_number() over (PARTITION BY symbol ORDER BY open_time desc) AS r
                ,open_time
            from {f_table} fcsm 
            where fcsm.open_time > {from_time}
        )
        where r <= 5
        order by open_time asc
    )
    group by symbol
    """
    result = db.execute(text(query)).fetchall()

    # Placeholder values
    uptrend_pairs = {}
    downtrend_pairs = {}

    for row in result:
        score = row.rsi * 0.3 + row.adx * 0.4 + row.psar * 0.3  # range -5 to 5
        if score > 1:
            uptrend_pairs[row.symbol] = score
        elif score < -1:
            downtrend_pairs[row.symbol] = -score

    uptrend_list = _generate_predict_list(uptrend_pairs)
    downtrend_list = _generate_predict_list(downtrend_pairs)

    return schemas.TrendResponse(uptrend=uptrend_list, downtrend=downtrend_list)


@router.get("/predict_signal", tags=group_tags, response_model=schemas.Validate)
@cache("in-5m")
def get_predict_validate(
    interval: str = "1h",
    db: Session = Depends(get_db),
) -> schemas.Validate:
    """
    - interval: 5m, 1h, 4h, 1d (default 1h)
    """
    url = "https://api.vistia.co/api/v2_2/ai-analysis/predict-validate?interval=3M&limit=100000"
    response = requests.get(url)
    data = schemas.Validate(**response.json())
    return data


@cache("in-5m", value_type=tuple[dict[str, float], dict[str, float]])
def _get_signal_adx() -> tuple[dict[str, float], dict[str, float]]:
    db: Session = SessionLocal()
    ts = TIMEFRAME_DURATION_MAP["1h"]
    f_table = tables["f1h"]  # Will be used in SQL query below
    from_time = int(datetime.now().timestamp()) - 10 * ts

    query = f"""
    select symbol, score
    from (
        select symbol --, di14_line_cross, adx_reversal, trend_reversal, r
            , cast(avg((adx_reversal+di14_line_cross)*trend_reversal*(6-r)) as float) score
        from (
            select symbol, close, di14_line_cross
                , case 
                    when adx = adx_1 and r <> 1 then 1 
                    else 0
                end adx_reversal,
                case 
                    when (CAST(open>close AS int) + CAST(high_1>high AS int) + CAST(low_1>low AS int) >= 2) then 1
                    else -1 
                end trend_reversal
                , open_time
                , r
            from (
                select symbol, open, close, high, low, di14_line_cross  
                    ,lag(high) over (
                        PARTITION BY symbol ORDER BY open_time asc) AS high_1,
                    lag(low) over (
                        PARTITION BY symbol ORDER BY open_time asc) AS low_1,
                    adx,
                    max(adx) over (PARTITION BY symbol ORDER BY open_time asc rows BETWEEN 2 PRECEDING AND 1 FOLLOWING) AS adx_1,
                    row_number() over (PARTITION BY symbol ORDER BY open_time desc) AS r
                    ,open_time
                from {f_table}  fcsm 
                where fcsm.open_time > {from_time}
            )    
            where r <= 5
            order by open_time asc
        )
        group by symbol
    )
    where score != 0
    """
    result = db.execute(text(query)).fetchall()
    predict_up = {}
    predict_down = {}
    for row in result:
        if row.score > 0:
            predict_up[row.symbol] = row.score
        else:
            predict_down[row.symbol] = -row.score
    return (predict_up, predict_down)


@cache("in-5m", value_type=tuple[dict[str, float], dict[str, float]])
def _get_signal_rsi() -> tuple[dict[str, float], dict[str, float]]:
    db: Session = SessionLocal()
    ts = TIMEFRAME_DURATION_MAP["1h"]
    f_table = tables["f1h"]  # Will be used in SQL query below
    from_time = int(datetime.now().timestamp()) - 10 * ts

    query = f"""
    select symbol, score
    from (
        select symbol
            , cast(sum(rsi14*CAST(r=1 AS int))/10 - 5 as float) score
        from (
            select symbol, rsi14
                , open_time
                , r
            from (
                select symbol, rsi14
                    , row_number() over (PARTITION BY symbol ORDER BY open_time desc) AS r
                    , open_time
                from {f_table} fcsm 
                where fcsm.open_time > {from_time}
            )    
            where r <= 5
            order by open_time asc
        )
        group by symbol
    )
    where score != 0
    """
    result = db.execute(text(query)).fetchall()
    predict_up = {}
    predict_down = {}
    for row in result:
        if row.score > 0:
            predict_up[row.symbol] = row.score
        else:
            predict_down[row.symbol] = -row.score
    return (predict_up, predict_down)


@cache("in-5m", value_type=tuple[dict[str, float], dict[str, float]])
def _get_signal_psar() -> tuple[dict[str, float], dict[str, float]]:
    db: Session = SessionLocal()
    ts = TIMEFRAME_DURATION_MAP["1h"]
    f_table = tables["f1h"]  # Will be used in SQL query below
    from_time = int(datetime.now().timestamp()) - 10 * ts

    query = f"""
    select symbol, score
    from (
        select symbol
            , cast(avg(psar*(6-r)) as float) score
        from (
            select symbol
                , case 
                    when psar_type_1 = 'UP' and psar_type = 'DOWN' then -1
                    when psar_type_1 = 'DOWN' and psar_type = 'UP' then 1
                    else 0
                end psar
                , open_time
                , r
            from (
                select symbol
                    , psar_type,
                    lag(psar_type) over (PARTITION BY symbol ORDER BY open_time asc) AS psar_type_1,
                    row_number() over (PARTITION BY symbol ORDER BY open_time desc) AS r
                    , open_time
                from {f_table} fcsm 
                where fcsm.open_time > {from_time}
            )    
            where r <= 5
            order by open_time asc
        )
        group by symbol
    )
    where score != 0
    """
    result = db.execute(text(query)).fetchall()
    predict_up = {}
    predict_down = {}
    for row in result:
        if row.score > 0:
            predict_up[row.symbol] = row.score
        else:
            predict_down[row.symbol] = -row.score
    return (predict_up, predict_down)


@cache("in-5m", value_type=tuple[dict[str, float], dict[str, float]])
def _get_signal_price_24h() -> tuple[dict[str, float], dict[str, float]]:
    db: Session = SessionLocal()
    ts = TIMEFRAME_DURATION_MAP["1h"]
    f_table = tables["f1h"]  # Will be used in SQL query below
    time_now = int(datetime.now().timestamp()) // ts * ts  # Round to nearest hour
    time_24h_ago = time_now - 24 * 60 * 60

    query = f"""
    select symbol, score
    from (
        select symbol
            , cast(
                case 
                    when price_24h > 0 then ((close - price_24h) / price_24h) * 100
                    else 0
                end as float
            ) score
        from (
            select symbol, close
                , lead(close, 24) over (PARTITION BY symbol ORDER BY open_time desc) AS price_24h
                , row_number() over (PARTITION BY symbol ORDER BY open_time desc) AS r
                , open_time
            from {f_table} fcsm 
            where fcsm.open_time >= {time_24h_ago}
                and fcsm.open_time <= {time_now}
        )
        where r = 1
    )
    where score != 0
    """
    result = db.execute(text(query)).fetchall()
    predict_up = {}
    predict_down = {}
    for row in result:
        if row.score > 0:
            predict_up[row.symbol] = row.score
        else:
            predict_down[row.symbol] = -row.score
    return (predict_up, predict_down)


@router.get(
    "/signal/{indicator}/{signal}",
    tags=group_tags,
    response_model=schemas.SignalResponse,
)
@cache("in-5m")
def get_predict_signal(
    indicator: str,
    signal: str,
    db: Session = Depends(get_db),
) -> schemas.SignalResponse:
    """Retrieves signal data for a specific indicator and signal.
    - indicator: adx, rsi, psar, price_24h (default: adx)
    - signal: up, down (default: up)
    output:
    - indicator: adx, rsi, psar, price_24h
    - signal: up, down
    - data: List[TrendPair_V2]
        - pair: Trading pair symbol (e.g., 'ETH/ADA')
        - timestamp: Timestamp of the prediction
        - confidence: Confidence score of the prediction (0-100)
        - price: Current price of the trading pair
        - change_24h: Change percentage of the trading pair in the last 24 hours
        - volume_24h: Volume of the trading pair in the last 24 hours
        - market_cap: Market cap of the trading pair
    """
    if indicator == "adx":
        predict_up, predict_down = _get_signal_adx()
    elif indicator == "rsi":
        predict_up, predict_down = _get_signal_rsi()
    elif indicator == "psar":
        predict_up, predict_down = _get_signal_psar()
    elif indicator == "price_24h":
        predict_up, predict_down = _get_signal_price_24h()
    else:
        raise HTTPException(status_code=400, detail=f"Invalid indicator: {indicator}")

    if signal == "up":
        return schemas.SignalResponse(
            indicator=indicator, signal=signal, data=_generate_predict_list(predict_up)
        )
    elif signal == "down":
        return schemas.SignalResponse(
            indicator=indicator,
            signal=signal,
            data=_generate_predict_list(predict_down),
        )
    else:
        raise HTTPException(status_code=400, detail=f"Invalid signal: {signal}")


# todo: fix this
# - [ ] implement predict_signal
@router.get("/predictions", tags=group_tags, response_model=List[schemas.Prediction])
@cache("in-5m")
def get_predictions(
    db: Session = Depends(get_db),
) -> List[schemas.Prediction]:
    """
    Retrieves prediction data for a specific trading pair.
    OUTPUT:
    - pair: Trading pair symbol (e.g., 'ETH/ADA')
    - current_price: Current price of the trading pair
    - predict_price: Predicted price of the trading pair
    - change_rate: Predicted change percentage between current and predicted price
    """

    data = [
        {
            "icon": "https://assets.coingecko.com/coins/images/279/small/ethereum.png?1595348880",
            "pair": "ETH/ADA",
            "current_price": 8.33636,
            "predict_price": 8.40000,
            "change_rate": 0.100768,
        },
        {
            "icon": "https://assets.coingecko.com/coins/images/975/small/cardano.png?1547034860",
            "pair": "USDM/ADA",
            "current_price": 2.82,
            "predict_price": 2.83,
            "change_rate": 0.294,
        },
        {
            "icon": "https://assets.coingecko.com/coins/images/975/small/cardano.png?1547034860",
            "pair": "SNEK/ADA",
            "current_price": 0.00265667166,
            "predict_price": 0.0026311,
            "change_rate": -0.96,
        },
    ]
    response = [schemas.Prediction(**item) for item in data]
    return response
