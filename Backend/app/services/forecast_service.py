from datetime import datetime,date
from dateutil.relativedelta import relativedelta
import math


# ======================================================
# HELPERS
# ======================================================
import datetime as dt

def parse_month(s) -> dt.datetime:
    """
    Accepts:
      - dt.datetime / dt.date
      - 'YYYY-MM'
      - 'YYYY-MM-DD'
    Returns: dt.datetime normalized to first day of month.
    """
    if s is None:
        raise ValueError("Empty date value")

    # Already datetime
    if isinstance(s, dt.datetime):
        return s.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Already date
    if isinstance(s, dt.date):
        return dt.datetime(s.year, s.month, 1)

    # Convert everything else to string
    s = str(s).strip()
    if not s:
        raise ValueError("Empty date string")

    if len(s) == 7:  # YYYY-MM
        s = s + "-01"

    d = dt.datetime.fromisoformat(s)
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def clamp_value(value: float, metric: str) -> float:
    if metric == "market_share":
        return max(min(value, 100.0), 0.0)
    return max(value, 0.0)


def apply_multiplier(values, multiplier, metric):
    if multiplier is None or multiplier == 1.0:
        return values

    adjusted = []
    for v in values:
        val = v * multiplier
        val = clamp_value(val, metric)
        adjusted.append(round(val, 2))

    return adjusted


# ======================================================
# PARAMETER ESTIMATION
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
    gamma = 1 - min(0.5, max(0.0, (ratio - 1) * 0.3))
    gamma = max(0.6, min(0.95, gamma))

    return round(alpha, 2), round(beta, 2), round(gamma, 2)


# ======================================================
# SEASONALITY (INTERNAL MONTHLY)
# ======================================================
def compute_initial_seasonality(values, period):
    if len(values) < 2 * period:
        return None

    seasonals = [0.0] * period
    n_seasons = len(values) // period

    season_averages = [
        sum(values[period * j: period * j + period]) / period
        for j in range(n_seasons)
    ]

    for i in range(period):
        offsets = [
            values[period * j + i] - season_averages[j]
            for j in range(n_seasons)
        ]
        seasonals[i] = sum(offsets) / len(offsets)

    return seasonals


# ======================================================
# ETS MODEL
# ======================================================
def forecast_ets(values, forecast_periods, alpha, beta, gamma, metric):
    n = len(values)

    level = values[0]
    trend = sum(values[i] - values[i - 1] for i in range(1, n)) / (n - 1)

    seasonal_period = 12
    seasonals = compute_initial_seasonality(values, seasonal_period)
    if not seasonals:
        seasonal_period = None

    # FIT
    for i in range(n):
        val = values[i]
        seasonal = seasonals[i % seasonal_period] if seasonal_period else 0.0

        prev_level = level

        level = alpha * (val - seasonal) + (1 - alpha) * (level + gamma * trend)
        trend = beta * (level - prev_level) + (1 - beta) * (gamma * trend)

    # FORECAST
    forecast = []
    for m in range(1, forecast_periods + 1):
        if gamma == 1:
            damped_trend = trend * m
        else:
            damped_trend = trend * ((1 - gamma ** m) / (1 - gamma))

        seasonal = seasonals[(n + m - 1) % seasonal_period] if seasonal_period else 0.0

        value = level + damped_trend + seasonal
        value = clamp_value(value, metric)

        forecast.append(round(value, 2))

    return forecast


# ======================================================
# TRAJECTORY MODELS
# ======================================================
def forecast_linear(base_value, forecast_periods, total_growth_pct, duration, metric):
    results = []
    growth = total_growth_pct / 100.0
    duration = max(1, int(duration))

    for t in range(1, forecast_periods + 1):
        t_eff = min(t, duration)
        value = base_value * (1 + growth * (t_eff / duration))
        results.append(round(clamp_value(value, metric), 2))

    return results


def forecast_exponential(base_value, forecast_periods, total_growth_pct, duration, k, metric):
    results = []
    growth = total_growth_pct / 100.0
    duration = max(1, int(duration))

    k = 1.0 if k is None else max(min(float(k), 10.0), 0.1)
    target = max(1.0 + growth, 1e-6)

    for t in range(1, forecast_periods + 1):
        t_eff = min(t, duration)
        exponent = (t_eff / duration) ** k
        value = base_value * (target ** exponent)
        results.append(round(clamp_value(value, metric), 2))

    return results


def forecast_logarithmic(base_value, forecast_periods, total_growth_pct, duration, k, metric):
    results = []
    growth = total_growth_pct / 100.0
    duration = max(1, int(duration))

    k = 1.0 if k is None else max(min(float(k), 10.0), 0.1)
    denom = max(math.log(1.0 + k * duration), 1e-12)

    for t in range(1, forecast_periods + 1):
        t_eff = min(t, duration)
        s = math.log(1.0 + k * t_eff) / denom
        value = base_value * (1.0 + growth * s)
        results.append(round(clamp_value(value, metric), 2))

    return results


def forecast_s_curve(base_value, forecast_periods, total_growth_pct, duration, k, metric):
    results = []
    growth = total_growth_pct / 100.0
    duration = max(1, int(duration))

    k = 1.0 if k is None else max(min(float(k), 10.0), 0.1)

    target = base_value * (1.0 + growth)
    t0 = duration / 2.0

    def logistic(t):
        return 1.0 / (1.0 + math.exp(-k * (t - t0)))

    f0 = logistic(0.0)
    fD = logistic(float(duration))
    denom = fD - f0

    if abs(denom) < 1e-9:
        return forecast_linear(base_value, forecast_periods, total_growth_pct, duration, metric)

    for t in range(1, forecast_periods + 1):
        t_eff = min(t, duration)
        s = (logistic(t_eff) - f0) / denom
        value = base_value + (target - base_value) * s
        results.append(round(clamp_value(value, metric), 2))

    return results


