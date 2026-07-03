from fastapi import APIRouter, HTTPException

from app.liver.schemas.liver_schema import (
    SaveLiverConfigRequest,
    LiverFiltersResponse,
    LiverApplyFiltersRequest,
    LiverApplyFiltersResponse,
    LiverRecalculateRequest,
    LiverSaveScenarioRequest,
    LiverRefreshRequest,
)
from app.liver.services.liver_service import (
    get_liver_configuration,
    save_liver_configuration,
    get_liver_filters,
    apply_liver_filters,
    recalculate_liver,
    save_liver_scenario,
    update_liver_scenario,
    refresh_liver,
)

router = APIRouter(prefix="/api/liver", tags=["Liver"])


# ---------------------------------------------------------------------------
# Configuration endpoints (mirrors oncology /api/configurations)
# ---------------------------------------------------------------------------

@router.get("/configurations/{ta_name}")
def liver_get_configuration(ta_name: str):
    """
    Load saved configuration for a TA. Config stores selected payers/brands as lists.
    Returns exists=False with config=None if no config saved yet.
    """
    try:
        return get_liver_configuration(ta_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configurations")
def liver_save_configuration(payload: SaveLiverConfigRequest):
    """
    Save or update configuration for a TA.
    Validates train dates against actual data range in transaction_data.
    """
    try:
        return save_liver_configuration(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Filter / data endpoints
# ---------------------------------------------------------------------------

@router.get("/filters", response_model=LiverFiltersResponse)
def liver_filters(ta: str = "HCV", payer: str = "Medicaid", brand: str = "GILD"):
    """
    Called on page load and whenever payer/brand selection changes.
    Returns from_date and to_date from the saved config for the given (ta, payer, brand).
    Falls back to 5-year default if no config saved for that combination.
    """
    try:
        return get_liver_filters(ta, payer, brand)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-filters", response_model=LiverApplyFiltersResponse)
def liver_apply_filters(payload: LiverApplyFiltersRequest):
    """
    Called when user clicks Apply Filter.
    Reads train_end_date and forecast_periods from saved configuration.
    Calculates all 5 tabs on the fly from transaction_data.
    Returns chart + table data for all tabs with ETS factors for sliders.
    """
    try:
        return apply_liver_filters(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recalculate", response_model=LiverApplyFiltersResponse)
def liver_recalculate(payload: LiverRecalculateRequest):
    """
    Called when user adjusts ETS sliders and clicks Recalculate.
    Re-runs forecast with new level/trend/damping/multiplier values.
    train_end_date and forecast_periods still come from saved configuration.
    """
    try:
        return recalculate_liver(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-scenario")
def liver_save_scenario(payload: LiverSaveScenarioRequest):
    """
    Create a new scenario. Rejects if scenario_name already exists or equals 'Base'.
    """
    try:
        return save_liver_scenario(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update-scenario")
def liver_update_scenario(payload: LiverSaveScenarioRequest):
    """
    Overwrite an existing non-Base scenario. Rejects if scenario doesn't exist or equals 'Base'.
    """
    try:
        return update_liver_scenario(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def liver_refresh(payload: LiverRefreshRequest):
    """
    Propagate a user's table edit across related tabs and metrics.
    - TMV edit: keep distribution shares, recompute volumes.
    - Dist tab volume edit: redistribute others to maintain sum = TMV, recompute shares.
    - Dist tab share edit: redistribute others to maintain sum = 100%, recompute volumes.
    """
    try:
        return refresh_liver(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
