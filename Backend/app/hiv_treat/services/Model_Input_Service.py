import pandas as pd
from collections import OrderedDict
from app.db.connection import get_connection


# =========================================================
# ================= DATA LAYER =============================
# =========================================================

def fetch_forecast(cur, ta, market, source, product, metric):
    cur.execute("""
        SELECT forecast_data
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND market = %s
          AND (%s IS NULL OR COALESCE(source_of_market,'ALL') = COALESCE(%s,'ALL'))
          AND product = %s
          AND metric = %s
    """, (ta, market, source, source, product, metric))

    row = cur.fetchone()
    return row[0] if row else None


def fetch_forecast_scenario(cur, ta, market, source, product, metric, scenario):
    is_base = scenario.upper() == "BASE"

    if is_base:
        cur.execute("""
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND market = %s
              AND (%s IS NULL OR COALESCE(source_of_market,'ALL') = COALESCE(%s,'ALL'))
              AND product = %s
              AND metric = %s
              AND UPPER(COALESCE(scenario_name, 'BASE')) = 'BASE'
        """, (ta, market, source, source, product, metric))
    else:
        cur.execute("""
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND market = %s
              AND (%s IS NULL OR COALESCE(source_of_market,'ALL') = COALESCE(%s,'ALL'))
              AND product = %s
              AND metric = %s
              AND scenario_name = %s
        """, (ta, market, source, source, product, metric, scenario))

    row = cur.fetchone()
    return row[0] if row else None


def get_markets(cur, ta):
    cur.execute("""
        SELECT DISTINCT market
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s AND metric = 'market_share' and market != 'ALL'
    """, (ta,))
    return [r[0] for r in cur.fetchall()]


def get_sources(cur, ta, market):
    cur.execute("""
        SELECT DISTINCT source_of_market
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND market = %s
          AND source_of_market IS NOT NULL
          AND UPPER(source_of_market) <> 'ALL'
    """, (ta, market))

    return [r[0] for r in cur.fetchall()]


def get_products(cur, ta):
    cur.execute("""
        SELECT DISTINCT product
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s AND product != 'ALL'
    """, (ta,))
    return [r[0] for r in cur.fetchall()]


def get_scenarios(cur, ta):
    cur.execute("""
        SELECT DISTINCT scenario_name
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name IS NOT NULL
    """, (ta,))
    rows = cur.fetchall()
    if not rows:
        return ["BASE"]

    all_scenarios  = [r[0] for r in rows]
    base_variants  = [s for s in all_scenarios if s.upper() == "BASE"]
    non_base       = [s for s in all_scenarios if s.upper() != "BASE"]
    canonical_base = base_variants[0] if base_variants else "BASE"

    return [canonical_base] + non_base


# =========================================================
# ================= TRANSFORM ==============================
# =========================================================

def format_months(months):
    return [pd.to_datetime(m).strftime("%b-%y") for m in months]


def split_series(values, split_idx):
    return values[:split_idx], values[split_idx:]


def build_series(data, start, end):
    months   = pd.to_datetime(data["months"])
    train    = data.get("train_values", [])
    forecast = data.get("forecast_values", [])

    full = train + forecast

    mask           = (months >= pd.to_datetime(start)) & (months <= pd.to_datetime(end))
    idx            = [i for i in range(len(months)) if mask[i]]
    filtered_months = months[mask]
    values         = [full[i] for i in idx]

    orig_split = data.get("forecast_start_index", len(train))
    split_idx  = sum(i < orig_split for i in idx)

    history, fc = split_series(values, split_idx)

    return {
        "months":   format_months(filtered_months),
        "values":   values,
        "history":  history,
        "forecast": fc,
        "split_idx": split_idx
    }


def build_volume_from_share(total, share):
    """
    Compute volume from total and share %.
    Returns RAW FLOAT values — rounding is intentionally deferred.

    Rounding here (at monthly level) and then summing to yearly causes drift:
      12 months × ±0.5 rounding error = up to ±6 unit yearly drift.
    By keeping floats, yearly aggregation sums the raws first and rounds
    once at the yearly level, eliminating that drift entirely.
    """
    min_len = min(len(total), len(share))
    return [total[i] * share[i] / 100 for i in range(min_len)]


def round_volume(values):
    """
    Round raw float volumes to integers FOR DISPLAY ONLY.
    Call this only at the final monthly output stage, never on intermediate
    values that will feed into yearly aggregation.
    """
    return [round(v) for v in values]


def normalize_shares_to_100(children_values_list, n):
    """
    Given a list of raw-float volume lists (one per child), compute each
    child's percentage share of the total at each time index.
    Guaranteed to sum to exactly 100 across siblings by construction.

    When the parent total is 0 (or negative), all children get 0% rather
    than an equal split -- a 0-volume parent has no meaningful
    distribution to show, and splitting evenly would misleadingly imply
    each child still holds a nonzero share.
    """
    num_children = len(children_values_list)
    if num_children == 0:
        return children_values_list

    normalized = [[0.0] * n for _ in range(num_children)]

    for t in range(n):
        total = sum(
            children_values_list[c][t] if t < len(children_values_list[c]) else 0
            for c in range(num_children)
        )
        for c in range(num_children):
            val = children_values_list[c][t] if t < len(children_values_list[c]) else 0
            if total > 0:
                normalized[c][t] = round((val / total) * 100, 2)
            else:
                normalized[c][t] = 0.0

    return normalized


def safe_pct(numerator, denominator, decimals=2):
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, decimals)


# =========================================================
# ================= YEARLY AGGREGATION =====================
# =========================================================

def get_month_year(month_str):
    """'Jan-24' -> '2024'"""
    return "20" + month_str.split("-")[1]


def get_ordered_years(monthly_months):
    """Return unique years in order from monthly month strings."""
    seen = OrderedDict()
    for m in monthly_months:
        seen[get_month_year(m)] = True
    return list(seen.keys())


def yearly_forecast_start_index(monthly_months, monthly_split_idx):
    """Which year index is the first forecast year."""
    if monthly_split_idx >= len(monthly_months):
        return len(get_ordered_years(monthly_months))

    forecast_year = get_month_year(monthly_months[monthly_split_idx])
    year_list     = get_ordered_years(monthly_months)

    return year_list.index(forecast_year) if forecast_year in year_list else len(year_list)


