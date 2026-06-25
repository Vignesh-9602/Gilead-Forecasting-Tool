from pydantic import BaseModel, Field
from typing import List, Optional


class DemandParams(BaseModel):
    base_mean: Optional[float] = Field(default=None, ge=0,
        description="Override total demand (sum across all months). If None → calculated from DB.")
    std: Optional[float] = Field(default=None, ge=0,
        description="Override demand std dev as absolute value (same scale as demand_volatility in response). If None → calculated from DB.")


class ComplianceParams(BaseModel):
    mean: Optional[float] = Field(default=None, ge=0, le=100,
        description="Compliance base mean (0–100 scale, same as DB). If None → calculated from DB.")
    std: Optional[float] = Field(default=None, ge=0, le=50,
        description="Compliance std dev on 0–100 scale (same as compliance_volatility in response). Max 50. If None → calculated from DB.")


class PricingParams(BaseModel):
    price_per_vial: Optional[float] = Field(default=None, ge=0,
        description="USD price per vial. If None → falls back to DB average net price.")
    std: Optional[float] = Field(default=None, ge=0,
        description="Pricing std dev in USD. If None or 0 → price is fixed (no randomness).")


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


class PeakBarContributors(BaseModel):
    revenue_range: str
    mean_demand: float
    mean_compliance: float
    price_per_vial: float


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
    peak_bar: PeakBarContributors


class InputParameters(BaseModel):
    demand_base_mean: float         # average monthly demand (auto-calculated or user override)
    demand_volatility: float        # effective std_pct used
    compliance_mean: float          # from DB or user override
    compliance_volatility: float    # std used
    price_per_vial: float           # from user or DB average
    pricing_std: float              # 0 if fixed, else USD std dev used


class MonteCarloRunResponse(BaseModel):
    histogram: List[HistogramBin]
    summary: SimulationSummary
    input_parameters: InputParameters


class ConfidenceIntervalOption(BaseModel):
    label: str
    value: float


class MonteCarloSelectedFilter(BaseModel):
    brand: str
    confidence_interval: float
    n_iterations: int


class MonteCarloFiltersResponse(BaseModel):
    brands: List[str]
    confidence_interval_options: List[ConfidenceIntervalOption]
    selected_filter: MonteCarloSelectedFilter
