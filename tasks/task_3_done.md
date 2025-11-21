# PATH
GET	GET /analysis/tokens

# Description
Search or list available tokens

# Input Parameters
"search (string, optional): seach key word
limit (int, optional): max records
offset (int, optional): skip records"


# Output Parameters
"tokens:
  - id: onchain address
  - name: token name
  - symbol: token symbol"


# Example Request
"GET /analysis/tokens

 {
    ""search"": ""usd"",
    ""limit"": 1,
    ""offset"": 0,
 }"


# Example Response
"[{
  ""id"": ""addr1qxy99g3k...tokenaddress"",
  ""name"": ""USDM"",
  ""symbol"": ""USDM"",
}, ...
]"