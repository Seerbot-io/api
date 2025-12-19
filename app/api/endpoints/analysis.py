import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import List, Optional

from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.schemas.analysis as schemas
from app.core.cache import cache
from app.core.config import settings
from app.core.router_decorated import APIRouter
from app.db.session import SessionLocal, get_db, get_tables
from app.models.pools import Pool
from app.models.swaps import Swap
from app.models.tokens import Token
from app.services.onchain_process import extract_swap_info

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


@cache("in-1m")
def _get_token_info_data(symbols: list[str]) -> list[schemas.TokenMarketInfo]:
    time_now = (int(datetime.now().timestamp()) // 300 - 1) * 300
    time_24h_ago = time_now - 24 * 60 * 60
    # print("[No cache] get_token_info_data for symbols: ", symbols)
    db = SessionLocal()
    data: list[schemas.TokenMarketInfo] = []
    if "ADA" in symbols:
        symbols.pop(symbols.index("ADA"))
        query = f"""  
        select a.*, c.price, c.change_24h 
        ,d.low_24h low_24h, d.high_24h high_24h, d.volume_24h volume_24h, c.price * a.total_supply as market_cap
        from (
            select id, name, symbol, logo_url, total_supply
            from proddb.tokens
            where symbol='ADA'
        ) a left join(
            select price, price - price_24h as change_24h
            from (
                select open_time, close as price, lead(close) over (ORDER by open_time desc) price_24h, row_number() over (ORDER by open_time desc) as r
                from proddb.coin_prices_5m cph
                where symbol='USDM/ADA'
                    and ((open_time >= {time_24h_ago} - 300 and open_time <= {time_24h_ago} + 300) -- range of 5 minutes for missing data
                        or open_time = {time_now}
                    )
            ) coin
            where r = 1
        ) c on TRUE
        left join(   
            select min(low) low_24h, max(high) high_24h, sum(volume) volume_24h
            from proddb.coin_prices_1h cph
            where symbol='USDM/ADA'
                and open_time > {time_24h_ago}
            ) d on TRUE
        """
        try:
            token = db.execute(text(query)).fetchone()
            if token is None:
                raise HTTPException(status_code=404, detail="Token not found")
            data.append(schemas.TokenMarketInfo.from_record(token))
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail="Failed to get token info")

    if len(symbols) > 0:
        symbols_str = "('" + "', '".join(symbols) + "')"
        pairs_str = "('" + "', '".join([f"{symbol}/ADA" for symbol in symbols]) + "')"
        query = f"""  
        select a.*, c.price/b.ada_price as price, c.change_24h/b.ada_price change_24h
        ,d.low_24h/b.ada_price low_24h, d.high_24h/b.ada_price high_24h, d.volume_24h/b.ada_price volume_24h, c.price * a.total_supply as market_cap
        from (
            select id, name, symbol, logo_url, total_supply, symbol || '/ADA' as pair
            from proddb.tokens
            where symbol in {symbols_str}
        ) a left join(
            select close as ada_price
            from proddb.coin_prices_5m cph
            where symbol='USDM/ADA'
                and open_time = {time_now}
        ) b on true
        left join(
            select symbol, price, price - price_24h as change_24h
            from (
                select symbol, open_time, close as price, lead(close, 2) over (PARTITION BY symbol ORDER by open_time desc) price_24h, row_number() over (PARTITION BY symbol ORDER by open_time desc) as r
                from proddb.coin_prices_5m cph
                where symbol in {pairs_str}
                    and ((open_time >= {time_24h_ago} - 600 and open_time <= {time_24h_ago}) -- range of 5 minutes for missing data (3 records)
                        or open_time > {time_now} - 300 -- if missing data, use the last 5 minutes data (2 records)
                    )
            ) coin
            where r = 1
        ) c on a.pair = c.symbol
        left join(   
            select symbol, min(low) low_24h, max(high) high_24h, sum(volume) volume_24h
            from proddb.coin_prices_1h cph
            where symbol in {pairs_str}
                and open_time > {time_24h_ago}
                group by symbol
            ) d on a.pair = d.symbol
        """
        tokens = db.execute(text(query)).fetchall()
        data += [schemas.TokenMarketInfo.from_record(token) for token in tokens]
    return data


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
    symbols = [token.symbol for token in tokens[offset : offset + page_size]]
    token_data = _get_token_info_data(symbols)
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
    token_data = _get_token_info_data([symbol])
    if token_data is None or len(token_data) == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    return token_data[0]


