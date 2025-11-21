import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from unittest.mock import Mock
from typing import Generator

from main import app
from app.db.session import get_db


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator:
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application"""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session():
    """Create a mock database session"""
    return Mock(spec=Session)


class MockRow:
    """Helper class for creating mock database result rows"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def mock_db_result():
    """Create mock database result rows based on f_coin_signal model example
    
    Includes all columns from f_coin_signal table to match the complete data structure.
    Same data structure as mock_result_rows for consistency.
    """
    # Same data as mock_result_rows - includes all columns from f_coin_signal model
    return [
        MockRow(
            # Query result columns (aliased/calculated)
            timestamp=1763461800,  # open_time + timeframe_offset (aliased as timestamp in query)
            open=0.02056261274726,
            high=0.02056261274726,
            low=0.02056261274726,
            close=0.02056261274726,
            volume=0.0,
            rsi7=100.0,
            rsi14=100.0,
            adx14=5.745545487187029,  # adx aliased as adx14 in query
            psar=0.021474670468631437,
            
            # Additional columns from f_coin_signal model (for completeness)
            update_time=1763463631,
            time=1763461800,  # time column in DB (open_time)
            open_time=1763461800,  # Used in query WHERE clause
            symbol="ADA/USDT",
            ph=0.02056261274726,
            pl=0.02056261274726,
            pc=0.02056261274726,
            tr=2.0562612747260002E-7,
            c_diff_p=0.0,
            c_diff_n=0.0,
            dm_p=0.0,
            dm_n=0.0,
            ep14_h=0.0216836223548,
            ep14_l=0.01960971685875,
            ep28_h=0.0216836223548,
            ep28_l=0.01960971685875,
            atr14=1.1520213582977417E-4,
            atr28=8.100797396564988E-5,
            ag7=3.2814708020137366E-5,
            ag14=3.4305784643420825E-5,
            al7=0.0,
            al14=0.0,
            dm14_p=1.4742779122165617E-4,
            dm14_n=1.1648817945952881E-4,
            di14_diff=26.856803946625245,
            di14_sum=229.08947718743207,
            dx14=11.723281346812824,
            di14_p=127.97314056702865,
            di14_n=101.1163366204034,
            di14_line_cross=0,
            adx=5.745545487187029,  # Original adx column
            af=0.08,
            psar_type="DOWN",
            ep=0.02056261274726
        ),
        MockRow(
            # Query result columns
            timestamp=1763465400,  # 1 hour later (3600 seconds after first)
            open=0.02060000000000,
            high=0.02065000000000,
            low=0.02055000000000,
            close=0.02062000000000,
            volume=11858.201102,
            rsi7=65.5,
            rsi14=68.2,
            adx14=6.123456789012345,
            psar=0.02150000000000,
            
            # Additional columns from f_coin_signal model
            update_time=1763467231,
            time=1763465400,
            open_time=1763465400,
            symbol="ADA/USDT",
            ph=0.02065000000000,
            pl=0.02055000000000,
            pc=0.02062000000000,
            tr=0.0001,
            c_diff_p=0.00003738725274,
            c_diff_n=0.0,
            dm_p=0.0001,
            dm_n=0.0,
            ep14_h=0.0216836223548,
            ep14_l=0.01960971685875,
            ep28_h=0.0216836223548,
            ep28_l=0.01960971685875,
            atr14=1.2000000000000000E-4,
            atr28=8.5000000000000000E-5,
            ag7=3.5000000000000000E-5,
            ag14=3.6000000000000000E-5,
            al7=0.0,
            al14=0.0,
            dm14_p=1.5000000000000000E-4,
            dm14_n=1.2000000000000000E-4,
            di14_diff=28.0,
            di14_sum=230.0,
            dx14=12.0,
            di14_p=130.0,
            di14_n=102.0,
            di14_line_cross=0,
            adx=6.123456789012345,
            af=0.08,
            psar_type="UP",
            ep=0.02060000000000
        ),
    ]


@pytest.fixture
def mock_tokens():
    """Create mock token objects for testing"""
    from app.models.tokens import Token
    
    return [
        Token(
            id="a0028f350aaabe0545fd1234567890abcdef",
            name="USDM",
            symbol="USDM",
            policy_id="a0028f350aaabe0545fd1234567890abcdef",
            asset_name="5553444d"
        ),
        Token(
            id="b0039f460bbcd1656ef2345678901bcdefg",
            name="HOSKY Token",
            symbol="HOSKY",
            policy_id="b0039f460bbcd1656ef2345678901bcdefg",
            asset_name="484f534b59"
        ),
        Token(
            id="c0040g571ccde2767fg3456789012cdefgh",
            name="ADA",
            symbol="ADA",
            policy_id="c0040g571ccde2767fg3456789012cdefgh",
            asset_name="414441"
        ),
        Token(
            id="d0051h682ddef3878gh4567890123defghi",
            name="USD Coin",
            symbol="USDC",
            policy_id="d0051h682ddef3878gh4567890123defghi",
            asset_name="55534443"
        ),
    ]


