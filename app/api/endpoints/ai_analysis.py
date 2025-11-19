from datetime import datetime, timedelta
from app.core.config import settings
import app.schemas.ai_analysis as schemas
from app.core.router_decorated import APIRouter
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from app.db.session import get_db, get_tables

router = APIRouter()
tables = get_tables(settings.SCHEMA_2)
group_tags=["Api"]


@router.get("/get-predictions", 
            tags=group_tags,
            response_model=List[schemas.PredictionV2])
def get_latest_predictions(db: Session = Depends(get_db)) -> List[schemas.PredictionV2]  |  HTTPException:
    """ Get the latest predictions of all coins
    OUTPUT: list of Prediction
    - symbol: str: coin symbol
    - update_time: int: time of the prediction
    - target_time: int: time of the target
    - price: float: current price
    - prediction: float: predicted price
    - price_change: float: price change in percentage
    """
    table_name = tables['predict']

    query = f"""
    select symbol, update_time, target_time, price, prediction, change_percentage
    from (
        SELECT
            symbol,
            open_time + 3600 as update_time,
            open_time + 2*3600 as target_time,  -- Price is predicted for the end of the next session, mean open_time + 2*period = predicted time
            last_price as price, 
            next_pred as prediction,
            ((next_pred - last_price) / last_price) * 100 AS change_percentage,
            row_number() over (PARTITION by symbol order by open_time desc) AS r
        FROM {table_name} cp 
        WHERE 
            open_time >=  (extract(epoch from now())::bigint-24*5*3600)  -- 3 hours
            and last_price <> 0 
            and last_price is not null
    ) a
    where r=1
    order by update_time desc 
    """
    print(query)
    result = db.execute(text(query)).fetchall()
    if not result or len(result) <= 0:
        # return HTTPException(status_code=404, detail="No data found")
        print("No data found")
        return [schemas.PredictionV2()]
    data = [ 
        schemas.PredictionV2(
            symbol=row.symbol,
            update_time=row.update_time,
            target_time=row.target_time,
            price=row.price,
            prediction=row.prediction,
            price_change=row.change_percentage
        ) for row in result
    ]
    return data

@router.get("/predict-validate", 
            tags=group_tags,
            response_model=schemas.Validate)
def validate(interval: str="", limit: int=-1, db: Session = Depends(get_db)) -> schemas.Validate:
    """Get the validation of the prediction from given time to now
    - timeframe: str: frame of time to get data, 1D | 1W | 1M | 3M | 1Y | all, default is all
    - limit: int: positive number to get the number of data, negative number to get all data, default is -1

    OUTPUT: list of Validate 
    - mae: mean absolute error - avg(true-predict) 
    - avg_err_rate: mean error rate - avg(abs(true-predict) / ATR14)  with ATR14 is average true range of the last 14 periods
    - accuracy: binary accuracy - sum(binary_acc)/n_trade with binary_acc = 1 if the prediction is in the same trend with the true price, 0 otherwise 
    - n_trade: number of trade
    - true_pred: number of true prediction
    - false_pred: number of false prediction
    - profit_rate: profit rate of each trade
    """
    
    if limit <= 0:
        return []
    else:
        interval = interval.strip().lower()
        time_frame = " and open_time >= extract(epoch from now())::bigint - {time_range}"
        if interval == 'one_year':
            time_frame = time_frame.format(time_range=365*24*3600)
        if interval == 'three_month':
            time_frame = time_frame.format(time_range=90*24*3600)
        elif interval == 'one_month':
            time_frame = time_frame.format(time_range=30*24*3600)
        elif interval == 'one_week':
            time_frame = time_frame.format(time_range=7*24*3600)
        elif interval == 'one_day':
            time_frame = time_frame.format(time_range=24*3600)
        else:  # interval == 'all'
            time_frame = ""
        limit_str = "" if limit < 0 else f" limit {limit}"

    p_table = tables['predict']
    f_table = tables['f1h']
    query = f"""
        SELECT
            avg(err) as mae,
            avg(err_on_atr) as avg_err_rate,
            avg(true_pred) as accuracy,
            count(1) as n_trade,
            sum(true_pred) as true_pred,
            count(1) - sum(true_pred) as false_pred,
            GREATEST(max(profit_rate) - 1, 0) as max_profit_rate,
            GREATEST(1 - min(profit_rate), 0) as max_loss_rate,
            avg(profit_rate) - 1 as avg_profit_rate
        from(
            SELECT p.symbol, r.open_time,
                (p.next_pred - r.close) as err,
                abs(p.next_pred - r.close)/r.atr14 as err_on_atr,  -- sai so tren bien dong thi truong
                CASE WHEN p.pred_trend=r.trend THEN 1 ELSE 0 END as true_pred,
                case 
                    when p.pred_trend='up' then r.close / p.last_price
                    when p.pred_trend='down' then p.last_price / r.close
                    else 1
                end as profit_rate
            from(
                SELECT symbol, (open_time + 3600) as open_time, last_price, next_pred,
                case 
                    when next_pred - last_price > 0 then 'up'
                    when next_pred - last_price < 0 then 'down'
                    else 'flat'
                end as pred_trend
                FROM {p_table} cp 
                WHERE last_price is not null and last_price > 0 {time_frame} 
                order by open_time desc   -- to optimization limit here but data is not correct so not all can join  
            ) p
            inner join(
                SELECT symbol, open, close, atr14, open_time,
                case 
                    when c_diff_p - c_diff_n > 0 then 'up'
                    when c_diff_p - c_diff_n < 0 then 'down'
                    else 'flat'
                end as trend
                from {f_table} fcsh 
                where atr14 is not null and atr14 > 0 {time_frame} 
                order by open_time desc
            ) r on r.open_time = p.open_time and r.symbol = p.symbol
            {limit_str}
        ) a
    """
    result = db.execute(text(query)).fetchall()
    if result is None or not result or len(result) <= 0:
        # raise HTTPException(status_code=404, detail="No data found")
        print("No data found")
        return [schemas.Validate()]

    row = result[0]
    return schemas.Validate(
            mae=row.mae,
            avg_err_rate=row.avg_err_rate,
            max_profit_rate=row.max_profit_rate,
            max_loss_rate=row.max_loss_rate,
            avg_profit_rate=row.avg_profit_rate,
            accuracy=row.accuracy,
            n_trade=row.n_trade,
            true_pred=row.true_pred,
            false_pred=row.false_pred
        )

@router.get("/predict-validate/{pair}", 
            tags=group_tags,
            response_model=schemas.Validate)
def validate_detail(pair: str, timeframe: str="", limit: int=-1, db: Session = Depends(get_db)) -> schemas.Validate:
    """Get the validation of the prediction of a coin
    - pair: str: pair
    - timeframe: str: frame of time to get data, 1D | 1W | 1M | 3M | 1Y | all, default is all
    - limit: int: positive number to get the number of data, negative number to get all data, default is -1
    
    OUTPUT: list of Validate
    - mae: mean absolute error - avg(true-predict) 
    - avg_err_rate: mean error rate - avg(abs(true-predict) / ATR14)  with ATR14 is average true range of the last 14 periods
    - max_profit_rate: max profit rate
    - max_loss_rate: max loss rate
    - accuracy: binary accuracy - sum(binary_acc)/n_trade with binary_acc = 1 if the prediction is in the same trend with the true price, 0 otherwise 
    - n_trade: number of trade
    - true_pred: number of true prediction
    - false_pred: number of false prediction
    - profit_rate: profit rate of each trade
    
    """
    symbol = pair.strip().lower()
    timeframe = timeframe.strip()
    time_frame = ""
    if timeframe == '1Y':
        time_frame = f" and open_time >= {(datetime.now() - timedelta(days=365)).timestamp()}"
    if timeframe == '3M':
        time_frame = f" and open_time >= {(datetime.now() - timedelta(days=90)).timestamp()}"
    elif timeframe == '1M':
        time_frame = f" and open_time >= {(datetime.now() - timedelta(days=30)).timestamp()}"
    elif timeframe == '1W':
        time_frame = f" and open_time >= {(datetime.now() - timedelta(weeks=1)).timestamp()}"
    elif timeframe == '1D':
        time_frame = f" and open_time >= {(datetime.now() - timedelta(days=1)).timestamp()}"
    else:  # timeframe == 'all'
        time_frame = ""
    limit_str = "" if limit < 0 else f" limit {limit}"
    p_table = tables['predict']
    f_table = tables['f1h']
    # todo: 
    query = f"""
        SELECT
            avg(err) as mae,
            avg(err_on_atr) as avg_err_rate,
            avg(true_pred) as accuracy,
            count(1) as n_trade,
            sum(true_pred) as true_pred,
            count(1) - sum(true_pred) as false_pred,
            GREATEST(max(profit_rate) - 1, 0) as max_profit_rate,
            GREATEST(1 - min(profit_rate), 0) as max_loss_rate,
            avg(profit_rate) - 1 as avg_profit_rate
        from(
            SELECT p.symbol, r.open_time,
                (p.next_pred - r.close) as err,
                abs(p.next_pred - r.close)/r.atr14 as err_on_atr,  -- sai so tren bien dong thi truong
                CASE WHEN p.pred_trend=r.trend THEN 1 ELSE 0 END as true_pred,
                case 
                    when p.pred_trend='up' then r.close / p.last_price
                    when p.pred_trend='down' then p.last_price / r.close
                    else 1
                end as profit_rate
            from(
                SELECT symbol, (open_time + 3600) as open_time, last_price, next_pred,
                case 
                    when next_pred - last_price > 0 then 'up'
                    when next_pred - last_price < 0 then 'down'
                    else 'flat'
                end as pred_trend
                FROM {p_table} cp 
                WHERE symbol = :symbol and last_price is not null and last_price > 0 {time_frame} 
                order by open_time desc
            ) p
            inner join(
                SELECT symbol, open, close, atr14, open_time,
                case 
                    when c_diff_p > 0 then 'up'
                    when c_diff_n > 0 then 'down'
                    else 'flat'
                end as trend
                from {f_table} fcsh 
                where symbol = :symbol and atr14 is not null and atr14 > 0 {time_frame} 
                order by open_time desc
            ) r on r.open_time = p.open_time
            {limit_str}
        ) a
    """
    result = db.execute(text(query),{
        "symbol": symbol,
    }).fetchall()
    if not result or len(result) <= 0:
        raise HTTPException(status_code=404, detail="No data found")
    row = result[0]
    return schemas.Validate(
            mae=row.mae,
            avg_err_rate=row.avg_err_rate,
            max_profit_rate=row.max_profit_rate,
            max_loss_rate=row.max_loss_rate,
            avg_profit_rate=row.avg_profit_rate,
            accuracy=row.accuracy,
            n_trade=row.n_trade,
            true_pred=row.true_pred,
            false_pred=row.false_pred
        )