def aggregate_yearly_volume(monthly_months, monthly_raw_values):
    """
    Sum RAW monthly float volumes by year, then round ONCE at yearly level.

    This is the key fix for yearly drift:
      sum(round(monthly)) can drift by up to ±N/2 where N = months per year.
      round(sum(monthly_raws)) has at most ±0.5 error total.

    So Biktarvy_yearly + Truvada_yearly + Descovy_yearly = Overall_yearly
    with at most ±1 unit discrepancy (unavoidable in integer display),
    vs the 7-unit drift seen when summing pre-rounded monthly integers.
    """
    year_sums = OrderedDict()
    for m, v in zip(monthly_months, monthly_raw_values):
        y = get_month_year(m)
        year_sums[y] = year_sums.get(y, 0) + v   # sum raw floats

    years  = list(year_sums.keys())
    values = [round(year_sums[y]) for y in years]  # single round at yearly level
    return years, values


def aggregate_yearly_share_from_volumes(monthly_months, child_vols, parent_vols):
    """
    Compute yearly share as: round(sum(child_vol_in_year) / sum(parent_vol_in_year) * 100, 2)

    This is the ONLY correct way to aggregate share values to yearly:
      - Volume-weighted: months with higher volume contribute more to the yearly %.
      - Siblings always sum to 100% by construction because
        child_A + child_B = parent => share_A + share_B = parent/parent = 100%.
      - Never use simple average of monthly % values — it ignores volume weights
        and causes rounding drift across siblings.

    child_vols:  raw monthly volumes for this segment  (e.g. Retail)
    parent_vols: raw monthly volumes for the parent    (e.g. Total market)
    """
    year_child  = OrderedDict()
    year_parent = OrderedDict()

    for m, cv, pv in zip(monthly_months, child_vols, parent_vols):
        y = get_month_year(m)
        year_child[y]  = year_child.get(y, 0)  + cv
        year_parent[y] = year_parent.get(y, 0) + pv

    years  = list(year_child.keys())
    values = [
        round((year_child[y] / year_parent[y]) * 100, 2) if year_parent[y] > 0 else 0.0
        for y in years
    ]
    return years, values


def build_yearly_volume_chart_and_table(monthly_months, monthly_split_idx,
                                        series_data, table_rows, table_type):
    """
    Build yearly chart + table for VOLUME metrics.

    series_data items: {"label", "monthly_values" (raw floats), optionally "market"/"product"}
    table_rows items:  {"label", "monthly_values" (raw floats), optionally "children" (same shape)}
    """
    all_years = get_ordered_years(monthly_months)
    y_split   = yearly_forecast_start_index(monthly_months, monthly_split_idx)

    # Chart
    yearly_series = []
    for s in series_data:
        _, yvals = aggregate_yearly_volume(monthly_months, s["monthly_values"])
        yh, yf   = split_series(yvals, y_split)
        entry    = {"label": s["label"]}
        for k in ("market", "product"):
            if k in s:
                entry[k] = s[k]
        entry["history"]  = yh
        entry["forecast"] = yf
        yearly_series.append(entry)

    yearly_chart = {
        "years":                all_years,
        "forecast_start_index": y_split,
        "series":               yearly_series
    }

    # Table (recursive to handle children)
    def agg_row(row):
        _, yvals = aggregate_yearly_volume(monthly_months, row["monthly_values"])
        result   = {"label": row["label"], "values": yvals}
        if "children" in row:
            result["children"] = [agg_row(c) for c in row["children"]]
        return result

    yearly_table = {
        "type": table_type,
        "rows": [agg_row(r) for r in table_rows]
    }

    return yearly_chart, yearly_table


def build_yearly_share_chart_and_table(monthly_months, monthly_split_idx,
                                       series_data, table_rows, table_type):
    """
    Build yearly chart + table for SHARE metrics.

    series_data items: {
        "label", optionally "market"/"product",
        "child_vols":  raw monthly volumes for this segment,
        "parent_vols": raw monthly volumes for the parent
    }
    table_rows items: {
        "label",
        EITHER "fixed_values": list (e.g. Overall = [100.0, 100.0, ...])
        OR     "child_vols" + "parent_vols" for computed share,
        optionally "children" (same shape, recursively)
    }
    """
    all_years = get_ordered_years(monthly_months)
    y_split   = yearly_forecast_start_index(monthly_months, monthly_split_idx)

    # Chart
    yearly_series = []
    for s in series_data:
        _, yvals = aggregate_yearly_share_from_volumes(
            monthly_months, s["child_vols"], s["parent_vols"]
        )
        yh, yf = split_series(yvals, y_split)
        entry  = {"label": s["label"]}
        for k in ("market", "product"):
            if k in s:
                entry[k] = s[k]
        entry["history"]  = yh
        entry["forecast"] = yf
        yearly_series.append(entry)

    yearly_chart = {
        "years":                all_years,
        "forecast_start_index": y_split,
        "series":               yearly_series
    }

    # Table (recursive)
    def agg_share_row(row):
        if "fixed_values" in row:
            n_years = len(all_years)
            fv      = row["fixed_values"]
            yvals   = (fv + [fv[-1]] * (n_years - len(fv)))[:n_years]
            result  = {"label": row["label"], "values": yvals}
        else:
            _, yvals = aggregate_yearly_share_from_volumes(
                monthly_months, row["child_vols"], row["parent_vols"]
            )
            result = {"label": row["label"], "values": yvals}

        if "children" in row:
            result["children"] = [agg_share_row(c) for c in row["children"]]
        return result

    yearly_table = {
        "type": table_type,
        "rows": [agg_share_row(r) for r in table_rows]
    }

    return yearly_chart, yearly_table


def wrap_monthly_yearly_volume(monthly_chart, monthly_table,
                               monthly_months, monthly_split_idx,
                               series_data, table_rows, table_type):
    y_chart, y_table = build_yearly_volume_chart_and_table(
        monthly_months, monthly_split_idx, series_data, table_rows, table_type
    )
    return {
        "monthly": {"chart": monthly_chart, "table": monthly_table},
        "yearly":  {"chart": y_chart,       "table": y_table}
    }


