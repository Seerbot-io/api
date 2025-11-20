from sqlalchemy import Column, String, BigInteger, Float, Numeric, SmallInteger, UniqueConstraint
from app.db.base import Base


class FCoinSignal(Base):
    """Model for f_coin_signal table in proddb schema
    Example:
	{
		"update_time" : 1763463631,
		"open_time" : 1763461800,
		"symbol" : "ADA/ADA",
		"open" : 0.02056261274726,
		"high" : 0.02056261274726,
		"low" : 0.02056261274726,
		"close" : 0.02056261274726,
		"volume" : 0.0,
		"ph" : 0.02056261274726,
		"pl" : 0.02056261274726,
		"pc" : 0.02056261274726,
		"tr" : 2.0562612747260002E-7,
		"c_diff_p" : 0.0,
		"c_diff_n" : 0.0,
		"dm_p" : 0.0,
		"dm_n" : 0.0,
		"ep14_h" : 0.0216836223548,
		"ep14_l" : 0.01960971685875,
		"ep28_h" : 0.0216836223548,
		"ep28_l" : 0.01960971685875,
		"atr14" : 1.1520213582977417E-4,
		"atr28" : 8.100797396564988E-5,
		"ag7" : 3.2814708020137366E-5,
		"ag14" : 3.4305784643420825E-5,
		"al7" : 0.0,
		"al14" : 0.0,
		"dm14_p" : 1.4742779122165617E-4,
		"dm14_n" : 1.1648817945952881E-4,
		"di14_diff" : 26.856803946625245,
		"di14_sum" : 229.08947718743207,
		"dx14" : 11.723281346812824,
		"rsi7" : 100.0,
		"rsi14" : 100.0,
		"di14_p" : 127.97314056702865,
		"di14_n" : 101.1163366204034,
		"di14_line_cross" : 0,
		"adx" : 5.745545487187029,
		"af" : 0.08,
		"psar_type" : "DOWN",
		"psar" : 0.021474670468631437,
		"ep" : 0.02056261274726
	}   
    """

    update_time = Column(BigInteger, default=None)
    time = Column(BigInteger, default=0)  # Note: constraint references open_time, but column is 'time'
    symbol = Column(String(225), default=None)
    open = Column(Float, default=0)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    ph = Column(Float)
    pl = Column(Float)
    pc = Column(Float)
    tr = Column(Float)
    c_diff_p = Column(Float)
    c_diff_n = Column(Float)
    dm_p = Column(Float)
    dm_n = Column(Float)
    ep14_h = Column(Float)
    ep14_l = Column(Float)
    ep28_h = Column(Float)
    ep28_l = Column(Float)
    atr14 = Column(Float)
    atr28 = Column(Float)
    ag7 = Column(Float)
    ag14 = Column(Float)
    al7 = Column(Float)
    al14 = Column(Float)
    dm14_p = Column(Float)
    dm14_n = Column(Float)
    di14_diff = Column(Float)
    di14_sum = Column(Float)
    dx14 = Column(Float)
    rsi7 = Column(Float)
    rsi14 = Column(Float)
    di14_p = Column(Float)
    di14_n = Column(Float)
    di14_line_cross = Column(SmallInteger, default=0, nullable=False)
    adx = Column(Float)
    af = Column(Numeric(3, 2), default=0.00, nullable=False)
    psar_type = Column(String(4), default="", nullable=False)
    psar = Column(Float)
    ep = Column(Float, default=0)



class FCoinSignal5m(FCoinSignal):   
    """Model for f_coin_signal_5m table in proddb schema"""
    __tablename__ = "f_coin_signal_5m"
    __table_args__ = (
        UniqueConstraint("symbol", "time", name="f_coin_signal_5m_symbol_open_time_key"),
        {"schema": "proddb"}
    )

class FCoinSignal30m(FCoinSignal):
    """Model for f_coin_signal_30m table in proddb schema"""
    __tablename__ = "f_coin_signal_30m"
    __table_args__ = (
        UniqueConstraint("symbol", "time", name="f_coin_signal_30m_symbol_open_time_key"),
        {"schema": "proddb"}
    )

class FCoinSignal1h(FCoinSignal):
    """Model for f_coin_signal_1h table in proddb schema"""
    __tablename__ = "f_coin_signal_1h"
    __table_args__ = (
        UniqueConstraint("symbol", "time", name="f_coin_signal_1h_symbol_open_time_key"),
        {"schema": "proddb"}
    )

class FCoinSignal4h(FCoinSignal):
    """Model for f_coin_signal_4h table in proddb schema"""
    __tablename__ = "f_coin_signal_4h"
    __table_args__ = (
        UniqueConstraint("symbol", "time", name="f_coin_signal_4h_symbol_open_time_key"),
        {"schema": "proddb"}
    )

class FCoinSignal1d(FCoinSignal):
    """Model for f_coin_signal_1d table in proddb schema"""
    __tablename__ = "f_coin_signal_1d"
    __table_args__ = (
        UniqueConstraint("symbol", "time", name="f_coin_signal_1d_symbol_open_time_key"),
        {"schema": "proddb"}
    )

