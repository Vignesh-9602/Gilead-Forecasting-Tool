from fastapi import APIRouter, HTTPException

from app.liver_output.schemas.output_schema import ApplyFiltersRequest, OutputFiltersResponse
from app.liver_output.services.output_service import apply_output_filters, get_output_filters

router = APIRouter(prefix="/api/liver-output", tags=["Liver Output"])


@router.get("/filters", response_model=OutputFiltersResponse)
def output_filters(ta: str = "HCV"):
    """
    Called on page load to populate all filter dropdowns.

    Returns the user's last applied filter in selected_filter (restored from DB).
    Falls back to defaults if the user has never applied a filter for this TA.
    """
    try:
        return get_output_filters(ta)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-filters")
def output_apply_filters(payload: ApplyFiltersRequest):
    """
    Called when the user clicks Apply Filter.

    Saves the filter selection, then returns output_tabs (all 5 tabs x both
    metrics x both views) for the selected scenarios. Only 'Base'/'BASE' can
    be computed today — any other scenario_name currently returns a 400 until
    a save mechanism exists for multi-payer/multi-product scenario snapshots.
    """
    try:
        return apply_output_filters(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
