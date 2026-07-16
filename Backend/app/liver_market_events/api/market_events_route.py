from fastapi import APIRouter, HTTPException

from app.liver_market_events.schemas.market_events_schema import ApplyFiltersRequest, RefreshRequest
from app.liver_market_events.services.market_events_service import (
    get_market_events_filters,
    apply_market_events_filters,
    refresh_market_events,
)

router = APIRouter(prefix="/api/liver-market-events", tags=["Liver Market Events"])


@router.get("/filters")
def market_events_filters(ta: str = "HCV"):
    """
    Called on page load to populate all filter dropdowns.

    Returns the user's last applied filter in selected_filter (restored from DB).
    Falls back to defaults if the user has never applied a filter for this TA.
    """
    try:
        return get_market_events_filters(ta)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-filters")
def market_events_apply_filters(payload: ApplyFiltersRequest):
    """
    Called when the user clicks Apply Filter.

    Saves the user's filter selections (so they are restored on next page load),
    then returns the full event_tabs data for the selected scenario.

    The metrics_views (chart + table data) are loaded from a pre-saved scenario in DB.
    The impact_curve_configuration is always built fresh from the latest master data.
    """
    try:
        return apply_market_events_filters(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def market_events_refresh(payload: RefreshRequest):
    """
    Called when the user edits a table cell.

    Loads the current event_tabs (BASE or saved scenario), patches the edited
    (tab, metric, view, table_view) with the new row values, and returns the
    same structure as /apply-filters so the frontend can re-render consistently.
    """
    try:
        return refresh_market_events(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
