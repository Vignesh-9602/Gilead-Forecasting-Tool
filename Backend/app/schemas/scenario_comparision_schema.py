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
    table: Dict[str, Any]

class SaveScenarioComparision(BaseModel):
    ta_name: str
    indication: str
    lot: str
    metric: str
    scenario_name: str


class SavedSelectionResponse(BaseModel):
    lot: str
    scenario_name: str


class FinalizationStatusItem(BaseModel):
    finalized: bool
    scenario_name: Optional[str] = None


class SaveScenarioResponse(BaseModel):
    message: str
    saved_selection: SavedSelectionResponse
    finalization_status: Dict[str, FinalizationStatusItem]
    can_finalize: bool

class FinalizeScenarioRequest(BaseModel):
    ta_name: str
    indication: str
    metric: str


class FinalizedSelectionItem(BaseModel):
    scenario_id: Optional[int] = None
    scenario_name: str


class FinalizeScenarioResponse(BaseModel):
    message: str
    finalized_selections: Dict[str, FinalizedSelectionItem]
    can_finalize: bool

class ScenarioStatusRequest(BaseModel):
    ta_name: str
    indication: str
    metric: str


class FinalizationStatusItem(BaseModel):
    finalized: bool
    scenario_name: Optional[str] = None


class ScenarioStatusResponse(BaseModel):
    ta_name: str
    indication: str
    metric: str
    finalization_status: Dict[str, FinalizationStatusItem]
    can_finalize: bool

class ClearScenarioRequest(BaseModel):
    ta_name: str
    indication: str
    metric: str


class ClearStatusItem(BaseModel):
    finalized: bool
    scenario_name: Optional[str] = None


class ClearScenarioResponse(BaseModel):
    success: bool
    message: str
    finalization_status: Dict[str, ClearStatusItem]
    can_finalize: bool