def wrap_monthly_yearly_share(monthly_chart, monthly_table,
                              monthly_months, monthly_split_idx,
                              series_data, table_rows, table_type):
    y_chart, y_table = build_yearly_share_chart_and_table(
        monthly_months, monthly_split_idx, series_data, table_rows, table_type
    )
    return {
        "monthly": {"chart": monthly_chart, "table": monthly_table},
        "yearly":  {"chart": y_chart,       "table": y_table}
    }


# =========================================================
# ================= FACTORS ================================
# =========================================================

def build_factors(cur, ta, scenario):
    is_base = scenario.upper() == "BASE"

    # ======================================================
    # Fetch market-volume factors
    # ======================================================

    if is_base:
        cur.execute(
            """
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_volume'
              AND market = 'ALL'
              AND UPPER(COALESCE(scenario_name, 'BASE')) = 'BASE'
            LIMIT 1
            """,
            (ta,),
        )
    else:
        cur.execute(
            """
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_volume'
              AND market = 'ALL'
              AND scenario_name = %s
            LIMIT 1
            """,
            (ta, scenario),
        )

    row = cur.fetchone()

    if not row or not isinstance(row[0], dict):
        return {}

    data = row[0]

    volume_factors = data.get("factors") or {}

    if not isinstance(volume_factors, dict):
        volume_factors = {}

    months = data.get("months") or []
    split_idx = data.get("forecast_start_index") or 0

    trajectory_start = (
        months[split_idx]
        if isinstance(split_idx, int)
        and 0 <= split_idx < len(months)
        else None
    )

    ets = {
        "alpha": volume_factors.get("alpha"),
        "beta": volume_factors.get("beta"),
        "gamma": volume_factors.get("gamma"),
    }

    # ======================================================
    # Fetch market-share factors
    # ======================================================

    if is_base:
        cur.execute(
            """
            SELECT forecast_data->'factors'
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_share'
              AND UPPER(COALESCE(scenario_name, 'BASE')) = 'BASE'
            LIMIT 1
            """,
            (ta,),
        )
    else:
        cur.execute(
            """
            SELECT forecast_data->'factors'
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_share'
              AND scenario_name = %s
            LIMIT 1
            """,
            (ta, scenario),
        )

    row = cur.fetchone()

    factors_data = row[0] if row else {}

    # A database row may exist while the JSON value is null.
    if not isinstance(factors_data, dict):
        factors_data = {}

    print("================================")
    print("Market-volume factors:", volume_factors)
    print("Market-share factors:", factors_data)
    print("================================")

    # Support either:
    # {"window": 3}
    #
    # or:
    # {"moving_average": {"window": 3}}
    moving_average_cfg = factors_data.get("moving_average")

    if not isinstance(moving_average_cfg, dict):
        moving_average_cfg = factors_data

    moving_average = {
        "window": moving_average_cfg.get("window"),
    }

    default_duration = max(
        0,
        len(months) - split_idx,
    )

    linear_cfg = factors_data.get("linear") or {}
    scurve_cfg = factors_data.get("s_curve") or {}
    exp_cfg = factors_data.get("exponential") or {}
    log_cfg = factors_data.get("logarithmic") or {}

    if not isinstance(linear_cfg, dict):
        linear_cfg = {}

    if not isinstance(scurve_cfg, dict):
        scurve_cfg = {}

    if not isinstance(exp_cfg, dict):
        exp_cfg = {}

    if not isinstance(log_cfg, dict):
        log_cfg = {}

    linear = {
        "duration": linear_cfg.get(
            "duration",
            default_duration,
        ),
        "total_growth": linear_cfg.get(
            "total_growth"
        ),
        "trajectory_start": linear_cfg.get(
            "trajectory_start",
            trajectory_start,
        ),
    }

    scurve = {
        "k_value": scurve_cfg.get(
            "k_value",
            1,
        ),
        "duration": scurve_cfg.get(
            "duration",
            default_duration,
        ),
        "total_growth": scurve_cfg.get(
            "total_growth"
        ),
        "trajectory_start": scurve_cfg.get(
            "trajectory_start",
            trajectory_start,
        ),
    }

    exponential = {
        "k_value": exp_cfg.get(
            "k_value",
            1,
        ),
        "duration": exp_cfg.get(
            "duration",
            default_duration,
        ),
        "total_growth": exp_cfg.get(
            "total_growth"
        ),
        "trajectory_start": exp_cfg.get(
            "trajectory_start",
            trajectory_start,
        ),
    }

    logarithmic = {
        "k_value": log_cfg.get(
            "k_value",
            1,
        ),
        "duration": log_cfg.get(
            "duration",
            default_duration,
        ),
        "total_growth": log_cfg.get(
            "total_growth"
        ),
        "trajectory_start": log_cfg.get(
            "trajectory_start",
            trajectory_start,
        ),
    }

    return {
        "ets": ets,
        "moving_average": moving_average,
        "linear": linear,
        "scurve": scurve,
        "multiplier": factors_data.get(
            "multiplier",
            1,
        ),
        "exponential": exponential,
        "logarithmic": logarithmic,
        "active_model": factors_data.get(
            "active_model",
            "ets",
        ),
        "multiplier_horizon": factors_data.get(
            "multiplier_horizon",
            "Forecast",
        ),
    }


# =========================================================
# ================= MARKET ANALYSIS BUILDERS ===============
# =========================================================

