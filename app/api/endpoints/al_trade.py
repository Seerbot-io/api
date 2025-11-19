import os
import pandas as pd
import app.schemas.al_trade as schemas
from app.core.config import settings

from app.core.router_decorated import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from app.db.session import get_db, get_tables
from datetime import datetime

os.environ['TZ'] = 'UTC'
router = APIRouter()
tables = get_tables(settings.SCHEMA_2)

periords = {
    '5m': 300,
    '10m': 600,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '4h': 14400,
    '1d': 86400,
    '1D': 86400,
    }

order_periords = {
    '5m': 21600,    # 6 hours
    '10m': 21600,    # 6 hours
    '15m': 86400,    # 1 days
    '30m': 86400,    # 1 days
    '1h': 86400,    # 1 days
    '4h': 2592000,    # 30 days
    '1d': 2592000,    # 30 days
    '1D': 2592000,    # 30 days
}

group_tags=["Api"]

@router.get("/top-over-sold", 
            tags=group_tags,
            response_model=List[schemas.RSIHeatMap])
def get_tos(heatMapType: str, timeframe: str, db: Session = Depends(get_db)) -> List[schemas.RSIHeatMap]:
    """ GET top coins are oversold by the RSI indicator. In case it does not have recent data, it will get the latest data
    PARAM:
    - heatmaptype: rsi window example rsi7|rsi14 (auto rsi7)
    - timeframe: 5m|30m|1h|4h|1D (auto 1D)
    """
    heatMapType = heatMapType.strip().lower()
    time_range = 0
    if heatMapType not in ("rsi7","rsi14"):
        heatMapType = "rsi7"
    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    time_range = periords.get(timeframe, 86400)*7
    rsi_period = heatMapType.lower()

    query = f"""
        select symbol, rsi, rsi_ep_l as rsi_bottom, rsi_ep_h as rsi_top, close, low, high, date_created
        from (
            select 
                symbol,
                {rsi_period} as rsi,
                close,
                low,
                high,
                row_number() over (PARTITION by symbol order by open_time desc) AS r,
                min({rsi_period}) over (PARTITION by symbol) AS rsi_ep_l,
                max({rsi_period}) over (PARTITION by symbol) AS rsi_ep_h,
                update_time as date_created
            from {table_name}
            where {rsi_period} is not null
            and symbol like '%USDT'
            and open_time >= (extract(epoch from now())::bigint-{time_range})  -- 7 candes
        ) a
        where  r=1 and rsi < 30
        order by rsi asc
    """
    result = []
    try:
        result = db.execute(text(query), {
            "rsi_period": rsi_period,
            }).fetchall()
    except Exception as e:
        print("error:", e)

    return [
        schemas.RSIHeatMap(
            symbol=row.symbol,
            rsi=row.rsi,
            close=row.close, 
            high=row.high, 
            low=row.low, 
            rsi_bottom=row.rsi_bottom,
            rsi_top=row.rsi_top,
            dateCreated=str(row.date_created)
        )
        for row in result
    ]

@router.get("/top-over-bought", 
            tags=group_tags,
            response_model=List[schemas.RSIHeatMap])
def get_tob(heatMapType: str, timeframe: str, db: Session = Depends(get_db)) -> List[schemas.RSIHeatMap]:  
    """ GET top coins are overbought by the RSI indicator. In case it does not have recent data, it will get the latest data
    PARAM:
    - heatmaptype: rsi window example rsi7|rsi14 (auto rsi7)
    - timeframe: 5m|30m|1h|4h|1D (auto 1D)
    """
    heatMapType = heatMapType.strip().lower()
    time_range = 0
    if heatMapType not in ("rsi7","rsi14"):
        heatMapType = "rsi7"
    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    time_range = periords.get(timeframe, 86400)*7

    rsi_period = heatMapType.lower()

    query = f"""
        select symbol, rsi_ep_l as rsi_bottom, rsi_ep_h as rsi_top, rsi, close, low, high, date_created
        from (
            select 
                symbol,
                {rsi_period} as rsi,
                close,
                low,
                high,
                row_number() over (PARTITION by symbol order by open_time desc) AS r,
                min({rsi_period}) over (PARTITION by symbol) AS rsi_ep_l,
                max({rsi_period}) over (PARTITION by symbol) AS rsi_ep_h,
                update_time as date_created
            from {table_name}
            where {rsi_period} is not null
            and symbol like '%USDT'
            and open_time > (extract(epoch from now())::bigint-{time_range})  -- 7 candes
            ) a
        where  r=1 and rsi > 70
        order by rsi desc
    """
    result = []
    try:
        result = db.execute(text(query),{
            "rsi_period": rsi_period,
        }).fetchall()
    except Exception as e:
        print("error:", e)
   
    return [
        schemas.RSIHeatMap(
            symbol=row.symbol,
            rsi=row.rsi,
            close=row.close, 
            high=row.high, 
            low=row.low,
            rsi_bottom=row.rsi_bottom,
            rsi_top=row.rsi_top,
            dateCreated=str(row.date_created)
        )
        for row in result
    ]

