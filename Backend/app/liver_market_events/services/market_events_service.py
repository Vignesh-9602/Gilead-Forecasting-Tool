import copy

from app.db.connection import get_connection
from app.liver_market_events.schemas.market_events_schema import (
    ApplyFiltersRequest,
    RefreshRequest,
    SaveMarketEventsRequest,
)
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
    aggregate_monthly_to_yearly,
)

DEFAULT_FORECAST_MONTHS = 12
CURVE_TYPES = ["Linear", "Exponential", "Logarithmic", "SCurve"]
METRIC_FILTERS = [
    {"label": "Payer Share",          "value": "payer_share"},
    {"label": "Overall Payer Volume", "value": "payer_volume"},
]

# View-level toggle options sent to the frontend
PAYER_EVENT_VIEW_OPTIONS = [
    {"label": "Payer Level",         "value": "payer_level"},
    {"label": "Product-Payer Level", "value": "product_payer_level"},
]
PRODUCT_EVENT_VIEW_OPTIONS = [
    {"label": "Product Level",       "value": "product_level"},
    {"label": "Payer-Product Level", "value": "payer_product_level"},
]

# Frontend always sends "payer_share"/"payer_volume" (via denormalizeMetricValue).
# payer_event stores payer_share/payer_volume — no mapping needed.
# product_event stores product_share/product_volume — needs translation.
_METRIC_KEY_MAP = {
    "product_event": {"payer_share": "product_share", "payer_volume": "product_volume"},
}

def _resolve_metric_key(tab: str, metric: str) -> str:
    return _METRIC_KEY_MAP.get(tab, {}).get(metric, metric)


# ---------------------------------------------------------------------------
# Helper: compute date range from liver_configurations config list
# ---------------------------------------------------------------------------

def _get_date_range_from_configs(configs: list) -> tuple:
    """
    Given a list of config dicts from liver_configurations, return three dates:

    - min_start:       min(train_start_date) across all configs
    - forecast_start:  max(train_end_date) + 1 month
    - max_end:         max(train_end_date + forecast_periods)

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

            ty, tm = parse_year_month(clean_end)
            fy, fm = add_months(ty, tm, periods)
            forecast_ends.append(to_month_label(fy, fm))

    if not starts or not train_ends:
        return None, None, None

    min_start     = min(starts)
    max_train_end = max(train_ends)

    ty, tm = parse_year_month(max_train_end)
    fsy, fsm = add_months(ty, tm, 1)
    forecast_start = to_month_label(fsy, fsm)

    max_end = max(forecast_ends)

    return min_start, forecast_start, max_end


def _available_months_fallback(cur, ta: str) -> tuple:
    """
    Fallback when no liver config exists: derive date range from transaction_data.
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
    Restores the user's last applied filter from DB; returns defaults on first visit.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        payers    = get_payers(cur)
        products  = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        configs = get_all_configs_for_ta(cur, ta)
        min_start, _, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year,   to_month   = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
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
    Saves the filter selection, then returns event_tabs for the chosen scenario.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta = payload.ta_name
        sf = payload.selected_filter

        save_filter_state(cur, ta, sf.model_dump())

        payers    = get_payers(cur)
        products  = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        configs = get_configs_for_selection(cur, ta, sf.payers, sf.products)
        min_start, forecast_start_date, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year,   to_month   = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            available_months, forecast_start_date = _available_months_fallback(cur, ta)

        if sf.scenario_name.upper() == "BASE":
            saved_event_tabs = _compute_base_event_tabs(cur, ta, sf.model_dump(), forecast_start_date)
        else:
            saved_event_tabs = load_scenario_event_tabs(cur, sf.scenario_name)

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
            "products":            products,
            "payers":              payers,
            "impact_payers":       ["Overall"],
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
    saved = get_scenarios(cur)
    saved = [s for s in saved if s.upper() != "BASE"]
    return ["BASE"] + saved


# ---------------------------------------------------------------------------
# Helper: compute BASE event_tabs from transaction_data
# ---------------------------------------------------------------------------

