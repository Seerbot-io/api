import asyncio
import json
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from app.api.endpoints.analysis import _get_token_info_data
from app.api.endpoints.charting import SUPPORTED_RESOLUTIONS, get_chart_data
from app.core.router_decorated import APIRouter

router = APIRouter()
group_tags = ["WebSocket"]

# Available channels
CHANNEL_HANDLERS = {}


class FatalSubscriptionError(Exception):
    """Exception raised when a subscription should be stopped due to a fatal error."""

    pass


class ChannelSubscription:
    """Represents a single channel subscription with its state and associated background task."""

    def __init__(
        self,
        channel: str,
        channel_type: str,
        params: Dict[str, Any],
        task: Optional[asyncio.Task] = None,
        stop_event: Optional[asyncio.Event] = None,
    ):
        self.channel = channel
        self.channel_type = channel_type
        self.params = params
        self.state: Dict[str, Any] = {}
        self.task = task
        self.stop_event = stop_event


# utils
def parse_channel(channel: str) -> Tuple[str, Dict[str, Any]]:
    """Parse channel string into channel type and parameters.

    Format: {function}:{param1}|{param2}|...

    Examples:
    - ohlc:USDM_ADA|5m -> ("ohlc", {"symbol": "USDM_ADA", "resolution": "5m"})
    - token_info:USDM -> ("token_info", {"symbol": "USDM"})
    """
    if ":" not in channel:
        raise ValueError(
            f"Invalid channel format: {channel}. Expected format: {{function}}:{{param1}}|{{param2}}|..."
        )

    channel_type, params_str = channel.split(":", 1)

    if not params_str:
        raise ValueError(
            f"Invalid channel format: {channel}. Missing parameters after ':'"
        )

    # Parse parameters based on channel type
    if channel_type == "ohlc":
        # Format: ohlc:{symbol}|{resolution}
        # Use pipe (|) as separator to handle symbols with underscores
        parts = params_str.split("|")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid ohlc channel format: {channel}. Expected: ohlc:{{symbol}}|{{resolution}}"
            )

        symbol = parts[0]
        resolution = parts[1]

        if not symbol or not resolution:
            raise ValueError(
                f"Invalid ohlc channel format: {channel}. Missing symbol or resolution"
            )

        return channel_type, {"symbol": symbol, "resolution": resolution}

    elif channel_type == "token_info":
        # Format: token_info:{symbol}
        # No separator needed for single parameter
        if not params_str:
            raise ValueError(
                f"Invalid token_info channel format: {channel}. Missing symbol"
            )

        return channel_type, {"symbol": params_str}

    else:
        raise ValueError(
            f"Unknown channel type: {channel_type}. Supported types: ohlc, token_info"
        )


async def subscription_update_task(
    subscription: ChannelSubscription, websocket: WebSocket, stop_event: asyncio.Event
):
    """Background task that continuously updates a subscription independently."""
    handler = CHANNEL_HANDLERS.get(subscription.channel_type)
    if not handler:
        return

    while not stop_event.is_set():
        try:
            # Check stop event before processing
            if stop_event.is_set():
                break

            # Get update data from handler
            update_data = await handler(subscription, websocket)

            # Check stop event again before sending
            if stop_event.is_set():
                break

            # Send update if available
            if update_data:
                try:
                    await websocket.send_json(update_data)
                except Exception as e:
                    print(f"Error sending update for {subscription.channel}: {e}")
                    break  # Exit if websocket is closed

            # Wait before next update cycle (adjust interval as needed)
            # Use wait_for to allow checking stop_event during sleep
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1.0)
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue to next iteration

        except asyncio.CancelledError:
            print(f"Subscription task for {subscription.channel} was cancelled")
            break
        except Exception as e:
            if isinstance(e, FatalSubscriptionError):
                stop_event.set()  # stop the subscription
                await websocket.send_json(
                    {"status": "unsubscribed", "channel": subscription.channel}
                )
            print(f"Error processing subscription {subscription.channel}: {e}")
            # Check stop event before retrying
            if stop_event.is_set():
                break
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1.0)
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue to next iteration
        await asyncio.sleep(60)

    print(f"Subscription task for {subscription.channel} stopped")