@router.get("/chart-data", 
            tags=group_tags,
            response_model=List[schemas.ChartData])
def get_chart_data_v2_2(heatMapType: str, timeframe: str, db: Session = Depends(get_db)) -> List[schemas.ChartData]:
    """ GET RSI heat map data. Incase not having recent data, it will get latest data
    PARAM:
    - heatMapType: RSI Window example rsi7|rsi14 (auto rsi7)
    - timeframe: 5m|30m|1h|4h|1D (auto 1D)
    """
    heatMapType = heatMapType.strip().lower()
    time_range = 0
    if heatMapType not in ("rsi7","rsi14"):
        heatMapType = "rsi7"
    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    time_range = periords.get(timeframe, 86400)*7
    rsi_period = heatMapType.strip().lower()

    query = f"""
        select symbol,
            rsi,
            percentage_change
        from (
        SELECT symbol, open_time,
            {rsi_period} AS rsi,
            ({rsi_period} - lead({rsi_period}) over (PARTITION by symbol order by open_time desc)) AS percentage_change,
            row_number() over (PARTITION by symbol order by open_time desc) AS r
        FROM {table_name}
        WHERE symbol LIKE '%USDT'
        	and {rsi_period} is not null
            and open_time > (extract(epoch from now())::bigint-{time_range})  -- 7 candes
        ) a
        where r=1 and rsi is not null and percentage_change is not null
        ORDER BY symbol asc
    """

    result = []
    try:
        result = db.execute(text(query)).fetchall()
    except Exception as e:
        print("error:", e)

    return [
        schemas.ChartData(
            symbol=row.symbol,
            rsi=row.rsi,
            percentage_change=row.percentage_change
        )
        for row in result
    ]


@router.get("/original-pair-list", 
            tags=group_tags,
            response_model=List[schemas.OriSymbol])
def get_original_pair_list(timeframe: str, db: Session = Depends(get_db)) -> List[schemas.OriSymbol]:
    """
    PARAM:
    - timeframe: 4h | 1h | 30m | 1D
    """
    timeframe = timeframe.strip()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])

    query = f"""
                SELECT  symbol2 as symbol, MAX(start_date2) AS discovered_symbol_time
                FROM {table_name}
                GROUP BY symbol2
                order by symbol2
            """
    result = []
    try:
        result = db.execute(text(query)).fetchall()
    except Exception as e:
        print("error:", e)
    return [
        schemas.OriSymbol(
            symbol=row.symbol,
            discoveredOn=str(row.discovered_symbol_time)
        )
        for row in result
    ]

# @router.get("/fibonacci-info",
#             tags=group_tags,
#             response_model=schemas.RefSymbol)
# def get_fibo_info(originalPair, timeframe, db: Session = Depends(get_db)) -> schemas.RefSymbol:
#     """
#     PARAM:
#     - originalPair: example BTCUSDT, ...
#     - timeframe: 4h | 1h | 1D
#     """
#     originalPair = originalPair.strip()
#     timeframe = timeframe.strip()
#     if timeframe == "1h":
#         table_name = SIGNAL_1
#     elif timeframe == "4h":
#         table_name = SIGNAL_4
#     else:
#         table_name = SIGNAL_24

