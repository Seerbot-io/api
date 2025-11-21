# *TASK 6*

# PATH
POST	/analysis/swaps

# Description
Creates a new swap transaction record. Used to record a token swap operation where one asset is exchanged for another.


# Input Parameters
"Request Header:
 - Authorization: Session token
Request Body (JSON):
 - transaction_id (string, required): On chain transaction ID
 - from_token (string, required): Source token symbol
 - to_token (string, required): Destination token symbol
 - from_amount (float, required): Amount of source token
 - to_amount (float, required): Amount of destination token
 - price (float, required): Exchange rate
 - timestamp (integer, optional): Transaction timestamp in seconds (defaults to current time)
"

# Output Parameters
"transaction_id (string): On chain transaction ID
status (string): Transaction status ('pending', 'completed', 'failed')"

# Example Request
"POST /analysis/swaps
 Content-Type: application/json
 Authorization: Bearer <session_token>

 {
  ""transaction_id"": ""998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb"",
  ""from_token"": ""USDM"",
  ""to_token"": ""ADA"",
  ""from_amount"": 0.1,
  ""to_amount"": 5000.00,
  ""price"": 50000.00
 }"

# Example Response
"{
  ""transaction_id"": ""998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb"",
  ""status"": ""completed"",
}"


# *TASK 7*

# PATH
POST	/analysis/swaps

# Description
Retrieves all swap transactions. Returns a paginated list of all swap transactions that have been recorded in the system.

# Input Parameters
"page (integer, optional): Page number (default: 1)
limit (integer, optional): Number of records per page (default: 20, max: 100)
from_token (string, optional): Filter by source token
to_token (string, optional): Filter by destination token
from_time (integer, optional): Start timestamp filter in seconds
to_time (integer, optional): End timestamp filter in seconds
user_id (string, optional): Filter by user ID"

# Output Parameters
"transactions (array): Array of transaction objects
 - transaction_id (string): On chain transaction ID
 - from_token (string): Source token
 - from_amount (float): Source amount
 - to_token (string): Destination token
 - to_amount (float): Destination amount
 - price (float): Exchange rate
 - timestamp (integer): Transaction timestamp in seconds
 - status (string): Transaction status
total (integer): Total number of transactions
page (integer): Current page number
limit (integer): Records per page"

# Example Request
GET /analysis/swaps?page=1&limit=20&from_token=USDM

# Example Response
"{
  ""transactions"": [
    {
      ""transaction_id"": ""998f435b05066bb1944804587dff6a64f4acdf0f0f793cd07a26a551a2b060eb"",
      ""from_token"": ""USDM"",
      ""from_amount"": 0.1,
      ""to_token"": ""ADA"",
      ""to_amount"": 5000.00,
      ""price"": 50000.00,
      ""timestamp"": 1697123456,
      ""status"": ""completed""
    }
  ],
  ""total"": 150,
  ""page"": 1,
  ""limit"": 20
}"

