# schema.py
from pydantic import BaseModel
from typing import Any, List, Dict,Optional


class MetricFilterOption(BaseModel):
    label: str
    value: str


class ScenarioOption(BaseModel):
    scenario_id: str
    scenario_name: str


class LotFilterData(BaseModel):
    products: List[str]
    available_scenarios: List[ScenarioOption]


class FilterResponse(BaseModel):
    ta_name: str
    data: Dict[str, Dict[str, LotFilterData]]
    metric_filters: List[MetricFilterOption]

class ApplyFilterRequest(BaseModel):
    ta_name: str
    indication: str
    lot: str
    metric: str
    scenario_names: List[str]
    product: Optional[str] = None


class ApplyFilterResponse(BaseModel):
    therapy_area: str
    indication: str
    lot: str
    metric: str
    product: Optional[str] = None
    chart: Dict[str, Any]
    table: List[Dict[str, Any]]

class SaveScenarioComparision(BaseModel):
    ta_name: str
    indication: str
    lot: str
    metric: str
    scenario_id: int

    finalize: Optional[bool] = False
    chart: Optional[Dict[str, Any]] = None
    table_data: Optional[List[Dict[str, Any]]] = None

class SavedSelectionResponse(BaseModel):
    lot: str
    scenario_id: int
    scenario_name: str

class SaveScenarioResponse(BaseModel):
    message: str
    saved_selection: SavedSelectionResponse
    finalization_status: Dict[str, bool]
    can_finalize: bool

class FinalizeScenarioRequest(BaseModel):
    ta_name: str
    indication: str
    metric: str


class FinalizeScenarioResponse(BaseModel):
    message: str
    finalized: bool
    finalized_selections: Dict[str, dict]