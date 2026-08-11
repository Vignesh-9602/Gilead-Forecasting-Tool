import json


# ---------------------------------------------------------------------------
# Configuration queries
# ---------------------------------------------------------------------------

def get_liver_configs_for_ta(cur, ta_name: str) -> list:
    """Returns all (payment_type, payer, brand, config, updated_at) rows for a TA."""
    cur.execute("""
        SELECT payment_type, payer, brand, config, updated_at
        FROM raw_liver.liver_configurations
        WHERE LOWER(TRIM(ta_name)) = LOWER(TRIM(%s))
        ORDER BY payment_type, payer, brand
    """, (ta_name,))
    return cur.fetchall()


def get_liver_config_by_payment_type_payer_brand(
    cur, ta_name: str, payment_type: str, payer: str, brand: str
):
    """Returns (config,) for a specific (ta, payment_type, payer, brand) combination, or None."""
    cur.execute("""
        SELECT config
        FROM raw_liver.liver_configurations
        WHERE LOWER(TRIM(ta_name))      = LOWER(TRIM(%s))
          AND LOWER(TRIM(payment_type)) = LOWER(TRIM(%s))
          AND LOWER(TRIM(payer))        = LOWER(TRIM(%s))
          AND LOWER(TRIM(brand))        = LOWER(TRIM(%s))
    """, (ta_name, payment_type, payer, brand))
    return cur.fetchone()


