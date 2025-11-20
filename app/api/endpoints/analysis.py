from datetime import datetime
from app.core.config import settings
import app.schemas.analysis as schemas
from app.core.router_decorated import APIRouter
from app.core.cache import cache
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, or_
from typing import List, Optional
from app.db.session import get_db, get_tables
from app.models.tokens import Token
from app.models.swaps import Swap
from app.core.dependencies import get_current_user

router = APIRouter()
tables = get_tables(settings.SCHEMA_2)
group_tags=["Api"]


@router.get("/indicators", 
            tags=group_tags,
            response_model=schemas.IndicatorsResponse)
@cache('at-e5m')
def get_indicators(
    pair: str,
    timeframe: str,
    limit: int = 100,
    from_time: int = None,
    to_time: int = None,
    indicators: str = "rsi7,rsi14,adx14,psar",
    db: Session = Depends(get_db)
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
    
    # Map timeframe to table key
    timeframe_map = {
        '5m': 'f5m',
        '30m': 'f30m',
        '1h': 'f1h',
        '4h': 'f4h',
        '1d': 'f1d',
    }
    
    timeframe_lower = timeframe.strip().lower()
    if timeframe_lower not in timeframe_map:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}. Valid values: 5m, 30m, 1h, 4h, 1d")
    
    table_key = timeframe_map[timeframe_lower]
    if table_key not in tables:
        raise HTTPException(status_code=400, detail=f"Table not found for timeframe: {timeframe}")
    
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
    indicator_list = [ind.strip().lower() for ind in indicators.split(",")] if indicators else ["rsi7", "rsi14", "adx14", "psar"]
    
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
    
    query = f"""
        SELECT 
            open_time + {timeframe_map[timeframe_lower]} as timestamp,
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
            psar=float(row.psar) if row.psar is not None else 0.0
        )
        for row in reversed(result)  # Reverse to get chronological order
    ]
    
    # Format pair for response (USDM_ADA -> USDM/ADA)
    response_pair = pair.strip().replace("_", "/").upper()
    
    return schemas.IndicatorsResponse(
        pair=response_pair,
        timeframe=timeframe_lower,
        data=data
    )


@router.get("/tokens",
            tags=group_tags,
            response_model=List[schemas.Token])
@cache('at-e5m')
def get_tokens(
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    db: Session = Depends(get_db)
) -> List[schemas.Token]:
    """Search or list available tokens
    
    - search: Search keyword to filter tokens by name or symbol (optional)
    - limit: Maximum number of records to return (optional)
    - offset: Number of records to skip (optional)
    
    OUTPUT: List of tokens with:
    - id: Onchain address
    - name: Token name
    - symbol: Token symbol
    """
    # Build query
    query = db.query(Token)
    
    # Apply search filter if provided
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Token.name.ilike(search_term),
                Token.symbol.ilike(search_term)
            )
        )
    
    # Apply offset if provided
    if offset is not None:
        offset = max(0, offset)
        query = query.offset(offset)
    
    # Apply limit if provided
    if limit is not None:
        limit = max(1, limit)
        query = query.limit(limit)
    
    # Execute query
    tokens = query.all()
    
    # Convert to response format
    return [
        schemas.Token(
            id=token.id if token.id else '',
            name=token.name if token.name else '',
            symbol=token.symbol if token.symbol else ''
        )
        for token in tokens
    ]


@router.get("/tokens/{symbol}",
            tags=group_tags,
            response_model=schemas.TokenMarketInfo)
@cache('at-e5m')
def get_token_market_info(
    symbol: str,
    db: Session = Depends(get_db)
) -> schemas.TokenMarketInfo:
    """Get token Market info
    
    - symbol: Token symbol (e.g., 'USDM')
    
    OUTPUT: Token market information with:
    - id: Onchain address
    - name: Token name
    - symbol: Token symbol
    - price: Token price in USD
    - 24h_change: Token price change in 24h (percentage)
    - 24h_low: Token lowest price in 24h
    - 24h_high: Token highest price in 24h
    - 24h_volume: Token trade volume in 24h
    """
    symbol = symbol.strip().upper()
    time_now = (int(datetime.now().timestamp()) // 300 - 1) *300
    time_24h_ago = time_now - 24 * 60 * 60
    query = f"""  
    select a.*, c.price/b.ada_price as price, c.change_24h/b.ada_price change_24h
	,d.low_24h/b.ada_price low_24h, d.high_24h/b.ada_price high_24h, d.volume_24h/b.ada_price volume_24h
    from (
        select id, name, symbol
        from proddb.tokens
        where symbol='{symbol}'
    ) a left join(
	    select close as ada_price
	    from proddb.coin_prices_5m cph
	    where symbol='USDM/ADA'
	    	and open_time = {time_now}
    ) b on true
    left join(
    	select price, price - price_24h as change_24h
        from (
            select open_time, close as price, lag(close) over (ORDER by open_time asc) price_24h
            from proddb.coin_prices_5m cph
            where symbol='{symbol}/ADA'
                and (open_time = {time_24h_ago} or open_time = {time_now})
        ) coin
        where price_24h is not null
    ) c on TRUE
    left join(   
        select min(low) low_24h, max(high) high_24h, sum(volume) volume_24h
        from proddb.coin_prices_1h cph
        where symbol='{symbol}/ADA'
		   	and open_time > {time_24h_ago}
        ) d on TRUE
    """
    token = db.execute(text(query)).fetchone()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return schemas.TokenMarketInfo(
        id=token.id if token.id else '',
        name=token.name if token.name else '',
        symbol=token.symbol if token.symbol else '',
        price=token.price if token.price else 0.0,
        change_24h=token.change_24h if token.change_24h else 0.0,
        low_24h=token.low_24h if token.low_24h else 0.0,
        high_24h=token.high_24h if token.high_24h else 0.0,
        volume_24h=token.volume_24h if token.volume_24h else 0.0
    )


@router.post("/swaps",
            tags=group_tags,
            response_model=schemas.SwapResponse)
def create_swap(
    swap_data: schemas.SwapCreate,
    db: Session = Depends(get_db),
    wallet_address: str = Depends(get_current_user)
) -> schemas.SwapResponse:
    """Creates a new swap transaction record.
    
    - transaction_id: On chain transaction ID (required)
    - from_token: Source token symbol (required)
    - to_token: Destination token symbol (required)
    - from_amount: Amount of source token (required)
    - to_amount: Amount of destination token (required)
    - price: Exchange rate (required)
    - timestamp: Transaction timestamp in seconds (optional, defaults to current time)
    
    OUTPUT:
    - transaction_id: On chain transaction ID
    - status: Transaction status ('pending', 'completed', 'failed')
    """
    # Check if transaction already exists
    existing_swap = db.query(Swap).filter(
        Swap.transaction_id == swap_data.transaction_id
    ).first()
    
    if existing_swap:
        raise HTTPException(
            status_code=400,
            detail=f"Transaction with ID '{swap_data.transaction_id}' already exists"
        )
    
    # Use current timestamp if not provided
    timestamp = swap_data.timestamp if swap_data.timestamp else int(datetime.now().timestamp())
    
    # Create new swap record
    new_swap = Swap(
        transaction_id=swap_data.transaction_id,
        user_address=wallet_address,
        from_token=swap_data.from_token,
        to_token=swap_data.to_token,
        from_amount=swap_data.from_amount,
        to_amount=swap_data.to_amount,
        price=swap_data.price,
        timestamp=timestamp,
        status='completed',  # Default to completed as per example
        user_id=None  # Optional user_id field, can be set if needed
    )
    
    try:
        db.add(new_swap)
        db.commit()
        db.refresh(new_swap)
    except Exception as e:
        db.rollback()
        print(f"Error creating swap: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create swap transaction: {str(e)}"
        )
    
    return schemas.SwapResponse(
        transaction_id=new_swap.transaction_id,
        status=new_swap.status
    )


@router.get("/swaps",
            tags=group_tags,
            response_model=schemas.SwapListResponse)
@cache('at-e5m')
def get_swaps(
    page: int = 1,
    limit: int = 20,
    from_token: Optional[str] = None,
    to_token: Optional[str] = None,
    from_time: Optional[int] = None,
    to_time: Optional[int] = None,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
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
        # Filter by user_address (wallet address) when user_id is provided
        query = query.filter(Swap.user_address == user_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    swaps = query.order_by(Swap.timestamp.desc()).offset(offset).limit(limit).all()
    
    # Convert to response format
    transactions = [
        schemas.SwapTransaction(
            transaction_id=swap.transaction_id,
            from_token=swap.from_token,
            from_amount=swap.from_amount,
            to_token=swap.to_token,
            to_amount=swap.to_amount,
            price=swap.price,
            timestamp=swap.timestamp,
            status=swap.status
        )
        for swap in swaps
    ]
    
    return schemas.SwapListResponse(
        transactions=transactions,
        total=total,
        page=page,
        limit=limit
    )
