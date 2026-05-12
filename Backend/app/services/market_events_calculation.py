import math
from typing import List, Optional


def clamp_k(k: Optional[float]) -> float:
    return 1.0 if k is None else max(min(float(k), 10.0), 0.1)


def exp_progress(progress: float, k: float) -> float:
    num = math.expm1(k * progress)
    den = math.expm1(k)

    if abs(den) < 1e-12:
        return progress

    return num / den


def generate_market_event_impact_percent(
    forecast_periods: int,
    peak_percent: float,
    duration: int,
    curve_type: str,
    k: Optional[float] = None
) -> List[float]:

    forecast_periods = max(0, int(forecast_periods))
    duration = max(1, int(duration))
    curve_type = curve_type.lower().strip().replace("-", "_")

    results: List[float] = []
    peak_growth = peak_percent / 100.0
    k_eff = clamp_k(k)

    for t in range(1, forecast_periods + 1):

        if t > duration:
            results.append(round(peak_percent, 2))
            continue

        progress = t / duration

        if curve_type == "linear":
            impact = peak_growth * progress

        elif curve_type == "exponential":
            sign = 1.0 if peak_growth >= 0 else -1.0
            mag = abs(peak_growth)
            s = exp_progress(progress, k_eff)
            impact = sign * mag * s

        elif curve_type == "logarithmic":
            denom = max(math.log(1.0 + k_eff * duration), 1e-12)
            s = math.log(1.0 + k_eff * t) / denom
            impact = peak_growth * s

        elif curve_type in ["scurve"]:
            t0 = duration / 2.0

            def logistic(x: float) -> float:
                return 1.0 / (1.0 + math.exp(-k_eff * (x - t0)))

            f0 = logistic(0.0)
            fD = logistic(float(duration))
            denom = fD - f0

            if abs(denom) < 1e-9:
                impact = peak_growth * progress
            else:
                s = (logistic(float(t)) - f0) / denom
                impact = peak_growth * s

        else:
            raise ValueError(
                "Invalid curve_type. Allowed values: linear, exponential, logarithmic, scurve"
            )

        results.append(round(impact * 100.0, 2))

    return results