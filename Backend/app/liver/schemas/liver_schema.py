from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Configuration  (mirrors oncology's Configuration schema)
# ---------------------------------------------------------------------------

class LiverConfiguration(BaseModel):
    ta_name: str = "HCV"
    payer: List[str] = ["All"]      # payers to save config for (expanded to rows per combination)
    brand: List[str] = ["All"]      # brands to save config for
    train_start_date: str           # "2020-04-01"
    train_end_date: str             # "2025-12-01"
    model_granularity: str = "monthly"
    forecast_periods: str           # frontend sends/receives as date "2026-06-01"; DB stores as int


class SaveLiverConfigRequest(BaseModel):
    config: LiverConfiguration


class ConfigEntry(BaseModel):
    """One saved (payer, brand) combination with its date config."""
    payer: str
    brand: str
    train_start_date: str
    train_end_date: str
    model_granularity: str
    forecast_periods: str           # returned as date string


class LiverConfigResponse(BaseModel):
    ta_name: str
    exists: bool
    entries: List[ConfigEntry]          # one entry per saved (payer, brand) combination
    available_train_months: List[str]
    default_config: Optional[ConfigEntry] = None  # pre-filled values when exists=False


# ---------------------------------------------------------------------------
# Filter response
# ---------------------------------------------------------------------------

class MetricOption(BaseModel):
    label: str
    value: str


class LiverFiltersResponse(BaseModel):
    payers: List[str]
    products: List[str]
    scenarios: List[str]
    metric_options: List[MetricOption]
    available_dates: List[str]
    from_date: str                      # train_start_date from saved config for selected payer+brand
    to_date: str                        # forecast end date from saved config
    default_payer: str                  # pre-selected payer on page load
    default_brand: str                  # pre-selected brand on page load


# ---------------------------------------------------------------------------
# Apply filters request
# to_date and forecast_periods are stored in config — not in request
# ---------------------------------------------------------------------------

class LiverApplyFiltersRequest(BaseModel):
    ta: str = "HCV"
    payer: List[str] = ["All"]          # multi-select
    brand: List[str] = ["All"]          # multi-select
    product: str = "All"
    metric: str = "market_volume"       # "market_volume" | "market_share"
    from_date: str                      # "2020-04-01" — start of view window
    to_date: Optional[str] = None       # "2027-12-01" — end of view; falls back to config forecast end
    scenario: str = "Base"


# ---------------------------------------------------------------------------
# Shared chart / table building blocks
# ---------------------------------------------------------------------------

class ChartSeries(BaseModel):
    label: str
    train_values: List[float]
    forecast_values: List[float]


class TableRow(BaseModel):
    hierarchy: str
    values: List[float]


class TabChart(BaseModel):
    series: List[ChartSeries]


class TabTable(BaseModel):
    headers: List[str]
    rows: List[TableRow]


class TabData(BaseModel):
    chart: TabChart
    table: TabTable


# Hierarchical table for payer_wise_product and product_wise_payer tabs

class ChildRow(BaseModel):
    label: str
    values: List[float]


class HierarchicalRow(BaseModel):
    hierarchy: str          # parent label (payer or product)
    total: List[float]      # sum across all children per month
    children: List[ChildRow]


class HierarchicalTabTable(BaseModel):
    headers: List[str]
    rows: List[HierarchicalRow]


class HierarchicalTabData(BaseModel):
    chart: TabChart
    table: HierarchicalTabTable


# ---------------------------------------------------------------------------
# ETS factors
# ---------------------------------------------------------------------------

class EtsFactors(BaseModel):
    level: float
    trend: float
    damping: float
    multiplier: float = 1.0


# ---------------------------------------------------------------------------
# Apply filters response
# ---------------------------------------------------------------------------

class LiverApplyFiltersResponse(BaseModel):
    months: List[str]               # ISO dates ["2020-04-01", ...]
    forecast_start_index: int
    factors: EtsFactors
    tabs: Dict[str, Any]            # tabs 1-3: TabData, tabs 4-5: HierarchicalTabData


# ---------------------------------------------------------------------------
# Recalculate request
# ---------------------------------------------------------------------------

class LiverRecalculateRequest(BaseModel):
    ta: str = "HCV"
    payer: List[str] = ["All"]          # multi-select
    brand: List[str] = ["All"]          # multi-select
    product: str = "All"
    metric: str = "market_volume"
    from_date: str
    to_date: Optional[str] = None       # overrides config forecast end if provided
    factors: EtsFactors


# ---------------------------------------------------------------------------
# Save scenario
# ---------------------------------------------------------------------------

class LiverSaveScenarioRequest(BaseModel):
    scenario_name: str
    ta: str = "HCV"
    payer: List[str] = ["All"]          # multi-select
    brand: List[str] = ["All"]          # multi-select
    product: str = "All"
    metric: str = "market_volume"
    from_date: str
    factors: EtsFactors
    chart_data: Dict[str, Any]


class LiverSaveScenarioResponse(BaseModel):
    scenario_name: str
    message: str
