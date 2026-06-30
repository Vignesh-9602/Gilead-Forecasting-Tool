import pandas as pd
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
    """
    Fetch forecast data filtered by scenario.
    BASE scenario is matched case-insensitively via UPPER() so that
    'BASE', 'Base', 'base' all resolve correctly without hardcoding.
    Non-BASE scenarios are matched exactly.
    """
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
        WHERE ta_name = %s AND metric = 'market_share'
    """, (ta,))
    return [r[0] for r in cur.fetchall()]


def get_sources(cur, ta, market):
    cur.execute("""
        SELECT DISTINCT source_of_market
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s AND market = %s
          AND source_of_market IS NOT NULL
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
    """
    Fetch all available scenarios from DB.
    Deduplicates BASE case-insensitively — returns one canonical
    entry for BASE (whichever casing is stored) plus all others.
    """
    cur.execute("""
        SELECT DISTINCT scenario_name
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name IS NOT NULL
    """, (ta,))
    rows = cur.fetchall()
    if not rows:
        return ["BASE"]

    all_scenarios = [r[0] for r in rows]

    # Separate BASE-variants from real named scenarios
    base_variants = [s for s in all_scenarios if s.upper() == "BASE"]
    non_base = [s for s in all_scenarios if s.upper() != "BASE"]

    # Use the stored BASE variant if found, else default to "BASE"
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
    months = pd.to_datetime(data["months"])
    train = data.get("train_values", [])
    forecast = data.get("forecast_values", [])

    full = train + forecast

    mask = (months >= pd.to_datetime(start)) & (months <= pd.to_datetime(end))

    idx = [i for i in range(len(months)) if mask[i]]
    filtered_months = months[mask]

    values = [full[i] for i in idx]

    orig_split = data.get("forecast_start_index", len(train))
    split_idx = sum(i < orig_split for i in idx)

    history, fc = split_series(values, split_idx)

    return {
        "months": format_months(filtered_months),
        "values": values,
        "history": history,
        "forecast": fc,
        "split_idx": split_idx
    }


def build_volume_from_share(total, share):
    """Compute volume from total and share %. Returns integer-rounded values."""
    min_len = min(len(total), len(share))
    return [round(total[i] * share[i] / 100) for i in range(min_len)]


def round_volume(values):
    """Round volume list to integers."""
    return [round(v) for v in values]


def round_share(values, decimals=2):
    """Round share list to 2 decimal places."""
    return [round(v, decimals) for v in values]


def normalize_shares_to_100(children_values_list, n):
    """
    Given a list of value-lists (one per child), normalize each time index
    so that children shares sum to exactly 100. Returns normalized lists.
    If total is 0 for a time index, distribute evenly.
    """
    num_children = len(children_values_list)
    if num_children == 0:
        return children_values_list

    normalized = [[0.0] * n for _ in range(num_children)]

    for t in range(n):
        total = sum(
            children_values_list[c][t]
            if t < len(children_values_list[c]) else 0
            for c in range(num_children)
        )
        for c in range(num_children):
            val = children_values_list[c][t] if t < len(children_values_list[c]) else 0
            if total > 0:
                normalized[c][t] = round((val / total) * 100, 2)
            else:
                normalized[c][t] = round(100 / num_children, 2)

    return normalized


def safe_pct(numerator, denominator, decimals=2):
    """Compute percentage safely. Returns 0 if denominator is 0."""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, decimals)


# =========================================================
# ================= FACTORS ================================
# =========================================================

