from datetime import datetime, date as date_type
from dateutil.relativedelta import relativedelta

from app.db.connection import get_connection
from app.services.forecast_service import (
    forecast_ets, estimate_parameters,
    forecast_linear, forecast_exponential, forecast_logarithmic, forecast_s_curve,
)
from app.liver.schemas.liver_schema import (
    LiverApplyFiltersRequest,
    LiverRecalculateRequest,
    LiverSaveScenarioRequest,
    LiverFactors,
    EtsParams,
    LinearParams,
    SCurveParams,
    ExponentialParams,
    LogarithmicParams,
    ChartSeries,
    TableRow,
    TabChart,
    TabTable,
    TabData,
    ChildRow,
    HierarchicalRow,
    HierarchicalTabTable,
    HierarchicalTabData,
    LiverRecalculateFactors,
    LiverGrowthFactors,
)
from app.liver.repository.liver_repo import (
    get_liver_configs_for_ta,
    get_liver_config_by_payer_brand,
    upsert_liver_config,
    get_payers,
    get_products,
    get_scenarios,
    get_transaction_date_range,
    get_transaction_distinct_months,
    get_total_market_volume,
    get_product_distribution,
    get_payer_distribution,
    get_payer_wise_product,
    get_product_wise_payer,
    get_total_market_volume_yearly,
    get_product_distribution_yearly,
    get_payer_distribution_yearly,
    get_payer_wise_product_yearly,
    get_product_wise_payer_yearly,
    save_scenario,
)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_ym(date_str: str) -> tuple:
    """'2020-04' or '2020-04-01' → (2020, 4)"""
    parts = date_str.split("-")
    return int(parts[0]), int(parts[1])


def _month_label(year: int, month: int, granularity: str = "monthly") -> str:
    if granularity == "yearly":
        return str(year)
    return date_type(year, month, 1).isoformat()


def _generate_months(from_year, from_month, to_year, to_month,
                     granularity: str = "monthly") -> list:
    """
    monthly → [(2020,4), (2020,5), ...]
    yearly  → [(2020,0), (2021,0), ...]  month=0 is the yearly placeholder
    """
    if granularity == "yearly":
        return [(y, 0) for y in range(from_year, to_year + 1)]

    months = []
    current = datetime(from_year, from_month, 1)
    end = datetime(to_year, to_month, 1)
    while current <= end:
        months.append((current.year, current.month))
        current += relativedelta(months=1)
    return months


# ---------------------------------------------------------------------------
# Configuration service
# ---------------------------------------------------------------------------

def _add_months(d: date_type, months: int) -> date_type:
    month = d.month - 1 + months
    year  = d.year + month // 12
    month = month % 12 + 1
    return date_type(year, month, 1)


