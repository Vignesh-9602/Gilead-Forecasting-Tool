from fastapi import APIRouter, HTTPException

from app.schemas.market_events_schema import DeleteMarketEventRequest, MarketEventApplyFilterRequest, MarketEventApplyFilterResponse, MarketEventFiltersResponse, MarketEventRunCalculationRequest, MarketEventRunCalculationResponse, MarketEventSaveRequest
from app.services.market_events_service import apply_market_event_filters_service, delete_market_event_service, get_market_event_filters_service, run_market_event_calculation_service, save_market_event_changes_service



router = APIRouter(prefix="/api/market-events", tags=["Market Events"])


@router.get( "/filters/{ta_name}", response_model=MarketEventFiltersResponse)
def get_market_event_filters(ta_name: str):
    try:
        return get_market_event_filters_service(ta_name)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while fetching market event filters: {str(e)}"
        )
    
@router.post( "/apply-filters", response_model=MarketEventApplyFilterResponse)
def apply_market_event_filters(payload: MarketEventApplyFilterRequest):
    try:
        return apply_market_event_filters_service(payload)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while applying market event filters: {str(e)}"
        )
    
@router.post("/run-calculation",response_model=MarketEventRunCalculationResponse)
def run_market_event_calculation(payload: MarketEventRunCalculationRequest):
    try:
        return run_market_event_calculation_service(payload)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while running market event calculation: {str(e)}"
        )
    
@router.post("/market-events/save")
def save_market_event_changes(payload: MarketEventSaveRequest):
    try:
        return save_market_event_changes_service(payload)

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error while saving market event changes: {str(e)}"
        )
    
@router.post("/market-events/delete-event", tags=["Market Events"])
def delete_market_event(payload: DeleteMarketEventRequest):
    return delete_market_event_service(payload)