@router.get("/predict-validate/{pair}/chart", 
            tags=group_tags,
            response_model=List[schemas.BackTestV2])
def get_predict_chart(pair: str, limit: int=-1, db: Session = Depends(get_db)) -> List[schemas.BackTestV2]:
    """Get the validation of the prediction of a coin 
    - symbol: str: coin symbol
    - limit: int: positive number to get the number of data, negative number to get all data, default is -1

    OUTPUT:
    - open_time: str: open time
    - close_time: str: close time
    - close_predict: float: predicted close price
    - open: float: open price
    - close: float: close price
    - high: float: high price
    - low: float: low price
    - pred_trend: str: predicted trend (up | down | flat)
    - trend: str: actual trend (up | down | flat)
    """
    symbol = pair.strip().lower()
    if limit < 0:
        time_cond = ""
    else:
        time_cond = f" and open_time >= extract(epoch from now())::bigint- {3600*(limit+1)}"
    p_table = tables['predict']
    f_table = tables['f1h']
    query = f"""
        SELECT r.open_time,
            (r.open_time + 3600) as close_time,
            p.next_pred as close_predict,
            r.open,
            r.close,
            r.high,
            r.low,
            case 
                when p.next_pred - r.open > 0 then 'up'
                when p.next_pred - r.open < 0 then 'down'
                else 'flat'
            end as pred_trend,
            case 
                when r.close - r.open > 0 then 'up'
                when r.close - r.open < 0 then 'down'
                else 'flat'
            end as trend
        from(
            SELECT symbol, (open_time + 3600) as open_time, next_pred
            FROM {p_table} cp 
                WHERE symbol = '{symbol}' and last_price is not null and last_price > 0 {time_cond} 
            order by open_time desc
        ) p
        right join(
            SELECT symbol, open, close, high, low, open_time
            from {f_table} fcsh 
                where symbol = '{symbol}' and atr14 is not null and atr14 > 0 {time_cond} 
            order by open_time desc
        ) r on r.open_time = p.open_time
        order by r.open_time asc
    """
    print(query)
    result = db.execute(text(query)).fetchall()
    print(result)
    if not result:
        raise HTTPException(status_code=404, detail="No data found")
    return [
        schemas.BackTestV2(
            open_time=row.open_time,
            close_time=row.close_time,
            close_predict=row.close_predict or 'null',
            open=row.open,
            close=row.close,
            high=row.high,
            low=row.low,
            pred_trend=row.pred_trend,
            trend=row.trend
        )
        for row in result
    ]
