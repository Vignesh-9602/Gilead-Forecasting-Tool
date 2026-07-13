from app.db.connection import get_connection
from app.liver_market_events.schemas.market_events_schema import ApplyFiltersRequest
from app.liver_market_events.repository.market_events_repo import (
    get_payers,
    get_products,
    get_scenarios,
    get_distinct_months,
    get_volume_by_product_payer,
    get_all_configs_for_ta,
    get_configs_for_selection,
    save_filter_state,
    load_filter_state,
    load_scenario_event_tabs,
    save_market_events_scenario,
)
from app.liver_market_events.helpers.date_helpers import (
    parse_year_month,
    generate_month_range,
    to_month_label,
    format_chart_month_label,
    add_months,
)
from app.liver_market_events.helpers.data_helpers import (
    organize_raw_data,
    get_volume,
    flat_forecast,
    build_values_for_series,
    compute_share,
    build_chart,
    build_flat_table,
    build_hierarchy_table,
)

DEFAULT_FORECAST_MONTHS = 12
CURVE_TYPES = ["Linear", "Exponential", "Logarithmic", "SCurve"]
METRIC_FILTERS = [
    {"label": "Payer Share",          "value": "payer_share"},
    {"label": "Overall Payer Volume", "value": "payer_volume"},
]


# ---------------------------------------------------------------------------
# Helper: compute date range from liver_configurations config list
# ---------------------------------------------------------------------------

def _get_date_range_from_configs(configs: list) -> tuple:
    """
    Given a list of config dicts from liver_configurations, return three dates:

    - min_start:       min(train_start_date) across all configs
    - forecast_start:  max(train_end_date) + 1 month  ← where history ends, forecast begins
    - max_end:         max(train_end_date + forecast_periods) ← furthest point in time

    For multi-select payers/products, this gives the broadest range that covers
    all selected combinations.

    Returns (None, None, None) if configs list is empty.
    """
    if not configs:
        return None, None, None

    starts        = []
    train_ends    = []
    forecast_ends = []

    for config in configs:
        train_start = config.get("train_start_date", "")
        train_end   = config.get("train_end_date", "")
        periods     = int(config.get("forecast_periods", DEFAULT_FORECAST_MONTHS))

        if train_start:
            starts.append(train_start[:10])

        if train_end:
            clean_end = train_end[:10]
            train_ends.append(clean_end)

            # forecast_end = train_end + forecast_periods months
            ty, tm = parse_year_month(clean_end)
            fy, fm = add_months(ty, tm, periods)
            forecast_ends.append(to_month_label(fy, fm))

    if not starts or not train_ends:
        return None, None, None

    min_start     = min(starts)
    max_train_end = max(train_ends)

    # forecast_start = one month after the latest train_end across all combinations
    ty, tm = parse_year_month(max_train_end)
    fsy, fsm = add_months(ty, tm, 1)
    forecast_start = to_month_label(fsy, fsm)

    max_end = max(forecast_ends)

    return min_start, forecast_start, max_end


def _available_months_fallback(cur, ta: str) -> tuple:
    """
    Fallback when no liver config exists: derive date range from transaction_data.
    Returns (available_months, forecast_start_date).
    """
    month_rows = get_distinct_months(cur, ta)
    if not month_rows:
        raise ValueError(f"No transaction data or config found for TA: {ta}")

    min_year, min_month = month_rows[0]
    max_year, max_month = month_rows[-1]

    fcast_end_year, fcast_end_month = add_months(max_year, max_month, DEFAULT_FORECAST_MONTHS)
    available_months = generate_month_range(min_year, min_month, fcast_end_year, fcast_end_month)

    fcast_start_year, fcast_start_month = add_months(max_year, max_month, 1)
    forecast_start_date = to_month_label(fcast_start_year, fcast_start_month)

    return available_months, forecast_start_date


# ---------------------------------------------------------------------------
# GET /filters
# ---------------------------------------------------------------------------

