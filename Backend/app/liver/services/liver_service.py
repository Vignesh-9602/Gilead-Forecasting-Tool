from collections import defaultdict
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
from app.liver_market_events.services.market_events_service import extract_snapshot_from_market_analysis
from app.liver_market_events.repository.market_events_repo import save_market_events_scenario, delete_scenario_impact_rows
from app.liver.repository.liver_repo import (
    get_liver_configs_for_ta,
    get_liver_config_by_payment_type_payer_brand,
    get_payment_types_and_payers,
    upsert_liver_config,
    get_payers,
    get_products,
    get_scenarios,
    get_transaction_date_range,
    get_transaction_distinct_months,
    get_total_market_volume,
    get_product_distribution,
    get_payer_distribution,  # kept for refresh_liver backward compat
    get_payer_wise_product,
    get_product_wise_payer,
    get_payment_type_wise_product,
    get_payment_type_payer_product,
    get_total_market_volume_yearly,
    get_product_distribution_yearly,
    get_payer_distribution_yearly,  # kept for refresh_liver backward compat
    get_payer_wise_product_yearly,
    get_product_wise_payer_yearly,
    get_payment_type_wise_product_yearly,
    get_payment_type_payer_product_yearly,
    save_scenario,
    scenario_exists,
    delete_scenario,
    save_filter_state,
    load_filter_state,
)


# ---------------------------------------------------------------------------
# Key normalisation — convert pre-rename DB keys to current names
# ---------------------------------------------------------------------------

_TAB_KEY_MAP    = {"market_distribution": "payment_type_distribution", "payer_distribution": "payment_type_distribution"}
_METRIC_KEY_MAP = {"market_volume": "payer_volume", "market_share": "payer_share"}

def _clip_ma_to_from_date(ma: dict, from_year: int, from_month: int) -> dict:
    """
    Clip a market_analysis dict (nested monthly/yearly format) so that all
    monthly chart months and table headers only cover (from_year, from_month)
    onwards.  This prevents DB-stored wide data (e.g. Apr-20 start) from
    appearing in responses when the user's filter starts later (e.g. Mar-22),
    which would otherwise make the comparison table use Apr-20 column headers.

    Yearly data is left unchanged.  Returns the original dict unchanged when
    all months already start at or after from_date.
    """
    from_ym = from_year * 100 + from_month

    def _find_clip_idx(months: list) -> int:
        for i, m in enumerate(months):
            try:
                parts = str(m).split("-")
                y, mo = int(parts[0]), int(parts[1])
                if y * 100 + mo >= from_ym:
                    return i
            except Exception:
                pass
        return 0

    def _clip_chart(chart: dict) -> dict:
        months = chart.get("months", [])
        if not months:
            return chart
        clip_idx = _find_clip_idx(months)
        if clip_idx == 0:
            return chart
        new_months = months[clip_idx:]
        old_fsi = chart.get("forecast_start_index", 0)
        new_fsi = max(0, old_fsi - clip_idx)
        new_series = []
        for s in chart.get("series", []):
            if "history" in s or "forecast" in s:
                history  = list(s.get("history", []))
                forecast = list(s.get("forecast", []))
                hist_key, fore_key = "history", "forecast"
            else:
                history  = list(s.get("train_values", []))
                forecast = list(s.get("forecast_values", []))
                hist_key, fore_key = "train_values", "forecast_values"
            if clip_idx <= old_fsi:
                new_h, new_f = history[clip_idx:], forecast
            else:
                new_h, new_f = [], forecast[clip_idx - old_fsi:]
            base = {k: v for k, v in s.items()
                    if k not in ("history", "forecast", "train_values", "forecast_values")}
            base[hist_key] = new_h
            base[fore_key] = new_f
            new_series.append(base)
        return {**chart, "months": new_months, "forecast_start_index": new_fsi, "series": new_series}

    def _clip_table(table: dict, clip_idx: int) -> dict:
        if not table or clip_idx == 0:
            return table
        # Only write "headers" if the source table already had the key.
        # Many stored tables omit "headers" (the frontend falls back to the
        # chart months).  Writing an empty list would override that fallback
        # in JavaScript ([] is truthy) and produce a zero-column table.
        src_headers = table.get("headers")  # None if key absent
        new_rows = []
        for row in table.get("rows", []):
            new_row = dict(row)
            if "values" in row:
                new_row["values"] = list(row["values"])[clip_idx:]
            if "total" in row:
                new_row["total"] = list(row["total"])[clip_idx:]
            new_children = []
            for child in row.get("children", []):
                nc = dict(child)
                if "values" in child:
                    nc["values"] = list(child["values"])[clip_idx:]
                new_children.append(nc)
            if new_children:
                new_row["children"] = new_children
            new_rows.append(new_row)
        result = {**table, "rows": new_rows}
        if src_headers is not None:
            result["headers"] = src_headers[clip_idx:]
        return result

    def _first_row_len(table: dict) -> int:
        """Return the value-array length of the first row in table (any shape)."""
        rows = table.get("rows", [])
        if not rows:
            return 0
        r = rows[0]
        for key in ("values", "total"):
            v = r.get(key)
            if v is not None:
                return len(v)
        children = r.get("children") or []
        if children:
            return len(children[0].get("values") or [])
        return 0

    def _table_clip_idx(chart: dict, table: dict, clip_idx: int) -> int:
        """
        _clip_chart uses clip_idx derived from the chart's original months array.
        But _prepend_wide_months widens only the CHART (e.g. to Apr-20) while the
        TABLE rows stay at the original filter window (e.g. Mar-22).  Applying
        clip_idx blindly to the table over-clips it — e.g. clipping 23 from a
        70-value table yields 47 instead of the correct 70.

        Correct the clip index by accounting for the gap between chart months and
        table row values: if the table already starts later than the chart, shift
        the clip index left by that offset so the table is not over-clipped.
        """
        orig_chart_len = len(chart.get("months", []))
        if not orig_chart_len or clip_idx == 0:
            return clip_idx
        tbl_len = _first_row_len(table)
        if 0 < tbl_len < orig_chart_len:
            # Table starts (orig_chart_len - tbl_len) months into the chart.
            return max(0, clip_idx - (orig_chart_len - tbl_len))
        return clip_idx

    result = {}
    for tab_key, tab in ma.items():
        result[tab_key] = {}
        for metric_key, metric in tab.items():
            monthly = metric.get("monthly", {})
            if monthly:
                chart = monthly.get("chart", {})
                table = monthly.get("table", {})
                clip_idx = _find_clip_idx(chart.get("months", [])) if chart.get("months") else 0
                clipped_tbl = _clip_table(table, _table_clip_idx(chart, table, clip_idx))
                result[tab_key][metric_key] = {
                    "monthly": {
                        "chart": _clip_chart(chart),
                        "table": clipped_tbl,
                    },
                    "yearly": metric.get("yearly", {}),
                }
            elif "chart" in metric:
                # Flat (legacy) format
                chart = metric.get("chart", {})
                table = metric.get("table", {})
                clip_idx = _find_clip_idx(chart.get("months", [])) if chart.get("months") else 0
                clipped_tbl = _clip_table(table, _table_clip_idx(chart, table, clip_idx))
                result[tab_key][metric_key] = {
                    "chart": _clip_chart(chart),
                    "table": clipped_tbl,
                }
            elif not any(k in metric for k in ("monthly", "yearly", "chart", "table")):
                # Sub-view: metric = {inner_metric: {monthly: ..., yearly: ...}}
                result[tab_key][metric_key] = {}
                for inner_key, inner_data in metric.items():
                    inner_monthly = inner_data.get("monthly", {}) if isinstance(inner_data, dict) else {}
                    if inner_monthly:
                        ic    = inner_monthly.get("chart", {})
                        it    = inner_monthly.get("table", {})
                        ci    = _find_clip_idx(ic.get("months", [])) if ic.get("months") else 0
                        ct    = _clip_table(it, _table_clip_idx(ic, it, ci))
                        result[tab_key][metric_key][inner_key] = {
                            "monthly": {"chart": _clip_chart(ic), "table": ct},
                            "yearly":  inner_data.get("yearly", {}),
                        }
                    else:
                        result[tab_key][metric_key][inner_key] = inner_data
            else:
                result[tab_key][metric_key] = metric
    return result


def _normalize_ma_keys(ma: dict) -> dict:
    """
    Rename legacy market_analysis keys produced before the payer-rename:
      tab    : market_distribution → payer_distribution
      metric : market_volume → payer_volume, market_share → payer_share
    Safe to call on already-normalised data (identity for new keys).
    """
    result = {}
    for tab_key, tab_data in ma.items():
        new_tab = _TAB_KEY_MAP.get(tab_key, tab_key)
        if not isinstance(tab_data, dict):
            result[new_tab] = tab_data
            continue
        result[new_tab] = {
            _METRIC_KEY_MAP.get(mk, mk): mv
            for mk, mv in tab_data.items()
        }
    return result


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


def _widest_forecast_end(cur, ta: str) -> tuple[int, int] | None:
    """
    Latest (train_end_date + forecast_periods) across EVERY (payer, brand)
    config for this TA -- the same "available_months" end-of-range concept
    already computed inline for the date-range dropdown (get_liver_filters,
    apply_liver_filters). Different (payer, brand) combos can have different
    train_end_date/forecast_periods, so the widest available end is not
    necessarily whatever the currently-selected combo's own config says.

    Returns None if no config has a usable train_end_date (caller should
    fall back to the selected config's own values in that case).
    """
    all_cfgs = get_liver_configs_for_ta(cur, ta)
    end_ym = None
    for row in all_cfgs:
        cfg = row[2] if isinstance(row[2], dict) else {}
        te = cfg.get("train_end_date", "")
        fp = int(cfg.get("forecast_periods", 24))
        if not te:
            continue
        try:
            ey, em = _parse_ym(te)
            fe = _add_months(date_type(ey, em, 1), fp)
            feym = fe.year * 100 + fe.month
            if end_ym is None or feym > end_ym:
                end_ym = feym
        except Exception:
            continue
    if end_ym is None:
        return None
    return end_ym // 100, end_ym % 100


def _extend_forecast_periods_to_widest_end(
    cur, ta: str, train_end_year: int, train_end_month: int, forecast_periods: int
) -> int:
    """
    Extend `forecast_periods` (from one specific config) so the resulting
    train_end + forecast_periods reaches at least as far as the widest
    available end across every config for this TA -- never shortens it.
    train_end_year/month stay as the SELECTED config's own values (that's
    still the correct model-fitting boundary); only how far the forecast is
    carried forward changes.
    """
    widest_end = _widest_forecast_end(cur, ta)
    if widest_end is None:
        return forecast_periods
    widest_end_dt = date_type(widest_end[0], widest_end[1], 1)
    this_end_dt = _add_months(date_type(train_end_year, train_end_month, 1), forecast_periods)
    if widest_end_dt <= this_end_dt:
        return forecast_periods
    return (widest_end_dt.year - train_end_year) * 12 + (widest_end_dt.month - train_end_month)


