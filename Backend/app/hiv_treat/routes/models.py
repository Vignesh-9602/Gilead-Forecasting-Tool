from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SelectedFilter(BaseModel):
    start_date: str
    end_date: str
    market: Optional[str] = None
    product: Optional[str] = None


class ETSFactors(BaseModel):
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None


class GrowthFactors(BaseModel):
    total_growth: Optional[float] = None
    duration: Optional[int] = None
    k_value: Optional[float] = None
    trajectory_start: Optional[str] = None


class Factors(BaseModel):
    ets: Optional[ETSFactors] = None
    linear: Optional[GrowthFactors] = None
    scurve: Optional[GrowthFactors] = None
    exponential: Optional[GrowthFactors] = None
    logarithmic: Optional[GrowthFactors] = None

    multiplier: Optional[float] = 1.0
    multiplier_horizon: Optional[str] = "Forecast"
    active_model: Optional[str] = None


class CellEdit(BaseModel):
    frequency: str = "monthly"      # monthly/yearly
    category: str                  # Overall, Retail, Non-retail, Biktarvy, etc.
    month: str                     # 2024-06-01
    value: float


class RefreshEditsRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter

    scenario_name: Optional[str] = "Base"
    model_type: Optional[str] = "ets"
    factors: Optional[Factors] = None

    selected_tab: str              # market_distribution
    selected_metric: str           # market_share

    market_analysis: Dict[str, Any]
    edits: List[CellEdit]


class SaveScenarioRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter

    scenario_name: str
    model_type: Optional[str] = "ets"
    factors: Optional[Factors] = None

    market_analysis: Dict[str, Any]