#     query = f"""
#         select original_symbol, original_start_date, original_end_date, original_prices, original_fibonacci, similar_symbol, similar_start_date, similar_end_date, similar_prices, similar_fibonacci
#         FROM (
#         SELECT 
#             pm.symbol2 as original_symbol, 
#             pm.start_date2 as original_start_date, 
#             pm.end_date as original_end_date, 
#             pm.prices2 as original_prices, 
#             pm.s2_norm as original_fibonacci, 
#             pm.symbol1 as similar_symbol, 
#             pm.start_date1 as similar_start_date, 
#             pm.end_date as similar_end_date, 
#             pm.prices1 as similar_prices, 
#             pm.s1_norm as similar_fibonacci,
#             row_number() over (PARTITION by symbol1 order by start_date2 desc) AS r
#         FROM {table_name} pm 
#         WHERE pm.symbol2 = :originalPair
#             and s2_norm is not null and s1_norm is not null
#             -- and start_date2 >= (extract(epoch from now())::bigint - 30*24*3600)  -- 7 days
#         ) a
#         where r=1 
#     """
#     result = []
#     try:
#         result = db.execute(text(query),{
#             'originalPair': originalPair
#             }).fetchall()  #
#         if not result or len(result) == 0:
#             return HTTPException(status_code=404, detail="No data found")
#     except Exception as e:
#         print("error:", e)
        
#     r = result[0]
#     res = schemas.RefSymbol(
#         originalSymbol=r.original_symbol,
#         originalStartDate=r.original_start_date, 
#         originalEndDate=r.original_end_date,
#         originalPrices=str_to_list(r.original_prices), 
#         originalFibonacci=str_to_list(r.similar_end_date),
#         similarSymbols=[str(r.similar_symbol)], 
#         similarStartDates=[str(r.similar_start_date)],
#         similarEndDates=[str(r.similar_end_date)],
#         similarPrices=str_to_list2d(r.similar_prices),
#         similarFibonacci=str_to_list2d(r.similar_fibonacci),
#     )
#     return res


@router.get("/trend-predict/trend-reversal-signal/adx/list", 
            tags=group_tags,
            response_model=List[schemas.PredictedTrend]
            )
def get_adx_reversal_list(timeframe: str, db: Session = Depends(get_db)) -> List[schemas.PredictedTrend]:
    """
    PARAM:
    - timeframe: 1h | 4h | 1D
    """
    # window: 5  - khung tg danh gia trend co the cho phep tuy chinh (3 - 9)
    window = 5
    # surround = window // 2
    behind = window - 1

    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    periord = periords.get(timeframe, 86400)

    time_range = (2*window+5) * periord # at least 2 times of window, the additional 5 is for condition in where data it's not up to date

    query = f"""
    select open_time, symbol, adx_type,
        CASE 
            when adx_type in ('TOP', 'BOTTOM') and trend = 'UP' then 'DOWN'
            when adx_type in ('TOP', 'BOTTOM') and trend = 'DOWN' then 'UP'
            ELSE trend
        END predicted_trend
        from (
    SELECT *, 
        case 
            when adx = adx_h then 'TOP' 
            when adx = adx_l then 'BOTTOM'
            ELSE '' 
        end adx_type, 
        case 
            when c_trend+l_trend+h_trend >= 2 then 'UP'
            ELSE 'DOWN' 
        end trend  -- price trend
        , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as ex_r
        from (
                SELECT open_time, symbol
                    , adx
                    , max(adx) over (PARTITION by symbol order by open_time desc ROWS  BETWEEN {behind} PRECEDING AND 2 FOLLOWING) as adx_h
                    , min(adx) over (PARTITION by symbol order by open_time desc ROWS  BETWEEN {behind} PRECEDING AND 2 FOLLOWING) as adx_l
                    , case when (close > AVG(close) over (PARTITION by symbol order by open_time desc ROWS {behind} PRECEDING)) then  1 else 0 end as c_trend
                    , case when (low > AVG(low) over (PARTITION by symbol order by open_time desc ROWS {behind} PRECEDING)) then  1 else 0 end as l_trend
                    , case when (high > AVG(high) over (PARTITION by symbol order by open_time desc ROWS {behind} PRECEDING)) then  1 else 0 end as h_trend
                    , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as r
                FROM {table_name}
                where open_time > (extract(epoch from now())::bigint - {time_range})  -- 5 cycles
        ) a
        where r>1 and r<6 and (adx = adx_h or adx = adx_l) -- only get signal in 5 nearest cycle and not from last one
    ) b
    where ex_r = 1
    order by open_time desc
    """

    data = []
    try: 
        result = db.execute(text(query)).fetchall()
        data = [
        schemas.PredictedTrend(
            open_time=row.open_time, 
            symbol=row.symbol,
            predicted_trend=row.predicted_trend
            )
        for row in result
        ]
    except Exception as e:
        print("error", e)
    return data


