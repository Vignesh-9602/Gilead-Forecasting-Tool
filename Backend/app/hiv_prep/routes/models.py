from typing import Any, Dict, Optional , List
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
    multiplier: Optional[float] = 1.0
    multiplier_horizon: Optional[str] = "Forecast"

    ets: Optional[ETSFactors] = None
    linear: Optional[GrowthFactors] = None
    scurve: Optional[GrowthFactors] = None
    exponential: Optional[GrowthFactors] = None
    logarithmic: Optional[GrowthFactors] = None
    active_model: Optional[str] = None


class RefreshScenarioRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter
    scenario_name: Optional[str] = "Base"
    model_type: Optional[str] = "ets"
    factors: Optional[Factors] = None

    selected_tab: str
    selected_metric: str

    market_analysis: Dict[str, Any]


class SaveScenarioRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter
    scenario_name: str
    model_type: Optional[str] = "ets"
    factors: Optional[Factors] = None
    market_analysis: Dict[str, Any]

class Scenario(BaseModel):
    factors: Dict[str, Any]
    market_analysis: Dict[str, Any]


# class RefreshEditsRequest(BaseModel):
#     ta_name: str

#     selected_filter: Dict[str, Any]

#     scenario_name: str

#     active_scenario: str

#     model_type: str

#     factors: Dict[str, Any]

#     selected_tab: str

#     selected_metric: str

#     market_analysis: Dict[str, Any]