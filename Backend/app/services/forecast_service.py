from datetime import datetime
from dateutil.relativedelta import relativedelta


# ------------------------------------------------------
# FORECAST ENGINE (ONLY FORECAST, NEVER HISTORY)
# ------------------------------------------------------
def forecast_series(values, months, config):
    """
    values: list[float] -> MUST be a COPY, never original history
    """

    alpha = config.level_alpha
    beta = config.trend_beta
    phi = config.damping_phi
    trend_type = config.trend_type
    forecast_periods = config.forecast_periods

    # ✅ Work only on a local variable
    level = float(values[-1])

    if len(values) >= 2:
        base_trend = values[-1] - values[-2]
    else:
        base_trend = level * 0.02

    trend = base_trend

    # ✅ Safe date parsing
    last_month = datetime.fromisoformat(months[-1])

    forecast = {}

    for k in range(1, forecast_periods + 1):

        # ----- Trend evolution (FORECAST ONLY) -----
        if trend_type != "none":
            trend = beta * base_trend + (1 - beta) * trend
            effective_trend = (phi ** k) * trend
        else:
            effective_trend = 0.0

        # ----- Level update (FORECAST ONLY) -----
        if trend_type == "additive":
            level = level + alpha * effective_trend
        elif trend_type == "multiplicative":
            level = level * (1 + alpha * effective_trend)

        next_month = last_month + relativedelta(months=k)

        forecast[next_month.strftime("%Y-%m-%d")] = round(level, 2)

    return forecast


# ------------------------------------------------------
# MAIN DISPATCHER
# ------------------------------------------------------
def process_forecast(metrics: dict, entity_key: str, config):
    """
    ✅ History is frozen
    ✅ Forecast uses a COPY
    """

    data = metrics.get(entity_key)
    if not data:
        raise ValueError(f"Selected entity not found: {entity_key}")

    months = data["month"]
    raw_values = data["market_share"] if "market_share" in data else data["nps"]

    # --------------------------------------------------
    # ✅ STEP 1: APPLY SCENARIO MULTIPLIER TO HISTORY ONLY
    # --------------------------------------------------
    scenario_multiplier = config.scenario_multiplier

    adjusted_history_values = [
        round(v * scenario_multiplier, 2)
        for v in raw_values
    ]

    # ✅ Freeze history
    history = dict(zip(months, adjusted_history_values))

    # --------------------------------------------------
    # ✅ STEP 2: FORECAST ON A COPY (CRITICAL FIX)
    # --------------------------------------------------
    forecast_input = adjusted_history_values.copy()   # 🔥 IMPORTANT

    forecast = forecast_series(
        forecast_input,
        months,
        config
    )

    return {
        "entity": entity_key,
        "history": history,
        "forecast": forecast,
        "parameters": {
            "scenario_multiplier": scenario_multiplier,
            "trend_type": config.trend_type,
            "alpha": config.level_alpha,
            "beta": config.trend_beta,
            "phi": config.damping_phi
        }
    }