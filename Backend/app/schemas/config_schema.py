from pydantic import BaseModel
from typing import Literal


class Config(BaseModel):
    # ------------------------
    # PAGE 1 (SCOPE)
    # ------------------------
    ta_name: str
    entity_keys: list[str]

    train_start_date: str
    train_end_date: str
    model_granularity: str
    forecast_periods: int

    # ------------------------
    # SCENARIO (GLOBAL SHIFT)
    # ------------------------
    scenario_multiplier: float

    # ------------------------
    # TREND ADJUSTMENTS (FORECAST ONLY)
    # ------------------------
    trend_type: Literal["additive", "multiplicative", "none"]
    level_alpha: float
    trend_beta: float
    damping_phi: float
