from pydantic import BaseModel, model_validator
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
# Factors — mirrors oncology structure
# ---------------------------------------------------------------------------

class EtsParams(BaseModel):
    alpha: float
    beta: float
    gamma: float


class LinearParams(BaseModel):
    duration: int
    total_growth: float
    trajectory_start: str


class SCurveParams(BaseModel):
    k_value: float
    duration: int
    total_growth: float
    trajectory_start: str


class ExponentialParams(BaseModel):
    k_value: float
    duration: int
    total_growth: float
    trajectory_start: str


class LogarithmicParams(BaseModel):
    k_value: float
    duration: int
    total_growth: float
    trajectory_start: str


class LiverFactors(BaseModel):
    ets: EtsParams
    linear: LinearParams
    scurve: SCurveParams
    exponential: ExponentialParams
    logarithmic: LogarithmicParams
    multiplier: float = 1.0
    multiplier_horizon: str = "Forecast"
    active_model: str = "ets"

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_format(cls, data):
        """Accept old frontend format {level, trend, damping, multiplier} and convert."""
        if isinstance(data, dict) and "level" in data:
            alpha = data.get("level", 0.3)
            beta  = data.get("trend", 0.2)
            gamma = data.get("damping", 0.98)
            mult  = data.get("multiplier", 1.0)
            return {
                "ets":         {"alpha": alpha, "beta": beta, "gamma": gamma},
                "linear":      {"duration": 12, "total_growth": 0, "trajectory_start": "2025-01-01"},
                "scurve":      {"k_value": 1, "duration": 12, "total_growth": 0, "trajectory_start": "2025-01-01"},
                "exponential": {"k_value": 1, "duration": 12, "total_growth": 0, "trajectory_start": "2025-01-01"},
                "logarithmic": {"k_value": 1, "duration": 12, "total_growth": 0, "trajectory_start": "2025-01-01"},
                "multiplier":         mult,
                "multiplier_horizon": "Forecast",
                "active_model":       "ets",
            }
        return data


# ---------------------------------------------------------------------------
# Apply filters response
# ---------------------------------------------------------------------------

class LiverApplyFiltersResponse(BaseModel):
    months: List[str]               # ISO dates ["2020-04-01", ...]
    forecast_start_index: int
    factors: Dict[str, Any]         # flat {level, trend, damping, multiplier} for frontend
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
    factors: LiverFactors


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
    factors: LiverFactors
    chart_data: Dict[str, Any]


class LiverSaveScenarioResponse(BaseModel):
    scenario_name: str
    message: str