def build_factors(cur, ta, scenario):
    """
    Build factors block for a given scenario.
    BASE is matched case-insensitively via UPPER() in SQL.
    """
    is_base = scenario.upper() == "BASE"

    if is_base:
        cur.execute("""
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_volume'
              AND market = 'ALL'
              AND UPPER(COALESCE(scenario_name, 'BASE')) = 'BASE'
            LIMIT 1
        """, (ta,))
    else:
        cur.execute("""
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_volume'
              AND market = 'ALL'
              AND scenario_name = %s
            LIMIT 1
        """, (ta, scenario))

    row = cur.fetchone()
    if not row:
        return {}

    data = row[0]
    months = data.get("months", [])
    split_idx = data.get("forecast_start_index", 0)
    trajectory_start = months[split_idx] if split_idx < len(months) else None

    f = data.get("factors", {})
    ets = {
        "alpha": f.get("alpha"),
        "beta": f.get("beta"),
        "gamma": f.get("gamma")
    }

    if is_base:
        cur.execute("""
            SELECT forecast_data->'factors'
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_share'
              AND UPPER(COALESCE(scenario_name, 'BASE')) = 'BASE'
            LIMIT 1
        """, (ta,))
    else:
        cur.execute("""
            SELECT forecast_data->'factors'
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND metric = 'market_share'
              AND scenario_name = %s
            LIMIT 1
        """, (ta, scenario))

    row = cur.fetchone()
    traj = row[0].get("trajectory", {}) if row else {}

    linear = {
        "duration": traj.get("duration"),
        "total_growth": traj.get("total_growth"),
        "trajectory_start": trajectory_start
    }

    def curve(k=1):
        return {
            "k_value": k,
            "duration": linear.get("duration"),
            "total_growth": linear.get("total_growth"),
            "trajectory_start": trajectory_start
        }

    return {
        "ets": ets,
        "linear": linear,
        "scurve": curve(),
        "multiplier": 1,
        "exponential": curve(),
        "logarithmic": curve(),
        "active_model": "ets",
        "multiplier_horizon": "Forecast"
    }


# =========================================================
# ================= MARKET ANALYSIS BUILDERS ===============
# =========================================================

def build_total_market_volume(total_vals, months, split_idx):
    """
    Total market = BASE series. Share is always 100%.
    Volumes: integers. Share: 2 decimal (100.0).
    """
    int_vals = round_volume(total_vals)
    h, f = split_series(int_vals, split_idx)

    n = len(int_vals)
    share_vals = [100.0] * n
    sh, sf = split_series(share_vals, split_idx)

    return {
        "market_volume": {
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": [{"label": "BASE", "history": h, "forecast": f}]
            },
            "table": {
                "type": "flat",
                "rows": [{"label": "BASE", "values": int_vals}]
            }
        },
        "market_share": {
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": [{"label": "Market Share", "history": sh, "forecast": sf}]
            },
            "table": {
                "type": "flat",
                "rows": [{"label": "Market Share", "values": share_vals}]
            }
        }
    }


def build_market_distribution(cur, ta, scenario, total_vals, months, split_idx, start, end):

    markets = get_markets(cur, ta)
    n = len(total_vals)

    vol_chart_series = []
    share_chart_series = []
    market_vol_rows = []
    market_share_rows = []

    overall_vol_row = {"label": "Overall",  "values": round_volume(total_vals)}
    overall_share_row = {"label": "Overall", "values": [100.0] * n}

    market_totals = {}

    for mkt in markets:
        d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
        if not d:
            continue

        s = build_series(d, start, end)
        share = s["values"]

        #   Market volume from total
        vol = build_volume_from_share(total_vals, share)
        vol = vol + [0] * (n - len(vol))

        market_totals[mkt] = vol

        h, f = split_series(vol, split_idx)
        sh, sf = split_series(share, split_idx)

        vol_chart_series.append({"label": mkt, "history": h, "forecast": f})
        share_chart_series.append({"label": mkt, "history": sh, "forecast": sf})

        #   SOURCES FIXED (use market volume, not total)
        sources = get_sources(cur, ta, mkt)
        vol_children = []
        share_children_vals = []
        share_children_labels = []  # FIX: track labels in lockstep with values

        for src in sources:
            sd = fetch_forecast_scenario(cur, ta, mkt, src, "ALL", "market_share", scenario)
            if not sd:
                continue

            ss = build_series(sd, start, end)
            src_share = ss["values"]

            #   FIX HERE
            src_vol = build_volume_from_share(vol, src_share)

            vol_children.append({"label": src, "values": src_vol})
            share_children_vals.append(src_vol)
            share_children_labels.append(src)  # FIX: only appended when src succeeds

        vol_row = {"label": mkt, "values": vol}
        share_row = {"label": mkt, "values": share}

        if vol_children:
            vol_row["children"] = vol_children

            norm = normalize_shares_to_100(share_children_vals, n)
            # FIX: use share_children_labels (aligned with norm) instead of
            # the original `sources` list, which may include sources that
            # had no data and were skipped above — using `sources` directly
            # would misalign labels with values whenever any source was skipped.
            share_row["children"] = [
                {"label": share_children_labels[i], "values": norm[i]}
                for i in range(len(norm))
            ]

        market_vol_rows.append(vol_row)
        market_share_rows.append(share_row)

    return {
        "market_volume": {
            "unit": "count",
            "chart": {"months": months, "forecast_start_index": split_idx, "series": vol_chart_series},
            "table": {"type": "hierarchy", "rows": [overall_vol_row] + market_vol_rows}
        },
        "market_share": {
            "unit": "%",
            "chart": {"months": months, "forecast_start_index": split_idx, "series": share_chart_series},
            "table": {"type": "hierarchy", "rows": [overall_share_row] + market_share_rows}
        }
    }


