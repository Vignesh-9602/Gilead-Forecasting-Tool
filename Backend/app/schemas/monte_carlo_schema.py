from pydantic import BaseModel, Field
from typing import List, Optional


class DemandParams(BaseModel):
    # If not sent → std auto-calculated using Poisson (sqrt of base demand per month)
    # If sent     → overrides the auto-calculated value
    std_pct: Optional[float] = Field(default=None, ge=0, description="Std dev as % of monthly demand. Auto-calculated if not provided.")


class ComplianceParams(BaseModel):
    # If not sent → std defaults to 0.05
    # If sent     → overrides the default
    std: Optional[float] = Field(default=None, ge=0, description="Compliance std dev. Defaults to 0.05 if not provided.")


class PricingParams(BaseModel):
    price_per_vial: float = Field(gt=0, description="USD price per vial (fixed)")


class MonteCarloRunRequest(BaseModel):
    ta_name: str
    brand: str = "All Brands"
    n_iterations: int = Field(default=1000, ge=100, le=10000)
    confidence_interval: float = Field(default=0.90, gt=0, lt=1)
    demand_params: Optional[DemandParams] = None      # None = auto-calculate
    compliance_params: Optional[ComplianceParams] = None  # None = use default
    pricing_params: PricingParams


class HistogramBin(BaseModel):
    range: str
    count: int


class SimulationSummary(BaseModel):
    number_of_simulations: int
    mean_revenue: float
    median_revenue: float
    std_dev_revenue: float
    min_revenue: float
    max_revenue: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float


class InputParameters(BaseModel):
    demand_volatility: float     # effective std_pct used (auto or user override)
    compliance_mean: float       # always from DB
    compliance_volatility: float # std used (auto or user override)


class MonteCarloRunResponse(BaseModel):
    histogram: List[HistogramBin]
    summary: SimulationSummary
    input_parameters: InputParameters


class ConfidenceIntervalOption(BaseModel):
    label: str
    value: float


class MonteCarloFiltersResponse(BaseModel):
    brands: List[str]
    confidence_interval_options: List[ConfidenceIntervalOption]
