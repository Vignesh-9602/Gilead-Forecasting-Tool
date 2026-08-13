from app.db.connection import get_connection
from app.liver_output.repository.output_repo import (
    get_payers,
    get_products,
    get_scenarios,
    get_distinct_months,
    get_all_configs_for_ta,
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
# Reused as-is from Liver Model Input so this screen's numbers can never drift
# from what Model Input itself computed and persisted -- these are pure,
# side-effect-free dict transforms (no DB access), safe to share directly
# rather than re-implementing (see this module's own long-standing comment
# on why independent re-implementations of the same math never agree).
from app.liver.services.liver_service import (
    _normalize_ma_keys,
    _clip_ma_to_from_date,
    _recompute_yearly_in_ma,
    _recompute_all_market_shares_nested,
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
        _, max_end = _get_date_range_from_configs(configs)

        # The available range should span from the earliest month real data
        # actually exists (not the configured train_start_date — the model may
        # only train on a subset of history, e.g. train_start_date=2022-09-01
        # while transaction_data actually goes back to 2020-04-01, and users
        # should still be able to view/select that earlier history here) out
        # to the forecast end (train_end_date + forecast_periods, from config).
        month_rows = get_distinct_months(cur, ta)
        min_start = to_month_label(*month_rows[0]) if month_rows else None

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
#
# Loads each selected scenario's already-computed market_analysis straight
# from raw_liver.liver_scenarios (the same table Liver Model Input persists
# to — 'BASE' included, since Model Input persists a live Base computation
# there every time it runs). No independent/live forecasting happens on this
# screen at all: if a requested scenario (including Base) has never been
# computed via Model Input, apply_output_filters raises rather than silently
# recomputing.
#
# output_tabs uses Model Input's own tab set and shape (total_market_volume,
# product_distribution, payment_type_distribution, payment_type_product,
# payment_type_payer_product), not this screen's older bespoke shape, so
# there is exactly one implementation of "what a tab looks like" shared by
# both screens. This screen's own "payer" filter maps to Model Input's
# payment_type dimension (Cash/Commercial/Medicaid/Medicare) — see
# get_payers/payer_master; the real payer sub-dimension (CVS/Non CVS) that
# Model Input added later is never filtered here, matching how this screen
# has always worked.
# ---------------------------------------------------------------------------

def _load_scenario_ma(cur, scenario_name: str, from_year: int, from_month: int) -> dict:
    """Load + clip one scenario's market_analysis. No live computation."""
    chart_data = get_scenario_chart_data(cur, scenario_name)
    if not chart_data or "market_analysis" not in chart_data:
        raise ValueError(
            f"Scenario '{scenario_name}' has not been computed yet. "
            "Open Liver Model Input and apply filters for it at least once first."
        )
    ma = _normalize_ma_keys(chart_data["market_analysis"])
    ma = _clip_ma_to_from_date(ma, from_year, from_month)
    ma = _recompute_yearly_in_ma(ma)
    ma = _recompute_all_market_shares_nested(ma)
    return ma


# (real-world dimension at L1, L2) for payment_type_product's two sub-views
_HIER2_SV_DIMS = {
    "payment_type_product": ("payment_type", "product"),
    "product_payment_type": ("product", "payment_type"),
}
# (real-world dimension at L1, L2, L3) for payment_type_payer_product's three sub-views
_HIER3_SV_DIMS = {
    "payment_type_payer_product": ("payment_type", "payer", "product"),
    "payment_type_product_payer": ("payment_type", "product", "payer"),
    "product_payment_type_payer": ("product", "payment_type", "payer"),
}


def _wanted_for(dim: str, sel_payment_types: set, sel_products: set):
    """None = don't filter this level at all (the real payer/CVS-NonCVS dimension)."""
    if dim == "payment_type":
        return sel_payment_types
    if dim == "product":
        return sel_products
    return None


def _apply_gran_filter(node, filter_fn):
    """Walk a market_analysis subtree, applying filter_fn to every leaf {chart, table} gran."""
    if not isinstance(node, dict):
        return node
    if "chart" in node or "table" in node:
        return filter_fn(node)
    return {k: _apply_gran_filter(v, filter_fn) for k, v in node.items()}


def _filter_gran_flat(gran: dict, wanted: set) -> dict:
    """Keep only rows/series in `wanted`, plus any Total row (always shown, it's the true grand total)."""
    def _keep(label: str) -> bool:
        return label.strip().lower() in ("total", "total market volume") or label in wanted

    table = gran.get("table", {})
    chart = gran.get("chart", {})
    return {
        **gran,
        "table": {**table, "rows": [r for r in table.get("rows", []) if _keep(r.get("label", ""))]},
        "chart": {**chart, "series": [s for s in chart.get("series", []) if _keep(s.get("label", ""))]},
    }


def _sum_values(nodes: list) -> list:
    """Elementwise sum of each node's "values" list (ragged-length safe)."""
    if not nodes:
        return []
    n = max(len(nd.get("values", [])) for nd in nodes)
    return [
        sum(float(nd.get("values", [])[i]) for nd in nodes if i < len(nd.get("values", [])))
        for i in range(n)
    ]


def _filter_hier_rows(rows: list, l1_wanted, l2_wanted, l3_wanted) -> list:
    """
    Filters a 2- or 3-level hierarchy row tree by label sets at each level.
    None for a level = no filter (keep everything at that level). A node whose
    every child gets filtered out is dropped entirely rather than shown empty.

    Handles Tab 5's "no real L2" case (e.g. Cash has no payer): when an L2
    node has no children of its own, it IS the leaf (product) and is filtered
    by l3_wanted instead of l2_wanted (matches how the tree is built — see
    Liver Model Input's _build_tab5_3level).

    Every surviving parent's "values" is unconditionally recomputed as the sum
    of its (already-filtered/recomputed) children, bottom-up — not just when
    that parent's OWN direct children were narrowed. Otherwise a change two
    levels down (e.g. a grandchild filtered out under "CVS") would leave its
    grandparent's total ("Commercial") stale, since "Commercial" itself kept
    the same two direct children (CVS, Non CVS) and only THEIR totals shrank.
    Harmless when nothing was actually filtered — summing unchanged children
    reproduces the original total.
    """
    out = []
    for r in rows:
        if l1_wanted is not None and r.get("label") not in l1_wanted:
            continue
        children = r.get("children")
        if not children:
            out.append(r)
            continue
        new_children = []
        for c in children:
            grandchildren = c.get("children")
            if grandchildren:
                if l2_wanted is not None and c.get("label") not in l2_wanted:
                    continue
                new_grandchildren = [
                    gc for gc in grandchildren
                    if l3_wanted is None or gc.get("label") in l3_wanted
                ]
                if not new_grandchildren:
                    continue
                new_children.append({**c, "children": new_grandchildren, "values": _sum_values(new_grandchildren)})
            else:
                wanted = l3_wanted if l3_wanted is not None else l2_wanted
                if wanted is not None and c.get("label") not in wanted:
                    continue
                new_children.append(c)
        if not new_children:
            continue
        out.append({**r, "children": new_children, "values": _sum_values(new_children)})
    return out


def _filter_gran_hier(gran: dict, l1_wanted, l2_wanted, l3_wanted) -> dict:
    """
    Filters only the table (row tree). Chart series are left as-is — Tab 4/5
    charts are already one line per leaf combo (e.g. "Cash - CVS - ASGA"); the
    comparison table below is what this screen's filter is actually meant to
    narrow, and re-deriving matching chart series from the filter is out of
    scope for this pass.
    """
    table = gran.get("table", {})
    return {**gran, "table": {**table, "rows": _filter_hier_rows(table.get("rows", []), l1_wanted, l2_wanted, l3_wanted)}}


def _filter_ma_by_selection(ma: dict, sel_payment_types: set, sel_products: set) -> dict:
    """Narrow a loaded market_analysis to this screen's selected payers (payment_types) and products."""
    result = dict(ma)

    for tab, wanted in (
        ("product_distribution", sel_products),
        ("payment_type_distribution", sel_payment_types),
    ):
        if tab in result:
            result[tab] = _apply_gran_filter(result[tab], lambda g, w=wanted: _filter_gran_flat(g, w))

    for tab, sv_dims in (
        ("payment_type_product", _HIER2_SV_DIMS),
        ("payment_type_payer_product", _HIER3_SV_DIMS),
    ):
        if tab not in result:
            continue
        new_tab = {}
        for sv, subtree in result[tab].items():
            dims = sv_dims.get(sv, (None, None, None) if tab == "payment_type_payer_product" else (None, None))
            l1w = _wanted_for(dims[0], sel_payment_types, sel_products)
            l2w = _wanted_for(dims[1], sel_payment_types, sel_products)
            l3w = _wanted_for(dims[2], sel_payment_types, sel_products) if len(dims) > 2 else None
            new_tab[sv] = _apply_gran_filter(
                subtree, lambda g, a=l1w, b=l2w, c=l3w: _filter_gran_hier(g, a, b, c)
            )
        result[tab] = new_tab

    return result


def _merge_gran(scenario_grans: dict) -> dict:
    """scenario_grans: {scenario: gran_dict}. Merges N scenarios' chart+table into one comparison gran_dict."""
    ref = next(iter(scenario_grans.values()), {}) or {}
    ref_chart = ref.get("chart", {})
    ref_table = ref.get("table", {})
    months_key = "months" if "months" in ref_chart else "years"

    def _suffixed(label: str, scenario: str, style: str) -> str:
        # TMV's own row/series is already scenario-specific (table row label ==
        # scenario_name) or scenario-agnostic ("Total Market Volume" chart
        # series) — don't double-suffix an already-scenario-named label.
        if label.strip().lower() == scenario.strip().lower():
            return label
        return f"{label} ({scenario} Scenario)" if style == "table" else f"{label} ({scenario})"

    merged_series = []
    merged_rows = []
    for scenario, gran in scenario_grans.items():
        for s in (gran or {}).get("chart", {}).get("series", []):
            merged_series.append({**s, "label": _suffixed(s.get("label", ""), scenario, "chart")})
        for r in (gran or {}).get("table", {}).get("rows", []):
            merged_rows.append({**r, "label": _suffixed(r.get("label", ""), scenario, "table")})

    return {
        "chart": {
            months_key: ref_chart.get(months_key, []),
            "forecast_start_index": ref_chart.get("forecast_start_index", 0),
            "series": merged_series,
        },
        "table": {
            **{k: v for k, v in ref_table.items() if k != "rows"},
            "rows": merged_rows,
        },
    }


def _merge_node(nodes: dict):
    """nodes: {scenario: subtree_at_this_path}. Recurses until a leaf {chart, table} gran, merging there."""
    sample = next((v for v in nodes.values() if isinstance(v, dict) and v), {})
    if "chart" in sample or "table" in sample:
        return _merge_gran(nodes)
    keys = set()
    for v in nodes.values():
        if isinstance(v, dict):
            keys |= set(v.keys())
    return {
        k: _merge_node({sc: (v.get(k, {}) if isinstance(v, dict) else {}) for sc, v in nodes.items()})
        for k in keys
    }


def _merge_scenarios_ma(scenario_mas: dict) -> dict:
    """scenario_mas: {scenario_name: market_analysis}. Merges into one comparison market_analysis."""
    tab_keys = set()
    for ma in scenario_mas.values():
        tab_keys |= set(ma.keys())
    tab_keys.discard("event_management")

    merged = {}
    for tab in tab_keys:
        nodes = {sc: ma.get(tab, {}) for sc, ma in scenario_mas.items()}
        merged[tab] = _merge_node(nodes)
    return merged


def apply_output_filters(payload) -> dict:
    """
    Called when the user clicks Apply Filter.
    Saves the filter selection, then returns output_tabs (Model Input's tab
    set: total_market_volume, product_distribution, payment_type_distribution,
    payment_type_product, payment_type_payer_product) for every selected
    scenario, merged into one comparison view per tab.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta             = payload.ta
        scenario_names = payload.scenario_names
        payers         = payload.payers      # this screen's "payer" == Model Input's payment_type
        products       = payload.products
        start_date     = payload.start_date
        end_date       = payload.end_date

        from_year, from_month = parse_year_month(start_date)
        sel_payment_types = set(payers)
        sel_products      = set(products)

        scenario_mas = {}
        for scenario in scenario_names:
            ma = _load_scenario_ma(cur, scenario, from_year, from_month)
            scenario_mas[scenario] = _filter_ma_by_selection(ma, sel_payment_types, sel_products)

        output_tabs = _merge_scenarios_ma(scenario_mas)

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
