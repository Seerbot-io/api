import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from fastapi import WebSocket, WebSocketDisconnect
from app.core.router_decorated import APIRouter
from app.api.endpoints.charting import get_chart_data, SUPPORTED_RESOLUTIONS
from app.api.endpoints.analysis import _get_token_info_data

router = APIRouter()
group_tags = ["WebSocket"]

# Channel handler registry
CHANNEL_HANDLERS = {}


def register_channel_handler(channel_type: str):
    """Decorator to register a channel handler function."""
    def decorator(func):
        CHANNEL_HANDLERS[channel_type] = func
        return func
    return decorator


class ChannelSubscription:
    """Represents a single channel subscription with its state."""
    def __init__(self, channel: str, channel_type: str, params: Dict[str, Any]):
        self.channel = channel
        self.channel_type = channel_type
        self.params = params
        self.state: Dict[str, Any] = {}


@register_channel_handler("ohlc")
async def handle_ohlc(
    subscription: ChannelSubscription,
    websocket: WebSocket
) -> Optional[Dict[str, Any]]:
    """Handle ohlc channel updates.
    
    Channel format: ohlc:{symbol}|{resolution}
    Example: ohlc:USDM_ADA|5m
    """
    symbol = subscription.params.get("symbol")
    resolution = subscription.params.get("resolution")
    
    if not symbol or not resolution:
        await websocket.send_json({
            "error": "Missing required parameters: symbol and resolution",
            "channel": subscription.channel
        })
        return None
    
    # Normalize symbol
    symbol = symbol.strip().replace("_", "/").upper()
    
    # Validate resolution
    if resolution not in SUPPORTED_RESOLUTIONS:
        await websocket.send_json({
            "error": f"Invalid resolution: {resolution}. Supported: {SUPPORTED_RESOLUTIONS}",
            "channel": subscription.channel
        })
        return None
    
    # Get last timestamp from state
    last_timestamp = subscription.state.get("last_timestamp", 0)
    
    try:
        # Get latest bar after last_timestamp
        result = get_chart_data(
            symbol=symbol,
            resolution=resolution,
            last_timestamp=last_timestamp,
            count_back=1
        )
        
        if result and len(result) > 0:
            row = result[0]
            current_timestamp = int(row['timestamp']) if row['timestamp'] else 0
            
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
                        "open": float(row['open']) if row['open'] is not None else 0.0,
                        "high": float(row['high']) if row['high'] is not None else 0.0,
                        "low": float(row['low']) if row['low'] is not None else 0.0,
                        "close": float(row['close']) if row['close'] is not None else 0.0,
                        "volume": float(row['volume']) if row['volume'] is not None else 0.0,
                    }
                }
    except Exception as e:
        print(f"Error querying data for {symbol} (channel {subscription.channel}): {e}")
        await websocket.send_json({
            "error": str(e),
            "channel": subscription.channel
        })
    return None

@register_channel_handler("token_info")
async def handle_token_info(
    subscription: ChannelSubscription,
    websocket: WebSocket
) -> Optional[Dict[str, Any]]:
    """Handle token_info channel updates.
    
    Channel format: token_info:{symbol}
    Example: token_info:USDM
    """
    symbol = subscription.params.get("symbol")
    
    if not symbol:
        await websocket.send_json({
            "error": "Missing required parameter: symbol",
            "channel": subscription.channel
        })
        return None
    
    # Normalize symbol
    symbol = symbol.strip().upper()
    try:
        token_data = _get_token_info_data(symbol)
        
        # Return update data
        return {
            "channel": subscription.channel,
            "type": "token_info",
            "data": {
                "symbol": symbol,
                "name": token_data.get("name"),
                "symbol": token_data.get("symbol"),
                "price": token_data.get("price", 0.0),
                "change_24h": token_data.get("change_24h", 0.0),
                "price_change_percentage": token_data.get("price_change_percentage", 0.0),
                "price_change_percentage_24h": token_data.get("price_change_percentage_24h", 0.0),
                "price_change_percentage_7d": token_data.get("price_change_percentage_7d", 0.0),
                "price_change_percentage_30d": token_data.get("price_change_percentage_30d", 0.0),
            }
        }
    except Exception as e:
        print(f"Error querying token data for {symbol} (channel {subscription.channel}): {e}")
        await websocket.send_json({
            "error": str(e),
            "channel": subscription.channel
        })
    return None

