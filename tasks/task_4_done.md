# PATH
GET	GET /analysis/tokens/{symbol}

# Description
Get token Market info


# Input Parameters
symbol (String): token symbol


# Output Parameters
"id: onchain address
name: token name
symbol: token symbol
price: token price in USD
change_24h: token price change in 24h
low_24h: token lowest price in 24h
high_24h: token lowest price in 24h
volume_24h: token trade volume in 24h\"


# Example Request
GET /analysis/tokens/USDM

# Example Response
"{
  ""id"": ""addr1qxy99g3k...tokenaddress"",
  ""name"": ""USDM"",
  ""symbol"": ""USDM"",
  ""price"": 50000.00,
  ""change_24h"": -1.25,
  ""low_24h"": 49500.00,
  ""high_24h"": 51500.00,
  ""volume_24h"": 982345000.00
}
"