"""
FastAPI Authentication Dependencies
This module provides FastAPI dependency functions that can be injected into route handlers
to automatically extract and validate JWT tokens from the Authorization header.
Usage in endpoints:
    @router.get("/protected")
    def protected_route(wallet_address: str = Depends(get_current_user)):
        # wallet_address is automatically extracted from JWT token
        return {"user": wallet_address}
Flow:
1. Client sends request with Authorization: Bearer <token> header
2. FastAPI calls get_current_user() dependency
3. _extract_token() extracts token from header
4. verify_token() validates the JWT (from jwt_utils.py)
5. Returns wallet_address to the route handler
"""

from fastapi import Header, HTTPException, status
from typing import Optional
from app.core.jwt_utils import verify_token


def _extract_token(authorization: Optional[str]) -> str:
    """
    Extract JWT token from Authorization header.
    Supports both "Bearer <token>" and plain token formats.
    Args:
        authorization: The Authorization header value (e.g., "Bearer eyJ...")
    Returns:
        The extracted token string
    Raises:
        HTTPException 401: If Authorization header is missing or invalid
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    authorization = authorization.strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    else:
        token = authorization
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    return verify_token(token)


def get_current_user(authorization: Optional[str] = Header(None, alias="Authorization")) -> str:
    """
    returning wallet address.
    """
    payload = _extract_token(authorization)
    return payload["wallet_address"]

