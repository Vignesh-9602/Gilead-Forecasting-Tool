from datetime import datetime
from dateutil.relativedelta import relativedelta
import math


# ======================================================
# PARAMETER ESTIMATION (STABLE)
# ======================================================
def estimate_parameters(values):
    if len(values) < 3:
        return 0.3, 0.1, 0.9

    diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_diff = sum(abs(d) for d in diffs) / len(diffs)
    last_diff = abs(diffs[-1])

    alpha = min(0.9, max(0.1, last_diff / (avg_diff + 1e-6)))
    beta = min(0.5, max(0.05, avg_diff / (max(abs(v) for v in values) + 1e-6)))

    ratio = last_diff / (avg_diff + 1e-6)

    # ✅ Improved damping (more stable)
    gamma = 1 - min(0.5, max(0.0, (ratio - 1) * 0.3))
    gamma = max(0.6, min(0.95, gamma))

    return round(alpha, 2), round(beta, 2), round(gamma, 2)


# ======================================================
# SEASONALITY
# ======================================================
def get_seasonal_period(seasonality):
    if seasonality == "monthly":
        return 12
    if seasonality == "quarterly":
        return 4
    return None


def compute_initial_seasonality(values, period):
    if len(values) < 2 * period:
        return None  # insufficient data

    seasonals = {}
    n_seasons = len(values) // period

    season_averages = [
        sum(values[period*j:period*j+period]) / period
        for j in range(n_seasons)
    ]

    for i in range(period):
        offsets = [
            values[period*j + i] - season_averages[j]
            for j in range(n_seasons)
        ]
        seasonals[i] = sum(offsets) / len(offsets)

    return seasonals


# ======================================================
# HOLT-WINTERS
# ======================================================
def forecast_series(
    values,
    forecast_periods,
    alpha,
    beta,
    gamma,
    seasonality,
    metric
):
    n = len(values)

    level = values[0]
    trend = (values[-1] - values[0]) / (n - 1)

    seasonal_period = get_seasonal_period(seasonality)

    if seasonal_period:
        seasonals = compute_initial_seasonality(values, seasonal_period)
        if not seasonals:
            seasonal_period = None
    else:
        seasonals = None

    season_alpha = 0.2

    # -------- FIT --------
    for i in range(n):
        val = values[i]
        seasonal = seasonals[i % seasonal_period] if seasonal_period else 0

        prev_level = level

        level = alpha * (val - seasonal) + (1 - alpha) * (level + gamma * trend)

        trend = beta * (level - prev_level) + (1 - beta) * (gamma * trend)

        if seasonal_period:
            seasonals[i % seasonal_period] = (
                season_alpha * (val - level)
                + (1 - season_alpha) * seasonal
            )

    # -------- FORECAST --------
    forecast = []

    for m in range(1, forecast_periods + 1):

        if gamma == 1:
            damped_trend = trend * m
        else:
            damped_trend = trend * ((1 - gamma**m) / (1 - gamma))

        seasonal = (
            seasonals[(n + m - 1) % seasonal_period]
            if seasonal_period else 0
        )

        value = level + damped_trend + seasonal

        if metric == "market_share":
            value = max(min(value, 100), 0)
        else:
            value = max(value, 0)

        forecast.append(round(value, 2))

    return forecast


# ======================================================
# MULTIPLIER + TRAJECTORY
# ======================================================
def apply_multiplier_and_trajectory(
    forecast_months,
    forecast_values,
    multiplier,
    growth_type,
    total_growth_pct,
    duration,
    trajectory_start,
    metric
):
    adjusted = []

    duration = max(1, duration)  # ✅ safety
    growth_factor = total_growth_pct / 100 if total_growth_pct else 0

    start_dt = datetime.fromisoformat(trajectory_start) if trajectory_start else None
    denominator = math.log(duration + 1) if duration > 1 else 1

    growth_index = 0

    for month_str, val in zip(forecast_months, forecast_values):

        value = val * multiplier
        current_dt = datetime.fromisoformat(month_str)

        if not start_dt or current_dt < start_dt:
            pass
        else:
            growth_index += 1
            t = growth_index

            if growth_type == "linear":
                factor = 1 + (growth_factor * t / duration)
            elif growth_type == "exponential":
                factor = (1 + growth_factor) ** (t / duration)
            elif growth_type == "logarithmic":
                factor = 1 + growth_factor * (math.log(t + 1) / denominator)
            else:
                factor = 1

            value = value * factor

        # ✅ FINAL constraint AFTER growth
        if metric == "market_share":
            value = max(min(value, 100), 0)
        else:
            value = max(value, 0)

        adjusted.append(round(value, 2))

    return adjusted


# ======================================================
# MAIN
# ======================================================

