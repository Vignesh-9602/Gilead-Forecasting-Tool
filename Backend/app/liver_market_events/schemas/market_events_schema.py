from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional


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


# ---------------------------------------------------------------------------
# POST /refresh request
# ---------------------------------------------------------------------------

class EditedTableRow(BaseModel):
    """One row from the edited table, possibly with payer/product children."""
    label: str
    values: List[float]
    children: Optional[List[EditedTableRow]] = None
    editable: Optional[bool] = None   # frontend may send this; ignored by backend


class RefreshRequest(BaseModel):
    """Request body for POST /api/liver-market-events/refresh."""
    ta_name: str = "HCV"
    selected_filter: SelectedFilter
    selected_tab: str           # "payer_event" | "product_event" | "overall_event"
    selected_metric: str        # "product_share" | "product_volume" | "payer_share" | "payer_volume"
    selected_view: str          # "monthly" | "yearly"
    selected_table_view: str    # "product_level" | "payer_product_level" | "payer_level" | "product_payer_level" | "overall_level"
    edited_table_rows: List[EditedTableRow]
    edited_label: Optional[str] = None
    # Flat row edit  → "ProductName"  (e.g. "Truvada")
    # Hierarchy edit → "ParentLabel - ChildLabel"  (e.g. "Truvada - Medicare")


# ---------------------------------------------------------------------------
# POST /run-calculation request
# ---------------------------------------------------------------------------

class ImpactCurveRow(BaseModel):
    """One event row from the impact_curve_configuration table."""
    event_id: Optional[int] = None
    event_name: str = "Event"
    # Entity selections (which fields are populated depends on the tab)
    payers: Optional[List[str]] = None          # payer_event: selected payer
    products: Optional[List[str]] = None        # product_event: selected product / payer_event: context
    impacted_payers: Optional[List[str]] = None
    impacted_products: Optional[List[str]] = None
    # Curve parameters
    start_date: str
    peak_percent: float
    months: int                                 # duration in months
    curve_type: str = "Linear"
    factor: float = 1.0
    # Optional coverage
    coverage_peak_percent: Optional[float] = None
    coverage_peak_months: Optional[int] = None
    coverage_curve_type: Optional[str] = None
    coverage_factor: float = 1.0
    # Optional redistribution weights keyed by entity name
    source_percentages: Optional[dict] = None


class ImpactCurveConfiguration(BaseModel):
    rows: List[ImpactCurveRow] = []


class RunCalculationRequest(BaseModel):
    """Request body for POST /api/liver-market-events/run-calculation."""
    ta_name: str = "HCV"
    selected_filter: SelectedFilter
    selected_tab: str       # "payer_event" | "product_event" | "overall_event"
    impact_curve_configuration: ImpactCurveConfiguration
