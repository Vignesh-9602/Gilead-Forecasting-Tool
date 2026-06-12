from fastapi import APIRouter, HTTPException

from app.schemas.monte_carlo_schema import (
    MonteCarloFiltersResponse,
    MonteCarloRunRequest,
    MonteCarloRunResponse,
)
from app.services.monte_carlo_service import (
    get_monte_carlo_filters,
    run_monte_carlo_simulation,
)

router = APIRouter(prefix="/api/monte-carlo", tags=["Monte Carlo"])


@router.get("/filters/{ta_name}", response_model=MonteCarloFiltersResponse)
def monte_carlo_filters(ta_name: str):
    """
    Returns the list of brands available in persistency_outputs for the given TA,
    plus the supported confidence-interval options for the frontend dropdowns.
    """
    result = get_monte_carlo_filters(ta_name)
    if not result["brands"]:
        raise HTTPException(
            status_code=404,
            detail=f"No persistency data found for TA '{ta_name}'. "
                   "Complete the persistency calculation step first."
        )
    return result


@router.post("/run", response_model=MonteCarloRunResponse)
def monte_carlo_run(payload: MonteCarloRunRequest):
    """
    Runs a Monte Carlo simulation and returns a revenue probability distribution.

    Variables sampled per iteration:
      - Demand (D)      : Normal(base_demand_per_month, std_pct * base_demand)
      - Compliance (C)  : TruncatedNormal(mean, std, low=0, high=1)
      - Pricing/Dosing  : Fixed (price_per_vial, no randomness)

    Revenue per iteration = sum_over_months(D_m) * C * price_per_vial
    """
    try:
        result = run_monte_carlo_simulation(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