def process_forecast(
    series_months,
    series_values,
    train_start_date,
    train_end_date,
    forecast_periods,
    multiplier=1.0,
    multiplier_horizon="Forecast",   # ✅ UI NAMING
    override_params=None,
    seasonality="none",
    metric="nps",
    growth_type=None,
    total_growth_pct=0,
    growth_duration=None,
    trajectory_start=None
):
    # ------------------------------------------------------
    # Normalize train dates
    # ------------------------------------------------------
    train_start = (
        datetime.fromisoformat(train_start_date).replace(day=1)
        if isinstance(train_start_date, str)
        else train_start_date.replace(day=1)
    )

    train_end = (
        datetime.fromisoformat(train_end_date).replace(day=1)
        if isinstance(train_end_date, str)
        else train_end_date.replace(day=1)
    )

    train_months, train_values = [], []

    for m, v in zip(series_months, series_values):
        d = datetime.fromisoformat(m)
        if train_start <= d <= train_end:
            train_months.append(m)
            train_values.append(v)

    if len(train_values) < 3:
        raise ValueError("Insufficient training data")

    # ------------------------------------------------------
    # ETS parameter estimation / override
    # ------------------------------------------------------
    if override_params:
        alpha = override_params.get("alpha")
        beta = override_params.get("beta")
        gamma = override_params.get("gamma")
    else:
        alpha, beta, gamma = estimate_parameters(train_values)

    # ------------------------------------------------------
    # FORECAST (ETS)
    # ------------------------------------------------------
    forecast_values = forecast_series(
        train_values,
        forecast_periods,
        alpha,
        beta,
        gamma,
        seasonality,
        metric
    )

    last_train_month = datetime.fromisoformat(train_months[-1])

    forecast_months = [
        (last_train_month + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(1, forecast_periods + 1)
    ]

    # ------------------------------------------------------
    # APPLY MULTIPLIER + TRAJECTORY TO FORECAST (IF NEEDED)
    # ------------------------------------------------------
    mh = (multiplier_horizon or "Forecast").strip().lower()

    apply_to_history = mh == "history" or mh == "both history & forecast"
    apply_to_forecast = mh == "forecast" or mh == "both history & forecast"

    if apply_to_forecast:
        forecast_values = apply_multiplier_and_trajectory(
            forecast_months,
            forecast_values,
            multiplier,
            growth_type,
            total_growth_pct,
            growth_duration or forecast_periods,
            trajectory_start,
            metric
        )

    # ------------------------------------------------------
    # APPLY MULTIPLIER TO HISTORY (POST‑MODEL)
    # ------------------------------------------------------
    if apply_to_history and multiplier != 1.0:
        train_values = [round(v * multiplier, 2) for v in train_values]

        if metric == "market_share":
            train_values = [max(min(v, 100), 0) for v in train_values]
        else:
            train_values = [max(v, 0) for v in train_values]

    # ------------------------------------------------------
    # FINAL OUTPUT
    # ------------------------------------------------------
    return {
        "months": train_months + forecast_months,
        "train_values": train_values,
        "forecast_values": forecast_values,
        "forecast_start_index": len(train_values),
        "factors": {
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "seasonality": seasonality,
            "multiplier": multiplier,
            "multiplier_horizon": multiplier_horizon,  # ✅ UI VALUE PRESERVED
            "growth_type": growth_type,
            "growth_pct": total_growth_pct,
            "trajectory_start": trajectory_start
        }
    }

# ======================================================
# MAIN Forecast for all indication 
# ======================================================

def generate_full_base_forecast(
    metrics,
    config,
    metric,
    train_start,
    train_end
):
    """
    Generates base forecast series and factor map.

    Returns:
    {
        months: [...],
        forecast_start_index: int,
        series: [
            {
                key,
                lot,
                label,
                train_values,
                forecast_values,
                display
            }
        ],
        factors_map: {
            (indication, lot) OR (indication, lot, product): factors
        }
    }
    """

    series_list = []
    factors_map = {}
    months = None
    forecast_start_index = None

    # Stable iteration order
    for key, data in sorted(metrics.items(), key=lambda x: x[0]):
        parts = key.split("-")

        # -----------------------------
        # DISPLAY VALUES (SOURCE OF TRUTH)
        # -----------------------------
        display_indication = data["display"]["indication"]   # e.g. mTNBC (or code equivalent)
        display_lot = data["display"]["lot"]                 # e.g. 1L

        # -----------------------------
        # NPS
        # -----------------------------
        if metric == "nps":

            if len(parts) != 2:
                continue

            series_values = data.get("nps", [])
            if not series_values or len(series_values) < 3:
                continue

            label = "NPS"

            # ✅ FACTOR KEY
            factor_key = (display_indication, display_lot)

        # -----------------------------
        # MARKET SHARE
        # -----------------------------
        else:
            if len(parts) != 3:
                continue

            display_product = data["display"]["brand"]       # canonical brand
            series_values = data.get("market_share", [])

            if not series_values or len(series_values) < 3:
                continue

            label = display_product

            # ✅ FACTOR KEY
            factor_key = (display_indication, display_lot, display_product)

        # -----------------------------
        # FORECAST
        # -----------------------------
        row = process_forecast(
            data["month"],
            series_values,
            train_start,
            train_end,
            config["forecast_periods"],
            metric=metric
        )

        # Capture shared timeline once
        if months is None:
            months = row["months"]
            forecast_start_index = row["forecast_start_index"]

        # -----------------------------
        # SERIES OUTPUT
        # -----------------------------
        series_list.append({
            "key": key,
            "lot": display_lot,
            "label": label,
            "train_values": row["train_values"],
            "forecast_values": row["forecast_values"],
            "display": {
                "indication": display_indication,
                "lot": display_lot,
                "product": label if metric == "market_share" else None
            }
        })

        # -----------------------------
        # FACTORS
        # -----------------------------
        start_idx = row["forecast_start_index"]
        trajectory_start = (
            row["months"][start_idx]
            if start_idx < len(row["months"])
            else None
        )

        factors_map[factor_key] = {
            "multiplier": 1.0,
            "ets": {
                "alpha": row["factors"]["alpha"],
                "beta": row["factors"]["beta"],
                "gamma": row["factors"]["gamma"],
                "seasonality": row["factors"]["seasonality"],
            },
            "trajectory": {
                "growth_type": "linear",
                "total_growth": 0,
                "duration": config["forecast_periods"],
                "trajectory_start": trajectory_start,
            }
        }

    if not series_list:
        raise ValueError("No valid series found for base forecast")

    return {
        "months": months,
        "forecast_start_index": forecast_start_index,
        "series": series_list,
        "factors_map": factors_map
    }