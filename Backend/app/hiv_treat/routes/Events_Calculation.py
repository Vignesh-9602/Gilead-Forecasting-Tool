"""Market / Product / Overall Event Curve Engine.

Event Curve x Coverage Curve = Final Event Curve, applied to the selected
entity and redistributed to impacted entities by weight.

`event_scope` is what tells us which calculation to run -- product_event
and market_event both just mean "one selected entity, one context
dimension, optional redistribution to impacted entities"; only the
*meaning* of "entity" and "context" changes:

    product_event: selected_entity = product,  context = market
    market_event:  selected_entity = market,   context = product
    overall_event: no entity, no context -- portfolio-level only

NOTE: This module is pure calculation -- schemas + curve math only. It has
no FastAPI router of its own. The only API route in this system is
POST /api/events/run-calculation (see run_calculation.py), which imports
compute_event_forecast() from here and does everything else: DB fetch,
laying the curve onto the baseline, grid/hierarchy building, write-back,
and shaping the full multi-tab response the FE needs. A standalone
"/forecast" endpoint that only returned the curve math (with no DB
baseline, no persistence, no tab response) would just be a subset of what
run-calculation already returns, so it's been removed rather than kept as
a second route.
"""

from __future__ import annotations

import math
from datetime import date
from enum import Enum
from typing import Dict, List, Optional

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field, model_validator


# ======================================================
# SCHEMA
# ======================================================

class CurveType(str, Enum):
    LINEAR = "Linear"
    SCURVE = "SCurve"
    EXPONENTIAL = "Exponential"
    LOGARITHMIC = "Logarithmic"


class EventScope(str, Enum):
    PRODUCT_EVENT = "product_event"
    MARKET_EVENT = "market_event"
    OVERALL_EVENT = "overall_event"


class CoverageInput(BaseModel):
    """Nested under `coverage`, so no "coverage_" prefix needed on the fields
    themselves."""
    curve_type: CurveType
    factor: float = 1.0
    peak_pct: float = Field(..., ge=0, le=100)
    peak_months: int = Field(..., ge=1)


class ImpactedEntity(BaseModel):
    """A product (for product_event) or market (for market_event) that
    loses share/volume to the selected entity's gain, weighted by `weight`."""
    name: str
    weight: float = Field(..., ge=0, le=100)


WEIGHT_SUM_TOLERANCE = 0.01


class EventInput(BaseModel):
    event_name: str
    event_scope: EventScope
    scenario_name: str
    ta_name: str = "HIV Treatment"

    # product_event: context = market, selected_entity = product
    # market_event:  context = product, selected_entity = market
    # overall_event: both left unset
    contexts: Optional[List[str]] = None
    selected_entity: Optional[str] = None

    # Shared curve fields
    start_date: date
    peak_pct: float = Field(..., ge=-100, le=100)
    duration_months: int = Field(..., ge=1)
    curve_type: CurveType
    factor: float = 1.0

    coverage: Optional[CoverageInput] = None
    impacted_entities: Optional[List[ImpactedEntity]] = None

    @model_validator(mode="after")
    def _validate_scope_fields(self) -> "EventInput":
        if self.event_scope == EventScope.OVERALL_EVENT:
            if self.contexts is not None or self.selected_entity is not None:
                raise ValueError("overall_event takes no contexts/selected_entity.")
            if self.impacted_entities is not None:
                raise ValueError("overall_event has no redistribution.")
        else:
            if not self.contexts:
                raise ValueError(f"contexts is required for a {self.event_scope.value}.")
            if not self.selected_entity:
                raise ValueError(f"selected_entity is required for a {self.event_scope.value}.")
        return self

    @model_validator(mode="after")
    def _validate_redistribution_weights(self) -> "EventInput":
        entities = self.impacted_entities
        if entities is None:
            return self

        if len(entities) == 0:
            raise ValueError("impacted_entities was provided but is empty.")

        total_weight = sum(e.weight for e in entities)
        if abs(total_weight - 100.0) > WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"impacted_entities weights must sum to 100 (got {total_weight}).")

        names = [e.name for e in entities]
        if len(set(names)) != len(names):
            raise ValueError("impacted_entities contains duplicate entries.")
        if self.selected_entity in names:
            raise ValueError(f"Selected entity '{self.selected_entity}' cannot also be impacted.")

        return self


class EventForecastResult(BaseModel):
    event_name: str
    selected_entity: Optional[str] = None
    months: List[str]
    base_curve: List[float]
    coverage_curve: Optional[List[float]] = None
    final_curve: List[float]
    selected_curve: List[float] = Field(default_factory=list)
    impacted_curves: Optional[Dict[str, List[float]]] = None