def get_market_events_filters(ta: str = "HCV") -> dict:
    """
    Populate all filter dropdowns on page load.

    FROM DATE / TO DATE come from liver_configurations (global config):
    - available_months start = min(train_start_date) across all (payer, product) combos
    - available_months end   = max(train_end_date + forecast_periods) across all combos

    Falls back to transaction_data date range if no config exists for this TA.
    Restores the user's last applied filter from DB; returns defaults on first visit.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        payers    = get_payers(cur)
        products  = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        # Get date range from global config (all combinations for this TA)
        configs = get_all_configs_for_ta(cur, ta)
        min_start, _, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year,   to_month   = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            # No config saved yet — fall back to transaction_data
            available_months, _ = _available_months_fallback(cur, ta)
            min_start = available_months[0]
            max_end   = available_months[-1]

        saved_filter = load_filter_state(cur, ta)
        selected_filter = saved_filter or {
            "scenario_name": "BASE",
            "payers":        [payers[0]]   if payers   else [],
            "products":      [products[0]] if products else [],
            "start_date":    min_start,
            "end_date":      max_end,
        }

        return {
            "ta_name":             ta,
            "available_scenarios": scenarios,
            "payers":              payers,
            "products":            products,
            "available_months":    available_months,
            "selected_filter":     selected_filter,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# POST /apply-filters
# ---------------------------------------------------------------------------

def apply_market_events_filters(payload: ApplyFiltersRequest) -> dict:
    """
    Called when user clicks Apply Filter.

    FROM DATE / TO DATE for the selected combination:
    - Gets liver_configurations rows matching the selected payers × products
    - available_months = min(start) → max(end) across those combinations
    - forecast_start_date = max(train_end_date) + 1 month across those combinations

    Falls back to transaction_data if no config found for the selection.

    BASE scenario → computed fresh from transaction_data.
    Named scenarios → loaded from liver_scenarios.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta = payload.ta_name
        sf = payload.selected_filter

        # Persist filter so it's restored on next page load
        save_filter_state(cur, ta, sf.model_dump())

        payers    = get_payers(cur)
        products  = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        # Get date range from config for the selected (payer, product) combination.
        # Multi-select: returns min of starts and max of ends across all matching combos.
        configs = get_configs_for_selection(cur, ta, sf.payers, sf.products)
        min_start, forecast_start_date, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year,   to_month   = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            # No config for this combo — fall back to transaction_data
            available_months, forecast_start_date = _available_months_fallback(cur, ta)

        # Load or compute metrics_views for the selected scenario
        if sf.scenario_name.upper() == "BASE":
            # BASE is always computed fresh from transaction_data
            saved_event_tabs = _compute_base_event_tabs(cur, ta, sf.model_dump(), forecast_start_date)
        else:
            # Named scenarios are pre-saved in liver_scenarios
            saved_event_tabs = load_scenario_event_tabs(cur, sf.scenario_name)

        # Build impact_curve_configuration fresh for each tab
        payer_event_config = {
            "products":            products,
            "payers":              payers,
            "impact_payers":       payers,
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                [],
        }
        product_event_config = {
            "products":            products,
            "payers":              payers,
            "impact_products":     products,
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                [],
        }
        overall_event_config = {
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                [],
        }

        event_tabs = _merge_config_with_saved_data(
            payer_event_config, product_event_config, overall_event_config, saved_event_tabs
        )

        conn.commit()

        return {
            "ta_name":             ta,
            "available_scenarios": scenarios,
            "available_months":    available_months,
            "selected_filter":     sf.model_dump(),
            "metric_filters":      METRIC_FILTERS,
            "event_tabs":          event_tabs,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Helper: always include BASE at the top of the scenarios list
# ---------------------------------------------------------------------------

def _get_scenarios_with_base(cur) -> list:
    """
    Return all saved scenario names with BASE always at the top.
    BASE is computed fresh (never stored in DB), so we prepend it manually.
    """
    saved = get_scenarios(cur)
    saved = [s for s in saved if s.upper() != "BASE"]
    return ["BASE"] + saved


# ---------------------------------------------------------------------------
# Helper: compute BASE event_tabs from transaction_data
# ---------------------------------------------------------------------------

def _compute_base_event_tabs(cur, ta: str, selected_filter: dict, forecast_start_date: str) -> dict:
    """
    Compute the three event tab metrics from transaction_data for the BASE scenario.

    History  = actual data from DB.
    Forecast = flat continuation (average of last 3 history values).
    """
    from_year, from_month = parse_year_month(selected_filter["start_date"])
    to_year,   to_month   = parse_year_month(selected_filter["end_date"])
    fcast_year, fcast_month = parse_year_month(forecast_start_date)

    sel_payers   = selected_filter.get("payers")   or []
    sel_products = selected_filter.get("products") or []

    raw_rows = get_volume_by_product_payer(
        cur, ta, from_year, from_month, to_year, to_month,
        sel_payers   or None,
        sel_products or None,
    )

    data = organize_raw_data(raw_rows)

    month_iso_list = generate_month_range(from_year, from_month, to_year, to_month)
    month_tuples   = [(int(m[:4]), int(m[5:7])) for m in month_iso_list]
    chart_headers  = [format_chart_month_label(y, m) for y, m in month_tuples]

    fcast_iso = to_month_label(fcast_year, fcast_month)
    if fcast_iso in month_iso_list:
        forecast_start_index = month_iso_list.index(fcast_iso)
    else:
        forecast_start_index = len(month_tuples)

    all_products_in_data = sorted({p for ym in data.values() for p in ym})
    all_payers_in_data   = sorted({py for ym in data.values() for pd in ym.values() for py in pd})
    show_products = sel_products if sel_products else all_products_in_data
    show_payers   = sel_payers   if sel_payers   else all_payers_in_data

    total_hist      = [get_volume(data, y, m) for y, m in month_tuples[:forecast_start_index]]
    total_fcast_val = flat_forecast(total_hist)
    total_all       = total_hist + [total_fcast_val] * max(0, len(month_tuples) - forecast_start_index)

    return {
        "payer_event": {
            "metrics_views": _build_payer_event_metrics(
                data, month_tuples, chart_headers, forecast_start_index, total_all, show_products, show_payers
            )
        },
        "product_event": {
            "metrics_views": _build_product_event_metrics(
                data, month_tuples, chart_headers, forecast_start_index, total_all, show_products
            )
        },
        "overall_event": {
            "metrics_views": _build_overall_event_metrics(
                month_tuples, chart_headers, forecast_start_index, total_all
            )
        },
    }


# ---------------------------------------------------------------------------
# Per-tab metric builders
# ---------------------------------------------------------------------------

def _build_overall_event_metrics(month_tuples, chart_headers, forecast_start_index, total_all) -> dict:
    n_hist  = forecast_start_index
    n_fcast = len(month_tuples) - n_hist

    return {
        "payer_share": {
            "monthly": {
                "chart": build_chart("months", chart_headers, forecast_start_index, [
                    {"label": "Overall", "history": [100.0] * n_hist, "forecast": [100.0] * n_fcast}
                ]),
                "table": build_flat_table(chart_headers, forecast_start_index, [
                    {"label": "Overall", "values": [100.0] * len(month_tuples)}
                ]),
            },
            "yearly": {},
        },
        "payer_volume": {
            "monthly": {
                "chart": build_chart("months", chart_headers, forecast_start_index, [
                    {"label": "Overall Payer", "history": total_all[:n_hist], "forecast": total_all[n_hist:]}
                ]),
                "table": build_flat_table(chart_headers, forecast_start_index, [
                    {"label": "Overall Payer", "values": [round(v, 2) for v in total_all]}
                ]),
            },
            "yearly": {},
        },
    }


def _build_product_event_metrics(data, month_tuples, chart_headers,
                                  forecast_start_index, total_all, show_products) -> dict:
    share_series, vol_series = [], []
    share_rows,   vol_rows   = [], []

    for product in show_products:
        hist, fcast, all_vals = build_values_for_series(data, month_tuples, forecast_start_index, product=product)

        share_hist  = [compute_share(hist[i], total_all[i]) for i in range(len(hist))]
        share_fcast = [flat_forecast(share_hist)] * len(fcast)
        share_all   = share_hist + share_fcast

        share_series.append({"label": product, "history": share_hist,  "forecast": share_fcast})
        vol_series.append(  {"label": product, "history": hist,        "forecast": fcast})
        share_rows.append(  {"label": product, "values": [round(v, 2) for v in share_all]})
        vol_rows.append(    {"label": product, "values": [round(v, 2) for v in all_vals]})

    return {
        "payer_share": {
            "monthly": {
                "chart": build_chart("months", chart_headers, forecast_start_index, share_series),
                "table": build_flat_table(chart_headers, forecast_start_index, share_rows),
            },
            "yearly": {},
        },
        "payer_volume": {
            "monthly": {
                "chart": build_chart("months", chart_headers, forecast_start_index, vol_series),
                "table": build_flat_table(chart_headers, forecast_start_index, vol_rows),
            },
            "yearly": {},
        },
    }


def _build_payer_event_metrics(data, month_tuples, chart_headers, forecast_start_index,
                                total_all, show_products, show_payers) -> dict:
    share_series, vol_series = [], []
    hier_share_rows = [{"label": "Overall", "values": [100.0] * len(month_tuples)}]
    hier_vol_rows   = [{"label": "Overall", "values": [round(v, 2) for v in total_all]}]

    for product in show_products:
        hist, fcast, all_vals = build_values_for_series(data, month_tuples, forecast_start_index, product=product)

        share_hist  = [compute_share(hist[i], total_all[i]) for i in range(len(hist))]
        share_fcast = [flat_forecast(share_hist)] * len(fcast)
        share_all   = share_hist + share_fcast

        share_series.append({"label": product, "history": share_hist, "forecast": share_fcast})
        vol_series.append(  {"label": product, "history": hist,       "forecast": fcast})

        children_share, children_vol = [], []
        for payer in show_payers:
            py_hist, py_fcast, py_all = build_values_for_series(
                data, month_tuples, forecast_start_index, product=product, payer=payer
            )
            py_share_hist  = [compute_share(py_hist[i], total_all[i]) for i in range(len(py_hist))]
            py_share_fcast = [flat_forecast(py_share_hist)] * len(py_fcast)
            py_share_all   = py_share_hist + py_share_fcast

            children_share.append({"label": payer, "values": [round(v, 2) for v in py_share_all]})
            children_vol.append(  {"label": payer, "values": [round(v, 2) for v in py_all]})

        hier_share_rows.append({"label": product, "values": [round(v, 2) for v in share_all],  "children": children_share})
        hier_vol_rows.append(  {"label": product, "values": [round(v, 2) for v in all_vals], "children": children_vol})

    return {
        "payer_share": {
            "monthly": {
                "chart": build_chart("months", chart_headers, forecast_start_index, share_series),
                "table": build_hierarchy_table(chart_headers, forecast_start_index, hier_share_rows),
            },
            "yearly": {},
        },
        "payer_volume": {
            "monthly": {
                "chart": build_chart("months", chart_headers, forecast_start_index, vol_series),
                "table": build_hierarchy_table(chart_headers, forecast_start_index, hier_vol_rows),
            },
            "yearly": {},
        },
    }


# ---------------------------------------------------------------------------
# Helper: merge freshly built config with saved metrics_views
# ---------------------------------------------------------------------------

def _merge_config_with_saved_data(payer_config, product_config, overall_config, saved_tabs) -> dict:
    saved = saved_tabs or {}

    def get_metrics(tab_key: str) -> dict:
        return saved.get(tab_key, {}).get("metrics_views", {})

    return {
        "payer_event": {
            "impact_curve_configuration": payer_config,
            "metrics_views":              get_metrics("payer_event"),
        },
        "product_event": {
            "impact_curve_configuration": product_config,
            "metrics_views":              get_metrics("product_event"),
        },
        "overall_event": {
            "impact_curve_configuration": overall_config,
            "metrics_views":              get_metrics("overall_event"),
        },
    }
