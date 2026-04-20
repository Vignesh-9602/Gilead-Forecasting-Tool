from pydantic import BaseModel
from typing import Dict, List, Optional


# ------------------------------------
# intial post
# ------------------------------------
class MetricSelectionRequest(BaseModel):
    ta_name: str
    indications: List[str]
    lots: List[str]
    metric_filter: str              # "market_share" | "nps"
    product: Optional[str] = ""     # required only for market_share


# ------------------------------------
# RECALCULATE FACTORS
# ------------------------------------
class RecalculateFactors(BaseModel):
    multiplier: float
    alpha: float           # level α
    beta: float            # trend β
    gamma: float           # damping φ
    trend_type: str        # "additive" | "none"
    seasonality: Optional[str] = ""        # "monthly" | "none" (metadata only)


# ------------------------------------
# RECALCULATE REQUEST
# ------------------------------------
class MetricRecalculateRequest(BaseModel):
    ta_name: str
    indications: List[str]
    lots: List[str]
    metric_filter: str
    product: Optional[str] = ""
    factors: RecalculateFactors

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
    product: Optional[str] = "" 
    lot: str
    table: List[LotGroup]


 