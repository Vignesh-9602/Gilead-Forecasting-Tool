from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Configuration  (mirrors oncology's Configuration schema)
# ---------------------------------------------------------------------------

class LiverConfiguration(BaseModel):
    ta_name: str = "HCV"
    payer: List[str] = ["All"]      # multi-select — ["All"] means no payer filter
    brand: List[str] = ["All"]      # multi-select — ["All"] means no brand filter
    train_start_date: str           # "2020-04-01"
    train_end_date: str             # "2025-12-01"
    model_granularity: str = "monthly"
    forecast_periods: str           # frontend sends/receives as date "2026-06-01"; DB stores as int


class SaveLiverConfigRequest(BaseModel):
    config: LiverConfiguration


class LiverConfigResponse(BaseModel):
    ta_name: str
    exists: bool
    config: Optional[LiverConfiguration]
    available_train_months: List[str]   # ["2020-01-01", "2020-02-01", ...]


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
    available_dates: List[str]          # ["Apr-20", "May-20", ...]
    from_date: str                      # train_start_date from saved config
    to_date: str                        # train_end_date from saved config


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
    from_date: str                      # "2020-04" — start of view window
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
# to_date and forecast_periods come from config — not in request
# ---------------------------------------------------------------------------

class LiverRecalculateRequest(BaseModel):
    ta: str = "HCV"
    payer: List[str] = ["All"]          # multi-select
    brand: List[str] = ["All"]          # multi-select
    product: str = "All"
    metric: str = "market_volume"
    from_date: str
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
