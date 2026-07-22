# ---------------------------------------------------------------------------
# Pure utility functions for building chart and table data structures.
# No DB calls here — these take already-fetched data and transform it.
# ---------------------------------------------------------------------------

from app.services.forecast_service import estimate_parameters, forecast_ets


def organize_raw_data(raw_rows: list) -> dict:
    """
    Convert flat DB rows into a nested lookup dict.

    Input:  [(year, month, product, payer, volume), ...]
    Output: {(year, month): {product: {payer: volume}}}
    """
    data = {}
    for year, month, product, payer, volume in raw_rows:
        data.setdefault((year, month), {}).setdefault(product, {})[payer] = float(volume or 0)
    return data


def get_volume(data: dict, year: int, month: int,
               product: str = None, payer: str = None) -> float:
    """
    Get volume for a (year, month), optionally narrowed by product and/or payer.
    Returns 0.0 if no data found for that combination.
    """
    ym = data.get((year, month), {})

    if product and payer:
        return ym.get(product, {}).get(payer, 0.0)

    if product:
        return sum(ym.get(product, {}).values())

    if payer:
        return sum(ym.get(p, {}).get(payer, 0.0) for p in ym)

    return sum(v for prod in ym.values() for v in prod.values())


def flat_forecast(history_values: list, window: int = 3) -> float:
    """
    Estimate a flat forecast value by averaging the last few history values.
    Returns the average of the most recent non-zero values, or 0.0 if empty.
    """
    recent = [v for v in history_values[-window:] if v > 0]
    return round(sum(recent) / len(recent), 2) if recent else 0.0


def forecast_fill(history: list, real_forecast: list) -> list:
    """
    Fill in a forecast series given its history and whatever real values are
    already present for the forecast months (0 = missing).

    Real (non-zero) values are kept as-is — e.g. a reshaped saved scenario
    already has real forecast values baked in. Any missing month is filled by
    an ETS forecast fit to `history` — matching how the Liver Model Input
    screen computes its Base forecast (same estimate_parameters/forecast_ets
    from app.services.forecast_service) — falling back to a flat continuation
    (avg of the last 3 history values) when there's fewer than 4 non-zero
    history points to fit ETS on.
    """
    n_forecast = len(real_forecast)
    if n_forecast == 0:
        return []

    hist_vals = [v for v in history if v > 0]
    if len(hist_vals) >= 4:
        alpha, beta, gamma = estimate_parameters(hist_vals)
        fallback = [
            round(float(v), 2) for v in forecast_ets(hist_vals, n_forecast, alpha, beta, gamma, "market_volume")
        ]
    else:
        flat = flat_forecast(history)
        fallback = [flat] * n_forecast

    return [v if v > 0 else fallback[i] for i, v in enumerate(real_forecast)]


def monthly_values(data: dict, month_tuples: list, forecast_start_index: int,
                    product: str = None, payer: str = None) -> list:
    """Raw (unrounded) volume for every month in month_tuples, in order (see forecast_fill)."""
    raw = [get_volume(data, y, m, product, payer) for y, m in month_tuples]
    history = raw[:forecast_start_index]
    return history + forecast_fill(history, raw[forecast_start_index:])


def compute_share(volume: float, total_volume: float) -> float:
    """
    Compute percentage share: volume / total * 100, rounded to 1 decimal place.
    Returns 0.0 if total_volume is zero (avoids division by zero).
    """
    return round(volume / total_volume * 100, 1) if total_volume else 0.0


def to_month_key(year: int, month: int) -> str:
    """
    Format (year, month) as a short 'YYYY-MM' label — used in output_tabs
    chart/table headers (note: no day component, unlike available_months).
    Example: (2026, 5) → '2026-05'
    """
    return f"{year:04d}-{month:02d}"


def aggregate_monthly_to_yearly(month_tuples: list, values: list, forecast_start_index: int) -> tuple:
    """
    Sum monthly values into yearly buckets.

    A year is treated as "forecast" if ANY of its months is in the forecast period.

    Returns (year_labels, yearly_values, yearly_forecast_start_index) where
    yearly_values is the full (history + forecast) list, summed per year.
    """
    yearly_sum = {}
    year_order = []
    year_is_forecast = {}

    for i, (y, m) in enumerate(month_tuples):
        if y not in year_is_forecast:
            year_order.append(y)
            year_is_forecast[y] = False
        yearly_sum[y] = yearly_sum.get(y, 0.0) + values[i]
        if i >= forecast_start_index:
            year_is_forecast[y] = True

    yearly_fsi = next(
        (i for i, y in enumerate(year_order) if year_is_forecast[y]),
        len(year_order)
    )

    year_labels = [str(y) for y in year_order]
    yearly_values = [yearly_sum[y] for y in year_order]
    return year_labels, yearly_values, yearly_fsi


def build_chart(header_key: str, header_values: list,
                forecast_start_index: int, series: list) -> dict:
    """
    Build a chart dict.

    series is a list of (label, values) tuples; values is the full
    (history + forecast) list, split here at forecast_start_index.
    """
    return {
        header_key: header_values,
        "forecast_start_index": forecast_start_index,
        "series": [
            {
                "label": label,
                "history": values[:forecast_start_index],
                "forecast": values[forecast_start_index:],
            }
            for label, values in series
        ],
    }


def build_flat_table(headers: list, rows: list, target_metric: str) -> dict:
    """
    Build a flat (non-hierarchical) table dict.

    rows is a list of (label, values) tuples.
    """
    return {
        "type": "flat",
        "headers": headers,
        "rows": [
            {"label": label, "target_metric": target_metric, "values": values}
            for label, values in rows
        ],
    }


def build_hierarchy_row(label: str, values: list, target_metric: str, children: list = None) -> dict:
    """
    Build one row of a hierarchical table. children is a list of already-built
    row dicts (recursive) — omitted entirely for leaf rows.
    """
    row = {"label": label, "target_metric": target_metric, "values": values}
    if children is not None:
        row["children"] = children
    return row


def build_hierarchy_table(headers: list, rows: list) -> dict:
    """rows is a list of already-built row dicts (see build_hierarchy_row)."""
    return {
        "type": "hierarchy",
        "headers": headers,
        "rows": rows,
    }