def build_total_market_volume(total_vals, months, split_idx,scenario_label="Base"):
    """
    Total market volume — share is always 100%.

    total_vals: raw floats from build_series.
    Monthly display rounds to int. Yearly sums raws then rounds once.
    """
    print(
        "build_total_market_volume called, scenario_label=",
        scenario_label
    )
    int_vals = round_volume(total_vals)   # display-only rounding
    n        = len(int_vals)
    h, f     = split_series(int_vals, split_idx)

    share_vals = [100.0] * n
    sh, sf     = split_series(share_vals, split_idx)

    all_years = get_ordered_years(months)

    # Monthly
    mv_chart = {"months": months, "forecast_start_index": split_idx,
                "series": [{"label": scenario_label, "history": h, "forecast": f}]}
    mv_table = {"type": "flat",
                "rows": [{"label": scenario_label, "values": int_vals}]}

    ms_chart = {"months": months, "forecast_start_index": split_idx,
                "series": [{"label": scenario_label, "history": sh, "forecast": sf}]}
    ms_table = {"type": "flat",
                "rows": [{"label": scenario_label, "values": share_vals}]}

    # Yearly descriptors — use raw total_vals (floats) for volume aggregation
    mv_series_data = [{"label": scenario_label, "monthly_values": total_vals}]
    mv_table_rows  = [{"label": scenario_label, "monthly_values": total_vals}]

    ms_series_data = [{"label": scenario_label,
                       "child_vols": total_vals, "parent_vols": total_vals}]
    ms_table_rows  = [{"label": scenario_label,
                       "fixed_values": [100.0] * len(all_years)}]

    return {
        "market_volume": wrap_monthly_yearly_volume(
            mv_chart, mv_table, months, split_idx,
            mv_series_data, mv_table_rows, "flat"
        ),
        "market_share": wrap_monthly_yearly_share(
            ms_chart, ms_table, months, split_idx,
            ms_series_data, ms_table_rows, "flat"
        )
    }


def build_market_distribution(cur, ta, scenario, total_vals, months, split_idx, start, end,selected_market):
    """
    Market distribution — volume and share split across markets.

    total_vals: raw floats.
    All market volumes are raw floats throughout; rounded only for monthly display.
    Yearly share = sum(mkt_raw_in_year) / sum(total_raw_in_year) * 100.
    Source children share = sum(src_raw_in_year) / sum(mkt_raw_in_year) * 100.
    """
    markets   = get_markets(cur, ta)
    n         = len(total_vals)
    all_years = get_ordered_years(months)

    vol_chart_series   = []
    share_chart_series = []
    market_vol_rows    = []
    market_share_rows  = []

    # Monthly display — round total for Overall row
    overall_vol_row   = {"label": "Overall", "values": round_volume(total_vals)}
    overall_share_row = {"label": "Overall", "values": [100.0] * n}

    # Yearly descriptors
    mv_series_data = []
    ms_series_data = []
    mv_table_rows  = [{"label": "Overall", "monthly_values": total_vals}]
    ms_table_rows  = [{"label": "Overall",
                       "fixed_values": [100.0] * len(all_years)}]

    market_totals = {}

    for mkt in markets:
        d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
        if not d:
            continue

        s     = build_series(d, start, end)
        share = s["values"]

        # raw float volumes
        vol = build_volume_from_share(total_vals, share)
        vol = vol + [0.0] * (n - len(vol))
        market_totals[mkt] = vol

        # Monthly display — round for chart/table
        vol_display = round_volume(vol)
        h, f        = split_series(vol_display, split_idx)
        sh, sf      = split_series(share, split_idx)

        if mkt == selected_market:
            vol_chart_series.append({"label": mkt, "history": h, "forecast": f})
            share_chart_series.append({"label": mkt, "history": sh, "forecast": sf})

            mv_series_data.append({"label": mkt, "monthly_values": vol})
            ms_series_data.append({"label": mkt,
                                    "child_vols": vol, "parent_vols": total_vals})

        # Sources
        sources               = get_sources(cur, ta, mkt)
        vol_children          = []
        share_children_vals   = []
        share_children_labels = []
        mv_child_rows         = []
        ms_child_rows         = []

        for src in sources:
            sd = fetch_forecast_scenario(cur, ta, mkt, src, "ALL", "market_share", scenario)
            if not sd:
                continue

            ss        = build_series(sd, start, end)
            src_share = ss["values"]
            src_vol   = build_volume_from_share(vol, src_share)   # raw floats

            vol_children.append({"label": src, "values": round_volume(src_vol)})
            share_children_vals.append(src_vol)
            share_children_labels.append(src)

            mv_child_rows.append({"label": src, "monthly_values": src_vol})
            ms_child_rows.append({"label": src,
                                   "child_vols": src_vol, "parent_vols": vol})

        vol_row   = {"label": mkt, "values": vol_display}
        share_row = {"label": mkt, "values": share}

        if vol_children:
            vol_row["children"] = vol_children
            norm = normalize_shares_to_100(share_children_vals, n)
            share_row["children"] = [
                {"label": share_children_labels[i], "values": norm[i]}
                for i in range(len(norm))
            ]

        market_vol_rows.append(vol_row)
        market_share_rows.append(share_row)

        mv_trow = {"label": mkt, "monthly_values": vol}
        if mv_child_rows:
            mv_trow["children"] = mv_child_rows
        mv_table_rows.append(mv_trow)

        ms_trow = {"label": mkt, "child_vols": vol, "parent_vols": total_vals}
        if ms_child_rows:
            ms_trow["children"] = ms_child_rows
        ms_table_rows.append(ms_trow)

    mv_chart = {"months": months, "forecast_start_index": split_idx,
                "series": vol_chart_series}
    mv_table = {"type": "hierarchy",
                "rows": [overall_vol_row] + market_vol_rows}

    ms_chart = {"months": months, "forecast_start_index": split_idx,
                "series": share_chart_series}
    ms_table = {"type": "hierarchy",
                "rows": [overall_share_row] + market_share_rows}

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart, mv_table, months, split_idx,
                mv_series_data, mv_table_rows, "hierarchy"
            )
        },
        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart, ms_table, months, split_idx,
                ms_series_data, ms_table_rows, "hierarchy"
            )
        },
        "_selected": {
            "months": months,
            "split_idx": split_idx,
            "volume": market_totals.get(selected_market, [0.0] * n),
            "parent_volume": total_vals,
        },
    }
def fetch_forecast_scenario_with_fallback(cur, ta, market, source, product, metric, scenario):
    """
    Try the requested scenario first. If no row exists for that exact
    scenario, fall back to BASE.

    This matters because non-BASE scenarios generally only override
    market-level and source-level shares, not every source x product
    combination -- those still need to come from BASE's mix.
    """
    data = fetch_forecast_scenario(cur, ta, market, source, product, metric, scenario)
    if data is not None:
        return data

    if scenario.upper() != "BASE":
        return fetch_forecast_scenario(cur, ta, market, source, product, metric, "BASE")

    return None

