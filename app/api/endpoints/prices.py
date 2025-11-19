import app.schemas.prices as schemas
from app.core.config import settings
from app.core.router_decorated import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from app.db.session import get_db, get_tables

router = APIRouter()
tables = get_tables(settings.SCHEMA_2)
group_tags=["Api"]

@router.get("/latest-prices",
            tags=group_tags,
            response_model=List[schemas.LatestPriceV2])
def get_latest_prices(offset:int=None, limit:int=None, db: Session = Depends(get_db)) -> List[schemas.LatestPriceV2]:
    """ Get the latest prices of coins
    - offset: int: number of records to skip, min 0
    - limit: int: number of records to return, min 1
    """
    str_limit = ''
    if offset and limit:
        offset = max(0, offset)
        limit = max(1, limit)
        str_limit = f'limit {limit} offset {offset}'

    table_5m = tables['p5m']
    table_1h = tables['p1h']

    #  sd table_1h sl bản ghi it hơn table_5m toi uu query hon 0.35s -> 0.27s
    query = f"""
    select coin, time, price,
        (price - base_price) price_change,
        round(((price - base_price)*100/base_price)::numeric, 2) as price_change_percent
    from (  	
        select left(a.symbol, char_length(a.symbol) - 4) as coin,
            a.time,
            a.close as price,
            COALESCE(b.open, a.close) base_price
        from (
            select symbol, time, close
            from (
                select symbol, open_time + 300 as time, close, row_number() over (PARTITION by symbol order by open_time desc) AS r
                from {table_5m}
                where open_time > extract(epoch from now())::bigint - 1800  -- 30 p
            ) a
            where r=1
        ) a  -- guarantee haveing the price at 24h ago
        left join (
            select symbol, open
                from (
                    select symbol, open, row_number() over (PARTITION by symbol order by open_time asc) AS r
                    from {table_1h}
                    where open_time > extract(epoch from now())::bigint - 25*3600  -- 25 h
                ) b
            where r=1
        ) b on b.symbol=a.symbol
        order by a.symbol
        {str_limit}
    ) c    
    """
    result = db.execute(text(query)).fetchall()
    
    if not result:
        raise HTTPException(status_code=404, detail="No data found")
    
    return [
        schemas.LatestPriceV2(
            coin=row.coin,
            time=row.time,
            price=row.price,
            price_change=row.price_change,
            price_change_percent=row.price_change_percent
            )
        for row in result
    ]


@router.get("/coin-prices",
            tags=group_tags,
            response_model=List[schemas.CoinPrice])
def get_coin_prices(offset:int=None, limit:int=None, db: Session = Depends(get_db)) -> List[schemas.CoinPrice]:
    """ Get the price of coins
    - offset: int: number of records to skip, default 0, min 0
    - limit: int: number of records to return, default 20, min 1, max 100
    """
    str_limit = ''
    if offset and limit:
        offset = max(0, offset)
        limit = max(1, limit)
        str_limit = f'limit {limit} offset {offset}'
    # reduce query time from ~0.8s to 0.5s
    table_5m = tables['p5m']
    query = f"""
    -- all data needed for 24h
        with price_24h as (
            select symbol, time, to_timestamp(time) , price, r,
            	row_number() over (PARTITION by symbol order by r desc) AS rt
            from (
                select *
                from (
                    select symbol, to_timestamp(open_time) , open_time + 300 as time, close as price,
                        row_number() over (PARTITION by symbol order by open_time desc) AS r
                    from {table_5m}
                    where open_time > (extract(epoch from now())::bigint - 25*3600) 
                    	and ((extract(epoch from now())::bigint - open_time) / 300) % 12 = 11 -- all price at n hours diff 
                ) a
                where r <= 25 -- 24h
            ) a
        )
    -- select the needed rows and columns for calculation
        SELECT l.symbol, l.price,
            ROUND((((l.price - f.price) / f.price) * 100)::numeric, 2) AS percent_change,
            g.list_prices
        from (select symbol, time, price from price_24h where r = 1 {str_limit}) l
        inner join (select symbol, price from price_24h where rt = 1) f on f.symbol = l.symbol
        inner join (
            select symbol, string_agg(price::text, ', ' ORDER BY rt) AS list_prices
            from price_24h
            group by symbol
        ) g on g.symbol = l.symbol
    """
    try:
        result = db.execute(text(query)).fetchall()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Query data error")

    return [
        schemas.CoinPrice(
            symbol=row.symbol,
            price=row.price,
            price_change=row.percent_change,
            list_prices=[float(price.strip()) for price in row.list_prices.split(",")]
        )
        for row in result
    ]


@router.get("/chart/indicators",
            tags=group_tags,
            response_model=List[schemas.Indicators])
