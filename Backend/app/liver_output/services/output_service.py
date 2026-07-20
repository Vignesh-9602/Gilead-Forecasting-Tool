from app.db.connection import get_connection
from app.liver_output.repository.output_repo import (
    get_payers,
    get_products,
    get_scenarios,
    get_distinct_months,
    get_all_configs_for_ta,
    get_volume_by_product_payer,
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
    monthly_values,
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


def _scenario_cube(cur, ta: str, scenario_name: str, from_year: int, from_month: int,
                    to_year: int, to_month: int, payers: list, products: list) -> dict:
    """
    Returns an {(year, month): {product: {payer: volume}}} cube for one scenario.

    Only 'Base'/'BASE' can be computed today — non-Base scenarios need a real
    multi-payer/multi-product save mechanism that doesn't exist yet (the
    existing raw_liver.liver_scenarios rows are single-payer/single-product
    snapshots from the Liver Model Input screen and can't supply this shape).
    """
    if not _is_base(scenario_name):
        raise ValueError(
            f"Scenario '{scenario_name}' is not yet available for comparison — "
            f"only 'Base' can be computed on the Output screen currently."
        )
    raw_rows = get_volume_by_product_payer(
        cur, ta, from_year, from_month, to_year, to_month, payers=payers, products=products
    )
    return organize_raw_data(raw_rows)


def _build_scenario_aggregates(cube: dict, month_tuples: list, forecast_start_index: int,
                                payers: list, products: list) -> dict:
    """
    Compute monthly volume for every (product, payer) cell — each with its own
    independent flat-forecast fallback, rounded to int immediately — then derive
    every coarser aggregate (per-product, per-payer, grand total) by SUMMING those
    already-rounded cells, never via an independent fallback or a fresh rounding
    of its own.

    Rounding at the cell level first (not the parent/total level) is what makes
    this consistent: round(sum(unrounded cells)) is not always equal to
    sum(round(each unrounded cell)) — e.g. four cells of 1.4 sum to 5.6 (rounds to
    6), but each cell individually rounds to 1 (sum of 4). Since cells are the
    finest grain actually displayed (hierarchy leaves), rounding them first and
    summing integers from there guarantees every parent/grand-total exactly
    matches the sum of its children, at every level, in every view.
    """
    n = len(month_tuples)
    cells = {
        (product, payer): [
            round(v)
            for v in monthly_values(cube, month_tuples, forecast_start_index, product=product, payer=payer)
        ]
        for product in products
        for payer in payers
    }
    by_product = {
        product: [sum(cells[(product, payer)][i] for payer in payers) for i in range(n)]
        for product in products
    }
    by_payer = {
        payer: [sum(cells[(product, payer)][i] for product in products) for i in range(n)]
        for payer in payers
    }
    total = [sum(by_product[product][i] for product in products) for i in range(n)]
    return {"cells": cells, "by_product": by_product, "by_payer": by_payer, "total": total}


def _build_distribution_tab(aggregates: dict, scenario_names: list, month_tuples: list, month_keys: list,
                             forecast_start_index: int, year_labels: list, yearly_fsi: int,
                             entities: list = None, agg_key: str = None) -> dict:
    """
    Build one flat tab: total_payer_volume when entities is empty/None (one row/series
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
            header_labels = month_keys if is_monthly else year_labels
            fsi           = forecast_start_index if is_monthly else yearly_fsi

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
                    parent_rows.append(
                        build_hierarchy_row(parent, _metric_vals(parent_view), target_metric, children=child_rows)
                    )

                rows.append(
                    build_hierarchy_row(
                        f"Grand Total ({scenario} Scenario)", _metric_vals(total_view), target_metric,
                        children=parent_rows,
                    )
                )

            result[metric][view] = {
                "chart": {},
                "table": build_hierarchy_table(["Metric"] + header_labels, rows),
            }

    return result


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

        aggregates = {}
        for scenario in scenario_names:
            cube = _scenario_cube(cur, ta, scenario, from_year, from_month, to_year, to_month, payers, products)
            aggregates[scenario] = _build_scenario_aggregates(
                cube, month_tuples, forecast_start_index, payers, products
            )

        common_args = (month_tuples, month_keys, forecast_start_index, year_labels, yearly_fsi)

        output_tabs = {
            "total_payer_volume": _build_distribution_tab(aggregates, scenario_names, *common_args),
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