def _compute_base_event_tabs(cur, ta: str, selected_filter: dict, forecast_start_date: str) -> dict:
    """
    Compute the three event tab metrics from transaction_data for the BASE scenario.
    Uses actual DB values for both history and forecast months (if populated by model).
    Falls back to flat forecast for any month with no DB data.
    """
    from_year, from_month = parse_year_month(selected_filter["start_date"])
    to_year,   to_month   = parse_year_month(selected_filter["end_date"])
    fcast_year, fcast_month = parse_year_month(forecast_start_date)

    # Always fetch all products and payers — filter selection only affects date range,
    # not which series appear in the charts/tables.
    raw_rows = get_volume_by_product_payer(
        cur, ta, from_year, from_month, to_year, to_month,
        payers=None, products=None,
    )

    data = organize_raw_data(raw_rows)

    month_iso_list = generate_month_range(from_year, from_month, to_year, to_month)
    month_tuples   = [(int(m[:4]), int(m[5:7])) for m in month_iso_list]
    chart_headers  = month_iso_list

    fcast_iso = to_month_label(fcast_year, fcast_month)
    if fcast_iso in month_iso_list:
        forecast_start_index = month_iso_list.index(fcast_iso)
    else:
        forecast_start_index = len(month_tuples)

    show_products = sorted({p  for ym in data.values() for p  in ym})
    show_payers   = sorted({py for ym in data.values() for pd in ym.values() for py in pd})

    # Total volume for ALL months (history + forecast); fall back to flat forecast when no data
    total_raw = [get_volume(data, y, m) for y, m in month_tuples]
    total_hist = total_raw[:forecast_start_index]
    total_fcast_val = flat_forecast(total_hist)
    total_all = total_hist + [v if v > 0 else total_fcast_val for v in total_raw[forecast_start_index:]]

    return {
        "payer_event": {
            "metrics_views": _build_payer_event_metrics(
                data, month_tuples, chart_headers, forecast_start_index, total_all, show_products, show_payers
            )
        },
        "product_event": {
            "metrics_views": _build_product_event_metrics(
                data, month_tuples, chart_headers, forecast_start_index, total_all, show_products, show_payers
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

OVERALL_EVENT_VIEW_OPTIONS = [
    {"label": "Overall", "value": "overall_level"},
]


def _build_overall_event_metrics(month_tuples, chart_headers, forecast_start_index, total_all) -> dict:
    """
    Overall event — single view level wrapped in the same view_options pattern
    as payer_event and product_event so the frontend renders it consistently.
    """
    n_hist  = forecast_start_index
    n_fcast = len(month_tuples) - n_hist

    year_labels, y_vol_hist, y_vol_fcast, y_fsi = aggregate_monthly_to_yearly(
        month_tuples, total_all, forecast_start_index
    )
    y_share_hist  = [100.0] * len(y_vol_hist)
    y_share_fcast = [100.0] * len(y_vol_fcast)

    def _wrap(monthly_chart, monthly_table, yearly_chart, yearly_table):
        return {
            "monthly": {
                "view_options":  OVERALL_EVENT_VIEW_OPTIONS,
                "selected_view": "overall_level",
                "overall_level": {"chart": monthly_chart, "table": monthly_table},
            },
            "yearly": {
                "view_options":  OVERALL_EVENT_VIEW_OPTIONS,
                "selected_view": "overall_level",
                "overall_level": {"chart": yearly_chart, "table": yearly_table},
            },
        }

    return {
        "payer_share": _wrap(
            build_chart("months", chart_headers, forecast_start_index, [
                {"label": "Overall", "history": [100.0] * n_hist, "forecast": [100.0] * n_fcast}
            ]),
            build_flat_table(chart_headers, forecast_start_index, [
                {"label": "Overall", "values": [100.0] * len(month_tuples)}
            ]),
            build_chart("years", year_labels, y_fsi, [
                {"label": "Overall", "history": y_share_hist, "forecast": y_share_fcast}
            ]),
            build_flat_table(year_labels, y_fsi, [
                {"label": "Overall", "values": y_share_hist + y_share_fcast}
            ]),
        ),
        "payer_volume": _wrap(
            build_chart("months", chart_headers, forecast_start_index, [
                {"label": "Overall Payer", "history": total_all[:n_hist], "forecast": total_all[n_hist:]}
            ]),
            build_flat_table(chart_headers, forecast_start_index, [
                {"label": "Overall Payer", "values": [round(v, 2) for v in total_all]}
            ]),
            build_chart("years", year_labels, y_fsi, [
                {"label": "Overall Payer", "history": y_vol_hist, "forecast": y_vol_fcast}
            ]),
            build_flat_table(year_labels, y_fsi, [
                {"label": "Overall Payer", "values": y_vol_hist + y_vol_fcast}
            ]),
        ),
    }


def _build_payer_event_metrics(data, month_tuples, chart_headers, forecast_start_index,
                                total_all, show_products, show_payers) -> dict:
    """
    Payer event — two view levels per metric/period:
      payer_level         : Overall + flat payer rows, read-only
      product_payer_level : Overall + product rows with payer children, editable

    Shows how payers are distributed; hierarchy drills into each product's payer breakdown.
    """
    n_hist = forecast_start_index

    # ── Per-payer monthly volumes and shares ──────────────────────────────────
    payer_vol_m   = {}   # payer → (hist, fcast, all_vals)
    payer_share_m = {}   # payer → (share_hist, share_fcast, share_all)

    for payer in show_payers:
        hist, fcast, all_vals = build_values_for_series(
            data, month_tuples, forecast_start_index, payer=payer
        )
        sh_all = [compute_share(all_vals[i], total_all[i]) for i in range(len(all_vals))]
        payer_vol_m[payer]   = (hist, fcast, all_vals)
        payer_share_m[payer] = (sh_all[:n_hist], sh_all[n_hist:], sh_all)

    # ── Per-product monthly volumes (parents in hierarchy) ───────────────────
    prod_vol_m   = {}   # product → (hist, fcast, all_vals)
    prod_share_m = {}   # product → (share_hist, share_fcast, share_all)

    for product in show_products:
        hist, fcast, all_vals = build_values_for_series(
            data, month_tuples, forecast_start_index, product=product
        )
        sh_all = [compute_share(all_vals[i], total_all[i]) for i in range(len(all_vals))]
        prod_vol_m[product]   = (hist, fcast, all_vals)
        prod_share_m[product] = (sh_all[:n_hist], sh_all[n_hist:], sh_all)

    # ── Per-(product×payer) monthly volumes and shares ────────────────────────
    pp_vol_m   = {}   # (product, payer) → (hist, fcast, all_vals)
    pp_share_m = {}   # (product, payer) → share_all

    for product in show_products:
        for payer in show_payers:
            h, f, av = build_values_for_series(
                data, month_tuples, forecast_start_index, product=product, payer=payer
            )
            sh_all = [compute_share(av[i], total_all[i]) for i in range(len(av))]
            pp_vol_m[(product, payer)]   = (h, f, av)
            pp_share_m[(product, payer)] = sh_all

    # ── Yearly aggregation ────────────────────────────────────────────────────
    year_labels, y_tot_hist, y_tot_fcast, y_fsi = aggregate_monthly_to_yearly(
        month_tuples, total_all, forecast_start_index
    )
    y_total_all = y_tot_hist + y_tot_fcast

    payer_vol_y   = {}
    payer_share_y = {}
    for payer in show_payers:
        _, _, av = payer_vol_m[payer]
        _, yv_h, yv_f, _ = aggregate_monthly_to_yearly(month_tuples, av, forecast_start_index)
        y_vol_all = yv_h + yv_f
        ys_all = [compute_share(y_vol_all[i], y_total_all[i]) for i in range(len(y_total_all))]
        payer_vol_y[payer]   = (yv_h, yv_f)
        payer_share_y[payer] = (ys_all[:y_fsi], ys_all[y_fsi:])

    prod_vol_y   = {}
    prod_share_y = {}
    for product in show_products:
        _, _, av = prod_vol_m[product]
        _, yv_h, yv_f, _ = aggregate_monthly_to_yearly(month_tuples, av, forecast_start_index)
        y_vol_all = yv_h + yv_f
        ys_all = [compute_share(y_vol_all[i], y_total_all[i]) for i in range(len(y_total_all))]
        prod_vol_y[product]   = (yv_h, yv_f)
        prod_share_y[product] = (ys_all[:y_fsi], ys_all[y_fsi:])

    pp_vol_y   = {}
    pp_share_y = {}
    for product in show_products:
        for payer in show_payers:
            _, _, av = pp_vol_m[(product, payer)]
            _, yv_h, yv_f, _ = aggregate_monthly_to_yearly(month_tuples, av, forecast_start_index)
            y_vol_all_pp = yv_h + yv_f
            ys_all = [compute_share(y_vol_all_pp[i], y_total_all[i]) for i in range(len(y_total_all))]
            pp_vol_y[(product, payer)]   = (yv_h, yv_f)
            pp_share_y[(product, payer)] = (ys_all[:y_fsi], ys_all[y_fsi:])

    # ── View builder helpers ──────────────────────────────────────────────────

    def _share_view(hdr, fsi, is_yearly):
        n_pts = len(year_labels) if is_yearly else len(month_tuples)
        hkey  = "years" if is_yearly else "months"
        spy   = payer_share_y if is_yearly else payer_share_m   # payer shares
        sp    = prod_share_y  if is_yearly else prod_share_m    # product shares (parents)
        pp    = pp_share_y    if is_yearly else pp_share_m      # cross shares

        def _payer_vals(payer):
            sh_h, sh_f = spy[payer][:2]
            return sh_h + sh_f

        def _prod_vals(product):
            sh_h, sh_f = sp[product][:2]
            return sh_h + sh_f

        # payer_level: flat payer rows, payer series on chart
        pl_series = [{"label": py, "history": spy[py][0], "forecast": spy[py][1]} for py in show_payers]
        pl_rows = [{"label": "Overall", "values": [100.0] * n_pts}] + [
            {"label": py, "values": [round(v, 2) for v in _payer_vals(py)]} for py in show_payers
        ]

        # product_payer_level: product→payer hierarchy; chart shows payer series
        ppl_series = [{"label": py, "history": spy[py][0], "forecast": spy[py][1]} for py in show_payers]
        ppl_rows = [{"label": "Overall", "values": [100.0] * n_pts}]
        for product in show_products:
            children = []
            for payer in show_payers:
                if is_yearly:
                    ys_h, ys_f = pp[(product, payer)]
                    children.append({"label": payer, "values": [round(v, 2) for v in (ys_h + ys_f)]})
                else:
                    children.append({"label": payer, "values": [round(v, 2) for v in pp[(product, payer)]]})
            ppl_rows.append({"label": product, "values": [round(v, 2) for v in _prod_vals(product)], "children": children})

        return {
            "view_options":  PAYER_EVENT_VIEW_OPTIONS,
            "selected_view": "product_payer_level",
            "payer_level": {
                "chart": build_chart(hkey, hdr, fsi, pl_series),
                "table": build_flat_table(hdr, fsi, pl_rows, editable=False, type_tag="flat"),
            },
            "product_payer_level": {
                "chart": build_chart(hkey, hdr, fsi, ppl_series),
                "table": build_hierarchy_table(hdr, fsi, ppl_rows),
            },
        }

    def _vol_view(hdr, fsi, is_yearly):
        hkey  = "years" if is_yearly else "months"
        vpy   = payer_vol_y if is_yearly else payer_vol_m
        vp    = prod_vol_y  if is_yearly else prod_vol_m
        pp    = pp_vol_y    if is_yearly else pp_vol_m

        overall_vals = (y_tot_hist + y_tot_fcast) if is_yearly else [round(v, 2) for v in total_all]

        def _payer_vals(payer):
            yv_h, yv_f = vpy[payer][:2]
            return yv_h + yv_f

        def _prod_vals(product):
            yv_h, yv_f = vp[product][:2]
            return yv_h + yv_f

        pl_series = [{"label": py, "history": list(vpy[py][0]), "forecast": list(vpy[py][1])} for py in show_payers]
        pl_rows = [{"label": "Overall", "values": list(overall_vals)}] + [
            {"label": py, "values": [round(v, 2) for v in _payer_vals(py)]} for py in show_payers
        ]

        ppl_series = [{"label": py, "history": list(vpy[py][0]), "forecast": list(vpy[py][1])} for py in show_payers]
        ppl_rows = [{"label": "Overall", "values": list(overall_vals)}]
        for product in show_products:
            children = []
            for payer in show_payers:
                if is_yearly:
                    pyv_h, pyv_f = pp[(product, payer)]
                    children.append({"label": payer, "values": [round(v, 2) for v in (pyv_h + pyv_f)]})
                else:
                    _, _, av = pp[(product, payer)]
                    children.append({"label": payer, "values": [round(v, 2) for v in av]})
            ppl_rows.append({"label": product, "values": [round(v, 2) for v in _prod_vals(product)], "children": children})

        return {
            "view_options":  PAYER_EVENT_VIEW_OPTIONS,
            "selected_view": "product_payer_level",
            "payer_level": {
                "chart": build_chart(hkey, hdr, fsi, pl_series),
                "table": build_flat_table(hdr, fsi, pl_rows, editable=False, type_tag="flat"),
            },
            "product_payer_level": {
                "chart": build_chart(hkey, hdr, fsi, ppl_series),
                "table": build_hierarchy_table(hdr, fsi, ppl_rows),
            },
        }

    return {
        "payer_share": {
            "monthly": _share_view(chart_headers, forecast_start_index, is_yearly=False),
            "yearly":  _share_view(year_labels,   y_fsi,                is_yearly=True),
        },
        "payer_volume": {
            "monthly": _vol_view(chart_headers, forecast_start_index, is_yearly=False),
            "yearly":  _vol_view(year_labels,   y_fsi,                is_yearly=True),
        },
    }


def _build_product_event_metrics(data, month_tuples, chart_headers, forecast_start_index,
                                   total_all, show_products, show_payers) -> dict:
    """
    Product event — two view levels per metric/period:
      product_level       : Overall + flat product rows, read-only
      payer_product_level : Overall + payer rows with product children, editable

    Shows how products are distributed; hierarchy drills into each payer's product breakdown.
    """
    n_hist = forecast_start_index

    # ── Per-product monthly volumes and shares ────────────────────────────────
    prod_vol_m   = {}   # product → (hist, fcast, all_vals)
    prod_share_m = {}   # product → (share_hist, share_fcast, share_all)

    for product in show_products:
        hist, fcast, all_vals = build_values_for_series(
            data, month_tuples, forecast_start_index, product=product
        )
        sh_all = [compute_share(all_vals[i], total_all[i]) for i in range(len(all_vals))]
        prod_vol_m[product]   = (hist, fcast, all_vals)
        prod_share_m[product] = (sh_all[:n_hist], sh_all[n_hist:], sh_all)

    # ── Per-payer monthly volumes (parents in hierarchy) ─────────────────────
    payer_vol_m   = {}   # payer → (hist, fcast, all_vals)
    payer_share_m = {}   # payer → (share_hist, share_fcast, share_all)

    for payer in show_payers:
        hist, fcast, all_vals = build_values_for_series(
            data, month_tuples, forecast_start_index, payer=payer
        )
        sh_all = [compute_share(all_vals[i], total_all[i]) for i in range(len(all_vals))]
        payer_vol_m[payer]   = (hist, fcast, all_vals)
        payer_share_m[payer] = (sh_all[:n_hist], sh_all[n_hist:], sh_all)

    # ── Per-(payer×product) monthly volumes and shares ────────────────────────
    pp_vol_m   = {}   # (payer, product) → (hist, fcast, all_vals)
    pp_share_m = {}   # (payer, product) → share_all

    for payer in show_payers:
        for product in show_products:
            h, f, av = build_values_for_series(
                data, month_tuples, forecast_start_index, product=product, payer=payer
            )
            sh_all = [compute_share(av[i], total_all[i]) for i in range(len(av))]
            pp_vol_m[(payer, product)]   = (h, f, av)
            pp_share_m[(payer, product)] = sh_all

    # ── Yearly aggregation ────────────────────────────────────────────────────
    year_labels, y_tot_hist, y_tot_fcast, y_fsi = aggregate_monthly_to_yearly(
        month_tuples, total_all, forecast_start_index
    )
    y_total_all = y_tot_hist + y_tot_fcast

    prod_vol_y   = {}
    prod_share_y = {}
    for product in show_products:
        _, _, av = prod_vol_m[product]
        _, yv_h, yv_f, _ = aggregate_monthly_to_yearly(month_tuples, av, forecast_start_index)
        y_vol_all = yv_h + yv_f
        ys_all = [compute_share(y_vol_all[i], y_total_all[i]) for i in range(len(y_total_all))]
        prod_vol_y[product]   = (yv_h, yv_f)
        prod_share_y[product] = (ys_all[:y_fsi], ys_all[y_fsi:])

    payer_vol_y   = {}
    payer_share_y = {}
    for payer in show_payers:
        _, _, av = payer_vol_m[payer]
        _, yv_h, yv_f, _ = aggregate_monthly_to_yearly(month_tuples, av, forecast_start_index)
        y_vol_all = yv_h + yv_f
        ys_all = [compute_share(y_vol_all[i], y_total_all[i]) for i in range(len(y_total_all))]
        payer_vol_y[payer]   = (yv_h, yv_f)
        payer_share_y[payer] = (ys_all[:y_fsi], ys_all[y_fsi:])

    pp_vol_y   = {}
    pp_share_y = {}
    for payer in show_payers:
        for product in show_products:
            _, _, av = pp_vol_m[(payer, product)]
            _, yv_h, yv_f, _ = aggregate_monthly_to_yearly(month_tuples, av, forecast_start_index)
            y_vol_all_pp = yv_h + yv_f
            ys_all = [compute_share(y_vol_all_pp[i], y_total_all[i]) for i in range(len(y_total_all))]
            pp_vol_y[(payer, product)]   = (yv_h, yv_f)
            pp_share_y[(payer, product)] = (ys_all[:y_fsi], ys_all[y_fsi:])

    # ── View builder helpers ──────────────────────────────────────────────────

    def _share_view(hdr, fsi, is_yearly):
        n_pts = len(year_labels) if is_yearly else len(month_tuples)
        hkey  = "years" if is_yearly else "months"
        sp    = prod_share_y   if is_yearly else prod_share_m   # product shares
        spy   = payer_share_y  if is_yearly else payer_share_m  # payer shares (parents)
        pp    = pp_share_y     if is_yearly else pp_share_m     # cross shares

        def _prod_vals(product):
            sh_h, sh_f = sp[product][:2]
            return sh_h + sh_f

        def _payer_vals(payer):
            sh_h, sh_f = spy[payer][:2]
            return sh_h + sh_f

        # product_level: flat product rows, product series on chart
        pl_series = [{"label": p, "history": sp[p][0], "forecast": sp[p][1]} for p in show_products]
        pl_rows = [{"label": "Overall", "values": [100.0] * n_pts}] + [
            {"label": p, "values": [round(v, 2) for v in _prod_vals(p)]} for p in show_products
        ]

        # payer_product_level: payer→product hierarchy; chart shows product series
        ppl_series = [{"label": p, "history": sp[p][0], "forecast": sp[p][1]} for p in show_products]
        ppl_rows = [{"label": "Overall", "values": [100.0] * n_pts}]
        for payer in show_payers:
            children = []
            for product in show_products:
                if is_yearly:
                    ys_h, ys_f = pp[(payer, product)]
                    children.append({"label": product, "values": [round(v, 2) for v in (ys_h + ys_f)]})
                else:
                    children.append({"label": product, "values": [round(v, 2) for v in pp[(payer, product)]]})
            ppl_rows.append({"label": payer, "values": [round(v, 2) for v in _payer_vals(payer)], "children": children})

        return {
            "view_options":  PRODUCT_EVENT_VIEW_OPTIONS,
            "selected_view": "payer_product_level",
            "product_level": {
                "chart": build_chart(hkey, hdr, fsi, pl_series),
                "table": build_flat_table(hdr, fsi, pl_rows, editable=False, type_tag="flat"),
            },
            "payer_product_level": {
                "chart": build_chart(hkey, hdr, fsi, ppl_series),
                "table": build_hierarchy_table(hdr, fsi, ppl_rows),
            },
        }

    def _vol_view(hdr, fsi, is_yearly):
        hkey  = "years" if is_yearly else "months"
        vp    = prod_vol_y   if is_yearly else prod_vol_m
        vpy   = payer_vol_y  if is_yearly else payer_vol_m
        pp    = pp_vol_y     if is_yearly else pp_vol_m

        overall_vals = (y_tot_hist + y_tot_fcast) if is_yearly else [round(v, 2) for v in total_all]

        def _prod_vals(product):
            yv_h, yv_f = vp[product][:2]
            return yv_h + yv_f

        def _payer_vals(payer):
            yv_h, yv_f = vpy[payer][:2]
            return yv_h + yv_f

        pl_series = [{"label": p, "history": list(vp[p][0]), "forecast": list(vp[p][1])} for p in show_products]
        pl_rows = [{"label": "Overall", "values": list(overall_vals)}] + [
            {"label": p, "values": [round(v, 2) for v in _prod_vals(p)]} for p in show_products
        ]

        ppl_series = [{"label": p, "history": list(vp[p][0]), "forecast": list(vp[p][1])} for p in show_products]
        ppl_rows = [{"label": "Overall", "values": list(overall_vals)}]
        for payer in show_payers:
            children = []
            for product in show_products:
                if is_yearly:
                    pyv_h, pyv_f = pp[(payer, product)]
                    children.append({"label": product, "values": [round(v, 2) for v in (pyv_h + pyv_f)]})
                else:
                    _, _, av = pp[(payer, product)]
                    children.append({"label": product, "values": [round(v, 2) for v in av]})
            ppl_rows.append({"label": payer, "values": [round(v, 2) for v in _payer_vals(payer)], "children": children})

        return {
            "view_options":  PRODUCT_EVENT_VIEW_OPTIONS,
            "selected_view": "payer_product_level",
            "product_level": {
                "chart": build_chart(hkey, hdr, fsi, pl_series),
                "table": build_flat_table(hdr, fsi, pl_rows, editable=False, type_tag="flat"),
            },
            "payer_product_level": {
                "chart": build_chart(hkey, hdr, fsi, ppl_series),
                "table": build_hierarchy_table(hdr, fsi, ppl_rows),
            },
        }

    return {
        "product_share": {
            "monthly": _share_view(chart_headers, forecast_start_index, is_yearly=False),
            "yearly":  _share_view(year_labels,   y_fsi,                is_yearly=True),
        },
        "product_volume": {
            "monthly": _vol_view(chart_headers, forecast_start_index, is_yearly=False),
            "yearly":  _vol_view(year_labels,   y_fsi,                is_yearly=True),
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


# ---------------------------------------------------------------------------
# POST /refresh — redistribution helpers + apply edits
# ---------------------------------------------------------------------------

def _redistribute_flat(rows: list, edited_label: str, is_share: bool) -> list:
    """
    Flat table: keep the edited row fixed (capped at target), scale all other
    non-Overall rows proportionally so the total stays consistent.

    - Share metric: each column must sum to 100.0; edited value capped at 100
    - Volume metric: overall total stays unchanged; edited value capped at overall
    """
    non_overall = [r for r in rows if r["label"] != "Overall"]
    edited      = next((r for r in non_overall if r["label"] == edited_label), None)
    others      = [r for r in non_overall if r["label"] != edited_label]

    if not edited:
        return rows

    n = len(edited["values"])

    if is_share:
        targets = [100.0] * n
    else:
        overall = next((r for r in rows if r["label"] == "Overall"), None)
        targets = (
            overall["values"]
            if overall
            else [sum(float(r["values"][i]) for r in non_overall) for i in range(n)]
        )

    # Cap the edited value at the target so it can never exceed 100% (share) or total (volume)
    capped_vals = [min(float(edited["values"][i]), float(targets[i])) for i in range(n)]
    capped_edited = {**edited, "values": [round(v, 2) for v in capped_vals]}

    new_others = []
    for other in others:
        new_vals = []
        for i in range(n):
            remaining   = max(0.0, float(targets[i]) - capped_vals[i])
            old_sib_sum = sum(float(r["values"][i]) for r in others)
            old_val     = float(other["values"][i])
            if old_sib_sum > 0:
                new_vals.append(round(old_val / old_sib_sum * remaining, 2))
            else:
                new_vals.append(round(remaining / max(1, len(others)), 2))
        new_others.append({"label": other["label"], "values": new_vals})

    # Recompute Overall as the fresh sum
    all_non_overall = [capped_edited] + new_others
    new_overall = [
        round(sum(float(r["values"][i]) for r in all_non_overall), 2) for i in range(n)
    ]

    # Rebuild preserving original row order
    sib_map = {o["label"]: o for o in new_others}
    result = []
    for r in rows:
        if r["label"] == "Overall":
            result.append({"label": "Overall", "values": new_overall})
        elif r["label"] == edited_label:
            result.append(capped_edited)
        else:
            result.append(sib_map.get(r["label"], r))
    return result


def _redistribute_hierarchy(rows: list, edited_label: str) -> list:
    """
    Hierarchy table: edited_label must be "ParentLabel - ChildLabel".

    - Caps the edited child's value at the parent total per column (it can never
      exceed its parent's share/volume).
    - Scales sibling children proportionally so they fill the remainder
      (parent_total - capped_edited_child).
    - Preserves original children order.
    - Leaves all other parents untouched.
    - Recomputes Overall from updated parent rows.
    """
    if " - " not in edited_label:
        return rows

    parent_lbl, child_lbl = edited_label.split(" - ", 1)

    new_rows = []
    for row in rows:
        if row["label"] == "Overall":
            new_rows.append(row)          # recomputed at end
            continue

        if row["label"] != parent_lbl:
            new_rows.append(row)
            continue

        children     = row.get("children", [])
        edited_child = next((c for c in children if c["label"] == child_lbl), None)
        siblings     = [c for c in children if c["label"] != child_lbl]

        if not edited_child:
            new_rows.append(row)
            continue

        n           = len(edited_child["values"])
        parent_vals = row["values"]       # parent total — the hard cap

        # Cap edited child at parent total so siblings always get a non-negative remainder
        capped_vals = [
            min(float(edited_child["values"][i]), float(parent_vals[i])) for i in range(n)
        ]
        capped_child = {**edited_child, "values": [round(v, 2) for v in capped_vals]}

        new_siblings = []
        for sib in siblings:
            new_vals = []
            for i in range(n):
                remaining   = max(0.0, float(parent_vals[i]) - capped_vals[i])
                old_sib_sum = sum(float(s["values"][i]) for s in siblings)
                old_val     = float(sib["values"][i])
                if old_sib_sum > 0:
                    new_vals.append(round(old_val / old_sib_sum * remaining, 2))
                else:
                    new_vals.append(round(remaining / max(1, len(siblings)), 2))
            new_siblings.append({"label": sib["label"], "values": new_vals})

        # Preserve original children order
        sib_map = {s["label"]: s for s in new_siblings}
        new_children = [
            capped_child if c["label"] == child_lbl else sib_map.get(c["label"], c)
            for c in children
        ]

        new_rows.append({
            "label":    parent_lbl,
            "values":   row["values"],    # parent total unchanged
            "children": new_children,
        })

    # Recompute Overall from updated parent rows
    parents = [r for r in new_rows if r["label"] != "Overall"]
    if parents:
        n = len(parents[0]["values"])
        new_overall = [
            round(sum(float(r["values"][i]) for r in parents), 2) for i in range(n)
        ]
        new_rows = [
            {"label": "Overall", "values": new_overall} if r["label"] == "Overall" else r
            for r in new_rows
        ]

    return new_rows


# Maps a flat view key → its companion hierarchy key (same tab, same metric, same period)
_FLAT_TO_HIER = {
    "payer_level":   "product_payer_level",   # payer_event: flat payers → product→payer hierarchy
    "product_level": "payer_product_level",   # product_event: flat products → payer→product hierarchy
}

# Maps a hierarchy view key → its companion flat key (reverse propagation)
_HIER_TO_FLAT = {
    "product_payer_level": "payer_level",    # payer_event: hierarchy edit → update flat payer totals
    "payer_product_level": "product_level",  # product_event: hierarchy edit → update flat product totals
}


def _propagate_flat_to_hierarchy(hier_rows: list, flat_rows: list) -> list:
    """
    Cross-dimension propagation: flat items are hierarchy CHILDREN, not parents.

    New design:
      payer_event  → flat shows payers;   hierarchy children are payers   (parents = products)
      product_event → flat shows products; hierarchy children are products (parents = payers)

    When a flat item's total changes, every matching child across all hierarchy
    parents is scaled proportionally (old_child / old_child_total_across_parents).
    Parent row totals are recomputed from their updated children.
    """
    flat_lookup = {r["label"]: r["values"] for r in flat_rows if r["label"] != "Overall"}

    # Compute old child totals by summing each child label across all parents
    old_child_totals: dict = {}
    for row in hier_rows:
        if row["label"] == "Overall":
            continue
        for child in row.get("children", []):
            lbl = child["label"]
            if lbl not in old_child_totals:
                old_child_totals[lbl] = [0.0] * len(child["values"])
            for i, v in enumerate(child["values"]):
                old_child_totals[lbl][i] += float(v)

    new_rows = []
    for row in hier_rows:
        if row["label"] == "Overall":
            new_rows.append(row)          # recomputed at end
            continue

        children = row.get("children", [])
        if not children:
            new_rows.append(row)
            continue

        new_children = []
        for child in children:
            new_flat_vals = flat_lookup.get(child["label"])
            if new_flat_vals is None:
                new_children.append(child)
                continue

            old_total = old_child_totals.get(child["label"], [])
            n         = len(child["values"])
            new_child_vals = []
            for i in range(n):
                old_tot   = float(old_total[i]) if i < len(old_total) else 0.0
                new_tot   = float(new_flat_vals[i])
                old_child = float(child["values"][i])
                if old_tot > 0:
                    new_child_vals.append(round(old_child / old_tot * new_tot, 2))
                else:
                    new_child_vals.append(round(new_tot / max(1, len(children)), 2))
            new_children.append({"label": child["label"], "values": new_child_vals})

        # Recompute parent total from updated children
        n = len(new_children[0]["values"]) if new_children else len(row["values"])
        new_parent_vals = [
            round(sum(float(c["values"][i]) for c in new_children), 2) for i in range(n)
        ]
        new_rows.append({"label": row["label"], "values": new_parent_vals, "children": new_children})

    # Recompute Overall from updated parent rows
    parents = [r for r in new_rows if r["label"] != "Overall"]
    if parents:
        n = len(parents[0]["values"])
        new_overall = [
            round(sum(float(r["values"][i]) for r in parents), 2) for i in range(n)
        ]
        new_rows = [
            {"label": "Overall", "values": new_overall} if r["label"] == "Overall" else r
            for r in new_rows
        ]

    return new_rows


def _propagate_hierarchy_to_flat(flat_rows: list, hier_rows: list) -> list:
    """
    After a hierarchy edit, recalculate the flat view by summing each child
    label across all parents.

    payer_event  → hierarchy children are payers;   flat shows payer totals.
    product_event → hierarchy children are products; flat shows product totals.
    """
    # Sum each child label across all parent rows
    child_totals: dict = {}
    for row in hier_rows:
        if row["label"] == "Overall":
            continue
        for child in row.get("children", []):
            lbl = child["label"]
            if lbl not in child_totals:
                child_totals[lbl] = [0.0] * len(child["values"])
            for i, v in enumerate(child["values"]):
                child_totals[lbl][i] += float(v)

    new_rows = []
    for row in flat_rows:
        if row["label"] == "Overall":
            new_rows.append(row)          # recomputed at end
            continue
        new_vals = child_totals.get(row["label"])
        if new_vals is not None:
            new_rows.append({"label": row["label"], "values": [round(v, 2) for v in new_vals]})
        else:
            new_rows.append(row)

    # Recompute Overall from updated flat rows
    non_overall = [r for r in new_rows if r["label"] != "Overall"]
    if non_overall:
        n = len(non_overall[0]["values"])
        new_overall = [round(sum(float(r["values"][i]) for r in non_overall), 2) for i in range(n)]
        new_rows = [
            {"label": "Overall", "values": new_overall} if r["label"] == "Overall" else r
            for r in new_rows
        ]

    return new_rows


def _update_view(target: dict, rows: list) -> None:
    """Patch a view's table rows and re-sync its chart series in place."""
    fsi = target["table"].get("forecast_start_index", 0)
    target["table"]["rows"] = rows
    target["chart"]["series"] = [
        {
            "label":    r["label"],
            "history":  [round(float(v), 2) for v in r["values"][:fsi]],
            "forecast": [round(float(v), 2) for v in r["values"][fsi:]],
        }
        for r in rows
        if r["label"] != "Overall"
    ]


def _detect_edited_label(old_rows: list, new_rows: list) -> str | None:
    """
    Diff old and new table rows to find which single cell the user changed.
    Returns "Label" for a flat-level change, or "Parent - Child" for a hierarchy change.
    Returns None when no change is detected (e.g. first load, no actual edit).
    Uses a small tolerance so float-rounding artefacts don't count as edits.
    """
    def _differs(a, b):
        return len(a) != len(b) or any(abs(float(x) - float(y)) > 0.001 for x, y in zip(a, b))

    old_map = {r["label"]: r for r in old_rows}

    for new_row in new_rows:
        lbl = new_row["label"]
        if lbl == "Overall":
            continue
        old_row = old_map.get(lbl)
        if old_row is None:
            continue

        new_children = new_row.get("children", [])
        old_children = old_row.get("children", [])

        if new_children:
            old_child_map = {c["label"]: c for c in old_children}
            for nc in new_children:
                oc = old_child_map.get(nc["label"])
                if oc and _differs(nc["values"], oc["values"]):
                    return f"{lbl} - {nc['label']}"
        else:
            if _differs(new_row["values"], old_row.get("values", [])):
                return lbl

    return None


def _update_hierarchy_parents_from_flat(hier_rows: list, flat_rows: list) -> list:
    """
    Update hierarchy PARENT row values to match a flat view's new totals, then
    scale each parent's children proportionally.

    Flat items are parents (not children) in this hierarchy:
      payer_event.payer_level (flat payers) → product_event.payer_product_level (payer parents)
    """
    flat_lookup = {r["label"]: r["values"] for r in flat_rows if r["label"] != "Overall"}

    new_rows = []
    for row in hier_rows:
        if row["label"] == "Overall":
            new_rows.append(row)
            continue

        new_parent_vals = flat_lookup.get(row["label"])
        if new_parent_vals is None:
            new_rows.append(row)
            continue

        old_parent_vals = row["values"]
        children = row.get("children", [])
        n = len(old_parent_vals)

        new_children = []
        for child in children:
            new_child_vals = []
            for i in range(n):
                old_p = float(old_parent_vals[i])
                new_p = float(new_parent_vals[i])
                old_c = float(child["values"][i]) if i < len(child["values"]) else 0.0
                new_child_vals.append(
                    round(old_c / old_p * new_p, 2) if old_p > 0 else 0.0
                )
            new_children.append({"label": child["label"], "values": new_child_vals})

        new_rows.append({
            "label":    row["label"],
            "values":   [round(float(v), 2) for v in new_parent_vals],
            "children": new_children,
        })

    # Recompute Overall from updated parent rows
    parents = [r for r in new_rows if r["label"] != "Overall"]
    if parents:
        n = len(parents[0]["values"])
        new_overall = [
            round(sum(float(r["values"][i]) for r in parents), 2) for i in range(n)
        ]
        new_rows = [
            {"label": "Overall", "values": new_overall} if r["label"] == "Overall" else r
            for r in new_rows
        ]

    return new_rows


def _apply_table_edits(saved_tabs: dict, selected_tab: str, selected_metric: str,
                        selected_view: str, selected_table_view: str,
                        edited_rows: list, edited_label: str | None) -> dict:
    """
    Deep-copy event_tabs, then patch one (tab, metric, view, table_view):
    1. Convert frontend rows to plain dicts.
    2. Auto-detect which cell changed (diff against stored rows) if edited_label not sent.
    3. Redistribute sibling rows so totals stay consistent.
    4. If a flat view was edited, propagate changes into the companion hierarchy view.
    """
    tabs = copy.deepcopy(saved_tabs)

    def _get_view(table_view_key):
        return (
            tabs
            .get(selected_tab, {})
            .get("metrics_views", {})
            .get(selected_metric, {})
            .get(selected_view, {})
            .get(table_view_key)
        )

    target = _get_view(selected_table_view)
    if target is None:
        return tabs

    def _row_to_dict(row):
        d = {"label": row.label, "values": [round(float(v), 2) for v in row.values]}
        if row.children:
            d["children"] = [_row_to_dict(c) for c in row.children]
        return d

    rows = [_row_to_dict(r) for r in edited_rows]

    # Auto-detect which cell was edited when the frontend doesn't send edited_label
    if not edited_label:
        old_rows = target["table"].get("rows", [])
        edited_label = _detect_edited_label(old_rows, rows)

    # Redistribute siblings to maintain totals
    if edited_label:
        is_share = selected_metric.endswith("_share")
        if " - " in edited_label:
            rows = _redistribute_hierarchy(rows, edited_label)
        else:
            rows = _redistribute_flat(rows, edited_label, is_share)

    _update_view(target, rows)

    is_flat_edit = edited_label and " - " not in edited_label
    is_hier_edit = edited_label and " - " in edited_label

    # Flat edit → propagate new totals down into companion hierarchy
    if is_flat_edit:
        companion_key = _FLAT_TO_HIER.get(selected_table_view)
        if companion_key:
            companion = _get_view(companion_key)
            if companion:
                hier_rows = _propagate_flat_to_hierarchy(companion["table"]["rows"], rows)
                _update_view(companion, hier_rows)

    # Hierarchy edit → propagate child totals back up into companion flat view
    if is_hier_edit:
        flat_key = _HIER_TO_FLAT.get(selected_table_view)
        if flat_key:
            flat_view = _get_view(flat_key)
            if flat_view:
                new_flat_rows = _propagate_hierarchy_to_flat(flat_view["table"]["rows"], rows)
                _update_view(flat_view, new_flat_rows)

    # ── Cross-tab propagation ─────────────────────────────────────────────────
    # Payer totals (payer_event.payer_level) are the PARENT rows in
    # product_event.payer_product_level. Any payer_event edit that changes
    # payer totals must be mirrored in product_event so both tabs stay in sync.
    _PAYER_TO_PRODUCT_METRIC = {
        "payer_share":  "product_share",
        "payer_volume": "product_volume",
    }
    if selected_tab == "payer_event":
        cross_metric = _PAYER_TO_PRODUCT_METRIC.get(selected_metric)
        if cross_metric:
            # Read the (possibly updated) payer_level rows — updated either
            # directly (flat edit) or via hier→flat propagation above.
            updated_payer_flat = _get_view("payer_level")
            if updated_payer_flat:
                payer_flat_rows = updated_payer_flat["table"]["rows"]

                def _cross_view(table_key):
                    return (
                        tabs
                        .get("product_event", {})
                        .get("metrics_views", {})
                        .get(cross_metric, {})
                        .get(selected_view, {})
                        .get(table_key)
                    )

                # Update payer parent rows in product_event.payer_product_level
                prod_hier = _cross_view("payer_product_level")
                if prod_hier:
                    new_prod_hier_rows = _update_hierarchy_parents_from_flat(
                        prod_hier["table"]["rows"], payer_flat_rows
                    )
                    _update_view(prod_hier, new_prod_hier_rows)

                    # Recompute product_level flat (sum products across payers)
                    prod_flat = _cross_view("product_level")
                    if prod_flat:
                        new_prod_flat_rows = _propagate_hierarchy_to_flat(
                            prod_flat["table"]["rows"], new_prod_hier_rows
                        )
                        _update_view(prod_flat, new_prod_flat_rows)

    return tabs


def refresh_market_events(payload: RefreshRequest) -> dict:
    """
    Called when the user edits a table cell.
    Loads the current event_tabs (from BASE computation or saved scenario),
    patches the edited (tab, metric, view, table_view) in-place,
    and returns the same structure as apply_filters.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta = payload.ta_name
        sf = payload.selected_filter

        payers    = get_payers(cur)
        products  = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        configs = get_configs_for_selection(cur, ta, sf.payers, sf.products)
        min_start, forecast_start_date, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year,   to_month   = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            available_months, forecast_start_date = _available_months_fallback(cur, ta)

        if sf.scenario_name.upper() == "BASE":
            saved_event_tabs = _compute_base_event_tabs(cur, ta, sf.model_dump(), forecast_start_date)
        else:
            saved_event_tabs = load_scenario_event_tabs(cur, sf.scenario_name)

        internal_metric = _resolve_metric_key(payload.selected_tab, payload.selected_metric)
        saved_event_tabs = _apply_table_edits(
            saved_event_tabs,
            payload.selected_tab,
            internal_metric,
            payload.selected_view,
            payload.selected_table_view,
            payload.edited_table_rows,
            payload.edited_label,
        )

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
            "products":            products,
            "payers":              payers,
            "impact_payers":       ["Overall"],
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                [],
        }

        event_tabs = _merge_config_with_saved_data(
            payer_event_config, product_event_config, overall_event_config, saved_event_tabs
        )

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
# Save scenario
# ---------------------------------------------------------------------------

def save_market_events(payload: SaveMarketEventsRequest) -> dict:
    """
    POST /save-scenario — persist the current event_tabs for a named scenario.
    Rejects with ValueError if the scenario name is 'Base'.
    Uses ON CONFLICT (scenario_name) DO UPDATE, so re-saving overwrites the existing record.
    """
    name = payload.scenario_name.strip()
    if name.lower() == "base":
        raise ValueError("Cannot save as 'Base'. Please provide a different scenario name.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        sf = payload.selected_filter
        save_market_events_scenario(
            cur,
            scenario_name=name,
            ta=payload.ta_name,
            selected_filter=sf.model_dump(),
            event_tabs=payload.event_tabs,
        )
        conn.commit()

        all_scenarios = get_scenarios(cur)
        if "Base" not in all_scenarios:
            all_scenarios = ["Base"] + all_scenarios
        else:
            all_scenarios.remove("Base")
            all_scenarios = ["Base"] + all_scenarios

        return {
            "message":             "Scenario saved successfully.",
            "scenario_name":       name,
            "available_scenarios": all_scenarios,
        }
    finally:
        cur.close()
        conn.close()
