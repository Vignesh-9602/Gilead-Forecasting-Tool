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