from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from fastapi import HTTPException


# Create the SQLAlchemy engine
engine = create_engine(settings.DATABASE_URL,
                       connect_args={"connect_timeout": 30},
                       pool_pre_ping=True,
                       pool_recycle=3600,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# do not change the order of the code below
# Dependency that can be used in routes to get the session
def get_db() -> Session  |  HTTPException:
    db = SessionLocal()  # generate a new SessionLocal
    try:
        yield db
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        else:
            print(e)
            raise HTTPException(status_code=500, detail="Query data error")
    finally:
        db.close()


def get_tables(schema: str = settings.SCHEMA_2) -> dict:
    if schema is None or schema == "":
        schema = ''
    else:
        schema = schema + "."
    
    return {
    'p5m': schema+'coin_prices_5m',
    'p1h': schema+'coin_prices_1h',
    'f5m': schema+'f_coin_signal_5m',
    # 'f10m': schema+'f_coin_signal_10m',
    # 'f15m': schema+'f_coin_signal_15m',
    'f30m': schema+'f_coin_signal_30m',
    'f1h': schema+'f_coin_signal_1h',
    'f4h': schema+'f_coin_signal_4h',
    'f1d': schema+'f_coin_signal_1d',
    'f1D': schema+'f_coin_signal_1d',
    'orders': schema+'trade_orders_sim',
    'tp_by_sess': schema+'trade_orders_tp_by_session',
    'predict': schema+'coin_predictions',
    'app_quote': schema+'app_quote',
    'currency': schema+'currency',
    }
