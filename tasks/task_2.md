# PATH
GET	/analysis/toptraders	

# Description
Retrieves a list of top traders based on trading volume, profit, or other metrics. Shows the most successful or active traders in the system.

# Input Parameters
"limit (integer, optional): Number of top traders to return (default: 10, max: 100)
metric (string, optional): Ranking metric ('volume', 'profit', 'trades', default: 'volume')
period (string, optional): Time period ('24h', '7d', '30d', 'all', default: '24h')
pair(string, optional): Filter by trading pair"


# Output Parameters
"traders (array): Array of trader objects
 - user_id (string): User identifier
 - total_volume (float): Total trading volume
 - total_trades (integer): Number of trades
 - rank (integer): Trader rank
period (string): Selected time period
timestamp (integer): Data timestamp in seconds"

# Example Request
GET /analysis/toptraders?limit=20&metric=volume&period=7d

# Example Response
"{
  ""traders"": [
    {
      ""user_id"": ""user_123"",
      ""total_volume"": 1000000.00,
      ""total_trades"": 150,
      ""rank"": 1
    },
    {
      ""user_id"": ""user_456"",
      ""total_volume"": 800000.00,
      ""total_trades"": 120,
      ""rank"": 2
    }
  ],
  ""period"": ""7d"",
  ""timestamp"": 1697123456
}"