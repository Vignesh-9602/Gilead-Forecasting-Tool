from datetime import datetime
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
)
from app.liver.repository.liver_repo import (
    get_liver_config,
    save_liver_config,
    get_payers,
    get_products,
    get_scenarios,
    get_transaction_date_range,
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
    """
    monthly → 'Apr-20'
    yearly  → '2020'   (month is ignored — use 0 as placeholder for yearly)
    """
    if granularity == "yearly":
        return str(year)
    return datetime(year, month, 1).strftime("%b-%y")


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

def get_liver_configuration(ta_name: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        row = get_liver_config(cur, ta_name)
        print(row)
        if row:
            return {"ta_name": ta_name, "exists": True, "config": row[0]}
        return {"ta_name": ta_name, "exists": False, "config": None}
    finally:
        cur.close()
        conn.close()


def save_liver_configuration(payload) -> dict:
    cfg = payload.config
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Validate train dates against actual DB data
        from_year, from_month = _parse_ym(cfg.train_start_date)
        to_year, to_month     = _parse_ym(cfg.train_end_date)

        if datetime(from_year, from_month, 1) > datetime(to_year, to_month, 1):
            raise ValueError("train_start_date cannot be after train_end_date")

        min_year, min_month, max_year, max_month = get_transaction_date_range(cur)

        min_dt = datetime(min_year, min_month, 1)
        max_dt = datetime(max_year, max_month, 1)
        start_dt = datetime(from_year, from_month, 1)
        end_dt   = datetime(to_year, to_month, 1)

        if start_dt < min_dt or start_dt > max_dt:
            raise ValueError(
                f"train_start_date is outside available data range "
                f"({_month_label(min_year, min_month)} – {_month_label(max_year, max_month)})"
            )
        if end_dt < min_dt or end_dt > max_dt:
            raise ValueError(
                f"train_end_date is outside available data range "
                f"({_month_label(min_year, min_month)} – {_month_label(max_year, max_month)})"
            )

        save_liver_config(cur, cfg.dict())
        conn.commit()
        return {"ta_name": cfg.ta_name, "exists": True, "config": cfg.dict()}
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

def _load_config(cur, ta: str) -> dict:
    """
    Returns config dict for the TA. Falls back to DB date range defaults.
    """
    row = get_liver_config(cur, ta)
    if row:
        return row[0]
    # Fallback — use full DB range with 24-month forecast
    min_year, min_month, max_year, max_month = get_transaction_date_range(cur)
    return {
        "ta_name":           ta,
        "payer":             ["All"],
        "brand":             ["All"],
        "train_start_date":  f"{min_year}-{min_month:02d}-01",
        "train_end_date":    f"{max_year}-{max_month:02d}-01",
        "model_granularity": "monthly",
        "forecast_periods":  24,
    }


# ---------------------------------------------------------------------------
# Get filters
# ---------------------------------------------------------------------------

def get_liver_filters() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        payers   = get_payers(cur)
        products = get_products(cur)
        scenarios = get_scenarios(cur)
        min_year, min_month, max_year, max_month = get_transaction_date_range(cur)

        all_months  = _generate_months(min_year, min_month, max_year, max_month)
        date_labels = [_month_label(y, m) for y, m in all_months]

        return {
            "payers":   ["All"] + payers,
            "products": ["All"] + products,
            "scenarios": ["Base"] + scenarios,
            "metric_options": [
                {"label": "Market Volume", "value": "market_volume"},
                {"label": "Market Share",  "value": "market_share"},
            ],
            "available_dates": date_labels,
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
        pwp_series = {}
        for r in pwp_rows:
            label = f"{r[2]} - {r[3]}"
            pwp_series.setdefault(label, {})[(r[0], r[1])] = float(r[4])
        tabs["payer_wise_product"] = _build_tab_data(pwp_series, month_range, month_labels, forecast_start_index, factors)

        # Tab 5
        pwpy_rows = get_product_wise_payer_yearly(cur, ta, from_year, train_end_year, product, metric)
        pwpy_series = {}
        for r in pwpy_rows:
            label = f"{r[2]} - {r[3]}"
            pwpy_series.setdefault(label, {})[(r[0], r[1])] = float(r[4])
        tabs["product_wise_payer"] = _build_tab_data(pwpy_series, month_range, month_labels, forecast_start_index, factors)

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
        pwp_series = {}
        for r in pwp_rows:
            label = f"{r[2]} - {r[3]}"
            pwp_series.setdefault(label, {})[(r[0], r[1])] = float(r[4])
        tabs["payer_wise_product"] = _build_tab_data(pwp_series, month_range, month_labels, forecast_start_index, factors)

        # Tab 5
        pwpy_rows  = get_product_wise_payer(cur, ta, from_year, from_month, train_end_year, train_end_month, product, metric)
        pwpy_series = {}
        for r in pwpy_rows:
            label = f"{r[2]} - {r[3]}"
            pwpy_series.setdefault(label, {})[(r[0], r[1])] = float(r[4])
        tabs["product_wise_payer"] = _build_tab_data(pwpy_series, month_range, month_labels, forecast_start_index, factors)

    return month_labels, forecast_start_index, tabs


# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

def apply_liver_filters(payload: LiverApplyFiltersRequest) -> dict:
    from_year, from_month = _parse_ym(payload.from_date)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cfg = _load_config(cur, payload.ta)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = cfg["forecast_periods"]
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
        cfg = _load_config(cur, payload.ta)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = cfg["forecast_periods"]
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
