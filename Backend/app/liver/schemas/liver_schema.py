from pydantic import BaseModel, model_validator
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Configuration  (mirrors oncology's Configuration schema)
# ---------------------------------------------------------------------------

class LiverConfiguration(BaseModel):
    ta_name: str = "HCV"
    payer: List[str] = []
    brand: List[str] = []
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

class LiverSelectedFilter(BaseModel):
    market: Optional[str] = None
    product: Optional[str] = None
    start_date: str
    end_date: str


class LiverFiltersResponse(BaseModel):
    ta_name: str
    markets: List[str]
    products: List[str]
    available_months: List[str]
    selected_filter: LiverSelectedFilter


# ---------------------------------------------------------------------------
# Apply filters request
# to_date and forecast_periods are stored in config — not in request
# ---------------------------------------------------------------------------

class LiverApplyFiltersRequest(BaseModel):
    ta: str = "HCV"
    payer: List[str] = []
    brand: List[str] = []
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
# Factors — internal computation types (mirrors oncology structure)
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
    """Internal type used by the service layer."""
    ets: EtsParams
    linear: LinearParams
    scurve: SCurveParams
    exponential: ExponentialParams
    logarithmic: LogarithmicParams
    multiplier: float = 1.0
    multiplier_horizon: str = "Forecast"
    active_model: str = "ets"


# ---------------------------------------------------------------------------
# Request factors — mirrors oncology's RecalculateFactors pattern
# ---------------------------------------------------------------------------

class LiverGrowthFactors(BaseModel):
    """Parameters for linear / exponential / logarithmic / scurve models."""
    total_growth: float
    duration: int
    k_value: Optional[float] = None        # required for exp/log/scurve; omit for linear
    trajectory_start: Optional[str] = None


class LiverRecalculateFactors(BaseModel):
    """
    factors: only the active model's params need to be provided.
    Also accepts legacy {level, trend, damping} ETS format.
    """
    multiplier: float = 1.0
    multiplier_horizon: str = "Forecast"
    ets: Optional[EtsParams] = None
    linear: Optional[LiverGrowthFactors] = None
    exponential: Optional[LiverGrowthFactors] = None
    logarithmic: Optional[LiverGrowthFactors] = None
    scurve: Optional[LiverGrowthFactors] = None
    growth: Optional[LiverGrowthFactors] = None  # legacy fallback

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_format(cls, data):
        if isinstance(data, dict) and "level" in data:
            return {
                "ets": {
                    "alpha": data.get("level", 0.3),
                    "beta":  data.get("trend", 0.2),
                    "gamma": data.get("damping", 0.98),
                },
                "multiplier":         data.get("multiplier", 1.0),
                "multiplier_horizon": "Forecast",
            }
        return data


# ---------------------------------------------------------------------------
# Apply filters response
# ---------------------------------------------------------------------------

class LiverApplyFiltersResponse(BaseModel):
    ta_name: str
    selected_filter: LiverSelectedFilter
    available_scenarios: List[str]
    active_scenario: str
    scenarios: Dict[str, Any]       # keyed by scenario name; active has factors + market_analysis


# ---------------------------------------------------------------------------
# Recalculate request
# ---------------------------------------------------------------------------

class LiverRecalculateRequest(BaseModel):
    ta_name: str = "HCV"
    selected_filter: LiverSelectedFilter
    scenario_name: str = "Base"
    model_type: str = "ets"             # "ets" | "linear" | "exponential" | "logarithmic" | "scurve"
    factors: LiverRecalculateFactors
    selected_tab: str = "total_market_volume"  # "total_market_volume" → affects all tabs; others → tab1 stays ETS


# ---------------------------------------------------------------------------
# Save scenario
# ---------------------------------------------------------------------------

class LiverSaveScenarioRequest(BaseModel):
    ta_name: str = "HCV"
    scenario_name: str
    selected_filter: LiverSelectedFilter
    source_scenario: str = "Base"
    factors: Dict[str, Any]
    market_analysis: Dict[str, Any] = {}


class LiverSaveScenarioResponse(BaseModel):
    scenario_name: str
    message: str


# ---------------------------------------------------------------------------
# Refresh / edit table
# ---------------------------------------------------------------------------

class LiverRefreshRequest(BaseModel):
    ta_name: str = "HCV"
    selected_filter: LiverSelectedFilter
    scenario_name: str = "Base"
    selected_tab: str                        # e.g. "total_market_volume", "market_distribution"
    selected_metric: str = "market_volume"   # "market_volume" | "market_share"
    edited_hierarchy: Optional[str] = None   # row label that was edited (for redistribution)
    factors: Optional[Dict[str, Any]] = None # pass-through; returned as-is for active scenario
    market_analysis: Dict[str, Any] = {}


