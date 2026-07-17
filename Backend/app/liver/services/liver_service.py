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
    MovingAverageParams,
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
    SaveScenarioRequest,
    ActivateScenarioRequest,
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

def _forecast_moving_average(train_values: list, forecast_count: int, window: int) -> list:
    """Rolling moving average — mirrors HIV process_moving_average_forecast core logic.
    Used for the user-selected MA model (Tab1/Tab2/Tab3 selected series).
    """
    window = max(1, int(window))
    history = list(train_values)
    result = []
    for _ in range(forecast_count):
        avg = sum(history[-window:]) / window
        history.append(avg)
        result.append(round(avg, 2))
    return result


def _simple_moving_average_forecast(train_values: list, forecast_count: int, window: int = 6) -> list:
    """Simple (non-rolling) moving average: constant flat line = mean of last N non-zero values.
    Used for auto_model='moving_average' on individual payer-product series (Tab4/Tab5).
    Rolling MA on sparse/seasonal series produces zig-zag; simple MA gives clean IPF starting points.
    """
    window = max(1, int(window))
    non_zero = [v for v in train_values if v > 0]
    pool = (non_zero if non_zero else train_values)[-window:]
    avg = sum(pool) / len(pool) if pool else 0.0
    return [round(avg, 2)] * forecast_count


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
        elif auto_model == "moving_average":
            fc = _simple_moving_average_forecast(original_train, forecast_count, window=6)
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
    elif active == "moving_average":
        window = getattr(factors.moving_average, "window", 6) if factors.moving_average else 6
        fc = _forecast_moving_average(original_train, forecast_count, window=window)
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


def _forecast_share_by_factors(train_values: list, forecast_count: int, factors) -> list:
    """Apply the user's active model to a share (%) training series.
    MA window is clamped to a minimum of 3.
    """
    if not train_values or all(v == 0 for v in train_values):
        return [0.0] * forecast_count
    active = factors.active_model.lower()
    base   = train_values[-1]
    if active == "ets":
        a, b, g = (estimate_parameters(train_values) if len(train_values) >= 4
                   else (0.30, 0.20, 0.98))
        return forecast_ets(train_values, forecast_count, a, b, g, "nps")
    if active == "moving_average":
        window = max(3, getattr(factors.moving_average, "window", 6) if factors.moving_average else 6)
        return _forecast_moving_average(train_values, forecast_count, window=window)
    f_params = getattr(factors, active, None)
    if f_params is None or not hasattr(f_params, "total_growth"):
        return _simple_moving_average_forecast(train_values, forecast_count, window=6)
    tg  = f_params.total_growth
    dur = f_params.duration
    k   = getattr(f_params, "k_value", None)
    if active == "linear":
        return forecast_linear(base, forecast_count, tg, dur, "nps")
    if active == "exponential":
        return forecast_exponential(base, forecast_count, tg, dur, k, "nps")
    if active == "logarithmic":
        return forecast_logarithmic(base, forecast_count, tg, dur, k, "nps")
    if active == "scurve":
        return forecast_s_curve(base, forecast_count, tg, dur, k, "nps")
    return _simple_moving_average_forecast(train_values, forecast_count, window=6)


def _build_tab_data_from_shares(share_series_dict, vol_series_dict, month_range, month_labels,
                                  forecast_start_index, factors, tmv_fc,
                                  selected_label=None, add_total=False):
    """
    Forecast each series' market share (%), normalize to 100 per period, then multiply
    by TMV forecast to produce volume forecasts.  Historical values come from actual
    volume data (vol_series_dict) so actuals are never touched.

    selected_label: that label uses user factors on its share; all others use simple MA.
    """
    fsi = forecast_start_index
    historical_months = month_range[:fsi]
    forecast_count = len(month_range) - fsi

    # ── Step 1: forecast the selected label's share directly ─────────────────
    # When a label is explicitly selected, apply the user's model to that series
    # and distribute the remainder proportionally to all other labels based on
    # their last-training-period shares.  This avoids the normalization-denominator
    # problem: if we normalize all forecasts together, simple-MA inflation on other
    # series can depress the selected series below its base even when growth > 0.
    labels = list(share_series_dict.keys())

    # Collect last-training share for every label (used for remainder distribution)
    last_train_share = {}
    for label, share_map in share_series_dict.items():
        vals = [float(share_map.get((y, m), 0)) for y, m in historical_months]
        last_train_share[label] = vals[-1] if vals else 0.0

    sel_fc_shares = {}   # final per-period share for each label

    if selected_label is not None and selected_label in share_series_dict:
        # -- Selected series: apply user's model directly --
        sel_share_map = share_series_dict[selected_label]
        sel_train = [float(sel_share_map.get((y, m), 0)) for y, m in historical_months]
        sel_raw = _forecast_share_by_factors(sel_train, forecast_count, factors)
        sel_fc_shares[selected_label] = [min(100.0, max(0.0, v)) for v in sel_raw]

        # -- Other series: distribute remainder proportionally from last training shares --
        other_labels = [l for l in labels if l != selected_label]
        other_base_sum = sum(last_train_share.get(l, 0.0) for l in other_labels)
        for l in other_labels:
            sel_fc_shares[l] = []
        for i in range(forecast_count):
            remainder = max(0.0, 100.0 - sel_fc_shares[selected_label][i])
            for l in other_labels:
                base_share = last_train_share.get(l, 0.0)
                sel_fc_shares[l].append(
                    remainder * base_share / other_base_sum if other_base_sum > 0 else 0.0
                )
    else:
        # No explicit selection — apply user's model to every series then normalize
        raw_fc = {}
        for label, share_map in share_series_dict.items():
            share_train = [float(share_map.get((y, m), 0)) for y, m in historical_months]
            raw_fc[label] = _forecast_share_by_factors(share_train, forecast_count, factors)
        for i in range(forecast_count):
            total = sum(raw_fc[l][i] for l in raw_fc)
            for l in raw_fc:
                sel_fc_shares.setdefault(l, []).append(
                    raw_fc[l][i] / total * 100.0 if total > 0 else 0.0
                )

    # Volume forecast = share% / 100 * TMV forecast
    chart_series, table_rows = [], []
    for label in share_series_dict:
        vol_map   = vol_series_dict.get(label, {})
        vol_train = [float(vol_map.get((y, m), 0)) for y, m in historical_months]
        fc_share  = sel_fc_shares.get(label, [0.0] * forecast_count)
        vol_fc    = [fc_share[i] / 100.0 * (tmv_fc[i] if i < len(tmv_fc) else 0.0)
                     for i in range(forecast_count)]
        chart_series.append(ChartSeries(label=label, train_values=vol_train, forecast_values=vol_fc))
        table_rows.append(TableRow(hierarchy=label, values=vol_train + vol_fc))

    if add_total and table_rows:
        n = len(month_range)
        total_vals = [0.0] * n
        for row in table_rows:
            for i, v in enumerate(row.values[:n]):
                total_vals[i] += v
        table_rows.insert(0, TableRow(hierarchy="Total", values=[round(v, 4) for v in total_vals]))

    return TabData(
        chart=TabChart(series=chart_series),
        table=TabTable(headers=month_labels, rows=table_rows),
    )


def _build_hierarchical_tab_data_from_shares(rows_ms, rows_mv, month_range, month_labels,
                                               forecast_start_index, factors=None,
                                               selected_child=None):
    """
    Build hierarchical tab data (Tab4/Tab5) by forecasting within-parent market shares,
    normalizing within each parent to 100 %, then converting to volume using a simple
    MA parent-volume estimate.  IPF (called after this) corrects absolute levels to
    match Tab2/Tab3 constraints.

    selected_child: the child label matching the UI filter — uses the user's projection
    model on its within-parent share; all other children use simple MA.
    """
    fsi = forecast_start_index
    historical_months = month_range[:fsi]
    forecast_count = len(month_range) - fsi

    # Group share rows: parent → child → {(year,month): share%}
    grouped_ms = {}
    for r in rows_ms:
        key = (r[0], r[1])
        parent, child = r[2], r[3]
        val = float(r[4]) if r[4] is not None else 0.0
        grouped_ms.setdefault(parent, {}).setdefault(child, {})[key] = val

    # Group volume rows: parent → child → {(year,month): volume}
    grouped_mv = {}
    for r in rows_mv:
        key = (r[0], r[1])
        parent, child = r[2], r[3]
        val = float(r[4]) if r[4] is not None else 0.0
        grouped_mv.setdefault(parent, {}).setdefault(child, {})[key] = val

    chart_series, table_rows = [], []

    for parent, children_ms in grouped_ms.items():
        children_mv = grouped_mv.get(parent, {})

        # Forecast within-parent share for each child.
        # Same approach as _build_tab_data_from_shares: when a child is selected,
        # apply the user model directly; distribute remainder to others proportionally
        # from their last-training shares (avoids denominator-inflation dip).
        child_list = list(children_ms.keys())
        last_child_share = {}
        for child, share_map in children_ms.items():
            vals = [float(share_map.get((y, m), 0)) for y, m in historical_months]
            last_child_share[child] = vals[-1] if vals else 0.0

        norm_shares = {}  # final per-period within-parent share for each child

        if selected_child is not None and selected_child in children_ms and factors is not None:
            sel_share_map = children_ms[selected_child]
            sel_train = [float(sel_share_map.get((y, m), 0)) for y, m in historical_months]
            sel_child_fc = _forecast_share_by_factors(sel_train, forecast_count, factors)
            norm_shares[selected_child] = [min(100.0, max(0.0, v)) for v in sel_child_fc]

            other_children = [c for c in child_list if c != selected_child]
            other_base_sum = sum(last_child_share.get(c, 0.0) for c in other_children)
            for c in other_children:
                norm_shares[c] = []
            for i in range(forecast_count):
                remainder = max(0.0, 100.0 - norm_shares[selected_child][i])
                for c in other_children:
                    base_s = last_child_share.get(c, 0.0)
                    norm_shares[c].append(
                        remainder * base_s / other_base_sum if other_base_sum > 0 else 0.0
                    )
        else:
            # No selection: apply user's model to every child then normalize within parent
            raw_shares = {}
            for child, share_map in children_ms.items():
                share_train = [float(share_map.get((y, m), 0)) for y, m in historical_months]
                raw_shares[child] = (
                    _forecast_share_by_factors(share_train, forecast_count, factors)
                    if factors is not None
                    else _simple_moving_average_forecast(share_train, forecast_count, window=6)
                )
            for i in range(forecast_count):
                total = sum(raw_shares[c][i] for c in raw_shares)
                for c in raw_shares:
                    norm_shares.setdefault(c, []).append(
                        raw_shares[c][i] / total * 100.0 if total > 0 else 0.0
                    )

        # Parent volume history = sum of children's actual volumes
        parent_vol_by_period = {}
        for child_mv in children_mv.values():
            for k, v in child_mv.items():
                parent_vol_by_period[k] = parent_vol_by_period.get(k, 0.0) + v
        parent_vol_train = [float(parent_vol_by_period.get((y, m), 0)) for y, m in historical_months]

        # Parent volume forecast placeholder: simple MA of parent history
        # (IPF will correct this to match Tab3/Tab2 row/column targets)
        if parent_vol_train and not all(v == 0 for v in parent_vol_train):
            parent_vol_fc = _simple_moving_average_forecast(parent_vol_train, forecast_count, window=3)
        else:
            parent_vol_fc = [0.0] * forecast_count

        # Child volume = normalized share% / 100 * parent volume forecast
        child_trains, child_forecasts, child_items = [], [], []
        for child in children_ms:
            vol_map = children_mv.get(child, {})
            child_train = [float(vol_map.get((y, m), 0)) for y, m in historical_months]
            fc_share = norm_shares.get(child, [0.0] * forecast_count)
            child_fc = [fc_share[i] / 100.0 * parent_vol_fc[i] for i in range(forecast_count)]
            child_trains.append(child_train)
            child_forecasts.append(child_fc)
            child_items.append((child, child_train, child_fc))

        n_tr = max((len(t) for t in child_trains), default=0)
        n_fc = max((len(f) for f in child_forecasts), default=0)
        parent_train_agg = [sum(t[i] if i < len(t) else 0 for t in child_trains) for i in range(n_tr)]
        parent_fc_agg    = [sum(f[i] if i < len(f) else 0 for f in child_forecasts) for i in range(n_fc)]

        chart_series.append(ChartSeries(label=parent, train_values=parent_train_agg,
                                         forecast_values=parent_fc_agg))
        child_rows = []
        for child, child_train, child_fc in child_items:
            chart_series.append(ChartSeries(label=f"{parent} - {child}",
                                             train_values=child_train, forecast_values=child_fc))
            child_rows.append(ChildRow(label=child, values=child_train + child_fc))

        table_rows.append(HierarchicalRow(
            hierarchy=parent,
            total=parent_train_agg + parent_fc_agg,
            children=child_rows,
        ))

    return HierarchicalTabData(
        chart=TabChart(series=chart_series),
        table=HierarchicalTabTable(headers=month_labels, rows=table_rows),
    )


def _build_response_factors(factors: LiverFactors, trajectory_start: str = "") -> dict:
    """Return full oncology-format factors dict for the API response."""
    def _growth(model_params):
        d = {
            "total_growth":     int(round(model_params.total_growth)),
            "duration":         model_params.duration,
            "trajectory_start": trajectory_start,
        }
        if hasattr(model_params, "k_value") and model_params.k_value is not None:
            d["k_value"] = model_params.k_value
        return d

    ma_params = factors.moving_average or MovingAverageParams()
    return {
        "active_model":       factors.active_model,
        "multiplier":         factors.multiplier,
        "multiplier_horizon": factors.multiplier_horizon,
        "ets": {
            "alpha": factors.ets.alpha,
            "beta":  factors.ets.beta,
            "gamma": factors.ets.gamma,
        },
        "linear":          _growth(factors.linear),
        "exponential":     _growth(factors.exponential),
        "logarithmic":     _growth(factors.logarithmic),
        "scurve":          _growth(factors.scurve),
        "moving_average":  {"window": ma_params.window},
    }


def _rows_to_series(rows, label_col_index, value_col_index):
    series = {}
    for row in rows:
        year, month = row[0], row[1]
        label = row[label_col_index]
        value = float(row[value_col_index]) if row[value_col_index] is not None else 0.0
        series.setdefault(label, {})[(year, month)] = value
    return series


def _fmt_flat(tab, month_labels, forecast_start_index, to_int=False):
    def _v(vals):
        return [int(v) for v in vals] if to_int else list(vals)

    return {
        "chart": {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "series": [
                {"label": s.label, "history": _v(s.train_values), "forecast": _v(s.forecast_values)}
                for s in tab.chart.series
            ],
        },
        "table": {
            "type": "flat",
            "rows": [{"label": r.hierarchy, "values": _v(r.values)} for r in tab.table.rows],
        },
    }


def _fmt_hier(tab, month_labels, forecast_start_index, to_int=False, chart_parent_filter=None):
    def _v(vals):
        return [int(v) for v in vals] if to_int else list(vals)

    if chart_parent_filter:
        prefix = f"{chart_parent_filter} - "
        chart_series = [s for s in tab.chart.series if s.label.startswith(prefix)]
    else:
        chart_series = tab.chart.series

    return {
        "chart": {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "series": [
                {"label": s.label, "history": _v(s.train_values), "forecast": _v(s.forecast_values)}
                for s in chart_series
            ],
        },
        "table": {
            "type": "hierarchy",
            "rows": [
                {
                    "label":    r.hierarchy,
                    "values":   _v(r.total),
                    "children": [{"label": c.label, "values": _v(c.values)} for c in r.children],
                }
                for r in tab.table.rows
            ],
        },
    }


def _scale_flat_to_tmv(tab_data: TabData, tmv_fc: list, fsi: int) -> None:
    """In-place: scale non-Total forecast values so they sum to tmv_fc per period."""
    n_fc = len(tmv_fc)
    if not n_fc:
        return

    # Chart series
    active_s = [s for s in tab_data.chart.series if s.label.lower() != "total"]
    s_sums   = [sum(s.forecast_values[i] if i < len(s.forecast_values) else 0.0 for s in active_s) for i in range(n_fc)]
    for s in active_s:
        s.forecast_values = [
            s.forecast_values[i] * tmv_fc[i] / s_sums[i] if i < len(s.forecast_values) and s_sums[i] else 0.0
            for i in range(n_fc)
        ]

    # Table rows
    non_tot = [r for r in tab_data.table.rows if r.hierarchy.lower() != "total"]
    tot_row = next((r for r in tab_data.table.rows if r.hierarchy.lower() == "total"), None)
    r_sums  = [sum(r.values[fsi+i] if fsi+i < len(r.values) else 0.0 for r in non_tot) for i in range(n_fc)]
    for r in non_tot:
        r.values = list(r.values[:fsi]) + [
            r.values[fsi+i] * tmv_fc[i] / r_sums[i] if fsi+i < len(r.values) and r_sums[i] else 0.0
            for i in range(n_fc)
        ]
    if tot_row:
        n = fsi + n_fc
        tot = [0.0] * n
        for r in non_tot:
            for i, v in enumerate(r.values[:n]):
                tot[i] += v
        tot_row.values = tot


def _ipf_hier_rows(hier_rows, row_targets, col_targets, max_iter=8):
    """Iterative Proportional Fitting on hierarchical rows.

    Scales cell values so that:
      - each parent's sum of children == row_targets[parent_label]  (row constraint)
      - each child's sum across parents == col_targets[child_label]  (col constraint)

    Returns a new list of hier_rows with integer-rounded values.
    """
    parents = [r.get("label", "") for r in hier_rows]
    child_set = list({c.get("label", "") for r in hier_rows for c in r.get("children", [])})
    n = max((len(r.get("values", [])) for r in hier_rows), default=0)
    if not n or not parents or not child_set:
        return hier_rows

    mat = {}
    for r in hier_rows:
        p = r.get("label", "")
        ch_by_label = {ch.get("label", ""): ch for ch in r.get("children", [])}
        mat[p] = {}
        for c in child_set:
            vals = ch_by_label[c].get("values", []) if c in ch_by_label else []
            mat[p][c] = [float(v) for v in vals] + [0.0] * (n - len(vals))

    for _ in range(max_iter):
        for p in parents:
            row_sum = [sum(mat[p][c][i] for c in child_set) for i in range(n)]
            tgt = row_targets.get(p, row_sum)
            for c in child_set:
                mat[p][c] = [mat[p][c][i] * tgt[i] / row_sum[i] if row_sum[i] else 0.0 for i in range(n)]
        for c in child_set:
            col_sum = [sum(mat[p][c][i] for p in parents) for i in range(n)]
            tgt = col_targets.get(c, col_sum)
            for p in parents:
                mat[p][c] = [mat[p][c][i] * tgt[i] / col_sum[i] if col_sum[i] else 0.0 for i in range(n)]

    new_rows = []
    for r in hier_rows:
        p = r.get("label", "")
        new_ch = [
            {"label": ch.get("label", ""), "values": [int(round(mat[p][ch.get("label","")][i])) for i in range(n)]}
            for ch in r.get("children", [])
        ]
        ptotal = [sum(ch["values"][i] for ch in new_ch) for i in range(n)]
        new_rows.append({"label": p, "values": ptotal, "children": new_ch})
    return new_rows


def _transpose_hier_rows(src_rows, dst_rows):
    """Build dst (product×payer) by transposing src (payer×product).

    dst_rows provides the parent/child structure; values come from src transposed.
    """
    lookup = {}
    for sp in src_rows:
        plbl = sp.get("label", "")
        for sc in sp.get("children", []):
            lookup.setdefault(sc.get("label", ""), {})[plbl] = [int(round(float(v))) for v in sc.get("values", [])]

    new_rows = []
    for dp in dst_rows:
        dp_lbl = dp.get("label", "")
        new_ch = []
        for dc in dp.get("children", []):
            dc_lbl = dc.get("label", "")
            fallback = [int(round(float(v))) for v in dc.get("values", [])]
            new_ch.append({"label": dc_lbl, "values": lookup.get(dp_lbl, {}).get(dc_lbl, fallback)})
        n_c = max((len(c["values"]) for c in new_ch), default=0)
        new_rows.append({
            "label": dp_lbl,
            "values": [sum(c["values"][i] for c in new_ch) for i in range(n_c)],
            "children": new_ch,
        })
    return new_rows


def _sync_hier_mv_chart(tab_mv, fsi, chart_parent_filter=None):
    """Rebuild market_volume chart series from table rows after an IPF update."""
    rows = tab_mv.get("table", {}).get("rows", [])
    series = []
    for parent in rows:
        plbl = parent.get("label", "")
        if chart_parent_filter and plbl != chart_parent_filter:
            continue
        for child in parent.get("children", []):
            clbl = child.get("label", "")
            cvals = [int(round(float(v))) for v in child.get("values", [])]
            series.append({"label": f"{plbl} - {clbl}", "history": cvals[:fsi], "forecast": cvals[fsi:]})
    tab_mv.setdefault("chart", {})["series"] = series