# ======================================================
# CURVE ENGINE
# ======================================================

def _normalized_curve(start: float, peak: float, periods: int,
                       curve_type: CurveType, factor: float) -> List[float]:
    if periods <= 0:
        return []

    factor = factor if factor and factor > 0 else 1.0
    values: List[float] = []

    for i in range(1, periods + 1):
        t = i / periods

        if curve_type == CurveType.LINEAR:
            shaped_t = t ** factor

        elif curve_type == CurveType.SCURVE:
            k = factor
            def _logistic(tt: float) -> float:
                return 1 / (1 + math.exp(-k * (tt - 0.5)))
            lo, hi = _logistic(0.0), _logistic(1.0)
            shaped_t = (_logistic(t) - lo) / (hi - lo + 1e-9)

        elif curve_type == CurveType.EXPONENTIAL:
            k = factor
            shaped_t = (math.exp(k * t) - 1) / (math.exp(k) - 1 + 1e-9)

        elif curve_type == CurveType.LOGARITHMIC:
            k = factor
            shaped_t = math.log(1 + k * t) / (math.log(1 + k) + 1e-9)

        else:
            raise ValueError(f"Unsupported curve type: {curve_type}")

        values.append(round(start + (peak - start) * shaped_t, 4))

    return values


def _extend_and_hold(curve: List[float], target_length: int) -> List[float]:
    if len(curve) >= target_length:
        return curve[:target_length]
    hold_value = curve[-1] if curve else 0.0
    return curve + [hold_value] * (target_length - len(curve))


def build_event_curve(event: EventInput) -> List[float]:
    return _normalized_curve(0.0, event.peak_pct, event.duration_months, event.curve_type, event.factor)


def build_coverage_curve(event: EventInput) -> List[float]:
    coverage = event.coverage
    raw = _normalized_curve(0.0, coverage.peak_pct, coverage.peak_months, coverage.curve_type, coverage.factor)
    return _extend_and_hold(raw, event.duration_months)


def apply_coverage(base_curve: List[float], coverage_curve: List[float]) -> List[float]:
    return [round(b * (c / 100.0), 4) for b, c in zip(base_curve, coverage_curve)]


def build_month_labels(start_date: date, duration_months: int) -> List[str]:
    return [(start_date + relativedelta(months=i)).strftime("%Y-%m-%d") for i in range(duration_months)]


# ======================================================
# REDISTRIBUTION
# ======================================================

def build_redistribution_curves(
    selected_curve: List[float],
    impacted_entities: Optional[List[ImpactedEntity]],
) -> Optional[Dict[str, List[float]]]:
    if not impacted_entities:
        return None
    return {
        e.name: [round(-v * (e.weight / 100.0), 4) for v in selected_curve]
        for e in impacted_entities
    }

def build_event_curve(event: EventInput, baseline_pct: float = 0.0) -> List[float]:
    """
    Absolute share curve for the selected entity: ramps from baseline_pct
    up to event.peak_pct following the chosen shape. The caller applies
    this by SETTING the entity's forecast to these values directly (not
    adding), so it lands exactly on peak_pct and holds there flat --
    baseline drift in the underlying forecast no longer leaks in.
    overall_event has no baseline concept; leave baseline_pct at 0.0.
    """
    return _normalized_curve(baseline_pct, event.peak_pct, event.duration_months,
                              event.curve_type, event.factor)


def compute_event_forecast(event: EventInput, baseline_pct: float = 0.0) -> EventForecastResult:
    base_curve = build_event_curve(event, baseline_pct=baseline_pct)
    coverage_curve = build_coverage_curve(event) if event.coverage else None

    # Only the event's incremental effect (delta from baseline) should be
    # gated by coverage -- not the entity's existing baseline share.
    delta_curve = [round(v - baseline_pct, 4) for v in base_curve]

    if coverage_curve:
        adjusted_delta = [round(d * (c / 100.0), 4) for d, c in zip(delta_curve, coverage_curve)]
    else:
        adjusted_delta = delta_curve

    final_curve = [round(baseline_pct + d, 4) for d in adjusted_delta]

    # impacted/sibling entities still redistribute off the same delta
    impacted_curves = build_redistribution_curves(adjusted_delta, event.impacted_entities)

    return EventForecastResult(
        event_name=event.event_name,
        selected_entity=event.selected_entity,
        months=build_month_labels(event.start_date, event.duration_months),
        base_curve=base_curve,
        coverage_curve=coverage_curve,
        final_curve=final_curve,
        selected_curve=final_curve,
        impacted_curves=impacted_curves,
    )
