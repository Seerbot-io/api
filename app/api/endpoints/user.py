from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, cast

from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.core.router_decorated import APIRouter
from app.db.session import SessionLocal, get_db
from app.models.notice import Notice
from app.schemas.notice import NoticeListResponse, NoticeResponse
from app.schemas.user import (
    PortfolioHoldingsResponse,
    PortfolioSummaryResponse,
    ProfileResponse,
    WalletBalanceResponse,
)

router = APIRouter()
group_tags: List[str | Enum] = ["user"]


"""
handle notice send to user via websocket / api

api: 
- input: type(optional), limit default 10, offset default 0
- output: notice

websocket:
- input: last_notice_id default 0
- output: notice

table: chatbot.notice -> notice
columns:
    type: str (info, account, signal)
    title: str (required)
    message: str (required)
    created_at: datetime
    meta_data: dict or json (optional)
"""


def _get_notices(
    type: Optional[str] = None,
    limit: Optional[int] = 10,
    offset: Optional[int] = 0,
    order: str = "desc",
    after_id: Optional[int] = None,
) -> List[NoticeResponse]:
    # Filter by type if provided
    db = SessionLocal()
    query = db.query(Notice)
    if type:
        allowed_types = ["info", "account", "signal", "all"]
        if type not in allowed_types:
            type = "all"
        if type != "all":
            query = query.filter(Notice.type == type)
    if order == "desc":
        if after_id:
            query = query.filter(Notice.id < after_id)
        query = query.order_by(Notice.id.desc())
    elif order == "asc":
        if after_id:
            query = query.filter(Notice.id > after_id)
        query = query.order_by(Notice.id.asc())
    notices = query.offset(offset).limit(limit).all()
    # Convert to response models
    notice_responses = [
        NoticeResponse(
            id=cast(int, notice.id),
            type=cast(str, notice.type),
            icon=cast(Optional[str], notice.icon),
            title=cast(str, notice.title),
            message=cast(str, notice.message),
            created_at=cast(datetime, notice.created_at),
            updated_at=cast(datetime, notice.updated_at),
            meta_data=cast(Optional[Dict[str, Any]], notice.meta_data),
        )
        for notice in notices
    ]
    db.close()
    return notice_responses


@router.get(
    "/notices",
    tags=group_tags,
    response_model=NoticeListResponse,
    status_code=status.HTTP_200_OK,
)
def get_notices(
    type: Optional[str] = Query(
        default="all",
        description="Filter by notice type: info, account, signal, default: all",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of notices to return, default: 10, max: 100",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of notices to skip for pagination, default: 0",
    ),
    order: str = Query(
        default="desc", description="Order by: desc, asc, default: desc"
    ),
    after_id: int = Query(
        default=None,
        ge=0,
        description="ID of the last notice to return, default: None, min: 0",
    ),
    db: Session = Depends(get_db),
) -> NoticeListResponse:
    """
    Get notices, currently all notices are global and sent to all users.

    Returns all global notices (all notices are sent to all users).

    Query Parameters:
    - type: Optional filter by notice type ("info", "account", "signal", default: "all")
    - order: Order by: desc, asc, default: desc
    - after_id: ID of the last notice to return, default: None, min: 0
    - limit: Maximum number of notices to return (default: 10, max: 100)
    - offset: Number of notices to skip for pagination (default: 0)

    Returns:
    - List of notices ordered by created_at DESC
    - Total count of matching notices
    """
    notice_responses = _get_notices(type, limit, offset, order, after_id, db)
    total = len(notice_responses)
    return NoticeListResponse(
        notices=notice_responses,
        total=total,
        limit=limit,
        offset=offset,
        order=order,
    )


@router.get(
    "/portfolio/balance",
    tags=group_tags,
    response_model=WalletBalanceResponse,
    status_code=status.HTTP_200_OK,
)
def get_portfolio_balance(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
) -> WalletBalanceResponse:
    """
    Get wallet balance for a user.

    Query Parameters:
    - wallet_address: Wallet address of the user (required)

    Returns:
    - Wallet balance with ADA and token balances
    """
    # TODO: Implement actual wallet balance retrieval
    # This is a placeholder - replace with actual data source
    return WalletBalanceResponse(
        ada_balance=0.0,
        tokens=[],
    )


@router.get(
    "/profile",
    tags=group_tags,
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_profile(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
) -> ProfileResponse:
    """
    Get user profile information.

    Query Parameters:
    - wallet_address: Wallet address of the user (required)

    Returns:
    - User profile information
    """
    # TODO: Implement actual profile retrieval
    # This is a placeholder - replace with actual data source
    return ProfileResponse(
        wallet_address=wallet_address,
        username=None,
        avatar_url=None,
    )


@router.get(
    "/portfolio/holdings",
    tags=group_tags,
    response_model=PortfolioHoldingsResponse,
    status_code=status.HTTP_200_OK,
)
def get_portfolio_holdings(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of holdings to return"),
    offset: int = Query(default=0, ge=0, description="Number of holdings to skip for pagination"),
) -> PortfolioHoldingsResponse:
    """
    Get portfolio holdings for a user.

    Query Parameters:
    - wallet_address: Wallet address of the user (required)
    - limit: Maximum number of holdings to return (default: 20, max: 100)
    - offset: Number of holdings to skip for pagination (default: 0)

    Returns:
    - List of portfolio holdings with pagination
    """
    # TODO: Implement actual portfolio holdings retrieval
    # This is a placeholder - replace with actual data source
    return PortfolioHoldingsResponse(
        holdings=[],
        total=0,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/portfolio/summary",
    tags=group_tags,
    response_model=PortfolioSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_portfolio_summary(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
) -> PortfolioSummaryResponse:
    """
    Get portfolio summary statistics for a user.

    Query Parameters:
    - wallet_address: Wallet address of the user (required)

    Returns:
    - Portfolio summary with total value, 24h change, etc.
    """
    # TODO: Implement actual portfolio summary retrieval
    # This is a placeholder - replace with actual data source
    return PortfolioSummaryResponse(
        total_value=0.0,
        total_value_ada=0.0,
        change_24h=0.0,
        change_24h_percent=0.0,
    )
