from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Any, Dict, List, Optional, Literal, Union


# ------------------------------------
# intial post
# ------------------------------------
class MetricSelectionRequest(BaseModel):
    ta_name: str
    scenario_name: str              
    indications: List[str]
    lots: List[str]
    metric_filter: str              # "market_share" | "nps"
    product: Optional[str] = ""     # required only for market_share

# ------------------------------------
# MODEL TYPES
# ------------------------------------
from pydantic import BaseModel, model_validator
from typing import Optional, Literal, List

ModelType = Literal["ets", "linear", "exponential", "logarithmic", "scurve"]

MultiplierHorizon = Literal[
    "Forecast",
    "History",
    "Both History & Forecast"
]

class ETSFactors(BaseModel):
    alpha: float
    beta: float
    gamma: float

class GrowthFactors(BaseModel):
    total_growth: float
    duration: int
    k_value: Optional[float] = None  # required for exp/log/s_curve; not allowed for linear

class RecalculateFactors(BaseModel):
    multiplier: float = 1.0
    multiplier_horizon: MultiplierHorizon = "Forecast"

    ets: Optional[ETSFactors] = None
    growth: Optional[GrowthFactors] = None  # used for linear/exp/log/s_curve

class MetricRecalculateRequest(BaseModel):
    ta_name: str
    indications: List[str]
    lots: List[str]
    metric_filter: str
    product: Optional[str] = ""

    model_type: ModelType
    factors: RecalculateFactors

    @model_validator(mode="after")
    def validate_payload(self):
        mt = self.model_type
        f = self.factors

        # ETS selected
        if mt == "ets":
            if f.ets is None:
                raise ValueError("For model_type='ets', factors.ets is required")
            if f.growth is not None:
                raise ValueError("For model_type='ets', do not send factors.growth")
            return self

        # Non-ETS selected (linear/exp/log/s_curve)
        if f.growth is None:
            raise ValueError(f"For model_type='{mt}', factors.growth is required")
        if f.ets is not None:
            raise ValueError(f"For model_type='{mt}', do not send factors.ets")

        if f.growth.duration <= 0:
            raise ValueError("duration must be > 0")

        # k rules by model
        if mt == "linear":
            if f.growth.k_value is not None:
                raise ValueError("linear model should not include k_value")
        else:
            if f.growth.k_value is None:
                raise ValueError(f"{mt} model requires k_value")
            if f.growth.k_value <= 0:
                raise ValueError("k_value must be > 0")

        return self

# ------------------------------------
# save changes
# ------------------------------------

class ChildRow(BaseModel):
    label: str
    values: List[float]

class LotGroup(BaseModel):
    lot: str
    total: List[float]
    children: List[ChildRow]

class Refreshchangerequest(BaseModel):
    therapy_area: str
    indication: str
    metric: str
    product: str
    lot: str
    table: List[LotGroup]

# ------------------------------------
# save scenario
# ------------------------------------

class SaveScenarioRequest(BaseModel):
    scenario_name: str
    user_id: Optional[str] = None

    ta_name: str
    indication: str

    metric: Optional[str] = None
    product: Optional[str] = None
    lot: Optional[str] = None
    model_type: str

    factors: Dict[str, Any]
    metrics_data: Dict[str, Any]


class UpdateScenarioRequest(BaseModel):
    scenario_name: str
    ta_name: str
    indication: str
    lot: str
    metric: str
    product: Optional[str] = None

    model_type: str
    factors: Dict[str, Any]
    metrics_data: Dict[str, Any]