@router.get("/trend-predict/trend-reversal-signal/adx-chart/{symbol}", 
            tags=group_tags,
            response_model=List[schemas.CandleADX]
            )
def get_adx_chart(symbol: str, timeframe: str, limit: int = 24, db: Session = Depends(get_db)) -> List[schemas.CandleADX]:
    """
    PARAM:
    - timeframe: 1h | 4h | 1D
    """
    # window: 5  - khung tg danh gia trend co the cho phep tuy chinh (3 - 9)
    window = 5
    # surround = window // 2
    behind = window - 1

    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    periord = periords.get(timeframe, 86400)
    time_range = (limit + 2) * periord

    limit = 5 if int(limit) <= 5 else int(limit) 

    query = f"""
    select open_time, open, high, low, close, volume, adx
		, CASE 
            when adx_type in ('TOP', 'BOTTOM') and trend = 'UP' then 'DOWN'
            when adx_type in ('TOP', 'BOTTOM') and trend = 'DOWN' then 'UP'
            ELSE ''
        END predicted_trend
        from (
    SELECT *, 
        case 
            when adx_check = 3 and adx = adx_h then 'TOP'
            when adx_check = 3 and adx = adx_l then 'BOTTOM'
            ELSE '' 
        end adx_type, 
        case 
            when c_trend+l_trend+h_trend >= 2 then 'UP'
            ELSE 'DOWN' 
        end trend  -- price trend
        , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as ex_r
        from (
                SELECT open_time, symbol, volume
					, open, high, low, close
                    , adx
                    , max(adx) over (PARTITION by symbol order by open_time desc ROWS  BETWEEN {behind} PRECEDING AND 2 FOLLOWING) as adx_h
                    , min(adx) over (PARTITION by symbol order by open_time desc ROWS  BETWEEN {behind} PRECEDING AND 2 FOLLOWING) as adx_l                    
                    , case when (close > AVG(close) over (PARTITION by symbol order by open_time desc ROWS {behind} PRECEDING)) then  1 else 0 end as c_trend
                    , case when (low > AVG(low) over (PARTITION by symbol order by open_time desc ROWS {behind} PRECEDING)) then  1 else 0 end as l_trend
                    , case when (high > AVG(high) over (PARTITION by symbol order by open_time desc ROWS {behind} PRECEDING)) then  1 else 0 end as h_trend
     				, count(adx) over (PARTITION by symbol order by open_time desc ROWS  BETWEEN 1 PRECEDING AND 1 FOLLOWING) as adx_check -- to check not first/last row, if that < 3
                    , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as r
                FROM {table_name}
                where symbol = '{symbol}'
                    and open_time > (extract(epoch from now())::bigint - {time_range})
        ) a
        limit {limit}
    ) b
    order by open_time asc
    """
    
    top = None
    bottom = None
    data = []
    try: 
        # Check the slope to make sure there are no sharp turns.
        result = db.execute(text(query)).fetchall()
        for i,row in enumerate(result):
            if row.predicted_trend == "DOWN":
                bottom = None
                if top is not None:
                    if row.high < top[1]:
                        data[top[0]].predicted_trend = ""
                        top = (i, row.high)
                    else:
                        row.predicted_trend = ""
                else:
                    top = (i, row.high)
            elif row.predicted_trend == "UP":
                top = None
                if bottom is not None:
                    if row.low > bottom[1]:
                        data[bottom[0]].predicted_trend = ""
                        bottom = (i, row.low)
                    else:
                        row.predicted_trend = ""
                else:
                    bottom = (i, row.low)
            data.append(schemas.CandleADX(
                time=row.open_time,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                adx=row.adx,
                predicted_trend=row.predicted_trend
                ))
    except Exception as e:
        print("error", e)
    return data


@router.get("/trend-predict/trend-reversal-signal/psar/list", 
            tags=group_tags,
            response_model=List[schemas.PredictedTrend]
            )
