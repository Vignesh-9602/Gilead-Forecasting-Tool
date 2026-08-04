from pydantic import BaseModel, Field
from typing import List, Optional

class OutputScreenResponse(BaseModel):
    ta_name: str
    available_scenarios: list[str]
    markets: list[str]
    products: list[str]
    available_months: list[str]
    selected_filter: dict


class OutputScreenSelectedFilter(BaseModel):
    scenario_names: List[str] = Field(default_factory=list)

    start_date: str
    end_date: str

    markets: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)


class ApplyOutputScreenFiltersRequest(BaseModel):
    ta_name: str

    selected_filter: OutputScreenSelectedFilter

    selected_metric: str = "market_volume"
    selected_view: str = "monthly"