def _build_all_tabs_both_metrics(cur, ta, from_year, from_month,
                                  train_end_year, train_end_month, forecast_periods, factors,
                                  granularity="monthly",
                                  sel_payer=None, sel_product=None,
                                  force_tab1_ets=True,
                                  scenario_name="Base",
                                  auto_model="moving_average"):
    """
    Build all 5 tabs for BOTH market_volume and market_share.
    Returns (month_labels, forecast_start_index, market_analysis_dict, tab1_ets).
    market_analysis_dict keys: total_market_volume, product_distribution,
      market_distribution, payer_product, product_payer.
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

    # TMV forecast values used to scale Tabs 2-5.
    # Always use Tab1's ETS forecast as the TMV multiplier for Tabs 2-5.
    # share-based flow: volume = share% × ETS_TMV; _recompute_all_market_shares then divides
    # by the same ETS_TMV, so recomputed share == forecasted share exactly. Using a different
    # TMV here (e.g. rolling MA) would cause a ratio mismatch and distort displayed shares.
    _tmv_fc = tab1_mv_data.chart.series[0].forecast_values if tab1_mv_data.chart.series else []

    def bflat_mv(rows_mv, rows_ms, label, to_int=False):
        tab_data = _build_tab_data_from_shares(
            share_series_dict=_rows_to_series(rows_ms, 2, 3),
            vol_series_dict=_rows_to_series(rows_mv, 2, 3),
            month_range=month_range,
            month_labels=month_labels,
            forecast_start_index=fsi,
            factors=factors,
            tmv_fc=_tmv_fc,
            selected_label=label,
            add_total=True,
        )
        return _fmt_flat(tab_data, month_labels, fsi, to_int=to_int)

    def bflat_ms(rows, label):
        return _fmt_flat(
            _build_tab_data(_rows_to_series(rows, 2, 3), month_range, month_labels, fsi, factors,
                            selected_label=label, auto_model=auto_model, add_total=True),
            month_labels, fsi,
        )

    def bhier_mv(rows_mv, rows_ms, parent_lbl, child_lbl, to_int=False):
        hier_data = _build_hierarchical_tab_data_from_shares(
            rows_ms=rows_ms,
            rows_mv=rows_mv,
            month_range=month_range,
            month_labels=month_labels,
            forecast_start_index=fsi,
            factors=factors,
            selected_child=child_lbl,
        )
        return _fmt_hier(hier_data, month_labels, fsi, to_int=to_int, chart_parent_filter=parent_lbl)

    def bhier_ms(rows, parent_lbl, child_lbl):
        return _fmt_hier(
            _build_hierarchical_tab_data(rows, month_range, month_labels, fsi, factors,
                                         selected_parent=parent_lbl or "",
                                         selected_child=child_lbl or "",
                                         auto_model=auto_model),
            month_labels, fsi, chart_parent_filter=parent_lbl,
        )

    market_analysis = {
        "total_market_volume": {
            "market_volume": _fmt_flat(tab1_mv_data, month_labels, fsi, to_int=True),
            "market_share":  tab1_ms,
        },
        "product_distribution": {
            "market_volume": bflat_mv(pd_mv,   pd_ms,   tab2_label, to_int=True),
            "market_share":  bflat_ms(pd_ms,   tab2_label),
        },
        "market_distribution": {
            "market_volume": bflat_mv(pyd_mv,  pyd_ms,  tab3_label, to_int=True),
            "market_share":  bflat_ms(pyd_ms,  tab3_label),
        },
        "payer_product": {
            "market_volume": bhier_mv(pwp_mv,  pwp_ms,  tab3_label, tab2_label, to_int=True),
            "market_share":  bhier_ms(pwp_ms,  tab3_label, tab2_label),
        },
        "product_payer": {
            "market_volume": bhier_mv(pwpy_mv, pwpy_ms, tab2_label, tab3_label, to_int=True),
            "market_share":  bhier_ms(pwpy_ms, tab2_label, tab3_label),
        },
    }

    # Align Tab4 (payer_product) and Tab5 (product_payer) so their parent totals match
    # Tab2 (product_distribution) and Tab3 (market_distribution) respectively.
    # Tab2/Tab3 forecast from share → volume; IPF corrects Tab4/Tab5 absolute levels.
    _tab2_mv_rows = market_analysis["product_distribution"]["market_volume"]["table"]["rows"]
    _tab3_mv_rows = market_analysis["market_distribution"]["market_volume"]["table"]["rows"]
    _tab4_mv = market_analysis["payer_product"]["market_volume"]
    _tab5_mv = market_analysis["product_payer"]["market_volume"]
    _col_tgts = {
        r["label"]: [float(v) for v in r["values"]]
        for r in _tab2_mv_rows if r.get("label", "").lower() != "total"
    }
    _row_tgts = {
        r["label"]: [float(v) for v in r["values"]]
        for r in _tab3_mv_rows if r.get("label", "").lower() != "total"
    }
    if _tab4_mv.get("table", {}).get("rows") and _col_tgts and _row_tgts:
        _new4 = _ipf_hier_rows(_tab4_mv["table"]["rows"], _row_tgts, _col_tgts)
        _tab4_mv["table"]["rows"] = _new4
        _sync_hier_mv_chart(_tab4_mv, fsi, chart_parent_filter=tab3_label)
        if _tab5_mv.get("table", {}).get("rows"):
            _tab5_mv["table"]["rows"] = _transpose_hier_rows(_new4, _tab5_mv["table"]["rows"])
            _sync_hier_mv_chart(_tab5_mv, fsi, chart_parent_filter=tab2_label)

    # Recompute market_share from scaled market_volume so all tabs are consistent
    market_analysis = _recompute_all_market_shares(market_analysis)

    return month_labels, forecast_start_index, market_analysis, tab1_ets


def _aggregate_monthly_to_yearly(ma_monthly: dict) -> dict:
    """
    Derive yearly market_analysis from monthly by summing each month's values
    into its calendar year. Parent values are always recomputed from children
    (not from stored parent values) to avoid int() truncation drift.
    After aggregation, flat and hierarchical market_volume tabs are re-scaled
    to match the yearly TMV so all tabs are consistent.
    market_share is recomputed from the final scaled market_volume.
    """
    def _group_sum(month_labels, values):
        year_sums = {}
        for i, m in enumerate(month_labels):
            y = m[:4]
            year_sums[y] = year_sums.get(y, 0.0) + (float(values[i]) if i < len(values) else 0.0)
        years = list(dict.fromkeys(m[:4] for m in month_labels))
        return years, [year_sums.get(y, 0.0) for y in years]

    def _vsum(series_list, key, idx):
        return sum(s.get(key, [])[idx] if idx < len(s.get(key, [])) else 0.0 for s in series_list)

    ma_yearly = {}
    for tab_key, metrics in ma_monthly.items():
        ma_yearly[tab_key] = {}
        for metric, data in metrics.items():
            chart  = data.get("chart", {})
            table  = data.get("table", {})
            months = chart.get("months", [])
            fsi    = chart.get("forecast_start_index", 0)

            hist_months = months[:fsi]
            fc_months   = months[fsi:]

            hist_years, _ = _group_sum(hist_months, [])
            fc_years,   _ = _group_sum(fc_months,   [])
            yearly_months  = hist_years + fc_years
            yearly_fsi     = len(hist_years)
            n_yrs          = len(yearly_months)

            table_type = table.get("type", "flat")

            if table_type == "flat":
                # Aggregate non-Total rows; recompute Total from them
                non_tot, tot_row_out = [], None
                for r in table.get("rows", []):
                    vals = r.get("values", [])
                    _, h = _group_sum(hist_months, vals[:fsi])
                    _, f = _group_sum(fc_months,   vals[fsi:])
                    nr = {"label": r["label"], "values": h + f}
                    if r["label"].lower() == "total":
                        tot_row_out = nr
                    else:
                        non_tot.append(nr)
                if tot_row_out:
                    tot_row_out["values"] = [
                        sum(r["values"][i] for r in non_tot if i < len(r["values"]))
                        for i in range(n_yrs)
                    ]
                new_rows  = ([tot_row_out] if tot_row_out else []) + non_tot
                new_table = {"type": "flat", "rows": new_rows}

                # Chart: aggregate each series; Total series recomputed from non-Total
                non_tot_ser, tot_ser_out = [], None
                for s in chart.get("series", []):
                    _, h = _group_sum(hist_months, s.get("history",  []))
                    _, f = _group_sum(fc_months,   s.get("forecast", []))
                    ns = {"label": s["label"], "history": h, "forecast": f}
                    if s["label"].lower() == "total":
                        tot_ser_out = ns
                    else:
                        non_tot_ser.append(ns)
                if tot_ser_out:
                    tot_ser_out["history"]  = [_vsum(non_tot_ser, "history",  i) for i in range(yearly_fsi)]
                    tot_ser_out["forecast"] = [_vsum(non_tot_ser, "forecast", i) for i in range(len(fc_years))]
                new_series = ([tot_ser_out] if tot_ser_out else []) + non_tot_ser

            else:  # hierarchy
                new_rows   = []
                new_series = []
                plabels    = set()

                for r in table.get("rows", []):
                    plabels.add(r["label"])
                    new_children = []
                    for c in r.get("children", []):
                        cv = c.get("values", [])
                        _, ch = _group_sum(hist_months, cv[:fsi])
                        _, cf = _group_sum(fc_months,   cv[fsi:])
                        new_children.append({"label": c["label"], "values": ch + cf})
                    # Parent = sum of children (not stored parent — avoids int() drift)
                    parent_vals = [
                        sum(c["values"][i] for c in new_children if i < len(c["values"]))
                        for i in range(n_yrs)
                    ]
                    new_rows.append({"label": r["label"], "values": parent_vals, "children": new_children})
                new_table = {"type": "hierarchy", "rows": new_rows}

                # Chart: aggregate child series; parent series = sum of their children
                child_ser_map = {}  # parent_label → [child series]
                for s in chart.get("series", []):
                    if s["label"] in plabels:
                        continue  # skip old parent series; we'll recompute
                    _, h = _group_sum(hist_months, s.get("history",  []))
                    _, f = _group_sum(fc_months,   s.get("forecast", []))
                    ns = {"label": s["label"], "history": h, "forecast": f}
                    # Determine parent by matching "Parent - Child" label format
                    parent = next((pl for pl in plabels if s["label"].startswith(f"{pl} - ")), None)
                    if parent:
                        child_ser_map.setdefault(parent, []).append(ns)
                    new_series.append(ns)

                for pl in plabels:
                    ch_ser = child_ser_map.get(pl, [])
                    n_h = max((len(s.get("history",  [])) for s in ch_ser), default=0)
                    n_f = max((len(s.get("forecast", [])) for s in ch_ser), default=0)
                    new_series.insert(0, {
                        "label":    pl,
                        "history":  [_vsum(ch_ser, "history",  i) for i in range(n_h)],
                        "forecast": [_vsum(ch_ser, "forecast", i) for i in range(n_f)],
                    })

            ma_yearly[tab_key][metric] = {
                "chart": {"months": yearly_months, "forecast_start_index": yearly_fsi, "series": new_series},
                "table": new_table,
            }

    # Re-scale flat and hierarchical market_volume tabs to match yearly TMV
    # (removes residual int() truncation drift accumulated from 12-month summation)
    tmv_chart = (ma_yearly.get("total_market_volume", {})
                          .get("market_volume", {})
                          .get("chart", {}))
    yearly_fsi_tmv = tmv_chart.get("forecast_start_index", 0)
    tmv_ser        = tmv_chart.get("series", [{}])[0] if tmv_chart.get("series") else {}
    tmv_fc_yearly  = tmv_ser.get("forecast", [])

    for tab_key in ("product_distribution", "market_distribution"):
        mv = ma_yearly.get(tab_key, {}).get("market_volume", {})
        if mv and tmv_fc_yearly:
            chart  = mv["chart"]
            table  = mv["table"]
            non_s  = [s for s in chart.get("series", []) if s["label"].lower() != "total"]
            s_sums = [sum(s.get("forecast", [])[i] if i < len(s.get("forecast", [])) else 0.0 for s in non_s) for i in range(len(tmv_fc_yearly))]
            for s in non_s:
                s["forecast"] = [s["forecast"][i] * tmv_fc_yearly[i] / s_sums[i] if i < len(s.get("forecast", [])) and s_sums[i] else 0.0 for i in range(len(tmv_fc_yearly))]
            tot_s = next((s for s in chart.get("series", []) if s["label"].lower() == "total"), None)
            if tot_s:
                tot_s["forecast"] = tmv_fc_yearly[:]
            non_r  = [r for r in table.get("rows", []) if r["label"].lower() != "total"]
            r_sums = [sum(r["values"][yearly_fsi_tmv+i] if yearly_fsi_tmv+i < len(r["values"]) else 0.0 for r in non_r) for i in range(len(tmv_fc_yearly))]
            for r in non_r:
                fc = [r["values"][yearly_fsi_tmv+i] * tmv_fc_yearly[i] / r_sums[i] if yearly_fsi_tmv+i < len(r["values"]) and r_sums[i] else 0.0 for i in range(len(tmv_fc_yearly))]
                r["values"] = list(r["values"][:yearly_fsi_tmv]) + fc
            tot_r = next((r for r in table.get("rows", []) if r["label"].lower() == "total"), None)
            if tot_r:
                tot_r["values"] = list(tot_r["values"][:yearly_fsi_tmv]) + tmv_fc_yearly[:]

    for tab_key in ("payer_product", "product_payer"):
        mv = ma_yearly.get(tab_key, {}).get("market_volume", {})
        if mv and tmv_fc_yearly:
            chart   = mv["chart"]
            table   = mv["table"]
            plabels = {r["label"] for r in table.get("rows", [])}
            ch_ser  = [s for s in chart.get("series", []) if s["label"] not in plabels]
            cs_sums = [sum(s.get("forecast", [])[i] if i < len(s.get("forecast", [])) else 0.0 for s in ch_ser) for i in range(len(tmv_fc_yearly))]
            for s in ch_ser:
                s["forecast"] = [s["forecast"][i] * tmv_fc_yearly[i] / cs_sums[i] if i < len(s.get("forecast", [])) and cs_sums[i] else 0.0 for i in range(len(tmv_fc_yearly))]
            # Recompute parent chart series from scaled children
            for ps in chart.get("series", []):
                if ps["label"] not in plabels:
                    continue
                ch = [s for s in ch_ser if s["label"].startswith(f"{ps['label']} - ")]
                if ch:
                    ps["forecast"] = [_vsum(ch, "forecast", i) for i in range(len(tmv_fc_yearly))]
            # Scale table children
            all_ch  = [c for r in table.get("rows", []) for c in r.get("children", [])]
            ct_sums = [sum(c["values"][yearly_fsi_tmv+i] if yearly_fsi_tmv+i < len(c["values"]) else 0.0 for c in all_ch) for i in range(len(tmv_fc_yearly))]
            for c in all_ch:
                fc = [c["values"][yearly_fsi_tmv+i] * tmv_fc_yearly[i] / ct_sums[i] if yearly_fsi_tmv+i < len(c["values"]) and ct_sums[i] else 0.0 for i in range(len(tmv_fc_yearly))]
                c["values"] = list(c["values"][:yearly_fsi_tmv]) + fc
            # Recompute parent table values from scaled children
            for r in table.get("rows", []):
                n = yearly_fsi_tmv + len(tmv_fc_yearly)
                r["values"] = [sum(c["values"][i] for c in r.get("children", []) if i < len(c["values"])) for i in range(n)]

    # Round all market_volume forecast values to int after scaling
    for tab_key, metrics in ma_yearly.items():
        mv = metrics.get("market_volume", {})
        if not mv:
            continue
        yr_fsi = mv.get("chart", {}).get("forecast_start_index", 0)
        for s in mv.get("chart", {}).get("series", []):
            s["forecast"] = [int(round(v)) for v in s.get("forecast", [])]
        for r in mv.get("table", {}).get("rows", []):
            r["values"] = list(r["values"][:yr_fsi]) + [int(round(v)) for v in r["values"][yr_fsi:]]
            for c in r.get("children", []):
                c["values"] = list(c["values"][:yr_fsi]) + [int(round(v)) for v in c["values"][yr_fsi:]]

    return _recompute_all_market_shares(ma_yearly)


def _build_market_analysis_both_granularities(
    cur, ta, from_year, from_month,
    train_end_year, train_end_month, forecast_periods_months, factors,
    sel_payer=None, sel_product=None,
    force_tab1_ets=True, scenario_name="Base",
    auto_model="moving_average",
):
    """
    Builds market_analysis for both monthly and yearly granularities.
    Yearly is derived by aggregating monthly values per calendar year so that
    sum(monthly forecast for a year) == yearly forecast value exactly.
    """
    _, _, ma_monthly, tab1_ets = _build_all_tabs_both_metrics(
        cur, ta, from_year, from_month,
        train_end_year, train_end_month, forecast_periods_months, factors,
        granularity="monthly",
        sel_payer=sel_payer, sel_product=sel_product,
        force_tab1_ets=force_tab1_ets, scenario_name=scenario_name,
        auto_model=auto_model,
    )
    ma_yearly = _aggregate_monthly_to_yearly(ma_monthly)

    merged = {}
    for tab_key, metrics in ma_monthly.items():
        merged[tab_key] = {}
        for metric, monthly_data in metrics.items():
            merged[tab_key][metric] = {
                "monthly": monthly_data,
                "yearly":  ma_yearly.get(tab_key, {}).get(metric, {}),
            }

    return merged, tab1_ets


def _split_by_granularity(ma_nested: dict):
    """Split {tab: {metric: {monthly: ..., yearly: ...}}} into two flat dicts."""
    monthly, yearly = {}, {}
    for tab, metrics in ma_nested.items():
        monthly[tab], yearly[tab] = {}, {}
        for metric, grans in metrics.items():
            monthly[tab][metric] = grans.get("monthly", {})
            yearly[tab][metric]  = grans.get("yearly", {})
    return monthly, yearly


def _merge_granularities(ma_monthly: dict, ma_yearly: dict) -> dict:
    """Merge two flat dicts into {tab: {metric: {monthly: ..., yearly: ...}}}."""
    merged = {}
    for tab in ma_monthly:
        merged[tab] = {}
        for metric in ma_monthly[tab]:
            merged[tab][metric] = {
                "monthly": ma_monthly[tab][metric],
                "yearly":  ma_yearly.get(tab, {}).get(metric, {}),
            }
    return merged


def _recompute_all_market_shares_nested(market_analysis: dict) -> dict:
    """Wrapper of _recompute_all_market_shares for the nested monthly/yearly format."""
    ma_monthly, ma_yearly = _split_by_granularity(market_analysis)
    ma_monthly = _recompute_all_market_shares(ma_monthly)
    ma_yearly  = _recompute_all_market_shares(ma_yearly)
    ma_monthly, ma_yearly = _split_by_granularity(market_analysis)
    return _merge_granularities(ma_monthly, ma_yearly)


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
        saved_factors_raw     = None

        # Load factors (and saved market_analysis) for the active scenario
        if active_scenario != "Base":
            cur.execute(
                "SELECT factors, chart_data FROM raw_liver.liver_scenarios WHERE scenario_name = %s",
                (active_scenario,),
            )
            row = cur.fetchone()
            if row:
                saved_factors_raw = row[0] if isinstance(row[0], dict) else {}
                try:
                    factors = LiverFactors(**saved_factors_raw)
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
            market_analysis = _recompute_all_market_shares_nested(saved_market_analysis)
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
            market_analysis, tab1_ets = _build_market_analysis_both_granularities(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, factors,
                sel_payer=_first(payload.payer), sel_product=_first(payload.brand),
                scenario_name=payload.scenario,
            )
            market_analysis = _recompute_all_market_shares_nested(market_analysis)

        _traj_start = _add_months(date_type(train_end_year, train_end_month, 1), 1).isoformat()
        if active_scenario != "Base" and saved_market_analysis and saved_factors_raw:
            # Use the factors exactly as saved — preserves active_model, slider values, etc.
            response_factors = dict(saved_factors_raw)
        else:
            # Base or no saved data: return computed ETS factors
            response_factors = _build_response_factors(factors, _traj_start)
            response_factors["active_model"] = "ets"
            response_factors["ets"] = {"alpha": tab1_ets.alpha, "beta": tab1_ets.beta, "gamma": tab1_ets.gamma}

        train_end_dt = date_type(train_end_year, train_end_month, 1)
        end_date     = _add_months(train_end_dt, forecast_periods).isoformat()

        # ── Build TMV stubs for inactive scenarios ────────────────────────────
        # Load stored chart_data for all saved scenarios — use that directly
        # instead of rebuilding from scratch (rebuilding can silently fall back
        # to ETS if the saved factors dict has unknown keys).
        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        all_saved_cd = {r[0]: (r[1] or {}) for r in cur.fetchall()}

        if active_scenario == "Base":
            base_tmv = market_analysis.get("total_market_volume", {})
        else:
            base_factors = _estimate_default_factors(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            _base_ma, _ = _build_market_analysis_both_granularities(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, base_factors,
                scenario_name="Base",
            )
            base_tmv = _base_ma.get("total_market_volume", {})

        def _tmv_table_only(tmv: dict) -> dict:
            """Keep only the table rows from TMV (both granularities), drop chart data."""
            result = {}
            for metric in ("market_volume", "market_share"):
                if metric not in tmv:
                    continue
                result[metric] = {}
                for gran in ("monthly", "yearly"):
                    if gran in tmv[metric] and "table" in tmv[metric][gran]:
                        result[metric][gran] = {"table": tmv[metric][gran]["table"]}
            return result

        def _inactive_stub(sc_name):
            if sc_name == "Base":
                tmv = base_tmv
            else:
                # Load directly from stored chart_data — never rebuild from factors
                cd  = all_saved_cd.get(sc_name, {})
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

    ma_window = (f.moving_average.window if f.moving_average else 6)

    return LiverFactors(
        active_model       = model_type,
        multiplier         = f.multiplier,
        multiplier_horizon = f.multiplier_horizon,
        ets                = EtsParams(alpha=ets_p.alpha, beta=ets_p.beta, gamma=ets_p.gamma),
        linear             = LinearParams(total_growth=lin_tg, duration=lin_dur, trajectory_start=lin_traj),
        exponential        = ExponentialParams(k_value=exp_k, total_growth=exp_tg, duration=exp_dur, trajectory_start=exp_traj),
        logarithmic        = LogarithmicParams(k_value=log_k, total_growth=log_tg, duration=log_dur, trajectory_start=log_traj),
        scurve             = SCurveParams(k_value=sc_k,  total_growth=sc_tg,  duration=sc_dur,  trajectory_start=sc_traj),
        moving_average     = MovingAverageParams(window=ma_window),
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
        forecast_periods = _resolve_forecast_periods(
            sf.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
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

        market_analysis, tab1_ets = _build_market_analysis_both_granularities(
            cur, payload.ta_name, from_year, from_month,
            train_end_year, train_end_month, forecast_periods, factors,
            sel_payer=market, sel_product=product,
            force_tab1_ets=False,
            scenario_name=payload.scenario_name,
            auto_model=model_type,
        )
        market_analysis = _recompute_all_market_shares_nested(market_analysis)

        _traj_start_rc = _add_months(date_type(train_end_year, train_end_month, 1), 1).isoformat()
        response_factors = _build_response_factors(factors, _traj_start_rc)
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

        # ── Build TMV stubs for inactive scenarios ────────────────────────────
        # Load stored chart_data from DB — never rebuild inactive scenarios from
        # factors, which would silently produce Base values on any LiverFactors
        # construction failure.
        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        all_saved_cd_rc = {r[0]: (r[1] or {}) for r in cur.fetchall()}

        if active_scenario == "Base":
            base_tmv_rc = market_analysis.get("total_market_volume", {})
        else:
            _base_f = _estimate_default_factors(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            _base_ma_rc, _ = _build_market_analysis_both_granularities(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, _base_f,
                scenario_name="Base",
            )
            base_tmv_rc = _base_ma_rc.get("total_market_volume", {})

        def _tmv_table_only_rc(tmv: dict) -> dict:
            result = {}
            for metric in ("market_volume", "market_share"):
                if metric not in tmv:
                    continue
                result[metric] = {}
                for gran in ("monthly", "yearly"):
                    if gran in tmv[metric] and "table" in tmv[metric][gran]:
                        result[metric][gran] = {"table": tmv[metric][gran]["table"]}
            return result

        def _inactive_stub_rc(sc_name):
            if sc_name == "Base":
                tmv = base_tmv_rc
            else:
                cd  = all_saved_cd_rc.get(sc_name, {})
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
    - payer_product / product_payer (hierarchical) → child / parent_total * 100
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

        # Use column sum of non-Total rows as denominator so shares always sum to 100%
        non_total_rows = [
            r for r in mv_data.get("table", {}).get("rows", [])
            if r.get("label", "").lower() != "total"
        ]
        tab_n = max((len(r.get("values", [])) for r in non_total_rows), default=0)
        col_sums = [
            sum(float(r["values"][i]) for r in non_total_rows if i < len(r.get("values", [])))
            for i in range(tab_n)
        ]

        for r in mv_data.get("table", {}).get("rows", []):
            lbl = r.get("label", "")
            if lbl.lower() == "total":
                if lbl in ms_row_map:
                    ms_row_map[lbl]["values"] = [100.0] * tab_n
                continue
            mv_vals = r.get("values", [])
            ms_vals = [
                round(float(mv_vals[i]) / col_sums[i] * 100, 4)
                if i < len(mv_vals) and i < tab_n and col_sums[i] != 0
                else 0.0
                for i in range(tab_n)
            ]
            if lbl in ms_row_map:
                ms_row_map[lbl]["values"] = ms_vals
            if lbl in ms_ser_map:
                ms_ser_map[lbl]["history"]  = ms_vals[:fsi]
                ms_ser_map[lbl]["forecast"] = ms_vals[fsi:]

    # ── Hierarchical cross-tabs (4, 5): child / sum(children) * 100 ─────────
    for tab in ("payer_product", "product_payer"):
        if tab not in market_analysis:
            continue
        mv_data = market_analysis[tab].get("market_volume", {})
        ms_data = market_analysis[tab].get("market_share", {})
        if not ms_data:
            continue

        ms_hier_map  = {r.get("label", ""): r for r in ms_data.get("table", {}).get("rows", [])}
        ms_chart_map = {s.get("label", ""): s for s in ms_data.get("chart", {}).get("series", [])}

        for mv_row in mv_data.get("table", {}).get("rows", []):
            parent_lbl = mv_row.get("label", "")
            children   = mv_row.get("children", [])
            ms_parent  = ms_hier_map.get(parent_lbl, {})

            if not children:
                continue

            # Derive length and per-period column sum directly from children
            # to avoid rounding drift when parent_vals used to_int=True
            hier_n = max((len(c.get("values", [])) for c in children), default=0)
            child_col_sums = [
                sum(float(c["values"][i]) for c in children if i < len(c.get("values", [])))
                for i in range(hier_n)
            ]

            if ms_parent:
                ms_parent["values"] = [100.0] * hier_n

            for child in children:
                child_lbl  = child.get("label", "")
                child_vals = child.get("values", [])
                child_ms   = [
                    round(float(child_vals[i]) / child_col_sums[i] * 100, 4)
                    if i < len(child_vals) and i < hier_n and child_col_sums[i] != 0
                    else 0.0
                    for i in range(hier_n)
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



def _persist_and_respond(payload: LiverSaveScenarioRequest, allow_overwrite: bool) -> dict:
    """
    Core for save/update: persists market_analysis + factors as-is, returns response.
    No recomputation — whatever the frontend sends is what gets stored.
    """
    name = payload.scenario_name.strip()
    ta   = payload.ta_name
    flt  = payload.selected_filter

    conn = get_connection()
    cur  = conn.cursor()
    try:
        exists = scenario_exists(cur, name)
        if not allow_overwrite and exists:
            raise ValueError(
                f"Scenario '{name}' already exists. "
                "Use Update Scenario to overwrite it, or choose a different name."
            )
        if allow_overwrite and not exists:
            raise ValueError(
                f"Scenario '{name}' does not exist. "
                "Use Save Scenario to create a new scenario first."
            )

        factors = payload.factors if isinstance(payload.factors, dict) else payload.factors.dict()

        save_scenario(
            cur,
            scenario_name=name,
            ta=ta,
            payer=flt.market or "",
            product=flt.product or "",
            from_date=flt.start_date,
            to_date=flt.end_date,
            chart_data={"market_analysis": payload.market_analysis},
            factors=factors,
        )
        conn.commit()

        # Build response -------------------------------------------------
        all_scenario_names = get_scenarios(cur)
        if "Base" in all_scenario_names:
            all_scenario_names.remove("Base")
        available_scenarios = ["Base"] + all_scenario_names

        # Load stored chart_data for inactive scenarios (TMV stub only)
        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        saved = {r[0]: (r[1] or {}) for r in cur.fetchall()}

        # Load config so we can compute Base TMV
        cfg = _load_config(cur, ta, flt.market or None, flt.product or None)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        from_year, from_month = _parse_ym(flt.start_date)
        forecast_periods = _resolve_forecast_periods(
            flt.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity = cfg.get("model_granularity", "monthly")

        base_factors = _estimate_default_factors(
            cur, ta, from_year, from_month, train_end_year, train_end_month, granularity
        )
        _base_ma, _ = _build_market_analysis_both_granularities(
            cur, ta, from_year, from_month,
            train_end_year, train_end_month, forecast_periods, base_factors,
            scenario_name="Base",
        )
        base_tmv = _base_ma.get("total_market_volume", {})

        def _tmv_stub(tmv: dict) -> dict:
            return {
                "market_analysis": {
                    "total_market_volume": {
                        "market_volume": {
                            "monthly": tmv.get("market_volume", {}).get("monthly", {}),
                            "yearly":  tmv.get("market_volume", {}).get("yearly",  {}),
                        },
                        "market_share": {
                            "monthly": tmv.get("market_share", {}).get("monthly", {}),
                            "yearly":  tmv.get("market_share", {}).get("yearly",  {}),
                        },
                    }
                }
            }

        def _inactive_stub(sc_name):
            if sc_name == "Base":
                return _tmv_stub(base_tmv)
            cd  = saved.get(sc_name, {})
            tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
            return _tmv_stub(tmv)

        scenarios = {}
        for sc in available_scenarios:
            if sc == name:
                scenarios[sc] = {
                    "factors":         factors,
                    "market_analysis": payload.market_analysis,
                }
            else:
                scenarios[sc] = _inactive_stub(sc)

        return {
            "available_scenarios": available_scenarios,
            "active_scenario":     name,
            "scenarios":           scenarios,
        }
    finally:
        cur.close()
        conn.close()


def save_liver_scenario(payload: LiverSaveScenarioRequest) -> dict:
    if payload.scenario_name.strip().lower() == "base":
        raise ValueError("Cannot overwrite the Base scenario. Please provide a different scenario name.")
    return _persist_and_respond(payload, allow_overwrite=False)


def update_liver_scenario(payload: LiverSaveScenarioRequest) -> dict:
    if payload.scenario_name.strip().lower() == "base":
        raise ValueError("The Base scenario cannot be updated.")
    return _persist_and_respond(payload, allow_overwrite=True)


# ---------------------------------------------------------------------------
# New scenario endpoints: POST /liver/save  PUT /liver/save  POST /activate-scenario
# ---------------------------------------------------------------------------

def _build_scenario_response(cur, name: str, ta: str, flt, factors: dict, market_analysis: dict) -> dict:
    """Shared response builder: active scenario gets full data, others get TMV stub."""
    all_names = get_scenarios(cur)
    if "Base" in all_names:
        all_names.remove("Base")
    available_scenarios = ["Base"] + all_names

    cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
    saved = {r[0]: (r[1] or {}) for r in cur.fetchall()}

    cfg = _load_config(cur, ta, flt.payer or None, flt.product or None)
    train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
    from_year, from_month = _parse_ym(flt.start_date)
    forecast_periods = _resolve_forecast_periods(
        flt.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
    )
    granularity = cfg.get("model_granularity", "monthly")

    base_factors = _estimate_default_factors(
        cur, ta, from_year, from_month, train_end_year, train_end_month, granularity
    )
    _base_ma, _ = _build_market_analysis_both_granularities(
        cur, ta, from_year, from_month,
        train_end_year, train_end_month, forecast_periods, base_factors,
        scenario_name="Base",
    )
    base_tmv = _base_ma.get("total_market_volume", {})

    def _tmv_stub(tmv):
        return {
            "market_analysis": {
                "total_market_volume": {
                    "market_volume": {
                        "monthly": tmv.get("market_volume", {}).get("monthly", {}),
                        "yearly":  tmv.get("market_volume", {}).get("yearly",  {}),
                    },
                    "market_share": {
                        "monthly": tmv.get("market_share", {}).get("monthly", {}),
                        "yearly":  tmv.get("market_share", {}).get("yearly",  {}),
                    },
                }
            }
        }

    scenarios = {}
    for sc in available_scenarios:
        if sc == name:
            scenarios[sc] = {"factors": factors, "market_analysis": market_analysis}
        elif sc == "Base":
            scenarios[sc] = _tmv_stub(base_tmv)
        else:
            cd  = saved.get(sc, {})
            tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
            scenarios[sc] = _tmv_stub(tmv)

    return {
        "message": "Scenario saved successfully",
        "available_scenarios": available_scenarios,
        "active_scenario": name,
        "scenarios": scenarios,
    }


def create_liver_scenario(payload: SaveScenarioRequest) -> dict:
    """POST /liver/save — create a new scenario. Rejects if name == 'Base' or already exists."""
    name = payload.scenario_name.strip()
    if name.lower() == "base":
        raise ValueError("Cannot save to Base. Provide a different scenario name.")

    ta  = payload.ta_name
    flt = payload.selected_filter
    factors = payload.factors or {}

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if scenario_exists(cur, name):
            raise ValueError(f"Scenario '{name}' already exists. Use PUT /liver/save to update it.")

        save_scenario(
            cur,
            scenario_name=name,
            ta=ta,
            payer=flt.payer or "",
            product=flt.product or "",
            from_date=flt.start_date,
            to_date=flt.end_date,
            chart_data={"market_analysis": payload.market_analysis},
            factors=factors,
        )
        conn.commit()
        return _build_scenario_response(cur, name, ta, flt, factors, payload.market_analysis)
    finally:
        cur.close()
        conn.close()


def update_liver_scenario_new(payload: SaveScenarioRequest) -> dict:
    """PUT /liver/save — update an existing scenario. Rejects if name == 'Base' or doesn't exist."""
    name = payload.scenario_name.strip()
    if name.lower() == "base":
        raise ValueError("The Base scenario cannot be updated.")

    ta  = payload.ta_name
    flt = payload.selected_filter
    factors = payload.factors or {}

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not scenario_exists(cur, name):
            raise ValueError(f"Scenario '{name}' does not exist. Use POST /liver/save to create it.")

        save_scenario(
            cur,
            scenario_name=name,
            ta=ta,
            payer=flt.payer or "",
            product=flt.product or "",
            from_date=flt.start_date,
            to_date=flt.end_date,
            chart_data={"market_analysis": payload.market_analysis},
            factors=factors,
        )
        conn.commit()
        return _build_scenario_response(cur, name, ta, flt, factors, payload.market_analysis)
    finally:
        cur.close()
        conn.close()