def get_liver_configuration(ta_name: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        month_rows = get_transaction_distinct_months(cur, ta_name)
        available_train_months = [
            date_type(int(r[0]), int(r[1]), 1).isoformat() for r in month_rows
        ]

        db_rows = get_liver_configs_for_ta(cur, ta_name)
        if not db_rows:
            # Compute default pre-fill: Medicaid + GILD, 5yr data + 1yr forecast
            _, _, max_year, max_month = get_transaction_date_range(cur)
            max_dt      = date_type(max_year, max_month, 1)
            start_dt    = _add_months(max_dt, -60)       # 5 years back
            forecast_dt = _add_months(max_dt, 12)        # 1 year forecast
            return {
                "ta_name": ta_name,
                "exists":  False,
                "entries": [],
                "available_train_months": available_train_months,
                "default_config": {
                    "payer":             "Medicaid",
                    "brand":             "GILD",
                    "train_start_date":  start_dt.isoformat(),
                    "train_end_date":    max_dt.isoformat(),
                    "model_granularity": "monthly",
                    "forecast_periods":  forecast_dt.isoformat(),
                },
                # `config` key for frontend compatibility
                "config": {
                    "payer":             ["Medicaid"],
                    "brand":             ["GILD"],
                    "train_start_date":  start_dt.isoformat(),
                    "train_end_date":    max_dt.isoformat(),
                    "model_granularity": "monthly",
                    "forecast_periods":  forecast_dt.isoformat(),
                },
            }

        entries = []
        for payer, brand, config in db_rows:
            train_end    = date_type.fromisoformat(config["train_end_date"][:10])
            forecast_end = _add_months(train_end, int(config["forecast_periods"]))
            entries.append({
                "payer":              payer,
                "brand":              brand,
                "train_start_date":   config["train_start_date"][:10],
                "train_end_date":     config["train_end_date"][:10],
                "model_granularity":  config.get("model_granularity", "monthly"),
                "forecast_periods":   forecast_end.isoformat(),
            })

        # Collect all unique payers/brands; use first entry's dates for the `config` key
        first = entries[0]
        return {
            "ta_name": ta_name,
            "exists": True,
            "entries": entries,
            "available_train_months": available_train_months,
            # `config` key for frontend compatibility
            "config": {
                "payer":             list({e["payer"] for e in entries}),
                "brand":             list({e["brand"] for e in entries}),
                "train_start_date":  first["train_start_date"],
                "train_end_date":    first["train_end_date"],
                "model_granularity": first["model_granularity"],
                "forecast_periods":  first["forecast_periods"],
            },
        }
    finally:
        cur.close()
        conn.close()


def save_liver_configuration(payload) -> dict:
    cfg = payload.config
    conn = get_connection()
    cur = conn.cursor()
    try:
        train_start  = date_type.fromisoformat(cfg.train_start_date[:10])
        train_end    = date_type.fromisoformat(cfg.train_end_date[:10])
        forecast_end = date_type.fromisoformat(cfg.forecast_periods[:10])

        if train_start > train_end:
            raise ValueError("train_start_date cannot be after train_end_date")
        if forecast_end <= train_end:
            raise ValueError("forecast_periods date must be after train_end_date")

        forecast_periods_int = (
            (forecast_end.year - train_end.year) * 12
            + (forecast_end.month - train_end.month)
        )

        min_year, min_month, max_year, max_month = get_transaction_date_range(cur)
        min_dt = date_type(min_year, min_month, 1)
        max_dt = date_type(max_year, max_month, 1)

        if not (min_dt <= train_start <= max_dt):
            raise ValueError(
                f"train_start_date is outside available data range "
                f"({_month_label(min_year, min_month)} – {_month_label(max_year, max_month)})"
            )
        if not (min_dt <= train_end <= max_dt):
            raise ValueError(
                f"train_end_date is outside available data range "
                f"({_month_label(min_year, min_month)} – {_month_label(max_year, max_month)})"
            )

        # Config stored without payer/brand (those are DB columns)
        config_to_save = {
            "ta_name":           cfg.ta_name,
            "train_start_date":  cfg.train_start_date[:10],
            "train_end_date":    cfg.train_end_date[:10],
            "model_granularity": cfg.model_granularity,
            "forecast_periods":  forecast_periods_int,
        }

        # Fan out: one DB row per (payer, brand) combination
        payers = cfg.payer if cfg.payer else ["All"]
        brands = cfg.brand if cfg.brand else ["All"]
        for payer in payers:
            for brand in brands:
                upsert_liver_config(cur, cfg.ta_name, payer, brand, config_to_save)

        conn.commit()

        return {
            "ta_name":  cfg.ta_name,
            "status":   "config_saved",
            "saved_combinations": len(payers) * len(brands),
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Core: build a single series with multi-model forecast
# is_selected=True        → apply user's factors (active_model dispatch)
# is_selected=False + ets → auto-estimate ETS params from the series' own history
# is_selected=False + linear → auto-estimate linear growth from the series' own history
# ---------------------------------------------------------------------------

def _estimate_linear_growth(values: list) -> float:
    """
    Estimate total_growth by comparing the average of the first few points
    to the average of the last few points.
    Window size = up to 3 months (or fewer if data is short).
    This is more stable than first-to-last because endpoint spikes don't dominate.
    """
    non_zero = [v for v in values if v > 0]
    if len(non_zero) < 2:
        return 0.0
    window    = max(1, min(3, len(non_zero) // 4))
    start_avg = sum(non_zero[:window]) / window
    end_avg   = sum(non_zero[-window:]) / window
    if start_avg == 0:
        return 0.0
    # Return as percentage (×100) because forecast_linear expects total_growth_pct
    return round(((end_avg - start_avg) / start_avg) * 100, 4)


def _build_series_with_forecast(month_range, data_map, forecast_start_index, factors,
                                 is_selected: bool = True, auto_model: str = "linear"):
    historical_months   = month_range[:forecast_start_index]
    forecast_months     = month_range[forecast_start_index:]
    forecast_count      = len(forecast_months)

    original_train      = [float(data_map.get((y, m), 0)) for y, m in historical_months]

    if not original_train or all(v == 0 for v in original_train):
        return original_train, [0.0] * forecast_count

    # Non-selected series: auto-estimate from data, NO multiplier applied.
    # Multiplier only affects the selected payer/brand (oncology pattern).
    if not is_selected:
        if auto_model == "ets":
            alpha, beta, gamma = (
                estimate_parameters(original_train) if len(original_train) >= 4
                else (0.30, 0.20, 0.98)
            )
            fc = forecast_ets(values=original_train, forecast_periods=forecast_count,
                              alpha=alpha, beta=beta, gamma=gamma, metric="nps")
        else:
            total_growth = _estimate_linear_growth(original_train)
            fc = forecast_linear(original_train[-1], forecast_count,
                                 total_growth, forecast_count, "nps")
        return original_train, fc

    # Selected series: user's factors + multiplier applied to display values only.
    # Model ALWAYS runs on original data (oncology pattern).
    multiplier        = factors.multiplier
    mh                = (factors.multiplier_horizon or "Forecast").lower()
    apply_to_history  = mh in ("history", "both history & forecast")
    apply_to_forecast = mh in ("forecast", "both history & forecast")

    active   = factors.active_model.lower()
    f_params = getattr(factors, active, None)

    if active == "ets":
        f  = factors.ets
        fc = forecast_ets(values=original_train, forecast_periods=forecast_count,
                          alpha=f.alpha, beta=f.beta, gamma=f.gamma, metric="nps")
    else:
        base_value = original_train[-1]
        traj_idx   = 0
        if forecast_months and f_params and hasattr(f_params, "trajectory_start") and f_params.trajectory_start:
            try:
                tstart = datetime.fromisoformat(f_params.trajectory_start[:10])
                for i, (fy, fm) in enumerate(forecast_months):
                    if datetime(fy, fm, 1) >= tstart:
                        traj_idx = i
                        break
            except Exception:
                pass

        pre_values = [base_value] * traj_idx
        remaining  = forecast_count - traj_idx

        if remaining > 0:
            if active == "linear":
                growth = forecast_linear(base_value, remaining, f_params.total_growth, f_params.duration, "nps")
            elif active == "exponential":
                growth = forecast_exponential(base_value, remaining, f_params.total_growth, f_params.duration, f_params.k_value, "nps")
            elif active == "logarithmic":
                growth = forecast_logarithmic(base_value, remaining, f_params.total_growth, f_params.duration, f_params.k_value, "nps")
            elif active == "scurve":
                growth = forecast_s_curve(base_value, remaining, f_params.total_growth, f_params.duration, f_params.k_value, "nps")
            else:
                growth = [0.0] * remaining
            fc = pre_values + growth
        else:
            fc = list(pre_values)

    # Apply multiplier to display values only (never to model input)
    display_train    = [round(v * multiplier, 2) for v in original_train] if apply_to_history  else original_train
    display_forecast = [round(v * multiplier, 2) for v in fc]             if apply_to_forecast else fc
    return display_train, display_forecast


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def _build_tab_data(series_dict, month_range, month_labels, forecast_start_index, factors,
                    selected_label=None, auto_model="linear", add_total=False):
    """
    selected_label: label whose series gets user factors; all others use auto_model.
    None → all series use user factors (is_selected=True for all).
    ""  → no series matches → all series use auto_model (used for Tab 1 ETS).
    add_total: if True, prepend a Total row that sums all series values.
    """
    chart_series, table_rows = [], []
    for label, data_map in series_dict.items():
        is_sel = (selected_label is None or label == selected_label)
        train_vals, forecast_vals = _build_series_with_forecast(
            month_range, data_map, forecast_start_index, factors,
            is_selected=is_sel, auto_model=auto_model,
        )
        chart_series.append(ChartSeries(
            label=label, train_values=train_vals, forecast_values=forecast_vals
        ))
        table_rows.append(TableRow(
            hierarchy=label, values=train_vals + forecast_vals
        ))

    if add_total and len(table_rows) > 0:
        n = len(month_range)
        total_vals = [0.0] * n
        for row in table_rows:
            for i, v in enumerate(row.values):
                if i < n:
                    total_vals[i] += v
        table_rows.insert(0, TableRow(hierarchy="Total", values=[round(v, 4) for v in total_vals]))

    return TabData(
        chart=TabChart(series=chart_series),
        table=TabTable(headers=month_labels, rows=table_rows),
    )


def _build_hierarchical_tab_data(rows, month_range, month_labels, forecast_start_index, factors,
                                  selected_parent=None, selected_child=None, auto_model="linear"):
    """
    selected_parent/selected_child: the combination that gets user factors.
    None for both → all series use auto_model.
    Parent totals are sum of individually-forecasted children.
    """
    grouped = {}
    for r in rows:
        key  = (r[0], r[1])
        parent, child, value = r[2], r[3], float(r[4])
        grouped.setdefault(parent, {}).setdefault(child, {})[key] = value

    chart_series = []
    table_rows   = []

    for parent, children in grouped.items():
        parent_is_sel = (selected_parent is None or parent == selected_parent)

        child_trains, child_forecasts, child_items = [], [], []
        for child, child_map in children.items():
            child_is_sel = parent_is_sel and (selected_child is None or child == selected_child)
            child_train, child_forecast = _build_series_with_forecast(
                month_range, child_map, forecast_start_index, factors,
                is_selected=child_is_sel, auto_model=auto_model,
            )
            child_trains.append(child_train)
            child_forecasts.append(child_forecast)
            child_items.append((child, child_train, child_forecast))

        # Parent total = sum of children's individual forecasts (not re-forecasted)
        n_tr = max((len(t) for t in child_trains),    default=0)
        n_fc = max((len(f) for f in child_forecasts), default=0)
        parent_train    = [sum(t[i] if i < len(t) else 0 for t in child_trains)    for i in range(n_tr)]
        parent_forecast = [sum(f[i] if i < len(f) else 0 for f in child_forecasts) for i in range(n_fc)]

        chart_series.append(ChartSeries(
            label=parent, train_values=parent_train, forecast_values=parent_forecast
        ))

        child_rows = []
        for child, child_train, child_forecast in child_items:
            chart_series.append(ChartSeries(
                label=f"{parent} - {child}",
                train_values=child_train,
                forecast_values=child_forecast,
            ))
            child_rows.append(ChildRow(label=child, values=child_train + child_forecast))

        table_rows.append(HierarchicalRow(
            hierarchy=parent,
            total=parent_train + parent_forecast,
            children=child_rows,
        ))

    return HierarchicalTabData(
        chart=TabChart(series=chart_series),
        table=HierarchicalTabTable(headers=month_labels, rows=table_rows),
    )



def _build_response_factors(factors: LiverFactors) -> dict:
    """Return full oncology-format factors dict for the API response."""
    return {
        "active_model":       factors.active_model,
        "multiplier":         factors.multiplier,
        "multiplier_horizon": factors.multiplier_horizon,
        "ets": {
            "alpha": factors.ets.alpha,
            "beta":  factors.ets.beta,
            "gamma": factors.ets.gamma,
        },
        "linear": {
            "total_growth":      factors.linear.total_growth,
            "duration":          factors.linear.duration,
            "trajectory_start":  factors.linear.trajectory_start,
        },
        "exponential": {
            "total_growth":      factors.exponential.total_growth,
            "duration":          factors.exponential.duration,
            "trajectory_start":  factors.exponential.trajectory_start,
            "k_value":           factors.exponential.k_value,
        },
        "logarithmic": {
            "total_growth":      factors.logarithmic.total_growth,
            "duration":          factors.logarithmic.duration,
            "trajectory_start":  factors.logarithmic.trajectory_start,
            "k_value":           factors.logarithmic.k_value,
        },
        "scurve": {
            "total_growth":      factors.scurve.total_growth,
            "duration":          factors.scurve.duration,
            "trajectory_start":  factors.scurve.trajectory_start,
            "k_value":           factors.scurve.k_value,
        },
    }


def _rows_to_series(rows, label_col_index, value_col_index):
    series = {}
    for row in rows:
        year, month = row[0], row[1]
        label = row[label_col_index]
        value = float(row[value_col_index]) if row[value_col_index] is not None else 0.0
        series.setdefault(label, {})[(year, month)] = value
    return series


# ---------------------------------------------------------------------------
# Helper: load config or fall back to DB defaults
# ---------------------------------------------------------------------------

def _load_config(cur, ta: str, payer: str = "All", brand: str = "All") -> dict:
    """
    Returns config dict for the given (ta, payer, brand).
    Falls back to 5 years of data + 12-month forecast if no config saved.
    """
    row = get_liver_config_by_payer_brand(cur, ta, payer, brand)
    if row:
        return row[0]

    # Fallback: 5 years back from max available date, 12-month forecast
    _, _, max_year, max_month = get_transaction_date_range(cur)
    max_dt   = date_type(max_year, max_month, 1)
    start_dt = _add_months(max_dt, -60)   # 5 years back
    return {
        "ta_name":           ta,
        "train_start_date":  start_dt.isoformat(),
        "train_end_date":    max_dt.isoformat(),
        "model_granularity": "monthly",
        "forecast_periods":  12,
    }


# ---------------------------------------------------------------------------
# Get filters
# ---------------------------------------------------------------------------

def get_liver_filters(ta: str = "HCV", payer: str = "All", brand: str = "All") -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        payers    = get_payers(cur)
        products  = get_products(cur)
        scenarios = get_scenarios(cur)

        # Load config for this payer+brand combo to derive date range
        cfg       = _load_config(cur, ta, payer=payer, brand=brand)
        from_date = cfg["train_start_date"][:10]
        train_end = date_type.fromisoformat(cfg["train_end_date"][:10])
        to_date   = _add_months(train_end, int(cfg["forecast_periods"])).isoformat()

        # available_dates bounded by config range (not full DB range)
        from_year, from_month = _parse_ym(from_date)
        to_year,   to_month   = _parse_ym(to_date)
        all_months  = _generate_months(from_year, from_month, to_year, to_month)
        date_labels = [_month_label(y, m) for y, m in all_months]

        return {
            "payers":   payers,
            "products": products,
            "scenarios": ["Base"] + scenarios,
            "metric_options": [
                {"label": "Market Volume", "value": "market_volume"},
                {"label": "Market Share",  "value": "market_share"},
            ],
            "available_dates": date_labels,
            "from_date":     from_date,
            "to_date":       to_date,
            "default_payer": payer,
            "default_brand": brand,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Core query + build logic (shared by apply and recalculate)
# ---------------------------------------------------------------------------

def _build_all_tabs(cur, ta, metric, from_year, from_month,
                    train_end_year, train_end_month, forecast_periods, factors,
                    granularity: str = "monthly",
                    sel_payer: str = None, sel_product: str = None,
                    scenario_name: str = "Base"):
    """
    Tab 1 always uses auto-ETS on the aggregate.
    Tabs 2-5:
      - If sel_payer/sel_product are given (recalculate): only that series uses user factors,
        all others use auto-estimated linear.
      - If both are None (apply_filters base): all series use auto-estimated linear.
    """
    is_yearly = granularity == "yearly"

    if is_yearly:
        forecast_end_year = train_end_year + forecast_periods
        month_range  = _generate_months(from_year, 0, forecast_end_year, 0, "yearly")
        actual_range = _generate_months(from_year, 0, train_end_year, 0, "yearly")
    else:
        forecast_end_dt = datetime(train_end_year, train_end_month, 1) + relativedelta(months=forecast_periods)
        month_range     = _generate_months(from_year, from_month, forecast_end_dt.year, forecast_end_dt.month)
        actual_range    = _generate_months(from_year, from_month, train_end_year, train_end_month)

    month_labels         = [_month_label(y, m, granularity) for y, m in month_range]
    forecast_start_index = len(actual_range)

    # Pre-estimate ETS for Tab 1 from training data so:
    #   a) the same params used in the chart are returned in the response (pre-fed to sliders)
    #   b) is_selected=True can be used → multiplier horizon is applied correctly
    # Tabs 2-5: sel_product/sel_payer gets user factors; others get auto-linear.
    tab2_label = sel_product if sel_product else ""
    tab3_label = sel_payer  if sel_payer  else ""

    if is_yearly:
        _tmv_train = get_total_market_volume_yearly(cur, ta, from_year, train_end_year, None)
    else:
        _tmv_train = get_total_market_volume(cur, ta, from_year, from_month, train_end_year, train_end_month, None)
    _tmv_values = [float(r[-1]) for r in _tmv_train if r[-1] is not None]
    if len(_tmv_values) >= 4:
        _t1a, _t1b, _t1g = estimate_parameters(_tmv_values)
    else:
        _t1a, _t1b, _t1g = 0.30, 0.20, 0.98
    tab1_ets     = EtsParams(alpha=round(_t1a, 4), beta=round(_t1b, 4), gamma=round(_t1g, 4))
    tab1_factors = factors.model_copy(update={"active_model": "ets", "ets": tab1_ets})

    tabs = {}

    if is_yearly:
        # Tab 1 — auto-ETS with is_selected=True so multiplier is applied
        tmv_map = {scenario_name: {(r[0], r[1]): float(r[-1]) for r in _tmv_train}}
        tabs["total_market_volume"] = _build_tab_data(
            tmv_map, month_range, month_labels, forecast_start_index, tab1_factors,
        )

        # Tab 2 — sel_product gets user factors; others get auto-linear
        pd_rows = get_product_distribution_yearly(cur, ta, from_year, train_end_year, "All", metric)
        tabs["product_distribution"] = _build_tab_data(
            _rows_to_series(pd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors,
            selected_label=tab2_label, auto_model="linear", add_total=True,
        )

        # Tab 3 — sel_payer gets user factors; others get auto-linear
        pyd_rows = get_payer_distribution_yearly(cur, ta, from_year, train_end_year, None, metric)
        tabs["payer_distribution"] = _build_tab_data(
            _rows_to_series(pyd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors,
            selected_label=tab3_label, auto_model="linear", add_total=True,
        )

        # Tab 4
        pwp_rows = get_payer_wise_product_yearly(cur, ta, from_year, train_end_year, None, metric)
        tabs["payer_wise_product"] = _build_hierarchical_tab_data(
            pwp_rows, month_range, month_labels, forecast_start_index, factors,
            selected_parent=tab3_label, selected_child=tab2_label, auto_model="linear",
        )

        # Tab 5
        pwpy_rows = get_product_wise_payer_yearly(cur, ta, from_year, train_end_year, "All", metric)
        tabs["product_wise_payer"] = _build_hierarchical_tab_data(
            pwpy_rows, month_range, month_labels, forecast_start_index, factors,
            selected_parent=tab2_label, selected_child=tab3_label, auto_model="linear",
        )

    else:
        # Tab 1 — auto-ETS with is_selected=True so multiplier is applied
        tmv_map = {scenario_name: {(r[0], r[1]): float(r[-1]) for r in _tmv_train}}
        tabs["total_market_volume"] = _build_tab_data(
            tmv_map, month_range, month_labels, forecast_start_index, tab1_factors,
        )

        # Tab 2 — sel_product gets user factors; others get auto-linear
        pd_rows = get_product_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, "All", metric)
        tabs["product_distribution"] = _build_tab_data(
            _rows_to_series(pd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors,
            selected_label=tab2_label, auto_model="linear", add_total=True,
        )

        # Tab 3 — sel_payer gets user factors; others get auto-linear
        pyd_rows = get_payer_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, None, metric)
        tabs["payer_distribution"] = _build_tab_data(
            _rows_to_series(pyd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors,
            selected_label=tab3_label, auto_model="linear", add_total=True,
        )

        # Tab 4
        pwp_rows = get_payer_wise_product(cur, ta, from_year, from_month, train_end_year, train_end_month, None, metric)
        tabs["payer_wise_product"] = _build_hierarchical_tab_data(
            pwp_rows, month_range, month_labels, forecast_start_index, factors,
            selected_parent=tab3_label, selected_child=tab2_label, auto_model="linear",
        )

        # Tab 5
        pwpy_rows = get_product_wise_payer(cur, ta, from_year, from_month, train_end_year, train_end_month, "All", metric)
        tabs["product_wise_payer"] = _build_hierarchical_tab_data(
            pwpy_rows, month_range, month_labels, forecast_start_index, factors,
            selected_parent=tab2_label, selected_child=tab3_label, auto_model="linear",
        )

    return month_labels, forecast_start_index, tabs, tab1_ets


# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

def _resolve_forecast_periods(to_date_str: str | None, train_end_year: int,
                               train_end_month: int, cfg_periods: int) -> int:
    """
    If the user supplied a to_date, compute forecast_periods from it.
    Otherwise fall back to the config value.
    to_date may be <= train_end_date (no forecast) or beyond it.
    """
    if not to_date_str:
        return cfg_periods
    to_year, to_month = _parse_ym(to_date_str)
    periods = (to_year - train_end_year) * 12 + (to_month - train_end_month)
    return max(periods, 0)


def _first(lst, default="All") -> str:
    """Return first non-'All' item from a list, or default."""
    non_all = [x for x in lst if x != "All"]
    return non_all[0] if non_all else default


def apply_liver_filters(payload: LiverApplyFiltersRequest) -> dict:
    from_year, from_month = _parse_ym(payload.from_date)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cfg = _load_config(cur, payload.ta,
                           payer=_first(payload.payer),
                           brand=_first(payload.brand))
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = _resolve_forecast_periods(
            payload.to_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity      = cfg.get("model_granularity", "monthly")

        # Load factors from saved scenario or estimate from data
        if payload.scenario != "Base":
            cur.execute("""
                SELECT factors FROM raw_liver.liver_scenarios WHERE scenario_name = %s
            """, (payload.scenario,))
            row = cur.fetchone()
            if row:
                try:
                    factors = LiverFactors(**row[0])
                except Exception:
                    factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)
            else:
                factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)
        else:
            factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)

        # apply_filters (Base): no selected payer/brand → all series use auto-linear
        month_labels, forecast_start_index, tabs, tab1_ets = _build_all_tabs(
            cur, payload.ta, payload.metric,
            from_year, from_month, train_end_year, train_end_month, forecast_periods, factors,
            granularity,
            scenario_name=payload.scenario or "Base",
        )

        response_factors = _build_response_factors(factors)
        response_factors["ets"] = {"alpha": tab1_ets.alpha, "beta": tab1_ets.beta, "gamma": tab1_ets.gamma}
        return {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "factors":              response_factors,
            "tabs":                 tabs,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Recalculate with user-provided factors
# ---------------------------------------------------------------------------

def _factors_from_request(f: LiverRecalculateFactors, model_type: str,
                           default_traj: str, default_duration: int) -> LiverFactors:
    """
    Build internal LiverFactors from the oncology-style recalculate request.
    Mirrors oncology's recalculate route which unpacks ets / growth separately.
    """
    ets_p  = f.ets    or EtsParams(alpha=0.3, beta=0.2, gamma=0.98)
    growth = f.growth

    tg   = growth.total_growth                                          if growth else 0.0
    dur  = growth.duration                                              if growth else default_duration
    traj = (growth.trajectory_start or default_traj)                   if growth else default_traj
    k    = (growth.k_value if growth and growth.k_value is not None else 1.0)

    return LiverFactors(
        active_model      = model_type,
        multiplier        = f.multiplier,
        multiplier_horizon= f.multiplier_horizon,
        ets               = EtsParams(alpha=ets_p.alpha, beta=ets_p.beta, gamma=ets_p.gamma),
        linear            = LinearParams(total_growth=tg,  duration=dur, trajectory_start=traj),
        exponential       = ExponentialParams(k_value=k, total_growth=tg, duration=dur, trajectory_start=traj),
        logarithmic       = LogarithmicParams(k_value=k, total_growth=tg, duration=dur, trajectory_start=traj),
        scurve            = SCurveParams(k_value=k,     total_growth=tg, duration=dur, trajectory_start=traj),
    )


def recalculate_liver(payload: LiverRecalculateRequest) -> dict:
    from_year, from_month = _parse_ym(payload.from_date)
    model_type = payload.model_type.lower()

    conn = get_connection()
    cur = conn.cursor()
    try:
        cfg = _load_config(cur, payload.ta,
                           payer=_first(payload.payer),
                           brand=_first(payload.brand))
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = _resolve_forecast_periods(
            payload.to_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity = cfg.get("model_granularity", "monthly")

        to_month_safe = train_end_month if granularity != "yearly" else 1
        default_traj  = date_type(train_end_year, to_month_safe, 1).isoformat()

        factors = _factors_from_request(
            payload.factors, model_type, default_traj, forecast_periods
        )

        # recalculate: selected payer+brand gets user factors; all others get auto-linear
        month_labels, forecast_start_index, tabs, tab1_ets = _build_all_tabs(
            cur, payload.ta, payload.metric,
            from_year, from_month, train_end_year, train_end_month, forecast_periods, factors,
            granularity,
            sel_payer=_first(payload.payer),
            sel_product=_first(payload.brand),
            scenario_name=payload.scenario or "Base",
        )

        response_factors = _build_response_factors(factors)
        # Match oncology: for ETS recalculate, echo back user's ETS values so sliders
        # show what was used for the selected series.
        # For non-ETS recalculate, show Tab 1's auto-estimated ETS (like oncology shows
        # stored DB ETS when model is not ETS).
        if model_type == "ets":
            response_factors["ets"] = {
                "alpha": factors.ets.alpha,
                "beta":  factors.ets.beta,
                "gamma": factors.ets.gamma,
            }
        else:
            response_factors["ets"] = {
                "alpha": tab1_ets.alpha,
                "beta":  tab1_ets.beta,
                "gamma": tab1_ets.gamma,
            }
        return {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "factors":              response_factors,
            "tabs":                 tabs,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Save scenario
# ---------------------------------------------------------------------------

def save_liver_scenario(payload: LiverSaveScenarioRequest) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        save_scenario(cur, payload, payload.chart_data)
        conn.commit()
        return {
            "scenario_name": payload.scenario_name,
            "message": f"Scenario '{payload.scenario_name}' saved successfully.",
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Helper: estimate ETS factors from transaction_data history
# ---------------------------------------------------------------------------

def _estimate_default_factors(cur, ta, from_year, from_month, to_year, to_month,
                               granularity: str = "monthly") -> LiverFactors:
    """Estimates ETS params from total market volume; builds full LiverFactors with defaults for other models."""
    if granularity == "yearly":
        cur.execute("""
            SELECT year, SUM(volume)
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year ORDER BY year
        """, (ta, from_year, to_year))
    else:
        cur.execute("""
            SELECT year, month, SUM(volume)
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month ORDER BY year, month
        """, (ta, from_year, from_month, to_year, to_month))

    rows   = cur.fetchall()
    values = [float(r[-1]) for r in rows if r[-1] is not None]

    if len(values) >= 4:
        alpha, beta, gamma = estimate_parameters(values)
        est_growth         = round(_estimate_linear_growth(values), 2)
    else:
        alpha, beta, gamma = 0.30, 0.20, 0.98
        est_growth         = 0.0

    to_month_safe      = to_month if granularity != "yearly" else 1
    trajectory_start   = date_type(to_year, to_month_safe, 1).isoformat()
    default_duration   = 12

    return LiverFactors(
        ets=EtsParams(alpha=round(alpha, 2), beta=round(beta, 2), gamma=round(gamma, 2)),
        linear=LinearParams(duration=default_duration, total_growth=est_growth, trajectory_start=trajectory_start),
        scurve=SCurveParams(k_value=1, duration=default_duration, total_growth=est_growth, trajectory_start=trajectory_start),
        exponential=ExponentialParams(k_value=1, duration=default_duration, total_growth=est_growth, trajectory_start=trajectory_start),
        logarithmic=LogarithmicParams(k_value=1, duration=default_duration, total_growth=est_growth, trajectory_start=trajectory_start),
        multiplier=1.0,
        multiplier_horizon="Forecast",
        active_model="linear",
    )
