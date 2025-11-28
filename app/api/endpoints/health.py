from app.core.router_decorated import APIRouter
from fastapi import status
from app.schemas.my_base_model import CustormBaseModel
from typing import List

router = APIRouter()
# REQUIREMENTS FOR MODEL DEFINITION 
# - Have all the fields needed
# - fields must have explicit types
# - fields must have default values 
class HealthCheck(CustormBaseModel):
    """Response model to validate and return when performing a health check."""
    status: str = "oke" 

@router.get(
    "/health",
    tags=["Health"],
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
)
async def get_health() -> HealthCheck:
    """
    ## Perform a Health Check
    Endpoint to perform a healthcheck on. This endpoint can primarily be used Docker
    to ensure a robust container orchestration and management is in place. Other
    services which rely on proper functioning of the API service will not deploy if this
    endpoint returns any other HTTP status code except 200 (OK).
    Returns:
        HealthCheck: Returns a JSON response with the health status
    """

    return HealthCheck(status="oke")


