
from fastapi import APIRouter
from app.schemas.Net_Revenue_Schema import NetRevenueFiltersResponse, RevenueEditRequest, RevenueRequest
from app.services.Net_Revenue_Service import edit_revenue_service, get_net_revenue_filters_service, get_revenue_service

router = APIRouter(prefix="/api/Net_Revenue", tags=["Net_Demand_Revenue"])


@router.get(
    "/filters/{ta_name}",
    response_model=NetRevenueFiltersResponse
)
def get_net_revenue_filters(ta_name: str):
    return get_net_revenue_filters_service(ta_name)

@router.post("/revenue/apply-filter")
def get_revenue(payload: RevenueRequest):
    return get_revenue_service(payload)

@router.post("/revenue/edit")
def edit_revenue(payload: RevenueEditRequest):
    return edit_revenue_service(payload)