@router.post("/swaps", tags=group_tags, response_model=schemas.MessageResponse)
def create_swap(
    form: schemas.SwapCreate,
    db: Session = Depends(get_db),
    # user_id: str = Depends(get_current_user)
) -> schemas.MessageResponse:
    """Create a new swap transaction record.
    - headers: Request headers containing:
        - Content-Type: application/json
    - body: Request body containing:
        - order_tx_id: On chain order transaction ID (required)
        - execution_tx_id: On chain execution transaction ID (optional)
        - from_token: From token symbol (e.g., 'USDM') (optional)
        - to_token: To token symbol (e.g., 'ADA') (optional)
    OUTPUT:
    - message: oke

    """
    try:
        swap_info = extract_swap_info(form.order_tx_id)
        # print(swap_info)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="failed to extract swap info")
    swap_info["extend_data"] = {
        "order_tx_id": form.order_tx_id,
        "execution_tx_id": swap_info["transaction_id"],
    }
    try:
        row = Swap(
            transaction_id=swap_info["transaction_id"],
            user_id=swap_info["user"],
            from_token=swap_info["token_in"],
            from_amount=swap_info["amount_in"],
            to_token=swap_info["token_out"],
            to_amount=swap_info["amount_out"],
            price=swap_info["price"],
            value=swap_info["value"],
            timestamp=swap_info["timestamp"],
            fee=swap_info["fee"],
            fee_price=swap_info["fee_price"],
            extend_data=json.dumps(swap_info["extend_data"]),
            status="completed",
        )
        db.add(row)
        db.commit()
    except Exception as e:
        print(e)
        if isinstance(e, IntegrityError):
            raise HTTPException(status_code=400, detail="transaction already exists")
        raise HTTPException(status_code=400, detail="failed to add swap to database")

    return schemas.MessageResponse(message="oke")