def build_product_distribution(cur, ta, scenario, markets, total_vals, months, split_idx, start, end):

    products = get_products(cur, ta)
    n = len(total_vals)

    prod_vol_map = {p: [0]*n for p in products}

    for mkt in markets:
        #   step1: market volume
        mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
        if not mkt_d:
            continue

        mkt_series = build_series(mkt_d, start, end)
        mkt_vol = build_volume_from_share(total_vals, mkt_series["values"])

        for prod in products:

            if mkt == "Retail":

                d = fetch_forecast_scenario(
                    cur, ta, mkt, None, prod, "market_share", scenario
                )

                if not d:
                    continue

                s = build_series(d, start, end)

                prod_vol = build_volume_from_share(mkt_vol, s["values"])

                for i in range(min(len(prod_vol), n)):
                    prod_vol_map[prod][i] += prod_vol[i]

            else:

                sources = get_sources(cur, ta, mkt)

                for src in sources:

                    src_d = fetch_forecast_scenario(
                        cur, ta, mkt, src, "ALL", "market_share", scenario
                    )

                    if not src_d:
                        continue

                    src_series = build_series(src_d, start, end)

                    src_vol = build_volume_from_share(mkt_vol, src_series["values"])

                    prod_d = fetch_forecast_scenario(
                        cur, ta, mkt, src, prod, "market_share", scenario
                    )

                    if not prod_d:
                        continue

                    prod_series = build_series(prod_d, start, end)

                    prod_vol = build_volume_from_share(src_vol, prod_series["values"])

                    for i in range(min(len(prod_vol), n)):
                        prod_vol_map[prod][i] += prod_vol[i]

    prod_labels = list(prod_vol_map.keys())
    raw_vols = [prod_vol_map[p] for p in prod_labels]
    norm_shares = normalize_shares_to_100(raw_vols, n)

    #   ADDED: Overall row, matching the pattern used in build_market_distribution
    overall_vol_row = {"label": "Overall", "values": round_volume(total_vals)}
    overall_share_row = {"label": "Overall", "values": [100.0] * n}

    return {
        "market_volume": {
            "unit": "count",
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": [
                    {"label": p, "history": split_series(prod_vol_map[p], split_idx)[0],
                     "forecast": split_series(prod_vol_map[p], split_idx)[1]}
                    for p in prod_labels
                ]
            },
            "table": {
                "type": "flat",
                #   Overall row prepended
                "rows": [overall_vol_row] + [{"label": p, "values": prod_vol_map[p]} for p in prod_labels]
            }
        },
        "market_share": {
            "unit": "%",
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": [
                    {"label": p, "history": split_series(norm_shares[i], split_idx)[0],
                     "forecast": split_series(norm_shares[i], split_idx)[1]}
                    for i, p in enumerate(prod_labels)
                ]
            },
            "table": {
                "type": "flat",
                #   Overall row prepended
                "rows": [overall_share_row] + [{"label": p, "values": norm_shares[i]} for i, p in enumerate(prod_labels)]
            }
        }
    }