@router.websocket("/ws")
async def unified_websocket(websocket: WebSocket):
    """Unified WebSocket endpoint for subscribing to multiple data channels.

    Client can send messages with:
    {
        "action": "subscribe" | "unsubscribe",
        "channel": "{function}:{param1}|{param2}|..."
    }

    Supported channels:
    - ohlc:{symbol}|{resolution} - e.g., ohlc:USDM_ADA|5m
    - token_info:{symbol} - e.g., token_info:USDM

    Response format:
    {
        "channel": "ohlc:USDM_ADA_5m",
        "type": "ohlc",
        "data": { ... }
    }
    """
    await websocket.accept()
    # Track subscriptions with their associated tasks: {channel: ChannelSubscription}
    subscriptions: Dict[str, ChannelSubscription] = {}
    # print(f"WebSocket connected: {websocket}")
    try:
        while True:
            try:
                # Receive message (wait indefinitely for new orders/messages)
                data = await websocket.receive_text()
                message = json.loads(data)
                action = message.get("action")
                channel = message.get("channel", "").strip()

                if not action or not channel:
                    await websocket.send_json(
                        {"error": "Missing required fields: action and channel"}
                    )
                    continue
                if action == "subscribe":
                    # Max 5 subscriptions per client
                    if len(subscriptions) >= 5:
                        await websocket.send_json(
                            {
                                "error": "Maximum number of subscriptions reached",
                                "channels": list(subscriptions.keys()),
                            }
                        )
                        continue
                    try:
                        # Parse channel
                        channel_type, params = parse_channel(channel)

                        # Check if handler exists
                        if channel_type not in CHANNEL_HANDLERS:
                            await websocket.send_json(
                                {
                                    "error": f"Unknown channel type: {channel_type}",
                                    "channel": channel,
                                }
                            )
                            continue
                        # Create subscription if it doesn't exist
                        if channel not in subscriptions:
                            # Create stop event and background task for this subscription
                            stop_event = asyncio.Event()

                            subscription = ChannelSubscription(
                                channel=channel,
                                channel_type=channel_type,
                                params=params,
                                stop_event=stop_event,
                            )
                            # Create and store task
                            task = asyncio.create_task(
                                subscription_update_task(
                                    subscription, websocket, stop_event
                                )
                            )
                            subscription.task = task
                            subscriptions[channel] = subscription
                            await websocket.send_json(
                                {
                                    "status": "subscribed",
                                    "channel": channel,
                                    "type": channel_type,
                                }
                            )
                        else:
                            await websocket.send_json(
                                {"status": "already_subscribed", "channel": channel}
                            )

                    except ValueError as e:
                        await websocket.send_json({"error": str(e), "channel": channel})

                elif action == "unsubscribe":
                    if channel in subscriptions:
                        # Stop and cancel background task for this channel
                        subscription = subscriptions[channel]
                        if subscription.stop_event:
                            subscription.stop_event.set()
                        if subscription.task:
                            subscription.task.cancel()
                            try:
                                await subscription.task
                            except asyncio.CancelledError:
                                pass

                        # Remove channel from subscriptions
                        subscriptions.pop(channel, None)
                        print(f"Unsubscribed from channel: {channel}")
                        await websocket.send_json(
                            {"status": "unsubscribed", "channel": channel}
                        )
                    else:
                        await websocket.send_json(
                            {
                                "error": f"Subscription not found for channel: {channel}",
                                "channel": channel,
                            }
                        )

                else:
                    await websocket.send_json(
                        {
                            "error": f"Invalid action: {action}. Expected 'subscribe' or 'unsubscribe'"
                        }
                    )

            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                await websocket.send_json({"error": str(e)})
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        # Clean up all channels and stop all background tasks when websocket closes/disconnects
        print(f"Cleaning up {len(subscriptions)} subscription tasks...")

        # Stop and cancel all background tasks
        for channel, subscription in list(subscriptions.items()):
            try:
                if subscription.stop_event:
                    subscription.stop_event.set()
                if subscription.task:
                    subscription.task.cancel()
                    try:
                        await subscription.task
                    except asyncio.CancelledError:
                        pass
                print(f"Stopped task for channel: {channel}")
            except Exception as e:
                print(f"Error stopping task for channel {channel}: {e}")

        # Clear all subscriptions
        subscriptions.clear()

        print("All channels and tasks cleaned up")


# Channel handlers
def channel_handler(channel_type: str):
    """Decorator to register a channel handler function."""

    def decorator(func):
        CHANNEL_HANDLERS[channel_type] = func
        return func

    return decorator


@channel_handler("ohlc")
async def handle_ohlc(
    subscription: ChannelSubscription, websocket: WebSocket
) -> Optional[Dict[str, Any]]:
    """Handle ohlc channel updates.

    Channel format: ohlc:{symbol}|{resolution}
    Example: ohlc:USDM_ADA|5m
    """
    symbol = subscription.params.get("symbol")
    resolution = subscription.params.get("resolution")

    if not symbol or not resolution:
        await websocket.send_json(
            {
                "error": "Missing required parameters: symbol and resolution",
                "channel": subscription.channel,
            }
        )
        return None

    # Normalize symbol
    symbol = symbol.strip().replace("_", "/").upper()

    # Validate resolution
    if resolution not in SUPPORTED_RESOLUTIONS:
        await websocket.send_json(
            {
                "error": f"Invalid resolution: {resolution}. Supported: {SUPPORTED_RESOLUTIONS}",
                "channel": subscription.channel,
            }
        )
        return None

    # Get last timestamp from state
    last_timestamp = subscription.state.get("last_timestamp", 0)

    try:
        # Get latest bar after last_timestamp
        result = get_chart_data(  # have cache
            symbol=symbol,
            resolution=resolution,
            from_time=last_timestamp+ 300,
            count_back=1,
        )
        print("result", result)
        if result and len(result) > 0:
            row = result[0]
            current_timestamp = int(row["timestamp"]) if row["timestamp"] else 0

            # Only send if this is a new bar
            if last_timestamp == 0 or current_timestamp > last_timestamp:
                # Update last_timestamp in state
                subscription.state["last_timestamp"] = current_timestamp

                # Return update data
                return {
                    "channel": subscription.channel,
                    "type": "ohlc",
                    "data": {
                        "symbol": symbol,
                        "timestamp": current_timestamp,
                        "open": round(
                            float(row["open"]) if row["open"] is not None else 0, 6
                        ),
                        "high": round(
                            float(row["high"]) if row["high"] is not None else 0, 6
                        ),
                        "low": round(
                            float(row["low"]) if row["low"] is not None else 0, 6
                        ),
                        "close": round(
                            float(row["close"]) if row["close"] is not None else 0, 6
                        ),
                        "volume": round(
                            float(row["volume"]) if row["volume"] is not None else 0, 6
                        ),
                        "decimals": 6,
                    },
                }
    except Exception as e:
        print(f"Error querying data for {symbol} (channel {subscription.channel}): {e}")
        await websocket.send_json(
            {"error": "failed to get ohlc data", "channel": subscription.channel}
        )
    return None


@channel_handler("token_info")
async def handle_token_info(
    subscription: ChannelSubscription, websocket: WebSocket
) -> Optional[Dict[str, Any]]:
    """Handle token_info channel updates.

    Channel format: token_info:{symbol}
    Example: token_info:USDM
    """
    symbol = subscription.params.get("symbol")

    if not symbol:
        await websocket.send_json(
            {
                "error": "Missing required parameter: symbol",
                "channel": subscription.channel,
            }
        )
        return None

    # Normalize symbol
    symbol = symbol.strip().upper()
    try:
        token_data = _get_token_info_data([symbol])  # have cache
        # Return update data
        if token_data is None or len(token_data) == 0:
            await websocket.send_json(
                {"error": "Token not found", "channel": subscription.channel}
            )
            return None
        token = token_data[0]
        result = {
            "channel": subscription.channel,
            "type": "token_info",
            "data": {
                "symbol": symbol,
                "name": token.name,
                "logo_url": token.logo_url,
                "price": token.price,
                "change_24h": token.change_24h,
                "low_24h": token.low_24h,
                "high_24h": token.high_24h,
                "volume_24h": token.volume_24h,
                "market_cap": token.market_cap,
                "decimals": 6,
            },
        }
        return result
    except Exception as e:
        print(
            f"Error querying token data for {symbol} (channel {subscription.channel}): {e}"
        )
        await websocket.send_json(
            {"error": "failed to get token info data", "channel": subscription.channel}
        )
        if isinstance(e, HTTPException) and e.status_code == 404:
            raise FatalSubscriptionError(f"Token not found: {symbol}")
    return None


websocket_schema = {
    "/ws": {
        "get": {
            "summary": "[WebSocket] Unified WebSocket endpoint",
            "tags": ["WebSocket"],
            "description": """Unified WebSocket endpoint for subscribing to multiple data channels.

**Connection:**
- Connect via WebSocket protocol (ws:// or wss://)
- Maximum 5 concurrent subscriptions per client
- Updates are sent every 60 seconds for active subscriptions

**Request Message Format:**
```json
{
    "action": "subscribe" | "unsubscribe",
    "channel": "{function}:{param1}|{param2}|..."
}
```

**Supported Channels:**

1. **OHLC (Candlestick Data)**
   - Format: `ohlc:{symbol}|{resolution}`
   - Example: `ohlc:USDM_ADA|5m`
   - Parameters:
     - `symbol`: Trading pair symbol (e.g., USDM_ADA, USDM_BTC)
     - `resolution`: Time resolution (e.g., 1m, 5m, 15m, 1h, 4h, 1d)
   - Response Data:
     ```json
     {
         "channel": "ohlc:USDM_ADA|5m",
         "type": "ohlc",
         "data": {
             "symbol": "USDM/ADA",
             "timestamp": 1234567890,
             "open": 0.123456,
             "high": 0.125000,
             "low": 0.122000,
             "close": 0.124500,
             "volume": 1000.123456,
             "decimals": 6
         }
     }
     ```

2. **Token Info**
   - Format: `token_info:{symbol}`
   - Example: `token_info:USDM`
   - Parameters:
     - `symbol`: Token symbol (e.g., USDM, ADA, BTC)
   - Response Data:
     ```json
     {
         "channel": "token_info:USDM",
         "type": "token_info",
         "data": {
             "symbol": "USDM",
             "name": "Token Name",
             "logo_url": "https://...",
             "price": 1.234567,
             "change_24h": 5.678901,
             "low_24h": 1.234567,
             "high_24h": 1.234567,
             "volume_24h": 1.234567,
             "market_cap": 1.234567,
             "decimals": 6
         }
     }
     ```

**Response Messages:**

- **Subscribe Success:**
  ```json
  {
      "status": "subscribed",
      "channel": "ohlc:USDM_ADA|5m",
      "type": "ohlc"
  }
  ```

- **Already Subscribed:**
  ```json
  {
      "status": "already_subscribed",
      "channel": "ohlc:USDM_ADA|5m"
  }
  ```

- **Unsubscribe Success:**
  ```json
  {
      "status": "unsubscribed",
      "channel": "ohlc:USDM_ADA|5m"
  }
  ```

- **Error Response:**
  ```json
  {
      "error": "Error message",
      "channel": "ohlc:USDM_ADA|5m"
  }
  ```

**Error Cases:**
- Missing required fields (action, channel)
- Invalid channel format
- Unknown channel type
- Maximum subscriptions reached (5)
- Invalid resolution (for OHLC channels)
- Token not found (for token_info channels)
- Invalid JSON format
                """,
            "responses": {
                "101": {
                    "description": "Switching Protocols - WebSocket connection established"
                }
            },
        }
    },
}
