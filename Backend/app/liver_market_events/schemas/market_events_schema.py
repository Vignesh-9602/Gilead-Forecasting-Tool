from pydantic import BaseModel
from typing import List


# ---------------------------------------------------------------------------
# Shared: selected filter (used in both request and response)
# ---------------------------------------------------------------------------

class SelectedFilter(BaseModel):
    """The filter values the user has selected."""
    scenario_name: str
    payers: List[str]       # multiple payers can be selected
    products: List[str]     # multiple products can be selected
    start_date: str         # "YYYY-MM-DD"
    end_date: str           # "YYYY-MM-DD"


# ---------------------------------------------------------------------------
# GET /filters response
# ---------------------------------------------------------------------------

class MarketEventsFiltersResponse(BaseModel):
    """Full response shape for GET /api/liver-market-events/filters."""
    ta_name: str
    available_scenarios: List[str]
    payers: List[str]
    products: List[str]
    available_months: List[str]
    selected_filter: SelectedFilter


# ---------------------------------------------------------------------------
# POST /apply-filters request
# ---------------------------------------------------------------------------

class ApplyFiltersRequest(BaseModel):
    """Request body for POST /api/liver-market-events/apply-filters."""
    ta_name: str = "HCV"
    selected_filter: SelectedFilter