def get_psar_reversal_list(timeframe: str, db: Session = Depends(get_db)) -> List[schemas.PredictedTrend]:
    """
    PARAM:
    - timeframe: 1h | 4h | 1D
    """
    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    periord = periords.get(timeframe, 86400)
    
    time_range = 5 * periord  # 5 cycles
    query = f"""
    SELECT open_time, symbol, predicted_trend
    from (
        SELECT open_time, symbol, predicted_trend
            , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as r
        from(
            SELECT open_time, symbol , r, psar_type, psar, next_psar, af, high, low
                , case
                    when af = 0.02 then psar_type
                    when (r=1 and (psar_type='UP' and next_psar>low)) then 'DOWN-WARNING'
                    when (r=1 and (psar_type='DOWN' and next_psar<high)) then 'UP-WARNING'
                end predicted_trend
            from (
                SELECT open_time, symbol, af, high, low, psar_type, psar
                    , psar+LEAST(af+0.02,0.2)*(ep-psar) as next_psar
                    , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as r
                FROM {table_name}
                where open_time > (extract(epoch from now())::bigint - {time_range}) 
            ) a
        ) b
        WHERE predicted_trend is not NULL
    ) c
    where r=1
    """
    data = []
    try: 
        result = db.execute(text(query)).fetchall()
        data = [
        schemas.PredictedTrend(
            open_time=row.open_time, 
            symbol=row.symbol,
            predicted_trend=row.predicted_trend
            )
        for row in result
        ]
    except Exception as e:
        print("error", e)
    return data


@router.get("/trend-predict/trend-reversal-signal/psar-chart/{symbol}", 
            tags=group_tags,
            response_model=List[schemas.CandlePSAR]
            )
def get_psar_chart(symbol: str, timeframe: str, limit: int = 24, db: Session = Depends(get_db)) -> List[schemas.CandlePSAR]:
    """
    PARAM:
    - timeframe: 1h | 4h | 1D
    """
    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().lower()
    table_name = tables.get(f'f{timeframe}', tables['f1D'])
    periord = periords.get(timeframe, 86400)
    time_range = (limit + 2) * periord

    limit = 5 if int(limit) <= 5 else int(limit) 
    query = f"""
    SELECT open_time, open, high, low, close, volume, psar
        , case
            when (r=1 and (psar_type='UP' and next_psar>low)) then 'DOWN-WARNING'
            when (r=1 and (psar_type='DOWN' and next_psar<high)) then 'UP-WARNING'
            else psar_type
        end predicted_trend
    from (
        SELECT open_time, symbol, volume, af, open, close, high, low, psar_type, psar
            , psar+LEAST(af+0.02,0.2)*(ep-psar) as next_psar
            , ROW_NUMBER() over (PARTITION by symbol order by open_time desc) as r
        FROM {table_name}
        WHERE symbol='{symbol}' and open_time > extract(epoch from now())::bigint - {time_range}
    ) a
    order by open_time asc
    """
    data = []
    try: 
        result = db.execute(text(query)).fetchall()
        data = [
        schemas.CandlePSAR(
            time=row.open_time,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            psar=row.psar,
            predicted_trend=row.predicted_trend
            )
        for row in result
        ]
    except Exception as e:
        print("error", e)
    return data

