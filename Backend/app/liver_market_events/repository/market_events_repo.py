import json

# ---------------------------------------------------------------------------
# Lookup queries — read master data from the liver database schema
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


def get_market_events_scenarios(cur) -> list:
    """Return scenario names that were saved as market events (metric='market_events')."""
    cur.execute("""
        SELECT scenario_name
        FROM raw_liver.liver_scenarios
        WHERE metric = 'market_events'
        ORDER BY created_at DESC
    """)
    return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Filter state — persist and restore the user's last selected filter per TA
#
# Requires this table in the DB:
#   CREATE TABLE raw_liver.market_events_filter_state (
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
        INSERT INTO raw_liver.market_events_filter_state (ta_name, selected_filter)
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
        FROM raw_liver.market_events_filter_state
        WHERE ta_name = %s
    """, (ta_name,))
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Global config — read date ranges from liver_configurations
# (brand column = product in market events context)
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


def get_configs_for_selection(cur, ta_name: str, payers: list, products: list) -> list:
    """
    Return config dicts for the specific (payer, brand) combinations that match
    the selected payers and products.

    Falls back to all configs for the TA if no match is found.
    Note: 'brand' in liver_configurations = 'product' in market events.
    """
    if not payers and not products:
        return get_all_configs_for_ta(cur, ta_name)

    conditions = ["LOWER(TRIM(ta_name)) = LOWER(TRIM(%s))"]
    params = [ta_name]

    if payers:
        conditions.append("payer = ANY(%s::text[])")
        params.append(payers)

    if products:
        conditions.append("brand = ANY(%s::text[])")   # brand = product
        params.append(products)

    cur.execute(f"""
        SELECT config
        FROM raw_liver.liver_configurations
        WHERE {' AND '.join(conditions)}
    """, params)

    rows = cur.fetchall()
    if not rows:
        return get_all_configs_for_ta(cur, ta_name)

    return [row[0] for row in rows]


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


# ---------------------------------------------------------------------------
# Scenario data — reuses raw_liver.liver_scenarios table
#
# market_events stores:
#   chart_data → the full event_tabs (metrics_views per tab)
#   factors    → the impact curve rows (events the user configured)
#   metric     → "market_events" (so it can be distinguished from liver scenarios if needed)
#   payer      → JSON string of selected payers
#   product    → JSON string of selected products
#
# Frontend ensures scenario names are unique (user is never allowed to save as "BASE"),
# so ON CONFLICT (scenario_name) is safe to use.
# ---------------------------------------------------------------------------

def load_market_analysis(cur, scenario_name: str) -> dict | None:
    """Load chart_data['market_analysis'] for an existing liver scenario."""
    cur.execute("""
        SELECT chart_data->'market_analysis'
        FROM raw_liver.liver_scenarios
        WHERE LOWER(TRIM(scenario_name)) = LOWER(TRIM(%s))
    """, (scenario_name,))
    row = cur.fetchone()
    return row[0] if row else None


def save_market_analysis(cur, scenario_name: str, market_analysis: dict) -> int:
    """Update chart_data['market_analysis'] in-place for an existing liver scenario."""
    cur.execute("""
        UPDATE raw_liver.liver_scenarios
        SET chart_data = jsonb_set(
            COALESCE(chart_data, '{}'),
            '{market_analysis}',
            %s::jsonb
        )
        WHERE LOWER(TRIM(scenario_name)) = LOWER(TRIM(%s))
    """, (json.dumps(market_analysis), scenario_name))
    return cur.rowcount


def load_scenario_event_tabs(cur, scenario_name: str) -> dict | None:
    """
    Load the market events data stored under chart_data['market_events'] for a scenario.
    Returns None if the scenario doesn't exist or has no market events data saved yet.
    """
    cur.execute("""
        SELECT chart_data->'market_events'
        FROM raw_liver.liver_scenarios
        WHERE LOWER(TRIM(scenario_name)) = LOWER(TRIM(%s))
    """, (scenario_name,))
    row = cur.fetchone()
    return row[0] if row else None


def save_market_events_scenario(cur, scenario_name: str, event_tabs: dict) -> int:
    """
    Persist market events data into the existing liver scenario row by writing
    event_tabs into chart_data['market_events'] via jsonb_set.

    Does NOT insert a new row — the scenario must already exist in liver_scenarios
    (created by the model input / liver module).

    Returns the number of rows updated (0 means the scenario was not found).
    """
    cur.execute("""
        UPDATE raw_liver.liver_scenarios
        SET chart_data = jsonb_set(
            COALESCE(chart_data, '{}'),
            '{market_events}',
            %s::jsonb
        )
        WHERE LOWER(TRIM(scenario_name)) = LOWER(TRIM(%s))
    """, (json.dumps(event_tabs), scenario_name))
    return cur.rowcount
