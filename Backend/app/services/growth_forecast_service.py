from datetime import datetime
from dateutil.relativedelta import relativedelta
import math


# ======================================================
# CORE GROWTH MODELS (UNCHANGED)
# ======================================================
def growth_forecast(values, forecast_periods, growth_type, metric):
    n = len(values)
    x = list(range(n))

    # -------------------------------
    # LINEAR: y = a + b*x
    # -------------------------------
    if growth_type == "linear":
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
        den = sum((xi - x_mean) ** 2 for xi in x)

        b = num / (den + 1e-6)
        a = y_mean - b * x_mean

        forecast = [a + b * (n + i) for i in range(1, forecast_periods + 1)]

    # -------------------------------
    # EXPONENTIAL: y = a * e^(b*x)
    # -------------------------------
    elif growth_type == "exponential":
        log_values = [math.log(v + 1e-6) for v in values]

        x_mean = sum(x) / n
        y_mean = sum(log_values) / n

        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, log_values))
        den = sum((xi - x_mean) ** 2 for xi in x)

        b = num / (den + 1e-6)
        a = math.exp(y_mean - b * x_mean)

        forecast = [a * math.exp(b * (n + i)) for i in range(1, forecast_periods + 1)]

    # -------------------------------
    # LOGARITHMIC: y = a + b*log(x)
    # -------------------------------
    elif growth_type == "logarithmic":
        x_log = [math.log(i + 1) for i in x]

        x_mean = sum(x_log) / n
        y_mean = sum(values) / n

        num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x_log, values))
        den = sum((xi - x_mean) ** 2 for xi in x_log)

        b = num / (den + 1e-6)
        a = y_mean - b * x_mean

        forecast = [a + b * math.log(n + i) for i in range(1, forecast_periods + 1)]

    else:
        raise ValueError("Unsupported growth type")

    # -------------------------------
    # CLIPPING
    # -------------------------------
    final_forecast = []
    for val in forecast:
        if metric == "market_share":
            val = max(min(val, 100), 0)
        else:
            val = max(val, 0)

        final_forecast.append(round(val, 2))

    return final_forecast


# ======================================================
# MAIN ENTRY (WITH GROWTH CONTROL)
# ======================================================
def process_growth_forecast(
    series_months,
    series_values,
    train_start_date,
    train_end_date,
    forecast_periods,
    multiplier,
    total_growth,
    duration,
    growth_type="linear",
    metric="nps"
):

    # --------------------------------
    # Use input directly
    # --------------------------------
    train_months = list(series_months)
    train_values = list(series_values)

    if len(train_values) < 2:
        raise ValueError("Insufficient training data")

    # --------------------------------
    # Apply multiplier
    # --------------------------------
    train_values = [round(v * multiplier, 2) for v in train_values]

    # --------------------------------
    # STEP 1: RAW MODEL FORECAST
    # --------------------------------
    raw_forecast = growth_forecast(
        train_values,
        duration,                     # ✅ use duration
        growth_type.lower(),
        metric
    )

    # --------------------------------
    # STEP 2: APPLY TOTAL GROWTH %
    # --------------------------------
    last_value = train_values[-1]
    target_value = last_value * (1 + total_growth / 100)

    model_end_value = raw_forecast[-1] if raw_forecast else last_value
    scale_factor = target_value / (model_end_value + 1e-6)

    forecast_values = [round(v * scale_factor, 2) for v in raw_forecast]

    # --------------------------------
    # STEP 3: CLIP AGAIN (safety)
    # --------------------------------
    final_forecast = []
    for val in forecast_values:
        if metric == "market_share":
            val = max(min(val, 100), 0)
        else:
            val = max(val, 0)

        final_forecast.append(val)

    # --------------------------------
    # FUTURE MONTHS
    # --------------------------------
    last_train_month = datetime.fromisoformat(train_months[-1])
    forecast_months = [
        (last_train_month + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(1, duration + 1)
    ]

    chart_months = train_months + forecast_months

    # --------------------------------
    # FINAL RESPONSE
    # --------------------------------
    return {
        "months": chart_months,
        "train_values": train_values,
        "forecast_values": final_forecast,
        "forecast_start_index": len(train_months),
        "factors": {
            "trajectory": {
            "growth_type": growth_type,
            "total_growth": total_growth,
            "duration": duration,
            "multiplier": multiplier
                        }
        }

    }