from typing import Any, Dict, Optional , List
from pydantic import BaseModel


class SelectedFilter(BaseModel):
    start_date: str
    end_date: str
    market: Optional[str] = None
    product: Optional[str] = None

class RefreshEditsRequest(BaseModel):

    ta_name: str
    selected_filter: Dict[str, Any]
    scenario_name: str
    model_type: str
    factors: Dict[str, Any]
    selected_tab: str
    selected_metric: str
    market_analysis: Dict[str, Any]
    edited_rows: Optional[list[str]] = None

class RefreshEditsResponse(BaseModel):

    ta_name: str
    selected_filter: Dict[str, Any]
    scenario_name: str
    model_type: str
    factors: Dict[str, Any]
    market_analysis: Dict[str, Any]