# ======================================================
# MAIN FUNCTION
# ======================================================
def process_forecast(
    series_months,
    series_values,
    train_start_date,
    train_end_date,
    forecast_periods,
    model_type="ETS",
    metric="nps",
    total_growth_pct=0,
    duration=None,
    k=None,
    multiplier=1.0,
    multiplier_horizon="Forecast",
    alpha=None, beta=None, gamma=None
):
    train_start = parse_month(train_start_date)
    train_end = parse_month(train_end_date)

    train_months, train_values = [], []

    for m, v in zip(series_months, series_values):
        d = parse_month(m)
        if train_start <= d <= train_end:
            train_months.append(d.strftime("%Y-%m-%d"))
            train_values.append(float(v))

    if len(train_values) < 3:
        raise ValueError("Insufficient training data")

    forecast_periods = int(forecast_periods)
    if forecast_periods <= 0:
        raise ValueError("forecast_periods must be > 0")

    last_train_month = parse_month(train_months[-1])

    forecast_months = [
        (last_train_month + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(1, forecast_periods + 1)
    ]

    # MULTIPLIER FLAGS
    mh = (multiplier_horizon or "Forecast").lower()
    apply_to_forecast = mh in ("forecast", "both history & forecast")
    apply_to_history = mh in ("history", "both history & forecast")

    # Apply to history BEFORE model
    if apply_to_history:
        train_values = apply_multiplier(train_values, multiplier, metric)

    model_type_l = model_type.lower()

    # MODEL SWITCH
    if model_type_l == "ets":
        if alpha is None or beta is None or gamma is None:
            alpha, beta, gamma = estimate_parameters(train_values)

        forecast_values = forecast_ets(
            train_values,
            forecast_periods,
            alpha,
            beta,
            gamma,
            metric
        )

        factors = {"alpha": alpha, "beta": beta, "gamma": gamma}

    else:
        base_value = train_values[-1]
        duration = forecast_periods if duration is None else max(1, int(duration))

        if model_type_l == "linear":
            forecast_values = forecast_linear(base_value, forecast_periods, total_growth_pct, duration, metric)

        elif model_type_l == "exponential":
            forecast_values = forecast_exponential(base_value, forecast_periods, total_growth_pct, duration, k, metric)

        elif model_type_l == "logarithmic":
            forecast_values = forecast_logarithmic(base_value, forecast_periods, total_growth_pct, duration, k, metric)

        elif model_type_l in ("s_curve", "s-curve", "scurve"):
            forecast_values = forecast_s_curve(base_value, forecast_periods, total_growth_pct, duration, k, metric)

        else:
            raise ValueError("Invalid model_type")

        factors = {
            "model_type": model_type_l,
            "growth_pct": float(total_growth_pct),
            "duration": duration,
            "k": None if k is None else float(k)
        }

    # ✅ Apply to forecast AFTER model
    if apply_to_forecast:
        forecast_values = apply_multiplier(forecast_values, multiplier, metric)

    return {
        "months": train_months + forecast_months,
        "train_values": train_values,
        "forecast_values": forecast_values,
        "forecast_start_index": len(train_values),
        "factors": factors
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
    series_list = []
    factors_map = {}
    months = None
    forecast_start_index = None

    for key, data in sorted(metrics.items(), key=lambda x: x[0]):
        parts = key.split("-")

        display_indication = data["display"]["indication"]
        display_lot = data["display"]["lot"]

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
            factor_key = (display_indication, display_lot)

        # -----------------------------
        # MARKET SHARE
        # -----------------------------
        else:
            if len(parts) != 3:
                continue

            display_product = data["display"]["brand"]
            series_values = data.get("market_share", [])
            if not series_values or len(series_values) < 3:
                continue

            label = display_product
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

        if months is None:
            months = row["months"]
            forecast_start_index = row["forecast_start_index"]

        # -----------------------------
        # SERIES
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
        # FACTORS (FULL MODEL STATE)
        # -----------------------------
        start_idx = row["forecast_start_index"]
        trajectory_start = row["months"][start_idx] if start_idx < len(row["months"]) else None

        ets_f = row.get("factors", {}) or {}
        fp = config["forecast_periods"]

        factors_map[factor_key] = {
            "active_model": "ets",
            "multiplier": 1.0,
            "multiplier_horizon": "Forecast",

            "ets": {
                "alpha": ets_f.get("alpha"),
                "beta": ets_f.get("beta"),
                "gamma": ets_f.get("gamma")
            },

            "linear": {
                "total_growth": 0,
                "duration": fp,
                "trajectory_start": trajectory_start,
            },

            "exponential": {
                "total_growth": 0,
                "duration": fp,
                "trajectory_start": trajectory_start,
                "k_value": 1.0,
            },

            "logarithmic": {
                "total_growth": 0,
                "duration": fp,
                "trajectory_start": trajectory_start,
                "k_value": 1.0,
            },

            "scurve": {
                "total_growth": 0,
                "duration": fp,
                "trajectory_start": trajectory_start,
                "k_value": 1.0,
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