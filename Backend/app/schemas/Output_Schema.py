from pydantic import BaseModel
from typing import List, Dict


class OutputSelectedFilter(BaseModel):
    scenario_name: str
    indications: List[str]
    lots: List[str]
    brands: List[str]
    start_date: str
    end_date: str


class OutputFiltersResponse(BaseModel):
    ta_name: str
    scenario_names: List[str]

    # scenario -> indication -> lot -> brands
    data: Dict[str, Dict[str, Dict[str, List[str]]]]

    available_months: List[str]
    selected_filter: OutputSelectedFilter


class OutputApplyRequest(BaseModel):
    ta_name: str
    scenario_name: str
    indications: List[str]
    lots: List[str]
    brands: List[str]
    start_date: str
    end_date: str