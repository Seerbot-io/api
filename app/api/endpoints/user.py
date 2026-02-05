from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, cast

from fastapi import Depends, Query, status
from sqlalchemy.orm import Session

from app.core.router_decorated import APIRouter
from app.db.session import SessionLocal, get_db
from app.models.tokens import Token
from app.schemas.notice import NoticeListResponse, NoticeResponse
from app.schemas.user import (
    VaultEarning,
    VaultEarningsResponse,
    SwapToken,
    TokenInfo,
    UserSwap,
    UserSwapListResponse,
    VaultTransaction,
    VaultTransactionListResponse,
)
from sqlalchemy import text

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
) -> tuple[List[NoticeResponse], int]:
    # Filter by type if provided
    db = SessionLocal()

    # Build WHERE clause
    where_clauses = []
    if type:
        allowed_types = ["info", "account", "signal", "all"]
        if type not in allowed_types:
            type = "all"
        if type != "all":
            where_clauses.append(f"type = '{type}'")

    if after_id:
        if order == "desc":
            where_clauses.append(f"id < {after_id}")
        elif order == "asc":
            where_clauses.append(f"id > {after_id}")

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    # Build ORDER BY clause
    order_sql = "DESC" if order == "desc" else "ASC"

    # Build LIMIT and OFFSET clause
    limit_offset_sql = ""
    if limit:
        limit_offset_sql = f"LIMIT {limit}"
    if offset:
        limit_offset_sql += (
            f" OFFSET {offset}" if limit_offset_sql else f"OFFSET {offset}"
        )

    # Query with COUNT(*) OVER() to get total count in one query
    query_sql = text(
        f"""
        SELECT 
            id,
            type,
            icon,
            title,
            message,
            created_at,
            updated_at,
            meta_data,
            COUNT(*) OVER() AS total_count
        FROM chatbot.notice
        WHERE {where_sql}
        ORDER BY id {order_sql}
        {limit_offset_sql}
        """
    )

    results = db.execute(query_sql).fetchall()
    total = int(results[0].total_count) if results else 0

    # Convert to response models
    notice_responses = [
        NoticeResponse(
            id=cast(int, row.id),
            type=cast(str, row.type),
            icon=cast(Optional[str], row.icon),
            title=cast(str, row.title),
            message=cast(str, row.message),
            created_at=cast(datetime, row.created_at),
            updated_at=cast(datetime, row.updated_at),
            meta_data=cast(Optional[Dict[str, Any]], row.meta_data),
        )
        for row in results
    ]
    db.close()
    return notice_responses, total


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
    type = type.lower().strip() if type else "all"
    order = order.lower().strip() if order else "desc"
    notice_responses, total = _get_notices(type, limit, offset, order, after_id)
    return NoticeListResponse(
        notices=notice_responses,
        total=total,
        limit=limit,
        offset=offset,
        order=order,
    )