# todo: fix feature symbols and group_by
def _hold_strategy(start_time:str, last_time:str, o_strat:str|list, timeframe: str, orders_table:str, signal_table:str, symbols:str|list=None, group_by:str=None) -> str:
    """PARAM: 
     - start_time: first session time
     - last_time: last session time
     - o_strat: strategy for take order
     - orders_table: ORDERS
     - signal_table: SIGNAL_...
    """
    add_data = """
    union (
        SELECT symbol, '{strategy}' as strategy, open_time, 'TAKE_PROFIT' as "order", close as price
        from {signal_table} fcsh 
        where open_time = {last_time}
    )
    """
    sql_orders =  """
        select symbol, strategy, open_time, "order", price
        from {orders_table} tos 
        where {strategy}
            and timeframe = '{timeframe}' 
            and open_time >= {start_time} 
            and open_time <= {last_time}
    """
    strats = ''
    take_profit_data = ''
    if isinstance(o_strat, str):
        strats = f"strategy = '{o_strat}'"
        take_profit_data = add_data.format(
            signal_table=signal_table,
            strategy=o_strat,
            last_time=last_time,
        )
    else:
        strats = "strategy in ('"
        take_profit_data = ""
        for strat in o_strat:
            strats += "','".join(o_strat)
            take_profit_data += add_data.format(
                signal_table=signal_table,
                strategy=strat,
                last_time=last_time,
            )
        strats += "')"
    orders_data = sql_orders.format(
        orders_table=orders_table,
        strategy=strats,
        timeframe=timeframe,
        start_time=start_time,
        last_time=last_time,
    )
    data_query = orders_data + take_profit_data

    # TO DO: calculate winrate formulation 
    sql = f"""
    WITH orders AS (
        {data_query}
    )
    SELECT symbol, strategy, revalue, total_volumn, num_order, 
        revalue*100/(total_volumn/ num_order) AS roi, 
        win_count * 100.0 / (num_order-1) AS win_rate 
    FROM (    
        SELECT symbol, strategy,
            SUM(money) AS revalue, 
            SUM(price) AS total_volumn, 
            count(1) AS num_order,
            SUM(
                CASE 
                    WHEN "order"= 'SELL' AND order_p = 'BUY' AND (price - prev_price) > 0 THEN 1
                    WHEN "order"= 'BUY' AND order_p = 'SELL' AND (prev_price - price) > 0 THEN 1
                    WHEN "order"= 'TAKE_PROFIT' AND order_p = 'SELL' AND (prev_price - price) > 0 THEN 1
     			    WHEN "order"= 'TAKE_PROFIT' AND order_p = 'BUY' AND (price - prev_price) > 0 THEN 1
                    else 0 
                END
            ) AS win_count
        FROM(
            SELECT *, 
                CASE
                    WHEN "order"= 'BUY' THEN - price 
                    WHEN "order"= 'SELL' THEN price
                    WHEN "order"= 'TAKE_PROFIT' AND order_p = 'BUY' THEN price
                    WHEN "order"= 'TAKE_PROFIT' AND order_p = 'SELL' THEN - price        
                end AS money,
                LAG(price, 1, NULL) over (PARTITION BY symbol order by open_time asc) as prev_price,
                ROW_NUMBER() OVER (PARTITION BY symbol order BY open_time asc) AS order_no
            FROM (
                SELECT symbol, strategy, open_time, "order", price
                        , LAG("order",1,'') OVER (PARTITION BY symbol order BY open_time asc) AS order_p
                FROM orders
            )  a
            WHERE order_p <> "order" 
        ) a
        WHERE NOT(a.order='TAKE_PROFIT' AND (a.order_no % 2)=1) 
        GROUP BY symbol, strategy
    ) a
    where num_order > 1
    """
    return sql


def _sess_strategy(start_time:str, last_time:str, o_strat:str|list, tp_strat: str, timeframe: str, orders_table:str=None, symbols:str|list=None, group_by:str=None) -> str:
    sess_mapping = {
        "sess1": "close_1",
        "sess2": "close_2",
        "sess3": "close_3",
        "sess4": "close_4",
        "sess5": "close_5",
        "sess6": "close_6",
        "sess7": "close_7",
        "sess8": "close_8",
    }
    # select_edit = '"all" as symbol, "all" as strategy,'
    select_symbol = 'symbol,'
    select_strategy = 'strategy,'
    strat_sql = ""
    if isinstance(o_strat, list):
        strat_sql = f"and strategy in ('" + "','".join(o_strat)+"')"
        select_strategy = "'all' as strategy,"
    elif isinstance(o_strat, str):
        strat_sql = f"and strategy = '{o_strat}'"
    else:
        raise ValueError("o_strat must be a string or a list of strings")
    
    symbol_cond = ""
    if symbols is not None:
        if isinstance(symbols, str):
            symbol_cond += f"and symbol = '{symbols.strip().upper()}'"
        elif isinstance(symbols, list):
            symbol_cond += f"and symbol in ('"+"','".join([s.strip().upper() for s in symbols])+ "')"
            select_symbol = "'all' as symbol,"
        else:
            raise ValueError("symbols must be a string")
    else:
        select_symbol = "'all' as symbol,"

    group_by = group_by.strip().lower() if group_by else 'both'
    group_sql = ''
    if group_by in ('strategy', 'symbol', 'both'):
        if group_by in 'strategy':
            select_strategy = 'strategy,'
        elif group_by == 'symbol':
            select_symbol = 'symbol,'
        else:
            select_strategy = 'strategy,'
            select_symbol = 'symbol,'
            group_by = "symbol, strategy"
        group_sql = f"GROUP BY {group_by}"

    if tp_strat not in sess_mapping:
        raise ValueError(f"Invalid session: {tp_strat}. Must be one of {list(sess_mapping.keys())}")

    close_col = sess_mapping[tp_strat]  
    
    sess_tb = tables.get('tp_by_sess') # todo: change to use on parameters

    sql = f"""
    WITH orders AS (
        select symbol, strategy, open_time, "order", price,  {close_col} c
        from {sess_tb} 
        where timeframe = '{timeframe}' 
            and open_time >= {start_time} 
            and open_time <= {last_time}
            {strat_sql}
            {symbol_cond}
    )
    SELECT {select_symbol} {select_strategy}
        SUM(CASE 
                WHEN "order" = 'BUY' THEN -price 
                WHEN "order" = 'SELL' THEN price 
                ELSE 0 
            END) AS revalue,
        SUM(price) AS total_volumn,
        COUNT(*) AS num_order,
        ROUND((SUM(CASE
                    WHEN "order" = 'BUY' AND c - price > 0 THEN 1  
                    WHEN "order" = 'SELL' AND price - c > 0 THEN 1  
                    ELSE 0
                  END)::numeric / NULLIF(COUNT(*), 0) * 100), 2) AS win_rate,
        ROUND((SUM(CASE
                    WHEN "order" = 'BUY' THEN c - price  
                    WHEN "order" = 'SELL' THEN price - c  
                    ELSE 0
                END)::numeric * 100 / NULLIF(SUM(price)::numeric, 0)), 2) AS roi
    FROM orders
    {group_sql}
    ORDER BY symbol, strategy
    """
    return sql


