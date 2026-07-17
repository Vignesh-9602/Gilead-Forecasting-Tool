"""
Run Calculation service for HCV Market Events.

Applies user-configured event curves (ramp-up / S-curve / etc.) to the BASE
transaction data and returns updated metrics_views for all three tabs.

Curve math is reused from the HIV team's Events_Calculation module.
Data access uses the existing liver_market_events repository and helpers.
"""

import copy
from datetime import date as date_type

from app.db.connection import get_connection
from app.hiv_treat.routes.Events_Calculation import (
    CoverageInput, CurveType, EventInput, EventScope, ImpactedEntity,
    compute_event_forecast,
)
from app.liver_market_events.helpers.data_helpers import (
    flat_forecast,
    get_volume,
    organize_raw_data,
)
from app.liver_market_events.helpers.date_helpers import (
    add_months,
    generate_month_range,
    parse_year_month,
    to_month_label,
)
from app.liver_market_events.repository.market_events_repo import (
    get_configs_for_selection,
    get_payers,
    get_products,
    get_volume_by_product_payer,
)
from app.liver_market_events.services.market_events_service import (
    CURVE_TYPES,
    DEFAULT_FORECAST_MONTHS,
    METRIC_FILTERS,
    _available_months_fallback,
    _build_overall_event_metrics,
    _build_payer_event_metrics,
    _build_product_event_metrics,
    _get_date_range_from_configs,
    _get_scenarios_with_base,
    _merge_config_with_saved_data,
)


# ---------------------------------------------------------------------------
# Data pre-population
# ---------------------------------------------------------------------------

def _fill_forecast_data(data: dict, month_tuples: list, forecast_start_index: int) -> None:
    """
    Pre-populate forecast months in `data` with flat_forecast values for every
    (product, payer) pair that appears in the history window.

    Without this, applying event curves to months not yet in transaction_data
    would silently have no effect (the key simply wouldn't exist in the dict).
    Modifies `data` in-place.
    """
    history_months = month_tuples[:forecast_start_index]
    forecast_months = month_tuples[forecast_start_index:]
    if not forecast_months:
        return

    pairs: set = set()
    for (y, m) in history_months:
        for prod, payer_dict in data.get((y, m), {}).items():
            for payer in payer_dict:
                pairs.add((prod, payer))

    for (prod, payer) in pairs:
        hist_vals = [
            data.get((y, m), {}).get(prod, {}).get(payer, 0.0)
            for (y, m) in history_months
        ]
        fcast_val = flat_forecast(hist_vals)
        if fcast_val <= 0:
            continue
        for (y, m) in forecast_months:
            data.setdefault((y, m), {}).setdefault(prod, {})
            if data[(y, m)][prod].get(payer, 0.0) <= 0:
                data[(y, m)][prod][payer] = fcast_val


def _recompute_total_all(data: dict, month_tuples: list) -> list:
    return [
        sum(
            v
            for prod_dict in data.get((y, m), {}).values()
            for v in prod_dict.values()
            if v > 0
        )
        for (y, m) in month_tuples
    ]


# ---------------------------------------------------------------------------
# Delta application helpers
# ---------------------------------------------------------------------------

def _apply_payer_delta(data: dict, y: int, m: int,
                       payer: str, show_products: list, delta_vol: float) -> None:
    """
    Scale all (product, payer) cells for `payer` so the payer's total volume
    changes by `delta_vol`. Proportional scaling preserves the product mix.
    """
    ym = data.get((y, m), {})
    current = sum(ym.get(prod, {}).get(payer, 0.0) for prod in show_products)
    target = max(0.0, current + delta_vol)
    if current <= 0:
        return
    scale = target / current
    for prod in show_products:
        if payer in ym.get(prod, {}):
            ym[prod][payer] *= scale


def _apply_product_delta(data: dict, y: int, m: int,
                         product: str, delta_vol: float) -> None:
    """
    Scale all (product, payer) cells for `product` so the product's total volume
    changes by `delta_vol`. Proportional scaling preserves the payer mix.
    """
    ym = data.get((y, m), {})
    prod_data = ym.get(product, {})
    current = sum(prod_data.values())
    target = max(0.0, current + delta_vol)
    if current <= 0:
        return
    scale = target / current
    for payer in prod_data:
        prod_data[payer] *= scale


# ---------------------------------------------------------------------------
# EventInput builder
# ---------------------------------------------------------------------------

