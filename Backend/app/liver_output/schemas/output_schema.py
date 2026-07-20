from __future__ import annotations
from pydantic import BaseModel
from typing import List


# ---------------------------------------------------------------------------
# Shared: selected filter (used in both request and response)
# ---------------------------------------------------------------------------

class SelectedFilter(BaseModel):
    """The filter values the user has selected."""
    scenario_names: List[str]   # multiple scenarios can be selected (comparison view)
    payers: List[str]           # multiple payers can be selected
    products: List[str]         # multiple products can be selected
    start_date: str             # "YYYY-MM-DD"
    end_date: str                # "YYYY-MM-DD"


# ---------------------------------------------------------------------------
# GET /filters response
# ---------------------------------------------------------------------------

class OutputFiltersResponse(BaseModel):
    """Full response shape for GET /api/liver-output/filters."""
    ta_name: str
    available_scenarios: List[str]
    payers: List[str]
    products: List[str]
    available_months: List[str]
    selected_filter: SelectedFilter


# ---------------------------------------------------------------------------
# POST /apply-filters request
#
# Response is intentionally left as a plain dict (not modeled) — output_tabs
# is a deeply nested, dynamically-shaped structure (5 tabs x 2 metrics x 2
# views, with 3-level recursive hierarchy on 2 of the tabs), matching the
# convention already used by liver_market_events' apply-filters/refresh.
# ---------------------------------------------------------------------------

class ApplyFiltersRequest(BaseModel):
    """Request body for POST /api/liver-output/apply-filters."""
    ta: str = "HCV"
    scenario_names: List[str]
    payers: List[str]
    products: List[str]
    start_date: str
    end_date: str
    selected_metric: str = "payer_volume"   # pass-through UI state; response always includes both metrics
    selected_view: str = "monthly"          # pass-through UI state; response always includes both views