def build_product_distribution(cur, ta, scenario, markets, total_vals, months, split_idx, start, end,selected_product):
    """
    Product distribution — volume and share split across products.

    prod_vol_map accumulates RAW floats throughout.
    Monthly display rounds at output; yearly sums raws then rounds once.
    Yearly share = sum(prod_raw_in_year) / sum(total_raw_in_year) * 100.
    """
    products  = get_products(cur, ta)
    n         = len(total_vals)
    all_years = get_ordered_years(months)

    # Accumulate raw floats
    prod_vol_map = {p: [0.0] * n for p in products}

    for mkt in markets:
        mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
        if not mkt_d:
            continue

        mkt_series = build_series(mkt_d, start, end)
        mkt_vol    = build_volume_from_share(total_vals, mkt_series["values"])  # raw

        for prod in products:

            if mkt == "Retail":
                d = fetch_forecast_scenario(cur, ta, mkt, None, prod, "market_share", scenario)
                if not d:
                    continue
                s        = build_series(d, start, end)
                prod_vol = build_volume_from_share(mkt_vol, s["values"])        # raw
                for i in range(min(len(prod_vol), n)):
                    prod_vol_map[prod][i] += prod_vol[i]

            else:
                sources = get_sources(cur, ta, mkt)
                for src in sources:
                    src_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, "ALL", "market_share", scenario)
                    if not src_d:
                        continue
                    src_series = build_series(src_d, start, end)
                    src_vol    = build_volume_from_share(mkt_vol, src_series["values"])

                    prod_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, prod, "market_share", scenario)
                    if not prod_d:
                        continue
                    prod_series = build_series(prod_d, start, end)
                    prod_vol    = build_volume_from_share(src_vol, prod_series["values"])

                    for i in range(min(len(prod_vol), n)):
                        prod_vol_map[prod][i] += prod_vol[i]

    prod_labels = list(prod_vol_map.keys())
    raw_vols    = [prod_vol_map[p] for p in prod_labels]
    norm_shares = normalize_shares_to_100(raw_vols, n)

    # Monthly display rows (round here, display only)
    overall_vol_row   = {"label": "Overall", "values": round_volume(total_vals)}
    overall_share_row = {"label": "Overall", "values": [100.0] * n}

    mv_chart = {
        "months": months, "forecast_start_index": split_idx,
        "series": [
            {"label": p,
             "history":  split_series(round_volume(prod_vol_map[p]), split_idx)[0],
             "forecast": split_series(round_volume(prod_vol_map[p]), split_idx)[1]}
            for p in prod_labels if p == selected_product
        ]
    }
    mv_table = {
        "type": "flat",
        "rows": [overall_vol_row] + [
            {"label": p, "values": round_volume(prod_vol_map[p])}
            for p in prod_labels
        ]
    }

    ms_chart = {
        "months": months, "forecast_start_index": split_idx,
        "series": [
            {"label": p,
             "history":  split_series(norm_shares[i], split_idx)[0],
             "forecast": split_series(norm_shares[i], split_idx)[1]}
            for i, p in enumerate(prod_labels) if p == selected_product
        ]
    }
    ms_table = {
        "type": "flat",
        "rows": [overall_share_row] + [
            {"label": p, "values": norm_shares[i]}
            for i, p in enumerate(prod_labels)
        ]
    }

    # Yearly descriptors — pass raw floats
    mv_series_data = [{"label": p, "monthly_values": prod_vol_map[p]}
                       for p in prod_labels if p == selected_product]
    mv_table_rows  = (
        [{"label": "Overall", "monthly_values": total_vals}] +
        [{"label": p, "monthly_values": prod_vol_map[p]} for p in prod_labels]
    )

    ms_series_data = [
        {"label": p, "child_vols": prod_vol_map[p], "parent_vols": total_vals}
        for p in prod_labels if p == selected_product
    ]
    ms_table_rows = (
        [{"label": "Overall", "fixed_values": [100.0] * len(all_years)}] +
        [{"label": p, "child_vols": prod_vol_map[p], "parent_vols": total_vals}
         for p in prod_labels]
    )

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart, mv_table, months, split_idx,
                mv_series_data, mv_table_rows, "flat"
            )
        },
        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart, ms_table, months, split_idx,
                ms_series_data, ms_table_rows, "flat"
            )
        },
        "_selected": {
            "months": months,
            "split_idx": split_idx,
            "volume": prod_vol_map.get(selected_product, [0.0] * n),
            "parent_volume": total_vals,
        }
    }