def strategy(o_strat:str|list, tp_strat:str|list, timeframe: str, start_time:str, last_time:str, symbols:str|list=None, group_by:str=None):
    """
    tp_strat: hold|sess4|sess8|lim1sess4|lim1sess8 
    """
    signal_table = tables.get(f'f{timeframe}', tables['f1D'])

    if tp_strat == "hold":
        sql = _hold_strategy(
            start_time=start_time,
            last_time=last_time,
            o_strat=o_strat,
            timeframe=timeframe,
            orders_table=tables['orders'],
            signal_table=signal_table,
            symbols=symbols,
            group_by=group_by
            )
    elif tp_strat.startswith("sess"):
        sql = _sess_strategy(
            start_time=start_time,
            last_time=last_time,
            o_strat=o_strat,
            tp_strat=tp_strat,
            timeframe=timeframe,
            orders_table=tables['orders'],
            symbols=symbols,
            group_by=group_by
            )
    return sql
    
@router.get("/validate/indicators/{indicator}", 
            tags=group_tags,
            response_model=List[schemas.TradeReport]
            )
def val_indicator(indicator:str, timeframe: str, num_sessions:int,tp_strat:str, db: Session = Depends(get_db)) -> List[schemas.TradeReport]:
    """
    PARAM:
     - indicator: rsi7|rsi14|adx
     - timeframe: 5m|30m|1h|4h|1D (auto 1D)
     - tp_strat: hold|sess1 -> sess8|lim1sess4 -> lim1sess8 
    """
    timeframe = timeframe.strip()
    time_cycle = periords.get(timeframe, 86400) 
    order_p = order_periords.get(timeframe, 2592000) # default 30 days
    end_time = int(datetime.now().timestamp()) // order_p * order_p
    last_time = end_time - time_cycle  # last session
    start_time = end_time - num_sessions*time_cycle  # first session

    indicator = indicator.strip().lower()
    if indicator in ('rsi7','rsi14'):
        o_strat = f"{indicator}_ep_30_70"
    elif indicator == 'adx':
        o_strat = f"{indicator}_ep_trend_reverse"
    else:
        o_strat = ''

    sql = strategy(o_strat, tp_strat, timeframe, start_time, last_time, group_by='both')
    data = []
    
    try: 
        result = db.execute(text(sql)).fetchall()
        data = [schemas.TradeReport(
                pair=row.symbol, 
                revalue=row.revalue,
                total_volumn=row.total_volumn,
                num_order=row.num_order,
                roi=row.roi,
                win_rate=row.win_rate
            )
            for row in result]
    except Exception as e:
        print("error", e)
    return data

@router.get("/validate/indicators", 
            tags=group_tags,
            response_model=List[schemas.ValIndicator]
            )
