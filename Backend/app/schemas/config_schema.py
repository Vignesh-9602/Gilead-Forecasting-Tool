from pydantic import BaseModel
from typing import List, Dict, Any


# ------------------------
# AVG VIAL
# ------------------------


class AvgVialUpdate(BaseModel):
    brand: str
    dose_per_month: int
    vials_per_month: int


# ------------------------
# CONFIGURATION
# ------------------------
class Configuration(BaseModel):
    # PAGE 1 (Scope)
    ta_name: str
    train_start_date: str
    train_end_date: str
    model_granularity: str
    forecast_periods: int

class SaveConfigRequest(BaseModel):
    config: Configuration


# ------------------------
# UPDATE AVG VIALS ONLY
# ------------------------

class UpdateAvgVialsRequest(BaseModel):
    ta_name: str
    avg_vials: List[AvgVialUpdate]

