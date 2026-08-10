# ---------------------------------------------------------------------------
# Pure utility functions for building chart and table data structures.
# No DB calls here — these take already-fetched data and transform it.
# ---------------------------------------------------------------------------


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
        # Sum across all products for this specific payer
        return sum(ym.get(p, {}).get(payer, 0.0) for p in ym)

    # No filter → total across all products and payers
    return sum(v for prod in ym.values() for v in prod.values())


def flat_forecast(history_values: list, window: int = 3) -> float:
    """
    Estimate a flat forecast value by averaging the last few history values.
    Returns the average of the most recent non-zero values, or 0.0 if empty.

    Example: flat_forecast([100, 110, 120]) → 110.0
    """
    recent = [v for v in history_values[-window:] if v > 0]
    return round(sum(recent) / len(recent), 2) if recent else 0.0


def build_values_for_series(data: dict, month_tuples: list, forecast_start_index: int,
                             product: str = None, payer: str = None,
                             forecast_fn=None, treat_zero_as_missing: bool = True) -> tuple:
    """
    Build (history, forecast, all_values) for a single chart/table series.

    - History: actual values from data for months before forecast_start_index
    - Forecast: if forecast_fn is provided, call it as forecast_fn(history, n_fcast).
                Otherwise fall back to flat continuation (avg of last 3 history values)
                for any forecast cell that is <= 0 -- UNLESS treat_zero_as_missing is
                False, in which case raw values are used exactly as stored.

    treat_zero_as_missing=True (the default) is correct when `data` may
    genuinely be sparse (e.g. built straight from transaction_data, where a
    missing row and a real zero can't be told apart, so treating a zero as
    "not forecast yet" is the safer assumption). Callers whose `data` has
    already had every (product, payer) cell explicitly pre-populated for
    every month (e.g. run_calculation_service.py's zero-seeding + event
    application, where a real event can legitimately drive an entity's
    volume to EXACTLY zero, such as a fully-drained impacted product) must
    pass False -- otherwise a deliberate zero gets silently overwritten with
    a flat-forecast fallback derived from history, corrupting both the
    displayed value and any share computed from it (observed as per-entity
    shares summing to over 100%, since the substituted value never went
    through the event's own zero-sum redistribution/renormalization).

    Returns (history_list, forecast_list, full_list)
    """
    all_raw = [get_volume(data, y, m, product, payer) for y, m in month_tuples]
    history  = all_raw[:forecast_start_index]
    n_fcast  = len(month_tuples) - forecast_start_index
    if forecast_fn is not None:
        forecast = forecast_fn(history, n_fcast)
    elif treat_zero_as_missing:
        flat_val = flat_forecast(history)
        forecast = [v if v > 0 else flat_val for v in all_raw[forecast_start_index:]]
    else:
        forecast = all_raw[forecast_start_index:]
    return history, forecast, history + forecast


def compute_share(volume: float, total_volume: float) -> float:
    """
    Compute percentage share: volume / total * 100.
    Returns 0.0 if total_volume is zero (avoids division by zero).
    """
    return round(volume / total_volume * 100, 2) if total_volume else 0.0


def build_chart(header_key: str, header_values: list,
                forecast_start_index: int, series: list) -> dict:
    """
    Build a chart dict.

    header_key is either "months" (monthly view) or "years" (yearly view).
    series is a list of {label, history, forecast} dicts.

    Example output:
    {
        "months": ["Jan-26", "Feb-26", ...],
        "forecast_start_index": 8,
        "series": [{"label": "Truvada", "history": [...], "forecast": [...]}]
    }
    """
    return {
        header_key:            header_values,
        "forecast_start_index": forecast_start_index,
        "series":              series,
    }


def build_flat_table(headers: list, forecast_start_index: int, rows: list,
                      editable: bool = True, type_tag: str = None) -> dict:
    """
    Build a flat (non-hierarchical) table dict.

    rows is a list of {"label": "...", "values": [...]} dicts.
    editable=False for read-only sub-views; type_tag="flat" adds a "type" field.
    """
    result = {
        "headers":              headers,
        "forecast_start_index": forecast_start_index,
        "editable":             editable,
        "rows":                 rows,
    }
    if type_tag:
        result["type"] = type_tag
    return result


def build_hierarchy_table(headers: list, forecast_start_index: int, rows: list) -> dict:
    """
    Build a hierarchical table dict (used in the payer_event tab).

    rows is a list of {"label": "...", "values": [...], "children": [...]} dicts.
    """
    return {
        "type":                "hierarchy",
        "headers":             headers,
        "forecast_start_index": forecast_start_index,
        "editable":            True,
        "rows":                rows,
    }


def aggregate_monthly_to_yearly(month_tuples: list, all_values: list,
                                 forecast_start_index: int) -> tuple:
    """
    Sum monthly values into yearly buckets and split into history/forecast.

    A year is treated as "forecast" if ANY of its months is in the forecast period.
    This means the first year that overlaps with forecast becomes the forecast_start
    in the yearly view.

    Returns (year_labels, history, forecast, yearly_forecast_start_index)

    Example:
        month_tuples = [(2025,10),(2025,11),(2025,12),(2026,1),(2026,2)]
        forecast_start_index = 3  → 2025 has months 10,11,12 all history;
                                      2026 has months 1,2 both forecast
        Result: (["2025","2026"], [sum_2025], [sum_2026], 1)
    """
    yearly_sum = {}
    year_order = []
    year_is_forecast = {}

    for i, (y, m) in enumerate(month_tuples):
        if y not in year_is_forecast:
            year_order.append(y)
            year_is_forecast[y] = False
        yearly_sum[y] = yearly_sum.get(y, 0.0) + all_values[i]
        if i >= forecast_start_index:
            year_is_forecast[y] = True

    # First year where any month is forecast
    yearly_fsi = next(
        (i for i, y in enumerate(year_order) if year_is_forecast[y]),
        len(year_order)
    )

    year_labels = [str(y) for y in year_order]
    history  = [round(yearly_sum[y], 2) for y in year_order[:yearly_fsi]]
    forecast = [round(yearly_sum[y], 2) for y in year_order[yearly_fsi:]]
    return year_labels, history, forecast, yearly_fsi
