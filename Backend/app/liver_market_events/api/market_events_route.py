from fastapi import APIRouter, HTTPException
from fastapi.params import Query

from app.liver_market_events.schemas.market_events_schema import (
    ApplyFiltersRequest,
    RefreshRequest,
    RunCalculationRequest,
    SaveMarketEventsRequest,
    CreateProductRequest,
    UpdateProductRequest,
)
from app.liver_market_events.services.market_events_service import (
    get_market_events_filters,
    apply_market_events_filters,
    refresh_market_events,
    save_market_events,
    get_manage_products,
    create_market_events_product,
    update_market_events_product,
    delete_market_events_product,
)
from app.liver_market_events.services.run_calculation_service import (
    run_market_events_calculation,
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


@router.post("/run-calculation")
def market_events_run_calculation(payload: RunCalculationRequest):
    """
    Called when the user clicks Run Calculation.

    Applies the configured event curves (from impact_curve_configuration.rows)
    to the BASE transaction data for the active tab, rebuilds metrics_views for
    all three tabs, and returns the same structure as /apply-filters.

    Only the active tab's data is modified by the events; the other two tabs
    continue to reflect BASE scenario values so the user can compare.
    """
    try:
        return run_market_events_calculation(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-scenario")
def market_events_save_scenario(payload: SaveMarketEventsRequest):
    """
    Called when the user clicks Save Scenario.

    Persists the current event_tabs under the given scenario_name.
    Returns 400 if scenario_name is 'Base' (Base cannot be overwritten).
    """
    try:
        return save_market_events(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products")
def manage_products():
    """
    Called when the Manage Products modal opens.

    Returns every product (active and inactive) with its audit columns
    (Date Added / Added By / Modified By) for the management table.
    """
    try:
        return get_manage_products()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/products")
def create_product_route(payload: CreateProductRequest):
    """
    Called when the user clicks Save on the Add Product form.

    Creates a new row in product_master, immediately visible in every
    product dropdown across Market Events, Model Input, and Output (they
    all read the same table).
    """
    try:
        return create_market_events_product(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_name}")
def update_product_route(product_name: str, payload: UpdateProductRequest):
    """Called when the user edits a product's name via the pencil icon."""
    try:
        return update_market_events_product(product_name, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_name}")
def delete_product_route(product_name: str):
    """Called when the user clicks the trash icon. Hard-deletes the row."""
    try:
        return delete_market_events_product(product_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from app.liver_market_events.services.Events_Management import (
    SaveEventRequest,
    EventType,
    get_all_market_events,
    save_market_events,
    delete_market_event,
)
 


@router.post("/save")
def save_market_events_route(payload: SaveEventRequest):
    try:
        return save_market_events(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{event_name}")
def delete_market_event_route(
    event_name: str,
    ta_name: str = Query(...),
    event_type: EventType = Query(...),
):
    try:
        return delete_market_event(event_name, ta_name, event_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/market-events/{ta_name}")
def get_all_events(ta_name: str):
    return get_all_market_events(ta_name)