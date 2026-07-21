import json

# ---------------------------------------------------------------------------
# Lookup queries — read master data from the liver (HCV) database schema
# ---------------------------------------------------------------------------

def get_payers(cur) -> list:
    """Return all payer names from payer_master, sorted alphabetically."""
    cur.execute("SELECT payer_name FROM raw_liver.payer_master ORDER BY payer_name")
    return [row[0] for row in cur.fetchall()]


def get_products(cur) -> list:
    """Return all active product names from product_master, sorted alphabetically."""
    cur.execute(
        "SELECT product_name FROM raw_liver.product_master WHERE active_flag = %s ORDER BY product_name",
        ("Y",)
    )
    return [row[0] for row in cur.fetchall()]


def get_scenarios(cur) -> list:
    """Return all saved scenario names, most recently created first."""
    cur.execute(
        "SELECT scenario_name FROM raw_liver.liver_scenarios ORDER BY created_at DESC"
    )
    return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Filter state — persist and restore the user's last selected filter per TA
#
# Requires this table in the DB:
#   CREATE TABLE raw_liver.output_filter_state (
#       ta_name         TEXT PRIMARY KEY,
#       selected_filter JSONB NOT NULL,
#       updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#   );
# ---------------------------------------------------------------------------

def save_filter_state(cur, ta_name: str, selected_filter: dict) -> None:
    """
    Save (or overwrite) the user's last selected filter for a given TA.
    Called every time the user clicks Apply Filter.
    """
    cur.execute("""
        INSERT INTO raw_liver.output_filter_state (ta_name, selected_filter)
        VALUES (%s, %s::jsonb)
        ON CONFLICT (ta_name)
        DO UPDATE SET
            selected_filter = EXCLUDED.selected_filter,
            updated_at      = CURRENT_TIMESTAMP
    """, (ta_name, json.dumps(selected_filter)))


def load_filter_state(cur, ta_name: str) -> dict | None:
    """
    Load the user's last saved filter for a given TA.
    Returns None if the user has never applied a filter for this TA.
    """
    cur.execute("""
        SELECT selected_filter
        FROM raw_liver.output_filter_state
        WHERE ta_name = %s
    """, (ta_name,))
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Global config — read date ranges from liver_configurations
# (brand column = product in output screen context)
# ---------------------------------------------------------------------------

def get_all_configs_for_ta(cur, ta_name: str) -> list:
    """
    Return all config dicts for every (payer, brand) combination saved for a TA.
    Each config has: train_start_date, train_end_date, forecast_periods (int), model_granularity.
    """
    cur.execute("""
        SELECT config
        FROM raw_liver.liver_configurations
        WHERE LOWER(TRIM(ta_name)) = LOWER(TRIM(%s))
    """, (ta_name,))
    return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Transaction data queries
# ---------------------------------------------------------------------------

def get_volume_by_product_payer(cur, ta: str, from_year: int, from_month: int,
                                to_year: int, to_month: int,
                                payers: list = None, products: list = None) -> list:
    """
    Return (year, month, product, payer, volume) tuples from transaction_data.
    Filtered by TA and date range; optionally narrowed by payers and products.
    """
    conditions = [
        "ta = %s",
        "(year * 100 + month) BETWEEN (%s * 100 + %s) AND (%s * 100 + %s)",
    ]
    params = [ta, from_year, from_month, to_year, to_month]

    if payers:
        conditions.append("payer = ANY(%s::text[])")
        params.append(payers)

    if products:
        conditions.append("product = ANY(%s::text[])")
        params.append(products)

    query = f"""
        SELECT year, month, product, payer, SUM(volume) AS volume
        FROM raw_liver.transaction_data
        WHERE {" AND ".join(conditions)}
        GROUP BY year, month, product, payer
        ORDER BY year, month, product, payer
    """
    cur.execute(query, params)
    return cur.fetchall()


def get_distinct_months(cur, ta: str) -> list:
    """
    Return all distinct (year, month) pairs from transaction_data for the given TA,
    sorted oldest first.

    Example return value: [(2024, 6), (2024, 7), ..., (2025, 12)]
    Returns an empty list if no data exists for the given TA.
    """
    cur.execute("""
        SELECT DISTINCT year, month
        FROM raw_liver.transaction_data
        WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
        ORDER BY year, month
    """, (ta,))
    return cur.fetchall()