@router.get(
    "/vaults/earnings",
    tags=group_tags,
    response_model=VaultEarningsResponse,
    status_code=status.HTTP_200_OK,
)
def get_vault_earnings(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
    limit: int = Query(
        default=20, ge=1, le=100, description="Maximum number of earnings to return"
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of earnings to skip for pagination"
    ),
    db: Session = Depends(get_db),
) -> VaultEarningsResponse:
    """
    Get vault earnings for a user (from vault positions).

    Query Parameters:
    - wallet_address: Wallet address of the user (required)
    - limit: Maximum number of earnings to return (default: 20, max: 100)
    - offset: Number of earnings to skip for pagination (default: 0)

    Returns:
    - earnings: List of vault earnings (vault_id, vault_name, vault_address, pool_id, total_deposit, current_value, roi)
    - total, page, limit: Pagination

    *Sample wallet address:* addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm
    """
    wallet_address = wallet_address.strip().lower()
    # Fetch user earnings with vault info and total count in one query
    data_sql = text(
        f"""
        SELECT 
            ue.vault_id,
            v.name as vault_name,
            v.address as vault_address,
            v.pool_id,
            ue.total_deposit,
            ue.total_withdrawal,
            ue.current_value,
            COUNT(*) OVER() AS total_count
        FROM proddb.user_earnings ue
        JOIN proddb.vault v ON ue.vault_id = v.id
        WHERE ue.wallet_address = '{wallet_address}' AND ue.current_value > 0
        ORDER BY ue.current_value DESC
        LIMIT {limit} OFFSET {offset}
        """
    )
    earnings_data = db.execute(data_sql).fetchall()
    total = int(earnings_data[0].total_count) if earnings_data else 0

    # Convert to earnings format
    earnings = []

    for earning in earnings_data:
        # Calculate ROI (Return on Investment)
        # ROI = ((current_value + total_withdrawal - total_deposit) / total_deposit) * 100
        total_deposit = float(earning.total_deposit)
        total_withdrawal = float(earning.total_withdrawal)
        current_value = float(earning.current_value)

        # Net investment = total_deposit - total_withdrawal
        # net_deposit = total_deposit - total_withdrawal

        # ROI calculation: (current_value - net_deposit) / net_deposit * 100
        # Or: (current_value + total_withdrawal - total_deposit) / total_deposit * 100
        if total_deposit > 0:
            roi = (
                (current_value + total_withdrawal - total_deposit) / total_deposit
            ) * 100
        else:
            roi = 0.0

        earnings.append(
            VaultEarning(
                vault_id=earning.vault_id,
                vault_name=str(earning.vault_name) if earning.vault_name else "",
                vault_address=str(earning.vault_address)
                if earning.vault_address
                else "",
                pool_id=str(earning.pool_id) if getattr(earning, "pool_id", None) else "",
                total_deposit=round(total_deposit, 2),
                current_value=round(current_value, 2),
                roi=round(roi, 2),
            )
        )

    return VaultEarningsResponse(
        earnings=earnings,
        total=total,
        page=(offset // limit) + 1,
        limit=limit,
    )


@router.get(
    "/swaps",
    tags=group_tags,
    response_model=UserSwapListResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_swaps(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
    page: int = Query(default=1, ge=1, description="Page number (default: 1)"),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of records per page (default: 20, max: 100)",
    ),
    db: Session = Depends(get_db),
) -> UserSwapListResponse:
    """
    Get user swap transactions.

    Query Parameters:
    - wallet_address: Wallet address of the user (required)
    - page: Page number (default: 1)
    - limit: Number of records per page (default: 20, max: 100)

    Returns:
    - List of swap transactions with token information

    *Sample wallet address:* addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm
    """
    wallet_address = wallet_address.strip().lower()
    # Validate and adjust pagination parameters
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    # Fetch paginated swaps with total count in one query
    data_sql = text(
        f"""
        SELECT 
            transaction_id,
            from_token,
            to_token,
            from_amount,
            to_amount,
            timestamp,
            COUNT(*) OVER() AS total_count
        FROM proddb.swap_transactions
        WHERE status = 'completed' AND wallet_address = '{wallet_address}'
        ORDER BY timestamp DESC
        LIMIT {limit} OFFSET {offset}
        """
    )
    swaps = db.execute(data_sql).fetchall()
    total = int(swaps[0].total_count) if swaps else 0

    # Get unique token symbols
    token_symbols = set()
    for swap in swaps:
        token_symbols.add(str(swap.from_token))
        token_symbols.add(str(swap.to_token))

    # Fetch token information
    token_info_map = {}
    if token_symbols:
        tokens = db.query(Token).filter(Token.symbol.in_(token_symbols)).all()
        for token in tokens:
            token_info_map[token.symbol] = TokenInfo(
                symbol=token.symbol or "",
                name=token.name or "",
                decimals=token.decimals or 0,
                address=token.id or "",
                logo_url=token.logo_url,
            )

    # Convert to response format
    swap_data = []
    for swap in swaps:
        from_token_symbol = str(swap.from_token)
        to_token_symbol = str(swap.to_token)

        # Get token info or create default
        from_token_info = token_info_map.get(
            from_token_symbol,
            TokenInfo(symbol=from_token_symbol, name="", decimals=0, address=""),
        )
        to_token_info = token_info_map.get(
            to_token_symbol,
            TokenInfo(symbol=to_token_symbol, name="", decimals=0, address=""),
        )

        swap_data.append(
            UserSwap(
                fromToken=SwapToken(
                    tokenInfo=from_token_info,
                    amount=str(swap.from_amount)
                    if swap.from_amount is not None
                    else "0",
                ),
                toToken=SwapToken(
                    tokenInfo=to_token_info,
                    amount=str(swap.to_amount) if swap.to_amount is not None else "0",
                ),
                txn=str(swap.transaction_id),
                timestamp=int(swap.timestamp) if swap.timestamp is not None else 0,
            )
        )

    return UserSwapListResponse(data=swap_data, total=total, page=page)


@router.get(
    "/vaults/transactions",
    tags=group_tags,
    response_model=VaultTransactionListResponse,
    status_code=status.HTTP_200_OK,
)
def get_vault_transactions(
    wallet_address: str = Query(
        ..., description="Wallet address of the user (required)"
    ),
    vault_id: Optional[str] = Query(
        default=None, description="Filter by vault ID (optional)"
    ),
    page: int = Query(default=1, ge=1, description="Page number (default: 1)"),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of records per page (default: 20, max: 100)",
    ),
    db: Session = Depends(get_db),
) -> VaultTransactionListResponse:
    """
    Get user vault transaction history.

    Query Parameters:
    - wallet_address: Wallet address of the user (required)
    - vault_id: Filter by vault ID (optional)
    - page: Page number (default: 1)
    - limit: Number of records per page (default: 20, max: 100)

    Returns:
    - List of vault transactions (deposits, withdrawals, claims, reinvests)

    *Sample wallet address:* addr1vyrq3xwa5gs593ftfpy2lzjjwzksdt0fkjjwge4ww6p53dqy4w5wm
    """
    wallet_address = wallet_address.strip().lower()
    # Validate and adjust pagination parameters
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    # Build WHERE clause
    where_clause = f"vl.wallet_address = '{wallet_address}'"
    if vault_id is not None:
        where_clause += f" AND vl.vault_id = {vault_id}"

    # Fetch paginated vault logs with total count in one query
    data_sql = text(
        f"""
        SELECT 
            vl.id,
            vl.vault_id,
            v.name as vault_name,
            vl.wallet_address,
            vl.action,
            vl.amount,
            vl.token_id,
            vl.txn,
            vl.timestamp,
            vl.status,
            vl.fee,
            COUNT(*) OVER() AS total_count
        FROM proddb.vault_logs vl
        LEFT JOIN proddb.vault v ON vl.vault_id = v.id
        WHERE {where_clause}
        ORDER BY vl.timestamp DESC
        LIMIT {limit} OFFSET {offset}
        """
    )
    transactions = db.execute(data_sql).fetchall()
    total = int(transactions[0].total_count) if transactions else 0

    # Get unique token IDs
    token_ids = set()
    for transaction in transactions:
        if transaction.token_id:
            token_ids.add(str(transaction.token_id))

    # Fetch token information
    token_info_map = {}
    if token_ids:
        tokens = db.query(Token).filter(Token.id.in_(token_ids)).all()
        for token in tokens:
            token_info_map[token.id] = token.symbol or ""

    # Convert to response format
    transaction_data = []
    for transaction in transactions:
        token_symbol = (
            token_info_map.get(str(transaction.token_id), None)
            if transaction.token_id
            else None
        )

        transaction_data.append(
            VaultTransaction(
                id=transaction.id,
                vault_id=transaction.vault_id,
                vault_name=transaction.vault_name,
                wallet_address=str(transaction.wallet_address),
                action=str(transaction.action),
                amount=float(transaction.amount)
                if transaction.amount is not None
                else 0.0,
                token_id=str(transaction.token_id) if transaction.token_id else "",
                token_symbol=token_symbol,
                txn=str(transaction.txn) if transaction.txn else "",
                timestamp=int(transaction.timestamp)
                if transaction.timestamp is not None
                else 0,
                status=str(transaction.status) if transaction.status else "pending",
                fee=float(transaction.fee) if transaction.fee is not None else 0.0,
            )
        )

    return VaultTransactionListResponse(
        transactions=transaction_data, total=total, page=page, limit=limit
    )
