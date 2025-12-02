from app.core.config import settings
from typing import List
from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.router_decorated import APIRouter
from app.db.session import get_db
from app.schemas.web_content import Statistics, Partner
from app.core.config import settings

router = APIRouter()
group_tags = ["content"]


def represent_number(number: float) -> str:
    """Format number with K, M, B suffixes for display"""
    if number < 1_000_000:
        s = f"{number:,.2f}".rstrip("0").rstrip(".")
    elif number < 1_000_000_000:
        s = f"{number/1_000:,.2f}".rstrip("0").rstrip(".") + "K"
    elif number < 1_000_000_000_000:
        s = f"{number/1_000_000:,.2f}".rstrip("0").rstrip(".") + "M"
    else:
        s = f"{number/1_000_000_000:,.2f}".rstrip("0").rstrip(".") + "B"
    return s


@router.get(
    "/statistics",
    tags=group_tags,
    response_model=Statistics,
    status_code=status.HTTP_200_OK,
    summary="Get platform statistics",
    response_description="Returns statistics including number of trading pairs, total liquidity, and transaction count"
)
def get_statistics(db: Session = Depends(get_db)) -> Statistics:
    """
    Get platform statistics including:
    - Number of trading pairs
    - Total liquidity
    - Number of transactions
    """
    
    query = """
    select n_token*(n_token-1)/2 as n_pair, liquidity, n_tx
    from (
        select count(*) as n_token
        from proddb.tokens
    ) a
    join (select sum(value) liquidity, count(*) n_tx
    from proddb.swap_transactions
    ) b on true
    """
    result = db.execute(text(query)).fetchone()
    
    if result is None:
        return Statistics(
            n_pair="0",
            liquidity="0",
            n_tx="0"
        )
    
    return Statistics(
        n_pair=represent_number(result.n_pair),
        liquidity=represent_number(result.liquidity),
        n_tx=represent_number(result.n_tx)
    )
    

@router.get(
    "/partners",
    tags=group_tags,
    response_model=List[Partner],
    status_code=status.HTTP_200_OK,
    summary="Get partners",
    response_description="Returns partners"
)
def get_partners() -> List[Partner]:  # noqa: F821
    """
    Get partners
    """
    return [
        Partner(
            name="Minswap",
            logo=settings.HOST + "/static/images/Minswap.png",
            url="https://www.minswap.org/"
        ),
        Partner(
            name="Cardano catalyst",
            logo=settings.HOST + "/static/images/Cardano_catalyst.png",
            url="https://milestones.projectcatalyst.io/"
        ),
        Partner(
            name="Cardano Foundation",
            logo=settings.HOST + "/static/images/Cardano.png",
            url="https://cardanofoundation.org/"
        ),
        Partner(
            name="SCI labs",
            logo=settings.HOST + "/static/images/SCI_labs.png",
            url="https://scilabs.io"
        ),
        Partner(
            name="Varmeta",
            logo=settings.HOST + "/static/images/Varmeta.png",
            url="https://www.var-meta.com/"
        ),
        Partner(
            name="Vtech com",
            logo=settings.HOST + "/static/images/Vtech_com.png",
            url="https://vtechcom.org/"
        ),
    ]