def get_payment_types_and_payers(cur, ta: str) -> dict:
    """
    Returns {payment_type: [payer, ...]} from transaction_data for a TA.
    Falls back to the old single-column schema (payer = payment_type, no sub-payer)
    when transaction_data has not yet been migrated to include a payment_type column.
    """
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = 'raw_liver'
          AND table_name   = 'transaction_data'
          AND column_name  = 'payment_type'
    """)
    has_payment_type_col = cur.fetchone()[0] > 0

    if has_payment_type_col:
        cur.execute("""
            SELECT DISTINCT payment_type, payer
            FROM raw_liver.transaction_data
            WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
            ORDER BY payment_type, payer
        """, (ta,))
        result: dict = {}
        for payment_type, payer in cur.fetchall():
            result.setdefault(payment_type, []).append(payer)
        return result

    # Old schema: payer column holds what will become payment_type values.
    # Return each value with an empty sub-payer list so callers stay consistent.
    cur.execute("""
        SELECT DISTINCT payer
        FROM raw_liver.transaction_data
        WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
        ORDER BY payer
    """, (ta,))
    return {r[0]: [] for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# Filter state — unified table shared by all screens
#
# CREATE TABLE raw_liver.filter_state (
#     ta_name         TEXT      NOT NULL,
#     screen          TEXT      NOT NULL,
#     selected_filter JSONB     NOT NULL,
#     updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     PRIMARY KEY (ta_name, screen)
# );
# ---------------------------------------------------------------------------

def save_filter_state(cur, ta_name: str, selected_filter: dict) -> None:
    """Upsert the last applied filter for the model-input screen."""
    cur.execute("""
        INSERT INTO raw_liver.filter_state (ta_name, screen, selected_filter)
        VALUES (%s, 'model_input', %s::jsonb)
        ON CONFLICT (ta_name, screen)
        DO UPDATE SET
            selected_filter = EXCLUDED.selected_filter,
            updated_at      = CURRENT_TIMESTAMP
    """, (ta_name, json.dumps(selected_filter)))


def load_filter_state(cur, ta_name: str) -> dict | None:
    """Return the last saved filter for the model-input screen, or None."""
    cur.execute("""
        SELECT selected_filter
        FROM raw_liver.filter_state
        WHERE ta_name = %s AND screen = 'model_input'
    """, (ta_name,))
    row = cur.fetchone()
    return row[0] if row else None


def upsert_liver_config(cur, ta_name: str, payment_type: str, payer: str, brand: str, config: dict):
    """Upsert one (ta_name, payment_type, payer, brand) row with the given config."""
    cur.execute("""
        INSERT INTO raw_liver.liver_configurations (ta_name, payment_type, payer, brand, config)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (ta_name, payment_type, payer, brand)
        DO UPDATE SET
            config     = EXCLUDED.config,
            updated_at = CURRENT_TIMESTAMP
    """, (ta_name, payment_type, payer, brand, json.dumps(config)))


# ---------------------------------------------------------------------------
# Master / lookup queries
# ---------------------------------------------------------------------------

def get_payers(cur) -> list:
    cur.execute("SELECT payer_name FROM raw_liver.payer_master ORDER BY payer_name")
    return [r[0] for r in cur.fetchall()]


def get_products(cur) -> list:
    cur.execute(
        "SELECT product_name FROM raw_liver.product_master WHERE active_flag = %s ORDER BY product_name",
        ("Y",)
    )
    return [r[0] for r in cur.fetchall()]


def get_scenarios(cur) -> list:
    cur.execute(
        "SELECT scenario_name FROM raw_liver.liver_scenarios ORDER BY created_at DESC"
    )
    return [r[0] for r in cur.fetchall()]


def get_transaction_date_range(cur) -> tuple:
    """Returns (min_year, min_month, max_year, max_month) using composite year*100+month sort."""
    cur.execute("""
        SELECT
            (MIN(year * 100 + month) / 100)::int,
            (MIN(year * 100 + month) % 100)::int,
            (MAX(year * 100 + month) / 100)::int,
            (MAX(year * 100 + month) % 100)::int
        FROM raw_liver.transaction_data
    """)
    return cur.fetchone()


def get_transaction_distinct_months(cur, ta: str) -> list:
    """Returns [(year, month), ...] ordered ascending for a given TA."""
    cur.execute("""
        SELECT DISTINCT year, month
        FROM raw_liver.transaction_data
        WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
        ORDER BY year, month
    """, (ta,))
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Tab 1 — Total Market Volume (on the fly from transaction_data)
# ---------------------------------------------------------------------------

def _payer_filter(payer) -> bool:
    """Returns True if a real payer filter should be applied."""
    if not payer:
        return False
    if isinstance(payer, list):
        return len(payer) > 0
    return bool(payer)


def _to_list(val) -> list:
    """Normalise str or list → list for use with ANY(%s::text[])."""
    return val if isinstance(val, list) else [val]


def get_total_market_volume(cur, ta: str, from_year: int, from_month: int,
                             to_year: int, to_month: int, payer=None) -> list:
    """Returns [(year, month, total_volume), ...]"""
    if _payer_filter(payer):
        cur.execute("""
            SELECT year, month, SUM(volume)
            FROM raw_liver.transaction_data
            WHERE ta = %s AND payer = ANY(%s::text[])
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month
            ORDER BY year, month
        """, (ta, _to_list(payer), from_year, from_month, to_year, to_month))
    else:
        cur.execute("""
            SELECT year, month, SUM(volume)
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month
            ORDER BY year, month
        """, (ta, from_year, from_month, to_year, to_month))
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Tab 2 — Product Distribution (on the fly)
# Percentages are always relative to ALL products for that month.
# Product filter narrows the returned rows but keeps correct percentages.
# ---------------------------------------------------------------------------

def get_product_distribution(cur, ta: str, from_year: int, from_month: int,
                              to_year: int, to_month: int,
                              product: str = None, metric: str = "payer_volume") -> list:
    """Returns [(year, month, product, volume, distribution_pct), ...]"""
    value_col = "distribution_pct" if metric == "payer_share" else "volume"

    base_query = """
        SELECT year, month, product, volume, distribution_pct
        FROM (
            SELECT year, month, product,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month), 0),
                   2) AS distribution_pct
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month, product
        ) agg
        {product_filter}
        ORDER BY product, year, month
    """

    if product:
        cur.execute(
            base_query.format(product_filter="WHERE product = %s"),
            (ta, from_year, from_month, to_year, to_month, product)
        )
    else:
        cur.execute(
            base_query.format(product_filter=""),
            (ta, from_year, from_month, to_year, to_month)
        )

    rows = cur.fetchall()
    # Return (year, month, product, selected_value)
    col_idx = 4 if metric == "payer_share" else 3
    return [(r[0], r[1], r[2], float(r[col_idx])) for r in rows]


# ---------------------------------------------------------------------------
# Tab 3 — Payer Distribution (on the fly)
# ---------------------------------------------------------------------------

def get_payer_distribution(cur, ta: str, from_year: int, from_month: int,
                            to_year: int, to_month: int,
                            payer=None, metric: str = "payer_volume") -> list:
    """Returns [(year, month, payer, value), ...]"""
    base_query = """
        SELECT year, month, payer, volume, distribution_pct
        FROM (
            SELECT year, month, payer,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month), 0),
                   2) AS distribution_pct
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month, payer
        ) agg
        {payer_filter}
        ORDER BY payer, year, month
    """

    if _payer_filter(payer):
        cur.execute(
            base_query.format(payer_filter="WHERE payer = ANY(%s::text[])"),
            (ta, from_year, from_month, to_year, to_month, _to_list(payer))
        )
    else:
        cur.execute(
            base_query.format(payer_filter=""),
            (ta, from_year, from_month, to_year, to_month)
        )

    rows = cur.fetchall()
    col_idx = 4 if metric == "payer_share" else 3
    return [(r[0], r[1], r[2], float(r[col_idx])) for r in rows]


# ---------------------------------------------------------------------------
# Tab 4 — Payer-wise Product (on the fly)
# pct_within_payer = product % within a specific payer's total
# ---------------------------------------------------------------------------

def get_payer_wise_product(cur, ta: str, from_year: int, from_month: int,
                            to_year: int, to_month: int,
                            payer=None, metric: str = "payer_volume") -> list:
    """Returns [(year, month, payer, product, value), ...]"""
    base_query = """
        SELECT year, month, payer, product, volume, pct_within_payer
        FROM (
            SELECT year, month, payer, product,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month, payer), 0),
                   2) AS pct_within_payer
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month, payer, product
        ) agg
        {payer_filter}
        ORDER BY payer, product, year, month
    """

    if _payer_filter(payer):
        cur.execute(
            base_query.format(payer_filter="WHERE payer = ANY(%s::text[])"),
            (ta, from_year, from_month, to_year, to_month, _to_list(payer))
        )
    else:
        cur.execute(
            base_query.format(payer_filter=""),
            (ta, from_year, from_month, to_year, to_month)
        )

    rows = cur.fetchall()
    col_idx = 5 if metric == "payer_share" else 4
    return [(r[0], r[1], r[2], r[3], float(r[col_idx])) for r in rows]


# ---------------------------------------------------------------------------
# Tab 5 — Product-wise Payer (on the fly)
# pct_within_product = payer % within a specific product's total
# ---------------------------------------------------------------------------

def get_product_wise_payer(cur, ta: str, from_year: int, from_month: int,
                            to_year: int, to_month: int,
                            product: str = None, metric: str = "payer_volume") -> list:
    """Returns [(year, month, product, payer, value), ...]"""
    base_query = """
        SELECT year, month, product, payer, volume, pct_within_product
        FROM (
            SELECT year, month, product, payer,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month, product), 0),
                   2) AS pct_within_product
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month, product, payer
        ) agg
        {product_filter}
        ORDER BY product, payer, year, month
    """

    if product:
        cur.execute(
            base_query.format(product_filter="WHERE product = %s"),
            (ta, from_year, from_month, to_year, to_month, product)
        )
    else:
        cur.execute(
            base_query.format(product_filter=""),
            (ta, from_year, from_month, to_year, to_month)
        )

    rows = cur.fetchall()
    col_idx = 5 if metric == "payer_share" else 4
    return [(r[0], r[1], r[2], r[3], float(r[col_idx])) for r in rows]


# ---------------------------------------------------------------------------
# Yearly variants — aggregate by year only (GROUP BY year, no month)
# All return rows with month=0 injected so callers stay consistent.
# ---------------------------------------------------------------------------

def get_total_market_volume_yearly(cur, ta: str, from_year: int, to_year: int,
                                    payer=None) -> list:
    """Returns [(year, 0, total_volume), ...]"""
    if _payer_filter(payer):
        cur.execute("""
            SELECT year, SUM(volume)
            FROM raw_liver.transaction_data
            WHERE ta = %s AND payer = ANY(%s::text[]) AND year BETWEEN %s AND %s
            GROUP BY year ORDER BY year
        """, (ta, _to_list(payer), from_year, to_year))
    else:
        cur.execute("""
            SELECT year, SUM(volume)
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year ORDER BY year
        """, (ta, from_year, to_year))
    return [(r[0], 0, float(r[1])) for r in cur.fetchall()]


def get_product_distribution_yearly(cur, ta: str, from_year: int, to_year: int,
                                     product: str = None, metric: str = "payer_volume") -> list:
    """Returns [(year, 0, product, value), ...]"""
    base_query = """
        SELECT year, product, volume, distribution_pct
        FROM (
            SELECT year, product,
                   SUM(volume) AS volume,
                   ROUND(SUM(volume) * 100.0 /
                         NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year), 0), 2
                   ) AS distribution_pct
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year, product
        ) agg
        {product_filter}
        ORDER BY product, year
    """
    if product:
        cur.execute(base_query.format(product_filter="WHERE product = %s"),
                    (ta, from_year, to_year, product))
    else:
        cur.execute(base_query.format(product_filter=""), (ta, from_year, to_year))

    col_idx = 3 if metric == "payer_share" else 2
    return [(r[0], 0, r[1], float(r[col_idx])) for r in cur.fetchall()]


def get_payer_distribution_yearly(cur, ta: str, from_year: int, to_year: int,
                                   payer=None, metric: str = "payer_volume") -> list:
    """Returns [(year, 0, payer, value), ...]"""
    base_query = """
        SELECT year, payer, volume, distribution_pct
        FROM (
            SELECT year, payer,
                   SUM(volume) AS volume,
                   ROUND(SUM(volume) * 100.0 /
                         NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year), 0), 2
                   ) AS distribution_pct
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year, payer
        ) agg
        {payer_filter}
        ORDER BY payer, year
    """
    if _payer_filter(payer):
        cur.execute(base_query.format(payer_filter="WHERE payer = ANY(%s::text[])"),
                    (ta, from_year, to_year, _to_list(payer)))
    else:
        cur.execute(base_query.format(payer_filter=""), (ta, from_year, to_year))

    col_idx = 3 if metric == "payer_share" else 2
    return [(r[0], 0, r[1], float(r[col_idx])) for r in cur.fetchall()]


def get_payer_wise_product_yearly(cur, ta: str, from_year: int, to_year: int,
                                   payer=None, metric: str = "payer_volume") -> list:
    """Returns [(year, 0, payer, product, value), ...]"""
    base_query = """
        SELECT year, payer, product, volume, pct_within_payer
        FROM (
            SELECT year, payer, product,
                   SUM(volume) AS volume,
                   ROUND(SUM(volume) * 100.0 /
                         NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, payer), 0), 2
                   ) AS pct_within_payer
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year, payer, product
        ) agg
        {payer_filter}
        ORDER BY payer, product, year
    """
    if _payer_filter(payer):
        cur.execute(base_query.format(payer_filter="WHERE payer = ANY(%s::text[])"),
                    (ta, from_year, to_year, _to_list(payer)))
    else:
        cur.execute(base_query.format(payer_filter=""), (ta, from_year, to_year))

    col_idx = 4 if metric == "payer_share" else 3
    return [(r[0], 0, r[1], r[2], float(r[col_idx])) for r in cur.fetchall()]


def get_product_wise_payer_yearly(cur, ta: str, from_year: int, to_year: int,
                                   product: str = None, metric: str = "payer_volume") -> list:
    """Returns [(year, 0, product, payer, value), ...]"""
    base_query = """
        SELECT year, product, payer, volume, pct_within_product
        FROM (
            SELECT year, product, payer,
                   SUM(volume) AS volume,
                   ROUND(SUM(volume) * 100.0 /
                         NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, product), 0), 2
                   ) AS pct_within_product
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year, product, payer
        ) agg
        {product_filter}
        ORDER BY product, payer, year
    """
    if product:
        cur.execute(base_query.format(product_filter="WHERE product = %s"),
                    (ta, from_year, to_year, product))
    else:
        cur.execute(base_query.format(product_filter=""), (ta, from_year, to_year))

    col_idx = 4 if metric == "payer_share" else 3
    return [(r[0], 0, r[1], r[2], float(r[col_idx])) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Tab 4 — Payment Type × Product  (uses payment_type column)
# pct_within_pt = product % within a specific payment_type's total
# ---------------------------------------------------------------------------

def get_payment_type_wise_product(cur, ta: str, from_year: int, from_month: int,
                                   to_year: int, to_month: int,
                                   payment_type=None, metric: str = "payer_volume") -> list:
    """Returns [(year, month, payment_type, product, value), ...]"""
    base_query = """
        SELECT year, month, payment_type, product, volume, pct_within_pt
        FROM (
            SELECT year, month, payment_type, product,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month, payment_type), 0),
                   2) AS pct_within_pt
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month, payment_type, product
        ) agg
        {pt_filter}
        ORDER BY payment_type, product, year, month
    """
    if _payer_filter(payment_type):
        cur.execute(
            base_query.format(pt_filter="WHERE payment_type = ANY(%s::text[])"),
            (ta, from_year, from_month, to_year, to_month, _to_list(payment_type))
        )
    else:
        cur.execute(base_query.format(pt_filter=""), (ta, from_year, from_month, to_year, to_month))
    rows = cur.fetchall()
    col_idx = 5 if metric == "payer_share" else 4
    return [(r[0], r[1], r[2], r[3], float(r[col_idx])) for r in rows]


def get_payment_type_wise_product_yearly(cur, ta: str, from_year: int, to_year: int,
                                          payment_type=None, metric: str = "payer_volume") -> list:
    """Returns [(year, 0, payment_type, product, value), ...]"""
    base_query = """
        SELECT year, payment_type, product, volume, pct_within_pt
        FROM (
            SELECT year, payment_type, product,
                   SUM(volume) AS volume,
                   ROUND(SUM(volume) * 100.0 /
                         NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, payment_type), 0), 2
                   ) AS pct_within_pt
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year, payment_type, product
        ) agg
        {pt_filter}
        ORDER BY payment_type, product, year
    """
    if _payer_filter(payment_type):
        cur.execute(base_query.format(pt_filter="WHERE payment_type = ANY(%s::text[])"),
                    (ta, from_year, to_year, _to_list(payment_type)))
    else:
        cur.execute(base_query.format(pt_filter=""), (ta, from_year, to_year))
    col_idx = 4 if metric == "payer_share" else 3
    return [(r[0], 0, r[1], r[2], float(r[col_idx])) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Tab 5 — Payment Type × Payer × Product  (3-level, payment_type column)
# pct = product % within the (payment_type, payer) sub-group
# ---------------------------------------------------------------------------

def get_payment_type_payer_product(cur, ta: str, from_year: int, from_month: int,
                                    to_year: int, to_month: int,
                                    payment_type=None, metric: str = "payer_volume") -> list:
    """Returns [(year, month, payment_type, payer, product, value), ...]"""
    base_query = """
        SELECT year, month, payment_type, payer, product, volume, pct_within_pt_payer
        FROM (
            SELECT year, month, payment_type, payer, product,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month, payment_type, payer), 0),
                   2) AS pct_within_pt_payer
            FROM raw_liver.transaction_data
            WHERE ta = %s
              AND (year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)
            GROUP BY year, month, payment_type, payer, product
        ) agg
        {pt_filter}
        ORDER BY payment_type, payer, product, year, month
    """
    if _payer_filter(payment_type):
        cur.execute(
            base_query.format(pt_filter="WHERE payment_type = ANY(%s::text[])"),
            (ta, from_year, from_month, to_year, to_month, _to_list(payment_type))
        )
    else:
        cur.execute(base_query.format(pt_filter=""), (ta, from_year, from_month, to_year, to_month))
    rows = cur.fetchall()
    col_idx = 6 if metric == "payer_share" else 5
    return [(r[0], r[1], r[2], r[3], r[4], float(r[col_idx])) for r in rows]


def get_payment_type_payer_product_yearly(cur, ta: str, from_year: int, to_year: int,
                                           payment_type=None, metric: str = "payer_volume") -> list:
    """Returns [(year, 0, payment_type, payer, product, value), ...]"""
    base_query = """
        SELECT year, payment_type, payer, product, volume, pct_within_pt_payer
        FROM (
            SELECT year, payment_type, payer, product,
                   SUM(volume) AS volume,
                   ROUND(SUM(volume) * 100.0 /
                         NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, payment_type, payer), 0), 2
                   ) AS pct_within_pt_payer
            FROM raw_liver.transaction_data
            WHERE ta = %s AND year BETWEEN %s AND %s
            GROUP BY year, payment_type, payer, product
        ) agg
        {pt_filter}
        ORDER BY payment_type, payer, product, year
    """
    if _payer_filter(payment_type):
        cur.execute(base_query.format(pt_filter="WHERE payment_type = ANY(%s::text[])"),
                    (ta, from_year, to_year, _to_list(payment_type)))
    else:
        cur.execute(base_query.format(pt_filter=""), (ta, from_year, to_year))
    col_idx = 5 if metric == "payer_share" else 4
    return [(r[0], 0, r[1], r[2], r[3], float(r[col_idx])) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Save / load scenario
# ---------------------------------------------------------------------------

def scenario_exists(cur, scenario_name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM raw_liver.liver_scenarios WHERE scenario_name = %s LIMIT 1",
        (scenario_name,)
    )
    return cur.fetchone() is not None


def delete_scenario(cur, scenario_name: str) -> int:
    cur.execute(
        "DELETE FROM raw_liver.liver_scenarios WHERE scenario_name = %s",
        (scenario_name,)
    )
    return cur.rowcount


def _to_full_date(d: str) -> str:
    """Ensure date is YYYY-MM-DD; appends -01 if only YYYY-MM is given."""
    if d and len(d.strip()) == 7:
        return d.strip() + "-01"
    return d


def save_scenario(cur, scenario_name: str, ta: str, payer: str, product: str,
                  from_date: str, to_date: str, chart_data: dict, factors: dict):
    from_date = _to_full_date(from_date)
    to_date   = _to_full_date(to_date)
    cur.execute("""
        INSERT INTO raw_liver.liver_scenarios
            (scenario_name, ta, payer, product, metric, from_date, to_date, chart_data, factors)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (scenario_name) DO UPDATE SET
            ta         = EXCLUDED.ta,
            payer      = EXCLUDED.payer,
            product    = EXCLUDED.product,
            metric     = EXCLUDED.metric,
            from_date  = EXCLUDED.from_date,
            to_date    = EXCLUDED.to_date,
            chart_data = jsonb_set(
                COALESCE(liver_scenarios.chart_data, '{}') - 'market_events',
                '{market_analysis}',
                EXCLUDED.chart_data->'market_analysis'
            ),
            factors    = EXCLUDED.factors,
            created_at = CURRENT_TIMESTAMP
    """, (
        scenario_name, ta, payer, product,
        "payer_volume",
        from_date, to_date,
        json.dumps(chart_data),
        json.dumps(factors),
    ))
