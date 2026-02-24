# SeerBot Service API

FastAPI backend for SeerBot - a Cardano trading platform that supports traders with vault management, market data, technical analysis, and AI-powered insights.

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL (multiple schemas)
- **Cache**: Redis + in-memory
- **Blockchain**: Cardano (PyCardano + Blockfrost API)
- **Auth**: JWT + Cardano wallet addresses

## API Endpoints

### Vaults
- `GET /vaults` - List vaults by status (active/inactive)
- `GET /vaults/{id}/info` - Get vault details
- `GET /vaults/{id}/stats` - Get vault statistics
- `GET /vaults/{id}/values` - Get vault value history (TradingView format)
- `GET /vaults/{id}/positions` - Get vault trade positions
- `GET /vaults/{id}/contribute` - Get user contribution info
- `POST /vaults/withdraw` - Withdraw from vault

### Market Data
- `GET /market/daily` - Get daily market data for token

### Analysis & Trading
- `GET /analysis/tokens` - List/search tokens
- `GET /analysis/tokens/{symbol}` - Get token market info
- `GET /analysis/swaps` - Get swap transactions
- `GET /analysis/toptraders` - Get top traders by volume/trades
- `GET /analysis/trend` - Get trend predictions (uptrend/downtrend)
- `GET /analysis/predictions` - Get price predictions
- `GET /analysis/signal/{indicator}/{signal}` - Get technical signals (RSI, ADX, PSAR, price_24h)
- `GET /analysis/charting/config` - TradingView config
- `GET /analysis/charting/pairs` - Search trading pairs
- `GET /analysis/charting/pairs/{pair}` - Resolve trading pair
- `GET /analysis/charting/history/{pair}` - Get OHLCV data

### AI Assistant
- `GET /ai-assistant/chat` - Load chat messages
- `POST /ai-assistant/chat` - Save chat messages

### WebSocket
- `WS /ws` - Real-time data streaming

### Health
- `GET /health` - Health check

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or with uv
uv pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and configure:

### Running the Server

```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

### API Documentation

Once running, access:
- **Swagger UI**: `https://your-host/docs`
- **ReDoc**: `https://your-host/redoc`

Enter the `DOC_PASSWORD` configured in your environment to view the documentation.

## Future Plans

### Completed Features ✓
- [x] Mobile App (Android)
- [x] Portfolio Feature
- [x] Asset Vault Dashboard
- [x] UI/UX Improvements

### Platform Accessibility
- [ ] Mobile App (iOS)
- [ ] Telegram Mini App (TMA)

### Advanced Trading Tools
- [ ] Quant Trading & Vaults
- [ ] Auto-Trading Bots
- [ ] Copy Trading
- [ ] Additional TA Signals
- [ ] Expanded Token Support

### AI & Data Enhancements
- [ ] AI Agents
- [ ] Deep Research
- [ ] AI Price Predictions
- [ ] Token Suggestions
- [ ] News Integration

## License

MIT License