def build_market_product(cur, ta, scenario, markets, products, total_vals, months,
                         split_idx, start, end, selected_market,selected_product):
    """
    Market -> Product breakdown.

    mp_vol accumulates RAW floats.
    Monthly display rounds at output.
    Yearly product share within market = sum(prod_raw) / sum(mkt_raw) * 100.
    """
    n         = len(total_vals)
    all_years = get_ordered_years(months)
    mp_vol    = {}
    market_totals = {}

    for mkt in markets:
        mp_vol[mkt] = {}

        mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
        if mkt_d:
            s       = build_series(mkt_d, start, end)
            min_len = min(n, len(s["values"]))
            mkt_vol = build_volume_from_share(total_vals[:min_len], s["values"][:min_len])  # raw
            mkt_vol = mkt_vol + [0.0] * (n - len(mkt_vol))
        else:
            mkt_vol = [0.0] * n

        market_totals[mkt] = mkt_vol

        for prod in products:

            if mkt == "Retail":
                d = fetch_forecast_scenario(cur, ta, mkt, None, prod, "market_share", scenario)
                if not d:
                    continue
                s       = build_series(d, start, end)
                min_len = min(n, len(s["values"]))
                vol     = build_volume_from_share(
                    market_totals[mkt][:min_len], s["values"][:min_len])  # raw

            else:
                total_prod_vol = [0.0] * n
                sources        = get_sources(cur, ta, mkt)

                for src in sources:
                    src_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, "ALL", "market_share", scenario)
                    if not src_d:
                        continue
                    src_series = build_series(src_d, start, end)

                    prod_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, prod, "market_share", scenario)
                    if not prod_d:
                        continue
                    prod_series = build_series(prod_d, start, end)

                    min_len = min(len(market_totals[mkt]),
                                  len(src_series["values"]),
                                  len(prod_series["values"]))

                    src_vol  = build_volume_from_share(
                        market_totals[mkt][:min_len], src_series["values"][:min_len])
                    prod_vol = build_volume_from_share(src_vol, prod_series["values"][:min_len])

                    for i in range(min_len):
                        total_prod_vol[i] += prod_vol[i]

                vol = total_prod_vol

            vol = vol + [0.0] * (n - len(vol))
            mp_vol[mkt][prod] = vol   # raw floats

    # --- CHART: selected market only ---
    vol_chart_series   = []
    share_chart_series = []
    mv_series_data     = []
    ms_series_data     = []

    if selected_market in mp_vol:
        mkt     = selected_market
        mkt_vol = market_totals[mkt]

        for prod in products:
            if prod not in mp_vol[mkt] or prod != selected_product:
                continue
            vol          = mp_vol[mkt][prod]
            vol_display  = round_volume(vol)
            h_v, f_v     = split_series(vol_display, split_idx)
            vol_chart_series.append({"label": f"{mkt} - {prod}", "market": mkt, "product": prod,
                                     "history": h_v, "forecast": f_v})
            mv_series_data.append({"label": f"{mkt} - {prod}", "market": mkt, "product": prod,
                                   "monthly_values": vol})

        prod_vols_in_mkt   = [mp_vol[mkt][p] for p in products if p in mp_vol[mkt]]
        prod_labels_in_mkt = [p for p in products if p in mp_vol[mkt]]
        norm_shares        = normalize_shares_to_100(prod_vols_in_mkt, n) if prod_vols_in_mkt else []

        for c, prod in enumerate(prod_labels_in_mkt):
            if prod != selected_product:
                continue
            sh, sf = split_series(norm_shares[c], split_idx)
            share_chart_series.append({"label": f"{mkt} - {prod}", "market": mkt, "product": prod,
                                       "history": sh, "forecast": sf})
            ms_series_data.append({
                "label": f"{mkt} - {prod}", "market": mkt, "product": prod,
                "child_vols":  mp_vol[mkt][prod],
                "parent_vols": mkt_vol
            })

    # --- TABLE: full hierarchy ---
    vol_table_rows   = []
    share_table_rows = []
    mv_table_rows    = []
    ms_table_rows    = []

    for mkt in markets:
        mkt_vol            = market_totals[mkt]
        prod_vols_in_mkt   = [mp_vol[mkt][p] for p in products if p in mp_vol[mkt]]
        prod_labels_in_mkt = [p for p in products if p in mp_vol[mkt]]
        norm_shares        = normalize_shares_to_100(prod_vols_in_mkt, n) if prod_vols_in_mkt else []

        vol_children   = [{"label": prod_labels_in_mkt[c],
                           "values": round_volume(prod_vols_in_mkt[c])}
                          for c in range(len(prod_labels_in_mkt))]
        share_children = [{"label": prod_labels_in_mkt[c], "values": norm_shares[c]}
                          for c in range(len(prod_labels_in_mkt))]

        vol_row   = {"label": mkt, "values": round_volume(mkt_vol)}
        share_row = {"label": mkt, "values": [100.0] * n}
        if vol_children:
            vol_row["children"]   = vol_children
            share_row["children"] = share_children

        vol_table_rows.append(vol_row)
        share_table_rows.append(share_row)

        mv_table_rows.append({
            "label":          mkt,
            "monthly_values": mkt_vol,
            "children": [
                {"label": prod_labels_in_mkt[c], "monthly_values": prod_vols_in_mkt[c]}
                for c in range(len(prod_labels_in_mkt))
            ]
        })
        ms_table_rows.append({
            "label":        mkt,
            "fixed_values": [100.0] * len(all_years),
            "children": [
                {"label":       prod_labels_in_mkt[c],
                 "child_vols":  prod_vols_in_mkt[c],
                 "parent_vols": mkt_vol}
                for c in range(len(prod_labels_in_mkt))
            ]
        })

    mv_chart = {"months": months, "forecast_start_index": split_idx,
                "series": vol_chart_series}
    mv_table = {"type": "hierarchy", "rows": vol_table_rows}
    ms_chart = {"months": months, "forecast_start_index": split_idx,
                "series": share_chart_series}
    ms_table = {"type": "hierarchy", "rows": share_table_rows}

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart, mv_table, months, split_idx,
                mv_series_data, mv_table_rows, "hierarchy"
            )
        },
        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart, ms_table, months, split_idx,
                ms_series_data, ms_table_rows, "hierarchy"
            )
        },
        "_selected": {
            "months": months,
            "split_idx": split_idx,
            "volume": mp_vol.get(selected_market, {}).get(selected_product, [0.0] * n),
            "parent_volume": market_totals.get(selected_market, total_vals),
        }
    }


