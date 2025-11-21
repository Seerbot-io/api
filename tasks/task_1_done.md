# PATH
GET	/analysis/indicators

# Description
Retrieves OHLC (Open, High, Low, Close) candlestick data and technical indicators (RSI7, RSI14, ADX14, PSAR) for a given trading pair. Used for technical analysis and charting.

# Input Parameters
"pair (string, required): Trading pair pair join by underscore ""_"" (e.g., 'USDM_ADA', )
timeframe (string, required): Time interval ('5m', '30m', '1h', '4h', '1d')
limit (integer, optional): Number of candles to return (default: 100, max: 1000)
from_time (integer, optional): Start timestamp in seconds
to_time (integer, optional): End timestamp in seconds
indicators (string, optional): Comma-separated list of indicators to include (default: 'rsi7,rsi14,adx14,psar')"

# Output Parameters
"data (array): Array of OHLC and indicator data objects
 - timestamp (integer): Candle timestamp in seconds
 - open (float): Opening price
 - high (float): Highest price
 - low (float): Lowest price
 - close (float): Closing price
 - volume (float): Trading volume
 - rsi7 (float): RSI 7-period value
 - rsi14 (float): RSI 14-period value
 - adx14 (float): ADX 14-period value
 - psar (float): Parabolic SAR value
pair (string): Trading pair
timeframe (string): Time interval"

# Example Request
GET /analysis/indicators?pair=USDM_ADA&timeframe=1h&limit=200&indicators=rsi7,rsi14,adx14,psar

# Example Response
"{
  ""pair"": ""USDM/ADA"",
  ""timeframe"": ""1h"",
  ""data"": [
    {
      ""timestamp"": 1697122800,
      ""open"": 50000.00,
      ""high"": 50100.00,
      ""low"": 49900.00,
      ""close"": 50050.00,
      ""volume"": 1250.5,
      ""rsi7"": 55.2,
      ""rsi14"": 58.7,
      ""adx14"": 25.3,
      ""psar"": 49950.00
    },
    {
      ""timestamp"": 1697126400,
      ""open"": 50050.00,
      ""high"": 50200.00,
      ""low"": 50000.00,
      ""close"": 50150.00,
      ""volume"": 1380.2,
      ""rsi7"": 57.8,
      ""rsi14"": 60.1,
      ""adx14"": 26.5,
      ""psar"": 50000.00
    }
  ]
}"
