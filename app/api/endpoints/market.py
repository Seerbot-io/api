from enum import Enum
from typing import Any, List

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.router_decorated import APIRouter
from app.db.session import get_db, get_tables

router = APIRouter()
SCHEMA_2 = settings.SCHEMA_2
tables = get_tables(settings.SCHEMA_2)
group_tags: List[str | Enum] = ["Market Data"]


@router.get(
    "/daily",
    tags=group_tags,
    summary="Get daily market data",
    response_description="Returns rows from the daily market data table",
)
def get_daily_market_data(
    symbol: str,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> List[dict[str, Any]]:
    """
    Fetch rows from the daily market data table filtered by token symbol.

    Args:
        symbol: Token symbol to filter on (matches the table's symbol column).
        limit: Maximum number of rows to return (default 100).
    """
    # Normalize symbol to end with "/ADA"
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    if "ADA" not in symbol:
        symbol = symbol + "/ADA"
    elif not symbol.endswith("/ADA"):
        symbol = symbol[:-3] + "/ADA"

    query = text(
        f"SELECT * FROM {tables['f1d']} WHERE symbol = '{symbol}' ORDER BY open_time DESC LIMIT {limit}"
    )
    rows = db.execute(query).mappings().all()
    return [{"index": i, **row} for i, row in enumerate(rows)]