def build_product_market(cur, ta, scenario, markets, products, total_vals, months,
                         split_idx, start, end, selected_product,selected_market):
    """
    Product -> Market breakdown.

    pm_vol accumulates RAW floats.
    Monthly display rounds at output.
    Yearly market share within product = sum(mkt_raw) / sum(prod_raw) * 100.
    """
    n         = len(total_vals)
    all_years = get_ordered_years(months)
    pm_vol    = {}
    product_totals = {}

    for prod in products:
        pm_vol[prod] = {}
        prod_total   = [0.0] * n

        for mkt in markets:

            if mkt == "Retail":
                d = fetch_forecast_scenario(cur, ta, mkt, None, prod, "market_share", scenario)
                if not d:
                    continue
                s = build_series(d, start, end)

                mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
                if not mkt_d:
                    continue
                mkt_series = build_series(mkt_d, start, end)

                min_len = min(len(total_vals), len(mkt_series["values"]), len(s["values"]))
                mkt_vol = build_volume_from_share(
                    total_vals[:min_len], mkt_series["values"][:min_len])  # raw
                vol     = build_volume_from_share(mkt_vol, s["values"][:min_len])  # raw

            else:
                total_prod_vol = [0.0] * n

                mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
                if not mkt_d:
                    continue
                mkt_series  = build_series(mkt_d, start, end)
                min_len_mkt = min(len(total_vals), len(mkt_series["values"]))
                mkt_vol     = build_volume_from_share(
                    total_vals[:min_len_mkt], mkt_series["values"][:min_len_mkt])

                sources = get_sources(cur, ta, mkt)
                for src in sources:
                    src_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, "ALL", "market_share", scenario)
                    if not src_d:
                        continue
                    src_series = build_series(src_d, start, end)

                    prod_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, prod, "market_share", scenario)
                    if not prod_d:
                        continue
                    prod_series = build_series(prod_d, start, end)

                    min_len  = min(len(mkt_vol),
                                   len(src_series["values"]),
                                   len(prod_series["values"]))
                    src_vol  = build_volume_from_share(
                        mkt_vol[:min_len], src_series["values"][:min_len])
                    prod_vol = build_volume_from_share(
                        src_vol, prod_series["values"][:min_len])

                    for i in range(min_len):
                        total_prod_vol[i] += prod_vol[i]

                vol = total_prod_vol

            vol = vol + [0.0] * (n - len(vol))
            pm_vol[prod][mkt] = vol   # raw floats

            for i in range(n):
                prod_total[i] += vol[i]

        product_totals[prod] = prod_total   # raw floats

    # --- CHART: selected product only ---
    vol_chart_series   = []
    share_chart_series = []
    mv_series_data     = []
    ms_series_data     = []

    if selected_product in pm_vol:
        prod       = selected_product
        prod_total = product_totals[prod]

        for mkt in markets:
            if mkt not in pm_vol[prod] or mkt != selected_market:
                continue
            vol         = pm_vol[prod][mkt]
            vol_display = round_volume(vol)
            h_v, f_v    = split_series(vol_display, split_idx)
            vol_chart_series.append({"label": f"{prod} - {mkt}", "product": prod, "market": mkt,
                                     "history": h_v, "forecast": f_v})
            mv_series_data.append({"label": f"{prod} - {mkt}", "product": prod, "market": mkt,
                                   "monthly_values": vol})

        mkt_vols    = [pm_vol[prod][mkt] for mkt in markets if mkt in pm_vol[prod]]
        labels      = [mkt for mkt in markets if mkt in pm_vol[prod]]
        norm_shares = normalize_shares_to_100(mkt_vols, n) if mkt_vols else []

        for i, mkt in enumerate(labels):
            if mkt != selected_market:
                continue
            sh, sf = split_series(norm_shares[i], split_idx)
            share_chart_series.append({"label": f"{prod} - {mkt}", "product": prod, "market": mkt,
                                       "history": sh, "forecast": sf})
            ms_series_data.append({
                "label": f"{prod} - {mkt}", "product": prod, "market": mkt,
                "child_vols":  pm_vol[prod][mkt],
                "parent_vols": prod_total
            })

    # --- TABLE: full hierarchy ---
    vol_table_rows   = []
    share_table_rows = []
    mv_table_rows    = []
    ms_table_rows    = []

    for prod in products:
        prod_total  = product_totals[prod]
        mkt_vols    = [pm_vol[prod][mkt] for mkt in markets if mkt in pm_vol[prod]]
        labels      = [mkt for mkt in markets if mkt in pm_vol[prod]]
        norm_shares = normalize_shares_to_100(mkt_vols, n) if mkt_vols else []

        vol_children   = [{"label": labels[i], "values": round_volume(mkt_vols[i])}
                          for i in range(len(labels))]
        share_children = [{"label": labels[i], "values": norm_shares[i]}
                          for i in range(len(labels))]

        vol_row   = {"label": prod, "values": round_volume(prod_total), "children": vol_children}
        share_row = {"label": prod, "values": [100.0] * n,              "children": share_children}

        vol_table_rows.append(vol_row)
        share_table_rows.append(share_row)

        mv_table_rows.append({
            "label":          prod,
            "monthly_values": prod_total,
            "children": [
                {"label": labels[i], "monthly_values": mkt_vols[i]}
                for i in range(len(labels))
            ]
        })
        ms_table_rows.append({
            "label":        prod,
            "fixed_values": [100.0] * len(all_years),
            "children": [
                {"label":       labels[i],
                 "child_vols":  mkt_vols[i],
                 "parent_vols": prod_total}
                for i in range(len(labels))
            ]
        })

    mv_chart = {"months": months, "forecast_start_index": split_idx,
                "series": vol_chart_series}
    mv_table = {"type": "hierarchy", "rows": vol_table_rows}
    ms_chart = {"months": months, "forecast_start_index": split_idx,
                "series": share_chart_series}
    ms_table = {"type": "hierarchy", "rows": share_table_rows}

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart, mv_table, months, split_idx,
                mv_series_data, mv_table_rows, "hierarchy"
            )
        },
        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart, ms_table, months, split_idx,
                ms_series_data, ms_table_rows, "hierarchy"
            )
        },
        "_selected": {
            "months": months,
            "split_idx": split_idx,
            "volume": pm_vol.get(selected_product, {}).get(selected_market, [0.0] * n),
            "parent_volume": product_totals.get(selected_product, total_vals),
        }
    }


def build_scenario_market_analysis(cur, ta, scenario, start, end,
                                   selected_market, selected_product):
    total_data = fetch_forecast_scenario(
        cur, ta, "ALL", "ALL", "ALL", "market_volume", scenario)
    if not total_data:
        return {"total_market_volume": {"market_volume": {}, "market_share": {}}}

    total      = build_series(total_data, start, end)
    total_vals = total["values"]   # raw floats from build_series
    months     = total["months"]
    split_idx  = total["split_idx"]

    markets  = get_markets(cur, ta)
    products = get_products(cur, ta)

    return {
        "total_market_volume": build_total_market_volume(total_vals, months, split_idx, scenario),
        "market_distribution": build_market_distribution(
            cur, ta, scenario, total_vals, months, split_idx, start, end, selected_market),
        "product_distribution": build_product_distribution(
            cur, ta, scenario, markets, total_vals, months, split_idx, start, end, selected_product),
        "market_product": build_market_product(
            cur, ta, scenario, markets, products, total_vals, months,
            split_idx, start, end, selected_market, selected_product),
        "product_market": build_product_market(
            cur, ta, scenario, markets, products, total_vals, months,
            split_idx, start, end, selected_product, selected_market)
    }

