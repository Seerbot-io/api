from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import time

from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal


@dataclass
class CachedTokenInfo:
    """Static token information"""
    id: str
    name: str
    symbol: str
    logo_url: str
    total_supply: float
    last_updated: datetime
    ttl_seconds: int = 3600  # 1 hour default
    
    @property
    def is_expired(self) -> bool:
        """Check if cached info is expired"""
        return datetime.now() - self.last_updated > timedelta(seconds=self.ttl_seconds)


@dataclass
class CachedTokenPrice:
    """Token price and 24h statistics"""
    price: float
    change_24h: float
    low_24h: float
    high_24h: float
    volume_24h: float
    market_cap: float
    last_updated: datetime
    ttl_seconds: int = 30  # 30 seconds default
    
    @property
    def is_expired(self) -> bool:
        """Check if cached price is expired"""
        return datetime.now() - self.last_updated > timedelta(seconds=self.ttl_seconds)


class TokenPriceCacheManager:
    """
    Singleton token price cache manager with separate caches for static info and price data.
    Supports lazy loading by default with optional background refresh.
    """
    
    _instance: Optional["TokenPriceCacheManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern with double-checked locking"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize cache manager (only once due to singleton)"""
        if hasattr(self, "_initialized") and self._initialized:
            return
        
        # Separate caches for info and price data
        self._info_cache: Dict[str, CachedTokenInfo] = {}
        self._price_cache: Dict[str, CachedTokenPrice] = {}
        
        # USDM/ADA price cache (used for USD conversions)
        self._ada_price_cache: Optional[float] = None
        self._ada_price_updated: Optional[datetime] = None
        self._ada_price_ttl = 30  # 30 seconds TTL for ADA price
        
        # Configuration from settings
        self._info_ttl = getattr(settings, "TOKEN_CACHE_INFO_TTL", 3600)
        self._price_ttl = getattr(settings, "TOKEN_CACHE_PRICE_TTL", 30)
        self._refresh_interval = getattr(settings, "TOKEN_CACHE_REFRESH_INTERVAL", 15)
        self._enable_background_refresh = getattr(
            settings, "TOKEN_CACHE_ENABLE_BACKGROUND_REFRESH", False
        )
        
        # Thread safety
        self._cache_lock = threading.RLock()
        
        # Background refresh state
        self._running = False
        self._refresh_thread: Optional[threading.Thread] = None
        
        self._initialized = True
    
    def _get_ada_price_usd(self) -> Optional[float]:
        """Get USDM/ADA price in USD, cached for 30 seconds"""
        now = datetime.now()
        
        # Check cache outside lock first (read-only check)
        if (
            self._ada_price_cache is not None
            and self._ada_price_updated is not None
            and (now - self._ada_price_updated).total_seconds() < self._ada_price_ttl
        ):
            return self._ada_price_cache
        
        # Need to fetch - acquire lock
        with self._cache_lock:
            # Double-check after acquiring lock
            if (
                self._ada_price_cache is not None
                and self._ada_price_updated is not None
                and (now - self._ada_price_updated).total_seconds() < self._ada_price_ttl
            ):
                return self._ada_price_cache
            
            # Fetch fresh price from database
            try:
                db = SessionLocal()
                try:
                    time_24h_ago = int(now.timestamp()) - 24 * 60 * 60
                    query = text(
                        f"""
                        SELECT close as price_ada
                        FROM proddb.coin_prices_5m cph
                        WHERE symbol='USDM/ADA'
                            AND open_time > {time_24h_ago}
                        ORDER BY open_time DESC
                        LIMIT 1
                        """
                    )
                    result = db.execute(query).fetchone()
                    
                    if result and hasattr(result, "price_ada") and result.price_ada:
                        self._ada_price_cache = float(result.price_ada)
                        self._ada_price_updated = now
                        return self._ada_price_cache
                finally:
                    db.close()
            except Exception as e:
                print(f"Failed to fetch ADA price: {e}")
                # Return cached value even if expired as fallback
                return self._ada_price_cache
        
        return None
    
    def _normalize_symbols(self, symbols: List[str]) -> List[str]:
        """Normalize and deduplicate symbols"""
        normalized = [s.strip().upper() for s in symbols if s.strip()]
        # Remove duplicates while preserving order
        seen = set()
        return [s for s in normalized if s not in seen and not seen.add(s)]
    
    def _fetch_token_info_from_db(self, symbols: List[str]) -> Dict[str, CachedTokenInfo]:
        """Fetch static token info from proddb.tokens (rarely updates)"""
        normalized_symbols = self._normalize_symbols(symbols)
        if not normalized_symbols:
            return {}
        
        result: Dict[str, CachedTokenInfo] = {}
        db = SessionLocal()
        
        try:
            symbols_str = "('" + "', '".join(normalized_symbols) + "')"
            query = text(
                f"""
                SELECT id, name, symbol, logo_url, total_supply
                FROM proddb.tokens
                WHERE symbol IN {symbols_str}
                """
            )
            tokens = db.execute(query).fetchall()
            
            now = datetime.now()
            for token in tokens:
                symbol = str(token.symbol).upper() if hasattr(token, "symbol") else ""
                if symbol:
                    result[symbol] = CachedTokenInfo(
                        id=str(token.id) if hasattr(token, "id") else "",
                        name=str(token.name) if hasattr(token, "name") else "",
                        symbol=symbol,
                        logo_url=str(token.logo_url) if hasattr(token, "logo_url") else "",
                        total_supply=float(token.total_supply) if hasattr(token, "total_supply") and token.total_supply else 0.0,
                        last_updated=now,
                        ttl_seconds=self._info_ttl
                    )
        except Exception as e:
            print(f"Failed to fetch token info from DB: {e}")
        finally:
            db.close()
        
        return result
    
    def get_token_info(self, symbol: str) -> Optional[CachedTokenInfo]:
        """Get static token info, check cache first, then fetch from proddb.tokens if needed"""
        symbol = symbol.strip().upper()
        
        # Quick check without lock (read-only)
        cached = self._info_cache.get(symbol)
        if cached and not cached.is_expired:
            return cached
        
        # Need to fetch - acquire lock
        with self._cache_lock:
            # Double-check after acquiring lock
            cached = self._info_cache.get(symbol)
            if cached and not cached.is_expired:
                return cached
            
            # Fetch from DB if missing or expired
            try:
                fresh_info = self._fetch_token_info_from_db([symbol])
                if symbol in fresh_info:
                    self._info_cache[symbol] = fresh_info[symbol]
                    return fresh_info[symbol]
            except Exception as e:
                print(f"Failed to fetch token info for {symbol}: {e}")
                # Return stale data if available
                return cached if cached else None
        
        return None
    
    def _fetch_token_price_from_db(self, symbols: List[str]) -> Dict[str, CachedTokenPrice]:
        """Fetch token price data (frequently updates)"""
        normalized_symbols = self._normalize_symbols(symbols)
        if not normalized_symbols:
            return {}
        
        # Get cached ADA price for USD conversions
        price_ada = self._get_ada_price_usd()
        if price_ada is None or price_ada <= 0:
            print("Warning: ADA price not available, cannot convert to USD")
            return {}
        
        time_now = (int(datetime.now().timestamp()) // 300 - 1) * 300
        time_24h_ago = time_now - 24 * 60 * 60
        now = datetime.now()
        result: Dict[str, CachedTokenPrice] = {}
        
        # Process ADA separately if needed
        process_ada = "ADA" in normalized_symbols
        if process_ada:
            normalized_symbols.remove("ADA")
        
        db = SessionLocal()
        try:
            # Fetch ADA data if needed
            if process_ada:
                # Get current USDM/ADA price and change_24h 
                price_query = text(
                    f"""
                    SELECT price, ((price - price_24h) / price) * 100 as change_24h
                    FROM (
                        SELECT open_time, close as price, 
                               lead(close, 3) over (ORDER BY open_time desc) price_24h, 
                               row_number() over (ORDER BY open_time desc) as r
                        FROM proddb.coin_prices_5m cph
                        WHERE symbol='USDM/ADA'
                            AND ((open_time >= {time_24h_ago} - 900 AND open_time <= {time_24h_ago})
                                OR open_time > {time_now} - 600)
                    ) coin
                    WHERE r = 1
                    """
                )
                price_result = db.execute(price_query).fetchone()
                
                # Get 24h stats
                stats_query = text(
                    f"""
                    SELECT min(low) as low_24h, max(high) as high_24h, sum(volume) as volume_24h
                    FROM proddb.coin_prices_1h cph
                    WHERE symbol='USDM/ADA'
                        AND open_time > {time_24h_ago}
                    """
                )
                stats_result = db.execute(stats_query).fetchone()
                
                if price_result:
                    change_24h = float(price_result.change_24h) if hasattr(price_result, "change_24h") and price_result.change_24h else 0.0
                    low_24h_usd = float(stats_result.low_24h) if stats_result and hasattr(stats_result, "low_24h") and stats_result.low_24h else 0.0
                    high_24h_usd = float(stats_result.high_24h) if stats_result and hasattr(stats_result, "high_24h") and stats_result.high_24h else 0.0
                    volume_24h_usd = float(stats_result.volume_24h) if stats_result and hasattr(stats_result, "volume_24h") and stats_result.volume_24h else 0.0
                    
                    result["ADA"] = CachedTokenPrice(
                        price=price_ada,
                        change_24h=change_24h,
                        low_24h=low_24h_usd,
                        high_24h=high_24h_usd,
                        volume_24h=volume_24h_usd,
                        market_cap=0.0,
                        last_updated=now,
                        ttl_seconds=self._price_ttl
                    )
            
            # Process other tokens
            if normalized_symbols:
                pairs_list = [f"{symbol}/ADA" for symbol in normalized_symbols]
                pairs_str = "('" + "', '".join(pairs_list) + "')"
                
                # Get current prices and 24h stats in parallel queries
                price_query = text(
                    f"""
                    SELECT symbol, price, ((price - price_24h) / price) * 100 as change_24h
                    FROM (
                        SELECT symbol, open_time, close as price, 
                               lead(close, 3) over (PARTITION BY symbol ORDER BY open_time desc) price_24h, 
                               row_number() over (PARTITION BY symbol ORDER BY open_time desc) as r
                        FROM proddb.coin_prices_5m cph
                        WHERE symbol IN {pairs_str}
                            AND ((open_time >= {time_24h_ago} - 900 AND open_time <= {time_24h_ago})
                                OR open_time > {time_now} - 600)
                    ) coin
                    WHERE r = 1
                    """
                )
                stats_query = text(
                    f"""
                    SELECT symbol, min(low) as low_24h, max(high) as high_24h, sum(volume) as volume_24h
                    FROM proddb.coin_prices_1h cph
                    WHERE symbol IN {pairs_str}
                        AND open_time > {time_24h_ago}
                    GROUP BY symbol
                    """
                )
                
                price_results = db.execute(price_query).fetchall()
                stats_results = db.execute(stats_query).fetchall()
                
                price_dict = {row.symbol: row for row in price_results}
                stats_dict = {row.symbol: row for row in stats_results}
                
                # Convert to USD using cached price_ada
                for symbol in normalized_symbols:
                    pair = f"{symbol}/ADA"
                    price_row = price_dict.get(pair)
                    stats_row = stats_dict.get(pair)
                    
                    if price_row:
                        price_ada_token = float(price_row.price) if hasattr(price_row, "price") and price_row.price else 0.0
                        change_24h = float(price_row.change_24h) if hasattr(price_row, "change_24h") and price_row.change_24h else 0.0
                        
                        # Convert to USD
                        price_usd = price_ada_token / price_ada if price_ada > 0 else 0.0
                        
                        # Get 24h stats and convert to USD
                        low_24h_usd = (float(stats_row.low_24h) / price_ada) if stats_row and hasattr(stats_row, "low_24h") and stats_row.low_24h else 0.0
                        high_24h_usd = (float(stats_row.high_24h) / price_ada) if stats_row and hasattr(stats_row, "high_24h") and stats_row.high_24h else 0.0
                        volume_24h_usd = (float(stats_row.volume_24h) / price_ada) if stats_row and hasattr(stats_row, "volume_24h") and stats_row.volume_24h else 0.0
                        
                        result[symbol] = CachedTokenPrice(
                            price=price_usd,
                            change_24h=change_24h,
                            low_24h=low_24h_usd,
                            high_24h=high_24h_usd,
                            volume_24h=volume_24h_usd,
                            market_cap=0.0,
                            last_updated=now,
                            ttl_seconds=self._price_ttl
                        )
        except Exception as e:
            print(f"Failed to fetch token prices from DB: {e}")
        finally:
            db.close()
        
        return result
    
    def get_token_price(self, symbol: str) -> Optional[CachedTokenPrice]:
        """Get token price data, check cache first, then fetch from coin_prices tables if needed"""
        symbol = symbol.strip().upper()
        
        # Quick check without lock (read-only)
        cached = self._price_cache.get(symbol)
        if cached and not cached.is_expired:
            return cached
        
        # Need to fetch - acquire lock
        with self._cache_lock:
            # Double-check after acquiring lock
            cached = self._price_cache.get(symbol)
            if cached and not cached.is_expired:
                return cached
            
            # Fetch from DB if missing or expired
            try:
                fresh_prices = self._fetch_token_price_from_db([symbol])
                if symbol in fresh_prices:
                    self._price_cache[symbol] = fresh_prices[symbol]
                    return fresh_prices[symbol]
            except Exception as e:
                print(f"Failed to fetch token price for {symbol}: {e}")
                # Return stale data if available
                return cached if cached else None
        
        return None
    
    def get_pair_price(self, pair: str) -> Optional[float]:
        """
        Get current price for a trading pair.
        
        Handles three cases:
        1. Direct pair (e.g., 'USDM/ADA'): Returns price directly
        2. Inverted pair (e.g., 'ADA/USDM'): Returns 1/price (inverted)
        3. Cross pair (e.g., 'USDM/NIGHT'): Calculates from (USDM/ADA) / (NIGHT/ADA)
        
        Args:
            pair: Trading pair in format 'BASE/QUOTE' (e.g., 'USDM/ADA', 'ADA/USDM', 'USDM/NIGHT')
        
        Returns:
            Current price as float, or None if pair cannot be resolved
        """
        pair = pair.strip().upper()
        
        # Parse pair
        if "/" not in pair:
            print(f"Invalid pair format: {pair}. Expected format: 'BASE/QUOTE'")
            return None
        
        base, quote = pair.split("/", 1)
        base = base.strip()
        quote = quote.strip()
        
        if not base or not quote:
            print(f"Invalid pair format: {pair}")
            return None
        
        # Case 1: Direct pair (TOKEN/ADA) - get price directly
        if quote == "ADA":
            price_data = self.get_token_price(base)
            if price_data:
                return price_data.price
            return None
        
        # Case 2: Inverted pair (ADA/TOKEN) - return 1/price
        if base == "ADA":
            price_data = self.get_token_price(quote)
            if price_data and price_data.price > 0:
                return 1.0 / price_data.price
            return None
        
        # Case 3: Cross pair (TOKEN1/TOKEN2) - calculate from both prices
        # Price = (TOKEN1/ADA) / (TOKEN2/ADA)
        base_price_data = self.get_token_price(base)
        quote_price_data = self.get_token_price(quote)
        
        if base_price_data and quote_price_data:
            base_price = base_price_data.price
            quote_price = quote_price_data.price
            
            if quote_price > 0:
                return base_price / quote_price
        
        return None
    
    def _refresh_all_prices(self):
        """Background refresh method - updates price cache for all cached tokens"""
        with self._cache_lock:
            if not self._price_cache:
                return
            symbols = list(self._price_cache.keys())
        
        if not symbols:
            return
        
        try:
            # Fetch fresh prices from DB
            fresh_prices = self._fetch_token_price_from_db(symbols)
            
            # Update cache with fresh data
            with self._cache_lock:
                for symbol, price_data in fresh_prices.items():
                    if symbol in self._price_cache:
                        self._price_cache[symbol] = price_data
        except Exception as e:
            print(f"Failed to refresh prices in background: {e}")
    
    def _background_refresh_loop(self):
        """Background refresh loop - runs continuously if enabled"""
        while self._running:
            try:
                start_time = time.time()
                self._refresh_all_prices()
                elapsed = time.time() - start_time
                
                # Sleep for remaining time in interval, but at least 1 second
                sleep_time = max(1, self._refresh_interval - elapsed)
                time.sleep(sleep_time)
            except Exception as e:
                print(f"Error in price refresh loop: {e}")
                time.sleep(5)  # Brief pause on error
    
    def start_background_refresh(self):
        """Start background price refresh thread (only if enabled in config)"""
        if not self._enable_background_refresh:
            return
        
        if self._running:
            return
        
        self._running = True
        self._refresh_thread = threading.Thread(
            target=self._background_refresh_loop,
            daemon=True,
            name="TokenPriceRefresh"
        )
        self._refresh_thread.start()
    
    def stop_background_refresh(self):
        """Stop background price refresh thread"""
        self._running = False
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5)
    
    def clear_cache(self):
        """Clear all cached data"""
        with self._cache_lock:
            self._info_cache.clear()
            self._price_cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        with self._cache_lock:
            total_info_cached = len(self._info_cache)
            total_price_cached = len(self._price_cache)
            expired_info_count = sum(
                1 for c in self._info_cache.values() if c.is_expired
            )
            expired_price_count = sum(
                1 for c in self._price_cache.values() if c.is_expired
            )
        
        return {
            "info_cache_size": total_info_cached,
            "price_cache_size": total_price_cached,
            "expired_info_count": expired_info_count,
            "expired_price_count": expired_price_count,
            "background_refresh_enabled": self._enable_background_refresh,
            "background_refresh_running": self._running,
            "info_ttl_seconds": self._info_ttl,
            "price_ttl_seconds": self._price_ttl,
            "refresh_interval_seconds": self._refresh_interval,
        }
