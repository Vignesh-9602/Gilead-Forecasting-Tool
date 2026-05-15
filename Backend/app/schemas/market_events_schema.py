from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class MarketEventIndicationData(BaseModel):
    scenarios: List[str]


class MarketEventFiltersResponse(BaseModel):
    ta_name: str
    # indications: List[str]
    data: Dict[str, MarketEventIndicationData]

class MarketEventApplyFilterRequest(BaseModel):
    ta_name: str
    indication: str
    scenario_name: str


class MarketEventApplyFilterResponse(BaseModel):
    ta_name: str
    indication: str
    scenario_name: str

    lots: List[str]
    target_products: List[str]
    source_products: List[str]

    metric_filters: List[Dict[str, str]]
    curve_types: List[str]
    forecast_start_date: Optional[str]

    metrics_data: Dict[str, Any]

class MarketEventRunEvent(BaseModel):
    event_name: Optional[str] = None
    lot: str
    target_product: str
    source_percentages: Dict[str, float]
    start_date: str
    peak_percent: float
    duration_months: int
    curve_type: str
    k_value: Optional[float] = None


class MarketEventRunCalculationRequest(BaseModel):
    ta_name: str
    indication: str
    scenario_name: str
    events: List[MarketEventRunEvent]


class MarketEventRunCalculationResponse(BaseModel):
    ta_name: str
    indication: str
    scenario_name: str
    events_applied: int
    metrics_data: Dict[str, Any]

class MarketEventChildRow(BaseModel):
    label: str
    values: List[float]


class MarketEventLotGroup(BaseModel):
    lot: str
    total: List[float]
    children: List[MarketEventChildRow]


class MarketEventSaveRequest(BaseModel):
    ta_name: str
    indication: str
    scenario_name: str
    metric: str
    table: List[MarketEventLotGroup]