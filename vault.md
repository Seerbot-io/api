# Vault API Documentation

This document describes the Vault-related API endpoints for managing user vault earnings and transactions.

## Base URL

All endpoints are prefixed with `/api/user` (or your API base path).

---

## Endpoints

### 1. Get Vault Earnings

Retrieves vault earnings for a user from their vault positions.

**Endpoint:** `GET /vaults/earnings`

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `wallet_address` | string | Yes | - | Wallet address of the user |
| `limit` | integer | No | 20 | Maximum number of earnings to return (1-100) |
| `offset` | integer | No | 0 | Number of earnings to skip for pagination |

**Sample Request:**

```bash
GET /vaults/earnings?wallet_address=addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm&limit=20&offset=0
```

**Response Schema:**

```json
{
  "earnings": [
    {
      "vault_id": 1,
      "vault_name": "USDM Vault",
      "vault_address": "addr1...",
      "total_deposit": 1000.0,
      "current_value": 1150.0,
      "roi": 15.0
    }
  ],
  "total": 5,
  "page": 1,
  "limit": 20
}
```

**Response Fields:**

- `earnings` (array): List of vault earnings
  - `vault_id` (integer): Unique vault identifier
  - `vault_name` (string): Name of the vault
  - `vault_address` (string): Address of the vault
  - `total_deposit` (float): Total amount deposited into the vault
  - `current_value` (float): Current value of the position
  - `roi` (float): Return on Investment percentage (calculated as: `((current_value + total_withdrawal - total_deposit) / total_deposit) * 100`)
- `total` (integer): Total number of earnings records
- `page` (integer): Current page number
- `limit` (integer): Number of records per page

**Notes:**

- Only returns vaults where `current_value > 0`
- Results are ordered by `current_value` in descending order
- ROI is calculated as: `((current_value + total_withdrawal - total_deposit) / total_deposit) * 100`
- Sample wallet address: `addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm`

---

### 2. Get Vault Transactions

Retrieves user vault transaction history (deposits, withdrawals, claims, reinvests).

**Endpoint:** `GET /vaults/transactions`

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `wallet_address` | string | Yes | - | Wallet address of the user |
| `vault_id` | integer | No | null | Filter by vault ID (optional) |
| `page` | integer | No | 1 | Page number (minimum: 1) |
| `limit` | integer | No | 20 | Number of records per page (1-100) |

**Sample Request:**

```bash
GET /vaults/transactions?wallet_address=addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm&vault_id=1&page=1&limit=20
```

**Response Schema:**

```json
{
  "transactions": [
    {
      "id": 123,
      "vault_id": 1,
      "vault_name": "USDM Vault",
      "wallet_address": "addr1...",
      "action": "deposit",
      "amount": 100.0,
      "token_id": "token123",
      "token_symbol": "USDM",
      "txn": "tx_hash_here",
      "timestamp": 1699123456,
      "status": "completed",
      "fee": 0.5
    }
  ],
  "total": 50,
  "page": 1,
  "limit": 20
}
```

**Response Fields:**

- `transactions` (array): List of vault transactions
  - `id` (integer): Unique transaction identifier
  - `vault_id` (integer): Vault identifier
  - `vault_name` (string, nullable): Name of the vault
  - `wallet_address` (string): Wallet address that performed the transaction
  - `action` (string): Transaction action type (`deposit`, `withdrawal`, `claim`, `reinvest`)
  - `amount` (float): Transaction amount
  - `token_id` (string): Token identifier
  - `token_symbol` (string, nullable): Token symbol (e.g., "USDM", "ADA")
  - `txn` (string): Transaction hash
  - `timestamp` (integer): Unix timestamp of the transaction
  - `status` (string): Transaction status (default: "pending")
  - `fee` (float): Transaction fee
- `total` (integer): Total number of transactions
- `page` (integer): Current page number
- `limit` (integer): Number of records per page

**Notes:**

- Results are ordered by `timestamp` in descending order (most recent first)
- If `vault_id` is provided, only transactions for that vault are returned
- Token symbols are automatically fetched and included in the response
- All amounts and fees are returned as floats

---

## Error Responses

Both endpoints may return standard HTTP error responses:

- `400 Bad Request`: Invalid query parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

---

## Example Usage

### Get all vault earnings for a user

```bash
curl -X GET "https://api.example.com/vaults/earnings?wallet_address=addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm&limit=10"
```

### Get vault transactions for a specific vault

```bash
curl -X GET "https://api.example.com/vaults/transactions?wallet_address=addr1vyrq3xwa5gs593ftfpy2lzjjwksdt0fkjjwge4ww6p53dqy4w5wm&vault_id=1&page=1&limit=20"
```

### Get paginated vault transactions

```bash
curl -X GET "https://api.example.com/vaults/transactions?wallet_address=addr1vyrq3xwa5gs593ftfpy2lzjjwksdt0fkjjwge4ww6p53dqy4w5wm&page=2&limit=50"
```