def get_kline(symbol:str, from_time:int, to_time:int, timeframe:str, db: Session = Depends(get_db)) -> List[schemas.Indicators]:
    """ Chart
    - symbol: str: coin symbol
    - from_time: int: start time in seconds
    - to_time: int: end time in seconds
    - timeframe: str: time timeframe (5m, 10m, 15m, 30m, 1h, 4h, 1D)
    """
    symbol = symbol.strip().upper()
    from_time = int(from_time)
    to_time = int(to_time)
    timeframe = timeframe.strip().lower()
    table_name = tables['f1h']
    ts = 24*3600
    if timeframe == "5m":
        table_name = tables['f5m']
        ts = 300
    elif timeframe == "10m":
        table_name = tables['f10m']
        ts = 600
    elif timeframe == "15m":
        table_name = tables['f15m']
        ts = 900
    elif timeframe == "30m":
        table_name = tables['f30m']
        ts = 1800
    elif timeframe == "1h":
        table_name = tables['f1h']
        ts = 3600
    elif timeframe == "4h":
        table_name = tables['f4h']
        ts = 4*3600
    else:  # timeframe == "1D":
        table_name = tables['f1d']
        ts = 24*3600

    query = f"""
    select open_time as timestamp, symbol, volume, trades, open, close, low, high
		, CASE WHEN close < pc THEN 'UP' ELSE 'DOWN' END trend1
		, CASE WHEN close < pc_3 THEN 'UP' ELSE 'DOWN' END trend3
		, CASE WHEN close < pc_7 THEN 'UP' ELSE 'DOWN' END trend7
		, CASE WHEN close < pc_14 THEN 'UP' ELSE 'DOWN' END trend14
		, rsi7, rsi14
		, CASE WHEN (rsi7 <= 30 and rsi7 < rsi7_p and rsi7 < rsi7_a) THEN 1 ELSE 0 END rsi7_epl
		, CASE WHEN (rsi7 >= 70 and rsi7 > rsi7_p and rsi7 < rsi7_a) THEN 1 ELSE 0 END rsi7_eph
		, CASE WHEN (rsi14 <= 30 and rsi14 < rsi14_p and rsi14 < rsi14_a) THEN 1 ELSE 0 END rsi14_epl
		, CASE WHEN (rsi14 >= 70 and rsi14 > rsi14_p and rsi14 < rsi14_a) THEN 1 ELSE 0 END rsi14_eph
		, adx
		, CASE WHEN ((adx < adx_p and adx < adx_a) or (adx > adx_p and adx > adx_a)) THEN 1 ELSE 0 END adx_ep
		, case
			WHEN (di14_line_cross = 1) THEN 2
			WHEN ((di14_p-di14_n)*(2*di14_p-0.7*di14_p1-0.3*di14_p2 - 2*di14_n+0.7*di14_n1+0.3*di14_n2) <= 0) THEN 1
			ELSE 0
		end di_cross
		, psar
		, case
			when af = 0.02 then psar_type
            when (r=1 and (psar_type='UP' and next_psar>low)) then 'DOWN-WARNING'
            when (r=1 and (psar_type='DOWN' and next_psar<high)) then 'UP-WARNING'
			ELSE psar_type
        end psar_trend
        from (
            select open_time,symbol, volume, num_trades trades
                , open,close,low,high, pc
                , lead(close,3) over (PARTITION by symbol order by open_time desc) AS pc_3
                , lead(close,7) over (PARTITION by symbol order by open_time desc) AS pc_7
                , lead(close,14) over (PARTITION by symbol order by open_time desc) AS pc_14
                , rsi7
                , lead(rsi7) over (PARTITION by symbol order by open_time desc) AS rsi7_p
                , lag(rsi7) over (PARTITION by symbol order by open_time desc) AS rsi7_a
                , rsi14
                , lead(rsi14) over (PARTITION by symbol order by open_time desc) AS rsi14_p
                , lag(rsi14) over (PARTITION by symbol order by open_time desc) AS rsi14_a
                , adx
                , lead(adx) over (PARTITION by symbol order by open_time desc) AS adx_p
                , lag(adx) over (PARTITION by symbol order by open_time desc) AS adx_a
                , di14_p, di14_n, di14_line_cross
                , lead(di14_p) over (PARTITION by symbol order by open_time desc) AS di14_p1
                , lead(di14_p,2) over (PARTITION by symbol order by open_time desc) AS di14_p2
                , lead(di14_n) over (PARTITION by symbol order by open_time desc) AS di14_n1
                , lead(di14_n,2) over (PARTITION by symbol order by open_time desc) AS di14_n2
                , psar_type, psar, af
                , psar+LEAST(af+0.02,0.2)*(ep-psar) as next_psar
            from {table_name}
            where open_time >= {from_time} and open_time < {to_time}
                and symbol = '{symbol}'
        ) a
        order by open_time asc
    """
    result = db.execute(text(query)).fetchall()
    if not result:
        return []
    
    return [
        schemas.Indicators(
            timestamp=row.timestamp + ts,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            trades=row.trades,
            trend1=row.trend1,
            trend3=row.trend3,
            trend7=row.trend7,
            trend14=row.trend14,
            rsi7=row.rsi7,
            rsi14=row.rsi14,
            rsi7_epl=row.rsi7_epl,
            rsi7_eph=row.rsi7_eph,
            rsi14_epl=row.rsi14_epl,
            rsi14_eph=row.rsi14_eph,
            adx=row.adx,
            adx_ep=row.adx_ep,
            di_cross=row.di_cross,
            psar=row.psar,
            psar_trend=row.psar_trend
            )
        for row in result
    ]