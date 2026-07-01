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
    scenario_exists,
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
        for payer, brand, config, updated_at in db_rows:
            train_end    = date_type.fromisoformat(config["train_end_date"][:10])
            forecast_end = _add_months(train_end, int(config["forecast_periods"]))
            entries.append({
                "payer":              payer,
                "brand":              brand,
                "train_start_date":   config["train_start_date"][:10],
                "train_end_date":     config["train_end_date"][:10],
                "model_granularity":  config.get("model_granularity", "monthly"),
                "forecast_periods":   forecast_end.isoformat(),
                "updated_at":         updated_at,
            })

        # Use updated_at to find rows from the most recent save.
        # Those rows' payer/brand values represent the user's latest selection.
        latest_ts = max(e["updated_at"] for e in entries)
        latest_entries = [e for e in entries if e["updated_at"] == latest_ts]
        first = latest_entries[0]

        return {
            "ta_name": ta_name,
            "exists": True,
            "entries": entries,
            "available_train_months": available_train_months,
            "config": {
                "payer":             list(dict.fromkeys(e["payer"] for e in latest_entries)),
                "brand":             list(dict.fromkeys(e["brand"] for e in latest_entries)),
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
        payers = cfg.payer or []
        brands = cfg.brand or []
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


def _fmt_flat(tab, month_labels, forecast_start_index):
   
    return {
        "chart": {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "series": [
                {"label": s.label, "history": s.train_values, "forecast": s.forecast_values}
                for s in tab.chart.series
            ],
        },
        "table": {
            "type": "flat",
            "rows": [{"label": r.hierarchy, "values": r.values} for r in tab.table.rows],
        },
    }


def _fmt_hier(tab, month_labels, forecast_start_index):
    
    return {
        "chart": {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "series": [
                {"label": s.label, "history": s.train_values, "forecast": s.forecast_values}
                for s in tab.chart.series
            ],
        },
        "table": {
            "type": "hierarchy",
            "rows": [
                {
                    "label":    r.hierarchy,
                    "values":   r.total,
                    "children": [{"label": c.label, "values": c.values} for c in r.children],
                }
                for r in tab.table.rows
            ],
        },
    }


def _build_all_tabs_both_metrics(cur, ta, from_year, from_month,
                                  train_end_year, train_end_month, forecast_periods, factors,
                                  granularity="monthly",
                                  sel_payer=None, sel_product=None,
                                  force_tab1_ets=True,
                                  scenario_name="Base"):
    """
    Build all 5 tabs for BOTH market_volume and market_share.
    Returns (month_labels, forecast_start_index, market_analysis_dict, tab1_ets).
    market_analysis_dict keys: total_market_volume, product_distribution,
      market_distribution, market_product, product_market.
    Each key maps to { market_volume: {chart, table}, market_share: {chart, table} }.
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
    n                    = len(month_labels)
    fsi                  = forecast_start_index

    tab2_label = sel_product  # None → factors apply to all series
    tab3_label = sel_payer

    # ── Tab 1: TMV (ETS) — metric-independent ──────────────────────────────
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
    tab1_factors = factors.model_copy(update={"active_model": "ets", "ets": tab1_ets}) if force_tab1_ets else factors
    tmv_map      = {scenario_name: {(r[0], r[1]): float(r[-1]) for r in _tmv_train}}
    tab1_mv_data = _build_tab_data(tmv_map, month_range, month_labels, fsi, tab1_factors)
    # chart label shows "Total Market Volume"; table hierarchy keeps scenario_name
    for s in tab1_mv_data.chart.series:
        s.label = "Total Market Volume"

    # TMV market_share is trivially 100% (it IS the total market)
    tab1_ms = {
        "chart": {
            "months": month_labels, "forecast_start_index": fsi,
            "series": [{"label": "Total Market Volume",
                        "history":  [100.0] * fsi,
                        "forecast": [100.0] * (n - fsi)}],
        },
        "table": {
            "type": "flat",
            "rows": [{"label": "Total Market Volume", "values": [100.0] * n}],
        },
    }

    # ── Tabs 2-5: query for both metrics ────────────────────────────────────
    if is_yearly:
        pd_mv   = get_product_distribution_yearly(cur, ta, from_year, train_end_year, None, "market_volume")
        pd_ms   = get_product_distribution_yearly(cur, ta, from_year, train_end_year, None, "market_share")
        pyd_mv  = get_payer_distribution_yearly(cur, ta, from_year, train_end_year, None, "market_volume")
        pyd_ms  = get_payer_distribution_yearly(cur, ta, from_year, train_end_year, None, "market_share")
        pwp_mv  = get_payer_wise_product_yearly(cur, ta, from_year, train_end_year, None, "market_volume")
        pwp_ms  = get_payer_wise_product_yearly(cur, ta, from_year, train_end_year, None, "market_share")
        pwpy_mv = get_product_wise_payer_yearly(cur, ta, from_year, train_end_year, None, "market_volume")
        pwpy_ms = get_product_wise_payer_yearly(cur, ta, from_year, train_end_year, None, "market_share")
    else:
        pd_mv   = get_product_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_volume")
        pd_ms   = get_product_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_share")
        pyd_mv  = get_payer_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_volume")
        pyd_ms  = get_payer_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_share")
        pwp_mv  = get_payer_wise_product(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_volume")
        pwp_ms  = get_payer_wise_product(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_share")
        pwpy_mv = get_product_wise_payer(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_volume")
        pwpy_ms = get_product_wise_payer(cur, ta, from_year, from_month, train_end_year, train_end_month, None, "market_share")

    def bflat(rows, label):
        return _fmt_flat(
            _build_tab_data(_rows_to_series(rows, 2, 3), month_range, month_labels, fsi, factors,
                            selected_label=label, auto_model="linear", add_total=True),
            month_labels, fsi,
        )

    def bhier(rows, parent_lbl, child_lbl):
        return _fmt_hier(
            _build_hierarchical_tab_data(rows, month_range, month_labels, fsi, factors,
                                         selected_parent=parent_lbl, selected_child=child_lbl,
                                         auto_model="linear"),
            month_labels, fsi,
        )

    market_analysis = {
        "total_market_volume": {
            "market_volume": _fmt_flat(tab1_mv_data, month_labels, fsi),
            "market_share":  tab1_ms,
        },
        "product_distribution": {
            "market_volume": bflat(pd_mv,  tab2_label),
            "market_share":  bflat(pd_ms,  tab2_label),
        },
        "market_distribution": {
            "market_volume": bflat(pyd_mv, tab3_label),
            "market_share":  bflat(pyd_ms, tab3_label),
        },
        "market_product": {
            "market_volume": bhier(pwp_mv,  tab3_label, tab2_label),
            "market_share":  bhier(pwp_ms,  tab3_label, tab2_label),
        },
        "product_market": {
            "market_volume": bhier(pwpy_mv, tab2_label, tab3_label),
            "market_share":  bhier(pwpy_ms, tab2_label, tab3_label),
        },
    }

    return month_labels, forecast_start_index, market_analysis, tab1_ets


# ---------------------------------------------------------------------------
# Helper: load config or fall back to DB defaults
# ---------------------------------------------------------------------------

def _load_config(cur, ta: str, payer: str = None, brand: str = None) -> dict:
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

def get_liver_filters(ta: str = "HCV", payer: str = None, brand: str = None) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        payers   = get_payers(cur)
        products = get_products(cur)

        cfg       = _load_config(cur, ta, payer=payer, brand=brand)
        from_date = cfg["train_start_date"][:10]
        train_end = date_type.fromisoformat(cfg["train_end_date"][:10])
        to_date   = _add_months(train_end, int(cfg["forecast_periods"])).isoformat()

        from_year, from_month = _parse_ym(from_date)
        to_year,   to_month   = _parse_ym(to_date)
        all_months  = _generate_months(from_year, from_month, to_year, to_month)
        date_labels = [_month_label(y, m) for y, m in all_months]

        default_payer = payer or (payers[0] if payers else None)
        default_brand = brand or (products[0] if products else None)

        return {
            "ta_name":          ta,
            "markets":          payers,
            "products":         products,
            "available_months": date_labels,
            "selected_filter": {
                "market":     default_payer,
                "product":    default_brand,
                "start_date": from_date,
                "end_date":   to_date,
            },
        }
    finally:
        cur.close()
        conn.close()


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


def _first(lst, default=None) -> str:
    """Return first item from a list, or default."""
    return lst[0] if lst else default


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

        active_scenario   = payload.scenario or "Base"
        all_scenario_names = get_scenarios(cur)
        available_scenarios = ["Base"] + all_scenario_names

        saved_market_analysis = None

        # Load factors (and saved market_analysis) for the active scenario
        if active_scenario != "Base":
            cur.execute(
                "SELECT factors, chart_data FROM raw_liver.liver_scenarios WHERE scenario_name = %s",
                (active_scenario,),
            )
            row = cur.fetchone()
            if row:
                try:
                    factors = LiverFactors(**row[0])
                except Exception:
                    factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)
                saved_cd = row[1] if row[1] else {}
                if isinstance(saved_cd, dict) and "market_analysis" in saved_cd:
                    saved_market_analysis = saved_cd["market_analysis"]
            else:
                factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)
        else:
            factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)

        if saved_market_analysis:
            # Use the exact data that was saved (includes any edited table values)
            # Recalculate market_share from market_volume to ensure consistency on load
            market_analysis = _recompute_all_market_shares(saved_market_analysis)
            # Still need tab1_ets for the factor sliders
            if granularity == "yearly":
                _tmv_train = get_total_market_volume_yearly(cur, payload.ta, from_year, train_end_year, None)
            else:
                _tmv_train = get_total_market_volume(cur, payload.ta, from_year, from_month, train_end_year, train_end_month, None)
            _tmv_values = [float(r[-1]) for r in _tmv_train if r[-1] is not None]
            if len(_tmv_values) >= 4:
                _t1a, _t1b, _t1g = estimate_parameters(_tmv_values)
            else:
                _t1a, _t1b, _t1g = 0.30, 0.20, 0.98
            tab1_ets = EtsParams(alpha=round(_t1a, 4), beta=round(_t1b, 4), gamma=round(_t1g, 4))
        else:
            _, _, market_analysis, tab1_ets = _build_all_tabs_both_metrics(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, factors,
                granularity, scenario_name=payload.scenario,
            )

        response_factors = _build_response_factors(factors)
        response_factors["active_model"] = "ets"
        response_factors["ets"] = {"alpha": tab1_ets.alpha, "beta": tab1_ets.beta, "gamma": tab1_ets.gamma}

        train_end_dt = date_type(train_end_year, train_end_month, 1)
        end_date     = _add_months(train_end_dt, forecast_periods).isoformat()

        # ── Build TMV data for inactive scenarios ─────────────────────────────
        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        all_saved_cd = {r[0]: (r[1] or {}) for r in cur.fetchall()}

        if active_scenario != "Base":
            base_factors = _estimate_default_factors(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            _, _, _base_ma, _ = _build_all_tabs_both_metrics(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, base_factors,
                granularity, scenario_name="Base",
            )
            base_tmv = _base_ma.get("total_market_volume", {})
        else:
            base_tmv = market_analysis.get("total_market_volume", {})

        def _tmv_table_only(tmv: dict) -> dict:
            """Keep only the table rows from TMV, drop chart data."""
            return {
                metric: {"table": tmv[metric]["table"]}
                for metric in ("market_volume", "market_share")
                if metric in tmv and "table" in tmv[metric]
            }

        def _inactive_stub(sc_name):
            if sc_name == "Base":
                tmv = base_tmv
            else:
                cd = all_saved_cd.get(sc_name, {})
                tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
            return {"market_analysis": {"total_market_volume": _tmv_table_only(tmv)}}

        scenarios = {
            sc: (
                {"factors": response_factors, "market_analysis": market_analysis}
                if sc == active_scenario
                else _inactive_stub(sc)
            )
            for sc in available_scenarios
        }

        return {
            "ta_name":            payload.ta,
            "selected_filter": {
                "market":     _first(payload.payer),
                "product":    _first(payload.brand),
                "start_date": payload.from_date,
                "end_date":   end_date,
            },
            "available_scenarios": available_scenarios,
            "active_scenario":     active_scenario,
            "scenarios":           scenarios,
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
    Build internal LiverFactors from the recalculate request.
    Only the active model's params are required; defaults fill in the rest.
    """
    ets_p = f.ets or EtsParams(alpha=0.3, beta=0.2, gamma=0.98)

    _GROWTH_MODELS = ("linear", "exponential", "logarithmic", "scurve")
    active_growth = (
        getattr(f, model_type, None) if model_type in _GROWTH_MODELS else None
    ) or f.growth

    tg   = active_growth.total_growth                                           if active_growth else 0.0
    dur  = active_growth.duration                                               if active_growth else default_duration
    traj = (active_growth.trajectory_start or default_traj)                    if active_growth else default_traj
    k    = (active_growth.k_value if active_growth and active_growth.k_value is not None else 1.0)

    lin  = f.linear      or active_growth
    exp  = f.exponential or active_growth
    log_ = f.logarithmic or active_growth
    sc   = f.scurve      or active_growth

    def _g(g):
        return (g.total_growth if g else tg,
                g.duration     if g else dur,
                g.trajectory_start or default_traj if g else traj,
                g.k_value if g and g.k_value is not None else k)

    lin_tg,  lin_dur,  lin_traj,  _    = _g(lin)
    exp_tg,  exp_dur,  exp_traj,  exp_k = _g(exp)
    log_tg,  log_dur,  log_traj,  log_k = _g(log_)
    sc_tg,   sc_dur,   sc_traj,   sc_k  = _g(sc)

    return LiverFactors(
        active_model       = model_type,
        multiplier         = f.multiplier,
        multiplier_horizon = f.multiplier_horizon,
        ets                = EtsParams(alpha=ets_p.alpha, beta=ets_p.beta, gamma=ets_p.gamma),
        linear             = LinearParams(total_growth=lin_tg, duration=lin_dur, trajectory_start=lin_traj),
        exponential        = ExponentialParams(k_value=exp_k, total_growth=exp_tg, duration=exp_dur, trajectory_start=exp_traj),
        logarithmic        = LogarithmicParams(k_value=log_k, total_growth=log_tg, duration=log_dur, trajectory_start=log_traj),
        scurve             = SCurveParams(k_value=sc_k,  total_growth=sc_tg,  duration=sc_dur,  trajectory_start=sc_traj),
    )


def recalculate_liver(payload: LiverRecalculateRequest) -> dict:
    sf         = payload.selected_filter
    from_date  = sf.start_date
    market     = sf.market
    product    = sf.product
    model_type = payload.model_type.lower()

    from_year, from_month = _parse_ym(from_date)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cfg = _load_config(cur, payload.ta_name, payer=market, brand=product)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = cfg["forecast_periods"]
        granularity      = cfg.get("model_granularity", "monthly")

        to_month_safe = train_end_month if granularity != "yearly" else 1
        default_traj  = date_type(train_end_year, to_month_safe, 1).isoformat()

        factors = _factors_from_request(
            payload.factors, model_type, default_traj, forecast_periods
        )

        # When ETS is active the user sends no growth params → fill them in from
        # training-data estimates so the response sliders show sensible defaults.
        if model_type == "ets":
            estimated = _estimate_default_factors(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            factors = factors.model_copy(update={
                "linear":      estimated.linear,
                "exponential": estimated.exponential,
                "logarithmic": estimated.logarithmic,
                "scurve":      estimated.scurve,
            })

        active_scenario    = payload.scenario_name or "Base"
        all_scenario_names = get_scenarios(cur)
        available_scenarios = ["Base"] + all_scenario_names

        _, _, market_analysis, tab1_ets = _build_all_tabs_both_metrics(
            cur, payload.ta_name, from_year, from_month,
            train_end_year, train_end_month, forecast_periods, factors,
            granularity,
            force_tab1_ets=False, scenario_name=payload.scenario_name,
        )

        response_factors = _build_response_factors(factors)
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

        train_end_dt = date_type(train_end_year, train_end_month, 1)
        end_date     = _add_months(train_end_dt, forecast_periods).isoformat()

        # ── Build TMV data for inactive scenarios ─────────────────────────────
        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        all_saved_cd_rc = {r[0]: (r[1] or {}) for r in cur.fetchall()}

        if active_scenario != "Base":
            _base_f = _estimate_default_factors(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            _, _, _base_ma_rc, _ = _build_all_tabs_both_metrics(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, _base_f,
                granularity, scenario_name="Base",
            )
            base_tmv_rc = _base_ma_rc.get("total_market_volume", {})
        else:
            base_tmv_rc = market_analysis.get("total_market_volume", {})

        def _tmv_table_only_rc(tmv: dict) -> dict:
            return {
                metric: {"table": tmv[metric]["table"]}
                for metric in ("market_volume", "market_share")
                if metric in tmv and "table" in tmv[metric]
            }

        def _inactive_stub_rc(sc_name):
            if sc_name == "Base":
                tmv = base_tmv_rc
            else:
                cd = all_saved_cd_rc.get(sc_name, {})
                tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
            return {"market_analysis": {"total_market_volume": _tmv_table_only_rc(tmv)}}

        scenarios = {
            sc: (
                {"factors": response_factors, "market_analysis": market_analysis}
                if sc == active_scenario
                else _inactive_stub_rc(sc)
            )
            for sc in available_scenarios
        }

        return {
            "ta_name": payload.ta_name,
            "selected_filter": {
                "market":     market,
                "product":    product,
                "start_date": from_date,
                "end_date":   end_date,
            },
            "available_scenarios": available_scenarios,
            "active_scenario":     active_scenario,
            "scenarios":           scenarios,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Save scenario helpers
# ---------------------------------------------------------------------------

def _recompute_all_market_shares(market_analysis: dict) -> dict:
    """
    Recompute market_share for every tab from the current market_volume values.
    - total_market_volume  → always 100 %
    - product_distribution / market_distribution → each row / total_volume * 100
    - market_product / product_market (hierarchical) → child / parent_total * 100
    """
    tmv_rows = (
        market_analysis.get("total_market_volume", {})
        .get("market_volume", {})
        .get("table", {})
        .get("rows", [])
    )
    total_vals = tmv_rows[0].get("values", []) if tmv_rows else []
    n = len(total_vals)

    tmv_chart  = (
        market_analysis.get("total_market_volume", {})
        .get("market_volume", {})
        .get("chart", {})
    )
    fsi = tmv_chart.get("forecast_start_index", 0)

    # ── Tab 1: always 100 % ───────────────────────────────────────────────
    tmv_ms = market_analysis.get("total_market_volume", {}).get("market_share", {})
    if tmv_ms:
        for r in tmv_ms.get("table", {}).get("rows", []):
            r["values"] = [100.0] * n
        for s in tmv_ms.get("chart", {}).get("series", []):
            s["history"]  = [100.0] * fsi
            s["forecast"] = [100.0] * (n - fsi)

    # ── Flat distribution tabs (2, 3) ─────────────────────────────────────
    for tab in ("product_distribution", "market_distribution"):
        if tab not in market_analysis:
            continue
        mv_data = market_analysis[tab].get("market_volume", {})
        ms_data = market_analysis[tab].get("market_share", {})
        if not ms_data:
            continue

        ms_row_map = {r.get("label", ""): r for r in ms_data.get("table", {}).get("rows", [])}
        ms_ser_map = {s.get("label", ""): s for s in ms_data.get("chart", {}).get("series", [])}

        for r in mv_data.get("table", {}).get("rows", []):
            lbl = r.get("label", "")
            if lbl.lower() == "total":
                if lbl in ms_row_map:
                    ms_row_map[lbl]["values"] = [100.0] * n
                continue
            mv_vals = r.get("values", [])
            ms_vals = [
                round(float(mv_vals[i]) / float(total_vals[i]) * 100, 4)
                if i < len(mv_vals) and i < n and float(total_vals[i]) != 0
                else 0.0
                for i in range(n)
            ]
            if lbl in ms_row_map:
                ms_row_map[lbl]["values"] = ms_vals
            if lbl in ms_ser_map:
                ms_ser_map[lbl]["history"]  = ms_vals[:fsi]
                ms_ser_map[lbl]["forecast"] = ms_vals[fsi:]

    # ── Hierarchical cross-tabs (4, 5): child / parent_total * 100 ────────
    for tab in ("market_product", "product_market"):
        if tab not in market_analysis:
            continue
        mv_data = market_analysis[tab].get("market_volume", {})
        ms_data = market_analysis[tab].get("market_share", {})
        if not ms_data:
            continue

        ms_hier_map  = {r.get("label", ""): r for r in ms_data.get("table", {}).get("rows", [])}
        ms_chart_map = {s.get("label", ""): s for s in ms_data.get("chart", {}).get("series", [])}

        for mv_row in mv_data.get("table", {}).get("rows", []):
            parent_lbl  = mv_row.get("label", "")
            parent_vals = mv_row.get("values", [])
            ms_parent   = ms_hier_map.get(parent_lbl, {})
            if ms_parent:
                ms_parent["values"] = [100.0] * n

            for child in mv_row.get("children", []):
                child_lbl  = child.get("label", "")
                child_vals = child.get("values", [])
                child_ms   = [
                    round(float(child_vals[i]) / float(parent_vals[i]) * 100, 4)
                    if i < len(child_vals) and i < len(parent_vals) and float(parent_vals[i]) != 0
                    else 0.0
                    for i in range(n)
                ]
                if ms_parent:
                    for c in ms_parent.get("children", []):
                        if c.get("label") == child_lbl:
                            c["values"] = child_ms
                            break
                chart_key = f"{parent_lbl} - {child_lbl}"
                if chart_key in ms_chart_map:
                    ms_chart_map[chart_key]["history"]  = child_ms[:fsi]
                    ms_chart_map[chart_key]["forecast"] = child_ms[fsi:]

    return market_analysis


# ---------------------------------------------------------------------------
# Save scenario
# ---------------------------------------------------------------------------

def _build_and_save_market_analysis(cur, conn, payload) -> dict:
    """
    Shared core used by both save_liver_scenario and update_liver_scenario.
    Builds market_analysis, applies the edited tab, propagates, recalculates
    market_share, then persists to DB.
    """
    from_year, from_month = _parse_ym(payload.from_date)
    cfg = _load_config(cur, payload.ta, _first(payload.payer), _first(payload.brand))
    train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
    forecast_periods = cfg["forecast_periods"]
    granularity = cfg.get("model_granularity", "monthly")

    fdict = payload.factors if isinstance(payload.factors, dict) else payload.factors.dict()
    try:
        factors = LiverFactors(
            ets=EtsParams(**fdict.get("ets", {})),
            linear=LinearParams(**fdict.get("linear", {})),
            scurve=SCurveParams(**fdict.get("scurve", {})),
            exponential=ExponentialParams(**fdict.get("exponential", {})),
            logarithmic=LogarithmicParams(**fdict.get("logarithmic", {})),
            multiplier=fdict.get("multiplier", 1.0),
            multiplier_horizon=fdict.get("multiplier_horizon", "Forecast"),
            active_model=fdict.get("active_model", "ets"),
        )
    except Exception:
        factors = _estimate_default_factors(cur, payload.ta, from_year, from_month,
                                            train_end_year, train_end_month, granularity)

    _, _, market_analysis, _ = _build_all_tabs_both_metrics(
        cur, payload.ta, from_year, from_month,
        train_end_year, train_end_month, forecast_periods, factors,
        granularity, scenario_name=payload.scenario_name,
    )

    raw_cd = payload.chart_data or {}
    edited_chart = raw_cd.get("chart") or {}
    edited_table = raw_cd.get("table") or []

    if edited_chart or edited_table:
        months = edited_chart.get("months") or []
        fsi    = edited_chart.get("forecast_start_index") or 0
        n      = len(months)

        hier_labels = [r.get("hierarchy") or r.get("label") for r in edited_table]
        has_total   = any(h and h.lower() == "total" for h in hier_labels)

        if not has_total:
            tab_key = "total_market_volume"
        else:
            non_total = [h for h in hier_labels if h and h.lower() != "total"]
            products = get_products(cur)
            payers   = get_payers(cur)
            if non_total and non_total[0] in products:
                tab_key = "product_distribution"
            elif non_total and non_total[0] in payers:
                tab_key = "market_distribution"
            else:
                tab_key = "product_distribution"

        metric_key = payload.metric or "market_volume"

        new_series = [
            {
                "label":    s.get("label", ""),
                "history":  s.get("history") or s.get("train_values") or [],
                "forecast": s.get("forecast") or s.get("forecast_values") or [],
            }
            for s in (edited_chart.get("series") or [])
        ]

        new_table_rows = []
        for r in edited_table:
            lbl     = r.get("hierarchy") or r.get("label") or ""
            monthly = r.get("monthly_data") or {}
            vals    = [monthly.get(m, 0) for m in months] if months else list(monthly.values())
            new_table_rows.append({"label": lbl, "values": vals})

        edited_tab_data = {
            "chart": {"months": months, "forecast_start_index": fsi, "series": new_series},
            "table": {"type": "flat", "rows": new_table_rows},
        }

        if metric_key == "market_volume":
            dist_tabs = ["product_distribution", "market_distribution",
                         "market_product", "product_market"]

            if tab_key == "total_market_volume":
                old_tmv_rows = (
                    market_analysis.get("total_market_volume", {})
                    .get("market_volume", {})
                    .get("table", {}).get("rows", [])
                )
                old_total = list(old_tmv_rows[0].get("values", [])) if old_tmv_rows else []
                new_total = list(new_table_rows[0].get("values", [])) if new_table_rows else []

                market_analysis["total_market_volume"]["market_volume"] = edited_tab_data

                scale = [
                    float(new_total[i]) / float(old_total[i])
                    if i < len(old_total) and float(old_total[i]) != 0 else 1.0
                    for i in range(n)
                ]
                for dt in dist_tabs:
                    if dt not in market_analysis:
                        continue
                    mv_data = market_analysis[dt].get("market_volume", {})
                    for s in (mv_data.get("chart", {}).get("series") or []):
                        h = s.get("history", [])
                        f = s.get("forecast", [])
                        s["history"]  = [round(float(h[i]) * scale[i], 4) if i < len(h) else 0.0 for i in range(fsi)]
                        s["forecast"] = [round(float(f[i]) * scale[fsi + i], 4) if i < len(f) else 0.0 for i in range(n - fsi)]
                    for r in (mv_data.get("table", {}).get("rows") or []):
                        vals = r.get("values", [])
                        r["values"] = [round(float(vals[i]) * scale[i], 4) if i < len(vals) else 0.0 for i in range(n)]
                        for child in r.get("children", []):
                            cvals = child.get("values", [])
                            child["values"] = [round(float(cvals[i]) * scale[i], 4) if i < len(cvals) else 0.0 for i in range(n)]
            else:
                if tab_key in market_analysis:
                    market_analysis[tab_key]["market_volume"] = edited_tab_data

                non_total_rows = [r for r in new_table_rows if r.get("label", "").lower() != "total"]
                if non_total_rows:
                    new_total_vals = [0.0] * n
                    for r in non_total_rows:
                        for i, v in enumerate(r.get("values", [])):
                            if i < n:
                                new_total_vals[i] += float(v)

                    tmv_mv = market_analysis.get("total_market_volume", {}).get("market_volume", {})
                    tmv_rows = tmv_mv.get("table", {}).get("rows", [])
                    if tmv_rows:
                        tmv_rows[0]["values"] = [round(v, 4) for v in new_total_vals]
                    tmv_series = tmv_mv.get("chart", {}).get("series", [])
                    if tmv_series:
                        tmv_series[0]["history"]  = [round(v, 4) for v in new_total_vals[:fsi]]
                        tmv_series[0]["forecast"] = [round(v, 4) for v in new_total_vals[fsi:]]
        else:
            if tab_key in market_analysis and metric_key in market_analysis[tab_key]:
                market_analysis[tab_key][metric_key] = edited_tab_data

    market_analysis = _recompute_all_market_shares(market_analysis)
    save_scenario(cur, payload, {"market_analysis": market_analysis})
    conn.commit()

    # Build response identical to apply_liver_filters (minus selected_filter)
    from_year, from_month = _parse_ym(payload.from_date)
    cfg = _load_config(cur, payload.ta, _first(payload.payer), _first(payload.brand))
    train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
    forecast_periods = cfg["forecast_periods"]
    granularity = cfg.get("model_granularity", "monthly")

    response_factors = _build_response_factors(factors)

    all_scenario_names = get_scenarios(cur)
    available_scenarios = ["Base"] + all_scenario_names
    active_scenario = payload.scenario_name

    cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
    all_saved_cd = {r[0]: (r[1] or {}) for r in cur.fetchall()}

    base_factors = _estimate_default_factors(
        cur, payload.ta, from_year, from_month,
        train_end_year, train_end_month, granularity,
    )
    _, _, _base_ma, _ = _build_all_tabs_both_metrics(
        cur, payload.ta, from_year, from_month,
        train_end_year, train_end_month, forecast_periods, base_factors,
        granularity, scenario_name="Base",
    )
    base_tmv = _base_ma.get("total_market_volume", {})

    def _tmv_table_only(tmv: dict) -> dict:
        return {
            metric: {"table": tmv[metric]["table"]}
            for metric in ("market_volume", "market_share")
            if metric in tmv and "table" in tmv[metric]
        }

    def _inactive_stub(sc_name):
        if sc_name == "Base":
            tmv = base_tmv
        else:
            cd = all_saved_cd.get(sc_name, {})
            tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
        return {"market_analysis": {"total_market_volume": _tmv_table_only(tmv)}}

    scenarios = {
        sc: (
            {"factors": response_factors, "market_analysis": market_analysis}
            if sc == active_scenario
            else _inactive_stub(sc)
        )
        for sc in available_scenarios
    }

    return {
        "ta_name":            payload.ta,
        "available_scenarios": available_scenarios,
        "active_scenario":     active_scenario,
        "scenarios":           scenarios,
    }


def save_liver_scenario(payload: LiverSaveScenarioRequest) -> dict:
    if payload.scenario_name.strip().lower() == "base":
        raise ValueError(
            "Cannot overwrite the Base scenario. Please provide a different scenario name."
        )

    conn = get_connection()
    cur = conn.cursor()
    try:
        if scenario_exists(cur, payload.scenario_name):
            raise ValueError(
                f"Scenario '{payload.scenario_name}' already exists. "
                "Use Update Scenario to overwrite it, or choose a different name."
            )
        return _build_and_save_market_analysis(cur, conn, payload)
    finally:
        cur.close()
        conn.close()


def update_liver_scenario(payload: LiverSaveScenarioRequest) -> dict:
    if payload.scenario_name.strip().lower() == "base":
        raise ValueError("The Base scenario cannot be updated.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if not scenario_exists(cur, payload.scenario_name):
            raise ValueError(
                f"Scenario '{payload.scenario_name}' does not exist. "
                "Use Save Scenario to create a new scenario first."
            )
        return _build_and_save_market_analysis(cur, conn, payload)
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

# ---------------------------------------------------------------------------
# Refresh Liver Table and chart
# ---------------------------------------------------------------------------

def refresh_liver_table(payload):
    from_year, from_month = _parse_ym(payload.from_date)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cfg = _load_config(cur, payload.ta, _first(payload.payer), _first(payload.brand))
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = cfg["forecast_periods"]
        granularity = cfg.get("model_granularity", "monthly")

        # Rebuild the full month range (same logic as _build_all_tabs)
        forecast_end_dt = datetime(train_end_year, train_end_month, 1) + relativedelta(months=forecast_periods)
        month_range = _generate_months(from_year, from_month, forecast_end_dt.year, forecast_end_dt.month)
        actual_range = _generate_months(from_year, from_month, train_end_year, train_end_month)
        month_labels = [_month_label(y, m, granularity) for y, m in month_range]
        forecast_start_index = len(actual_range)

        # Filter to only the active scenario's row — frontend may send all scenarios
        active_scenario = payload.scenario or "Base"
        active_table = [r for r in payload.table if r.hierarchy == active_scenario] or payload.table

        is_dist_tab      = payload.tab_key in ("product_distribution", "market_distribution")
        total_row_input  = next((r for r in active_table if r.hierarchy.lower() == "total"), None)
        non_total_rows   = [r for r in active_table if r.hierarchy.lower() != "total"]

        # For distribution tabs: validate + proportionally redistribute when edited_hierarchy is set
        if is_dist_tab and payload.edited_hierarchy and total_row_input:
            edited_row  = next((r for r in non_total_rows if r.hierarchy == payload.edited_hierarchy), None)
            other_rows  = [r for r in non_total_rows if r.hierarchy != payload.edited_hierarchy]

            if edited_row:
                n_vals = len(total_row_input.values)

                # Validate: no edited value may exceed the Total for that month
                for i, edited_val in enumerate(edited_row.values):
                    total_val = float(total_row_input.values[i]) if i < n_vals else 0.0
                    if float(edited_val) > total_val:
                        raise ValueError(
                            f"'{payload.edited_hierarchy}' value ({edited_val}) exceeds "
                            f"Total ({total_val}) at month index {i + 1}"
                        )

                # Redistribute remaining proportionally among the other rows
                redistributed_others = []
                for other_row in other_rows:
                    new_vals = []
                    for i in range(len(other_row.values)):
                        total_val   = float(total_row_input.values[i]) if i < n_vals else 0.0
                        edited_val  = float(edited_row.values[i]) if i < len(edited_row.values) else 0.0
                        remaining   = max(0.0, total_val - edited_val)
                        other_total = sum(
                            float(r.values[i]) if i < len(r.values) else 0.0
                            for r in other_rows
                        )
                        old_val = float(other_row.values[i]) if i < len(other_row.values) else 0.0
                        if other_total > 0:
                            new_vals.append(round((old_val / other_total) * remaining, 4))
                        else:
                            new_vals.append(0.0)
                    redistributed_others.append(
                        TableRow(hierarchy=other_row.hierarchy, values=new_vals)
                    )
                non_total_rows = [edited_row] + redistributed_others

        # Build chart series from (redistributed) non_total_rows
        series = []
        for row in non_total_rows:
            vals = row.values
            series.append({
                "label":   row.hierarchy,
                "history":  list(vals[:forecast_start_index]),
                "forecast": list(vals[forecast_start_index:]),
            })

        # Recompute Total row as sum of non_total_rows
        n = len(month_labels)
        total_vals = [0.0] * n
        for row in non_total_rows:
            for i, v in enumerate(row.values):
                if i < n:
                    total_vals[i] += round(v, 4)

        # Distribution tabs get a recomputed Total row prepended; Tab 1 has no Total row
        table_rows = []
        if is_dist_tab:
            table_rows.append({"label": "Total", "values": [round(v, 4) for v in total_vals]})
        for row in non_total_rows:
            table_rows.append({"label": row.hierarchy, "values": list(row.values)})

        return {
            "chart": {
                "months":               month_labels,
                "forecast_start_index": forecast_start_index,
                "series":               series,
            },
            "table": {
                "type": "flat",
                "rows": table_rows,
            },
        }
    finally:
        cur.close()
        conn.close()