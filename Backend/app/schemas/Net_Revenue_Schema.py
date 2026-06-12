from pydantic import BaseModel

from pydantic import BaseModel
from typing import Any, Dict, List


class NetRevenueSelectedFilter(BaseModel):
    scenario_name: str
    product: str
    start_date: str
    end_date: str


class NetRevenueFiltersResponse(BaseModel):
    ta_name: str
    scenario_names: List[str]
    products_by_scenario: Dict[str, List[str]]
    available_months: List[str]
    selected_filter: NetRevenueSelectedFilter

class RevenueRequest(BaseModel):
    ta_name: str
    scenario_name: str
    product: str
    start_date: str
    end_date: str


class RevenueEditRow(BaseModel):
    metric: str
    values: List[Any]


class RevenueEditRequest(BaseModel):
    ta_name: str
    scenario_name: str
    product: str
    months: List[str]
    rows: List[RevenueEditRow]