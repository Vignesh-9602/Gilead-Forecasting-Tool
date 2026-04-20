from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict


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
    beta = min(0.5, max(0.05, avg_diff / (max(values) + 1e-6)))
    gamma = 0.9 if last_diff > avg_diff else 1.0  # damping φ

    return round(alpha, 2), round(beta, 2), round(gamma, 2)


# ======================================================
# SEASONALITY HELPERS
# ======================================================
def get_seasonal_period(seasonality):
    if seasonality == "monthly":
        return 12
    if seasonality == "quarterly":
        return 4
    return None


def compute_initial_seasonality(values, period):
    seasonals = {}
    n_seasons = len(values) // period

    season_averages = []
    for j in range(n_seasons):
        season_avg = sum(values[period * j: period * j + period]) / period
        season_averages.append(season_avg)

    for i in range(period):
        vals = []
        for j in range(n_seasons):
            vals.append(values[period * j + i] - season_averages[j])
        seasonals[i] = sum(vals) / len(vals)

    return seasonals


# ======================================================
# HOLT-WINTERS FORECAST
# ======================================================
def forecast_series(
    values,
    forecast_periods,
    alpha,
    beta,
    gamma,   # damping φ
    trend_type,
    seasonality,
    metric
):
    n = len(values)

    level = values[0]
    trend = values[1] - values[0]

    seasonal_period = get_seasonal_period(seasonality)
    seasonals = {}

    if seasonal_period and len(values) >= seasonal_period:
        seasonals = compute_initial_seasonality(values, seasonal_period)
    else:
        seasonal_period = None

    # smoothing for seasonality (fixed internally)
    season_alpha = 0.2

    # -------------------------------
    # FIT MODEL
    # -------------------------------
    for i in range(n):
        val = values[i]

        if seasonal_period:
            seasonal = seasonals[i % seasonal_period]
        else:
            seasonal = 0

        prev_level = level

        # Level update
        level = alpha * (val - seasonal) + (1 - alpha) * (level + gamma * trend)

        # Trend update
        trend = beta * (level - prev_level) + (1 - beta) * (gamma * trend)

        # Seasonality update
        if seasonal_period:
            seasonals[i % seasonal_period] = (
                season_alpha * (val - level)
                + (1 - season_alpha) * seasonal
            )

    # -------------------------------
    # FORECAST
    # -------------------------------
    forecast = []

    for m in range(1, forecast_periods + 1):

        # Damped trend sum
        if gamma == 1:
            damped_trend = trend * m
        else:
            damped_trend = trend * ((1 - gamma**m) / (1 - gamma))

        if seasonal_period:
            seasonal = seasonals[(n + m - 1) % seasonal_period]
        else:
            seasonal = 0

        value = level + damped_trend + seasonal

        # Domain constraints
        if metric == "market_share":
            value = max(min(value, 100), 0)
        else:
            value = max(value, 0)

        forecast.append(round(value, 2))

    return forecast


from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict


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
    beta = min(0.5, max(0.05, avg_diff / (max(values) + 1e-6)))
    gamma = 0.9 if last_diff > avg_diff else 1.0  # damping φ

    return round(alpha, 2), round(beta, 2), round(gamma, 2)


# ======================================================
# SEASONALITY HELPERS
# ======================================================
def get_seasonal_period(seasonality):
    if seasonality == "monthly":
        return 12
    if seasonality == "quarterly":
        return 4
    return None


def compute_initial_seasonality(values, period):
    seasonals = {}
    n_seasons = len(values) // period

    season_averages = []
    for j in range(n_seasons):
        season_avg = sum(values[period * j: period * j + period]) / period
        season_averages.append(season_avg)

    for i in range(period):
        vals = []
        for j in range(n_seasons):
            vals.append(values[period * j + i] - season_averages[j])
        seasonals[i] = sum(vals) / len(vals)

    return seasonals


