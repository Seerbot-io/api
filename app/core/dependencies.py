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

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.jwt_utils import verify_token
from app.db.session import get_db
from app.models.users import User


def _extract_token(authorization: Optional[str]) -> Dict[str, Any]:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    authorization = authorization.strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    else:
        token = authorization
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    return verify_token(token)


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    """
    returning wallet address.
    """
    payload = _extract_token(authorization)
    return payload["wallet_address"]


def get_current_user_id(
    wallet_address: str = Depends(get_current_user), db: Session = Depends(get_db)
) -> str:
    """
    Get user_id (UUID) from users table based on wallet_address.
    Creates a new user if one doesn't exist.
    Updates last_active_at timestamp.
    Returns the user_id as a string.
    """
    # Query for existing user
    user = db.query(User).filter(User.wallet_address == wallet_address).first()

    now = datetime.now(timezone.utc)
    if not user:
        # Create new user if doesn't exist
        user = User(wallet_address=wallet_address, last_active_at=now)
        db.add(user)
        db.flush()  # Flush to get the ID without committing
        db.refresh(user)
    else:
        # Update last_active_at for existing user
        user.last_active_at = now  # type: ignore

    db.commit()

    return str(user.id)
