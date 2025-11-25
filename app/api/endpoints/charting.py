from app.core.config import settings
from app.core.router_decorated import APIRouter
from app.core.cache import cache
from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from app.db.session import get_db, get_tables, SessionLocal
from app.schemas.charting import CachedRow
import asyncio
import json

router = APIRouter()
tables = get_tables(settings.SCHEMA_2)
group_tags = ["Charting"]

# Map timeframes to table keys (same as in analysis.py)
TIMEFRAME_MAP = {
    '5m': 'p5m',
    '30m': 'f30m',
    '1h': 'p1h',
    '4h': 'f4h',
    '1d': 'f1d',
}

# Supported resolutions for TradingView
SUPPORTED_RESOLUTIONS = ['5m', '30m', '1h', '4h', '1d']

# Get timeframe duration in seconds
TIMEFRAME_DURATION_MAP = {
    '5m': 300,
    '30m': 1800,
    '1h': 3600,
    '4h': 14400,
    '1d': 86400,
}


@cache('in-1m', key_prefix='chart_data_impl')
def _get_chart_data_impl(
    symbol: str,
    resolution: str,
    from_time: Optional[int] = None,
    to_time: Optional[int] = None,
    last_timestamp: Optional[int] = None,
    count_back: Optional[int] = None
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
            raise ValueError(f"Invalid resolution: {resolution}. Supported: {SUPPORTED_RESOLUTIONS}")
        
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
            "close IS NOT NULL"
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
            
            # If countBack is specified and we don't have enough bars, try to get earlier bars
            # This meets TradingView's requirement to return countBack bars even if range is insufficient
            if count_back is not None and len(result) < count_back and from_time is not None:
                additional_needed = count_back - len(result)
                earlier_query = f"""
                    SELECT 
                        open_time + {timeframe_duration} as timestamp,
                        open,
                        high,
                        low,
                        close,
                        volume
                    FROM {f_table}
                    WHERE symbol = '{symbol_clean}'
                        AND open IS NOT NULL 
                        AND close IS NOT NULL
                        AND open_time < {from_time}
                    ORDER BY open_time DESC
                    LIMIT {additional_needed}
                """
                earlier_result = db.execute(text(earlier_query)).fetchall()
                # Combine results: earlier bars (reversed to maintain ASC order) + current bars
                all_results = list(reversed(earlier_result)) + list(result)
                result = all_results[:count_back] if len(all_results) > count_back else all_results
            
            # Convert Row objects to dicts for caching
            return [
                {
                    'timestamp': row.timestamp,
                    'open': row.open,
                    'high': row.high,
                    'low': row.low,
                    'close': row.close,
                    'volume': row.volume
                }
                for row in result
            ]
                
        except Exception as e:
            raise Exception(f"Database query error: {str(e)}")
    finally:
        db.close()


def get_chart_data(
    symbol: str,
    resolution: str,
    from_time: Optional[int] = None,
    to_time: Optional[int] = None,
    last_timestamp: Optional[int] = None,
    count_back: Optional[int] = None
) -> list:
    """Wrapper that converts cached dict rows into CachedRow objects."""
    raw_result = _get_chart_data_impl(
        symbol=symbol,
        resolution=resolution,
        from_time=from_time,
        to_time=to_time,
        last_timestamp=last_timestamp,
        count_back=count_back
    )
    
    normalized = []
    for idx, item in enumerate(raw_result):
        if isinstance(item, CachedRow):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(CachedRow(item))
        elif isinstance(item, str):
            # Skip stale stringified cache entries
            print(f"Warning: Skipping string item at index {idx} in get_chart_data result")
            continue
        else:
            try:
                normalized.append(CachedRow({
                    'timestamp': getattr(item, 'timestamp', None),
                    'open': getattr(item, 'open', None),
                    'high': getattr(item, 'high', None),
                    'low': getattr(item, 'low', None),
                    'close': getattr(item, 'close', None),
                    'volume': getattr(item, 'volume', None),
                }))
            except Exception as e:
                print(f"Warning: Could not convert item at index {idx} to CachedRow: {e}")
    
    if len(normalized) < len(raw_result):
        print(f"Warning: Filtered out {len(raw_result) - len(normalized)} corrupted cache entries in get_chart_data")
    
    return normalized


def format_tradingview_data(result: list) -> dict:
    """Format database result to TradingView format.
    
    Args:
        result: List of database rows with (timestamp, open, high, low, close, volume)
    
    Returns:
        Dictionary in TradingView format with arrays: t, o, h, l, c, v
    """
    if not result or len(result) == 0:
        return {
            "s": "no_data",
            "t": [],
            "o": [],
            "h": [],
            "l": [],
            "c": [],
            "v": []
        }
    
    # Convert to TradingView format
    timestamps = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []
    
    for row in result:
        if isinstance(row, dict):
            row = CachedRow(row)
        elif not isinstance(row, CachedRow):
            continue
        
        timestamps.append(int(row.timestamp) if row.timestamp else 0)
        opens.append(float(row.open) if row.open is not None else 0.0)
        highs.append(float(row.high) if row.high is not None else 0.0)
        lows.append(float(row.low) if row.low is not None else 0.0)
        closes.append(float(row.close) if row.close is not None else 0.0)
        volumes.append(float(row.volume) if row.volume is not None else 0.0)
    
    return {
        "s": "ok",
        "t": timestamps,
        "o": opens,
        "h": highs,
        "l": lows,
        "c": closes,
        "v": volumes
    }


@router.get("/config", tags=group_tags)
@cache('in-1h')
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


@router.get("/symbols", tags=group_tags)
@cache('in-1h')
def resolve_symbol(symbol: str):
    """TradingView resolveSymbol endpoint.
    
    - symbol: Trading pair symbol (e.g., 'USDM/ADA' or 'USDM_ADA')
    """
    # Normalize symbol format
    symbol_clean = symbol.strip().replace("_", "/").upper()
    
    return {
        "name": symbol_clean,
        "ticker": symbol_clean,
        "description": f"{symbol_clean} Trading Pair",
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


@router.get("/search", tags=group_tags)
@cache('in-1h')
def search_symbols(
    query: Optional[str] = None,
    exchange: Optional[str] = None,
    symbol_type: Optional[str] = None,
    limit: Optional[int] = 50,
    db: Session = Depends(get_db)
):
    """TradingView searchSymbols endpoint.
    - query: Search query string (optional)
    - exchange: Exchange filter (optional, not used currently)
    - symbol_type: Symbol type filter (optional, not used currently)
    - limit: Maximum number of results (default: 50, max: 100)
    """
    # Get distinct symbols from the database
    # Query from one of the signal tables to get available trading pairs
    f_table = tables.get('f5m')  # Use 5m table to get symbols
    
    if not f_table:
        return []
    
    search_sql = f"""
        SELECT DISTINCT symbol
        FROM {f_table}
        WHERE symbol IS NOT NULL
    """
    if query:
        query_clean = query.strip().upper().replace("'", "''")  # Escape single quotes
        search_sql += f" AND symbol LIKE '%{query_clean}%'"
    search_sql += " ORDER BY symbol"
    if limit:
        limit = max(1, min(100, limit))  # Limit between 1 and 100
        search_sql += f" LIMIT {limit}"
    try:
        results = db.execute(text(search_sql)).fetchall()
        # Format results for TradingView SearchSymbolResultItem format
        symbols = []
        for row in results:
            symbol = row.symbol if row.symbol else ''
            if symbol:
                symbol_clean = symbol.strip().replace("_", "/").upper()
                symbols.append({
                    "symbol": symbol_clean,
                    "description": f"{symbol_clean} Trading Pair",
                    "exchange": "",
                    "ticker": symbol_clean,
                    "type": "crypto"
                })
        
        return symbols
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@router.get("/history", tags=group_tags)
@cache('in-5m')
def get_bars(
    symbol: str,
    resolution: str,
    from_: int,
    to: int,
    count_back: Optional[int] = None
):
    """TradingView getBars endpoint (historical data).
    
    - symbol: Trading pair symbol (e.g., 'USDM/ADA' or 'USDM_ADA')
    - resolution: Chart resolution ('5m', '30m', '1h', '4h', '1d')
    - from_: Start timestamp in seconds
    - to: End timestamp in seconds (exclusive)
    - count_back: Required number of bars (optional, TradingView uses this)
    """
    try:
        result = get_chart_data(
            symbol=symbol,
            resolution=resolution,
            from_time=from_,
            to_time=to,
            count_back=count_back
        )
        
        # Ensure at least 2 bars as per TradingView requirements (if we have data)
        # If countBack is specified, we already handled it in get_chart_data
        if len(result) < 2 and count_back is None and len(result) > 0:
            # Return what we have - TradingView will handle it
            pass
        
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

@router.websocket("/streaming")
async def subscribe_bars(websocket: WebSocket):
    """TradingView subscribeBars/unsubscribeBars WebSocket endpoint.
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
        
    try:
        # Handle messages and send updates in a loop
        while True:
            try:
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
                            await websocket.send_json({
                                "error": f"Invalid resolution: {resolution}",
                                "subscriber_id": subscriber_id
                            })
                        else:
                            # Generate subscriber_id automatically
                            subscriber_id = generate_subscriber_id(symbol, resolution)
                            subscriptions[subscriber_id] = {
                                "symbol": symbol,
                                "resolution": resolution,
                                "last_timestamp": 0
                            }
                            await websocket.send_json({
                                "status": "subscribed",
                                "subscriber_id": subscriber_id,
                                "symbol": symbol,
                                "resolution": resolution
                            })
                    else:
                        await websocket.send_json({
                            "error": "Missing required fields: symbol or resolution",
                            "subscriber_id": ""
                        })
                
                elif action == "unsubscribe":
                    if symbol and resolution:
                        # Generate subscriber_id from symbol and resolution
                        subscriber_id = generate_subscriber_id(symbol, resolution)
                        if subscriber_id in subscriptions:
                            del subscriptions[subscriber_id]
                            await websocket.send_json({
                                "status": "unsubscribed",
                                "subscriber_id": subscriber_id,
                                "symbol": symbol,
                                "resolution": resolution
                            })
                        else:
                            await websocket.send_json({
                                "error": f"Subscription not found for subscriber_id: {subscriber_id}",
                                "subscriber_id": subscriber_id
                            })
                    else:
                        await websocket.send_json({
                            "error": "Missing required fields: symbol or resolution",
                            "subscriber_id": ""
                        })
                
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
                            count_back=1
                        )
                        
                        if result and len(result) > 0:
                            row = result[0]
                            if isinstance(row, dict):
                                row = CachedRow(row)
                            elif not isinstance(row, CachedRow):
                                print(f"Unexpected row type from get_chart_data: {type(row)}")
                                continue
                            
                            current_timestamp = int(row.timestamp) if row.timestamp else 0
                                                        
                            # Only send if this is a new bar (open_time > last_timestamp)
                            # This prevents sending duplicate bars when no new data is available
                            if last_timestamp == 0 or current_timestamp > last_timestamp:
                                # Update last_timestamp to the open_time of this bar
                                # Next query will get bars that opened after this bar
                                subscriptions[subscriber_id]["last_timestamp"] = current_timestamp
                                
                                # Send update to this specific subscriber
                                await websocket.send_json({
                                    "subscriber_id": subscriber_id,
                                    "symbol": symbol,
                                    "timestamp": current_timestamp,
                                    "open": float(row.open) if row.open is not None else 0.0,
                                    "high": float(row.high) if row.high is not None else 0.0,
                                    "low": float(row.low) if row.low is not None else 0.0,
                                    "close": float(row.close) if row.close is not None else 0.0,
                                    "volume": float(row.volume) if row.volume is not None else 0.0,
                                })
                    except Exception as e:
                        # Log error but continue
                        print(f"Error querying data for {symbol} (subscriber {subscriber_id}): {e}")
            
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