def activate_liver_scenario(payload: ActivateScenarioRequest) -> dict:
    """POST /liver/activate-scenario — load a scenario from DB (or compute Base fresh)."""
    name = payload.scenario_name.strip()
    ta   = payload.ta_name
    flt  = payload.selected_filter
    is_base = name.lower() == "base"

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cfg = _load_config(cur, ta, flt.payer or None, flt.product or None)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        from_year, from_month = _parse_ym(flt.start_date)
        forecast_periods = _resolve_forecast_periods(
            flt.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity = cfg.get("model_granularity", "monthly")

        cur.execute(
            "SELECT scenario_name, chart_data, factors FROM raw_liver.liver_scenarios"
        )
        saved = {r[0]: {"chart_data": r[1] or {}, "factors": r[2] or {}} for r in cur.fetchall()}

        all_names = get_scenarios(cur)
        if "Base" in all_names:
            all_names.remove("Base")
        available_scenarios = ["Base"] + all_names

        base_factors = _estimate_default_factors(
            cur, ta, from_year, from_month, train_end_year, train_end_month, granularity
        )
        _base_ma, _ = _build_market_analysis_both_granularities(
            cur, ta, from_year, from_month,
            train_end_year, train_end_month, forecast_periods, base_factors,
            scenario_name="Base",
        )
        base_tmv = _base_ma.get("total_market_volume", {})

        if is_base:
            active_ma      = _base_ma
            active_factors = base_factors.model_dump()
        elif name in saved:
            active_ma      = saved[name]["chart_data"].get("market_analysis", {})
            active_factors = saved[name]["factors"]
        else:
            raise ValueError(f"Scenario '{name}' not found.")

        def _tmv_stub(tmv):
            return {
                "market_analysis": {
                    "total_market_volume": {
                        "market_volume": {
                            "monthly": tmv.get("market_volume", {}).get("monthly", {}),
                            "yearly":  tmv.get("market_volume", {}).get("yearly",  {}),
                        },
                        "market_share": {
                            "monthly": tmv.get("market_share", {}).get("monthly", {}),
                            "yearly":  tmv.get("market_share", {}).get("yearly",  {}),
                        },
                    }
                }
            }

        scenarios = {}
        for sc in available_scenarios:
            if sc == name or (is_base and sc == "Base"):
                scenarios[sc] = {"factors": active_factors, "market_analysis": active_ma}
            elif sc == "Base":
                scenarios[sc] = _tmv_stub(base_tmv)
            else:
                cd  = saved.get(sc, {}).get("chart_data", {})
                tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
                scenarios[sc] = _tmv_stub(tmv)

        return {
            "ta_name": ta,
            "selected_filter": {
                "start_date": flt.start_date,
                "end_date":   flt.end_date,
                "payer":      flt.payer,
                "product":    flt.product,
            },
            "available_scenarios": available_scenarios,
            "active_scenario": name,
            "scenarios": scenarios,
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
        moving_average=MovingAverageParams(window=6),
        multiplier=1.0,
        multiplier_horizon="Forecast",
        active_model="moving_average",
    )


# ---------------------------------------------------------------------------
# Refresh / edit table
# ---------------------------------------------------------------------------

def refresh_liver(payload):
    import copy

    tab    = payload.selected_tab
    metric = payload.selected_metric
    eh     = payload.edited_hierarchy
    flt    = payload.selected_filter
    active = payload.scenario_name

    FLAT_DIST_TABS = ["market_distribution", "product_distribution"]
    HIER_DIST_TABS = ["payer_product", "product_payer"]
    DIST_TABS      = FLAT_DIST_TABS + HIER_DIST_TABS
    HIER_TABS      = set(HIER_DIST_TABS)

    # ── Load full market_analysis from DB / recompute so all tabs are populated ─
    conn = get_connection()
    cur  = conn.cursor()
    try:
        from_year, from_month = _parse_ym(flt.start_date)
        cfg = _load_config(cur, payload.ta_name, flt.market or None, flt.product or None)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = _resolve_forecast_periods(
            flt.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity = cfg.get("model_granularity", "monthly")

        if active == "Base":
            base_f = _estimate_default_factors(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            full_ma, _ = _build_market_analysis_both_granularities(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, base_f,
                sel_payer=flt.market or None, sel_product=flt.product or None,
                scenario_name="Base",
            )
        else:
            cur.execute(
                "SELECT chart_data, factors FROM raw_liver.liver_scenarios WHERE scenario_name = %s",
                (active,)
            )
            row = cur.fetchone()
            if row and row[0] and "market_analysis" in row[0]:
                full_ma = row[0]["market_analysis"]
            else:
                # Scenario not found or no chart_data — recompute with default factors
                sc_f = _estimate_default_factors(
                    cur, payload.ta_name, from_year, from_month,
                    train_end_year, train_end_month, granularity,
                )
                full_ma, _ = _build_market_analysis_both_granularities(
                    cur, payload.ta_name, from_year, from_month,
                    train_end_year, train_end_month, forecast_periods, sc_f,
                    sel_payer=flt.market or None, sel_product=flt.product or None,
                    scenario_name=active,
                )

        # Merge payload's edited tab on top of the full market_analysis so the
        # user's changes override the DB values for the selected tab only.
        ma = copy.deepcopy(full_ma)
        payload_ma = payload.market_analysis or {}
        for tab_key, tab_data in payload_ma.items():
            if not tab_data:
                continue
            if tab_key not in ma:
                ma[tab_key] = {}
            for metric_key, metric_data in tab_data.items():
                if not metric_data:
                    continue
                if metric_key not in ma[tab_key]:
                    ma[tab_key][metric_key] = {}
                for gran_key, gran_data in metric_data.items():
                    if gran_data:
                        ma[tab_key][metric_key][gran_key] = gran_data

        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        all_saved_cd = {r[0]: (r[1] or {}) for r in cur.fetchall()}
        available_scenarios = ["Base"] + list(all_saved_cd.keys())
    finally:
        cur.close()
        conn.close()

    # ── Infer effective TMV from the edited tab when it isn't in the payload ────
    # If the user previously edited TMV (first refresh) and now edits a distribution
    # tab (second refresh), the payload won't re-send TMV data, so `ma` would have
    # the stale DB TMV.  We recover the correct TMV from:
    #   flat tabs  → the "Total" row already equals the current effective TMV
    #   hier tabs  → sum of all parent-total rows equals the current effective TMV
    if tab != "total_market_volume":
        payload_tab_rows = (
            (payload_ma.get(tab) or {})
            .get("market_volume", {})
            .get("monthly", {})
            .get("table", {})
            .get("rows", [])
        )
        eff_tmv = None
        if tab in FLAT_DIST_TABS and payload_tab_rows:
            tot = next((r for r in payload_tab_rows if r.get("label", "").lower() == "total"), None)
            if tot and tot.get("values"):
                eff_tmv = [float(v) for v in tot["values"]]
        elif tab in HIER_TABS and payload_tab_rows:
            n = max((len(r.get("values", [])) for r in payload_tab_rows), default=0)
            eff_tmv = [
                sum(float(r["values"][i]) if i < len(r.get("values", [])) else 0.0
                    for r in payload_tab_rows)
                for i in range(n)
            ]
        if eff_tmv:
            tmv_mv_monthly = (ma.get("total_market_volume", {})
                               .get("market_volume", {})
                               .get("monthly", {}))
            tmv_rows = tmv_mv_monthly.get("table", {}).get("rows", [])
            # TMV table has one row per scenario — update the active scenario's row
            updated = False
            for r in tmv_rows:
                if r.get("label") == active:
                    r["values"] = eff_tmv
                    updated = True
                    break
            if not updated and len(tmv_rows) == 1:
                tmv_rows[0]["values"] = eff_tmv

    # Re-derive yearly from the updated monthly data so the propagation loop
    # for "yearly" uses values that reflect the user's edits (frontend sends monthly only).
    ma_monthly_flat, _ = _split_by_granularity(ma)
    ma_yearly_rederived = _aggregate_monthly_to_yearly(ma_monthly_flat)
    for _t, _metrics in ma_yearly_rederived.items():
        for _m, _yd in _metrics.items():
            ma.setdefault(_t, {}).setdefault(_m, {})["yearly"] = _yd

    # ── Low-level helpers ────────────────────────────────────────────────────

    def _rows(t, m, g):
        return ma.get(t, {}).get(m, {}).get(g, {}).get("table", {}).get("rows", [])

    def _set_gran(t, m, g, gran_dict):
        ma.setdefault(t, {}).setdefault(m, {})[g] = gran_dict

    def _total_vals(rows):
        """
        Extract TMV values from the TMV table rows.
        Priority:
          1. Row labeled with the active scenario name  (TMV table stores one row per scenario)
          2. Row labeled "Total"
          3. First row (single-row tables)
        Never sums multiple rows — that would add scenario values together.
        """
        # 1. Active scenario row (TMV tab uses scenario names as row labels)
        for r in rows:
            if r.get("label") == active:
                return [float(v) for v in r["values"]]
        # 2. Explicit Total row
        for r in rows:
            if r.get("label", "").lower() == "total":
                return [float(v) for v in r["values"]]
        # 3. Only one row — use it directly
        if len(rows) == 1:
            return [float(v) for v in rows[0]["values"]]
        return []

    def _sync_flat_chart(gran_dict, to_int=False):
        rows = gran_dict.get("table", {}).get("rows", [])
        # fsi lives inside chart, not at the top level
        fsi  = gran_dict.get("chart", {}).get("forecast_start_index", 0)
        def _v(vals): return [int(round(v)) for v in vals] if to_int else list(vals)
        series = []
        for r in rows:
            if r.get("label", "").lower() == "total":
                continue
            vals = [float(v) for v in r.get("values", [])]
            series.append({"label": r["label"], "history": _v(vals[:fsi]), "forecast": _v(vals[fsi:])})
        gran_dict.setdefault("chart", {})["series"] = series

    def _sync_hier_chart(gran_dict, to_int=False, chart_parent_filter=None):
        rows = gran_dict.get("table", {}).get("rows", [])
        fsi  = gran_dict.get("chart", {}).get("forecast_start_index", 0)
        def _v(vals): return [int(round(v)) for v in vals] if to_int else list(vals)
        series = []
        for parent in rows:
            plbl  = parent.get("label", "")
            # When a parent filter is set, skip parents that don't match
            if chart_parent_filter and plbl != chart_parent_filter:
                continue
            # Parent row itself is excluded from chart — only children are shown
            for child in parent.get("children", []):
                clbl  = child.get("label", "")
                cvals = [float(v) for v in child.get("values", [])]
                series.append({"label": f"{plbl} - {clbl}", "history": _v(cvals[:fsi]), "forecast": _v(cvals[fsi:])})
        gran_dict.setdefault("chart", {})["series"] = series

    def _hier_chart_parent_filter(t):
        if t == "payer_product":
            return flt.market or None
        if t == "product_payer":
            return flt.product or None
        return None

    def _put_flat(t, m, g, rows, to_int=False):
        gran_dict = dict(ma.get(t, {}).get(m, {}).get(g, {}))
        gran_dict.setdefault("table", {})["rows"] = rows
        _sync_flat_chart(gran_dict, to_int=to_int)
        _set_gran(t, m, g, gran_dict)

    def _put_hier(t, m, g, rows, to_int=False):
        gran_dict = dict(ma.get(t, {}).get(m, {}).get(g, {}))
        gran_dict.setdefault("table", {})["rows"] = rows
        _sync_hier_chart(gran_dict, to_int=to_int, chart_parent_filter=_hier_chart_parent_filter(t))
        _set_gran(t, m, g, gran_dict)

    # ── Flat conversion helpers ──────────────────────────────────────────────

    def _share_from_vol(vol_rows, tmv):
        out = []
        for r in vol_rows:
            lbl = r.get("label", "")
            if lbl.lower() == "total":
                out.append({"label": lbl, "values": [100.0] * len(tmv)})
            else:
                vals = [round(float(v) / float(t) * 100, 4) if t else 0.0
                        for v, t in zip(r.get("values", []), tmv)]
                out.append({"label": lbl, "values": vals})
        return out

    def _vol_from_share(share_rows, tmv):
        out = []
        for r in share_rows:
            lbl = r.get("label", "")
            if lbl.lower() == "total":
                out.append({"label": lbl, "values": [int(round(v)) for v in tmv]})
            else:
                vals = [int(round(float(s) / 100.0 * float(t)))
                        for s, t in zip(r.get("values", []), tmv)]
                out.append({"label": lbl, "values": vals})
        return out

    def _redistribute(rows, edited_lbl, target_vals):
        """
        Keep the edited row as-is; scale the other non-total rows proportionally
        so that non-total values sum to target_vals per column.
        Returns a new rows list (total row recomputed).
        """
        non_tot = [r for r in rows if r.get("label", "").lower() != "total"]
        edited  = next((r for r in non_tot if r["label"] == edited_lbl), None)
        others  = [r for r in non_tot if r["label"] != edited_lbl]
        if not edited:
            return rows  # nothing to redistribute

        n = len(target_vals)
        # Cap edited value per period so it never exceeds the target (TMV / 100% for share)
        capped_edited_vals = [
            min(float(edited["values"][i]) if i < len(edited.get("values", [])) else 0.0,
                float(target_vals[i]) if i < len(target_vals) else 0.0)
            for i in range(n)
        ]
        capped_edited = {**edited, "values": capped_edited_vals}

        new_others = []
        for other in others:
            new_vals = []
            for i in range(n):
                tgt   = float(target_vals[i]) if i < len(target_vals) else 0.0
                ed_v  = capped_edited_vals[i]
                remaining = max(0.0, tgt - ed_v)
                old_other_sum = sum(
                    float(o["values"][i]) if i < len(o.get("values", [])) else 0.0
                    for o in others
                )
                old_v = float(other["values"][i]) if i < len(other.get("values", [])) else 0.0
                if old_other_sum > 0:
                    new_vals.append(round(old_v / old_other_sum * remaining, 4))
                else:
                    new_vals.append(round(remaining / max(1, len(others)), 4))
            new_others.append({"label": other["label"], "values": new_vals})

        new_non_tot = [capped_edited] + new_others
        # Recompute total
        tot_vals = [0.0] * n
        for r in new_non_tot:
            for i, v in enumerate(r.get("values", [])):
                if i < n:
                    tot_vals[i] += float(v)
        return [{"label": "Total", "values": [round(v, 4) for v in tot_vals]}] + new_non_tot

    # ── Hierarchical volume scaling (used when TMV changes) ──────────────────

    def _old_rows(t, m, g):
        """Read rows from the unedited full_ma (before payload merge)."""
        return full_ma.get(t, {}).get(m, {}).get(g, {}).get("table", {}).get("rows", [])

    def _get_old_tmv(gran):
        """Extract old TMV values from full_ma using the same priority as _total_vals."""
        rows = _old_rows("total_market_volume", "market_volume", gran)
        for r in rows:
            if r.get("label") == active:
                return [float(v) for v in r["values"]]
        for r in rows:
            if r.get("label", "").lower() == "total":
                return [float(v) for v in r["values"]]
        if len(rows) == 1:
            return [float(v) for v in rows[0]["values"]]
        return []

    def _scale_hier_vols(old_rows, old_tmv, new_tmv):
        """
        Scale hierarchical child volumes proportionally: new = old * (new_tmv / old_tmv).
        Parent values are recomputed as sum of children.
        This avoids any share-format ambiguity (shares in payer_product/product_payer
        are % within parent, NOT % of total market, so share/100*TMV gives wrong numbers).
        """
        n = len(new_tmv)
        out = []
        for parent in old_rows:
            new_children = []
            for child in parent.get("children", []):
                cvals = []
                for i in range(n):
                    old_t = float(old_tmv[i]) if i < len(old_tmv) else 0.0
                    new_t = float(new_tmv[i])
                    old_v = float(child["values"][i]) if i < len(child.get("values", [])) else 0.0
                    cvals.append(int(round(old_v * new_t / old_t)) if old_t else 0)
                new_children.append({"label": child["label"], "values": cvals})
            parent_vals = [0] * n
            for child in new_children:
                for i, v in enumerate(child["values"]):
                    if i < n:
                        parent_vals[i] += v
            out.append({"label": parent["label"],
                        "values": list(parent_vals),
                        "children": new_children})
        return out

    def _transpose_hier(src_rows, dst_rows):
        """
        Mirror a hier tab into its counterpart by transposing parent↔child.
        payer_product[Medicaid][GILD] == product_payer[GILD][Medicaid].
        src_rows: updated rows of the edited tab.
        dst_rows: current rows of the counterpart tab (provides parent/child structure).
        """
        # Build lookup: {dst_parent (=src_child): {dst_child (=src_parent): [values]}}
        lookup = {}
        for sp in src_rows:
            sp_lbl = sp.get("label", "")
            for sc in sp.get("children", []):
                sc_lbl = sc.get("label", "")
                lookup.setdefault(sc_lbl, {})[sp_lbl] = [float(v) for v in sc.get("values", [])]

        new_rows = []
        for dp in dst_rows:
            dp_lbl   = dp.get("label", "")
            children = dp.get("children", [])
            new_children = []
            for dc in children:
                dc_lbl = dc.get("label", "")
                vals   = lookup.get(dp_lbl, {}).get(dc_lbl,
                         [float(v) for v in dc.get("values", [])])
                new_children.append({"label": dc_lbl, "values": [int(round(v)) for v in vals]})
            n_c = max((len(c["values"]) for c in new_children), default=0)
            parent_total = [
                sum(c["values"][i] if i < len(c["values"]) else 0 for c in new_children)
                for i in range(n_c)
            ]
            new_rows.append({"label": dp_lbl, "values": parent_total, "children": new_children})
        return new_rows

    def _scale_hier_by_flat_vol(old_hier_rows, flat_vol_map):
        """
        Scale each parent row so its total matches the corresponding flat_vol_map entry.
        Children within a parent are scaled proportionally (old_child * new_parent / old_parent).
        flat_vol_map: {parent_label: [new_vol_per_period]}
        """
        out = []
        for parent in old_hier_rows:
            plbl = parent.get("label", "")
            old_pvals = [float(v) for v in parent.get("values", [])]
            new_pvals = flat_vol_map.get(plbl, old_pvals)
            n = len(new_pvals)
            children = parent.get("children", [])
            new_children = []
            for child in children:
                old_cvals = [float(v) for v in child.get("values", [])]
                new_cvals = []
                for i in range(n):
                    op = old_pvals[i] if i < len(old_pvals) else 0.0
                    np_ = new_pvals[i]
                    oc = old_cvals[i] if i < len(old_cvals) else 0.0
                    if op:
                        new_cvals.append(int(round(oc * np_ / op)))
                    elif children:
                        new_cvals.append(int(round(np_ / len(children))))
                    else:
                        new_cvals.append(0)
                new_children.append({"label": child.get("label", ""), "values": new_cvals})
            new_parent_total = [
                sum(c["values"][i] if i < len(c["values"]) else 0 for c in new_children)
                for i in range(n)
            ]
            out.append({"label": plbl, "values": new_parent_total, "children": new_children})
        return out

    def _hier_redistribute_share(hier_rows, edited_lbl, n_cols):
        """
        edited_lbl = "ParentLabel - ChildLabel".
        Within that parent, keep edited child's share; redistribute siblings so
        children shares sum to 100%.
        """
        if not edited_lbl or " - " not in edited_lbl:
            return hier_rows
        parent_lbl, child_lbl = edited_lbl.split(" - ", 1)
        out = []
        for parent in hier_rows:
            if parent.get("label") != parent_lbl:
                out.append(parent)
                continue
            children     = parent.get("children", [])
            edited_child = next((c for c in children if c["label"] == child_lbl), None)
            sibling_cs   = [c for c in children if c["label"] != child_lbl]
            if not edited_child:
                out.append(parent)
                continue
            new_siblings = []
            for sib in sibling_cs:
                new_vals = []
                for i in range(n_cols):
                    ed_share  = float(edited_child["values"][i]) if i < len(edited_child.get("values", [])) else 0.0
                    remaining = max(0.0, 100.0 - ed_share)
                    old_sib_sum = sum(
                        float(s["values"][i]) if i < len(s.get("values", [])) else 0.0
                        for s in sibling_cs
                    )
                    old_v = float(sib["values"][i]) if i < len(sib.get("values", [])) else 0.0
                    new_vals.append(
                        round(old_v / old_sib_sum * remaining, 4) if old_sib_sum
                        else round(remaining / max(1, len(sibling_cs)), 4)
                    )
                new_siblings.append({"label": sib["label"], "values": new_vals})
            out.append({"label": parent_lbl,
                        "values": [100.0] * n_cols,
                        "children": [edited_child] + new_siblings})
        return out

    def _hier_vol_from_parent_share(hier_rows, tmv):
        """
        For user-edited market_share in a hier tab (shares are % within parent).
        Needs parent volume to derive child volume.
        parent_vol = parent_share_of_distribution * TMV — but we don't have that directly.
        Instead, keep parent vol from the existing ma and apply child distribution.
        """
        n = len(tmv)
        out = []
        for parent in hier_rows:
            # Get parent volume from current ma (already merged with payload edit)
            parent_vol_row = next(
                (r for r in _rows(tab, "market_volume", gran) if r.get("label") == parent.get("label")),
                None
            )
            if parent_vol_row is None:
                out.append(parent)
                continue
            parent_vol = [float(v) for v in parent_vol_row.get("values", [])]
            new_children = []
            for child in parent.get("children", []):
                cvals = [
                    round(float(s) / 100.0 * float(p), 4)
                    for s, p in zip(child.get("values", []), parent_vol)
                ]
                new_children.append({"label": child["label"], "values": cvals})
            # Recompute parent as sum of children
            pv = [0.0] * n
            for child in new_children:
                for i, v in enumerate(child["values"]):
                    if i < n:
                        pv[i] += v
            out.append({"label": parent["label"],
                        "values": [round(v, 4) for v in pv],
                        "children": new_children})
        return out

    # ── Core propagation ─────────────────────────────────────────────────────

    for gran in ("monthly", "yearly"):
        tmv_rows = _rows("total_market_volume", "market_volume", gran)
        tmv_vals = _total_vals(tmv_rows)
        if not tmv_vals:
            continue

        if tab == "total_market_volume":
            # Sync TMV chart from (user-edited) table
            tmv_gran = dict(ma.get("total_market_volume", {}).get("market_volume", {}).get(gran, {}))
            _sync_flat_chart(tmv_gran)
            _set_gran("total_market_volume", "market_volume", gran, tmv_gran)

            old_tmv = _get_old_tmv(gran)

            # Flat distribution tabs: share-based (shares are % of total = % of TMV)
            for dtab in FLAT_DIST_TABS:
                share_rows = _rows(dtab, "market_share", gran)
                if share_rows:
                    _put_flat(dtab, "market_volume", gran, _vol_from_share(share_rows, tmv_vals), to_int=True)

            # Hierarchical tabs: proportional scaling (shares are % within parent, not TMV)
            for dtab in HIER_DIST_TABS:
                old_vol_rows = _old_rows(dtab, "market_volume", gran)
                if old_vol_rows and old_tmv:
                    new_vol_rows = _scale_hier_vols(old_vol_rows, old_tmv, tmv_vals)
                    _put_hier(dtab, "market_volume", gran, new_vol_rows, to_int=True)

        elif tab in FLAT_DIST_TABS:
            if metric == "market_volume":
                vol_rows = _rows(tab, "market_volume", gran)
                if eh:
                    vol_rows = _redistribute(vol_rows, eh, tmv_vals)
                    _put_flat(tab, "market_volume", gran, vol_rows, to_int=True)
                _put_flat(tab, "market_share", gran,
                          _share_from_vol(_rows(tab, "market_volume", gran), tmv_vals))
            else:
                share_rows = _rows(tab, "market_share", gran)
                if eh:
                    share_rows = _redistribute(share_rows, eh, [100.0] * len(tmv_vals))
                    _put_flat(tab, "market_share", gran, share_rows)
                _put_flat(tab, "market_volume", gran,
                          _vol_from_share(_rows(tab, "market_share", gran), tmv_vals), to_int=True)

            # Top-to-bottom rule: Tab2 (product_distribution) rescales Tab3 downward,
            # but Tab3 edits do NOT touch Tab2.
            if tab == "product_distribution":
                other_flat_shares = _rows("market_distribution", "market_share", gran)
                if other_flat_shares:
                    _put_flat("market_distribution", "market_volume", gran,
                              _vol_from_share(other_flat_shares, tmv_vals), to_int=True)

            # Derive Tab4 (payer_product) and Tab5 (product_payer) using IPF.
            # Row targets = Tab3 (payer) volumes — always read after redistribution above.
            # Col targets:
            #   Tab2 edit → use Tab2 directly (just redistributed, authoritative).
            #   Tab3 edit → derive from Tab4's current column sums, which carry forward
            #               the product state from the previous Tab2 refresh.  The payload
            #               may not re-send Tab2 data, so Tab4 col sums are the best proxy.
            tab4_seed = _rows("payer_product", "market_volume", gran)
            row_targets = {
                r["label"]: [float(v) for v in r["values"]]
                for r in _rows("market_distribution", "market_volume", gran)
                if r.get("label", "").lower() != "total"
            }
            if tab == "product_distribution":
                col_targets = {
                    r["label"]: [float(v) for v in r["values"]]
                    for r in _rows("product_distribution", "market_volume", gran)
                    if r.get("label", "").lower() != "total"
                }
            elif tab4_seed:
                child_labels = list({c.get("label", "")
                                     for r in tab4_seed for c in r.get("children", [])})
                _n = len(tmv_vals)
                col_targets = {
                    lbl: [sum(float(c["values"][i]) if i < len(c.get("values", [])) else 0.0
                              for r in tab4_seed
                              for c in r.get("children", [])
                              if c.get("label", "") == lbl)
                          for i in range(_n)]
                    for lbl in child_labels
                }
            else:
                col_targets = {
                    r["label"]: [float(v) for v in r["values"]]
                    for r in _rows("product_distribution", "market_volume", gran)
                    if r.get("label", "").lower() != "total"
                }
            if tab4_seed and row_targets and col_targets:
                new_tab4 = _ipf_hier_rows(tab4_seed, row_targets, col_targets)
                _put_hier("payer_product", "market_volume", gran, new_tab4, to_int=True)
                tab5_seed = _rows("product_payer", "market_volume", gran)
                if tab5_seed:
                    _put_hier("product_payer", "market_volume", gran,
                              _transpose_hier(new_tab4, tab5_seed), to_int=True)

        elif tab in HIER_TABS:
            share_rows = _rows(tab, "market_share", gran)
            if metric == "market_share":
                if eh:
                    share_rows = _hier_redistribute_share(share_rows, eh, len(tmv_vals))
                    _put_hier(tab, "market_share", gran, share_rows)
                _put_hier(tab, "market_volume", gran,
                          _hier_vol_from_parent_share(_rows(tab, "market_share", gran), tmv_vals), to_int=True)
            else:
                # Volume edited in hier tab: edit the specific child (eh), redistribute siblings.
                hier_rows = _rows(tab, "market_volume", gran)

                edited_parent_lbl = None
                edited_child_lbl  = None
                if eh and " - " in eh:
                    edited_parent_lbl, edited_child_lbl = eh.split(" - ", 1)

                new_hier_rows = []
                for parent in hier_rows:
                    plbl     = parent.get("label", "")
                    cur_pt   = [float(v) for v in parent.get("values", [])]  # payload parent total
                    children = parent.get("children", [])
                    n_p      = len(cur_pt)

                    if edited_parent_lbl and plbl == edited_parent_lbl and edited_child_lbl:
                        edited_ch = next((c for c in children if c.get("label") == edited_child_lbl), None)
                        siblings  = [c for c in children if c.get("label") != edited_child_lbl]
                        if edited_ch:
                            # Cap edited child at the CURRENT parent total (from payload)
                            ec_vals = [
                                min(float(edited_ch["values"][i]) if i < len(edited_ch.get("values", [])) else 0.0,
                                    cur_pt[i] if i < len(cur_pt) else 0.0)
                                for i in range(n_p)
                            ]
                            # Redistribute remaining budget among siblings proportionally
                            new_siblings = []
                            for sib in siblings:
                                sib_vals = []
                                for i in range(n_p):
                                    remaining = max(0.0, cur_pt[i] - ec_vals[i])
                                    old_sib_sum = sum(
                                        float(s["values"][i]) if i < len(s.get("values", [])) else 0.0
                                        for s in siblings
                                    )
                                    old_sv = float(sib["values"][i]) if i < len(sib.get("values", [])) else 0.0
                                    if old_sib_sum > 0:
                                        sib_vals.append(round(old_sv / old_sib_sum * remaining, 4))
                                    elif siblings:
                                        sib_vals.append(round(remaining / len(siblings), 4))
                                    else:
                                        sib_vals.append(0.0)
                                new_siblings.append({"label": sib.get("label", ""), "values": sib_vals})
                            new_children = [{"label": edited_child_lbl, "values": ec_vals}] + new_siblings
                        else:
                            new_children = children
                    else:
                        # Unedited parent — keep children unchanged
                        new_children = [
                            {"label": c.get("label", ""),
                             "values": [float(v) for v in c.get("values", [])]}
                            for c in children
                        ]
                    new_hier_rows.append({
                        "label":    plbl,
                        "values":   [int(round(v)) for v in cur_pt],  # preserve payload parent total
                        "children": new_children,
                    })
                _put_hier(tab, "market_volume", gran, new_hier_rows, to_int=True)

            # Top-to-bottom rule:
            # Tab4 (payer_product) edit → propagates down to Tab5 (transpose)
            # Tab5 (product_payer) edit → affects only Tab5, no propagation
            if tab == "payer_product":
                updated_vol = _rows("payer_product", "market_volume", gran)
                tab5_seed   = _rows("product_payer", "market_volume", gran)
                if updated_vol and tab5_seed:
                    _put_hier("product_payer", "market_volume", gran,
                              _transpose_hier(updated_vol, tab5_seed), to_int=True)

    # Recompute all market_share from final market_volume values so everything is consistent.
    # For hier tabs: child_share = child_vol / sum(children) * 100 (% within parent).
    # For flat tabs: row_share  = row_vol  / col_sum         * 100 (% of distribution).
    ma = _recompute_all_market_shares_nested(ma)

    # ── Build response ────────────────────────────────────────────────────────
    def _tmv_table_only(tmv_dict):
        result = {}
        for mk in ("market_volume", "market_share"):
            if mk not in tmv_dict:
                continue
            result[mk] = {}
            for g in ("monthly", "yearly"):
                if g in tmv_dict[mk] and "table" in tmv_dict[mk][g]:
                    result[mk][g] = {"table": tmv_dict[mk][g]["table"]}
        return result

    def _inactive_stub(sc_name):
        if sc_name == "Base":
            # Base was already computed above — reuse full_ma if active is not Base,
            # otherwise recompute fresh (active == Base means full_ma is the edited Base)
            if active == "Base":
                conn2 = get_connection()
                cur2  = conn2.cursor()
                try:
                    base_f = _estimate_default_factors(
                        cur2, payload.ta_name, from_year, from_month,
                        train_end_year, train_end_month, granularity,
                    )
                    base_ma2, _ = _build_market_analysis_both_granularities(
                        cur2, payload.ta_name, from_year, from_month,
                        train_end_year, train_end_month, forecast_periods, base_f,
                        sel_payer=flt.market or None, sel_product=flt.product or None,
                        scenario_name="Base",
                    )
                    tmv = base_ma2.get("total_market_volume", {})
                finally:
                    cur2.close()
                    conn2.close()
            else:
                tmv = full_ma.get("total_market_volume", {})
        else:
            cd  = all_saved_cd.get(sc_name, {})
            tmv = cd.get("market_analysis", {}).get("total_market_volume", {})
        return {"market_analysis": {"total_market_volume": _tmv_table_only(tmv)}}

    scenarios = {}
    for sc in available_scenarios:
        if sc == active:
            scenarios[sc] = {
                "factors":         payload.factors or {},
                "market_analysis": ma,
            }
        else:
            scenarios[sc] = _inactive_stub(sc)

    return {
        "available_scenarios": available_scenarios,
        "active_scenario":     active,
        "scenarios":           scenarios,
    }
