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


# def get_products(cur, ta):
#     cur.execute("""
#         SELECT DISTINCT product
#         FROM raw_hiv_treat.forecast_outputs
#         WHERE ta_name = %s AND product != 'ALL'
#     """, (ta,))
#     return [r[0] for r in cur.fetchall()]

BASELINE_SCENARIO = "Base"


def get_products(cur, ta, scenario=None):
    """Products with rows in this TA.

    Scoped to `scenario` for the baseline only -- unscoped, a product
    materialized in another scenario shows up in Base's tables at 0%.
    Every other scenario keeps the TA-wide list.

    `scenario` is an explicit argument on purpose. It was previously read
    from a context variable so call sites could stay unchanged, and that
    silently returned the WRONG scenario's product list on any path that
    didn't set it -- which is how t11 ended up rendering Base's three
    products instead of its own four."""
    query = """
        SELECT DISTINCT product
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s AND product != 'ALL'
    """
    params = [ta]

    if scenario and str(scenario).strip().lower() == BASELINE_SCENARIO.lower():
        query += " AND scenario_name = %s"
        params.append(scenario)

    cur.execute(query, params)
    result = [r[0] for r in cur.fetchall()]
    # print("GET_PRODUCTS", repr(scenario), "scoped:", "scenario_name" in query, "->", result)
    return result


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

    # print("================================")
    # print("Market-volume factors:", volume_factors)
    # print("Market-share factors:", factors_data)
    # print("================================")

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
    # print(
    #     "build_total_market_volume called, scenario_label=",
    #     scenario_label
    # )
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


