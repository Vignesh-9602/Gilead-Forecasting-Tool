from typing import List
from pydantic import BaseModel


class SelectedFilter(BaseModel):
    scenario_name: str
    markets: List[str]
    products: List[str]
    start_date: str
    end_date: str


class ApplyFiltersRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter