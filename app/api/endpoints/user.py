import asyncio
from enum import Enum
from typing import List, Optional

from fastapi import Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.router_decorated import APIRouter
from app.db.session import SessionLocal, get_db
from app.models.notice import Notice
from app.schemas.notice import NoticeListResponse, NoticeResponse

router = APIRouter()
group_tags: List[str | Enum] = ["user"]


"""
handle notice send to user via websocket / api

api: 
- input: wallet_address, type(optional), limit default 10, offset default 0
- output: notice

websocket:
- input: wallet_address, last_notice_id default 0
- output: notice

table: chatbot.notice -> notice
columns:
    type: str (info, account, signal)
    title: str (required)
    message: str (required)
    created_at: datetime
    meta_data: dict or json (optional)
"""


@router.get(
    "/notices",
    tags=group_tags,
    response_model=NoticeListResponse,
    status_code=status.HTTP_200_OK,
)
def get_notices(
    type: Optional[str] = Query(default="all", description="Filter by notice type: info, account, signal, default: all"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of notices to return, default: 10, max: 100"),
    offset: int = Query(default=0, ge=0, description="Number of notices to skip for pagination, default: 0"),
    db: Session = Depends(get_db),
) -> NoticeListResponse:
    """
    Get notices, currently all notices are global and sent to all users.

    Query Parameters:
    - type: Optional filter by notice type ("info", "account", "signal", default: "all")
    - limit: Maximum number of notices to return (default: 10, max: 100)
    - offset: Number of notices to skip for pagination (default: 0)

    Returns:
    - List of notices ordered by created_at DESC
    - Total count of matching notices
    """
    print(type, limit, offset)
    # Build query - all notices are global
    query = db.query(Notice)

    # Filter by type if provided
    if type:
        allowed_types = ["info", "account", "signal", "all"]
        if type not in allowed_types:
            type = "all"
        if type != "all":
            query = query.filter(Notice.type == type)

    # Get total count
    total = query.count()

    # Apply ordering and pagination
    notices = query.order_by(Notice.created_at.desc()).offset(offset).limit(limit).all()

    # Convert to response models
    notice_responses = [
        NoticeResponse(
            id=notice.id,
            type=notice.type,
            icon=notice.icon,
            title=notice.title,
            message=notice.message,
            created_at=notice.created_at,
            updated_at=notice.updated_at,
            meta_data=notice.meta_data,
        )
        for notice in notices
    ]

    return NoticeListResponse(
        notices=notice_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.websocket("/notices/ws")
async def notices_websocket(websocket: WebSocket, wallet_address: str , last_notice_id: int = Query(default=0, ge=0, description="Last notice ID to receive notices for, default: 0, min: 0")):
    """
    WebSocket endpoint for real-time notice updates.

    Query Parameters:
    - wallet_address: Wallet address to receive notices for
    - last_notice_id: Last notice ID to receive notices for
    On connection:
    - Sends all existing notices for the user

    Then:
    - Polls database every 5 seconds for new notices
    - Sends new notices as they appear

    Message Format:
    {
        "type": "notice",
        "data": {
            "id": 1,
            "type": "info",
            "icon": "https://seerbot.io/icon.png",
            "title": "Welcome",
            "message": "Welcome to SeerBot",
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:00:00",
            "meta_data": {"indicatorType": "signal", "token": "ADA"}
        }
    }
    """
    await websocket.accept()

    db = SessionLocal()

    try:
        # Send existing notices on connection
        existing_notices = (
            db.query(Notice)
            .filter(Notice.id > last_notice_id)
            .order_by(Notice.created_at.desc())
            .limit(50)  # Limit initial load
            .all()
        )

        for notice in existing_notices:
            notice_response = NoticeResponse(
                id=notice.id,
                type=notice.type,
                icon=notice.icon,
                title=notice.title,
                message=notice.message,
                created_at=notice.created_at,
                updated_at=notice.updated_at,
                meta_data=notice.meta_data,
            )
            await websocket.send_json(
                {
                    "type": "notice",
                    "data": notice_response.model_dump(by_alias=True),
                }
            )
            last_notice_id = max(last_notice_id, notice.id)

        # Poll for new notices every 5 seconds
        while True:
            try:
                # Wait 5 seconds or until disconnection
                await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                # If we receive a message, it might be a ping or other control message
                # For now, we'll just continue polling
            except asyncio.TimeoutError:
                # Timeout means no message received, continue with polling
                pass

            # Check for new notices
            new_notices = (
                db.query(Notice)
                .filter(Notice.id > last_notice_id)  # Only new notices
                .order_by(Notice.created_at.asc())  # Process oldest first
                .all()
            )

            for notice in new_notices:
                notice_response = NoticeResponse(
                    id=notice.id,
                    type=notice.type,
                    icon=notice.icon,
                    title=notice.title,
                    message=notice.message,
                    created_at=notice.created_at,
                    updated_at=notice.updated_at,
                    meta_data=notice.meta_data,
                )
                await websocket.send_json(
                    {
                        "type": "notice",
                        "data": notice_response.model_dump(by_alias=True),
                    }
                )
                last_notice_id = max(last_notice_id, notice.id)

            # Refresh the session periodically to avoid stale data
            db.commit()

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for wallet_address: {wallet_address}")
    except Exception as e:
        print(f"WebSocket error for wallet_address {wallet_address}: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        db.close()