def _build_event_input(event_row: dict, tab: str) -> EventInput | None:
    """
    Build a pydantic EventInput from one impact_curve_configuration row.
    Returns None if required fields are missing or invalid.

    The curve math in compute_event_forecast is independent of HCV/HIV context;
    we use EventScope.PRODUCT_EVENT as a valid non-overall scope so validation
    passes, with a dummy `context` string that the curve engine never reads.
    """
    try:
        start_dt = date_type.fromisoformat(str(event_row.get("start_date", ""))[:10])
    except (ValueError, TypeError):
        return None

    peak_pct = float(event_row.get("peak_percent", 0.0))
    duration = max(1, int(event_row.get("months", 12)))
    factor = float(event_row.get("factor", 1.0))

    try:
        curve_type = CurveType(event_row.get("curve_type", "Linear"))
    except ValueError:
        curve_type = CurveType.LINEAR

    if tab == "payer_event":
        payers_list = event_row.get("payers") or []
        selected = payers_list[0] if payers_list else None
        impacted_names = [n for n in (event_row.get("impacted_payers") or []) if n != selected]
    elif tab == "product_event":
        products_list = event_row.get("products") or []
        selected = products_list[0] if products_list else None
        impacted_names = [n for n in (event_row.get("impacted_products") or []) if n != selected]
    else:
        selected = None
        impacted_names = []

    if tab != "overall_event" and not selected:
        return None

    # Normalise weights to sum exactly to 100 so the validator passes
    source_pcts = event_row.get("source_percentages") or {}
    raw_w = [float(source_pcts.get(n, 0.0)) for n in impacted_names]
    total_w = sum(raw_w)
    if total_w > 0:
        weights = [w / total_w * 100.0 for w in raw_w]
    elif impacted_names:
        eq = 100.0 / len(impacted_names)
        weights = [eq] * len(impacted_names)
    else:
        weights = []

    if weights:
        weights[-1] = round(100.0 - sum(weights[:-1]), 4)

    impacted_entities = (
        [ImpactedEntity(name=n, weight=w) for n, w in zip(impacted_names, weights)]
        or None
    )

    coverage = None
    if (
        event_row.get("coverage_peak_percent") is not None
        and event_row.get("coverage_peak_months") is not None
    ):
        try:
            cov_ct = CurveType(event_row.get("coverage_curve_type") or event_row.get("curve_type", "Linear"))
        except ValueError:
            cov_ct = CurveType.LINEAR
        coverage = CoverageInput(
            curve_type=cov_ct,
            factor=float(event_row.get("coverage_factor", 1.0)),
            peak_pct=float(event_row["coverage_peak_percent"]),
            peak_months=int(event_row["coverage_peak_months"]),
        )

    scope = EventScope.OVERALL_EVENT if tab == "overall_event" else EventScope.PRODUCT_EVENT

    try:
        return EventInput(
            event_name=event_row.get("event_name", "Event"),
            event_scope=scope,
            scenario_name="BASE",
            ta_name="HCV",
            start_date=start_dt,
            peak_pct=peak_pct,
            duration_months=duration,
            curve_type=curve_type,
            factor=factor,
            coverage=coverage,
            impacted_entities=impacted_entities,
            context="context" if scope != EventScope.OVERALL_EVENT else None,
            selected_entity=selected,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Event application
# ---------------------------------------------------------------------------

def _apply_events_to_data(
    data: dict,
    month_tuples: list,
    forecast_start_index: int,
    total_all: list,
    event_rows: list,
    tab: str,
    show_products: list,
    show_payers: list,
) -> list:
    """
    Apply each event row's curve to `data` (forecast months only).
    Curves represent percentage-point share changes; these are converted to
    volume deltas using the per-month total volume and applied proportionally.
    Modifies `data` in-place. Returns the updated `total_all` list.
    """
    month_iso = [f"{y:04d}-{m:02d}-01" for y, m in month_tuples]

    for event_row in event_rows:
        event_input = _build_event_input(event_row, tab)
        if event_input is None:
            continue

        result = compute_event_forecast(event_input)

        selected_deltas = dict(zip(result.months, result.selected_curve))
        impacted_deltas = {
            entity: dict(zip(result.months, deltas))
            for entity, deltas in (result.impacted_curves or {}).items()
        }

        for i in range(forecast_start_index, len(month_tuples)):
            y, m = month_tuples[i]
            month_str = month_iso[i]
            total_vol = total_all[i]
            if total_vol <= 0:
                continue

            if tab == "overall_event":
                delta_share = selected_deltas.get(month_str, 0.0)
                if delta_share == 0.0:
                    continue
                scale = max(0.0, total_vol + delta_share / 100.0 * total_vol) / total_vol
                ym = data.get((y, m), {})
                for prod in ym:
                    for payer in ym[prod]:
                        ym[prod][payer] = max(0.0, ym[prod][payer] * scale)

            elif tab == "payer_event":
                sel_payer = event_input.selected_entity
                delta_share = selected_deltas.get(month_str, 0.0)
                if delta_share != 0.0:
                    _apply_payer_delta(data, y, m, sel_payer, show_products,
                                       delta_share / 100.0 * total_vol)
                for imp, imp_map in impacted_deltas.items():
                    d = imp_map.get(month_str, 0.0)
                    if d != 0.0:
                        _apply_payer_delta(data, y, m, imp, show_products,
                                           d / 100.0 * total_vol)

            elif tab == "product_event":
                sel_prod = event_input.selected_entity
                delta_share = selected_deltas.get(month_str, 0.0)
                if delta_share != 0.0:
                    _apply_product_delta(data, y, m, sel_prod,
                                         delta_share / 100.0 * total_vol)
                for imp, imp_map in impacted_deltas.items():
                    d = imp_map.get(month_str, 0.0)
                    if d != 0.0:
                        _apply_product_delta(data, y, m, imp, d / 100.0 * total_vol)

        # Recompute total after each event so stacked events use the right baseline
        total_all = _recompute_total_all(data, month_tuples)

    return total_all


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_market_events_calculation(payload) -> dict:
    """
    POST /api/liver-market-events/run-calculation

    1. Fetches BASE transaction data for the selected filter.
    2. Applies event curves (from impact_curve_configuration.rows) to the
       active tab's data only.
    3. Rebuilds metrics_views for all three tabs (active tab uses post-event
       data; the other two tabs reflect BASE data unchanged).
    4. Returns the same shape as /apply-filters so the frontend can re-render
       consistently.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta = payload.ta_name
        sf = payload.selected_filter
        tab = payload.selected_tab

        payers = get_payers(cur)
        products = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        configs = get_configs_for_selection(cur, ta, sf.payers, sf.products)
        min_start, forecast_start_date, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year, to_month = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            available_months, forecast_start_date = _available_months_fallback(cur, ta)
            from_year, from_month = parse_year_month(available_months[0])
            to_year, to_month = parse_year_month(available_months[-1])

        fcast_year, fcast_month = parse_year_month(forecast_start_date)

        raw_rows = get_volume_by_product_payer(
            cur, ta, from_year, from_month, to_year, to_month,
            payers=None, products=None,
        )

        month_iso_list = generate_month_range(from_year, from_month, to_year, to_month)
        month_tuples = [(int(s[:4]), int(s[5:7])) for s in month_iso_list]
        chart_headers = month_iso_list

        fcast_iso = to_month_label(fcast_year, fcast_month)
        forecast_start_index = (
            month_iso_list.index(fcast_iso)
            if fcast_iso in month_iso_list
            else len(month_tuples)
        )

        # ── Base data ──────────────────────────────────────────────────────
        base_data = organize_raw_data(raw_rows)

        show_products = sorted({p for ym in base_data.values() for p in ym})
        show_payers = sorted({
            py
            for ym in base_data.values()
            for pd in ym.values()
            for py in pd
        })

        base_total_raw = [get_volume(base_data, y, m) for y, m in month_tuples]
        base_hist = base_total_raw[:forecast_start_index]
        base_fcast_flat = flat_forecast(base_hist)
        base_total_all = base_hist + [
            v if v > 0 else base_fcast_flat
            for v in base_total_raw[forecast_start_index:]
        ]

        # ── Apply events to a deep copy of base data (active tab only) ─────
        event_rows = [
            {**row.model_dump(), "event_id": row.event_id or idx + 1}
            for idx, row in enumerate(payload.impact_curve_configuration.rows)
        ]

        if event_rows:
            mod_data = copy.deepcopy(base_data)
            _fill_forecast_data(mod_data, month_tuples, forecast_start_index)
            # Start from recomputed totals (pre-fill may raise per-series totals above base)
            mod_total = _recompute_total_all(mod_data, month_tuples)
            # Keep history months aligned with base
            mod_total[:forecast_start_index] = list(base_total_all[:forecast_start_index])
            mod_total = _apply_events_to_data(
                mod_data, month_tuples, forecast_start_index,
                mod_total, event_rows, tab,
                show_products, show_payers,
            )
        else:
            mod_data = base_data
            mod_total = base_total_all

        # ── Build metrics_views for every tab ─────────────────────────────
        def _metrics(t: str) -> dict:
            d = mod_data if t == tab else base_data
            tot = mod_total if t == tab else base_total_all

            if t == "payer_event":
                return _build_payer_event_metrics(
                    d, month_tuples, chart_headers, forecast_start_index,
                    tot, show_products, show_payers,
                )
            if t == "product_event":
                return _build_product_event_metrics(
                    d, month_tuples, chart_headers, forecast_start_index,
                    tot, show_products, show_payers,
                )
            return _build_overall_event_metrics(
                month_tuples, chart_headers, forecast_start_index, tot,
            )

        saved_tabs = {
            t: {"metrics_views": _metrics(t)}
            for t in ("payer_event", "product_event", "overall_event")
        }

        # ── Assemble impact_curve_configuration per tab ────────────────────
        payer_event_cfg = {
            "products":            products,
            "payers":              payers,
            "impact_payers":       payers,
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                event_rows if tab == "payer_event" else [],
        }
        product_event_cfg = {
            "products":            products,
            "payers":              payers,
            "impact_products":     products,
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                event_rows if tab == "product_event" else [],
        }
        overall_event_cfg = {
            "products":            products,
            "payers":              payers,
            "impact_payers":       ["Overall"],
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                event_rows if tab == "overall_event" else [],
        }

        event_tabs = _merge_config_with_saved_data(
            payer_event_cfg, product_event_cfg, overall_event_cfg, saved_tabs
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
