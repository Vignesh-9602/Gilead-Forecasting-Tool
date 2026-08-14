from app.db.connection import get_connection
from app.liver_output.repository.output_repo import (
    get_payers,
    get_products,
    get_scenarios,
    get_distinct_months,
    get_all_configs_for_ta,
    get_scenario_chart_data_and_factors,
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
# from what Model Input itself computed and persisted, rather than
# re-implementing (see this module's own long-standing comment on why
# independent re-implementations of the same math never agree). Most of these
# are pure, side-effect-free dict transforms (no DB access); _ensure_base_snapshot
# and _load_config do read the DB, and _ensure_base_snapshot self-heals (writes)
# Base's own row when it's stale for the requested date range -- the same
# self-heal every other Base-reading call site in Model Input already relies
# on, reused here rather than re-implemented so Base's date range is never
# shorter on this screen than what Model Input itself would show.
from app.liver.services.liver_service import (
    _normalize_ma_keys,
    _clip_ma_to_from_date,
    _recompute_yearly_in_ma,
    _recompute_all_market_shares_nested,
    _ensure_base_snapshot,
    _load_config,
    _resolve_forecast_periods,
    _parse_ym,
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
# to). No independent forecasting logic lives on this screen: saved (non-Base)
# scenarios are read as-is and raise if never computed via Model Input. Base
# is the one exception — its own row is read through Model Input's own
# _ensure_base_snapshot self-heal (not re-implemented here, just reused) so
# Base's date range always covers this screen's selected end_date rather than
# silently ending wherever Base's row last happened to be refreshed.
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

def _factors_effectively_equal(a: dict | None, b: dict | None) -> bool:
    """
    True when two stored `factors` dicts would drive Liver Model Input's model
    to produce the same forecast: same active_model, same params for THAT model
    (the only ones actually used — see _forecast_share_by_factors), and same
    multiplier. Deliberately ignores every other model's leftover params (e.g.
    a stale `ets` block while active_model is "moving_average") and
    trajectory_start-style fields that can legitimately differ run to run
    without changing the output.
    """
    if not a or not b:
        return False
    am = (a.get("active_model") or "moving_average").lower()
    bm = (b.get("active_model") or "moving_average").lower()
    if am != bm:
        return False
    if float(a.get("multiplier", 1.0)) != float(b.get("multiplier", 1.0)):
        return False
    if a.get("multiplier_horizon", "Forecast") != b.get("multiplier_horizon", "Forecast"):
        return False
    a_params = a.get(am) or {}
    b_params = b.get(am) or {}
    keys = set(a_params.keys()) | set(b_params.keys())
    keys.discard("trajectory_start")
    for k in keys:
        if a_params.get(k) != b_params.get(k):
            return False
    return True


def _splice_values(scenario_vals: list, base_vals: list) -> list:
    """Base's values for the overlapping prefix (by position — both start at the
    same clipped from_date), then the scenario's own tail beyond Base's range."""
    n = min(len(scenario_vals), len(base_vals))
    return list(base_vals[:n]) + list(scenario_vals[n:])


def _splice_rows_from_base(scenario_rows: list, base_rows: list) -> list:
    """Recursively replace each row's values (and its children/grandchildren,
    matched by label) with Base's, for tabs where a scenario with the same
    factors as Base should be numerically identical to it."""
    base_by_label = {r.get("label"): r for r in base_rows}
    new_rows = []
    for r in scenario_rows:
        br = base_by_label.get(r.get("label"))
        new_r = dict(r)
        if br is not None:
            new_r["values"] = _splice_values(r.get("values", []), br.get("values", []))
            if r.get("children"):
                new_r["children"] = _splice_rows_from_base(r["children"], br.get("children", []))
        new_rows.append(new_r)
    return new_rows


def _reconcile_payment_type_payer_product_with_base(ma: dict, base_ma: dict) -> dict:
    """
    payment_type_payer_product's per-series forecast depends on which
    payment_type/product happened to be the active filter at the moment each
    scenario's data was computed (see Liver Model Input's
    _build_tab_data_from_shares/_build_tab5_3level) — two scenarios with
    identical factors can end up with different child-level (payer/product)
    splits even though their totals roughly agree. Since this tab is entirely
    model-computed (never user-edited on this read-only screen), when a saved
    scenario's factors match Base's, substitute Base's own monthly payer_volume
    table values so the numbers a user compares are always consistent. Only the
    monthly payer_volume table is touched — yearly aggregation and payer_share
    are both derived FROM it later in _load_scenario_ma, so they inherit the
    correction automatically.
    """
    tab = ma.get("payment_type_payer_product")
    base_tab = base_ma.get("payment_type_payer_product")
    if not tab or not base_tab:
        return ma
    new_tab = dict(tab)
    for sv, subtree in tab.items():
        base_subtree = base_tab.get(sv)
        if not base_subtree or "payer_volume" not in subtree:
            continue
        monthly = subtree["payer_volume"].get("monthly")
        base_monthly = base_subtree.get("payer_volume", {}).get("monthly")
        if not monthly or not base_monthly:
            continue
        new_table = dict(monthly.get("table", {}))
        new_table["rows"] = _splice_rows_from_base(
            new_table.get("rows", []), base_monthly.get("table", {}).get("rows", [])
        )
        new_tab[sv] = {
            **subtree,
            "payer_volume": {**subtree["payer_volume"], "monthly": {**monthly, "table": new_table}},
        }
    return {**ma, "payment_type_payer_product": new_tab}


def _load_scenario_ma(cur, scenario_name: str, from_year: int, from_month: int,
                       base_ma: dict | None = None, base_factors: dict | None = None) -> dict:
    """Load + clip one scenario's market_analysis. No live computation.

    base_ma/base_factors: Base's own already-clipped (same from_year/from_month)
    market_analysis + factors, passed in by apply_output_filters for every
    non-Base scenario so payment_type_payer_product can be reconciled with Base
    when factors match (see _reconcile_payment_type_payer_product_with_base).
    """
    chart_data, factors = get_scenario_chart_data_and_factors(cur, scenario_name)
    if not chart_data or "market_analysis" not in chart_data:
        raise ValueError(
            f"Scenario '{scenario_name}' has not been computed yet. "
            "Open Liver Model Input and apply filters for it at least once first."
        )
    ma = _normalize_ma_keys(chart_data["market_analysis"])
    ma = _clip_ma_to_from_date(ma, from_year, from_month)
    if base_ma is not None and scenario_name.strip().upper() != "BASE" \
            and _factors_effectively_equal(factors, base_factors):
        ma = _reconcile_payment_type_payer_product_with_base(ma, base_ma)
    ma = _recompute_yearly_in_ma(ma)
    ma = _recompute_all_market_shares_nested(ma)
    # Hierarchy tabs' (payment_type_product / payment_type_payer_product) chart
    # series get fully rebuilt from their table during filtering below
    # (_filter_gran_hier), regardless of whatever was persisted in chart.series
    # at save time — table.rows is the reliable source; trusting stored
    # chart.series is what caused "nothing in chart data" for saved scenarios.
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


def _wanted_for(dim: str, sel_payment_types: set, sel_sub_payers: set, sel_products: set):
    if dim == "payment_type":
        return sel_payment_types
    if dim == "payer":
        return sel_sub_payers
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


def _filter_hier_rows(rows: list, l1_wanted, l2_wanted, l3_wanted, recompute_values: bool) -> list:
    """
    Filters a 2- or 3-level hierarchy row tree by label sets at each level.
    None for a level = no filter (keep everything at that level). A node whose
    every child gets filtered out is dropped entirely rather than shown empty.

    Handles Tab 5's "no real L2" case (e.g. Cash has no payer): when an L2
    node has no children of its own, it IS the leaf (product) and is filtered
    by l3_wanted instead of l2_wanted (matches how the tree is built — see
    Liver Model Input's _build_tab5_3level).

    recompute_values: for the VOLUME metric, every surviving parent's "values"
    is unconditionally recomputed as the sum of its (already-filtered/
    recomputed) children, bottom-up — not just when that parent's OWN direct
    children were narrowed, since a change two levels down (e.g. a grandchild
    filtered out under "CVS") would otherwise leave its grandparent's total
    ("Commercial") stale. For the SHARE metric this must be False: a child's
    share value is already a percentage of its OWN direct parent (e.g. CVS =
    62.5% of Commercial's total, ASGA = 40% of CVS's total) — summing
    filtered children's shares back up would overwrite the parent's true,
    fixed share (e.g. Commercial's 80% share of the grand total) with an
    unrelated number on a completely different scale. Share values are always
    left exactly as computed from the full, unfiltered data — narrowing which
    payers/products are shown must never change what percentage any of them
    truly represents (same principle as the flat tabs' "Total" row).
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
                new_c = {**c, "children": new_grandchildren}
                if recompute_values:
                    new_c["values"] = _sum_values(new_grandchildren)
                new_children.append(new_c)
            else:
                wanted = l3_wanted if l3_wanted is not None else l2_wanted
                if wanted is not None and c.get("label") not in wanted:
                    continue
                new_children.append(c)
        if not new_children:
            continue
        new_r = {**r, "children": new_children}
        if recompute_values:
            new_r["values"] = _sum_values(new_children)
        out.append(new_r)
    return out


def _split_hist_fore(values: list, fsi: int) -> tuple:
    return list(values[:fsi]), list(values[fsi:])


def _chart_series_2level(rows: list, fsi: int) -> list:
    """Tab 4 (payment_type_product): always one series per (L1, L2) pair — there's
    no deeper level to collapse to or drill into, so this doesn't depend on leaf_mode."""
    series = []
    for l1 in rows:
        d1 = l1.get("label", "")
        for l2 in l1.get("children", []):
            hist, fore = _split_hist_fore(l2.get("values", []), fsi)
            series.append({"label": f"{d1} - {l2.get('label', '')}", "history": hist, "forecast": fore})
    return series


def _chart_series_3level(rows: list, fsi: int, leaf_mode: bool) -> list:
    """
    Tab 5 (payment_type_payer_product, and its two derived orientations): one
    series per L1/L2 aggregate by default (matching the existing view), or one
    series per product leaf when leaf_mode is on (i.e. a product filter is
    active) — e.g. selecting Cash, Commercial | CVS | ASGA, GILD produces
    "Cash - ASGA", "Cash - GILD", "Commercial - CVS - ASGA", "Commercial - CVS - GILD".

    An L1 group whose children have no children of their own (e.g. Cash has no
    real payer — its "children" are actually promoted product rows, not payer
    rows) is detected structurally, not by label, since Cash's rows are
    labeled with the product name, never the literal string "NA".
    """
    series = []
    for l1 in rows:
        d1 = l1.get("label", "")
        l2_children = l1.get("children", [])
        if not l2_children:
            hist, fore = _split_hist_fore(l1.get("values", []), fsi)
            series.append({"label": d1, "history": hist, "forecast": fore})
            continue

        no_real_payer = not any(c.get("children") for c in l2_children)
        if no_real_payer:
            if leaf_mode:
                for c in l2_children:
                    hist, fore = _split_hist_fore(c.get("values", []), fsi)
                    series.append({"label": f"{d1} - {c.get('label', '')}", "history": hist, "forecast": fore})
            else:
                hist, fore = _split_hist_fore(l1.get("values", []), fsi)
                series.append({"label": d1, "history": hist, "forecast": fore})
            continue

        for l2 in l2_children:
            d2 = l2.get("label", "")
            l3_children = l2.get("children", [])
            if leaf_mode and l3_children:
                for l3 in l3_children:
                    hist, fore = _split_hist_fore(l3.get("values", []), fsi)
                    series.append({"label": f"{d1} - {d2} - {l3.get('label', '')}", "history": hist, "forecast": fore})
            else:
                hist, fore = _split_hist_fore(l2.get("values", []), fsi)
                series.append({"label": f"{d1} - {d2}", "history": hist, "forecast": fore})
    return series


def _filter_gran_hier(gran: dict, l1_wanted, l2_wanted, l3_wanted, is_3level: bool, leaf_mode: bool,
                       recompute_values: bool) -> dict:
    """
    Filters the table (row tree), then rebuilds the chart series entirely from
    the FILTERED table — never from whatever was in the stored chart.series —
    so table and chart always agree and a stale/empty stored chart.series
    (see _load_scenario_ma) can never leak through.
    """
    table = gran.get("table", {})
    chart = gran.get("chart", {})
    new_rows = _filter_hier_rows(table.get("rows", []), l1_wanted, l2_wanted, l3_wanted, recompute_values)
    fsi = chart.get("forecast_start_index", 0)
    new_series = (
        _chart_series_3level(new_rows, fsi, leaf_mode) if is_3level
        else _chart_series_2level(new_rows, fsi)
    )
    return {
        **gran,
        "table": {**table, "rows": new_rows},
        "chart": {**chart, "series": new_series},
    }


def _filter_ma_by_selection(ma: dict, sel_payment_types: set, sel_sub_payers: set, sel_products: set) -> dict:
    """Narrow a loaded market_analysis to this screen's selected payment_types, payers (CVS/Non CVS), and products."""
    result = dict(ma)

    for tab, wanted in (
        ("product_distribution", sel_products),
        ("payment_type_distribution", sel_payment_types),
    ):
        if tab in result:
            result[tab] = _apply_gran_filter(result[tab], lambda g, w=wanted: _filter_gran_flat(g, w))

    leaf_mode = bool(sel_products)
    for tab, sv_dims, is_3level in (
        ("payment_type_product", _HIER2_SV_DIMS, False),
        ("payment_type_payer_product", _HIER3_SV_DIMS, True),
    ):
        if tab not in result:
            continue
        new_tab = {}
        for sv, subtree in result[tab].items():
            dims = sv_dims.get(sv, (None, None, None) if is_3level else (None, None))
            l1w = _wanted_for(dims[0], sel_payment_types, sel_sub_payers, sel_products)
            l2w = _wanted_for(dims[1], sel_payment_types, sel_sub_payers, sel_products)
            l3w = _wanted_for(dims[2], sel_payment_types, sel_sub_payers, sel_products) if len(dims) > 2 else None
            new_sv = {}
            for metric_key, metric_subtree in subtree.items():
                # Volume genuinely changes when children are excluded from a total,
                # so it's recomputed bottom-up. Share values are already a percentage
                # of their own direct parent — narrowing the filter must never change
                # what percentage something truly represents, so they're left as-is
                # (see _filter_hier_rows' docstring).
                recompute = metric_key == "payer_volume"
                new_sv[metric_key] = _apply_gran_filter(
                    metric_subtree,
                    lambda g, a=l1w, b=l2w, c=l3w, rc=recompute: _filter_gran_hier(
                        g, a, b, c, is_3level, leaf_mode, rc
                    ),
                )
            new_tab[sv] = new_sv
        result[tab] = new_tab

    return result


def apply_output_filters(payload) -> dict:
    """
    Called when the user clicks Apply Filter.
    Saves the filter selection, then returns output_tabs keyed by scenario
    name — output_tabs = {scenario_name: {"market_analysis": {...}}, ...} —
    the same shape Liver Model Input's own apply-filters/activate-scenario
    responses use for their "scenarios" dict, with each scenario's
    market_analysis using Model Input's own tab set: total_market_volume,
    product_distribution, payment_type_distribution, payment_type_product,
    payment_type_payer_product.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta             = payload.ta
        scenario_names = payload.scenario_names
        # payment_type is the primary field; "payers" is a legacy alias some
        # callers still send instead (see ApplyFiltersRequest's docstring).
        payment_types  = payload.payment_type or payload.payers
        sub_payers     = payload.payer       # real payer sub-dimension (CVS/Non CVS)
        products       = payload.products
        start_date     = payload.start_date
        end_date       = payload.end_date

        from_year, from_month = parse_year_month(start_date)
        sel_payment_types = set(payment_types)
        sel_sub_payers    = set(sub_payers)
        sel_products      = set(products)

        # Load Base's own (self-healed) wide snapshot once, even when "BASE"
        # isn't among the requested scenarios, so:
        #  1. every other scenario can be reconciled against it in
        #     _load_scenario_ma when their factors match (see
        #     _reconcile_payment_type_payer_product_with_base), and
        #  2. Base's own date range always covers up to the selected end_date.
        #     Reading Base's raw stored row directly (as this used to) could
        #     silently show Base ending short of the filter's end_date, e.g.
        #     Base's row last self-healed while forecast_periods only reached
        #     Dec-2026, while a saved scenario (saved after forecast_periods
        #     was extended) already covers through Dec-2027 -- the date
        #     dropdown here offers Dec-2027 for the whole TA, but Base's own
        #     row was never refreshed to match. _ensure_base_snapshot is the
        #     same self-heal every Base-reading call site in Model Input
        #     already relies on for exactly this; reused here rather than
        #     re-implemented.
        try:
            cfg = _load_config(cur, ta, payment_type=None, brand=None)
            train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
            forecast_periods = _resolve_forecast_periods(
                end_date, train_end_year, train_end_month, cfg["forecast_periods"]
            )
            granularity = cfg.get("model_granularity", "monthly")
            wide_base_ma, base_factors = _ensure_base_snapshot(
                cur, ta, train_end_year, train_end_month, forecast_periods, granularity,
                sel_payer=None, sel_product=None, sel_payment_type=None,
            )
            conn.commit()
            base_ma = _clip_ma_to_from_date(_normalize_ma_keys(wide_base_ma), from_year, from_month)
        except Exception as _base_err:
            print(f"[liver_output] Base self-heal skipped: {_base_err}")
            base_ma, base_factors = None, None

        output_tabs = {}
        for scenario in scenario_names:
            if scenario.strip().upper() == "BASE" and base_ma is not None:
                ma = _recompute_all_market_shares_nested(_recompute_yearly_in_ma(base_ma))
            else:
                ma = _load_scenario_ma(cur, scenario, from_year, from_month, base_ma, base_factors)
            ma = _filter_ma_by_selection(ma, sel_payment_types, sel_sub_payers, sel_products)
            ma.pop("event_management", None)
            output_tabs[scenario] = {"market_analysis": ma}

        selected_filter = {
            "ta":             ta,
            "scenario_names": scenario_names,
            "payers":         payment_types,
            "payment_type":   payment_types,
            "payer":          sub_payers,
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