@pytest.fixture
def mock_result_rows():
    """Create mock database result rows for indicators based on f_coin_signal model example
    
    Includes all columns from f_coin_signal table to match the complete data structure.
    Note: The query uses 'open_time + timeframe_offset as timestamp', so the mock row has 'timestamp' attribute.
    Also includes 'adx14' which is aliased from 'adx' column in the query.
    """
    # First row based on f_coin_signal.py example with ALL columns
    return [
        MockRow(
            # Query result columns (aliased/calculated)
            timestamp=1763461800,  # open_time + timeframe_offset (aliased as timestamp in query)
            open=0.02056261274726,
            high=0.02056261274726,
            low=0.02056261274726,
            close=0.02056261274726,
            volume=0.0,
            rsi7=100.0,
            rsi14=100.0,
            adx14=5.745545487187029,  # adx aliased as adx14 in query
            psar=0.021474670468631437,
            
            # Additional columns from f_coin_signal model (for completeness)
            update_time=1763463631,
            time=1763461800,  # time column in DB (open_time)
            open_time=1763461800,  # Used in query WHERE clause
            symbol="ADA/USDT",
            ph=0.02056261274726,
            pl=0.02056261274726,
            pc=0.02056261274726,
            tr=2.0562612747260002E-7,
            c_diff_p=0.0,
            c_diff_n=0.0,
            dm_p=0.0,
            dm_n=0.0,
            ep14_h=0.0216836223548,
            ep14_l=0.01960971685875,
            ep28_h=0.0216836223548,
            ep28_l=0.01960971685875,
            atr14=1.1520213582977417E-4,
            atr28=8.100797396564988E-5,
            ag7=3.2814708020137366E-5,
            ag14=3.4305784643420825E-5,
            al7=0.0,
            al14=0.0,
            dm14_p=1.4742779122165617E-4,
            dm14_n=1.1648817945952881E-4,
            di14_diff=26.856803946625245,
            di14_sum=229.08947718743207,
            dx14=11.723281346812824,
            di14_p=127.97314056702865,
            di14_n=101.1163366204034,
            di14_line_cross=0,
            adx=5.745545487187029,  # Original adx column
            af=0.08,
            psar_type="DOWN",
            ep=0.02056261274726
        ),
        MockRow(
            # Query result columns
            timestamp=1763465400,  # 1 hour later (3600 seconds after first)
            open=0.02060000000000,
            high=0.02065000000000,
            low=0.02055000000000,
            close=0.02062000000000,
            volume=11858.201102,
            rsi7=65.5,
            rsi14=68.2,
            adx14=6.123456789012345,
            psar=0.02150000000000,
            
            # Additional columns from f_coin_signal model
            update_time=1763467231,
            time=1763465400,
            open_time=1763465400,
            symbol="ADA/USDT",
            ph=0.02065000000000,
            pl=0.02055000000000,
            pc=0.02062000000000,
            tr=0.0001,
            c_diff_p=0.00003738725274,
            c_diff_n=0.0,
            dm_p=0.0001,
            dm_n=0.0,
            ep14_h=0.0216836223548,
            ep14_l=0.01960971685875,
            ep28_h=0.0216836223548,
            ep28_l=0.01960971685875,
            atr14=1.2000000000000000E-4,
            atr28=8.5000000000000000E-5,
            ag7=3.5000000000000000E-5,
            ag14=3.6000000000000000E-5,
            al7=0.0,
            al14=0.0,
            dm14_p=1.5000000000000000E-4,
            dm14_n=1.2000000000000000E-4,
            di14_diff=28.0,
            di14_sum=230.0,
            dx14=12.0,
            di14_p=130.0,
            di14_n=102.0,
            di14_line_cross=0,
            adx=6.123456789012345,
            af=0.08,
            psar_type="UP",
            ep=0.02060000000000
        ),
    ]


@pytest.fixture
def mock_tokens():
    """Create mock token objects for testing"""
    from app.models.tokens import Token
    
    return [
        Token(
            id="a0028f350aaabe0545fd1234567890abcdef",
            name="USDM",
            symbol="USDM",
            policy_id="a0028f350aaabe0545fd1234567890abcdef",
            asset_name="5553444d"
        ),
        Token(
            id="b0039f460bbcd1656ef2345678901bcdefg",
            name="HOSKY Token",
            symbol="HOSKY",
            policy_id="b0039f460bbcd1656ef2345678901bcdefg",
            asset_name="484f534b59"
        ),
        Token(
            id="c0040g571ccde2767fg3456789012cdefgh",
            name="ADA",
            symbol="ADA",
            policy_id="c0040g571ccde2767fg3456789012cdefgh",
            asset_name="414441"
        ),
        Token(
            id="d0051h682ddef3878gh4567890123defghi",
            name="USD Coin",
            symbol="USDC",
            policy_id="d0051h682ddef3878gh4567890123defghi",
            asset_name="55534443"
        ),
    ]

