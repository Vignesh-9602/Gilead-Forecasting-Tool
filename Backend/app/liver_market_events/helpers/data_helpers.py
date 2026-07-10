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
                             product: str = None, payer: str = None) -> tuple:
    """
    Build (history, forecast, all_values) for a single chart/table series.

    - History: actual values from data for months before forecast_start_index
    - Forecast: flat continuation (average of last 3 history values)

    Returns (history_list, forecast_list, full_list)
    """
    history = [
        get_volume(data, y, m, product, payer)
        for y, m in month_tuples[:forecast_start_index]
    ]
    forecast_val = flat_forecast(history)
    forecast = [forecast_val] * max(0, len(month_tuples) - forecast_start_index)
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


def build_flat_table(headers: list, forecast_start_index: int, rows: list) -> dict:
    """
    Build a flat (non-hierarchical) table dict.

    rows is a list of {"label": "...", "values": [...]} dicts.
    """
    return {
        "headers":             headers,
        "forecast_start_index": forecast_start_index,
        "editable":            True,
        "rows":                rows,
    }


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