# ======================================================
# HOLT-WINTERS FORECAST
# ======================================================
def forecast_series(
    values,
    forecast_periods,
    alpha,
    beta,
    gamma,   # damping φ
    trend_type,
    seasonality,
    metric
):
    n = len(values)

    level = values[0]
    trend = values[1] - values[0]

    seasonal_period = get_seasonal_period(seasonality)
    seasonals = {}

    if seasonal_period and len(values) >= seasonal_period:
        seasonals = compute_initial_seasonality(values, seasonal_period)
    else:
        seasonal_period = None

    # smoothing for seasonality (fixed internally)
    season_alpha = 0.2

    # -------------------------------
    # FIT MODEL
    # -------------------------------
    for i in range(n):
        val = values[i]

        if seasonal_period:
            seasonal = seasonals[i % seasonal_period]
        else:
            seasonal = 0

        prev_level = level

        # Level update
        level = alpha * (val - seasonal) + (1 - alpha) * (level + gamma * trend)

        # Trend update
        trend = beta * (level - prev_level) + (1 - beta) * (gamma * trend)

        # Seasonality update
        if seasonal_period:
            seasonals[i % seasonal_period] = (
                season_alpha * (val - level)
                + (1 - season_alpha) * seasonal
            )

    # -------------------------------
    # FORECAST
    # -------------------------------
    forecast = []

    for m in range(1, forecast_periods + 1):

        # Damped trend sum
        if gamma == 1:
            damped_trend = trend * m
        else:
            damped_trend = trend * ((1 - gamma**m) / (1 - gamma))

        if seasonal_period:
            seasonal = seasonals[(n + m - 1) % seasonal_period]
        else:
            seasonal = 0

        value = level + damped_trend + seasonal

        # Domain constraints
        if metric == "market_share":
            value = max(min(value, 100), 0)
        else:
            value = max(value, 0)

        forecast.append(round(value, 2))

    return forecast


# ======================================================
# MAIN ENTRY POINT
# ======================================================
def process_forecast(
    series_months,        # e.g. ["2023-01-01", "2023-02-01", ...]
    series_values,
    train_start_date,     # e.g. "2023-01-03"
    train_end_date,       # e.g. "2024-12-04"
    forecast_periods,
    multiplier,
    override_params=None,
    trend_type_override="additive",
    seasonality="none",
    metric="nps"
):
    """
    ✅ Month-based slicing using (YYYY, MM)
    ✅ Never drops existing monthly data
    ✅ Includes Jan-2023 correctly
    """

    # --------------------------------------------------
    # ✅ Convert train bounds to (YEAR, MONTH)
    # --------------------------------------------------
    train_start_dt = datetime.fromisoformat(train_start_date)
    train_end_dt = datetime.fromisoformat(train_end_date)

    train_start_key = (train_start_dt.year, train_start_dt.month)
    train_end_key = (train_end_dt.year, train_end_dt.month)

    # --------------------------------------------------
    # ✅ Slice training window BY MONTH KEY
    # --------------------------------------------------
    train_months = []
    train_values = []

    for m, v in zip(series_months, series_values):
        d = datetime.fromisoformat(m)
        data_key = (d.year, d.month)

        if train_start_key <= data_key <= train_end_key:
            train_months.append(m)
            train_values.append(v)

    if len(train_values) < 3:
        raise ValueError("Insufficient training history")

    # --------------------------------------------------
    # ✅ Apply multiplier
    # --------------------------------------------------
    train_values = [round(v * multiplier, 2) for v in train_values]

    # --------------------------------------------------
    # ✅ Parameters
    # --------------------------------------------------
    if override_params:
        alpha = override_params["alpha"]
        beta = override_params["beta"]
        gamma = override_params["gamma"]
    else:
        alpha, beta, gamma = estimate_parameters(train_values)

    # --------------------------------------------------
    # ✅ Forecast values
    # --------------------------------------------------
    forecast_values = forecast_series(
        train_values,
        forecast_periods,
        alpha,
        beta,
        gamma,
        trend_type_override,
        seasonality,
        metric
    )

    # --------------------------------------------------
    # ✅ Forecast months (start AFTER last train month)
    # --------------------------------------------------
    last_train_month = datetime.fromisoformat(train_months[-1])

    forecast_months = [
        (last_train_month + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(1, forecast_periods + 1)
    ]

    chart_months = train_months + forecast_months

    return {
        "months": chart_months,
        "train_values": train_values,
        "forecast_values": forecast_values,
        "forecast_start_index": len(train_values),
        "factors": {
            "multiplier": multiplier,
            "alpha": alpha,
            "beta": beta,
            "gamma": gamma,
            "trend_type": trend_type_override,
            "seasonality": seasonality
        }
    }