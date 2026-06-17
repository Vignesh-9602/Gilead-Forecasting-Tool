from pydantic import BaseModel, Field
from typing import List, Optional


class DemandParams(BaseModel):
    base_mean: Optional[float] = Field(default=None, ge=0,
        description="Override base demand per month. If None → dynamic from DB per month.")
    std_pct: Optional[float] = Field(default=None, ge=0,
        description="Std dev as % of mean. If None → auto-calculated using Poisson (sqrt of mean).")


class ComplianceParams(BaseModel):
    mean: Optional[float] = Field(default=None, ge=0, le=1,
        description="Compliance base mean (0–1). If None → calculated from DB (fact_vials_compliance).")
    std: Optional[float] = Field(default=None, ge=0,
        description="Compliance std dev. If None → defaults to 0.05.")


class PricingParams(BaseModel):
    price_per_vial: Optional[float] = Field(default=None, ge=0,
        description="USD price per vial. If None → revenue calculated as 0 (no price set).")
    std: float = Field(default=0.0, ge=0,
        description="Pricing std dev. Always 0 (Fixed distribution) — shown in modal but not sampled.")


class MonteCarloRunRequest(BaseModel):
    ta_name: str
    brand: str = "All Brands"
    n_iterations: int = Field(default=1000, ge=100, le=10000)
    confidence_interval: float = Field(default=0.90, gt=0, lt=1)
    demand_params: Optional[DemandParams] = None
    compliance_params: Optional[ComplianceParams] = None
    pricing_params: Optional[PricingParams] = None


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
    demand_base_mean: float         # average monthly demand (auto-calculated or user override)
    demand_volatility: float        # effective std_pct used
    compliance_mean: float          # from DB or user override
    compliance_volatility: float    # std used
    price_per_vial: float           # from user or 0 if not set
    pricing_std: float              # always 0.00


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