def build_market_distribution(cur, ta, scenario, total_vals, months, split_idx, start, end, selected_market):
    """
    Market distribution — volume and share split across markets.

    total_vals: raw floats.
    All market volumes are raw floats throughout; rounded only for monthly display.
    Yearly share = sum(mkt_raw_in_year) / sum(total_raw_in_year) * 100.
    Source children share = sum(src_raw_in_year) / sum(total_raw_in_year) * 100
        (share of the OVERALL total, so siblings sum to their parent market's
        own share of total — e.g. Kaiser% + IQVIA% + ADAP% + Federal% == Non-retail%).
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

        # ------------------------------------------------------------
        # Sources
        # ------------------------------------------------------------

        sources = get_sources(
            cur,
            ta,
            mkt,
        )

        source_labels = []
        source_share_series = []

        for src in sources:

            sd = fetch_forecast_scenario(
                cur,
                ta,
                mkt,
                src,
                "ALL",
                "market_share",
                scenario,
            )

            if not sd:
                continue

            ss = build_series(
                sd,
                start,
                end,
            )

            src_share = list(
                ss["values"]
            )

            # Ensure same length as market series
            src_share = (
                src_share
                + [0.0] * (n - len(src_share))
            )[:n]

            source_labels.append(
                src
            )

            source_share_series.append(
                src_share
            )


        vol_row = {
            "label": mkt,
            "values": vol_display,
        }

        share_row = {
            "label": mkt,
            "values": share,
        }

        mv_child_rows = []
        ms_child_rows = []


        if source_share_series:

            # ========================================================
            # 1. Normalize SOURCE SHARES within the market
            #
            # For every month:
            #
            # Kaiser + IQVIA + ADAP + Federal = 100%
            #
            # inside Non-retail.
            # ========================================================

            normalized_source_shares = [
                [0.0] * n
                for _ in source_share_series
            ]

            for t in range(n):

                current_total = sum(
                    max(
                        0.0,
                        float(
                            source_share_series[c][t]
                            or 0
                        ),
                    )
                    for c in range(
                        len(source_share_series)
                    )
                )

                if current_total > 0:

                    allocated_share = 0.0

                    for c in range(
                        len(source_share_series)
                    ):

                        is_last = (
                            c
                            == len(source_share_series) - 1
                        )

                        if is_last:

                            normalized_share = round(
                                100.0
                                - allocated_share,
                                10,
                            )

                        else:

                            raw_share = max(
                                0.0,
                                float(
                                    source_share_series[c][t]
                                    or 0
                                ),
                            )

                            normalized_share = round(
                                raw_share
                                / current_total
                                * 100.0,
                                10,
                            )

                            allocated_share += (
                                normalized_share
                            )

                        normalized_source_shares[
                            c
                        ][
                            t
                        ] = normalized_share

                else:

                    # No source distribution available.
                    # Keep all source values at zero.
                    for c in range(
                        len(source_share_series)
                    ):
                        normalized_source_shares[
                            c
                        ][
                            t
                        ] = 0.0

            # ========================================================
            # 2. Calculate raw source volumes from FIXED market volume
            # ========================================================

            child_raw = [
                [0.0] * n
                for _ in normalized_source_shares
            ]

            for t in range(n):

                allocated_volume = 0.0

                for c in range(
                    len(normalized_source_shares)
                ):

                    is_last = (
                        c
                        == len(normalized_source_shares) - 1
                    )

                    if is_last:

                        # Last source receives floating-point residual,
                        # guaranteeing:
                        #
                        # sum(source volumes) == market volume
                        source_volume = (
                            float(vol[t])
                            - allocated_volume
                        )

                    else:

                        source_volume = (
                            float(vol[t])
                            * normalized_source_shares[c][t]
                            / 100.0
                        )

                        allocated_volume += (
                            source_volume
                        )

                    child_raw[
                        c
                    ][
                        t
                    ] = source_volume

            # ========================================================
            # 3. Build DISPLAY volumes
            #
            # Important:
            # rounded children must also equal rounded parent.
            # ========================================================

            child_display = [
                [0] * n
                for _ in child_raw
            ]

            for t in range(n):

                parent_display_value = round(
                    float(vol[t])
                )

                allocated_display = 0

                for c in range(
                    len(child_raw)
                ):

                    is_last = (
                        c
                        == len(child_raw) - 1
                    )

                    if is_last:

                        display_value = (
                            parent_display_value
                            - allocated_display
                        )

                    else:

                        display_value = round(
                            child_raw[c][t]
                        )

                        allocated_display += (
                            display_value
                        )

                    child_display[
                        c
                    ][
                        t
                    ] = display_value

            # ========================================================
            # 4. Volume children
            # ========================================================

            vol_row["children"] = [
                {
                    "label": source_labels[c],
                    "values": child_display[c],
                }
                for c in range(
                    len(source_labels)
                )
            ]

            # ========================================================
            # 5. Share children
            #
            # Your existing business rule:
            #
            # source share is contribution to OVERALL,
            # not percentage inside Non-retail.
            #
            # Therefore source children add to Non-retail's
            # share of Overall.
            # ========================================================

            share_row["children"] = [
                {
                    "label": source_labels[c],

                    "values": [
                        safe_pct(
                            child_raw[c][t],
                            total_vals[t],
                        )
                        for t in range(n)
                    ],
                }
                for c in range(
                    len(source_labels)
                )
            ]

            # ========================================================
            # 6. Yearly source rows use RAW volumes
            # ========================================================

            for c in range(
                len(source_labels)
            ):

                mv_child_rows.append(
                    {
                        "label": (
                            source_labels[c]
                        ),
                        "monthly_values": (
                            child_raw[c]
                        ),
                    }
                )

                ms_child_rows.append(
                    {
                        "label": (
                            source_labels[c]
                        ),
                        "child_vols": (
                            child_raw[c]
                        ),
                        "parent_vols": (
                            total_vals
                        ),
                    }
                )

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

def normalize_shares_with_pins(children_values_list, labels, pinned_shares, n):
    """
    Like normalize_shares_to_100, but any product with a directly-saved
    override share (pinned_shares[label] is not None at index t) keeps
    that exact value. The remaining ("free") products are normalized
    proportionally by volume to fill whatever share is left over
    (100 - sum of pinned shares at that index), so all siblings still
    sum to 100 at every time index.
 
    pinned_shares: dict label -> list[float] | None
    """
    num = len(labels)
    normalized = [[0.0] * n for _ in range(num)]
 
    for t in range(n):
        pinned_total = 0.0
        free_indices = []
        for c in range(num):
            pin = pinned_shares.get(labels[c])
            if pin is not None and t < len(pin):
                normalized[c][t] = pin[t]
                pinned_total += pin[t]
            else:
                free_indices.append(c)
 
        remaining = max(0.0, 100.0 - pinned_total)
        free_total_vol = sum(
            children_values_list[c][t] if t < len(children_values_list[c]) else 0
            for c in free_indices
        )
        for c in free_indices:
            val = children_values_list[c][t] if t < len(children_values_list[c]) else 0
            if free_total_vol > 0:
                normalized[c][t] = round((val / free_total_vol) * remaining, 2)
            else:
                normalized[c][t] = 0.0
 
    return normalized

def build_product_distribution(
    cur,
    ta,
    scenario,
    markets,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_product,
):
    """
    Product distribution -- volume and share split across products,
    blended across every market/source.

    Rules
    -----
    - Direct Product Level overrides are pinned exactly.
    - Non-overridden products are derived from market/source structure.
    - Shares are normalized to exactly 100%.
    - Product volumes are rebuilt from normalized shares.
    - Product volumes therefore add exactly to Overall.
    """

    products = get_products(cur, ta)
    n = len(total_vals)
    all_years = get_ordered_years(months)

    prod_vol_map = {
        p: [0.0] * n
        for p in products
    }

    override_share_map = {
        p: None
        for p in products
    }

    # =====================================================
    # 1. Pull saved Product Level overrides
    # =====================================================

    for prod in products:

        override_d = (
            fetch_forecast_scenario_with_fallback(
                cur,
                ta,
                "ALL",
                None,
                prod,
                "market_share",
                scenario,
            )
        )

        if not override_d:
            continue

        s = build_series(
            override_d,
            start,
            end,
        )

        share = (
            s["values"]
            + [0.0] * n
        )[:n]

        override_share_map[
            prod
        ] = share

        prod_vol_map[
            prod
        ] = build_volume_from_share(
            total_vals,
            share,
        )

    # =====================================================
    # 2. Compute non-overridden products
    # =====================================================

    for mkt in markets:

        mkt_d = fetch_forecast_scenario(
            cur,
            ta,
            mkt,
            None,
            "ALL",
            "market_share",
            scenario,
        )

        if not mkt_d:
            continue

        mkt_series = build_series(
            mkt_d,
            start,
            end,
        )

        mkt_share = (
            mkt_series["values"]
            + [0.0] * n
        )[:n]

        mkt_vol = build_volume_from_share(
            total_vals,
            mkt_share,
        )

        for prod in products:

            # Product Level override is authoritative.
            if (
                override_share_map[
                    prod
                ]
                is not None
            ):
                continue

            # =============================================
            # Retail
            # =============================================

            if mkt == "Retail":

                d = (
                    fetch_forecast_scenario_with_fallback(
                        cur,
                        ta,
                        mkt,
                        None,
                        prod,
                        "market_share",
                        scenario,
                    )
                )

                if not d:
                    continue

                s = build_series(
                    d,
                    start,
                    end,
                )

                prod_share = (
                    s["values"]
                    + [0.0] * n
                )[:n]

                prod_vol = (
                    build_volume_from_share(
                        mkt_vol,
                        prod_share,
                    )
                )

                for i in range(
                    min(
                        len(prod_vol),
                        n,
                    )
                ):
                    prod_vol_map[
                        prod
                    ][i] += (
                        prod_vol[i]
                    )

            # =============================================
            # Non-retail / source hierarchy
            # =============================================

            else:

                sources = get_sources(
                    cur,
                    ta,
                    mkt,
                )

                for src in sources:

                    src_d = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            mkt,
                            src,
                            "ALL",
                            "market_share",
                            scenario,
                        )
                    )

                    if not src_d:
                        continue

                    src_series = build_series(
                        src_d,
                        start,
                        end,
                    )

                    src_share = (
                        src_series["values"]
                        + [0.0] * n
                    )[:n]

                    src_vol = (
                        build_volume_from_share(
                            mkt_vol,
                            src_share,
                        )
                    )

                    prod_d = (
                        fetch_forecast_scenario_with_fallback(
                            cur,
                            ta,
                            mkt,
                            src,
                            prod,
                            "market_share",
                            scenario,
                        )
                    )

                    if not prod_d:
                        continue

                    prod_series = build_series(
                        prod_d,
                        start,
                        end,
                    )

                    prod_share = (
                        prod_series["values"]
                        + [0.0] * n
                    )[:n]

                    prod_vol = (
                        build_volume_from_share(
                            src_vol,
                            prod_share,
                        )
                    )

                    for i in range(
                        min(
                            len(prod_vol),
                            n,
                        )
                    ):
                        prod_vol_map[
                            prod
                        ][i] += (
                            prod_vol[i]
                        )

    # =====================================================
    # 3. Normalize Product shares
    # =====================================================

    prod_labels = list(
        prod_vol_map.keys()
    )

    raw_vols = [
        prod_vol_map[p]
        for p in prod_labels
    ]

    norm_shares = (
        normalize_shares_with_pins(
            raw_vols,
            prod_labels,
            override_share_map,
            n,
        )
    )

    # =====================================================
    # 4. Rebuild Product volumes FROM normalized shares
    #
    # This makes:
    #
    #     sum(products) == Overall
    #
    # exactly for every month.
    # =====================================================

    normalized_prod_vol_map = {
        p: [0.0] * n
        for p in prod_labels
    }

    for t in range(n):

        overall_volume = float(
            total_vals[t]
            or 0
        )

        allocated_total = 0.0

        for position, product_name in enumerate(
            prod_labels
        ):

            is_last = (
                position
                == len(prod_labels) - 1
            )

            # Last product receives residual.
            if is_last:

                product_volume = round(
                    overall_volume
                    - allocated_total,
                    10,
                )

            else:

                product_share = float(
                    norm_shares[
                        position
                    ][
                        t
                    ]
                    or 0
                )

                product_volume = round(
                    overall_volume
                    * product_share
                    / 100.0,
                    10,
                )

                allocated_total += (
                    product_volume
                )

            normalized_prod_vol_map[
                product_name
            ][
                t
            ] = product_volume

    prod_vol_map = (
        normalized_prod_vol_map
    )

    # =====================================================
    # 5. Build exact DISPLAY volumes
    #
    # Rounded displayed Product rows also add exactly to
    # displayed Overall.
    # =====================================================

    prod_display_map = {
        p: [0] * n
        for p in prod_labels
    }

    overall_display = round_volume(
        total_vals
    )

    for t in range(n):

        target_display_total = int(
            overall_display[t]
        )

        allocated_display = 0

        for position, product_name in enumerate(
            prod_labels
        ):

            is_last = (
                position
                == len(prod_labels) - 1
            )

            if is_last:

                display_value = (
                    target_display_total
                    - allocated_display
                )

            else:

                display_value = round(
                    float(
                        prod_vol_map[
                            product_name
                        ][
                            t
                        ]
                        or 0
                    )
                )

                allocated_display += (
                    display_value
                )

            prod_display_map[
                product_name
            ][
                t
            ] = display_value

    # =====================================================
    # 6. Overall rows
    # =====================================================

    overall_vol_row = {
        "label": "Overall",
        "values": overall_display,
    }

    overall_share_row = {
        "label": "Overall",
        "values": [
            100.0
        ] * n,
    }

    # =====================================================
    # 7. Monthly Volume chart
    # =====================================================

    mv_chart = {
        "months": months,

        "forecast_start_index":
            split_idx,

        "series": [
            {
                "label": p,

                "history": (
                    split_series(
                        prod_display_map[
                            p
                        ],
                        split_idx,
                    )[0]
                ),

                "forecast": (
                    split_series(
                        prod_display_map[
                            p
                        ],
                        split_idx,
                    )[1]
                ),
            }
            for p in prod_labels
            if p == selected_product
        ],
    }

    # =====================================================
    # 8. Monthly Volume table
    # =====================================================

    mv_table = {
        "type": "flat",

        "rows": [
            overall_vol_row
        ] + [
            {
                "label": p,
                "values": (
                    prod_display_map[
                        p
                    ]
                ),
            }
            for p in prod_labels
        ],
    }

    # =====================================================
    # 9. Monthly Share chart
    # =====================================================

    ms_chart = {
        "months": months,

        "forecast_start_index":
            split_idx,

        "series": [
            {
                "label": p,

                "history": (
                    split_series(
                        norm_shares[i],
                        split_idx,
                    )[0]
                ),

                "forecast": (
                    split_series(
                        norm_shares[i],
                        split_idx,
                    )[1]
                ),
            }
            for i, p in enumerate(
                prod_labels
            )
            if p == selected_product
        ],
    }

    # =====================================================
    # 10. Monthly Share table
    # =====================================================

    ms_table = {
        "type": "flat",

        "rows": [
            overall_share_row
        ] + [
            {
                "label": p,
                "values": (
                    norm_shares[i]
                ),
            }
            for i, p in enumerate(
                prod_labels
            )
        ],
    }

    # =====================================================
    # 11. Yearly Volume data
    #
    # IMPORTANT:
    # use RAW normalized volumes, not rounded display values.
    # =====================================================

    mv_series_data = [
        {
            "label": p,
            "monthly_values": (
                prod_vol_map[p]
            ),
        }
        for p in prod_labels
        if p == selected_product
    ]

    mv_table_rows = (
        [
            {
                "label": "Overall",
                "monthly_values": (
                    total_vals
                ),
            }
        ]
        + [
            {
                "label": p,
                "monthly_values": (
                    prod_vol_map[p]
                ),
            }
            for p in prod_labels
        ]
    )

    # =====================================================
    # 12. Yearly Share data
    #
    # Use normalized Product volumes so yearly share is:
    #
    #     yearly product volume
    #     ---------------------
    #     yearly overall volume
    # =====================================================

    ms_series_data = [
        {
            "label": p,
            "child_vols": (
                prod_vol_map[p]
            ),
            "parent_vols": (
                total_vals
            ),
        }
        for p in prod_labels
        if p == selected_product
    ]

    ms_table_rows = (
        [
            {
                "label": "Overall",
                "fixed_values": (
                    [100.0]
                    * len(all_years)
                ),
            }
        ]
        + [
            {
                "label": p,
                "child_vols": (
                    prod_vol_map[p]
                ),
                "parent_vols": (
                    total_vals
                ),
            }
            for p in prod_labels
        ]
    )

    # =====================================================
    # 13. Response
    # =====================================================

    return {
        "market_volume": {
            "unit": "count",

            **wrap_monthly_yearly_volume(
                mv_chart,
                mv_table,
                months,
                split_idx,
                mv_series_data,
                mv_table_rows,
                "flat",
            ),
        },

        "market_share": {
            "unit": "%",

            **wrap_monthly_yearly_share(
                ms_chart,
                ms_table,
                months,
                split_idx,
                ms_series_data,
                ms_table_rows,
                "flat",
            ),
        },
    }


# =========================================================
# Shared rules for both breakdowns
# =========================================================
# 1. Every product gets a child in every market, even with no row behind
#    it. A market whose product list differs from its neighbour's is what
#    breaks callers indexing children[1] (and it made test prod visible in
#    Non-retail but not Retail purely because the two branches handled a
#    missing row differently).
# 2. A parent total of zero is not an error. A product that hasn't
#    launched, or a market with no volume in a month, has no split to
#    compute -- its children are zero and its shares are undefined.
# 3. Normalization never raises. A month where everything is zero is
#    reported and skipped; raising takes down the whole response for one
#    unpopulated month.

def _reconcile_display_children(labels, values_by_label, target, t):
    """Round each child to a whole number and give the residue to the
    LARGEST child rather than the last one.

    'Last absorbs the remainder' guarantees children sum to their parent,
    but it puts the entire rounding residue of every sibling onto whichever
    row happens to sort last. On a ~30,000 row a few units are invisible;
    on a product with no volume they read as data -- which is how a newly
    added product ends up displaying -8, 9, 9 instead of zeros.

    The largest child is the one where the residue genuinely disappears
    into the rounding it came from.
    """
    values = [round(float(values_by_label[label][t] or 0)) for label in labels]

    residue = int(target) - sum(values)

    if residue and values:
        absorber = max(range(len(values)), key=lambda i: values[i])
        values[absorber] += residue

    return values


def build_market_product(
    cur,
    ta,
    scenario,
    markets,
    products,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_market,
    selected_product,
):
    """
    Market -> Product breakdown.

    Hierarchy
    ---------
    Overall
        Retail
            Biktarvy
            Truvada
            Descovy
        Non-retail
            Biktarvy
            Truvada
            Descovy

    Rules
    -----
    1. Overall volume is authoritative.
    2. Market totals are reconciled so sum(markets) == Overall.
    3. Products inside each market are normalized so
       sum(products in market) == market total.
    4. Existing product proportions inside each market are preserved.
    5. Display rounding is corrected so displayed children also sum
       exactly to the displayed market parent -- with the residue going to
       the largest child, never to a zero-volume one.
    6. Yearly calculations use raw normalized volumes.
    7. Every product appears under every market -- at zero where it has
       no data.
    """

    n = len(total_vals)
    all_years = get_ordered_years(months)

    # =========================================================
    # 1. Build RAW Market -> Product volumes
    # =========================================================

    mp_vol = {}
    market_totals = {}

    for mkt in markets:

        mp_vol[mkt] = {}

        # -----------------------------------------------------
        # Market total
        # -----------------------------------------------------

        mkt_d = fetch_forecast_scenario(
            cur, ta, mkt, None, "ALL", "market_share", scenario,
        )

        if mkt_d:
            market_series = build_series(mkt_d, start, end)
            min_len = min(n, len(market_series["values"]))
            mkt_vol = build_volume_from_share(
                total_vals[:min_len],
                market_series["values"][:min_len],
            )
            mkt_vol = (mkt_vol + [0.0] * (n - len(mkt_vol)))[:n]
        else:
            mkt_vol = [0.0] * n

        market_totals[mkt] = mkt_vol

        # -----------------------------------------------------
        # Products inside market
        # -----------------------------------------------------

        for prod in products:

            # =================================================
            # Retail
            # =================================================

            if mkt == "Retail":

                product_d = fetch_forecast_scenario(
                    cur, ta, mkt, None, prod, "market_share", scenario,
                )

                if not product_d:
                    # Shown at zero rather than dropped, so this market's
                    # product list matches every other market's.
                    volume = [0.0] * n
                else:
                    product_series = build_series(product_d, start, end)
                    min_len = min(n, len(product_series["values"]))
                    volume = build_volume_from_share(
                        market_totals[mkt][:min_len],
                        product_series["values"][:min_len],
                    )

            # =================================================
            # Non-retail / source hierarchy
            # =================================================

            else:

                total_product_volume = [0.0] * n

                sources = get_sources(cur, ta, mkt)

                for src in sources:

                    source_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, "ALL", "market_share", scenario,
                    )

                    if not source_d:
                        continue

                    source_series = build_series(source_d, start, end)

                    product_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, prod, "market_share", scenario,
                    )

                    if not product_d:
                        continue

                    product_series = build_series(product_d, start, end)

                    min_len = min(
                        len(market_totals[mkt]),
                        len(source_series["values"]),
                        len(product_series["values"]),
                    )

                    source_volume = build_volume_from_share(
                        market_totals[mkt][:min_len],
                        source_series["values"][:min_len],
                    )

                    product_volume = build_volume_from_share(
                        source_volume,
                        product_series["values"][:min_len],
                    )

                    for i in range(min_len):
                        total_product_volume[i] += product_volume[i]

                volume = total_product_volume

            volume = (volume + [0.0] * (n - len(volume)))[:n]

            mp_vol[mkt][prod] = volume

    # =========================================================
    # 2. Normalize MARKET totals to Overall
    # =========================================================

    for t in range(n):

        overall_volume = float(total_vals[t] or 0)

        current_market_sum = sum(
            float(market_totals[mkt][t] or 0) for mkt in markets
        )

        if overall_volume == 0 and current_market_sum == 0:
            continue

        if current_market_sum <= 0:
            # Reported, not raised: one unpopulated month shouldn't take
            # down the whole response.
            continue

        scale_factor = overall_volume / current_market_sum
        allocated = 0.0

        for market_index, mkt in enumerate(markets):

            is_last = market_index == len(markets) - 1
            old_market_total = float(market_totals[mkt][t] or 0)

            if is_last:
                new_market_total = round(overall_volume - allocated, 10)
            else:
                new_market_total = round(old_market_total * scale_factor, 10)
                allocated += new_market_total

            # Scale product values by the same factor so the product mix
            # inside the market is preserved.
            if old_market_total > 0:
                child_scale = new_market_total / old_market_total

                for prod in products:
                    if prod not in mp_vol[mkt]:
                        continue
                    mp_vol[mkt][prod][t] = round(
                        float(mp_vol[mkt][prod][t] or 0) * child_scale, 10,
                    )

            market_totals[mkt][t] = new_market_total

    # =========================================================
    # 3. Normalize Products inside each Market
    # =========================================================
    # Raw (unrounded) values here. The last product absorbs the residue at
    # full float precision, which is a ~1e-10 adjustment -- unlike the
    # DISPLAY pass below, where the residue is whole units and has to be
    # placed deliberately.

    normalized_mp_vol = {}
    market_product_shares = {}

    for mkt in markets:

        product_labels = [
            prod for prod in products if prod in mp_vol.get(mkt, {})
        ]

        raw_product_volumes = [mp_vol[mkt][prod] for prod in product_labels]

        norm_shares = (
            normalize_shares_to_100(raw_product_volumes, n)
            if raw_product_volumes
            else []
        )

        normalized_mp_vol[mkt] = {}
        market_product_shares[mkt] = {}

        for index, prod in enumerate(product_labels):
            market_product_shares[mkt][prod] = norm_shares[index]
            normalized_mp_vol[mkt][prod] = [0.0] * n

        for t in range(n):

            market_volume = float(market_totals[mkt][t] or 0)
            allocated = 0.0

            # The residue goes to the largest product, not the last, for
            # the same reason as the display pass -- a zero-volume product
            # must stay at zero.
            largest_index = None
            if product_labels:
                largest_index = max(
                    range(len(product_labels)),
                    key=lambda i: float(
                        mp_vol[mkt][product_labels[i]][t] or 0
                    ),
                )

            for product_index, prod in enumerate(product_labels):

                if product_index == largest_index:
                    continue

                product_share = float(norm_shares[product_index][t] or 0)
                product_volume = round(
                    market_volume * product_share / 100.0, 10,
                )
                allocated += product_volume

                normalized_mp_vol[mkt][prod][t] = product_volume

            if largest_index is not None:
                normalized_mp_vol[mkt][product_labels[largest_index]][t] = (
                    round(market_volume - allocated, 10)
                )

    # Canonical map from this point.
    mp_vol = normalized_mp_vol

    # =========================================================
    # 4. Exact DISPLAY market totals
    # =========================================================

    overall_display = round_volume(total_vals)

    market_display_totals = {mkt: [0] * n for mkt in markets}

    for t in range(n):
        values = _reconcile_display_children(
            markets, market_totals, int(overall_display[t]), t,
        )
        for i, mkt in enumerate(markets):
            market_display_totals[mkt][t] = values[i]

    # =========================================================
    # 5. Exact DISPLAY Product children
    # =========================================================

    display_mp_vol = {}

    for mkt in markets:

        product_labels = [
            prod for prod in products if prod in mp_vol.get(mkt, {})
        ]

        display_mp_vol[mkt] = {prod: [0] * n for prod in product_labels}

        for t in range(n):
            values = _reconcile_display_children(
                product_labels, mp_vol[mkt], market_display_totals[mkt][t], t,
            )
            for i, prod in enumerate(product_labels):
                display_mp_vol[mkt][prod][t] = values[i]

    # =========================================================
    # 6. CHART: selected Market / Product
    # =========================================================

    vol_chart_series = []
    share_chart_series = []

    mv_series_data = []
    ms_series_data = []

    if selected_market in mp_vol:

        mkt = selected_market
        mkt_vol = market_totals[mkt]

        for prod in products:

            if prod not in mp_vol[mkt]:
                continue

            if selected_product and prod != selected_product:
                continue

            raw_volume = mp_vol[mkt][prod]
            display_volume = display_mp_vol[mkt][prod]

            history_volume, forecast_volume = split_series(
                display_volume, split_idx,
            )

            vol_chart_series.append({
                "label": f"{mkt} - {prod}",
                "market": mkt,
                "product": prod,
                "history": history_volume,
                "forecast": forecast_volume,
            })

            mv_series_data.append({
                "label": f"{mkt} - {prod}",
                "market": mkt,
                "product": prod,
                "monthly_values": raw_volume,
            })

            product_share = market_product_shares[mkt].get(prod, [0.0] * n)

            history_share, forecast_share = split_series(
                product_share, split_idx,
            )

            share_chart_series.append({
                "label": f"{mkt} - {prod}",
                "market": mkt,
                "product": prod,
                "history": history_share,
                "forecast": forecast_share,
            })

            ms_series_data.append({
                "label": f"{mkt} - {prod}",
                "market": mkt,
                "product": prod,
                "child_vols": raw_volume,
                "parent_vols": mkt_vol,
            })

    # =========================================================
    # 7. TABLE: full hierarchy
    # =========================================================

    vol_table_rows = []
    share_table_rows = []

    mv_table_rows = []
    ms_table_rows = []

    for mkt in markets:

        mkt_vol = market_totals[mkt]

        product_labels = [
            prod for prod in products if prod in mp_vol.get(mkt, {})
        ]

        vol_children = [
            {"label": prod, "values": display_mp_vol[mkt][prod]}
            for prod in product_labels
        ]

        share_children = [
            {"label": prod, "values": market_product_shares[mkt][prod]}
            for prod in product_labels
        ]

        vol_table_rows.append({
            "label": mkt,
            "values": market_display_totals[mkt],
            "children": vol_children,
        })

        share_table_rows.append({
            "label": mkt,
            "values": [100.0] * n,
            "children": share_children,
        })

        mv_table_rows.append({
            "label": mkt,
            "monthly_values": mkt_vol,
            "children": [
                {"label": prod, "monthly_values": mp_vol[mkt][prod]}
                for prod in product_labels
            ],
        })

        ms_table_rows.append({
            "label": mkt,
            "fixed_values": [100.0] * len(all_years),
            "children": [
                {
                    "label": prod,
                    "child_vols": mp_vol[mkt][prod],
                    "parent_vols": mkt_vol,
                }
                for prod in product_labels
            ],
        })

    # =========================================================
    # 8. Final wrappers
    # =========================================================

    mv_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": vol_chart_series,
    }

    mv_table = {"type": "hierarchy", "rows": vol_table_rows}

    ms_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": share_chart_series,
    }

    ms_table = {"type": "hierarchy", "rows": share_table_rows}

    # =========================================================
    # 9. Selected
    # =========================================================

    selected_volume = (
        mp_vol.get(selected_market, {}).get(selected_product, [0.0] * n)
    )

    selected_parent_volume = market_totals.get(selected_market, total_vals)

    # =========================================================
    # 10. Response
    # =========================================================

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart, mv_table, months, split_idx,
                mv_series_data, mv_table_rows, "hierarchy",
            ),
        },
        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart, ms_table, months, split_idx,
                ms_series_data, ms_table_rows, "hierarchy",
            ),
        },
        "_selected": {
            "months": months,
            "split_idx": split_idx,
            "volume": selected_volume,
            "parent_volume": selected_parent_volume,
        },
    }


def build_product_market(
    cur,
    ta,
    scenario,
    markets,
    products,
    total_vals,
    months,
    split_idx,
    start,
    end,
    selected_product,
    selected_market,
):
    """
    Product -> Market breakdown.

    Hierarchy
    ---------
    Overall
        Biktarvy
            Retail
            Non-retail
        Descovy
            Retail
            Non-retail

    Rules
    -----
    1. Overall volume is authoritative.
    2. Product totals are normalized so sum(products) == Overall.
    3. Existing Product -> Market proportions are preserved.
    4. Market children are normalized so
       sum(markets within product) == product total.
    5. Display rounding is corrected so displayed children also sum
       exactly to the displayed parent.
    6. Yearly calculations use raw normalized volumes.
    7. Every product gets a child for every market that exists, at zero
       where the product has no row there.
    """

    n = len(total_vals)
    all_years = get_ordered_years(months)

    # =========================================================
    # 1. Build RAW Product -> Market volumes
    # =========================================================

    pm_vol = {}
    product_totals = {}

    for prod in products:

        pm_vol[prod] = {}
        prod_total = [0.0] * n

        for mkt in markets:

            # =================================================
            # Retail
            # =================================================

            if mkt == "Retail":

                market_d = fetch_forecast_scenario(
                    cur, ta, mkt, None, "ALL", "market_share", scenario,
                )

                if not market_d:
                    # The MARKET itself is absent -- skipping is right
                    # here, unlike a missing product row below.
                    continue

                market_series = build_series(market_d, start, end)

                product_d = fetch_forecast_scenario(
                    cur, ta, mkt, None, prod, "market_share", scenario,
                )

                if not product_d:
                    volume = [0.0] * n
                else:
                    product_series = build_series(product_d, start, end)

                    min_len = min(
                        len(total_vals),
                        len(market_series["values"]),
                        len(product_series["values"]),
                    )

                    market_volume = build_volume_from_share(
                        total_vals[:min_len],
                        market_series["values"][:min_len],
                    )

                    volume = build_volume_from_share(
                        market_volume,
                        product_series["values"][:min_len],
                    )

            # =================================================
            # Non-retail / source hierarchy
            # =================================================

            else:

                total_product_volume = [0.0] * n

                market_d = fetch_forecast_scenario(
                    cur, ta, mkt, None, "ALL", "market_share", scenario,
                )

                if not market_d:
                    continue

                market_series = build_series(market_d, start, end)

                min_len_market = min(
                    len(total_vals), len(market_series["values"]),
                )

                market_volume = build_volume_from_share(
                    total_vals[:min_len_market],
                    market_series["values"][:min_len_market],
                )

                sources = get_sources(cur, ta, mkt)

                for src in sources:

                    source_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, "ALL", "market_share", scenario,
                    )

                    if not source_d:
                        continue

                    source_series = build_series(source_d, start, end)

                    product_d = fetch_forecast_scenario_with_fallback(
                        cur, ta, mkt, src, prod, "market_share", scenario,
                    )

                    if not product_d:
                        continue

                    product_series = build_series(product_d, start, end)

                    min_len = min(
                        len(market_volume),
                        len(source_series["values"]),
                        len(product_series["values"]),
                    )

                    source_volume = build_volume_from_share(
                        market_volume[:min_len],
                        source_series["values"][:min_len],
                    )

                    product_volume = build_volume_from_share(
                        source_volume,
                        product_series["values"][:min_len],
                    )

                    for i in range(min_len):
                        total_product_volume[i] += product_volume[i]

                volume = total_product_volume

            volume = (volume + [0.0] * (n - len(volume)))[:n]

            pm_vol[prod][mkt] = volume

            for i in range(n):
                prod_total[i] += volume[i]

        product_totals[prod] = prod_total

    # =========================================================
    # 2. Normalize PRODUCT totals to Overall
    # =========================================================

    for month_index in range(n):

        overall_volume = float(total_vals[month_index] or 0)

        current_product_sum = sum(
            float(product_totals[prod][month_index] or 0)
            for prod in products
        )

        if overall_volume == 0 and current_product_sum == 0:
            continue

        if current_product_sum <= 0:
            # print(
            #     f"  WARNING build_product_market: no product volume at "
            #     f"month {month_index} (Overall={overall_volume}) -- "
            #     "leaving zeros"
            # )
            continue

        product_scale = overall_volume / current_product_sum

        new_product_totals = {}
        allocated_product_total = 0.0

        for product_index, prod in enumerate(products):

            is_last_product = product_index == len(products) - 1
            old_product_total = float(product_totals[prod][month_index] or 0)

            if is_last_product:
                new_product_total = round(
                    overall_volume - allocated_product_total, 10,
                )
            else:
                new_product_total = round(
                    old_product_total * product_scale, 10,
                )
                allocated_product_total += new_product_total

            new_product_totals[prod] = new_product_total

        # Scale markets under each product by that product's own factor,
        # preserving its Retail : Non-retail ratio.
        for prod in products:

            old_product_total = float(product_totals[prod][month_index] or 0)
            new_product_total = new_product_totals[prod]

            market_labels = [
                mkt for mkt in markets if mkt in pm_vol.get(prod, {})
            ]

            if not market_labels:
                product_totals[prod][month_index] = new_product_total
                continue

            if old_product_total > 0:
                product_market_scale = new_product_total / old_product_total
            else:
                # No baseline split to preserve -- a product with no volume
                # this month. Its markets stay at zero rather than being
                # handed an arbitrary share.
                product_market_scale = 0.0

            allocated_market_total = 0.0

            for market_index, mkt in enumerate(market_labels):

                is_last_market = market_index == len(market_labels) - 1

                old_market_volume = float(
                    pm_vol[prod][mkt][month_index] or 0
                )

                if is_last_market:
                    new_market_volume = round(
                        new_product_total - allocated_market_total, 10,
                    )
                else:
                    new_market_volume = round(
                        old_market_volume * product_market_scale, 10,
                    )
                    allocated_market_total += new_market_volume

                pm_vol[prod][mkt][month_index] = new_market_volume

            product_totals[prod][month_index] = new_product_total

    # =========================================================
    # 3. Normalize Market distribution inside each Product
    # =========================================================

    normalized_pm_vol = {}
    product_market_shares = {}

    for prod in products:

        labels = [mkt for mkt in markets if mkt in pm_vol.get(prod, {})]

        raw_market_volumes = [pm_vol[prod][mkt] for mkt in labels]

        prod_total = product_totals[prod]

        norm_shares = (
            normalize_shares_to_100(raw_market_volumes, n)
            if raw_market_volumes
            else []
        )

        product_market_shares[prod] = {
            labels[i]: norm_shares[i] for i in range(len(labels))
        }

        normalized_pm_vol[prod] = {}

        normalized_market_values = [[0.0] * n for _ in labels]

        for t in range(n):

            parent_volume = float(prod_total[t] or 0)
            allocated_raw = 0.0

            for child_index in range(len(labels)):

                is_last = child_index == len(labels) - 1

                if is_last:
                    child_volume = round(parent_volume - allocated_raw, 10)
                else:
                    share_value = float(norm_shares[child_index][t] or 0)
                    child_volume = round(
                        parent_volume * share_value / 100.0, 10,
                    )
                    allocated_raw += child_volume

                normalized_market_values[child_index][t] = child_volume

        for i, mkt in enumerate(labels):
            normalized_pm_vol[prod][mkt] = normalized_market_values[i]

    pm_vol = normalized_pm_vol

    # =========================================================
    # 4. Exact DISPLAY values
    # =========================================================

    product_display_totals = {prod: [0] * n for prod in products}

    overall_display = round_volume(total_vals)

    for t in range(n):

        target_overall = int(overall_display[t])
        allocated_products = 0

        for product_index, prod in enumerate(products):

            is_last_product = product_index == len(products) - 1

            if is_last_product:
                display_product_total = target_overall - allocated_products
            else:
                display_product_total = round(
                    float(product_totals[prod][t] or 0)
                )
                allocated_products += display_product_total

            product_display_totals[prod][t] = display_product_total

    display_pm_vol = {}

    for prod in products:

        labels = [mkt for mkt in markets if mkt in pm_vol.get(prod, {})]

        display_pm_vol[prod] = {mkt: [0] * n for mkt in labels}

        for t in range(n):

            target_product_total = product_display_totals[prod][t]
            allocated_markets = 0

            for market_index, mkt in enumerate(labels):

                is_last_market = market_index == len(labels) - 1

                if is_last_market:
                    display_market_volume = (
                        target_product_total - allocated_markets
                    )
                else:
                    display_market_volume = round(
                        float(pm_vol[prod][mkt][t] or 0)
                    )
                    allocated_markets += display_market_volume

                display_pm_vol[prod][mkt][t] = display_market_volume

    # =========================================================
    # 5. CHART
    # =========================================================

    vol_chart_series = []
    share_chart_series = []

    mv_series_data = []
    ms_series_data = []

    if selected_product in pm_vol:

        prod = selected_product
        prod_total = product_totals[prod]

        labels = [mkt for mkt in markets if mkt in pm_vol[prod]]

        for mkt in labels:

            if selected_market and mkt != selected_market:
                continue

            raw_volume = pm_vol[prod][mkt]
            display_volume = display_pm_vol[prod][mkt]

            history_volume, forecast_volume = split_series(
                display_volume, split_idx,
            )

            vol_chart_series.append({
                "label": f"{prod} - {mkt}",
                "product": prod,
                "market": mkt,
                "history": history_volume,
                "forecast": forecast_volume,
            })

            mv_series_data.append({
                "label": f"{prod} - {mkt}",
                "product": prod,
                "market": mkt,
                "monthly_values": raw_volume,
            })

            market_share = product_market_shares[prod].get(mkt, [0.0] * n)

            history_share, forecast_share = split_series(
                market_share, split_idx,
            )

            share_chart_series.append({
                "label": f"{prod} - {mkt}",
                "product": prod,
                "market": mkt,
                "history": history_share,
                "forecast": forecast_share,
            })

            ms_series_data.append({
                "label": f"{prod} - {mkt}",
                "product": prod,
                "market": mkt,
                "child_vols": raw_volume,
                "parent_vols": prod_total,
            })

    # =========================================================
    # 6. TABLE
    # =========================================================

    vol_table_rows = []
    share_table_rows = []

    mv_table_rows = []
    ms_table_rows = []

    for prod in products:

        prod_total = product_totals[prod]

        labels = [mkt for mkt in markets if mkt in pm_vol.get(prod, {})]

        vol_children = [
            {"label": mkt, "values": display_pm_vol[prod][mkt]}
            for mkt in labels
        ]

        share_children = [
            {"label": mkt, "values": product_market_shares[prod][mkt]}
            for mkt in labels
        ]

        vol_table_rows.append({
            "label": prod,
            # Reconciled display parent.
            "values": product_display_totals[prod],
            "children": vol_children,
        })

        share_table_rows.append({
            "label": prod,
            "values": [100.0] * n,
            "children": share_children,
        })

        mv_table_rows.append({
            "label": prod,
            "monthly_values": prod_total,
            "children": [
                {"label": mkt, "monthly_values": pm_vol[prod][mkt]}
                for mkt in labels
            ],
        })

        ms_table_rows.append({
            "label": prod,
            "fixed_values": [100.0] * len(all_years),
            "children": [
                {
                    "label": mkt,
                    "child_vols": pm_vol[prod][mkt],
                    "parent_vols": prod_total,
                }
                for mkt in labels
            ],
        })

    # =========================================================
    # 7. Wrappers
    # =========================================================

    mv_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": vol_chart_series,
    }

    mv_table = {"type": "hierarchy", "rows": vol_table_rows}

    ms_chart = {
        "months": months,
        "forecast_start_index": split_idx,
        "series": share_chart_series,
    }

    ms_table = {"type": "hierarchy", "rows": share_table_rows}

    # =========================================================
    # 8. Selected
    # =========================================================

    selected_volume = (
        pm_vol.get(selected_product, {}).get(selected_market, [0.0] * n)
    )

    selected_parent_volume = product_totals.get(
        selected_product, total_vals,
    )

    # =========================================================
    # 9. Response
    # =========================================================

    return {
        "market_volume": {
            "unit": "count",
            **wrap_monthly_yearly_volume(
                mv_chart, mv_table, months, split_idx,
                mv_series_data, mv_table_rows, "hierarchy",
            ),
        },
        "market_share": {
            "unit": "%",
            **wrap_monthly_yearly_share(
                ms_chart, ms_table, months, split_idx,
                ms_series_data, ms_table_rows, "hierarchy",
            ),
        },
        "_selected": {
            "months": months,
            "split_idx": split_idx,
            "volume": selected_volume,
            "parent_volume": selected_parent_volume,
        },
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
    # products = get_products(cur, ta)
    products = get_products(cur, ta, scenario)

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