def build_market_product(cur, ta, scenario, markets, products, total_vals, months, split_idx, start, end, selected_market):
    """
    market_product: grouped by market -> product children.
      - Chart: ONLY the selected market's product breakdown (Retail - Biktarvy,
        Retail - Truvada, Retail - Descovy, etc. — not every market combo).
      - Table: full hierarchy across all markets — market row (100%) with
        product children normalized to sum to 100. (Unchanged.)
      - Volume: integers. Share: 2 decimals.
    """
    n = len(total_vals)

    mp_vol = {}
    market_totals = {}

    for mkt in markets:
        mp_vol[mkt] = {}

        mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
        if mkt_d:
            s = build_series(mkt_d, start, end)
            min_len = min(n, len(s["values"]))
            mkt_vol = build_volume_from_share(total_vals[:min_len], s["values"][:min_len])
            mkt_vol = mkt_vol + [0] * (n - len(mkt_vol))
        else:
            mkt_vol = [0] * n

        market_totals[mkt] = mkt_vol

        for prod in products:

            if mkt == "Retail":
                # Retail direct mapping (unchanged logic)
                d = fetch_forecast_scenario(cur, ta, mkt, None, prod, "market_share", scenario)
                if not d:
                    continue

                s = build_series(d, start, end)
                min_len = min(n, len(s["values"]))

                vol = build_volume_from_share(
                    market_totals[mkt][:min_len],
                    s["values"][:min_len]
                )

            else:
                # Non-retail: go via SOURCE
                total_prod_vol = [0] * n
                sources = get_sources(cur, ta, mkt)

                for src in sources:

                    # Step 1: source share
                    src_d = fetch_forecast_scenario(cur, ta, mkt, src, "ALL", "market_share", scenario)
                    if not src_d:
                        continue

                    src_series = build_series(src_d, start, end)

                    # Step 2: product share within source
                    prod_d = fetch_forecast_scenario(cur, ta, mkt, src, prod, "market_share", scenario)
                    if not prod_d:
                        continue

                    prod_series = build_series(prod_d, start, end)

                    min_len = min(
                        len(market_totals[mkt]),
                        len(src_series["values"]),
                        len(prod_series["values"])
                    )

                    src_vol = build_volume_from_share(
                        market_totals[mkt][:min_len],
                        src_series["values"][:min_len]
                    )

                    prod_vol = build_volume_from_share(
                        src_vol,
                        prod_series["values"][:min_len]
                    )

                    for i in range(min_len):
                        total_prod_vol[i] += prod_vol[i]

                vol = total_prod_vol

            vol = vol + [0] * (n - len(vol))
            mp_vol[mkt][prod] = vol

    # ================= CHART (filtered to selected market only) =================
    vol_chart_series = []
    share_chart_series = []

    if selected_market in mp_vol:
        mkt = selected_market

        for prod in products:
            if prod not in mp_vol[mkt]:
                continue
            vol = mp_vol[mkt][prod]
            h_v, f_v = split_series(vol, split_idx)
            vol_chart_series.append({"label": f"{mkt} - {prod}", "history": h_v, "forecast": f_v})

        prod_vols_in_mkt = []
        prod_labels_in_mkt = []
        for prod in products:
            if prod not in mp_vol[mkt]:
                continue
            prod_vols_in_mkt.append(mp_vol[mkt][prod])
            prod_labels_in_mkt.append(prod)

        norm_shares = normalize_shares_to_100(prod_vols_in_mkt, n) if prod_vols_in_mkt else []

        for c, prod in enumerate(prod_labels_in_mkt):
            sh, sf = split_series(norm_shares[c], split_idx)
            share_chart_series.append({"label": f"{mkt} - {prod}", "history": sh, "forecast": sf})

    # ================= TABLE (full hierarchy, all markets — unchanged) =================
    vol_table_rows = []
    share_table_rows = []

    for mkt in markets:
        mkt_vol = market_totals[mkt]

        prod_vols_in_mkt = []
        prod_labels_in_mkt = []

        for prod in products:
            if prod not in mp_vol[mkt]:
                continue
            prod_vols_in_mkt.append(mp_vol[mkt][prod])
            prod_labels_in_mkt.append(prod)

        norm_shares = normalize_shares_to_100(prod_vols_in_mkt, n) if prod_vols_in_mkt else []

        vol_children = [
            {"label": prod_labels_in_mkt[c], "values": prod_vols_in_mkt[c]}
            for c in range(len(prod_labels_in_mkt))
        ]
        share_children = [
            {"label": prod_labels_in_mkt[c], "values": norm_shares[c]}
            for c in range(len(prod_labels_in_mkt))
        ]

        vol_row = {"label": mkt, "values": mkt_vol}
        share_row = {"label": mkt, "values": [100.0] * n}

        if vol_children:
            vol_row["children"] = vol_children
        if share_children:
            share_row["children"] = share_children

        vol_table_rows.append(vol_row)
        share_table_rows.append(share_row)

    return {
        "market_volume": {
            "unit": "count",
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": vol_chart_series
            },
            "table": {
                "type": "hierarchy",
                "rows": vol_table_rows
            }
        },
        "market_share": {
            "unit": "%",
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": share_chart_series
            },
            "table": {
                "type": "hierarchy",
                "rows": share_table_rows
            }
        }
    }