@router.get("/swaps", tags=group_tags, response_model=schemas.SwapListResponse)
@cache("in-1m")
def get_swaps(
    page: int = 1,
    limit: int = 20,
    from_token: Optional[str] = None,
    to_token: Optional[str] = None,
    from_time: Optional[int] = None,
    to_time: Optional[int] = None,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> schemas.SwapListResponse:
    """Retrieves all swap transactions with pagination and filters.

    - page: Page number (default: 1)
    - limit: Number of records per page (default: 20, max: 100)
    - from_token: Filter by source token (optional)
    - to_token: Filter by destination token (optional)
    - from_time: Start timestamp filter in seconds (optional)
    - to_time: End timestamp filter in seconds (optional)
    - user_id: Filter by user ID (optional)

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

    # Build query
    query = db.query(Swap)

    # Apply filters
    if from_token:
        query = query.filter(Swap.from_token.ilike(f"%{from_token.strip()}%"))
    if to_token:
        query = query.filter(Swap.to_token.ilike(f"%{to_token.strip()}%"))
    if from_time:
        query = query.filter(Swap.timestamp >= from_time)
    if to_time:
        query = query.filter(Swap.timestamp <= to_time)
    if user_id:
        # Filter by user_id (wallet address) when user_id is provided
        query = query.filter(Swap.user_id == user_id)

    # Get total count
    total = query.count()

    # Apply pagination and ordering
    swaps = query.order_by(Swap.timestamp.desc()).offset(offset).limit(limit).all()

    # Convert to response format
    transactions = [
        schemas.SwapTransaction(
            transaction_id=str(swap.transaction_id),
            from_token=str(swap.from_token),
            from_amount=float(swap.from_amount),  # type: ignore
            to_token=str(swap.to_token),
            to_amount=float(swap.to_amount),  # type: ignore
            price=float(swap.price),  # type: ignore
            timestamp=int(swap.timestamp),  # type: ignore
            status=str(swap.status),
        )
        for swap in swaps
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
            user_id,
            COALESCE(SUM(value), 0) as total_volume,
            COUNT(transaction_id) as total_trades
        FROM proddb.swap_transactions
        WHERE {where_clause}
        GROUP BY user_id
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
                "user_id": row.user_id or "",
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
    last_timestamp: Optional[int] = None,
    count_back: Optional[int] = None,
) -> list:
    """Fetch OHLCV data from database for charting.

    Creates its own database session internally. Returns dicts for proper JSON serialization.

    Args:
        symbol: Trading pair symbol (e.g., 'USDM/ADA')
        resolution: Chart resolution ('5m', '30m', '1h', '4h', '1d')
        from_time: Start timestamp in seconds (optional)
        to_time: End timestamp in seconds (optional, exclusive for TradingView)
        last_timestamp: Get data after this timestamp (optional, for WebSocket)
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

        f_table = tables[table_key]
        timeframe_duration = TIMEFRAME_DURATION_MAP.get(timeframe, 3600)

        if from_time is not None:
            from_time = from_time - timeframe_duration
        if to_time is not None:
            to_time = to_time - timeframe_duration
        if last_timestamp is not None:
            last_timestamp = last_timestamp - timeframe_duration

        # Build WHERE conditions
        where_conditions = [
            f"symbol = '{symbol_clean}'",
            "open IS NOT NULL",
            "close IS NOT NULL",
        ]

        if last_timestamp is not None:
            where_conditions.append(f"open_time > {last_timestamp}")
        elif from_time is not None and to_time is not None:
            # Make to_time exclusive for TradingView: use < instead of <=
            where_conditions.append(f"open_time >= {from_time}")
            where_conditions.append(f"open_time < {to_time}")
        elif from_time is not None:
            where_conditions.append(f"open_time >= {from_time}")
        elif to_time is not None:
            where_conditions.append(f"open_time < {to_time}")

        where_clause = " AND ".join(where_conditions)

        # Build ORDER BY clause
        if last_timestamp is not None:
            order_by = "ORDER BY open_time DESC"
        else:
            order_by = "ORDER BY open_time ASC"

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
            {order_by}
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

    - pair: Trading pair symbol (e.g., 'USDM/ADA' or 'USDM_ADA')
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

    - pair: Trading pair symbol (e.g., 'USDM/ADA' or 'USDM_ADA')
    - resolution: Chart resolution ('5m', '30m', '1h', '4h', '1d')
    - from_: Start timestamp in seconds
    - to: End timestamp in seconds (exclusive)
    - count_back: Required number of bars (optional, TradingView uses this)
    """
    if to is None:
        to = int(datetime.now().timestamp())
    if from_ is None:
        from_ = to - 10 * TIMEFRAME_DURATION_MAP[resolution]
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


# todo: remove this websocket
@router.websocket("/charting/ws")
async def ohlc(websocket: WebSocket):
    """TradingView subscribeBars/unsubscribeBars WebSocket endpoint.

    DEPRECATED: Use the unified WebSocket endpoint at /ws with channel 'ohlc:{symbol}_{resolution}' instead.

    Expected message format:
    {
        "action": "subscribe" | "unsubscribe",
        "symbol": "USDM/ADA",
        "resolution": "5m"
    }
    Note: subscriber_id is automatically generated as "BARS_{pair}_{resolution}"
    Response format:
    {
        "subscriber_id": "BARS_USDM_ADA_5m",
        "symbol": "USDM/ADA",
        "timestamp": 1234567890,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0
    }
    """
    await websocket.accept()
    # Track subscriptions with subscriber IDs
    # Format: {subscriber_id: {"symbol": str, "resolution": str, "last_timestamp": int}}
    # subscriber_id format: "BARS_{pair}_{resolution}" (e.g., "BARS_USDM_ADA_5m")
    subscriptions = {}
    print("Websocket connected: ", websocket)

    try:
        # Handle messages and send updates in a loop
        while True:
            try:
                print("Waiting for message...")
                # Receive message (with timeout to allow periodic updates)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)
                action = message.get("action")
                symbol = message.get("symbol", "").strip().replace("_", "/").upper()
                resolution = message.get("resolution", "")

                if action == "subscribe":
                    if symbol and resolution:
                        if resolution not in SUPPORTED_RESOLUTIONS:
                            subscriber_id = generate_subscriber_id(symbol, resolution)
                            await websocket.send_json(
                                {
                                    "error": f"Invalid resolution: {resolution}",
                                    "subscriber_id": subscriber_id,
                                }
                            )
                        else:
                            # Generate subscriber_id automatically
                            subscriber_id = generate_subscriber_id(symbol, resolution)
                            subscriptions[subscriber_id] = {
                                "symbol": symbol,
                                "resolution": resolution,
                                "last_timestamp": 0,
                            }
                            await websocket.send_json(
                                {
                                    "status": "subscribed",
                                    "subscriber_id": subscriber_id,
                                    "symbol": symbol,
                                    "resolution": resolution,
                                }
                            )
                    else:
                        await websocket.send_json(
                            {
                                "error": "Missing required fields: symbol or resolution",
                                "subscriber_id": "",
                            }
                        )

                elif action == "unsubscribe":
                    if symbol and resolution:
                        # Generate subscriber_id from symbol and resolution
                        subscriber_id = generate_subscriber_id(symbol, resolution)
                        if subscriber_id in subscriptions:
                            del subscriptions[subscriber_id]
                            await websocket.send_json(
                                {
                                    "status": "unsubscribed",
                                    "subscriber_id": subscriber_id,
                                    "symbol": symbol,
                                    "resolution": resolution,
                                }
                            )
                        else:
                            await websocket.send_json(
                                {
                                    "error": f"Subscription not found for subscriber_id: {subscriber_id}",
                                    "subscriber_id": subscriber_id,
                                }
                            )
                    else:
                        await websocket.send_json(
                            {
                                "error": "Missing required fields: symbol or resolution",
                                "subscriber_id": "",
                            }
                        )

            except asyncio.TimeoutError:
                # Timeout is expected - continue to send updates
                pass
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                await websocket.send_json({"error": str(e)})

            # Send real-time updates for all active subscriptions
            # print(f"Subscriptions: {subscriptions}")
            if subscriptions:
                for subscriber_id, sub_info in subscriptions.items():
                    symbol = sub_info["symbol"]
                    resolution = sub_info["resolution"]
                    last_timestamp = sub_info["last_timestamp"]
                    # print(f"Last timestamp: {last_timestamp}")

                    try:
                        # Get latest bar after last_timestamp
                        # last_timestamp stores the open_time of the last bar we sent
                        # Query for bars where open_time > last_timestamp to get new bars
                        result = get_chart_data(
                            symbol=symbol,
                            resolution=resolution,
                            last_timestamp=last_timestamp,
                            count_back=1,
                        )

                        if result and len(result) > 0:
                            row = result[0]
                            current_timestamp = (
                                int(row["timestamp"]) if row["timestamp"] else 0
                            )

                            # Only send if this is a new bar (open_time > last_timestamp)
                            # This prevents sending duplicate bars when no new data is available
                            if (
                                last_timestamp == 0
                                or current_timestamp > last_timestamp
                            ):
                                # Update last_timestamp to the open_time of this bar
                                # Next query will get bars that opened after this bar
                                subscriptions[subscriber_id]["last_timestamp"] = (
                                    current_timestamp
                                )

                                # Send update to this specific subscriber
                                await websocket.send_json(
                                    {
                                        "subscriber_id": subscriber_id,
                                        "symbol": symbol,
                                        "timestamp": current_timestamp,
                                        "open": float(row["open"])
                                        if row["open"] is not None
                                        else 0.0,
                                        "high": float(row["high"])
                                        if row["high"] is not None
                                        else 0.0,
                                        "low": float(row["low"])
                                        if row["low"] is not None
                                        else 0.0,
                                        "close": float(row["close"])
                                        if row["close"] is not None
                                        else 0.0,
                                        "volume": float(row["volume"])
                                        if row["volume"] is not None
                                        else 0.0,
                                    }
                                )
                    except Exception as e:
                        # Log error but continue
                        print(
                            f"Error querying data for {symbol} (subscriber {subscriber_id}): {e}"
                        )

            # Wait before next update (poll every 60 seconds)
            await asyncio.sleep(10)

    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass


@router.get("/trend", tags=group_tags, response_model=schemas.TrendResponse)
@cache("at-e5m")
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
            uptrend_pairs[row.symbol] = round(20 * score, 2)
        elif score < -1:
            downtrend_pairs[row.symbol] = round(-20 * score, 2)

    sorted_uptrend_pairs = sorted(
        uptrend_pairs.items(), key=lambda item: item[1], reverse=True
    )
    sorted_downtrend_pairs = sorted(
        downtrend_pairs.items(), key=lambda item: item[1], reverse=True
    )
    if limit is not None and limit > 0:
        sorted_uptrend_pairs = sorted_uptrend_pairs[:limit]
        sorted_downtrend_pairs = sorted_downtrend_pairs[:limit]

    uptrend_list = []
    downtrend_list = []
    token_list = [pair.split("/")[0] for pair, confidence in sorted_uptrend_pairs] + [
        pair.split("/")[0] for pair, confidence in sorted_downtrend_pairs
    ]
    token_data = _get_token_info_data(token_list)
    token_data_dict = {}
    for token in token_data:
        token_data_dict[token.symbol] = token
    for pair, confidence in sorted_uptrend_pairs:
        token = token_data_dict[pair.split("/")[0]]
        uptrend_list.append(
            schemas.TrendPair(
                pair=pair,
                confidence=confidence,
                price=token.price,
                change_24h=token.change_24h,
                volume_24h=token.volume_24h,
                market_cap=token.market_cap,
                logo_url=token.logo_url,
            )
        )
    for pair, confidence in sorted_downtrend_pairs:
        token = token_data_dict[pair.split("/")[0]]
        downtrend_list.append(
            schemas.TrendPair(
                pair=pair,
                confidence=confidence,
                price=token.price,
                change_24h=token.change_24h,
                volume_24h=token.volume_24h,
                market_cap=token.market_cap,
                logo_url=token.logo_url,
            )
        )
    return schemas.TrendResponse(uptrend=uptrend_list, downtrend=downtrend_list)