def get_liver_configuration(ta_name: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        month_rows = get_transaction_distinct_months(cur, ta_name)
        available_train_months = [
            date_type(int(r[0]), int(r[1]), 1).isoformat() for r in month_rows
        ]

        # Available payment_types and their sub-payers from transaction_data
        pt_payer_map    = get_payment_types_and_payers(cur, ta_name)
        available_pt    = sorted(pt_payer_map.keys())
        available_brands = get_products(cur)

        db_rows = get_liver_configs_for_ta(cur, ta_name)
        if not db_rows:
            _, _, max_year, max_month = get_transaction_date_range(cur)
            max_dt      = date_type(max_year, max_month, 1)
            start_dt    = _add_months(max_dt, -60)
            forecast_dt = _add_months(max_dt, 12)
            default_pt  = available_pt[0] if available_pt else "Commercial"
            default_payer = pt_payer_map.get(default_pt, [""])[0]
            return {
                "ta_name":                ta_name,
                "exists":                 False,
                "entries":                [],
                "available_train_months": available_train_months,
                "available_payment_types": available_pt,
                "available_payers":        pt_payer_map,
                "available_brands":        available_brands,
                "default_config": {
                    "payment_type":      default_pt,
                    "payer":             default_payer,
                    "brand":             available_brands[0] if available_brands else "GILD",
                    "train_start_date":  start_dt.isoformat(),
                    "train_end_date":    max_dt.isoformat(),
                    "model_granularity": "monthly",
                    "forecast_periods":  forecast_dt.isoformat(),
                },
                "config": {
                    "payment_type":      [default_pt],
                    "payer":             [default_payer],
                    "brand":             [available_brands[0]] if available_brands else ["GILD"],
                    "train_start_date":  start_dt.isoformat(),
                    "train_end_date":    max_dt.isoformat(),
                    "model_granularity": "monthly",
                    "forecast_periods":  forecast_dt.isoformat(),
                },
            }

        entries = []
        for payment_type, payer, brand, config, updated_at in db_rows:
            train_end    = date_type.fromisoformat(config["train_end_date"][:10])
            forecast_end = _add_months(train_end, int(config["forecast_periods"]))
            entries.append({
                "payment_type":       payment_type,
                "payer":              payer,
                "brand":              brand,
                "train_start_date":   config["train_start_date"][:10],
                "train_end_date":     config["train_end_date"][:10],
                "model_granularity":  config.get("model_granularity", "monthly"),
                "forecast_periods":   forecast_end.isoformat(),
                "updated_at":         updated_at,
            })

        latest_ts      = max(e["updated_at"] for e in entries)
        latest_entries = [e for e in entries if e["updated_at"] == latest_ts]
        first          = latest_entries[0]

        return {
            "ta_name":                ta_name,
            "exists":                 True,
            "entries":                entries,
            "available_train_months": available_train_months,
            "available_payment_types": available_pt,
            "available_payers":        pt_payer_map,
            "available_brands":        available_brands,
            "config": {
                "payment_type":      list(dict.fromkeys(e["payment_type"] for e in latest_entries)),
                "payer":             list(dict.fromkeys(e["payer"]         for e in latest_entries)),
                "brand":             list(dict.fromkeys(e["brand"]         for e in latest_entries)),
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

        # Config stored without payment_type/payer/brand (those are DB columns)
        config_to_save = {
            "ta_name":           cfg.ta_name,
            "train_start_date":  cfg.train_start_date[:10],
            "train_end_date":    cfg.train_end_date[:10],
            "model_granularity": cfg.model_granularity,
            "forecast_periods":  forecast_periods_int,
        }

        # Resolve valid (payment_type, payer) combos from transaction_data so that
        # selecting Cash + [CVS, Non CVS] doesn't silently create dead rows.
        pt_payer_map   = get_payment_types_and_payers(cur, cfg.ta_name)
        payment_types  = cfg.payment_type or []
        selected_payers = cfg.payer or []
        brands         = cfg.brand or []

        saved = 0
        for pt in payment_types:
            available_payers = pt_payer_map.get(pt, [])
            # Intersect selected payers with those that actually exist for this payment_type.
            # If the intersection is empty fall back to all available payers for this payment_type.
            if available_payers:
                # transaction_data is migrated — intersect to only valid combos.
                # If intersection is empty (e.g. Cash has no CVS/Non-CVS) fall back
                # to all real payers for that payment_type (e.g. NA for Cash).
                resolved_payers = [p for p in selected_payers if p in available_payers]
                if not resolved_payers:
                    resolved_payers = available_payers
            else:
                # transaction_data not yet migrated — no sub-payer info available.
                # Cannot determine which payers are valid per payment_type, so store
                # '' (no sub-payer) for every payment_type to avoid cross-contamination
                # (e.g. Cash getting CVS/Non-CVS rows that don't belong to it).
                resolved_payers = [""]
            for payer in resolved_payers:
                for brand in brands:
                    upsert_liver_config(cur, cfg.ta_name, pt, payer, brand, config_to_save)
                    saved += 1

        conn.commit()

        return {
            "ta_name":            cfg.ta_name,
            "status":             "config_saved",
            "saved_combinations": saved,
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


def _series_model_months(config_map: dict, payer: str, brand: str, historical_months: list) -> list:
    """Return the subset of historical_months within the configured train date range for (payer, brand).
    Falls back to full historical_months when no config is found or the filtered result is empty.
    """
    if not config_map or not payer or not brand:
        return historical_months
    key = (payer.strip().lower(), brand.strip().lower())
    cfg = config_map.get(key)
    if not cfg:
        return historical_months
    ts_y, ts_m, te_y, te_m = cfg
    ts = ts_y * 100 + ts_m
    te = te_y * 100 + te_m
    filtered = [(y, m) for y, m in historical_months if ts <= y * 100 + m <= te]
    return filtered if filtered else historical_months


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
                                 is_selected: bool = True, auto_model: str = "linear",
                                 model_start_ym: int = None, fc_offset: int = 0):
    """
    model_start_ym: year*100+month cutoff — only months >= this value are used
    for model training.  Months before it are still included in the returned
    history array for display (may be zero if no data exists there).
    When None, leading zeros are stripped as a fallback.
    fc_offset: number of extra forecast periods to generate before the display
    window starts (used when FROM DATE is past train_end).  The model always
    generates forecast_count+fc_offset periods; only the last forecast_count
    values are returned so the phase is aligned to the display window.
    """
    historical_months   = month_range[:forecast_start_index]
    forecast_months     = month_range[forecast_start_index:]
    forecast_count      = len(forecast_months)
    _model_fc_count     = forecast_count + fc_offset

    original_train      = [float(data_map.get((y, m), 0)) for y, m in historical_months]

    # Build model_train from ALL data_map entries within the configured training window.
    # data_map is always fetched from min(from_year, _wide_from_year), so it contains
    # the full training range regardless of what the user selected as FROM DATE.
    # This means changing the display FROM DATE never changes which data the model trains on.
    if model_start_ym is not None:
        _model_keys = sorted(
            (k for k in data_map if k[0] * 100 + k[1] >= model_start_ym),
            key=lambda k: k[0] * 100 + k[1],
        )
        model_train = [float(data_map[k]) for k in _model_keys if data_map.get(k) is not None]
        if not model_train or all(v == 0 for v in model_train):
            model_train = original_train  # last-resort fallback
    else:
        # Fallback: strip leading zeros when no explicit cutoff is given
        _first_nz = next((i for i, v in enumerate(original_train) if v != 0), 0)
        model_train = original_train[_first_nz:] if _first_nz > 0 else original_train

    if not model_train or all(v == 0 for v in model_train):
        return original_train, [0.0] * forecast_count

    # Non-selected series: auto-estimate from data, NO multiplier applied.
    # Multiplier only affects the selected payer/brand (oncology pattern).
    if not is_selected:
        if auto_model == "ets":
            if len(model_train) >= 4:
                alpha, beta, gamma = estimate_parameters(model_train)
            else:
                alpha, beta, gamma = 0.30, 0.20, 0.98
            if len(model_train) >= 2:
                fc = forecast_ets(values=model_train, forecast_periods=_model_fc_count,
                                  alpha=alpha, beta=beta, gamma=gamma, metric="nps")
            else:
                fc = _simple_moving_average_forecast(model_train, _model_fc_count, window=6)
        elif auto_model == "moving_average":
            fc = _simple_moving_average_forecast(model_train, _model_fc_count, window=6)
        else:
            total_growth = _estimate_linear_growth(model_train)
            fc = forecast_linear(model_train[-1], _model_fc_count,
                                 total_growth, _model_fc_count, "nps")
        return original_train, fc[fc_offset:]

    # Selected series: user's factors + multiplier applied to display values only.
    # Model ALWAYS runs on original data (oncology pattern).
    multiplier        = factors.multiplier
    mh                = (factors.multiplier_horizon or "Forecast").lower()
    apply_to_history  = mh in ("history", "both history & forecast")
    apply_to_forecast = mh in ("forecast", "both history & forecast")

    active   = factors.active_model.lower()
    f_params = getattr(factors, active, None)

    if active == "ets":
        f = factors.ets
        if len(model_train) >= 2:
            fc = forecast_ets(values=model_train, forecast_periods=_model_fc_count,
                              alpha=f.alpha, beta=f.beta, gamma=f.gamma, metric="nps")
        else:
            fc = _simple_moving_average_forecast(model_train, _model_fc_count, window=6)
    elif active == "moving_average":
        window = getattr(factors.moving_average, "window", 6) if factors.moving_average else 6
        fc = _forecast_moving_average(model_train, _model_fc_count, window=window)
    else:
        base_value = model_train[-1]
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

        # Shift traj_idx by fc_offset: the generated array starts fc_offset periods
        # before the display window, so the flat pre-growth region must also extend
        # fc_offset extra periods so the trajectory start aligns after slicing.
        _traj_adj  = traj_idx + fc_offset
        pre_values = [base_value] * _traj_adj
        remaining  = _model_fc_count - _traj_adj

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

    fc = fc[fc_offset:]  # align to display window: drop periods before FROM DATE
    # Apply multiplier to display values only (never to model input)
    display_train    = [round(v * multiplier, 2) for v in original_train] if apply_to_history  else original_train
    display_forecast = [round(v * multiplier, 2) for v in fc]             if apply_to_forecast else fc
    return display_train, display_forecast


# ---------------------------------------------------------------------------
# Tab builder
# ---------------------------------------------------------------------------

def _build_tab_data(series_dict, month_range, month_labels, forecast_start_index, factors,
                    selected_label=None, auto_model="linear", add_total=False,
                    model_start_ym: int = None, fc_offset: int = 0):
    """
    selected_label: label whose series gets user factors; all others use auto_model.
    None → all series use user factors (is_selected=True for all).
    ""  → no series matches → all series use auto_model (used for Tab 1 ETS).
    add_total: if True, prepend a Total row that sums all series values.
    model_start_ym: year*100+month; only months >= this are used for model training.
    fc_offset: extra periods generated before the display window (see _build_series_with_forecast).
    """
    chart_series, table_rows = [], []
    for label, data_map in series_dict.items():
        is_sel = (selected_label is None or label == selected_label)
        train_vals, forecast_vals = _build_series_with_forecast(
            month_range, data_map, forecast_start_index, factors,
            is_selected=is_sel, auto_model=auto_model, model_start_ym=model_start_ym,
            fc_offset=fc_offset,
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
                                  selected_parent=None, selected_child=None, auto_model="linear",
                                  fc_offset: int = 0):
    """
    selected_parent/selected_child: the combination that gets user factors.
    None for both → all series use auto_model.
    Parent totals are sum of individually-forecasted children.
    fc_offset: extra periods before the display window (see _build_series_with_forecast).
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
                is_selected=child_is_sel, auto_model=auto_model, fc_offset=fc_offset,
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


def _forecast_share_by_factors(train_values: list, forecast_count: int, factors,
                                traj_adj: int = 0) -> list:
    """Apply the user's active model to a share (%) training series.
    MA window is clamped to a minimum of 3.
    traj_adj: number of flat (base-value) periods prepended before growth, matching
    the trajectory_start offset computed by the caller (traj_idx + fc_offset).
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
    pre_values = [base] * traj_adj
    remaining  = forecast_count - traj_adj
    if remaining <= 0:
        return pre_values[:forecast_count]
    if active == "linear":
        return pre_values + forecast_linear(base, remaining, tg, dur, "nps")
    if active == "exponential":
        return pre_values + forecast_exponential(base, remaining, tg, dur, k, "nps")
    if active == "logarithmic":
        return pre_values + forecast_logarithmic(base, remaining, tg, dur, k, "nps")
    if active == "scurve":
        return pre_values + forecast_s_curve(base, remaining, tg, dur, k, "nps")
    return _simple_moving_average_forecast(train_values, forecast_count, window=6)


def _build_tab_data_from_shares(share_series_dict, vol_series_dict, month_range, month_labels,
                                  forecast_start_index, factors, tmv_fc,
                                  selected_label=None, add_total=False,
                                  model_months_by_label=None, fc_offset: int = 0):
    """
    Forecast each series' market share (%), normalize to 100 per period, then multiply
    by TMV forecast to produce volume forecasts.  Historical values come from actual
    volume data (vol_series_dict) so actuals are never touched.

    selected_label: that label uses user factors on its share; all others use simple MA.
    model_months_by_label: {label: [(year,month),...]} — per-series training window from
        global config; falls back to full historical_months when absent.
    fc_offset: extra forecast periods before the display window (see _build_series_with_forecast).
    """
    fsi = forecast_start_index
    historical_months = month_range[:fsi]
    forecast_count = len(month_range) - fsi
    _model_fc_count = forecast_count + fc_offset

    # Compute trajectory adjustment so _forecast_share_by_factors can insert the
    # same flat pre-growth period that _build_series_with_forecast does for Tab1.
    _forecast_months = month_range[fsi:]
    _active_key = factors.active_model.lower() if factors else "moving_average"
    _fp = getattr(factors, _active_key, None) if factors else None
    _traj_str = getattr(_fp, "trajectory_start", None) if _fp else None
    _traj_idx = 0
    if _traj_str:
        try:
            _tstart = datetime.fromisoformat(_traj_str[:10])
            for _i, (_fy, _fm) in enumerate(_forecast_months):
                if datetime(_fy, _fm, 1) >= _tstart:
                    _traj_idx = _i
                    break
        except Exception:
            pass
    _traj_adj = _traj_idx + fc_offset

    def _mtm(label):
        """Return the model-training months for this label (per-series config or full history)."""
        if model_months_by_label:
            mm = model_months_by_label.get(label)
            if mm:
                return mm
        return historical_months

    # ── Step 1: forecast the selected label's share directly ─────────────────
    # When a label is explicitly selected, apply the user's model to that series
    # and distribute the remainder proportionally to all other labels based on
    # their last-training-period shares.  This avoids the normalization-denominator
    # problem: if we normalize all forecasts together, simple-MA inflation on other
    # series can depress the selected series below its base even when growth > 0.
    labels = list(share_series_dict.keys())

    # Collect last-training share for every label (used for remainder distribution)
    # Use each label's own configured training window so the base share reflects
    # the correct end of its configured period.
    last_train_share = {}
    for label, share_map in share_series_dict.items():
        vals = [float(share_map.get((y, m), 0)) for y, m in _mtm(label)]
        last_train_share[label] = vals[-1] if vals else 0.0

    sel_fc_shares = {}   # final per-period share for each label

    if selected_label is not None and selected_label in share_series_dict:
        # -- Selected series: apply user's model directly --
        sel_share_map = share_series_dict[selected_label]
        sel_train = [float(sel_share_map.get((y, m), 0)) for y, m in _mtm(selected_label)]
        sel_raw = _forecast_share_by_factors(sel_train, _model_fc_count, factors, traj_adj=_traj_adj)
        # Slice off the fc_offset periods before the display window.
        sel_fc_shares[selected_label] = [min(100.0, max(0.0, v)) for v in sel_raw[fc_offset:]]

        # -- Other series: distribute remainder proportionally from last training shares --
        other_labels = [l for l in labels if l != selected_label]
        other_base_sum = sum(last_train_share.get(l, 0.0) for l in other_labels)
        for l in other_labels:
            sel_fc_shares[l] = []
        # sel_fc_shares[selected_label] is already sliced to forecast_count entries.
        for i in range(forecast_count):
            remainder = max(0.0, 100.0 - sel_fc_shares[selected_label][i])
            for l in other_labels:
                base_share = last_train_share.get(l, 0.0)
                sel_fc_shares[l].append(
                    remainder * base_share / other_base_sum if other_base_sum > 0 else 0.0
                )
    else:
        # No explicit selection — apply user's model to every series then normalize.
        # Generate _model_fc_count periods so the result aligns correctly after slicing.
        raw_fc = {}
        for label, share_map in share_series_dict.items():
            share_train = [float(share_map.get((y, m), 0)) for y, m in _mtm(label)]
            raw_fc[label] = _forecast_share_by_factors(share_train, _model_fc_count, factors,
                                                        traj_adj=_traj_adj)
        for i in range(_model_fc_count):
            total = sum(raw_fc[l][i] for l in raw_fc)
            for l in raw_fc:
                sel_fc_shares.setdefault(l, []).append(
                    raw_fc[l][i] / total * 100.0 if total > 0 else 0.0
                )
        # Drop the fc_offset periods that precede the display window.
        for l in sel_fc_shares:
            sel_fc_shares[l] = sel_fc_shares[l][fc_offset:]

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
                                               selected_child=None,
                                               model_months_by_pair=None, fc_offset: int = 0):
    """
    Build hierarchical tab data (Tab4/Tab5) by forecasting within-parent market shares,
    normalizing within each parent to 100 %, then converting to volume using a simple
    MA parent-volume estimate.  IPF (called after this) corrects absolute levels to
    match Tab2/Tab3 constraints.

    selected_child: the child label matching the UI filter — uses the user's projection
    model on its within-parent share; all other children use simple MA.
    model_months_by_pair: {(parent, child): [(year,month),...]} — per-cell training window
        from global config; falls back to full historical_months when absent.
    fc_offset: extra forecast periods before the display window (see _build_series_with_forecast).
    """
    fsi = forecast_start_index
    historical_months = month_range[:fsi]
    forecast_count = len(month_range) - fsi
    _model_fc_count = forecast_count + fc_offset

    # Compute trajectory adjustment (mirrors _build_tab_data_from_shares logic).
    _forecast_months_h = month_range[fsi:]
    _active_key_h = factors.active_model.lower() if factors else "moving_average"
    _fp_h = getattr(factors, _active_key_h, None) if factors else None
    _traj_str_h = getattr(_fp_h, "trajectory_start", None) if _fp_h else None
    _traj_idx_h = 0
    if _traj_str_h:
        try:
            _tstart_h = datetime.fromisoformat(_traj_str_h[:10])
            for _i_h, (_fy_h, _fm_h) in enumerate(_forecast_months_h):
                if datetime(_fy_h, _fm_h, 1) >= _tstart_h:
                    _traj_idx_h = _i_h
                    break
        except Exception:
            pass
    _traj_adj_h = _traj_idx_h + fc_offset

    def _mtm(parent, child):
        """Return model-training months for this (parent, child) cell."""
        if model_months_by_pair:
            mm = model_months_by_pair.get((parent, child))
            if mm:
                return mm
        return historical_months

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
            vals = [float(share_map.get((y, m), 0)) for y, m in _mtm(parent, child)]
            last_child_share[child] = vals[-1] if vals else 0.0

        norm_shares = {}  # final per-period within-parent share for each child

        if selected_child is not None and selected_child in children_ms and factors is not None:
            sel_share_map = children_ms[selected_child]
            sel_train = [float(sel_share_map.get((y, m), 0)) for y, m in _mtm(parent, selected_child)]
            sel_child_fc = _forecast_share_by_factors(sel_train, _model_fc_count, factors,
                                                       traj_adj=_traj_adj_h)
            # Slice off fc_offset periods that precede the display window.
            norm_shares[selected_child] = [min(100.0, max(0.0, v)) for v in sel_child_fc[fc_offset:]]

            other_children = [c for c in child_list if c != selected_child]
            other_base_sum = sum(last_child_share.get(c, 0.0) for c in other_children)
            for c in other_children:
                norm_shares[c] = []
            # norm_shares[selected_child] is already sliced to forecast_count entries.
            for i in range(forecast_count):
                remainder = max(0.0, 100.0 - norm_shares[selected_child][i])
                for c in other_children:
                    base_s = last_child_share.get(c, 0.0)
                    norm_shares[c].append(
                        remainder * base_s / other_base_sum if other_base_sum > 0 else 0.0
                    )
        else:
            # No selection: apply user's model to every child then normalize within parent.
            # Generate _model_fc_count periods so the result aligns correctly after slicing.
            raw_shares = {}
            for child, share_map in children_ms.items():
                share_train = [float(share_map.get((y, m), 0)) for y, m in _mtm(parent, child)]
                raw_shares[child] = (
                    _forecast_share_by_factors(share_train, _model_fc_count, factors)
                    if factors is not None
                    else _simple_moving_average_forecast(share_train, _model_fc_count, window=6)
                )
            for i in range(_model_fc_count):
                total = sum(raw_shares[c][i] for c in raw_shares)
                for c in raw_shares:
                    norm_shares.setdefault(c, []).append(
                        raw_shares[c][i] / total * 100.0 if total > 0 else 0.0
                    )
            # Drop fc_offset periods that precede the display window.
            for c in norm_shares:
                norm_shares[c] = norm_shares[c][fc_offset:]

        # Parent volume history = sum of children's actual volumes
        parent_vol_by_period = {}
        for child_mv in children_mv.values():
            for k, v in child_mv.items():
                parent_vol_by_period[k] = parent_vol_by_period.get(k, 0.0) + v
        parent_vol_train = [float(parent_vol_by_period.get((y, m), 0)) for y, m in historical_months]

        # When FROM DATE is past train_end, historical_months is empty so parent_vol_train
        # is empty too — but parent_vol_by_period still holds the training-period data
        # (DB query starts from _min_from_year).  Use all available data as the MA base.
        _parent_model_train = parent_vol_train
        if not _parent_model_train and parent_vol_by_period:
            _sorted_keys = sorted(parent_vol_by_period.keys(), key=lambda k: k[0] * 100 + k[1])
            _parent_model_train = [float(parent_vol_by_period[k]) for k in _sorted_keys]

        # Parent volume forecast placeholder: simple MA of parent history
        # (IPF will correct this to match Tab3/Tab2 row/column targets)
        # Generate _model_fc_count periods and slice so the phase matches norm_shares.
        if _parent_model_train and not all(v == 0 for v in _parent_model_train):
            parent_vol_fc = _simple_moving_average_forecast(_parent_model_train, _model_fc_count, window=3)[fc_offset:]
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
            # Prefer the model's own trajectory_start (from the user's request);
            # fall back to the caller-supplied default only when absent.
            "trajectory_start": getattr(model_params, "trajectory_start", None) or trajectory_start,
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
        return [int(round(v)) for v in vals] if to_int else list(vals)

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


def _fmt_hier(tab, month_labels, forecast_start_index, to_int=False, chart_parent_filter=None, chart_child_filter=None):
    def _v(vals):
        return [int(round(v)) for v in vals] if to_int else list(vals)

    if chart_parent_filter and chart_child_filter:
        target = f"{chart_parent_filter} - {chart_child_filter}"
        chart_series = [s for s in tab.chart.series if s.label == target]
    elif chart_parent_filter:
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
    Build all tabs for BOTH market_volume and market_share.
    Returns (month_labels, forecast_start_index, market_analysis_dict, tab1_ets).
    market_analysis_dict keys:
      total_market_volume, product_distribution, payment_type_distribution (flat tabs),
      payment_type_product (nested: payment_type_product / product_payment_type),
      payment_type_payer_product (nested: payment_type_payer / payment_type_product / product_payment_type),
      event_management (empty dict placeholder for Tab 6).
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

    # ── Per-series config training windows ──────────────────────────────────
    # _wide_from_year/_month = earliest configured train_start across all (payer,brand)
    # configs.  This is the MODEL training start — it must NOT be influenced by the
    # user's display FROM DATE so that changing the display range never retrains the
    # model on a different dataset.
    _all_cfgs = get_liver_configs_for_ta(cur, ta)
    _config_map: dict = {}
    _wide_from_year, _wide_from_month = train_end_year, train_end_month  # sentinel: high
    for _row in _all_cfgs:
        # Row is now (payment_type, payer, brand, config, updated_at)
        _pt, _b, _cfg = _row[0], _row[2], (_row[3] if isinstance(_row[3], dict) else {})
        _ts = _cfg.get("train_start_date", "")
        _te = _cfg.get("train_end_date", "")
        if _ts and _te:
            try:
                _ts_y, _ts_m = _parse_ym(_ts)
                _te_y, _te_m = _parse_ym(_te)
                _key = (_pt.strip().lower(), _b.strip().lower())
                # Take the earliest train_start for this (payment_type, brand) pair
                if _key not in _config_map or _ts_y * 100 + _ts_m < _config_map[_key][0] * 100 + _config_map[_key][1]:
                    _config_map[_key] = (_ts_y, _ts_m, _te_y, _te_m)
                if _ts_y * 100 + _ts_m < _wide_from_year * 100 + _wide_from_month:
                    _wide_from_year, _wide_from_month = _ts_y, _ts_m
            except Exception:
                pass

    # No configs found — fall back to the payload's from_date for training start
    if _wide_from_year * 100 + _wide_from_month >= train_end_year * 100 + train_end_month:
        _wide_from_year, _wide_from_month = from_year, from_month

    # Model training actual range (candidate pool for _series_model_months)
    if is_yearly:
        _wide_actual_range = _generate_months(_wide_from_year, 0, train_end_year, 0, "yearly")
    else:
        _wide_actual_range = _generate_months(_wide_from_year, _wide_from_month, train_end_year, train_end_month)
    actual_range = _wide_actual_range

    # Chart display range: user's FROM DATE (independent of model training window)
    if is_yearly:
        month_range = _generate_months(from_year, 0, forecast_end_year, 0, "yearly")
    else:
        month_range = _generate_months(from_year, from_month, forecast_end_dt.year, forecast_end_dt.month)
    month_labels = [_month_label(y, m, granularity) for y, m in month_range]

    # fsi = number of months in month_range that are ≤ train_end (actual data period)
    if is_yearly:
        fsi = sum(1 for y, _ in month_range if y <= train_end_year)
    else:
        fsi = sum(1 for y, m in month_range if y * 100 + m <= train_end_year * 100 + train_end_month)
    forecast_start_index = fsi
    n                    = len(month_labels)

    # When FROM DATE is past train_end (fsi=0), ETS must still generate forecasts
    # starting at train_end+1.  _fc_offset is the number of periods between
    # train_end+1 and FROM DATE; builders generate (forecast_count + _fc_offset) values
    # then slice off the first _fc_offset so the displayed values are phase-aligned.
    _fc_offset = 0
    if fsi == 0 and not is_yearly and month_range:
        _first_fy, _first_fm = month_range[0]
        _train_next = datetime(train_end_year, train_end_month, 1) + relativedelta(months=1)
        _fc_offset = max(0, (_first_fy - _train_next.year) * 12 + (_first_fm - _train_next.month))

    # DB queries always start from min(from_year, _wide_from_year) so that:
    # - data_map always contains the full configured training window (Apr 2020–Dec 2025)
    # - model_train in _build_series_with_forecast is never truncated by a later FROM DATE
    # - pre-training display months (from_year < _wide_from_year) are also included if they
    #   exist in the DB (those months get 0 from data_map.get(..., 0) if absent)
    if is_yearly:
        _min_from_year  = min(from_year, _wide_from_year)
        _min_from_month = 0
    else:
        if from_year * 100 + from_month < _wide_from_year * 100 + _wide_from_month:
            _min_from_year, _min_from_month = from_year, from_month
        else:
            _min_from_year, _min_from_month = _wide_from_year, _wide_from_month

    # ── Tab 1: TMV (ETS) — metric-independent ──────────────────────────────
    # Fetch display data from user's from_year so pre-training history shows in chart.
    # ETS params are estimated only from the configured training window (_wide_from_year+).
    _model_start_ym = _wide_from_year * 100 + _wide_from_month
    if is_yearly:
        _tmv_train = get_total_market_volume_yearly(cur, ta, _min_from_year, train_end_year, None)
    else:
        _tmv_train = get_total_market_volume(cur, ta, _min_from_year, _min_from_month, train_end_year, train_end_month, None)
    if is_yearly:
        _tmv_values = [float(r[-1]) for r in _tmv_train
                       if r[-1] is not None and r[0] >= _wide_from_year]
    else:
        _tmv_values = [float(r[-1]) for r in _tmv_train
                       if r[-1] is not None and r[0] * 100 + r[1] >= _model_start_ym]
    if len(_tmv_values) >= 4:
        _t1a, _t1b, _t1g = estimate_parameters(_tmv_values)
    else:
        _t1a, _t1b, _t1g = 0.30, 0.20, 0.98
    tab1_ets     = EtsParams(alpha=round(_t1a, 4), beta=round(_t1b, 4), gamma=round(_t1g, 4))
    tab1_factors = factors.model_copy(update={"active_model": "ets", "ets": tab1_ets}) if force_tab1_ets else factors
    # When Tab1 is the recalculate target (force_tab1_ets=False), Tab2-5 shares stay
    # flat via simple MA — the user's growth model only applies to Tab1's total volume.
    tab25_factors = factors if force_tab1_ets else factors.model_copy(update={"active_model": "moving_average"})
    tmv_map      = {scenario_name: {(r[0], r[1]): float(r[-1]) for r in _tmv_train}}
    tab1_mv_data = _build_tab_data(tmv_map, month_range, month_labels, fsi, tab1_factors,
                                   model_start_ym=_model_start_ym, fc_offset=_fc_offset)
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
    # Use _min_from_year so pre-training history appears when FROM DATE is historical,
    # and model training data is still available when FROM DATE is in the forecast period.
    if is_yearly:
        pd_mv   = get_product_distribution_yearly(cur, ta, _min_from_year, train_end_year, None, "payer_volume")
        pd_ms   = get_product_distribution_yearly(cur, ta, _min_from_year, train_end_year, None, "payer_share")
        # Tab 4: payment_type × product (2-level); Tab 5: payment_type × payer × product (3-level)
        pt_mv   = get_payment_type_wise_product_yearly(cur, ta, _min_from_year, train_end_year, None, "payer_volume")
        pt_ms   = get_payment_type_wise_product_yearly(cur, ta, _min_from_year, train_end_year, None, "payer_share")
        ptpp_mv = get_payment_type_payer_product_yearly(cur, ta, _min_from_year, train_end_year, None, "payer_volume")
    else:
        pd_mv   = get_product_distribution(cur, ta, _min_from_year, _min_from_month, train_end_year, train_end_month, None, "payer_volume")
        pd_ms   = get_product_distribution(cur, ta, _min_from_year, _min_from_month, train_end_year, train_end_month, None, "payer_share")
        # Tab 4: payment_type × product (2-level); Tab 5: payment_type × payer × product (3-level)
        pt_mv   = get_payment_type_wise_product(cur, ta, _min_from_year, _min_from_month, train_end_year, train_end_month, None, "payer_volume")
        pt_ms   = get_payment_type_wise_product(cur, ta, _min_from_year, _min_from_month, train_end_year, train_end_month, None, "payer_share")
        ptpp_mv = get_payment_type_payer_product(cur, ta, _min_from_year, _min_from_month, train_end_year, train_end_month, None, "payer_volume")

    # Tab 3: payment_type distribution derived from pt_mv by summing across products
    def _flat_dist_from_2level(rows):
        vol: dict = defaultdict(float)
        for r in rows:
            vol[(r[0], r[1], r[2])] += float(r[-1]) if r[-1] is not None else 0.0
        grand: dict = defaultdict(float)
        for (y, m, pt), v in vol.items():
            grand[(y, m)] += v
        vrows, msrows = [], []
        for key in sorted(vol):
            y, m, pt = key
            v = vol[key]
            vrows.append((y, m, pt, v))
            g = grand[(y, m)]
            msrows.append((y, m, pt, round(v / g * 100, 4) if g else 0.0))
        return vrows, msrows

    _ptd_mv, _ptd_ms = _flat_dist_from_2level(pt_mv)

    # _wide_actual_range is the candidate pool for per-series model training months.
    # Tab 2 (product distribution): series label = product, config key = (sel_payer, product)
    _tab2_mmbl = {
        lbl: _series_model_months(_config_map, sel_payer or "", lbl, _wide_actual_range)
        for lbl in {r[2] for r in pd_mv}
    }
    # Tab 3 (payment_type distribution): series label = payment_type, config key = (payment_type, sel_product)
    _tab3_mmbl = {
        lbl: _series_model_months(_config_map, lbl, sel_product or "", _wide_actual_range)
        for lbl in {r[2] for r in _ptd_mv}
    }
    # Tab 4 (payment_type_product): parent=payment_type r[2], child=product r[3]
    _tab4_mmbp = {
        (r[2], r[3]): _series_model_months(_config_map, r[2], r[3], _wide_actual_range)
        for r in pt_mv
    }

    # TMV forecast values used to scale Tabs 2-5.
    # Always use Tab1's ETS forecast as the TMV multiplier for Tabs 2-5.
    # share-based flow: volume = share% × ETS_TMV; _recompute_all_market_shares then divides
    # by the same ETS_TMV, so recomputed share == forecasted share exactly. Using a different
    # TMV here (e.g. rolling MA) would cause a ratio mismatch and distort displayed shares.
    _tmv_fc = tab1_mv_data.chart.series[0].forecast_values if tab1_mv_data.chart.series else []

    def bflat_mv(rows_mv, rows_ms, label, to_int=False, mmbl=None):
        tab_data = _build_tab_data_from_shares(
            share_series_dict=_rows_to_series(rows_ms, 2, 3),
            vol_series_dict=_rows_to_series(rows_mv, 2, 3),
            month_range=month_range,
            month_labels=month_labels,
            forecast_start_index=fsi,
            factors=tab25_factors,
            tmv_fc=_tmv_fc,
            selected_label=label,
            add_total=True,
            model_months_by_label=mmbl,
            fc_offset=_fc_offset,
        )
        return _fmt_flat(tab_data, month_labels, fsi, to_int=to_int)

    def bflat_ms(rows, label):
        return _fmt_flat(
            _build_tab_data(_rows_to_series(rows, 2, 3), month_range, month_labels, fsi, tab25_factors,
                            selected_label=label, auto_model=auto_model, add_total=True,
                            fc_offset=_fc_offset),
            month_labels, fsi,
        )

    def bhier_mv(rows_mv, rows_ms, parent_lbl, child_lbl, to_int=False, mmbp=None):
        hier_data = _build_hierarchical_tab_data_from_shares(
            rows_ms=rows_ms,
            rows_mv=rows_mv,
            month_range=month_range,
            month_labels=month_labels,
            forecast_start_index=fsi,
            factors=tab25_factors,
            selected_child=child_lbl,
            model_months_by_pair=mmbp,
            fc_offset=_fc_offset,
        )
        return _fmt_hier(hier_data, month_labels, fsi, to_int=to_int,
                         chart_parent_filter=parent_lbl, chart_child_filter=child_lbl)

    def bhier_ms(rows, parent_lbl, child_lbl):
        return _fmt_hier(
            _build_hierarchical_tab_data(rows, month_range, month_labels, fsi, tab25_factors,
                                         selected_parent=parent_lbl or "",
                                         selected_child=child_lbl or "",
                                         auto_model=auto_model, fc_offset=_fc_offset),
            month_labels, fsi, chart_parent_filter=parent_lbl, chart_child_filter=child_lbl,
        )

    # ── Helper: swap parent/child columns in 2-level rows (y, m, parent, child, val) ──
    def _swap_pc(rows):
        return [(r[0], r[1], r[3], r[2]) + tuple(r[4:]) for r in rows]

    # ── Helper: true 3-level hierarchy builder for Tab 5 ─────────────────────
    # ptpp rows: (year[0], month[1], payment_type[2], payer[3], product[4], value[5])
    #
    # Level 1 : r[dim1_col]                    (standalone label, e.g. "Cash")
    # Level 2 : "dim1 - dim2" composite        (e.g. "Cash - GILD", "Medicaid - CVS")
    #            Special: if dim2 == "NA" (Cash payer) → its children collapse up to
    #            become level-2 entries directly under dim1 (no composite label)
    # Level 3 : r[dim3_col], skipped if "NA"   (e.g. CVS/Non-CVS; absent for Cash)
    #
    # Forecasting: proportional share distribution from _tmv_fc using a 6-period
    # trailing average.  Uses the closure variables month_range / month_labels / fsi
    # / _tmv_fc / tab25_factors that are already in scope.
    def _build_tab5_3level(ptpp_rows, dim1_col, dim2_col, dim3_col, to_int=False, as_share=False):
        n     = len(month_range)
        n_fc  = n - fsi
        w     = min(6, fsi)

        # aggregate
        vol3: dict = defaultdict(float)
        for r in ptpp_rows:
            d1, d2, d3 = r[dim1_col], r[dim2_col], r[dim3_col]
            vol3[(r[0], r[1], d1, d2, d3)] += float(r[-1]) if r[-1] is not None else 0.0

        vol2: dict = defaultdict(float)
        vol1: dict = defaultdict(float)
        vol0: dict = defaultdict(float)
        for (y, m, d1, d2, d3), v in vol3.items():
            vol2[(y, m, d1, d2)] += v
            vol1[(y, m, d1)]     += v
            vol0[(y, m)]         += v

        # unique label sets
        all_d1: list      = sorted({d1 for (_, _, d1, d2, d3) in vol3})
        dim2_by_d1: dict  = defaultdict(set)
        dim3_by_d1d2: dict = defaultdict(set)
        for (_, _, d1, d2, d3) in vol3:
            dim2_by_d1[d1].add(d2)
            if d3 != "NA":
                dim3_by_d1d2[(d1, d2)].add(d3)

        # historical vector helper
        def _h(vol, key):
            return [float(vol.get((y, m) + key, 0.0)) for y, m in month_range[:fsi]]

        # proportional share: sum(last-w numerator) / sum(last-w denominator)
        def _sh(num_h, den_h):
            tn = sum(num_h[-w:])
            td = sum(den_h[-w:])
            return tn / td if td else 0.0

        # ── forecast ────────────────────────────────────────────────────────
        gt_h = [float(vol0.get((y, m), 0.0)) for y, m in month_range[:fsi]]

        def _h_pct(vol, key):
            return [
                vol.get((y, m) + key, 0.0) / gt_h[i] * 100 if gt_h[i] else 0.0
                for i, (y, m) in enumerate(month_range[:fsi])
            ]

        l1_fc: dict = {}
        for d1 in all_d1:
            s = _sh(_h(vol1, (d1,)), gt_h)
            l1_fc[d1] = [s * t for t in _tmv_fc] if _tmv_fc else [0.0] * n_fc

        l2_fc: dict = {}
        for d1 in all_d1:
            h1 = _h(vol1, (d1,))
            for d2 in dim2_by_d1[d1]:
                s = _sh(_h(vol2, (d1, d2)), h1)
                l2_fc[(d1, d2)] = [s * v for v in l1_fc[d1]]

        l3_fc: dict = {}
        for (d1, d2), d3_set in dim3_by_d1d2.items():
            h2 = _h(vol2, (d1, d2))
            for d3 in d3_set:
                s = _sh(_h(vol3, (d1, d2, d3)), h2)
                l3_fc[(d1, d2, d3)] = [s * v for v in l2_fc.get((d1, d2), [0.0] * n_fc)]

        # full (history + forecast) value series
        def _full(vol, key, fc_dict):
            if as_share:
                hist   = _h_pct(vol, key)
                fc_val = sum(hist[-w:]) / w if w and hist else 0.0
                return [round(v, 4) for v in hist + [fc_val] * n_fc]
            hist = _h(vol, key)
            fc   = fc_dict.get(key, [0.0] * n_fc)
            vals = hist + list(fc)
            if to_int:
                return [int(round(v)) for v in vals]
            return [round(v, 4) for v in vals]

        # ── build table ──────────────────────────────────────────────────────
        table_rows = []
        for d1 in all_d1:
            l1_vals     = _full(vol1, (d1,), l1_fc)
            children_l2 = []

            for d2 in sorted(dim2_by_d1[d1]):
                if d2 == "NA":
                    # dim2 is payer "NA" (Cash): products become direct level-2 children
                    for d3 in sorted(dim3_by_d1d2.get((d1, d2), set())):
                        children_l2.append({
                            "label":    d3,
                            "values":   _full(vol3, (d1, d2, d3), l3_fc),
                            "children": [],
                        })
                else:
                    lbl2     = f"{d1} - {d2}"
                    d3_set   = sorted(dim3_by_d1d2.get((d1, d2), set()))
                    children_l2.append({
                        "label":  lbl2,
                        "values": _full(vol2, (d1, d2), l2_fc),
                        "children": [
                            {
                                "label":    d3,
                                "values":   _full(vol3, (d1, d2, d3), l3_fc),
                                "children": [],
                            }
                            for d3 in d3_set
                        ],
                    })

            table_rows.append({"label": d1, "values": l1_vals, "children": children_l2})

        # ── build chart (leaf-level series only) ─────────────────────────────
        # No parent-total series — the chart shows only the most granular level.
        # _aggregate_monthly_to_yearly is told to skip parent recomputation for
        # any hierarchy whose monthly chart has no parent-labelled series.
        #
        # Leaf label rules:
        # • d3 exists (non-NA): "d1 - d3" if d2=="NA" else "d1 - d2 - d3"
        # • d3 absent (all NA, Cash in sub-views 2/3): "d1 - d2" (level-2)
        chart_series: list = []

        for d1 in all_d1:
            for d2 in sorted(dim2_by_d1[d1]):
                d3_set = sorted(dim3_by_d1d2.get((d1, d2), set()))
                if d3_set:
                    for d3 in d3_set:
                        lbl = f"{d1} - {d3}" if d2 == "NA" else f"{d1} - {d2} - {d3}"
                        if as_share:
                            h_vals = _h_pct(vol3, (d1, d2, d3))
                            fc_val = sum(h_vals[-w:]) / w if w and h_vals else 0.0
                            fc     = [round(fc_val, 4)] * n_fc
                        else:
                            h_vals = _h(vol3, (d1, d2, d3))
                            fc     = list(l3_fc.get((d1, d2, d3), [0.0] * n_fc))
                        chart_series.append({
                            "label":    lbl,
                            "history":  [round(v, 4) for v in h_vals],
                            "forecast": [round(v, 4) for v in fc],
                        })
                else:
                    # No valid d3 (Cash with no sub-payer): fall back to level-2
                    lbl = d1 if d2 == "NA" else f"{d1} - {d2}"
                    if as_share:
                        h_vals = _h_pct(vol2, (d1, d2))
                        fc_val = sum(h_vals[-w:]) / w if w and h_vals else 0.0
                        fc     = [round(fc_val, 4)] * n_fc
                    else:
                        h_vals = _h(vol2, (d1, d2))
                        fc     = list(l2_fc.get((d1, d2), [0.0] * n_fc))
                    chart_series.append({
                        "label":    lbl,
                        "history":  [round(v, 4) for v in h_vals],
                        "forecast": [round(v, 4) for v in fc],
                    })

        return {
            "chart": {
                "months":               month_labels,
                "forecast_start_index": fsi,
                "series":               chart_series,
            },
            "table": {
                "type": "hierarchy",
                "rows": table_rows,
            },
        }

    market_analysis = {
        "total_market_volume": {
            "payer_volume": _fmt_flat(tab1_mv_data, month_labels, fsi, to_int=True),
            "payer_share":  tab1_ms,
        },
        "product_distribution": {
            "payer_volume": bflat_mv(pd_mv,  pd_ms,  tab2_label, to_int=True, mmbl=_tab2_mmbl),
            "payer_share":  bflat_ms(pd_ms,  tab2_label),
        },
        "payment_type_distribution": {
            "payer_volume": bflat_mv(_ptd_mv, _ptd_ms, None, to_int=True, mmbl=_tab3_mmbl),
            "payer_share":  bflat_ms(_ptd_ms, None),
        },
        # Tab 4: payment_type × product (2-level); two orderings.
        # Each sub-view contains payer_volume and payer_share as metric keys.
        "payment_type_product": {
            "payment_type_product": {
                "payer_volume": bhier_mv(pt_mv,           pt_ms,          None,       tab2_label, to_int=True, mmbp=_tab4_mmbp),
                "payer_share":  bhier_ms(pt_ms,           None,           tab2_label),
            },
            "product_payment_type": {
                "payer_volume": bhier_mv(_swap_pc(pt_mv), _swap_pc(pt_ms), tab2_label, None,       to_int=True),
                "payer_share":  bhier_ms(_swap_pc(pt_ms), tab2_label,      None),
            },
        },
        # Tab 5: three 3-level views of payment_type × payer × product.
        # Each sub-view contains payer_volume and payer_share as metric keys.
        "payment_type_payer_product": {
            "payment_type_payer_product": {
                "payer_volume": _build_tab5_3level(ptpp_mv, 2, 3, 4, to_int=True),
                "payer_share":  _build_tab5_3level(ptpp_mv, 2, 3, 4, as_share=True),
            },
            "payment_type_product_payer": {
                "payer_volume": _build_tab5_3level(ptpp_mv, 2, 4, 3, to_int=True),
                "payer_share":  _build_tab5_3level(ptpp_mv, 2, 4, 3, as_share=True),
            },
            "product_payment_type_payer": {
                "payer_volume": _build_tab5_3level(ptpp_mv, 4, 2, 3, to_int=True),
                "payer_share":  _build_tab5_3level(ptpp_mv, 4, 2, 3, as_share=True),
            },
        },
        "event_management": {},
    }

    # Recompute market_share from market_volume for Tabs 1-3 so all flat tabs are consistent
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

    def _agg_metric(data):
        """Aggregate a single {chart, table} monthly metric dict to yearly."""
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

            def _agg_node(node):
                children = node.get("children", [])
                if not children:
                    cv = node.get("values", [])
                    _, ch = _group_sum(hist_months, cv[:fsi])
                    _, cf = _group_sum(fc_months,   cv[fsi:])
                    return {"label": node["label"], "values": ch + cf, "children": []}
                new_ch = [_agg_node(c) for c in children]
                pv = [
                    sum(c["values"][i] for c in new_ch if i < len(c["values"]))
                    for i in range(n_yrs)
                ]
                return {"label": node["label"], "values": pv, "children": new_ch}

            for r in table.get("rows", []):
                plabels.add(r["label"])
            new_rows  = [_agg_node(r) for r in table.get("rows", [])]
            new_table = {"type": "hierarchy", "rows": new_rows}

            monthly_series_labels = {s["label"] for s in chart.get("series", [])}
            child_ser_map = {}
            for s in chart.get("series", []):
                if s["label"] in plabels:
                    continue
                _, h = _group_sum(hist_months, s.get("history",  []))
                _, f = _group_sum(fc_months,   s.get("forecast", []))
                ns = {"label": s["label"], "history": h, "forecast": f}
                parent = next((pl for pl in plabels if s["label"].startswith(f"{pl} - ")), None)
                if parent:
                    child_ser_map.setdefault(parent, []).append(ns)
                new_series.append(ns)

            for pl in plabels:
                if pl not in monthly_series_labels:
                    continue
                ch_ser = child_ser_map.get(pl, [])
                n_h = max((len(s.get("history",  [])) for s in ch_ser), default=0)
                n_f = max((len(s.get("forecast", [])) for s in ch_ser), default=0)
                new_series.insert(0, {
                    "label":    pl,
                    "history":  [_vsum(ch_ser, "history",  i) for i in range(n_h)],
                    "forecast": [_vsum(ch_ser, "forecast", i) for i in range(n_f)],
                })

        return {
            "chart": {"months": yearly_months, "forecast_start_index": yearly_fsi, "series": new_series},
            "table": new_table,
        }

    ma_yearly = {}
    for tab_key, metrics in ma_monthly.items():
        ma_yearly[tab_key] = {}
        for level2_key, level2_data in metrics.items():
            if "chart" in level2_data or "table" in level2_data:
                # Standard metric: level2_data is {chart, table}
                ma_yearly[tab_key][level2_key] = _agg_metric(level2_data)
            else:
                # Sub-view: level2_data is {metric_key: {chart, table}}
                ma_yearly[tab_key][level2_key] = {
                    mk: _agg_metric(md) for mk, md in level2_data.items()
                }

    # Re-scale flat and hierarchical market_volume tabs to match yearly TMV
    # (removes residual int() truncation drift accumulated from 12-month summation)
    tmv_chart = (ma_yearly.get("total_market_volume", {})
                          .get("payer_volume", {})
                          .get("chart", {}))
    yearly_fsi_tmv = tmv_chart.get("forecast_start_index", 0)
    tmv_ser        = tmv_chart.get("series", [{}])[0] if tmv_chart.get("series") else {}
    tmv_fc_yearly  = tmv_ser.get("forecast", [])

    for tab_key in ("product_distribution", "payment_type_distribution"):
        mv = ma_yearly.get(tab_key, {}).get("payer_volume", {})
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
        mv = ma_yearly.get(tab_key, {}).get("payer_volume", {})
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

    # Round all market_volume values to int after scaling (history and forecast)
    for tab_key, metrics in ma_yearly.items():
        mv = metrics.get("payer_volume", {})
        if not mv:
            continue
        for s in mv.get("chart", {}).get("series", []):
            s["history"]  = [int(round(v)) for v in s.get("history",  [])]
            s["forecast"] = [int(round(v)) for v in s.get("forecast", [])]
        for r in mv.get("table", {}).get("rows", []):
            r["values"] = [int(round(v)) for v in r["values"]]
            for c in r.get("children", []):
                c["values"] = [int(round(v)) for v in c["values"]]

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
        for level2_key, level2_data in metrics.items():
            if "chart" in level2_data or "table" in level2_data:
                # Standard metric
                merged[tab_key][level2_key] = {
                    "monthly": level2_data,
                    "yearly":  ma_yearly.get(tab_key, {}).get(level2_key, {}),
                }
            else:
                # Sub-view: level2_data = {metric_key: {chart, table}}
                yearly_sv = ma_yearly.get(tab_key, {}).get(level2_key, {})
                merged[tab_key][level2_key] = {
                    mk: {
                        "monthly": md,
                        "yearly":  yearly_sv.get(mk, {}),
                    }
                    for mk, md in level2_data.items()
                }

    return merged, tab1_ets


def _split_by_granularity(ma_nested: dict):
    """Split {tab: {key: {monthly: ..., yearly: ...}}} into two flat dicts.
    Handles sub-view tabs where key maps to {metric: {monthly, yearly}}."""
    monthly, yearly = {}, {}
    for tab, metrics in ma_nested.items():
        monthly[tab], yearly[tab] = {}, {}
        for key, grans in metrics.items():
            if "monthly" in grans or "yearly" in grans:
                # Standard metric
                monthly[tab][key] = grans.get("monthly", {})
                yearly[tab][key]  = grans.get("yearly", {})
            else:
                # Sub-view: grans = {metric: {monthly, yearly}}
                monthly[tab][key], yearly[tab][key] = {}, {}
                for mk, mg in grans.items():
                    monthly[tab][key][mk] = mg.get("monthly", {})
                    yearly[tab][key][mk]  = mg.get("yearly", {})
    return monthly, yearly


def _merge_granularities(ma_monthly: dict, ma_yearly: dict) -> dict:
    """Merge two flat dicts into {tab: {key: {monthly: ..., yearly: ...}}}.
    Handles sub-view tabs where key maps to {metric: {chart, table}}."""
    merged = {}
    for tab in ma_monthly:
        merged[tab] = {}
        for key in ma_monthly[tab]:
            val = ma_monthly[tab][key]
            if "chart" in val or "table" in val:
                # Standard metric
                merged[tab][key] = {
                    "monthly": val,
                    "yearly":  ma_yearly.get(tab, {}).get(key, {}),
                }
            else:
                # Sub-view: val = {metric: {chart, table}}
                yearly_sv = ma_yearly.get(tab, {}).get(key, {})
                merged[tab][key] = {
                    mk: {
                        "monthly": mv,
                        "yearly":  yearly_sv.get(mk, {}),
                    }
                    for mk, mv in val.items()
                }
    return merged


def _recompute_all_market_shares_nested(market_analysis: dict) -> dict:
    """Wrapper of _recompute_all_market_shares for the nested monthly/yearly format."""
    ma_monthly, ma_yearly = _split_by_granularity(market_analysis)
    ma_monthly = _recompute_all_market_shares(ma_monthly)
    ma_yearly  = _recompute_all_market_shares(ma_yearly)
    return _merge_granularities(ma_monthly, ma_yearly)


# ---------------------------------------------------------------------------
# Helper: load config or fall back to DB defaults
# ---------------------------------------------------------------------------

def _load_config(cur, ta: str, payment_type: str = None, payer: str = None, brand: str = None) -> dict:
    """
    Returns config dict for the given (ta, payment_type, payer, brand).
    Falls back to any saved config for the TA, then to 5-year defaults.
    """
    if payment_type is not None and payer is not None and brand is not None:
        row = get_liver_config_by_payment_type_payer_brand(cur, ta, payment_type, payer, brand)
        if row:
            return row[0]

    # Second chance: any config saved for this TA (pick the one with the
    # furthest forecast end so forecast_periods is never accidentally truncated).
    all_cfgs = get_liver_configs_for_ta(cur, ta)
    if all_cfgs:
        best_cfg, best_end = None, -1
        for row in all_cfgs:
            cfg = row[3] if isinstance(row[3], dict) else {}
            te  = cfg.get("train_end_date", "")
            fp  = int(cfg.get("forecast_periods", 0))
            try:
                te_y, te_m = _parse_ym(te)
                end_ym = te_y * 12 + te_m + fp
                if end_ym > best_end:
                    best_end = end_ym
                    best_cfg = cfg
            except Exception:
                pass
        if best_cfg:
            return best_cfg

    # Last resort: 5 years back from max available date, 24-month forecast
    _, _, max_year, max_month = get_transaction_date_range(cur)
    max_dt   = date_type(max_year, max_month, 1)
    start_dt = _add_months(max_dt, -60)
    return {
        "ta_name":           ta,
        "train_start_date":  start_dt.isoformat(),
        "train_end_date":    max_dt.isoformat(),
        "model_granularity": "monthly",
        "forecast_periods":  24,
    }


# ---------------------------------------------------------------------------
# Get filters
# ---------------------------------------------------------------------------

def get_liver_filters(ta: str = "HCV") -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        payers   = get_payers(cur)
        products = get_products(cur)

        # START of available_months: earliest data in transaction_data (no TA filter,
        # same source used in save_liver_configuration for validation).
        _dt_range = get_transaction_date_range(cur)
        if _dt_range and _dt_range[0]:
            avail_start_year, avail_start_month = _dt_range[0], _dt_range[1]
        else:
            avail_start_year, avail_start_month = 2020, 1

        # END of available_months: latest forecast end across ALL configs for this TA.
        all_cfgs = get_liver_configs_for_ta(cur, ta)
        avail_end_ym = None
        for _row in all_cfgs:
            _cfg = _row[3] if isinstance(_row[3], dict) else {}
            _te = _cfg.get("train_end_date", "")
            _fp = int(_cfg.get("forecast_periods", 24))
            try:
                if _te:
                    _ey, _em = _parse_ym(_te)
                    _fe = _add_months(date_type(_ey, _em, 1), _fp)
                    _feym = _fe.year * 100 + _fe.month
                    if avail_end_ym is None or _feym > avail_end_ym:
                        avail_end_ym = _feym
            except Exception:
                pass

        if avail_end_ym is None:
            # Fallback: DB end + 24 months
            if _dt_range and _dt_range[2]:
                _fe = _add_months(date_type(_dt_range[2], _dt_range[3], 1), 24)
                avail_end_ym = _fe.year * 100 + _fe.month
            else:
                avail_end_ym = 202712

        avail_end_year  = avail_end_ym // 100
        avail_end_month = avail_end_ym  % 100

        # selected_filter: start = first DB month, end = widest forecast end
        from_date = date_type(avail_start_year, avail_start_month, 1).isoformat()
        to_date   = date_type(avail_end_year,   avail_end_month,   1).isoformat()

        all_months  = _generate_months(avail_start_year, avail_start_month,
                                       avail_end_year,   avail_end_month)
        date_labels = [_month_label(y, m) for y, m in all_months]

        # Load last saved filter state for this TA; fall back to defaults
        try:
            saved_filter = load_filter_state(cur, ta)
        except Exception as _lfe:
            print(f"[get_liver_filters] load_filter_state skipped: {_lfe}")
            saved_filter = None
        selected_filter = saved_filter if saved_filter else {
            "payer":      payers[0] if payers else None,
            "product":    products[0] if products else None,
            "start_date": from_date,
            "end_date":   to_date,
        }

        return {
            "ta_name":          ta,
            "payers":           payers,
            "products":         products,
            "available_months": date_labels,
            "selected_filter":  selected_filter,
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
                           payment_type=_first(payload.payer),
                           brand=_first(payload.brand))
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = _resolve_forecast_periods(
            payload.to_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity      = cfg.get("model_granularity", "monthly")

        active_scenario   = payload.scenario or "Base"
        all_scenario_names = get_scenarios(cur)
        # "Base" is now a real persisted row (see the Base-persist block below),
        # so it must be excluded here the same way _persist_and_respond /
        # _build_scenario_response already do -- otherwise it's prepended AND
        # present in all_scenario_names, listing "Base" twice.
        if "Base" in all_scenario_names:
            all_scenario_names.remove("Base")
        available_scenarios = ["Base"] + all_scenario_names

        saved_market_analysis = None
        saved_factors_raw     = None

        # For non-Base scenarios load both factors AND the saved chart_data.
        # apply_liver_filters shows saved values (the scenario's committed state);
        # recalculate_liver is the action that recomputes with new factor inputs.
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
            # Non-Base with saved chart data: return committed values, clipped to the
            # user's requested date window so the chart axis starts at from_date not at
            # the DB-stored wide start (e.g. Apr-20).
            saved_market_analysis = _normalize_ma_keys(saved_market_analysis)
            saved_market_analysis = _clip_ma_to_from_date(saved_market_analysis, from_year, from_month)
            market_analysis = _recompute_all_market_shares_nested(saved_market_analysis)
            _ets_raw = (saved_factors_raw or {}).get("ets", {})
            tab1_ets = EtsParams(
                alpha=float(_ets_raw.get("alpha", 0.30)),
                beta=float(_ets_raw.get("beta", 0.20)),
                gamma=float(_ets_raw.get("gamma", 0.98)),
            )
        else:
            # Base or non-Base with no saved chart data: freshly compute.
            market_analysis, tab1_ets = _build_market_analysis_both_granularities(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, factors,
                sel_payer=_first(payload.payer), sel_product=_first(payload.brand),
                scenario_name=payload.scenario,
            )
            market_analysis = _recompute_all_market_shares_nested(market_analysis)

        _traj_start = _add_months(date_type(train_end_year, train_end_month, 1), 1).isoformat()
        if active_scenario != "Base" and saved_factors_raw:
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
            base_full_ma = market_analysis

            # Persist this live Base computation the same way a real scenario
            # gets saved (see _persist_and_respond), so Market Events can read
            # it back as a stored snapshot instead of independently
            # re-implementing Model Input's own forecasting logic (frozen-
            # remainder shares, per-combo training windows, etc.) — two
            # separate implementations of the same math kept drifting out of
            # sync with each other, which is what caused the BASE-view
            # mismatches between the two screens. Base is never user-editable
            # here, so it's always safe to overwrite with the freshest
            # computation.
            #
            # Deliberately recomputed at the TRUE earliest transaction month
            # for this TA (not the config's train_start_date, and not
            # whatever narrower from/to date the user currently has applied
            # in Model Input's own display filter). Two distinct reasons:
            #
            # 1. `market_analysis` as originally computed above is scoped to
            #    payload.from_date/to_date -- if the persisted snapshot only
            #    covered that narrow window, Market Events could never show/
            #    filter back to months outside it.
            #
            # 2. Using the config's train_start_date itself (an earlier
            #    version of this fix) was ALSO wrong: _build_all_tabs_both_metrics
            #    only includes real pre-training data when the from_year it's
            #    given is EARLIER than the config's own training start --
            #    see its "_min_from_year = min(from_year, _wide_from_year)"
            #    comment. Passing the training start itself as from_year makes
            #    that min() collapse to the training start, so every month
            #    genuinely before it (e.g. real transaction_data from Apr-2020
            #    when training was configured to start Sep-2022) came back as
            #    0 instead of its real historical value, even though that data
            #    exists and the function already supports showing it. Training
            #    start is a MODEL-FITTING boundary (where ETS parameters get
            #    estimated from), not a "data before this doesn't count"
            #    boundary -- the persisted Base snapshot should carry every
            #    actual historical month regardless of it.
            #
            # Best-effort: a failure here must not break the live Model Input response.
            try:
                _txn_months = get_transaction_distinct_months(cur, payload.ta)
                if _txn_months:
                    wide_from_year, wide_from_month = _txn_months[0]
                else:
                    wide_from_year, wide_from_month = _parse_ym(cfg["train_start_date"])
                # forecast_periods from the currently-selected (payer, brand)
                # config alone isn't necessarily the widest available end --
                # a different combo's config may forecast further out.
                # Extend (never shorten) to match that widest end, the same
                # "available_months" concept the date-range dropdown already
                # uses, so what's persisted for Base isn't capped by whichever
                # combo happens to be selected right now.
                wide_forecast_periods = _extend_forecast_periods_to_widest_end(
                    cur, payload.ta, train_end_year, train_end_month, int(cfg["forecast_periods"])
                )
                persist_ma, _ = _build_market_analysis_both_granularities(
                    cur, payload.ta, wide_from_year, wide_from_month,
                    train_end_year, train_end_month, wide_forecast_periods, factors,
                    sel_payer=_first(payload.payer), sel_product=_first(payload.brand),
                    scenario_name=payload.scenario,
                )
                persist_ma = _recompute_all_market_shares_nested(persist_ma)
                wide_end_date = _add_months(
                    date_type(train_end_year, train_end_month, 1), wide_forecast_periods
                ).isoformat()

                wide_start_date = date_type(wide_from_year, wide_from_month, 1).isoformat()

                save_scenario(
                    cur,
                    scenario_name="Base",
                    ta=payload.ta,
                    payer=_first(payload.payer) or "",
                    product=_first(payload.brand) or "",
                    from_date=wide_start_date,
                    to_date=wide_end_date,
                    chart_data={"market_analysis": persist_ma},
                    factors=response_factors,
                )
                base_snapshot = extract_snapshot_from_market_analysis(persist_ma)
                if base_snapshot:
                    save_market_events_scenario(cur, "Base", base_snapshot)
                conn.commit()
            except Exception as _base_persist_err:
                conn.rollback()
                print(f"[liver] Base snapshot persist skipped: {_base_persist_err}")
        else:
            base_factors = _estimate_default_factors(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            base_full_ma, _ = _build_market_analysis_both_granularities(
                cur, payload.ta, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, base_factors,
                scenario_name="Base",
            )

        def _inactive_stub(sc_name):
            # Always prefer DB-persisted data — it is stable regardless of the
            # current date filter. Clip to the user's from_date so the shared chart
            # axis (derived from the active scenario) and the inactive stubs all start
            # at the same month.  Without clipping, a DB-stored wide snapshot (Apr-20)
            # causes the X-axis to drift left whenever an inactive scenario's months
            # array is longer than the active scenario's clipped months.
            cd     = all_saved_cd.get(sc_name, {})
            raw_ma = _normalize_ma_keys(cd.get("market_analysis", {}))
            if raw_ma:
                return {"market_analysis": _clip_ma_to_from_date(raw_ma, from_year, from_month)}
            # Fallback for Base when it has never been persisted yet
            if sc_name == "Base":
                return {"market_analysis": base_full_ma}  # freshly computed from from_year/from_month
            return {"market_analysis": {}}

        scenarios = {
            sc: (
                {"factors": response_factors, "market_analysis": market_analysis}
                if sc == active_scenario
                else _inactive_stub(sc)
            )
            for sc in available_scenarios
        }

        # available_months: full DB range (same no-TA-filter source used for
        # config validation) → latest forecast end across all configs.
        _dt_range_av = get_transaction_date_range(cur)
        if _dt_range_av and _dt_range_av[0]:
            _av_sy, _av_sm = _dt_range_av[0], _dt_range_av[1]
        else:
            _av_sy, _av_sm = from_year, from_month

        _all_cfgs_av = get_liver_configs_for_ta(cur, payload.ta)
        _av_end_ym = None
        for _r in _all_cfgs_av:
            _c = _r[2] if isinstance(_r[2], dict) else {}
            _te, _fp2 = _c.get("train_end_date", ""), int(_c.get("forecast_periods", 24))
            try:
                if _te:
                    _ey, _em = _parse_ym(_te)
                    _fe2 = _add_months(date_type(_ey, _em, 1), _fp2)
                    _feym2 = _fe2.year * 100 + _fe2.month
                    if _av_end_ym is None or _feym2 > _av_end_ym:
                        _av_end_ym = _feym2
            except Exception:
                pass
        if _av_end_ym is None:
            _fc_end_dt = _add_months(date_type(train_end_year, train_end_month, 1), forecast_periods)
            _av_end_ym = _fc_end_dt.year * 100 + _fc_end_dt.month
        _av_ey, _av_em = _av_end_ym // 100, _av_end_ym % 100
        _avail_all = _generate_months(_av_sy, _av_sm, _av_ey, _av_em)
        available_months = [_month_label(y, m) for y, m in _avail_all]

        filter_to_save = {
            "payer":      _first(payload.payer),
            "product":    _first(payload.brand),
            "start_date": payload.from_date,
            "end_date":   end_date,
            "scenario":   active_scenario,
        }
        try:
            save_filter_state(cur, payload.ta, filter_to_save)
            conn.commit()
        except Exception as _fe:
            conn.rollback()
            print(f"[apply_liver_filters] filter state save skipped: {_fe}")

        return {
            "ta_name":            payload.ta,
            "selected_filter":    filter_to_save,
            "available_months":   available_months,
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
    market     = sf.payer
    product    = sf.product
    model_type = payload.model_type.lower()

    from_year, from_month = _parse_ym(from_date)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cfg = _load_config(cur, payload.ta_name, payment_type=market, brand=product)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        forecast_periods = _resolve_forecast_periods(
            sf.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity      = cfg.get("model_granularity", "monthly")

        to_month_safe = train_end_month if granularity != "yearly" else 1
        _dt_dt        = datetime(train_end_year, to_month_safe, 1) + relativedelta(months=1)
        default_traj  = date_type(_dt_dt.year, _dt_dt.month, 1).isoformat()

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
        # See apply_liver_filters: "Base" is now a real persisted row, so it
        # must be excluded here too or it's listed twice.
        if "Base" in all_scenario_names:
            all_scenario_names.remove("Base")
        available_scenarios = ["Base"] + all_scenario_names

        # Tab1 only changes when the user explicitly recalculates total_market_volume.
        # For all other tabs the projection runs on share only — Tab1 stays ETS.
        _force_ets = payload.selected_tab.lower() != "total_market_volume"

        market_analysis, tab1_ets = _build_market_analysis_both_granularities(
            cur, payload.ta_name, from_year, from_month,
            train_end_year, train_end_month, forecast_periods, factors,
            sel_payer=market, sel_product=product,
            force_tab1_ets=_force_ets,
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
            base_full_ma_rc = market_analysis
        else:
            _base_f = _estimate_default_factors(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, granularity,
            )
            base_full_ma_rc, _ = _build_market_analysis_both_granularities(
                cur, payload.ta_name, from_year, from_month,
                train_end_year, train_end_month, forecast_periods, _base_f,
                scenario_name="Base",
            )

        def _inactive_stub_rc(sc_name):
            if sc_name == "Base":
                return {"market_analysis": base_full_ma_rc}
            cd     = all_saved_cd_rc.get(sc_name, {})
            raw_ma = _normalize_ma_keys(cd.get("market_analysis", {}))
            return {"market_analysis": raw_ma}

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
                "payer":      market,
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
    - product_distribution / payer_distribution → each row / total_volume * 100
    - payer_product / product_payer (hierarchical) → child / parent_total * 100
    """
    tmv_rows = (
        market_analysis.get("total_market_volume", {})
        .get("payer_volume", {})
        .get("table", {})
        .get("rows", [])
    )
    total_vals = tmv_rows[0].get("values", []) if tmv_rows else []
    n = len(total_vals)

    tmv_chart  = (
        market_analysis.get("total_market_volume", {})
        .get("payer_volume", {})
        .get("chart", {})
    )
    fsi = tmv_chart.get("forecast_start_index", 0)

    # ── Tab 1: always 100 % ───────────────────────────────────────────────
    tmv_ms = market_analysis.get("total_market_volume", {}).get("payer_share", {})
    if tmv_ms:
        for r in tmv_ms.get("table", {}).get("rows", []):
            r["values"] = [100.0] * n
        for s in tmv_ms.get("chart", {}).get("series", []):
            s["history"]  = [100.0] * fsi
            s["forecast"] = [100.0] * (n - fsi)

    # ── Flat distribution tabs (2, 3) ─────────────────────────────────────
    for tab in ("product_distribution", "payment_type_distribution"):
        if tab not in market_analysis:
            continue
        mv_data = market_analysis[tab].get("payer_volume", {})
        ms_data = market_analysis[tab].get("payer_share", {})
        if not ms_data:
            continue

        ms_rows   = ms_data.setdefault("table", {}).setdefault("rows", [])
        ms_series = ms_data.setdefault("chart", {}).setdefault("series", [])
        ms_row_map = {r.get("label", ""): r for r in ms_rows}
        ms_ser_map = {s.get("label", ""): s for s in ms_series}

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
            else:
                # Brand-new product/payer (e.g. one added on the fly via
                # Manage Products, never seen here before) -- its volume
                # row already exists (added by market_events_service.py's
                # own sync), but there's no share row for it yet. Add one
                # instead of silently leaving it volume-only.
                new_row = {"label": lbl, "values": ms_vals}
                ms_rows.append(new_row)
                ms_row_map[lbl] = new_row
            if lbl in ms_ser_map:
                ms_ser_map[lbl]["history"]  = ms_vals[:fsi]
                ms_ser_map[lbl]["forecast"] = ms_vals[fsi:]
            else:
                new_series = {"label": lbl, "history": ms_vals[:fsi], "forecast": ms_vals[fsi:]}
                ms_series.append(new_series)
                ms_ser_map[lbl] = new_series

    # ── Hierarchical cross-tabs (4, 5): child / sum(children) * 100 ─────────
    for tab in ("payer_product", "product_payer"):
        if tab not in market_analysis:
            continue
        mv_data = market_analysis[tab].get("payer_volume", {})
        ms_data = market_analysis[tab].get("payer_share", {})
        if not ms_data:
            continue

        ms_rows      = ms_data.setdefault("table", {}).setdefault("rows", [])
        ms_series    = ms_data.setdefault("chart", {}).setdefault("series", [])
        ms_hier_map  = {r.get("label", ""): r for r in ms_rows}
        ms_chart_map = {s.get("label", ""): s for s in ms_series}

        for mv_row in mv_data.get("table", {}).get("rows", []):
            parent_lbl = mv_row.get("label", "")
            children   = mv_row.get("children", [])
            ms_parent  = ms_hier_map.get(parent_lbl)

            if not children:
                # "Total" header row — set share to 100 so it's always consistent
                if ms_parent:
                    ms_parent["values"] = [100.0] * n
                continue

            if ms_parent is None:
                # Brand-new parent (product or payer) with no existing share
                # row at all -- its volume row already exists, but there's
                # nowhere for its (or its children's) share to land. Add one
                # instead of silently leaving it volume-only.
                ms_parent = {"label": parent_lbl, "values": [], "children": []}
                ms_rows.append(ms_parent)
                ms_hier_map[parent_lbl] = ms_parent

            # Derive length and per-period column sum directly from children
            # to avoid rounding drift when parent_vals used to_int=True
            hier_n = max((len(c.get("values", [])) for c in children), default=0)
            child_col_sums = [
                sum(float(c["values"][i]) for c in children if i < len(c.get("values", [])))
                for i in range(hier_n)
            ]

            ms_parent["values"] = [100.0] * hier_n
            ms_children  = ms_parent.setdefault("children", [])
            ms_child_map = {c.get("label", ""): c for c in ms_children}

            for child in children:
                child_lbl  = child.get("label", "")
                child_vals = child.get("values", [])
                child_ms   = [
                    round(float(child_vals[i]) / child_col_sums[i] * 100, 4)
                    if i < len(child_vals) and i < hier_n and child_col_sums[i] != 0
                    else 0.0
                    for i in range(hier_n)
                ]
                if child_lbl in ms_child_map:
                    ms_child_map[child_lbl]["values"] = child_ms
                else:
                    new_child = {"label": child_lbl, "values": child_ms}
                    ms_children.append(new_child)
                    ms_child_map[child_lbl] = new_child
                chart_key = f"{parent_lbl} - {child_lbl}"
                if chart_key in ms_chart_map:
                    ms_chart_map[chart_key]["history"]  = child_ms[:fsi]
                    ms_chart_map[chart_key]["forecast"] = child_ms[fsi:]
                else:
                    new_series = {"label": chart_key, "history": child_ms[:fsi], "forecast": child_ms[fsi:]}
                    ms_series.append(new_series)
                    ms_chart_map[chart_key] = new_series

    # ── Sub-view cross-tabs (Tab 4): each sub-view is a 2-level hierarchy ────
    for tab in ("payment_type_product",):
        if tab not in market_analysis:
            continue
        for subview_data in market_analysis[tab].values():
            mv_data = subview_data.get("payer_volume", {})
            ms_data = subview_data.get("payer_share", {})
            if not ms_data or not mv_data:
                continue

            ms_rows      = ms_data.setdefault("table", {}).setdefault("rows", [])
            ms_series    = ms_data.setdefault("chart", {}).setdefault("series", [])
            ms_hier_map  = {r.get("label", ""): r for r in ms_rows}
            ms_chart_map = {s.get("label", ""): s for s in ms_series}

            for mv_row in mv_data.get("table", {}).get("rows", []):
                parent_lbl = mv_row.get("label", "")
                children   = mv_row.get("children", [])
                ms_parent  = ms_hier_map.get(parent_lbl)

                if not children:
                    if ms_parent:
                        ms_parent["values"] = [100.0] * n
                    continue

                if ms_parent is None:
                    ms_parent = {"label": parent_lbl, "values": [], "children": []}
                    ms_rows.append(ms_parent)
                    ms_hier_map[parent_lbl] = ms_parent

                hier_n = max((len(c.get("values", [])) for c in children), default=0)
                child_col_sums = [
                    sum(float(c["values"][i]) for c in children if i < len(c.get("values", [])))
                    for i in range(hier_n)
                ]
                ms_parent["values"] = [100.0] * hier_n
                ms_children  = ms_parent.setdefault("children", [])
                ms_child_map = {c.get("label", ""): c for c in ms_children}

                for child in children:
                    child_lbl  = child.get("label", "")
                    child_vals = child.get("values", [])
                    child_ms   = [
                        round(float(child_vals[i]) / child_col_sums[i] * 100, 4)
                        if i < len(child_vals) and i < hier_n and child_col_sums[i] != 0
                        else 0.0
                        for i in range(hier_n)
                    ]
                    if child_lbl in ms_child_map:
                        ms_child_map[child_lbl]["values"] = child_ms
                    else:
                        new_child = {"label": child_lbl, "values": child_ms}
                        ms_children.append(new_child)
                        ms_child_map[child_lbl] = new_child
                    chart_key = f"{parent_lbl} - {child_lbl}"
                    if chart_key in ms_chart_map:
                        ms_chart_map[chart_key]["history"]  = child_ms[:fsi]
                        ms_chart_map[chart_key]["forecast"] = child_ms[fsi:]
                    else:
                        new_ser = {"label": chart_key, "history": child_ms[:fsi], "forecast": child_ms[fsi:]}
                        ms_series.append(new_ser)
                        ms_chart_map[chart_key] = new_ser

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

        wide = _compute_wide_chart_data(cur, ta, flt, factors)
        # Store the payload's market_analysis (filter window with user edits) for the
        # chart. from_date/to_date use the wide range so activate knows the full span.
        store_from = wide.get("_wide_start") or flt.start_date
        store_to   = wide.get("_wide_end")   or flt.end_date

        # Splice: pre-filter months from wide (full history), filter-window from payload
        # (preserves user's table edits). Falls back to payload alone if wide failed.
        spliced_ma = _prepend_wide_months(
            wide.get("market_analysis", {}), payload.market_analysis, flt.start_date
        ) if wide.get("market_analysis") else payload.market_analysis

        save_scenario(
            cur,
            scenario_name=name,
            ta=ta,
            payer=flt.payer or "",
            product=flt.product or "",
            from_date=store_from,
            to_date=store_to,
            chart_data={"market_analysis": spliced_ma},
            factors=factors,
        )

        # Sync market_events from the wide recompute (full date range Apr 2020+),
        # not from the payload which only covers the user's filter window.
        try:
            me_snap = _splice_snapshots(
                extract_snapshot_from_market_analysis(wide.get("market_analysis", {})),
                extract_snapshot_from_market_analysis(payload.market_analysis),
                flt.start_date,
            )
            if me_snap:
                save_market_events_scenario(cur, name, me_snap)
        except Exception as _sync_err:
            print(f"[liver] market_events snapshot sync skipped: {_sync_err}")

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
        cfg = _load_config(cur, ta, payment_type=flt.payer or None, brand=flt.product or None)
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
        def _inactive_stub(sc_name):
            if sc_name == "Base":
                return {"market_analysis": _base_ma}
            cd     = saved.get(sc_name, {})
            raw_ma = _normalize_ma_keys(cd.get("market_analysis", {}))
            return {"market_analysis": raw_ma}

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
    """Shared response builder: active scenario gets full data, others get full market_analysis from DB."""
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
    scenarios = {}
    for sc in available_scenarios:
        if sc == name:
            # Return the payload's market_analysis (the user's filter-window view with
            # any table edits). The DB stores the full wide range via _prepend_wide_months;
            # the response only needs to cover the visible filter window.
            scenarios[sc] = {"factors": factors, "market_analysis": market_analysis}
        elif sc == "Base":
            scenarios[sc] = {"market_analysis": _base_ma}
        else:
            cd     = saved.get(sc, {})
            raw_ma = _normalize_ma_keys(cd.get("market_analysis", {}))
            scenarios[sc] = {"market_analysis": raw_ma}

    return {
        "message": "Scenario saved successfully",
        "available_scenarios": available_scenarios,
        "active_scenario": name,
        "scenarios": scenarios,
    }


def _splice_snapshots(wide_snap: dict, payload_snap: dict, filter_start: str) -> dict | None:
    """
    Build a market_events snapshot with the full date range AND user edits:
      pre-filter months  → from wide_snap  (model-computed, Apr 2020 start)
      filter window      → from payload_snap (carries user's table edits)
    """
    if not wide_snap and not payload_snap:
        return None
    if not wide_snap:
        return payload_snap
    if not payload_snap:
        return wide_snap

    wide_months = wide_snap.get("months", [])
    p_months    = payload_snap.get("months", [])
    splice_idx  = sum(1 for m in wide_months if str(m) < filter_start)

    if splice_idx == 0:
        return payload_snap

    pre_train = min(splice_idx, wide_snap.get("forecast_start_index", 0))
    new_fsi   = pre_train + payload_snap.get("forecast_start_index", 0)
    new_total = list(wide_snap.get("total_all", []))[:splice_idx] + \
                list(payload_snap.get("total_all", []))

    w_series, p_series = wide_snap.get("series", {}), payload_snap.get("series", {})
    new_series: dict = {}
    for product in set(w_series) | set(p_series):
        wp, pp = w_series.get(product, {}), p_series.get(product, {})
        new_series[product] = {
            payer: list(wp.get(payer, [0.0] * splice_idx))[:splice_idx] +
                   list(pp.get(payer, []))
            for payer in set(wp) | set(pp)
        }

    return {
        "months":               wide_months[:splice_idx] + p_months,
        "forecast_start_index": new_fsi,
        "total_all":            new_total,
        "series":               new_series,
    }


def _prepend_wide_months(wide_ma: dict, payload_ma: dict, filter_start: str) -> dict:
    """
    Merge wide_ma (full date range, model-computed) with payload_ma (user's filter
    view, may contain table edits).

    Months BEFORE filter_start  → taken from wide_ma  (user was not viewing/editing these)
    Months FROM filter_start on → taken from payload_ma (preserves any table edits)

    Falls back gracefully when either side is absent.
    """
    if not wide_ma:
        return payload_ma or {}
    if not payload_ma:
        return wide_ma

    def _splice_chart(w_chart: dict, p_chart: dict) -> dict:
        w_months = w_chart.get("months", [])
        if not w_months:
            return p_chart
        p_months  = p_chart.get("months", [])
        # Use the payload chart's actual first month as the splice point.
        # filter_start can be earlier than the payload data (e.g., user saved
        # with Jun-22 data but re-saves with a Mar-22 filter) which would create
        # a month gap in the stored chart.  The payload's own first month is
        # always the correct boundary.
        actual_p_start = str(p_months[0]) if p_months else filter_start
        splice_idx = sum(1 for m in w_months if str(m) < actual_p_start)
        if splice_idx == 0:
            return p_chart
        w_fsi     = w_chart.get("forecast_start_index", 0)
        p_fsi     = p_chart.get("forecast_start_index", 0)
        new_months    = w_months[:splice_idx] + p_months
        pre_train_cnt = min(splice_idx, w_fsi)
        new_fsi       = pre_train_cnt + p_fsi

        w_series_map = {s.get("label"): s for s in w_chart.get("series", [])}
        new_series = []
        for ps in p_chart.get("series", []):
            ws = w_series_map.get(ps.get("label"))
            if ws is None:
                new_series.append(ps)
                continue
            w_all    = list(ws.get("history", ws.get("train_values", []))) + \
                       list(ws.get("forecast", ws.get("forecast_values", [])))
            pre_vals = w_all[:splice_idx]
            new_hist = pre_vals[:pre_train_cnt] + \
                       list(ps.get("history", ps.get("train_values", [])))
            new_fore = pre_vals[pre_train_cnt:] + \
                       list(ps.get("forecast", ps.get("forecast_values", [])))
            new_series.append({**ps, "history": new_hist, "forecast": new_fore})

        return {**p_chart, "months": new_months, "forecast_start_index": new_fsi, "series": new_series}

    def _splice_flat_table(w_table: dict, p_table: dict, splice_idx: int) -> dict:
        if not w_table or splice_idx == 0:
            return p_table
        w_rows_list = w_table.get("rows", [])
        w_rows_by_label = {r.get("label", r.get("hierarchy", "")): r for r in w_rows_list}
        new_rows = []
        for i, pr in enumerate(p_table.get("rows", [])):
            key = pr.get("label", pr.get("hierarchy", ""))
            wr  = w_rows_by_label.get(key)
            if wr is None and i < len(w_rows_list):
                # Label mismatch fallback: use the wide row at the same position.
                # This handles the TMV tab where the wide row is labeled with the
                # TA name (e.g. "HCV") but the payload row carries the scenario name
                # (e.g. "Base" or "t1"), so label-keyed lookup always returns None.
                wr = w_rows_list[i]
            pre_v = list(wr.get("values", []))[:splice_idx] if wr else []
            new_rows.append({**pr, "values": pre_v + list(pr.get("values", []))})
        return {**p_table, "rows": new_rows}

    def _splice_hier_table(w_table: dict, p_table: dict, splice_idx: int) -> dict:
        if not w_table or splice_idx == 0:
            return p_table
        # stored format uses "label" (from _fmt_hier); fall back to "hierarchy" for legacy
        w_rows = {r.get("label", r.get("hierarchy", "")): r for r in w_table.get("rows", [])}
        new_rows = []
        for pr in p_table.get("rows", []):
            row_key = pr.get("label", pr.get("hierarchy", ""))
            wr = w_rows.get(row_key)
            if wr is None:
                new_rows.append(pr)
                continue
            # stored format uses "values" for parent totals (from _fmt_hier), not "total"
            val_key   = "values" if "values" in wr else "total"
            pre_total = list(wr.get(val_key, []))[:splice_idx]
            w_children = {c.get("label", ""): c for c in wr.get("children", [])}
            new_children = []
            for pc in pr.get("children", []):
                wc    = w_children.get(pc.get("label", ""))
                pre_c = list(wc.get("values", []))[:splice_idx] if wc else []
                new_children.append({**pc, "values": pre_c + list(pc.get("values", []))})
            p_val_key = "values" if "values" in pr else "total"
            new_rows.append({**pr,
                             p_val_key:  pre_total + list(pr.get(p_val_key, [])),
                             "children": new_children})
        return {**p_table, "rows": new_rows}

    def _splice_gran(w_gran: dict, p_gran: dict) -> dict:
        if not w_gran or not p_gran:
            return p_gran or w_gran or {}
        w_chart    = w_gran.get("chart", {})
        p_chart    = p_gran.get("chart", {})
        w_months   = w_chart.get("months", [])
        p_months   = p_chart.get("months", [])
        # Mirror _splice_chart: derive splice point from payload's actual first
        # month so the chart and table always use the same boundary and never
        # produce a month gap when filter_start < payload start date.
        actual_p_start = str(p_months[0]) if p_months else filter_start
        splice_idx = sum(1 for m in w_months if str(m) < actual_p_start) if w_months else 0
        new_chart  = _splice_chart(w_chart, p_chart)
        w_table    = w_gran.get("table", {})
        p_table    = p_gran.get("table", {})
        table_type = (p_table or w_table).get("type", "flat")
        if table_type == "hierarchy":
            new_table = _splice_hier_table(w_table, p_table, splice_idx)
        else:
            new_table = _splice_flat_table(w_table, p_table, splice_idx)
        return {**p_gran, "chart": new_chart, "table": new_table}

    def _splice_metric(w_metric: dict, p_metric: dict) -> dict:
        if not w_metric or not p_metric:
            return p_metric or w_metric or {}
        return {gk: _splice_gran(w_metric.get(gk, {}), pg) for gk, pg in p_metric.items()}

    def _splice_tab(w_tab: dict, p_tab: dict) -> dict:
        if not w_tab or not p_tab:
            return p_tab or w_tab or {}
        return {mk: _splice_metric(w_tab.get(mk, {}), pm) for mk, pm in p_tab.items()}

    return {tk: _splice_tab(wide_ma.get(tk, {}), pt) for tk, pt in payload_ma.items()}


def _compute_wide_chart_data(cur, ta: str, flt, factors_dict: dict) -> dict:
    """
    Recompute market_analysis for the FULL available date range (first TA
    transaction month → config forecast end) using the saved factors.

    Always returns at least {"_wide_start": ..., "_wide_end": ...} so callers
    store the correct available dates even when chart building fails.
    Falls back to {} only if the date range itself cannot be computed.
    """
    # Stage 1: compute the available date range independently of chart building
    wide_start = wide_end = None
    wide_from_year = wide_from_month = train_end_year = train_end_month = None
    wide_forecast_periods = None
    granularity = "monthly"
    try:
        cfg = _load_config(cur, ta, payment_type=flt.payer or None, brand=flt.product or None)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        # Same reasoning as apply_liver_filters' Base-persist block: the
        # selected (payer, brand) combo's own forecast_periods isn't
        # necessarily the widest available end across every config for this
        # TA -- extend (never shorten) to match that widest end so a saved
        # scenario isn't capped by whichever combo happened to be active.
        wide_forecast_periods = _extend_forecast_periods_to_widest_end(
            cur, ta, train_end_year, train_end_month, int(cfg["forecast_periods"])
        )
        granularity = cfg.get("model_granularity", "monthly")

        txn_months = get_transaction_distinct_months(cur, ta)
        if txn_months:
            wide_from_year, wide_from_month = txn_months[0]
        else:
            wide_from_year, wide_from_month = _parse_ym(cfg.get("train_start_date", flt.start_date))

        wide_start = date_type(wide_from_year, wide_from_month, 1).isoformat()
        wide_end   = _add_months(date_type(train_end_year, train_end_month, 1),
                                  wide_forecast_periods).isoformat()
    except Exception as _de:
        print(f"[liver] wide date range skipped: {_de}")

    if wide_from_year is None or train_end_year is None:
        return {}

    # Stage 2: build full chart data — may fail; dates are already computed above
    try:
        try:
            factors = LiverFactors(**factors_dict)
        except Exception:
            factors = _estimate_default_factors(
                cur, ta, wide_from_year, wide_from_month,
                train_end_year, train_end_month, granularity,
            )

        wide_ma, _ = _build_market_analysis_both_granularities(
            cur, ta, wide_from_year, wide_from_month,
            train_end_year, train_end_month, wide_forecast_periods, factors,
            sel_payer=flt.payer or None, sel_product=flt.product or None,
            force_tab1_ets=False,
            scenario_name=ta,
        )
        wide_ma = _recompute_all_market_shares_nested(wide_ma)
        return {"market_analysis": wide_ma, "_wide_start": wide_start, "_wide_end": wide_end}
    except Exception as _e:
        print(f"[liver] wide chart_data recompute skipped: {_e}")
        return {"_wide_start": wide_start, "_wide_end": wide_end}


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

        wide = _compute_wide_chart_data(cur, ta, flt, factors)
        store_from = wide.get("_wide_start") or flt.start_date
        store_to   = wide.get("_wide_end")   or flt.end_date

        spliced_ma = _prepend_wide_months(
            wide.get("market_analysis", {}), payload.market_analysis, flt.start_date
        ) if wide.get("market_analysis") else payload.market_analysis

        save_scenario(
            cur,
            scenario_name=name,
            ta=ta,
            payer=flt.payer or "",
            product=flt.product or "",
            from_date=store_from,
            to_date=store_to,
            chart_data={"market_analysis": spliced_ma},
            factors=factors,
        )

        try:
            me_snap = _splice_snapshots(
                extract_snapshot_from_market_analysis(wide.get("market_analysis", {})),
                extract_snapshot_from_market_analysis(payload.market_analysis),
                flt.start_date,
            )
            if me_snap:
                save_market_events_scenario(cur, name, me_snap)
        except Exception as _sync_err:
            print(f"[liver] market_events snapshot sync skipped: {_sync_err}")

        conn.commit()
        return _build_scenario_response(cur, name, ta, flt, factors, payload.market_analysis)
    finally:
        cur.close()
        conn.close()


def update_liver_scenario_new(payload: SaveScenarioRequest) -> dict:
    """PUT /liver/update-scenario — update an existing scenario. Rejects if name == 'Base' or doesn't exist."""
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

        wide = _compute_wide_chart_data(cur, ta, flt, factors)
        store_from = wide.get("_wide_start") or flt.start_date
        store_to   = wide.get("_wide_end")   or flt.end_date

        spliced_ma = _prepend_wide_months(
            wide.get("market_analysis", {}), payload.market_analysis, flt.start_date
        ) if wide.get("market_analysis") else payload.market_analysis

        save_scenario(
            cur,
            scenario_name=name,
            ta=ta,
            payer=flt.payer or "",
            product=flt.product or "",
            from_date=store_from,
            to_date=store_to,
            chart_data={"market_analysis": spliced_ma},
            factors=factors,
        )

        try:
            me_snap = _splice_snapshots(
                extract_snapshot_from_market_analysis(wide.get("market_analysis", {})),
                extract_snapshot_from_market_analysis(payload.market_analysis),
                flt.start_date,
            )
            if me_snap:
                save_market_events_scenario(cur, name, me_snap)
        except Exception as _sync_err:
            print(f"[liver] market_events snapshot sync skipped: {_sync_err}")

        conn.commit()
        return _build_scenario_response(cur, name, ta, flt, factors, payload.market_analysis)
    finally:
        cur.close()
        conn.close()


def delete_liver_scenario(payload: ActivateScenarioRequest) -> dict:
    """DELETE /liver/delete-scenario — remove a scenario and cascade to market_events_impact_rows."""
    name = payload.scenario_name.strip()
    if name.lower() == "base":
        raise ValueError("The Base scenario cannot be deleted.")

    ta  = payload.ta_name
    flt = payload.selected_filter

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if not scenario_exists(cur, name):
            raise ValueError(f"Scenario '{name}' does not exist.")

        delete_scenario(cur, name)

        try:
            delete_scenario_impact_rows(cur, ta, name)
        except Exception as _me_err:
            print(f"[liver] market_events impact rows delete skipped: {_me_err}")

        conn.commit()

        all_names = get_scenarios(cur)
        if "Base" in all_names:
            all_names.remove("Base")
        available_scenarios = ["Base"] + all_names

        cur.execute("SELECT scenario_name, chart_data FROM raw_liver.liver_scenarios")
        saved = {r[0]: (r[1] or {}) for r in cur.fetchall()}

        cfg = _load_config(cur, ta, payment_type=flt.payer or None, brand=flt.product or None)
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

        scenarios = {}
        for sc in available_scenarios:
            if sc == "Base":
                scenarios[sc] = {"market_analysis": _base_ma}
            else:
                cd     = saved.get(sc, {})
                raw_ma = _normalize_ma_keys(cd.get("market_analysis", {}))
                scenarios[sc] = {"market_analysis": raw_ma}

        return {
            "status": "success",
            "message": "Scenario deleted successfully",
            "ta_name": ta,
            "selected_filter": {
                "start_date": flt.start_date,
                "end_date": flt.end_date,
                "payer": flt.payer,
                "product": flt.product,
            },
            "available_scenarios": available_scenarios,
            "active_scenario": "Base",
            "deleted_scenario": name,
            "scenarios": scenarios,
        }
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
        cfg = _load_config(cur, ta, payment_type=flt.payer or None, brand=flt.product or None)
        train_end_year, train_end_month = _parse_ym(cfg["train_end_date"])
        from_year, from_month = _parse_ym(flt.start_date)
        forecast_periods = _resolve_forecast_periods(
            flt.end_date, train_end_year, train_end_month, cfg["forecast_periods"]
        )
        granularity = cfg.get("model_granularity", "monthly")

        cur.execute(
            "SELECT scenario_name, chart_data, factors, from_date, to_date FROM raw_liver.liver_scenarios"
        )
        saved = {
            r[0]: {"chart_data": r[1] or {}, "factors": r[2] or {}, "from_date": r[3], "to_date": r[4]}
            for r in cur.fetchall()
        }

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
        if is_base:
            active_ma      = _base_ma
            active_factors = base_factors.model_dump()
        elif name in saved:
            active_ma      = _normalize_ma_keys(saved[name]["chart_data"].get("market_analysis", {}))
            # Clip to the user's filter window: DB stores wide data (e.g. Apr-20)
            # but the response must cover only the user's selected range (e.g. Mar-22).
            # Without clipping, normalizeLiverResponse picks the active scenario's
            # Apr-20 months as the comparison-table axis, making all other scenarios
            # appear to start from Apr-20 in the chart and table.
            active_ma      = _clip_ma_to_from_date(active_ma, from_year, from_month)
            active_factors = saved[name]["factors"]
        else:
            raise ValueError(f"Scenario '{name}' not found.")

        scenarios = {}
        for sc in available_scenarios:
            if sc == name or (is_base and sc == "Base"):
                scenarios[sc] = {"factors": active_factors, "market_analysis": active_ma}
            elif sc == "Base":
                # _base_ma is freshly computed from from_year/from_month, but clip
                # defensively in case its month count differs from active_ma's.
                scenarios[sc] = {"market_analysis": _clip_ma_to_from_date(_base_ma, from_year, from_month)}
            else:
                cd     = saved.get(sc, {}).get("chart_data", {})
                raw_ma = _normalize_ma_keys(cd.get("market_analysis", {}))
                # Clip DB-stored wide data to the user's filter window so all
                # scenarios share the same month axis in the comparison chart.
                scenarios[sc] = {"market_analysis": _clip_ma_to_from_date(raw_ma, from_year, from_month) if raw_ma else raw_ma}

        # Return the REQUEST's filter dates — not DB-stored wide dates.
        # Returning stored.get("from_date") (e.g. "2020-04-01") poisoned
        # liverRawData.selected_filter so the 2nd "Apply Selected Scenario"
        # click sent Apr-20 to the backend, causing Base to expand to the
        # full wide range instead of the user's filter window.
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
    # Default trajectory start = first forecast month (train_end + 1), so the
    # dropdown always shows a valid, selectable date on initial load.
    _traj_dt           = datetime(to_year, to_month_safe, 1) + relativedelta(months=1)
    trajectory_start   = date_type(_traj_dt.year, _traj_dt.month, 1).isoformat()
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

    FLAT_DIST_TABS = ["payer_distribution", "product_distribution"]
    HIER_DIST_TABS = ["payer_product", "product_payer"]
    DIST_TABS      = FLAT_DIST_TABS + HIER_DIST_TABS
    HIER_TABS      = set(HIER_DIST_TABS)

    # ── Load full market_analysis from DB / recompute so all tabs are populated ─
    conn = get_connection()
    cur  = conn.cursor()
    try:
        from_year, from_month = _parse_ym(flt.start_date)
        cfg = _load_config(cur, payload.ta_name, payment_type=flt.payer or None, brand=flt.product or None)
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
                sel_payer=flt.payer or None, sel_product=flt.product or None,
                scenario_name="Base",
            )
        else:
            cur.execute(
                "SELECT chart_data, factors FROM raw_liver.liver_scenarios WHERE scenario_name = %s",
                (active,)
            )
            row = cur.fetchone()
            if row and row[0] and "market_analysis" in row[0]:
                full_ma = _normalize_ma_keys(row[0]["market_analysis"])
            else:
                # Scenario not found or no chart_data — recompute with default factors
                sc_f = _estimate_default_factors(
                    cur, payload.ta_name, from_year, from_month,
                    train_end_year, train_end_month, granularity,
                )
                full_ma, _ = _build_market_analysis_both_granularities(
                    cur, payload.ta_name, from_year, from_month,
                    train_end_year, train_end_month, forecast_periods, sc_f,
                    sel_payer=flt.payer or None, sel_product=flt.product or None,
                    scenario_name=active,
                )

        # Merge payload's edited tab on top of the full market_analysis so the
        # user's changes override the DB values for the selected tab only.
        ma = copy.deepcopy(full_ma)
        # Normalise old-key data from the frontend (liverRawData may carry pre-rename keys)
        payload_ma = _normalize_ma_keys(payload.market_analysis or {})
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
        # "Base" is now a real persisted row (see apply_liver_filters), so it
        # must be excluded here too or it's listed twice. all_saved_cd itself
        # keeps its "Base" key untouched -- only this scenario-name list drops it.
        available_scenarios = ["Base"] + [s for s in all_saved_cd.keys() if s != "Base"]
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
            .get("payer_volume", {})
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
                               .get("payer_volume", {})
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
            return flt.payer or None
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
        rows = _old_rows("total_market_volume", "payer_volume", gran)
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
                (r for r in _rows(tab, "payer_volume", gran) if r.get("label") == parent.get("label")),
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

    def _backfill_flat(hier_tab, flat_tab, g):
        """Sync flat distribution volumes from hier parent totals to the flat tab."""
        hier_rows = _rows(hier_tab, "payer_volume", g)
        flat_rows = _rows(flat_tab, "payer_volume", g)
        if not hier_rows or not flat_rows:
            return
        hier_map = {r.get("label", ""): [int(round(float(v))) for v in r.get("values", [])]
                    for r in hier_rows}
        n = max((len(r.get("values", [])) for r in flat_rows), default=0)
        new_non_total = [
            {"label": r.get("label", ""),
             "values": hier_map.get(r.get("label", ""),
                                    [int(round(float(v))) for v in r.get("values", [])])}
            for r in flat_rows if r.get("label", "").lower() != "total"
        ]
        total_vals = [
            sum(r["values"][i] if i < len(r["values"]) else 0 for r in new_non_total)
            for i in range(n)
        ]
        _put_flat(flat_tab, "payer_volume", g,
                  [{"label": "Total", "values": total_vals}] + new_non_total,
                  to_int=True)

    # ── Core propagation ─────────────────────────────────────────────────────

    for gran in ("monthly", "yearly"):
        tmv_rows = _rows("total_market_volume", "payer_volume", gran)
        tmv_vals = _total_vals(tmv_rows)
        if not tmv_vals:
            continue

        if tab == "total_market_volume":
            # Sync TMV chart from (user-edited) table
            tmv_gran = dict(ma.get("total_market_volume", {}).get("payer_volume", {}).get(gran, {}))
            _sync_flat_chart(tmv_gran)
            _set_gran("total_market_volume", "payer_volume", gran, tmv_gran)

            old_tmv = _get_old_tmv(gran)

            # Flat distribution tabs: share-based (shares are % of total = % of TMV)
            for dtab in FLAT_DIST_TABS:
                share_rows = _rows(dtab, "payer_share", gran)
                if share_rows:
                    _put_flat(dtab, "payer_volume", gran, _vol_from_share(share_rows, tmv_vals), to_int=True)

            # Hierarchical tabs: proportional scaling (shares are % within parent, not TMV)
            for dtab in HIER_DIST_TABS:
                old_vol_rows = _old_rows(dtab, "payer_volume", gran)
                if old_vol_rows and old_tmv:
                    new_vol_rows = _scale_hier_vols(old_vol_rows, old_tmv, tmv_vals)
                    _put_hier(dtab, "payer_volume", gran, new_vol_rows, to_int=True)

        elif tab in FLAT_DIST_TABS:
            if metric == "payer_volume":
                vol_rows = _rows(tab, "payer_volume", gran)
                if eh:
                    vol_rows = _redistribute(vol_rows, eh, tmv_vals)
                    _put_flat(tab, "payer_volume", gran, vol_rows, to_int=True)
                _put_flat(tab, "payer_share", gran,
                          _share_from_vol(_rows(tab, "payer_volume", gran), tmv_vals))
            else:
                share_rows = _rows(tab, "payer_share", gran)
                if eh:
                    share_rows = _redistribute(share_rows, eh, [100.0] * len(tmv_vals))
                    _put_flat(tab, "payer_share", gran, share_rows)
                _put_flat(tab, "payer_volume", gran,
                          _vol_from_share(_rows(tab, "payer_share", gran), tmv_vals), to_int=True)

            # Top-to-bottom rule: Tab2 (product_distribution) rescales Tab3 downward,
            # but Tab3 edits do NOT touch Tab2.
            if tab == "product_distribution":
                other_flat_shares = _rows("payer_distribution", "payer_share", gran)
                if other_flat_shares:
                    _put_flat("payer_distribution", "payer_volume", gran,
                              _vol_from_share(other_flat_shares, tmv_vals), to_int=True)

            # Derive Tab4 (payer_product) and Tab5 (product_payer) using IPF.
            # Row targets = Tab3 (payer) volumes — always read after redistribution above.
            # Col targets:
            #   Tab2 edit → use Tab2 directly (just redistributed, authoritative).
            #   Tab3 edit → derive from Tab4's current column sums, which carry forward
            #               the product state from the previous Tab2 refresh.  The payload
            #               may not re-send Tab2 data, so Tab4 col sums are the best proxy.
            tab4_seed = _rows("payer_product", "payer_volume", gran)
            row_targets = {
                r["label"]: [float(v) for v in r["values"]]
                for r in _rows("payer_distribution", "payer_volume", gran)
                if r.get("label", "").lower() != "total"
            }
            if tab == "product_distribution":
                col_targets = {
                    r["label"]: [float(v) for v in r["values"]]
                    for r in _rows("product_distribution", "payer_volume", gran)
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
                    for r in _rows("product_distribution", "payer_volume", gran)
                    if r.get("label", "").lower() != "total"
                }
            if tab4_seed and row_targets and col_targets:
                new_tab4 = _ipf_hier_rows(tab4_seed, row_targets, col_targets)
                _put_hier("payer_product", "payer_volume", gran, new_tab4, to_int=True)
                tab5_seed = _rows("product_payer", "payer_volume", gran)
                if tab5_seed:
                    _put_hier("product_payer", "payer_volume", gran,
                              _transpose_hier(new_tab4, tab5_seed), to_int=True)

        elif tab in HIER_TABS:
            share_rows = _rows(tab, "payer_share", gran)
            if metric == "payer_share":
                if eh:
                    share_rows = _hier_redistribute_share(share_rows, eh, len(tmv_vals))
                    _put_hier(tab, "payer_share", gran, share_rows)
                _put_hier(tab, "payer_volume", gran,
                          _hier_vol_from_parent_share(_rows(tab, "payer_share", gran), tmv_vals), to_int=True)
            else:
                # Volume edited in hier tab: edit the specific child (eh), redistribute siblings.
                hier_rows = _rows(tab, "payer_volume", gran)

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
                _put_hier(tab, "payer_volume", gran, new_hier_rows, to_int=True)

            # Propagate between payer_product ↔ product_payer bidirectionally
            # then backfill flat distribution tabs from the updated hier parent totals.
            # payer_product parents (payers)   → payer_distribution rows
            # product_payer parents (products) → product_distribution rows
            if tab == "payer_product":
                updated_vol = _rows("payer_product", "payer_volume", gran)
                tab5_seed   = _rows("product_payer", "payer_volume", gran)
                if updated_vol and tab5_seed:
                    _put_hier("product_payer", "payer_volume", gran,
                              _transpose_hier(updated_vol, tab5_seed), to_int=True)
            elif tab == "product_payer":
                updated_vol = _rows("product_payer", "payer_volume", gran)
                tab4_seed   = _rows("payer_product", "payer_volume", gran)
                if updated_vol and tab4_seed:
                    _put_hier("payer_product", "payer_volume", gran,
                              _transpose_hier(updated_vol, tab4_seed), to_int=True)

            _backfill_flat("payer_product", "payer_distribution", gran)
            _backfill_flat("product_payer", "product_distribution", gran)

    # Recompute all market_share from final market_volume values so everything is consistent.
    # For hier tabs: child_share = child_vol / sum(children) * 100 (% within parent).
    # For flat tabs: row_share  = row_vol  / col_sum         * 100 (% of distribution).
    ma = _recompute_all_market_shares_nested(ma)

    # ── Build response ────────────────────────────────────────────────────────
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
                        sel_payer=flt.payer or None, sel_product=flt.product or None,
                        scenario_name="Base",
                    )
                finally:
                    cur2.close()
                    conn2.close()
                return {"market_analysis": base_ma2}
            else:
                return {"market_analysis": full_ma}
        else:
            cd      = all_saved_cd.get(sc_name, {})
            raw_ma  = _normalize_ma_keys(cd.get("market_analysis", {}))
            return {"market_analysis": raw_ma}

    # Strip extra scenario rows from the active scenario's TMV table.
    # The frontend sends all scenario rows in the payload; we only want the
    # active scenario's row so normalizeLiverResponse correctly reads it.
    for gran in ("monthly", "yearly"):
        tmv_gran = (ma.get("total_market_volume", {})
                      .get("payer_volume", {})
                      .get(gran, {}))
        if "table" in tmv_gran:
            all_rows = tmv_gran["table"].get("rows", [])
            active_row = next(
                (r for r in all_rows if r.get("label") == active or r.get("hierarchy") == active),
                None
            )
            if active_row:
                tmv_gran["table"]["rows"] = [active_row]

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
        "selected_filter": {
            "start_date": flt.start_date,
            "end_date":   flt.end_date,
            "payer":      flt.payer,
            "product":    flt.product,
        },
        "scenarios":           scenarios,
    }
