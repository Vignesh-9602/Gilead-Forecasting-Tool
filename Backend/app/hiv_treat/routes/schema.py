from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date


class Configuration(BaseModel):
    ta_name: str
    train_start_date: str
    train_end_date: str
    model_granularity: str
    forecast_periods: str
    window: int = 6

class ConfigurationResponse(BaseModel):
    ta_name: str
    exists: bool
    config: Optional[Configuration] = None
    available_train_months: List[str] = []

class SaveConfigRequest(BaseModel):
    config: Configuration

class SelectedFilter(BaseModel):
    market: str
    product: str
    start_date: str
    end_date: str


class ModelInputFilterResponse(BaseModel):
    ta_name: str
    markets: List[str]
    products: List[str]
    available_months: List[str]
    selected_filter: SelectedFilter
from pydantic import BaseModel
from typing import Optional


# selected filter
class SelectedFilter(BaseModel):
    start_date: str
    end_date: str
    market: Optional[str] = "All"
    product: Optional[str] = "All"


# main request
class ApplyScenarioRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter


class ETSFactors(BaseModel):
    alpha: float
    beta: float
    gamma: float


class GrowthFactors(BaseModel):
    window: Optional[int] = None
    forecast_periods: Optional[int] = None
    total_growth: Optional[float] = None
    duration: Optional[int] = None
    k_value: Optional[float] = None
    trajectory_start: Optional[str] = None
    

class Factors(BaseModel):
    multiplier: Optional[float] = 1.0
    multiplier_horizon: Optional[str] = "Forecast"
    ets: Optional[ETSFactors] = None
    growth: Optional[GrowthFactors] = None


class RecalculateRequest(BaseModel):
    ta_name: str
    selected_filter: "SelectedFilter"
    scenario_name: Optional[str] = "Base"
    selected_tab: Optional[str] = None
    metric: Optional[str] = "market_share"   # "market_share" | "volume" -- interpretation of target growth
    model_type: str
    factors: Optional["Factors"] = None



#response models


class ChartSeries(BaseModel):
    label: str
    history: List[float]
    forecast: List[float]


class Chart(BaseModel):
    months: List[str]
    forecast_start_index: int
    series: List[ChartSeries]


class MarketVolume(BaseModel):
    chart: Chart
    market_volume: Dict[str, float]
    market_share: Dict[str, float]


class MarketAnalysis(BaseModel):
    total_market_volume: MarketVolume


class Scenario(BaseModel):
    factors: Optional[Dict[str, Any]] = None
    market_analysis: Dict[str, Any]


class RecalculateResponse(BaseModel):
    ta_name: str
    selected_filter: Dict[str, Any]
    available_scenarios: List[str]
    active_scenario: str
    scenarios: Dict[str, Scenario]

class SelectedFilter(BaseModel):
    start_date: str
    end_date: str
    market: str
    product: str
 
 
class SaveScenarioRequest(BaseModel):
    ta_name: str
    scenario_name: str                          # scenario being saved, e.g. "Scenario ABC" -- becomes active_scenario in the response
    selected_filter: SelectedFilter              # needed to rebuild market_product/product_market for the active scenario
    user_id: Optional[str] = "default_user"
    factors: Optional[Dict[str, Any]] = None     # the "factors" block from the frontend -> stored + echoed back for the active scenario
    market_analysis: Dict[str, Any]              # the whole "market_analysis" block the frontend is saving, unmodified

class ApplyScenarioRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter
    scenario_name: str    # scenario the user clicked -> becomes active_scenario
 