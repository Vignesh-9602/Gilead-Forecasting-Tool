import math
from typing import List, Optional
from datetime import datetime


# ---------------------------------------------------------
# Curve helpers
# ---------------------------------------------------------

def clamp_k(k: Optional[float]) -> float:
    return 1.0 if k is None else max(min(float(k), 10.0), 0.1)


def exp_progress(progress: float, k: float) -> float:
    num = math.expm1(k * progress)
    den = math.expm1(k)

    if abs(den) < 1e-12:
        return progress

    return num / den


# ---------------------------------------------------------
# Date helper
# ---------------------------------------------------------

def get_previous_month(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")

    if dt.month == 1:
        return f"{dt.year - 1}-12-01"

    return f"{dt.year}-{dt.month - 1:02d}-01"


# ---------------------------------------------------------
# Get current share from chart
# ---------------------------------------------------------

def get_current_share_from_chart(
    market_share_chart: dict,
    target_product: str,
    start_date: str
) -> float:

    previous_month = get_previous_month(start_date)

    months = market_share_chart.get("months", [])
    series = market_share_chart.get("series", [])

    if previous_month not in months:
        raise ValueError(
            f"Previous month {previous_month} not found in market share chart"
        )

    month_index = months.index(previous_month)

    tgt = str(target_product).strip().lower()

    for item in series:
        label = item.get("label") or item.get("product") or item.get("brand")
        if label is None:
            continue

        if str(label).strip().lower() != tgt:
            continue

        values = item.get("train_values", []) + item.get("forecast_values", [])

        if month_index >= len(values):
            raise ValueError(
                f"Value missing for {target_product} at {previous_month}"
            )

        return float(values[month_index])

    raise ValueError(
        f"Target product {target_product} not found in market share chart"
    )


# ---------------------------------------------------------
# Generate event path
# ---------------------------------------------------------

def generate_market_event_impact_percent(
    forecast_periods: int,
    peak_percent: float,
    duration: int,
    curve_type: str,
    k: Optional[float] = None,
    current_share: Optional[float] = None,
) -> List[float]:

    forecast_periods = max(0, int(forecast_periods))
    duration = max(1, int(duration))
    curve_type = curve_type.lower().strip().replace("-", "_")

    results: List[float] = []
    k_eff = clamp_k(k)

    peak_growth = float(peak_percent) / 100.0

    start_share = float(current_share) if current_share is not None else None
    target_share = float(peak_percent) if current_share is not None else None

    for t in range(1, forecast_periods + 1):

        if t > duration:
            if current_share is None:
                results.append(round(float(peak_percent), 2))
            else:
                results.append(round(max(0.0, min(100.0, target_share)), 2))
            continue

        progress = t / duration  # keep as-is (start-month moves immediately)

        if curve_type == "linear":
            s = progress

        elif curve_type == "exponential":
            s = exp_progress(progress, k_eff)

        elif curve_type == "logarithmic":
            denom = max(math.log(1.0 + k_eff * duration), 1e-12)
            s = math.log(1.0 + k_eff * t) / denom

        elif curve_type in ["scurve", "s_curve"]:
            t0 = duration / 2.0

            def logistic(x: float) -> float:
                return 1.0 / (1.0 + math.exp(-k_eff * (x - t0)))

            f0 = logistic(0.0)
            fD = logistic(float(duration))
            denom = fD - f0

            if abs(denom) < 1e-9:
                s = progress
            else:
                s = (logistic(float(t)) - f0) / denom

        else:
            raise ValueError(
                "Invalid curve_type. Allowed values: linear, exponential, logarithmic, scurve"
            )

        s = max(0.0, min(1.0, float(s)))

        if current_share is not None:
            desired = start_share + (target_share - start_share) * s
            desired = max(0.0, min(100.0, desired))
            results.append(round(desired, 2))
        else:
            impact = peak_growth * s
            results.append(round(impact * 100.0, 2))

    return results


# ---------------------------------------------------------
# Main function to use in market event logic
# ---------------------------------------------------------

def generate_market_event_share_from_start_date(
    forecast_periods: int,
    peak_percent: float,
    duration: int,
    curve_type: str,
    start_date: str,
    target_product: str,
    market_share_chart: dict,
    k: Optional[float] = None,
) -> List[float]:

    current_share = get_current_share_from_chart(
        market_share_chart=market_share_chart,
        target_product=target_product,
        start_date=start_date
    )

    return generate_market_event_impact_percent(
        forecast_periods=forecast_periods,
        peak_percent=peak_percent,
        duration=duration,
        curve_type=curve_type,
        k=k,
        current_share=current_share
    )