def build_product_market(cur, ta, scenario, markets, products, total_vals, months, split_idx, start, end, selected_product):
    """
    product_market: grouped by product -> market children.
      - Chart: ONLY the selected product's market breakdown (Truvada - Retail,
        Truvada - Non-retail, etc. — not every product combo).
      - Table: full hierarchy across all products — Retail → Product,
        Non-retail → Source → Product. (Unchanged.)
    """

    n = len(total_vals)

    pm_vol = {}
    product_totals = {}

    for prod in products:
        pm_vol[prod] = {}
        prod_total = [0] * n

        for mkt in markets:

            if mkt == "Retail":
                # Retail: direct mapping

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
                    total_vals[:min_len],
                    mkt_series["values"][:min_len]
                )

                vol = build_volume_from_share(
                    mkt_vol,
                    s["values"][:min_len]
                )

            else:
                # Non-retail: MUST go via SOURCE

                total_prod_vol = [0] * n

                # Step 1: market volume
                mkt_d = fetch_forecast_scenario(cur, ta, mkt, None, "ALL", "market_share", scenario)
                if not mkt_d:
                    continue

                mkt_series = build_series(mkt_d, start, end)

                min_len_mkt = min(len(total_vals), len(mkt_series["values"]))

                mkt_vol = build_volume_from_share(
                    total_vals[:min_len_mkt],
                    mkt_series["values"][:min_len_mkt]
                )

                sources = get_sources(cur, ta, mkt)

                for src in sources:

                    # Step 2: source share
                    src_d = fetch_forecast_scenario(cur, ta, mkt, src, "ALL", "market_share", scenario)
                    if not src_d:
                        continue

                    src_series = build_series(src_d, start, end)

                    # Step 3: product share within source
                    prod_d = fetch_forecast_scenario(cur, ta, mkt, src, prod, "market_share", scenario)
                    if not prod_d:
                        continue

                    prod_series = build_series(prod_d, start, end)

                    min_len = min(
                        len(mkt_vol),
                        len(src_series["values"]),
                        len(prod_series["values"])
                    )

                    src_vol = build_volume_from_share(
                        mkt_vol[:min_len],
                        src_series["values"][:min_len]
                    )

                    prod_vol = build_volume_from_share(
                        src_vol,
                        prod_series["values"][:min_len]
                    )

                    for i in range(min_len):
                        total_prod_vol[i] += prod_vol[i]

                vol = total_prod_vol

            # Padding
            vol = vol + [0] * (n - len(vol))

            pm_vol[prod][mkt] = vol

            for i in range(n):
                prod_total[i] += vol[i]

        product_totals[prod] = prod_total

    # ================= CHART (filtered to selected product only) =================
    vol_chart_series = []
    share_chart_series = []

    if selected_product in pm_vol:
        prod = selected_product

        for mkt in markets:
            if mkt not in pm_vol[prod]:
                continue
            vol = pm_vol[prod][mkt]
            h_v, f_v = split_series(vol, split_idx)
            vol_chart_series.append({
                "label": f"{prod} - {mkt}",
                "history": h_v,
                "forecast": f_v
            })

        mkt_vols = [pm_vol[prod][mkt] for mkt in markets if mkt in pm_vol[prod]]
        labels = [mkt for mkt in markets if mkt in pm_vol[prod]]

        norm_shares = normalize_shares_to_100(mkt_vols, n) if mkt_vols else []

        for i, mkt in enumerate(labels):
            sh, sf = split_series(norm_shares[i], split_idx)
            share_chart_series.append({
                "label": f"{prod} - {mkt}",
                "history": sh,
                "forecast": sf
            })

    # ================= TABLE (full hierarchy, all products — unchanged) =================
    vol_table_rows = []
    share_table_rows = []

    for prod in products:
        prod_total = product_totals[prod]

        mkt_vols = [pm_vol[prod][mkt] for mkt in markets if mkt in pm_vol[prod]]
        labels = [mkt for mkt in markets if mkt in pm_vol[prod]]

        norm_shares = normalize_shares_to_100(mkt_vols, n) if mkt_vols else []

        vol_children = [
            {"label": labels[i], "values": mkt_vols[i]}
            for i in range(len(labels))
        ]

        share_children = [
            {"label": labels[i], "values": norm_shares[i]}
            for i in range(len(labels))
        ]

        vol_row = {"label": prod, "values": prod_total, "children": vol_children}
        share_row = {"label": prod, "values": [100.0] * n, "children": share_children}

        vol_table_rows.append(vol_row)
        share_table_rows.append(share_row)

    return {
        "market_volume": {
            "unit": "count",
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": vol_chart_series
            },
            "table": {
                "type": "hierarchy",
                "rows": vol_table_rows
            }
        },
        "market_share": {
            "unit": "%",
            "chart": {
                "months": months,
                "forecast_start_index": split_idx,
                "series": share_chart_series
            },
            "table": {
                "type": "hierarchy",
                "rows": share_table_rows
            }
        }
    }