def val_indicators(timeframe: str, num_sessions:int, tp_strat:str='sess4', db: Session = Depends(get_db)) -> List[schemas.ValIndicator]:
    """
    summary validate of all indicators  
    PARAM:
     - timeframe: 5m|30m|1h|4h|1D (auto 1D)
     - num_sessions: number of time sessions to now
     - tp_strat: hold|sess1 -> sess8|lim1sess4 -> lim1sess8 
    """
    timeframe = timeframe.strip()
    time_cycle = periords.get(timeframe, 86400) 
    order_p = order_periords.get(timeframe, 2592000) # default 30 days
    end_time = int(datetime.now().timestamp()) // order_p * order_p
    last_time = end_time - time_cycle  # last session
    start_time = end_time - num_sessions*time_cycle  # first session

    o_strat = ["rsi7_ep_30_70", "rsi14_ep_30_70", "adx_ep_trend_reverse"]

    sql = strategy(o_strat, tp_strat, timeframe, start_time, last_time, group_by='strategy')
    data = []
    try: 
        result = db.execute(text(sql)).fetchall()
        data = [schemas.ValIndicator(
                indicator=row.strategy.split('_')[0],
                revalue=row.revalue,
                total_volumn=row.total_volumn,
                num_order=row.num_order,
                roi=row.roi,
                win_rate=row.win_rate
            )
            for row in result]
    except Exception as e:
        print("error", e)
    return data

@router.get("/validate/symbols", 
            tags=group_tags,
            response_model=List[schemas.ValDetail]
            )
def val_symbols(timeframe: str, num_sessions:int, tp_strat:str='sess4', detail:bool=False, db: Session = Depends(get_db)) -> List[schemas.ValDetail]:
    """
    summary validate of all indicators  
    PARAM:
     - timeframe: 5m|30m|1h|4h|1D (auto 1D)
     - num_sessions: number of time sessions to now
     - tp_strat: hold|sess1 -> sess8|lim1sess4 -> lim1sess8 
     - detail: show detail
    """
    timeframe = timeframe.strip()
    time_cycle = periords.get(timeframe, 86400) 
    order_p = order_periords.get(timeframe, 2592000) # default 30 days
    end_time = int(datetime.now().timestamp()) // order_p * order_p
    last_time = end_time - time_cycle  # last session
    start_time = end_time - num_sessions*time_cycle  # first session

    o_strat = ["rsi7_ep_30_70", "rsi14_ep_30_70", "adx_ep_trend_reverse"]

    group_by = 'both' if detail else 'symbol'
    sql = strategy(o_strat, tp_strat, timeframe, start_time, last_time, group_by=group_by)
    data = []

    try:
        result = db.execute(text(sql)).fetchall()
        pair = None
        val_indicators = []
        for row in result:
            if pair == row.symbol:
                val_indicators.append(
                    schemas.ValIndicator(
                        indicator=row.strategy.split('_')[0],
                        revalue=row.revalue,
                        total_volumn=row.total_volumn,
                        num_order=row.num_order,
                        roi=row.roi,
                        win_rate=row.win_rate
                    )
                )
            else:
                if pair is not None and pair != '':
                    data.append(
                        schemas.ValDetail(
                            pair=pair,
                            indicators=val_indicators
                        )
                    )
                pair = row.symbol
                val_indicators= [schemas.ValIndicator(
                        indicator=row.strategy.split('_')[0],
                        revalue=row.revalue,
                        total_volumn=row.total_volumn,
                        num_order=row.num_order,
                        roi=row.roi,
                        win_rate=row.win_rate
                )]
        if pair is not None and pair != '':
            data.append(
                schemas.ValDetail(
                    pair=pair,
                    indicators=val_indicators
                )
            )
    except Exception as e:
        print("error", e)

    return data

@router.get("/summary/{pair}/signal-scores", 
            tags=group_tags,
            # response_model=List[schemas.BackTestV2]
            )
def get_signal_scores(pair: str, db: Session = Depends(get_db)) :
    sql = f"""
    select * from proddb.tmp_signal_scores
    where symbol = '{pair}'
    """
    result = {}
    try:
        data = db.execute(text(sql)).fetchall()
        for row in data:
            result[row['signal']] = row['score']
    except Exception as e:
        print("error", e)
    return result
