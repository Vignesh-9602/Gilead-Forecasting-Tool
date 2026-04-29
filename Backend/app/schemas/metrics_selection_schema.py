from pydantic import BaseModel, Field
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
# ETS FACTORS
# ------------------------------------
class ETSFactors(BaseModel):
    alpha: float
    beta: float
    gamma: float
    # trend_type: Literal["additive"]
    # seasonality: Optional[str] = "none"

# ------------------------------------
# TRAJECTORY FACTORS
# ------------------------------------
class TrajectoryFactors(BaseModel):
    growth_type: Literal["linear", "exponential", "logarithmic"]
    total_growth: float
    duration: int
    trajectory_start: Optional[str] = None

from typing import Literal

MultiplierHorizon = Literal[
    "Forecast",
    "History",
    "Both History & Forecast"
]


class RecalculateETSFactors(BaseModel):
    multiplier: float
    multiplier_horizon: MultiplierHorizon = "Forecast"
    ets: ETSFactors

class RecalculateTrajectoryFactors(BaseModel):
    multiplier: float
    multiplier_horizon: MultiplierHorizon = "Forecast"
    ets: ETSFactors
    trajectory: TrajectoryFactors

class MetricRecalculateETSRequest(BaseModel):
    ta_name: str
    indications: List[str]
    lots: List[str]
    metric_filter: str
    product: Optional[str] = ""

    model_type: Literal["ets"]
    factors: RecalculateETSFactors

class MetricRecalculateTrajectoryRequest(BaseModel):
    ta_name: str
    indications: List[str]
    lots: List[str]
    metric_filter: str
    product: Optional[str] = ""

    model_type: Literal["trajectory"]
    factors: RecalculateTrajectoryFactors
# ------------------------------------
# UNION (IMPORTANT)
# ------------------------------------


MetricRecalculateRequest = Annotated[
    Union[
        MetricRecalculateETSRequest,
        MetricRecalculateTrajectoryRequest
    ],
    Field(discriminator="model_type")
]


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

class SaveChangesRequest(BaseModel):
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
    lot: str
    metric: str
    product: Optional[str] = None

    model_type: str  # "ets" or "trajectory"

    factors: Dict[str, Any]
    chart: Dict[str, Any]
    table: List[Dict[str, Any]]