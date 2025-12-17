class CachedRow:
    """Simple row-like object for cached data"""

    def __init__(self, data: dict):
        self.timestamp = data.get("timestamp")
        self.open = data.get("open")
        self.high = data.get("high")
        self.low = data.get("low")
        self.close = data.get("close")
        self.volume = data.get("volume")
