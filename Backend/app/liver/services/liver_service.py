from datetime import datetime, date as date_type
from dateutil.relativedelta import relativedelta

from app.db.connection import get_connection
from app.services.forecast_service import forecast_ets, estimate_parameters
from app.liver.schemas.liver_schema import (
    LiverApplyFiltersRequest,
    LiverRecalculateRequest,
    LiverSaveScenarioRequest,
    EtsFactors,
    ChartSeries,
    TableRow,
    TabChart,
    TabTable,
    TabData,
    ChildRow,
    HierarchicalRow,
    HierarchicalTabTable,
    HierarchicalTabData,
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

        return {
            "ta_name": ta_name,
            "exists": True,
            "entries": entries,
            "available_train_months": available_train_months,
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
# Core: build a single series with ETS forecast
# ---------------------------------------------------------------------------

def _build_series_with_forecast(month_range, data_map, forecast_start_index, factors):
    historical_months = month_range[:forecast_start_index]
    forecast_count    = len(month_range) - forecast_start_index

    train_values = [float(data_map.get((y, m), 0)) for y, m in historical_months]

    if not train_values or all(v == 0 for v in train_values):
        return train_values, [0.0] * forecast_count

    scaled = [v * factors.multiplier for v in train_values]

    forecast_values = forecast_ets(
        values=scaled,
        forecast_periods=forecast_count,
        alpha=factors.level,
        beta=factors.trend,
        gamma=factors.damping,
        metric="nps",
    )
    return train_values, forecast_values


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def _build_tab_data(series_dict, month_range, month_labels, forecast_start_index, factors):
    chart_series, table_rows = [], []
    for label, data_map in series_dict.items():
        train_vals, forecast_vals = _build_series_with_forecast(
            month_range, data_map, forecast_start_index, factors
        )
        chart_series.append(ChartSeries(
            label=label, train_values=train_vals, forecast_values=forecast_vals
        ))
        table_rows.append(TableRow(
            hierarchy=label, values=train_vals + forecast_vals
        ))
    return TabData(
        chart=TabChart(series=chart_series),
        table=TabTable(headers=month_labels, rows=table_rows),
    )


def _build_hierarchical_tab_data(rows, month_range, month_labels, forecast_start_index, factors):
    """
    Builds HierarchicalTabData for tabs where rows are (year, month, parent, child, value).
    Table has one HierarchicalRow per parent with a summed total and individual child rows.
    """
    # Group: {parent: {child: {(year, month): value}}}
    grouped = {}
    for r in rows:
        key  = (r[0], r[1])
        parent, child, value = r[2], r[3], float(r[4])
        grouped.setdefault(parent, {}).setdefault(child, {})[key] = value

    chart_series = []
    table_rows   = []

    for parent, children in grouped.items():
        # Sum children per month to get parent total
        parent_map = {}
        for child_map in children.values():
            for k, v in child_map.items():
                parent_map[k] = parent_map.get(k, 0.0) + v

        parent_train, parent_forecast = _build_series_with_forecast(
            month_range, parent_map, forecast_start_index, factors
        )
        chart_series.append(ChartSeries(
            label=parent, train_values=parent_train, forecast_values=parent_forecast
        ))

        child_rows = []
        for child, child_map in children.items():
            child_train, child_forecast = _build_series_with_forecast(
                month_range, child_map, forecast_start_index, factors
            )
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

def _build_all_tabs(cur, ta, payer, product, metric, from_year, from_month,
                    train_end_year, train_end_month, forecast_periods, factors,
                    granularity: str = "monthly"):
    """
    Queries all 5 tabs from transaction_data and builds chart/table data.
    Branches on granularity — monthly uses (year, month) keys,
    yearly uses (year, 0) keys so the rest of the pipeline stays identical.
    """
    is_yearly = granularity == "yearly"

    if is_yearly:
        forecast_end_year = train_end_year + forecast_periods
        month_range          = _generate_months(from_year, 0, forecast_end_year, 0, "yearly")
        actual_range         = _generate_months(from_year, 0, train_end_year, 0, "yearly")
    else:
        forecast_end_dt  = datetime(train_end_year, train_end_month, 1) + relativedelta(months=forecast_periods)
        month_range      = _generate_months(from_year, from_month, forecast_end_dt.year, forecast_end_dt.month)
        actual_range     = _generate_months(from_year, from_month, train_end_year, train_end_month)

    month_labels         = [_month_label(y, m, granularity) for y, m in month_range]
    forecast_start_index = len(actual_range)

    tabs = {}

    if is_yearly:
        # Tab 1
        tmv_rows = get_total_market_volume_yearly(cur, ta, from_year, train_end_year, payer)
        tmv_map  = {"Total Market Volume": {(r[0], r[1]): float(r[2]) for r in tmv_rows}}
        tabs["total_market_volume"] = _build_tab_data(tmv_map, month_range, month_labels, forecast_start_index, factors)

        # Tab 2
        pd_rows  = get_product_distribution_yearly(cur, ta, from_year, train_end_year, product, metric)
        tabs["product_distribution"] = _build_tab_data(_rows_to_series(pd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors)

        # Tab 3
        pyd_rows = get_payer_distribution_yearly(cur, ta, from_year, train_end_year, payer, metric)
        tabs["payer_distribution"] = _build_tab_data(_rows_to_series(pyd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors)

        # Tab 4
        pwp_rows = get_payer_wise_product_yearly(cur, ta, from_year, train_end_year, payer, metric)
        tabs["payer_wise_product"] = _build_hierarchical_tab_data(
            pwp_rows, month_range, month_labels, forecast_start_index, factors
        )

        # Tab 5
        pwpy_rows = get_product_wise_payer_yearly(cur, ta, from_year, train_end_year, product, metric)
        tabs["product_wise_payer"] = _build_hierarchical_tab_data(
            pwpy_rows, month_range, month_labels, forecast_start_index, factors
        )

    else:
        # Tab 1
        tmv_rows = get_total_market_volume(cur, ta, from_year, from_month, train_end_year, train_end_month, payer)
        tmv_map  = {"Total Market Volume": {(r[0], r[1]): float(r[2]) for r in tmv_rows}}
        tabs["total_market_volume"] = _build_tab_data(tmv_map, month_range, month_labels, forecast_start_index, factors)

        # Tab 2
        pd_rows  = get_product_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, product, metric)
        tabs["product_distribution"] = _build_tab_data(_rows_to_series(pd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors)

        # Tab 3
        pyd_rows  = get_payer_distribution(cur, ta, from_year, from_month, train_end_year, train_end_month, payer, metric)
        tabs["payer_distribution"] = _build_tab_data(_rows_to_series(pyd_rows, 2, 3), month_range, month_labels, forecast_start_index, factors)

        # Tab 4
        pwp_rows  = get_payer_wise_product(cur, ta, from_year, from_month, train_end_year, train_end_month, payer, metric)
        tabs["payer_wise_product"] = _build_hierarchical_tab_data(
            pwp_rows, month_range, month_labels, forecast_start_index, factors
        )

        # Tab 5
        pwpy_rows  = get_product_wise_payer(cur, ta, from_year, from_month, train_end_year, train_end_month, product, metric)
        tabs["product_wise_payer"] = _build_hierarchical_tab_data(
            pwpy_rows, month_range, month_labels, forecast_start_index, factors
        )

    return month_labels, forecast_start_index, tabs


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
                f = row[0]
                factors = EtsFactors(
                    level=f["level"], trend=f["trend"],
                    damping=f["damping"], multiplier=f.get("multiplier", 1.0)
                )
            else:
                factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)
        else:
            factors = _estimate_default_factors(cur, payload.ta, from_year, from_month, train_end_year, train_end_month)

        month_labels, forecast_start_index, tabs = _build_all_tabs(
            cur, payload.ta, payload.payer, payload.product, payload.metric,
            from_year, from_month, train_end_year, train_end_month, forecast_periods, factors,
            granularity
        )

        return {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "factors":              factors,
            "tabs":                 tabs,
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Recalculate with user-provided factors
# ---------------------------------------------------------------------------

def recalculate_liver(payload: LiverRecalculateRequest) -> dict:
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

        month_labels, forecast_start_index, tabs = _build_all_tabs(
            cur, payload.ta, payload.payer, payload.product, payload.metric,
            from_year, from_month, train_end_year, train_end_month, forecast_periods, payload.factors,
            granularity
        )

        return {
            "months":               month_labels,
            "forecast_start_index": forecast_start_index,
            "factors":              payload.factors,
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
                               granularity: str = "monthly") -> EtsFactors:
    """Estimates ETS params from total market volume derived from transaction_data."""
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
    else:
        alpha, beta, gamma = 0.30, 0.20, 0.98

    return EtsFactors(level=round(alpha, 2), trend=round(beta, 2), damping=round(gamma, 2), multiplier=1.0)
