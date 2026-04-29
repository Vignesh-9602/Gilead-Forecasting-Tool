# schema.py
from pydantic import BaseModel
from typing import Any, List, Dict,Optional

class Scenario(BaseModel):
    scenario_id: int
    scenario_name: str

class LotData(BaseModel):
    products: List[str]
    available_scenarios: List[Scenario]

class FilterResponse(BaseModel):
    ta_name: str
    data: Dict[str, Dict[str, LotData]]  # indication -> lot -> LotData
    metric_filters: List[Dict[str, str]]

class ApplyFilterRequest(BaseModel):
    ta_name: str
    indication: str
    lot: str
    metric: str
    scenario_ids: List[int]

class ApplyFilterResponse(BaseModel):
    therapy_area: str
    indication: str
    lot: str
    metric: str
    chart: Dict[str, Any]
    table: List[Dict[str, Any]]

class SaveScenarioComparision(BaseModel):
    ta_name: str
    indication: str
    lot: str
    metric: str
    scenario_id: int
    user_id: Optional[str]   # IMPORTANT (add this)