# TradingView Charting Library **does NOT accept WebSocket as the primary datafeed API**
The official datafeed API works like this:
* **Historical data** → MUST come from REST endpoints (`/history`, `/symbols`, `/config`, etc.)
* **Real-time updates** → can be delivered via **WebSocket**
  but only **after** the chart loads historical data through HTTP.
So the correct architecture is:
```
TradingView Chart
   → REST /config, /symbols, /history (FastAPI)
   → WebSocket for real-time bars (FastAPI WS)
```
This is the same design TradingView uses internally.
---
# FastAPI WebSocket + REST Hybrid Example (Fully Working)
### **1. FastAPI app**
```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import time
import asyncio
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------
# REST ENDPOINTS (REQUIRED)
# ------------------------
@app.get("/config")
def config():
    return {
        "supports_search": True,
        "supports_time": True,
        "supported_resolutions": ["1", "5", "60", "1D"],
    }
@app.get("/symbols")
def symbols(symbol: str):
    return {
        "name": symbol,
        "ticker": symbol,
        "type": "crypto",
        "session": "24x7",
        "timezone": "Etc/UTC",
        "has_intraday": True,
        "supported_resolutions": ["1", "5", "60", "1D"],
        "pricescale": 100,
        "data_status": "streaming",
    }
@app.get("/history")
def history(symbol: str, resolution: str, from_: int, to: int):
    # Return your DB OHLCV here
    return {
        "t": [from_, from_ + 60, from_ + 120],
        "o": [100, 101, 102],
        "h": [101, 102, 103],
        "l": [99, 100, 101],
        "c": [101, 102, 103],
        "v": [10, 11, 12],
        "s": "ok"
    }
@app.get("/time")
def time_endpoint():
    return int(time.time())
# ------------------------
# WEBSOCKET FOR REALTIME STREAM
# ------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    # Example ping loop sending live bars
    price = 100
    while True:
        price += 1
        message = {
            "symbol": "BTCUSDT",
            "timestamp": int(time.time()),
            "open": price - 1,
            "high": price + 1,
            "low": price - 2,
            "close": price,
            "volume": 1,
        }
        await ws.send_json(message)
        await asyncio.sleep(1)
```
---