def build_scenario_market_analysis(cur, ta, scenario, start, end, selected_market, selected_product):
    """
    Build full market_analysis block for any scenario.
    All sub-builders receive the scenario and use fetch_forecast_scenario internally.
    selected_market / selected_product are used only to filter the
    market_product / product_market CHART series respectively.
    """
    total_data = fetch_forecast_scenario(cur, ta, "ALL", "ALL", "ALL", "market_volume", scenario)
    if not total_data:
        return {
            "total_market_volume": {"market_volume": {}, "market_share": {}}
        }

    total = build_series(total_data, start, end)
    total_vals = total["values"]
    months = total["months"]
    split_idx = total["split_idx"]

    markets = get_markets(cur, ta)
    products = get_products(cur, ta)

    return {
        "total_market_volume": build_total_market_volume(total_vals, months, split_idx),
        "market_distribution": build_market_distribution(
            cur, ta, scenario, total_vals, months, split_idx, start, end
        ),
        "product_distribution": build_product_distribution(
            cur, ta, scenario, markets, total_vals, months, split_idx, start, end
        ),
        "market_product": build_market_product(
            cur, ta, scenario, markets, products, total_vals, months, split_idx, start, end, selected_market
        ),
        "product_market": build_product_market(
            cur, ta, scenario, markets, products, total_vals, months, split_idx, start, end, selected_product
        )
    }


# =========================================================
# ================= MAIN FUNCTION ==========================
# =========================================================

def build_apply_scenario_response(cur, payload, config):

    ta = payload.ta_name
    flt = payload.selected_filter
    start = flt.start_date
    end = flt.end_date

    # Fetch all available scenarios — BASE-variants are deduplicated,
    # canonical BASE is always first
    available_scenarios = get_scenarios(cur, ta)

    # Determine active scenario: the first entry is always the BASE-equivalent
    active_scenario = available_scenarios[0]

    # Build each scenario block
    scenarios_block = {}

    for scenario in available_scenarios:
        has_data = fetch_forecast_scenario(
            cur, ta, "ALL", "ALL", "ALL", "market_volume", scenario
        )

        if has_data:
            market_analysis = build_scenario_market_analysis(
                cur, ta, scenario, start, end, flt.market, flt.product
            )

            # Only BASE-equivalent scenario gets factors
            if scenario.upper() == "BASE":
                scenario_block = {
                    "factors": build_factors(cur, ta, scenario),
                    "market_analysis": market_analysis
                }
            else:
                scenario_block = {"market_analysis": market_analysis}
        else:
            scenario_block = {
                "market_analysis": {
                    "total_market_volume": {
                        "market_volume": {},
                        "market_share": {}
                    }
                }
            }

        scenarios_block[scenario] = scenario_block

    return {
        "ta_name": ta,
        "selected_filter": {
            "start_date": start,
            "end_date": end,
            "market": flt.market,
            "product": flt.product
        },
        "available_scenarios": available_scenarios,
        "active_scenario": active_scenario,
        "scenarios": scenarios_block
    }