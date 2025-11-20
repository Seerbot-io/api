from __future__ import annotations

# redis caching manager system
import hashlib
import inspect
import json
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

from redis import Connection, ConnectionPool, Redis, SSLConnection

from app.core.config import settings

CacheTTLFactory = Callable[[], Optional[int]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def seconds_until_next_interval(minutes: int, *, now: datetime | None = None) -> int:
    """
    Return the number of seconds until the next interval boundary.
    Example: when minutes=5 the cache expires at hh:00, hh:05, hh:10, ...
    """
    if minutes <= 0:
        raise ValueError("minutes must be positive")

    start = (now or _utc_now())
    current = start.replace(second=0)
    next_minute = (current.minute // minutes + 1) * minutes

    if next_minute >= 60:
        boundary = current.replace(minute=0) + timedelta(hours=1)
    else:
        boundary = current.replace(minute=next_minute)

    delta = int((boundary - start).total_seconds())
    return max(delta, 1)


def seconds_until_hour_minute(minute_mark: int, *, now: datetime | None = None) -> int:
    """
    Return the seconds until the clock reaches HH:minute_mark.
    """
    if minute_mark < 0 or minute_mark >= 60:
        raise ValueError("minute_mark must be within [0, 59]")

    current = (now or _utc_now())
    boundary = current.replace(minute=minute_mark, second=0)
    if current.minute >= minute_mark:
        boundary += timedelta(hours=1)

    delta = int((boundary - current).total_seconds())
    return max(delta, 1)


def _static_ttl(seconds: int) -> CacheTTLFactory:
    def factory() -> int:
        return max(int(seconds), 0)

    return factory


def _dynamic_ttl(func: Callable[[], int]) -> CacheTTLFactory:
    def factory() -> int:
        return max(int(func()), 1)

    return factory


CACHE_TYPE: Dict[str, Dict[str, CacheTTLFactory]] = {
    'no-exp': {
        'ttl_factory': lambda: None,
    },
    'in-1m': {
        'ttl_factory': _static_ttl(60),
    },
    'in-5m': {
        'ttl_factory': _static_ttl(300),
    },
    'in-30m': {
        'ttl_factory': _static_ttl(1800),
    },
    'in-1h': {
        'ttl_factory': _static_ttl(3600),
    },
    'at-eh-m5': {
        'ttl_factory': _dynamic_ttl(lambda: seconds_until_hour_minute(5)),
    },
    'at-eh-m10': {
        'ttl_factory': _dynamic_ttl(lambda: seconds_until_hour_minute(10)),
    },
    'at-e5m': {
        'ttl_factory': _dynamic_ttl(lambda: seconds_until_next_interval(5)),
    },
    'at-e30m': {
        'ttl_factory': _dynamic_ttl(lambda: seconds_until_next_interval(30)),
    },
}


def resolve_cache_ttl(cache_type: str) -> Optional[int]:
    """Resolve cache type to TTL in seconds"""
    config = CACHE_TYPE.get(cache_type)
    if not config:
        return None

    ttl_factory = config['ttl_factory']
    ttl = ttl_factory()
    if ttl is None:
        return None

    return max(int(ttl), 0)


class HybridCacheManager:
    """Hybrid cache manager with Redis + in-memory fallback"""
    
    _instance: Optional['HybridCacheManager'] = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.pool = ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            socket_connect_timeout=0.05,
            socket_timeout=5,
            retry_on_timeout=False,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            connection_class=SSLConnection if settings.REDIS_SSL else Connection
        )
        self.redis_available = False
        self.memory_cache: Dict[str, Tuple[bytes, Optional[float]]] = {}
        self._memory_lock = Lock()
        self._initialized = True
    
    def redis_connect(self) -> Optional[Redis]:
        try:
            rc = Redis(connection_pool=self.pool)
            if rc.ping():
                if not self.redis_available:
                    print("Redis cache connection available")
                self.redis_available = True
                return rc
            print("Failed to connect to Redis")
        except Exception as e:
            if self.redis_available:
                print("Lost Redis connection", e)
            else:
                print("Failed to connect to Redis", e)
        self.redis_available = False
        return None
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value, deserializing from JSON"""
        # Try Redis first
        result = self._get_redis(key)
        if result is not None:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return None
        
        # Fallback to memory
        result = self._get_memory(key)
        if result is not None:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return None
        return None
    
    def set(self, key: str, value: Any, cache_type: str = 'in-5m') -> bool:
        """Set cached value, serializing to JSON"""
        try:
            data = json.dumps(value, default=str).encode('utf-8')
        except (TypeError, ValueError) as e:
            print(f"Failed to serialize cache value: {e}")
            return False
        
        ttl_seconds = resolve_cache_ttl(cache_type)
        
        # Try Redis first
        if self._set_redis(key, data, ttl_seconds):
            return True
        
        # Fallback to memory
        self._set_memory(key, data, ttl_seconds)
        return True
    
    def _set_redis(self, key: str, data: bytes, ttl_seconds: Optional[int]) -> bool:
        rc = self.redis_connect()
        if rc is None:
            return False
        try:
            rc.set(key, data)
            if ttl_seconds is not None and ttl_seconds > 0:
                rc.expire(key, ttl_seconds)
            return True
        except Exception as e:
            print("Failed to set Redis cache", e)
            return False
        finally:
            rc.close()
    
    def _get_redis(self, key: str) -> Optional[bytes]:
        rc = self.redis_connect()
        if rc is None:
            return None
        try:
            result = rc.get(key)
            if result is not None and result != b'':
                return result
            return None
        except Exception as e:
            print("Failed to read Redis cache", e)
            return None
        finally:
            rc.close()
    
    def _set_memory(self, key: str, data: bytes, ttl_seconds: Optional[int]) -> None:
        expires_at = None if ttl_seconds is None else time.time() + ttl_seconds
        with self._memory_lock:
            self.memory_cache[key] = (data, expires_at)
    
    def _get_memory(self, key: str) -> Optional[bytes]:
        now = time.time()
        with self._memory_lock:
            cached = self.memory_cache.get(key)
            if cached is None:
                return None
            value, expires_at = cached
            if expires_at is not None and expires_at <= now:
                self.memory_cache.pop(key, None)
                return None
            return value


# Global singleton instance
cache_manager = HybridCacheManager()


def _make_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Generate cache key from function name and arguments"""
    # Convert args and kwargs to a stable string representation
    key_parts = [func_name]
    
    # Add args (skip 'self' and 'cls')
    for arg in args:
        if isinstance(arg, (str, int, float, bool, type(None))):
            key_parts.append(str(arg))
        else:
            # For complex objects, use their string representation
            key_parts.append(str(hash(str(arg))))
    
    # Add kwargs (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool, type(None))):
            key_parts.append(f"{k}:{v}")
        else:
            key_parts.append(f"{k}:{hash(str(v))}")
    
    key_str = "|".join(key_parts)
    # Hash for shorter keys
    return f"cache:{hashlib.md5(key_str.encode()).hexdigest()}"


def cache(cache_type: str = 'in-5m', key_prefix: Optional[str] = None):
    """
    Decorator for caching function results with hybrid Redis + memory fallback.
    
    Args:
        cache_type: Cache type from CACHE_TYPE (e.g., 'at-e5m', 'in-5m', 'in-1h')
        key_prefix: Optional prefix for cache key (defaults to function name)
    
    Example:
        @cache('at-e5m')
        def get_predictions():
            return expensive_operation()
    """
    def decorator(func: Callable) -> Callable:
        func_name = key_prefix or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _make_cache_key(func_name, args, kwargs)
            
            # Try to get from cache
            cached = cache_manager.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            cache_manager.set(cache_key, result, cache_type)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _make_cache_key(func_name, args, kwargs)
            
            # Try to get from cache
            cached = cache_manager.get(cache_key)
            if cached is not None:
                return cached
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache_manager.set(cache_key, result, cache_type)
            
            return result
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