def parse_channel(channel: str) -> Tuple[str, Dict[str, Any]]:
    """Parse channel string into channel type and parameters.
    
    Format: {function}:{param1}|{param2}|...
    
    Examples:
    - ohlc:USDM_ADA|5m -> ("ohlc", {"symbol": "USDM_ADA", "resolution": "5m"})
    - token_info:USDM -> ("token_info", {"symbol": "USDM"})
    """
    if ":" not in channel:
        raise ValueError(f"Invalid channel format: {channel}. Expected format: {{function}}:{{param1}}|{{param2}}|...")
    
    channel_type, params_str = channel.split(":", 1)
    
    if not params_str:
        raise ValueError(f"Invalid channel format: {channel}. Missing parameters after ':'")
    
    # Parse parameters based on channel type
    if channel_type == "ohlc":
        # Format: ohlc:{symbol}|{resolution}
        # Use pipe (|) as separator to handle symbols with underscores
        parts = params_str.split("|")
        if len(parts) != 2:
            raise ValueError(f"Invalid ohlc channel format: {channel}. Expected: ohlc:{{symbol}}|{{resolution}}")
        
        symbol = parts[0]
        resolution = parts[1]
        
        if not symbol or not resolution:
            raise ValueError(f"Invalid ohlc channel format: {channel}. Missing symbol or resolution")
        
        return channel_type, {
            "symbol": symbol,
            "resolution": resolution
        }
    
    elif channel_type == "token_info":
        # Format: token_info:{symbol}
        # No separator needed for single parameter
        if not params_str:
            raise ValueError(f"Invalid token_info channel format: {channel}. Missing symbol")
        
        return channel_type, {
            "symbol": params_str
        }
    
    else:
        raise ValueError(f"Unknown channel type: {channel_type}. Supported types: ohlc, token_info")


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
    
    # Track subscriptions: {channel: ChannelSubscription}
    subscriptions: Dict[str, ChannelSubscription] = {}
    
    print(f"WebSocket connected: {websocket}")
    
    try:
        while True:
            try:
                # Receive message (with timeout to allow periodic updates)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)
                
                action = message.get("action")
                channel = message.get("channel", "").strip()
                
                if not action or not channel:
                    await websocket.send_json({
                        "error": "Missing required fields: action and channel"
                    })
                    continue
                
                if action == "subscribe":
                    try:
                        # Parse channel
                        channel_type, params = parse_channel(channel)
                        
                        # Check if handler exists
                        if channel_type not in CHANNEL_HANDLERS:
                            await websocket.send_json({
                                "error": f"Unknown channel type: {channel_type}",
                                "channel": channel
                            })
                            continue
                        
                        # Create subscription if it doesn't exist
                        if channel not in subscriptions:
                            subscriptions[channel] = ChannelSubscription(
                                channel=channel,
                                channel_type=channel_type,
                                params=params
                            )
                            
                            await websocket.send_json({
                                "status": "subscribed",
                                "channel": channel,
                                "type": channel_type
                            })
                        else:
                            await websocket.send_json({
                                "status": "already_subscribed",
                                "channel": channel
                            })
                    
                    except ValueError as e:
                        await websocket.send_json({
                            "error": str(e),
                            "channel": channel
                        })
                
                elif action == "unsubscribe":
                    if channel in subscriptions:
                        del subscriptions[channel]
                        await websocket.send_json({
                            "status": "unsubscribed",
                            "channel": channel
                        })
                    else:
                        await websocket.send_json({
                            "error": f"Subscription not found for channel: {channel}",
                            "channel": channel
                        })
                
                else:
                    await websocket.send_json({
                        "error": f"Invalid action: {action}. Expected 'subscribe' or 'unsubscribe'"
                    })
            
            except asyncio.TimeoutError:
                # Timeout is expected - continue to send updates
                pass
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                await websocket.send_json({"error": str(e)})
            
            # Send real-time updates for all active subscriptions
            if subscriptions:
                for channel, subscription in subscriptions.items():
                    try:
                        # Get handler for this channel type
                        handler = CHANNEL_HANDLERS.get(subscription.channel_type)
                        if handler:
                            # Get update data
                            update_data = await handler(subscription, websocket)
                            
                            # Send update if available
                            if update_data:
                                await websocket.send_json(update_data)
                    
                    except Exception as e:
                        print(f"Error processing subscription {channel}: {e}")
            
            # Wait before next update cycle
            # await asyncio.sleep(10)
    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass

