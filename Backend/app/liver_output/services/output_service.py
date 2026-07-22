from app.db.connection import get_connection
from app.liver_output.repository.output_repo import (
    get_payers,
    get_products,
    get_scenarios,
    get_distinct_months,
    get_all_configs_for_ta,
    get_volume_by_product_payer,
    get_scenario_chart_data,
    load_filter_state,
    save_filter_state,
)
from app.liver_output.helpers.date_helpers import (
    parse_year_month,
    generate_month_range,
    to_month_label,
    add_months,
)
from app.liver_output.helpers.data_helpers import (
    organize_raw_data,
    get_volume,
    forecast_fill,
    compute_share,
    to_month_key,
    aggregate_monthly_to_yearly,
    build_chart,
    build_flat_table,
    build_hierarchy_row,
    build_hierarchy_table,
)

DEFAULT_FORECAST_MONTHS = 12

METRIC_FILTERS = [
    {"label": "Payer Volume", "value": "payer_volume"},
    {"label": "Payer Share",  "value": "payer_share"},
]
VIEW_OPTIONS = [
    {"label": "Monthly", "value": "monthly"},
    {"label": "Yearly",  "value": "yearly"},
]
TARGET_METRIC_LABELS = {
    "payer_volume": "Payer Volume",
    "payer_share":  "Payer Share (%)",
}


# ---------------------------------------------------------------------------
# Helper: compute date range from liver_configurations config list
# ---------------------------------------------------------------------------

def _get_date_range_from_configs(configs: list) -> tuple:
    """
    Given a list of config dicts from liver_configurations, return two dates:

    - min_start: min(train_start_date) across all configs
    - max_end:   max(train_end_date + forecast_periods)

    Returns (None, None) if configs list is empty.
    """
    if not configs:
        return None, None

    starts        = []
    forecast_ends = []

    for config in configs:
        train_start = config.get("train_start_date", "")
        train_end   = config.get("train_end_date", "")
        periods     = int(config.get("forecast_periods", DEFAULT_FORECAST_MONTHS))

        if train_start:
            starts.append(train_start[:10])

        if train_end:
            ty, tm = parse_year_month(train_end[:10])
            fy, fm = add_months(ty, tm, periods)
            forecast_ends.append(to_month_label(fy, fm))

    if not starts or not forecast_ends:
        return None, None

    min_start = min(starts)
    max_end   = max(forecast_ends)

    return min_start, max_end


def _available_months_fallback(cur, ta: str) -> list:
    """
    Fallback when no liver config exists: derive date range from transaction_data.
    """
    month_rows = get_distinct_months(cur, ta)
    if not month_rows:
        raise ValueError(f"No transaction data or config found for TA: {ta}")

    min_year, min_month = month_rows[0]
    max_year, max_month = month_rows[-1]

    fcast_end_year, fcast_end_month = add_months(max_year, max_month, DEFAULT_FORECAST_MONTHS)
    return generate_month_range(min_year, min_month, fcast_end_year, fcast_end_month)


# ---------------------------------------------------------------------------
# Helper: always include BASE at the top of the scenarios list
# ---------------------------------------------------------------------------

def _get_scenarios_with_base(cur) -> list:
    saved = get_scenarios(cur)
    saved = [s for s in saved if s.upper() != "BASE"]
    return ["BASE"] + saved


# ---------------------------------------------------------------------------
# GET /filters
# ---------------------------------------------------------------------------

def get_output_filters(ta: str = "HCV") -> dict:
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
        min_start, max_end = _get_date_range_from_configs(configs)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year,   to_month   = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            available_months = _available_months_fallback(cur, ta)
            min_start = available_months[0]
            max_end   = available_months[-1]

        saved_filter = load_filter_state(cur, ta)
        selected_filter = saved_filter or {
            "scenario_names": ["BASE"],
            "payers":         [payers[0]]   if payers   else [],
            "products":       [products[0]] if products else [],
            "start_date":     min_start,
            "end_date":       max_end,
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

def _get_forecast_start_from_configs(configs: list) -> str | None:
    """Earliest month after the latest train_end_date across configs, or None if no configs."""
    train_ends = [c["train_end_date"][:10] for c in configs if c.get("train_end_date")]
    if not train_ends:
        return None
    ty, tm = parse_year_month(max(train_ends))
    fy, fm = add_months(ty, tm, 1)
    return to_month_label(fy, fm)


def _is_base(scenario_name: str) -> bool:
    return scenario_name.strip().upper() == "BASE"


def _cube_from_saved_scenario(chart_data: dict, scenario_name: str, payers: list, products: list) -> dict:
    """
    Reshape a saved scenario's chart_data into the same {(year, month): {product: {payer:
    volume}}} cube shape used for Base, by pulling raw cell volumes out of its
    market_analysis.payer_product hierarchy tab (rows = payers, each row's children =
    products, each child's values = one volume per month).

    Only raw volume numbers are extracted — never chart_data's own pre-computed
    percentages, since this module's share convention (% of grand total at every
    level) differs from the Liver Model Input screen's (% of parent).

    Scenarios saved by the older Liver Model Input flow key this data as
    "market_volume"; newer saves (from an updated Save Scenario flow) key it as
    "payer_volume". Both are accepted.
    """
    try:
        payer_product = chart_data["market_analysis"]["payer_product"]
        volume_data = payer_product.get("payer_volume") or payer_product["market_volume"]
        monthly = volume_data["monthly"]
        months = monthly["chart"]["months"]
        payer_rows = monthly["table"]["rows"]
    except (KeyError, TypeError):
        raise ValueError(
            f"Scenario '{scenario_name}' does not have the expected saved data shape "
            f"(market_analysis.payer_product) and cannot be used for comparison."
        )

    month_tuples = [(int(m[:4]), int(m[5:7])) for m in months]
    wanted_payers = set(payers)
    wanted_products = set(products)

    raw_rows = []
    for payer_row in payer_rows:
        payer = payer_row.get("label")
        if payer not in wanted_payers:
            continue
        for child in payer_row.get("children", []):
            product = child.get("label")
            if product not in wanted_products:
                continue
            for (y, m), v in zip(month_tuples, child.get("values", [])):
                raw_rows.append((y, m, product, payer, v))

    return organize_raw_data(raw_rows)


def _scenario_cube(cur, ta: str, scenario_name: str, from_year: int, from_month: int,
                    to_year: int, to_month: int, payers: list, products: list) -> dict:
    """
    Returns an {(year, month): {product: {payer: volume}}} cube for one scenario.

    'Base'/'BASE' is always computed fresh from transaction_data. Any other name
    is looked up in raw_liver.liver_scenarios (shared with the Liver Model Input
    and Market Events screens) and its saved chart_data is reshaped into this
    same cube format.
    """
    if _is_base(scenario_name):
        raw_rows = get_volume_by_product_payer(
            cur, ta, from_year, from_month, to_year, to_month, payers=payers, products=products
        )
        return organize_raw_data(raw_rows)

    chart_data = get_scenario_chart_data(cur, scenario_name)
    if chart_data is None:
        raise ValueError(f"Scenario '{scenario_name}' was not found.")
    return _cube_from_saved_scenario(chart_data, scenario_name, payers, products)


def _round_preserving_sum(values: list, target: int) -> list:
    """
    Round each value to an int such that the results sum to exactly `target`
    (largest-remainder / Hamilton apportionment method), instead of rounding
    each one independently — which can drift ±1 from the target once summed
    (e.g. four 1.4s independently round to 1 each, summing to 4, not 6).
    """
    floors = [int(v) for v in values]
    remainder = target - sum(floors)
    result = list(floors)
    n = len(values)
    if remainder > 0:
        order = sorted(range(n), key=lambda i: values[i] - floors[i], reverse=True)
        for i in range(min(remainder, n)):
            result[order[i]] += 1
    elif remainder < 0:
        order = sorted(range(n), key=lambda i: values[i] - floors[i])
        for i in range(min(-remainder, n)):
            result[order[i]] -= 1
    return result


def _build_scenario_aggregates(cube: dict, month_tuples: list, forecast_start_index: int,
                                payers: list, products: list) -> dict:
    """
    Compute the grand total and every (product, payer) cell for one scenario, all
    consistent with each other AND with the Liver Model Input / Market Events
    screens' Base numbers.

    The grand total is forecast top-down: ETS fit directly to the total's own
    history (via forecast_fill), exactly like Model Input's Tab 1 (Total Market
    Volume) and Market Events' Overall Payer Volume both do. Fitting ETS
    independently per cell and summing up (the previous approach here) does NOT
    reproduce that number — ETS is not linear, so sum(ETS(part)) != ETS(sum(parts)).

    Each cell's forecast is then allocated as its historical share of the grand
    total (real per-cell forecast values — e.g. from a reshaped saved scenario —
    are kept as-is instead), and rescaled so cells sum exactly back to the SAME
    top-down total for every forecast month, before rounding once at the cell
    level. Every coarser aggregate (per-product, per-payer) is then derived by
    summing those already-rounded cells, which is what keeps every parent and
    the grand total exactly consistent with their children in every tab.
    """
    n          = len(month_tuples)
    n_forecast = n - forecast_start_index

    total_raw     = [get_volume(cube, y, m) for y, m in month_tuples]
    total_history = total_raw[:forecast_start_index]
    total_forecast = forecast_fill(total_history, total_raw[forecast_start_index:])

    raw_cells = {}
    for product in products:
        for payer in payers:
            raw = [get_volume(cube, y, m, product, payer) for y, m in month_tuples]
            history = raw[:forecast_start_index]
            if n_forecast == 0:
                raw_cells[(product, payer)] = history
                continue

            fcast_real = raw[forecast_start_index:]
            shares = [
                history[i] / total_history[i] for i in range(len(history)) if total_history[i] > 0
            ]
            avg_share = sum(shares) / len(shares) if shares else 0.0
            allocated = [avg_share * total_forecast[i] for i in range(n_forecast)]
            forecast = [v if v > 0 else allocated[i] for i, v in enumerate(fcast_real)]
            raw_cells[(product, payer)] = history + forecast

    # Rescale each forecast month's (unrounded) cells to sum exactly to that
    # month's top-down total, then round every cell for that month TOGETHER
    # via largest-remainder rounding, so they sum to exactly round(total) —
    # not just close to it (see _round_preserving_sum).
    cell_keys = list(raw_cells.keys())
    cells = {key: [round(v) for v in raw_cells[key][:forecast_start_index]] for key in cell_keys}
    for i in range(n_forecast):
        idx = forecast_start_index + i
        month_sum = sum(raw_cells[key][idx] for key in cell_keys)
        month_values = [raw_cells[key][idx] for key in cell_keys]
        if month_sum > 0:
            scale = total_forecast[i] / month_sum
            month_values = [v * scale for v in month_values]
        rounded = _round_preserving_sum(month_values, round(total_forecast[i]))
        for key, v in zip(cell_keys, rounded):
            cells[key].append(v)

    by_product = {
        product: [sum(cells[(product, payer)][i] for payer in payers) for i in range(n)]
        for product in products
    }
    by_payer = {
        payer: [sum(cells[(product, payer)][i] for product in products) for i in range(n)]
        for payer in payers
    }

    # History: derive from summing rounded cells (bottom-up, exact — it's real
    # data, so there's no ETS-methodology mismatch to worry about here, only
    # rounding, and this is what keeps history consistent with the other tabs).
    # Forecast: the independently top-down-computed number (matches Model Input
    # / Market Events); cells were already rescaled above to sum to it almost
    # exactly (± a possible 1-unit rounding artifact, same as any independently
    # rounded percentage/total — negligible next to the values involved).
    total_history_from_cells = [sum(by_product[product][i] for product in products) for i in range(forecast_start_index)]
    total = total_history_from_cells + [round(v) for v in total_forecast]

    return {"cells": cells, "by_product": by_product, "by_payer": by_payer, "total": total}


def _build_distribution_tab(aggregates: dict, scenario_names: list, month_tuples: list, month_keys: list,
                             forecast_start_index: int, year_labels: list, yearly_fsi: int,
                             entities: list = None, agg_key: str = None) -> dict:
    """
    Build one flat tab: total_market_volume when entities is empty/None (one row/series
    per scenario, the grand total), otherwise payer_distribution / product_distribution
    (a "Grand Total" row plus one row per entity, per scenario). agg_key selects
    "by_payer" or "by_product" from each scenario's aggregates.
    """
    per_scenario = {}
    for scenario in scenario_names:
        agg = aggregates[scenario]
        # Already int (rounded at the cell level in _build_scenario_aggregates); no
        # further rounding here — that's what keeps rows summing to the grand total.
        total_vol = agg["total"]
        entity_vols = {entity: agg[agg_key][entity] for entity in entities} if entities else {}
        per_scenario[scenario] = (total_vol, entity_vols)

    def _yearly(monthly_vals):
        # aggregate_monthly_to_yearly's sum accumulator seeds at 0.0, so even
        # summing ints yields a float (e.g. 4880.0) — round() here just cleans
        # that back to int; it does not change the value (ints sum exactly).
        _, summed, _ = aggregate_monthly_to_yearly(month_tuples, monthly_vals, forecast_start_index)
        return [round(v) for v in summed]

    result = {}
    for metric in ("payer_volume", "payer_share"):
        target_metric = TARGET_METRIC_LABELS[metric]
        result[metric] = {}
        for view in ("monthly", "yearly"):
            is_monthly    = view == "monthly"
            header_key    = "months" if is_monthly else "years"
            header_labels = month_keys if is_monthly else year_labels
            fsi           = forecast_start_index if is_monthly else yearly_fsi

            chart_series = []
            table_rows   = []

            for scenario in scenario_names:
                total_vol, entity_vols = per_scenario[scenario]
                total_view = total_vol if is_monthly else _yearly(total_vol)
                total_metric_vals = (
                    total_view if metric == "payer_volume"
                    else [compute_share(v, v) for v in total_view]
                )

                if not entities:
                    chart_series.append((scenario, total_metric_vals))
                    table_rows.append((f"Grand Total ({scenario} Scenario)", total_metric_vals))
                    continue

                table_rows.append((f"Grand Total ({scenario} Scenario)", total_metric_vals))
                for entity in entities:
                    entity_view = entity_vols[entity] if is_monthly else _yearly(entity_vols[entity])
                    entity_metric_vals = (
                        entity_view if metric == "payer_volume"
                        else [compute_share(ev, tv) for ev, tv in zip(entity_view, total_view)]
                    )
                    chart_series.append((f"{entity} ({scenario})", entity_metric_vals))
                    table_rows.append((f"{entity} ({scenario} Scenario)", entity_metric_vals))

            result[metric][view] = {
                "chart": build_chart(header_key, header_labels, fsi, chart_series),
                "table": build_flat_table(["Metric"] + header_labels, table_rows, target_metric),
            }

    return result


def _build_hierarchy_tab(aggregates: dict, scenario_names: list, month_tuples: list, month_keys: list,
                          forecast_start_index: int, year_labels: list, yearly_fsi: int,
                          parents: list, children: list, parent_agg_key: str, cell_key) -> dict:
    """
    Build one 3-level hierarchical tab: Grand Total (per scenario) -> parent entity -> child
    entity (leaf). Percentages at every level are computed against that scenario's grand
    total, not the immediate parent's total — matching the target contract (this differs
    from the existing Liver Model Input screen's payer_product/product_payer tabs, which
    use % of parent).

    parent_agg_key: "by_product" or "by_payer" — which aggregate holds the parent rows.
    cell_key(parent, child): maps to the (product, payer) tuple used to key aggregates["cells"].
    """
    per_scenario = {}
    for scenario in scenario_names:
        agg = aggregates[scenario]
        # Already int (rounded at the cell level in _build_scenario_aggregates); no
        # further rounding here — that's what keeps children summing to parents.
        total_vol   = agg["total"]
        parent_vols = {parent: agg[parent_agg_key][parent] for parent in parents}
        cell_vols = {
            (parent, child): agg["cells"][cell_key(parent, child)]
            for parent in parents for child in children
        }
        per_scenario[scenario] = (total_vol, parent_vols, cell_vols)

    def _yearly(monthly_vals):
        # See _build_distribution_tab._yearly — same float-accumulator cleanup.
        _, summed, _ = aggregate_monthly_to_yearly(month_tuples, monthly_vals, forecast_start_index)
        return [round(v) for v in summed]

    result = {}
    for metric in ("payer_volume", "payer_share"):
        target_metric = TARGET_METRIC_LABELS[metric]
        result[metric] = {}
        for view in ("monthly", "yearly"):
            is_monthly    = view == "monthly"
            header_key    = "months" if is_monthly else "years"
            header_labels = month_keys if is_monthly else year_labels
            fsi           = forecast_start_index if is_monthly else yearly_fsi

            chart_series = []
            rows = []
            for scenario in scenario_names:
                total_vol, parent_vols, cell_vols = per_scenario[scenario]
                total_view = total_vol if is_monthly else _yearly(total_vol)

                def _metric_vals(view_vals, _total_view=total_view):
                    return view_vals if metric == "payer_volume" else [
                        compute_share(v, t) for v, t in zip(view_vals, _total_view)
                    ]

                parent_rows = []
                for parent in parents:
                    child_rows = []
                    for child in children:
                        cell_view = cell_vols[(parent, child)] if is_monthly else _yearly(cell_vols[(parent, child)])
                        child_rows.append(build_hierarchy_row(child, _metric_vals(cell_view), target_metric))

                    parent_view = parent_vols[parent] if is_monthly else _yearly(parent_vols[parent])
                    parent_metric_vals = _metric_vals(parent_view)
                    parent_rows.append(
                        build_hierarchy_row(parent, parent_metric_vals, target_metric, children=child_rows)
                    )
                    # One chart line per parent per scenario — the same grain as the
                    # sibling flat tab's chart (payer_product ~ payer_distribution,
                    # product_payer ~ product_distribution). The table above already
                    # carries the child-level drill-down; plotting all parent x child x
                    # scenario combinations here would be unreadable.
                    chart_series.append((f"{parent} ({scenario})", parent_metric_vals))

                rows.append(
                    build_hierarchy_row(
                        f"Grand Total ({scenario} Scenario)", _metric_vals(total_view), target_metric,
                        children=parent_rows,
                    )
                )

            result[metric][view] = {
                "chart": build_chart(header_key, header_labels, fsi, chart_series),
                "table": build_hierarchy_table(["Metric"] + header_labels, rows),
            }

    return result


def _slice_aggregates(aggregates: dict, offset: int) -> dict:
    """
    Trim every series in one scenario's aggregates down to the display window,
    dropping the first `offset` months that were only fetched to give ETS
    enough history to train on (see apply_output_filters).
    """
    return {
        "cells":      {k: v[offset:] for k, v in aggregates["cells"].items()},
        "by_product": {k: v[offset:] for k, v in aggregates["by_product"].items()},
        "by_payer":   {k: v[offset:] for k, v in aggregates["by_payer"].items()},
        "total":      aggregates["total"][offset:],
    }


def apply_output_filters(payload) -> dict:
    """
    Called when the user clicks Apply Filter.
    Saves the filter selection, then returns the full output_tabs (all 5 tabs,
    both metrics, both views) for the selected scenarios.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta             = payload.ta
        scenario_names = payload.scenario_names
        payers         = payload.payers
        products       = payload.products
        start_date     = payload.start_date
        end_date       = payload.end_date

        from_year, from_month = parse_year_month(start_date)
        to_year,   to_month   = parse_year_month(end_date)
        month_iso_list = generate_month_range(from_year, from_month, to_year, to_month)
        month_tuples   = [(int(m[:4]), int(m[5:7])) for m in month_iso_list]
        month_keys     = [to_month_key(y, m) for y, m in month_tuples]

        configs = get_all_configs_for_ta(cur, ta)
        forecast_start_date = _get_forecast_start_from_configs(configs)
        if forecast_start_date:
            fy, fm = parse_year_month(forecast_start_date)
            forecast_start_index = next(
                (i for i, (y, m) in enumerate(month_tuples) if (y, m) >= (fy, fm)),
                len(month_tuples),
            )
        else:
            forecast_start_index = len(month_tuples)

        year_labels, _, yearly_fsi = aggregate_monthly_to_yearly(
            month_tuples, [0.0] * len(month_tuples), forecast_start_index
        )

        # ETS must be trained on the FULL configured training window, not just
        # whatever range the user happens to be viewing — otherwise a narrower
        # display range would refit ETS on less history and disagree with Model
        # Input / Market Events, which always train on the full config window
        # regardless of display range. Fetch that wider window here purely for
        # fitting, then slice back down to the display range after aggregating.
        wide_min_start, _ = _get_date_range_from_configs(configs)
        if wide_min_start and wide_min_start < start_date:
            train_from_year, train_from_month = parse_year_month(wide_min_start)
        else:
            train_from_year, train_from_month = from_year, from_month

        wide_month_iso    = generate_month_range(train_from_year, train_from_month, to_year, to_month)
        wide_month_tuples = [(int(m[:4]), int(m[5:7])) for m in wide_month_iso]
        display_offset          = len(wide_month_tuples) - len(month_tuples)
        wide_forecast_start_index = forecast_start_index + display_offset

        aggregates = {}
        for scenario in scenario_names:
            cube = _scenario_cube(
                cur, ta, scenario, train_from_year, train_from_month, to_year, to_month, payers, products
            )
            wide_aggregates = _build_scenario_aggregates(
                cube, wide_month_tuples, wide_forecast_start_index, payers, products
            )
            aggregates[scenario] = _slice_aggregates(wide_aggregates, display_offset)

        common_args = (month_tuples, month_keys, forecast_start_index, year_labels, yearly_fsi)

        output_tabs = {
            "total_market_volume": _build_distribution_tab(aggregates, scenario_names, *common_args),
            "payer_distribution": _build_distribution_tab(
                aggregates, scenario_names, *common_args, entities=payers, agg_key="by_payer"
            ),
            "product_distribution": _build_distribution_tab(
                aggregates, scenario_names, *common_args, entities=products, agg_key="by_product"
            ),
            "product_payer": _build_hierarchy_tab(
                aggregates, scenario_names, *common_args,
                parents=products, children=payers, parent_agg_key="by_product",
                cell_key=lambda p, c: (p, c),
            ),
            "payer_product": _build_hierarchy_tab(
                aggregates, scenario_names, *common_args,
                parents=payers, children=products, parent_agg_key="by_payer",
                cell_key=lambda p, c: (c, p),
            ),
        }

        selected_filter = {
            "ta":             ta,
            "scenario_names": scenario_names,
            "payers":         payers,
            "products":       products,
            "start_date":     start_date,
            "end_date":       end_date,
        }
        save_filter_state(cur, ta, selected_filter)
        conn.commit()

        return {
            "selected_filter": selected_filter,
            "metric_filters":  METRIC_FILTERS,
            "selected_metric": payload.selected_metric,
            "view_options":    VIEW_OPTIONS,
            "selected_view":   payload.selected_view,
            "output_tabs":     output_tabs,
        }
    finally:
        cur.close()
        conn.close()
