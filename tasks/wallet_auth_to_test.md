Here is the **simple, clean plan** for implementing wallet authentication on **Cardano**, without icons.

---

# **Plan: How to Implement Wallet Login on Cardano**

### 1. Frontend connects to a Cardano wallet

Use the browser wallet interface (CIP-30):

* Call `window.cardano.nami.enable()`
* Get user address using `wallet.getUsedAddresses()`

### 2. Backend generates a nonce

Flow:

1. Frontend calls `/auth/request_nonce`
2. Backend creates a random nonce and stores it temporarily
3. Backend sends that nonce back to the frontend

### 3. Frontend signs the nonce with the Cardano wallet

Cardano uses CIP-8 for data signing:

* Convert the nonce to hex
* Call: `wallet.signData(address, nonce_hex)`
* Wallet returns:

  * the signature
  * the public key

### 4. Frontend sends the signature to backend

Request body:

```
{
  address,
  nonce,
  signature,
  key
}
```

### 5. Backend verifies the signature

Backend checks three things:

1. Nonce matches stored nonce
2. Signature is valid using ED25519 verification
3. The public key corresponds to the provided Cardano address

If all checks pass, the wallet is confirmed to belong to the user.

### 6. Backend creates a session or JWT

Once the wallet is verified:

* Backend issues a session token or JWT
* Frontend uses that token for authenticated API calls

---

This is the core plan for doing signature-based authentication on Cardano.
If you want the clean code version for both FastAPI and frontend, I can generate it.