def build_comparison_volume_chart(entries):
    months, split_idx = entries[0]["months"], entries[0]["split_idx"]
    series = []
    for e in entries:
        disp = round_volume(e["volume"])
        h, f = split_series(disp, split_idx)
        series.append({"label": e["label"], "history": h, "forecast": f})
    return {"months": months, "forecast_start_index": split_idx, "series": series}


def build_comparison_volume_chart_yearly(entries):
    months, split_idx = entries[0]["months"], entries[0]["split_idx"]
    all_years = get_ordered_years(months)
    y_split = yearly_forecast_start_index(months, split_idx)
    series = []
    for e in entries:
        _, yvals = aggregate_yearly_volume(months, e["volume"])
        yh, yf = split_series(yvals, y_split)
        series.append({"label": e["label"], "history": yh, "forecast": yf})
    return {"years": all_years, "forecast_start_index": y_split, "series": series}


def build_comparison_share_chart(entries):
    months, split_idx = entries[0]["months"], entries[0]["split_idx"]
    series = []
    for e in entries:
        n = len(e["volume"])
        vals = [safe_pct(e["volume"][i], e["parent_volume"][i]) for i in range(n)]
        h, f = split_series(vals, split_idx)
        series.append({"label": e["label"], "history": h, "forecast": f})
    return {"months": months, "forecast_start_index": split_idx, "series": series}


def build_comparison_share_chart_yearly(entries):
    months, split_idx = entries[0]["months"], entries[0]["split_idx"]
    all_years = get_ordered_years(months)
    y_split = yearly_forecast_start_index(months, split_idx)
    series = []
    for e in entries:
        _, yvals = aggregate_yearly_share_from_volumes(months, e["volume"], e["parent_volume"])
        yh, yf = split_series(yvals, y_split)
        series.append({"label": e["label"], "history": yh, "forecast": yf})
    return {"years": all_years, "forecast_start_index": y_split, "series": series}
# =========================================================
# ================= MAIN FUNCTION ==========================
# =========================================================

# def build_apply_scenario_response(cur, payload, config):

#     ta    = payload.ta_name
#     flt   = payload.selected_filter
#     start = flt.start_date
#     end   = flt.end_date

#     available_scenarios = get_scenarios(cur, ta)
#     active_scenario     = available_scenarios[0]

#     scenarios_block = {}

#     for scenario in available_scenarios:

#         if scenario == active_scenario:

#             market_analysis = build_scenario_market_analysis(
#                 cur, ta, scenario, start, end, flt.market, flt.product
#             )

#             scenario_block = {
#                 "factors": build_factors(cur, ta, scenario),
#                 "market_analysis": market_analysis
#             }

#         else:

#             total_data = fetch_forecast_scenario(
#                 cur,
#                 ta,
#                 "ALL",
#                 "ALL",
#                 "ALL",
#                 "market_volume",
#                 scenario
#             )

#             total = build_series(total_data, start, end)

#             scenario_block = {
#                 "market_analysis": {
#                     "total_market_volume": build_total_market_volume(
#                         total["values"],
#                         total["months"],
#                         total["split_idx"],
#                         scenario
#                     )
#                 }
#             }

#         scenarios_block[scenario] = scenario_block

#     return {
#         "ta_name": ta,
#         "selected_filter": {
#             "start_date": start,
#             "end_date":   end,
#             "market":     flt.market,
#             "product":    flt.product
#         },
#         "available_scenarios": available_scenarios,
#         "active_scenario":     active_scenario,
#         "scenarios":           scenarios_block
#     }

def build_apply_scenario_response(
    cur,
    payload,
    config,
):
    ta = payload.ta_name
    flt = payload.selected_filter

    start = flt.start_date
    end = flt.end_date

    available_scenarios = get_scenarios(
        cur,
        ta,
    )

    requested_scenario = getattr(
        payload,
        "scenario_name",
        None,
    )

    active_scenario = (
        requested_scenario
        if requested_scenario in available_scenarios
        else available_scenarios[0]
    )

    scenarios_block = {}

    for scenario in available_scenarios:

        market_analysis = (
            build_scenario_market_analysis(
                cur,
                ta,
                scenario,
                start,
                end,
                flt.market,
                flt.product,
            )
        )

        scenarios_block[scenario] = {
            "factors": build_factors(
                cur,
                ta,
                scenario,
            ),
            "market_analysis": market_analysis,
        }

    breakdown_keys = [
        "market_distribution",
        "product_distribution",
        "market_product",
        "product_market",
    ]

    comparison_charts = {}

    for bk in breakdown_keys:

        vol_entries = []
        share_entries = []

        for scenario in available_scenarios:
            ma = scenarios_block[scenario]["market_analysis"].get(bk, {})
            sel = ma.get("_selected")
            if not sel:
                continue

            vol_entries.append({"label": scenario, **sel})
            share_entries.append({"label": scenario, **sel})

        # clean up the internal marker regardless of whether
        # we had enough data to build a comparison chart
        for scenario in available_scenarios:
            ma = scenarios_block[scenario]["market_analysis"].get(bk, {})
            ma.pop("_selected", None)

        if not vol_entries:
            continue

        comparison_charts[bk] = {
            "market_volume": {
                "monthly": build_comparison_volume_chart(vol_entries),
                "yearly": build_comparison_volume_chart_yearly(vol_entries),
            },
            "market_share": {
                "monthly": build_comparison_share_chart(share_entries),
                "yearly": build_comparison_share_chart_yearly(share_entries),
            },
        }

    return {
        "ta_name": ta,
        "selected_filter": {
            "start_date": start,
            "end_date": end,
            "market": flt.market,
            "product": flt.product,
        },
        "available_scenarios": (
            available_scenarios
        ),
        "active_scenario": active_scenario,
        "scenarios": scenarios_block,
        "comparison_charts": comparison_charts,
    }