from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class Configuration(BaseModel):
    ta_name: str
    train_start_date: str
    train_end_date: str
    model_granularity: str
    forecast_periods: str

class ConfigurationResponse(BaseModel):
    ta_name: str
    exists: bool
    config: Optional[Configuration] = None
    available_train_months: List[str] = []

class SaveConfigRequest(BaseModel):
    config: Configuration

class SelectedFilter(BaseModel):
    market: str
    product: str
    start_date: str
    end_date: str


class ModelInputFilterResponse(BaseModel):
    ta_name: str
    markets: List[str]
    products: List[str]
    available_months: List[str]
    selected_filter: SelectedFilter
from pydantic import BaseModel
from typing import Optional


# selected filter
class SelectedFilter(BaseModel):
    start_date: str
    end_date: str
    market: Optional[str] = "All"
    product: Optional[str] = "All"


# main request
class ApplyScenarioRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter
