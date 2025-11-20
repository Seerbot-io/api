"""
JWT Token Utilities

This module handles JSON Web Token (JWT) creation and verification for wallet authentication.
After a user successfully verifies their Cardano wallet signature, this module creates a JWT token
that can be used for subsequent authenticated API requests.

Flow:
1. User verifies wallet signature -> create_access_token() generates JWT
2. User makes API request with JWT in Authorization header -> verify_token() validates it
3. Protected endpoints use get_current_user() from dependencies.py to extract wallet_address

The JWT contains:
- wallet_address: The authenticated Cardano wallet address
- iat: Issued at timestamp
- exp: Expiration timestamp (configurable via ACCESS_TOKEN_EXPIRE_SECONDS)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException, status

from app.core.config import settings


if not settings.ENCODE_KEY:
    raise RuntimeError("ENCODE_KEY is not configured")


def create_access_token(wallet_address: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a JWT access token for an authenticated wallet address.
    
    This is called after successful wallet signature verification in /auth/verify endpoint.
    The token is returned to the frontend and used in subsequent API requests.
    
    Args:
        wallet_address: The Cardano wallet address that was verified
        extra_claims: Optional additional claims to include in the JWT payload
    
    Returns:
        A JWT token string that can be used in Authorization: Bearer <token> header
    
    Raises:
        ValueError: If wallet_address is empty
    """
    if not wallet_address:
        raise ValueError("wallet_address is required")

    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "wallet_address": wallet_address,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.ENCODE_KEY, algorithm=settings.ENCODE_ALGORITHM)


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    This is called by protected endpoints to validate the JWT token from the Authorization header.
    Checks token signature, expiration, and required payload fields.
    
    Args:
        token: The JWT token string from Authorization header
    
    Returns:
        Decoded JWT payload dictionary containing wallet_address and other claims
    
    Raises:
        HTTPException 401: If token is missing, expired, invalid, or missing wallet_address
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        payload = jwt.decode(token, settings.ENCODE_KEY, algorithms=[settings.ENCODE_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if "wallet_address" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    return payload

