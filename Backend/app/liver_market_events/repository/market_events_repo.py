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


# ---------------------------------------------------------------------------
# Manage Products — CRUD on product_master, for the Manage Products modal
#
# product_master pre-dates this feature and only ever had product_name/
# active_flag (read by get_products() above, and by the equivalent functions
# in app/liver/repository/liver_repo.py and app/liver_output/repository/
# output_repo.py — all three read the exact same table, so a product created
# here is immediately visible in Model Input's and Output's own product
# dropdowns too, with no separate sync step). Audit columns added here so
# Date Added/Added By/Modified By can be tracked and shown in that modal.
# ---------------------------------------------------------------------------

def _ensure_product_master_audit_columns(cur) -> None:
    """Idempotent -- called before every write/read below."""
    cur.execute("ALTER TABLE raw_liver.product_master ADD COLUMN IF NOT EXISTS added_by TEXT")
    cur.execute("ALTER TABLE raw_liver.product_master ADD COLUMN IF NOT EXISTS added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    cur.execute("ALTER TABLE raw_liver.product_master ADD COLUMN IF NOT EXISTS modified_by TEXT")
    cur.execute("ALTER TABLE raw_liver.product_master ADD COLUMN IF NOT EXISTS modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")


def get_products_with_audit(cur) -> list:
    """
    Return every product (active AND inactive -- a removed product still
    shows in the management table with its history) with its audit columns,
    for the Manage Products screen. get_products() above (bare active names
    only) is unchanged and keeps serving every other dropdown.
    """
    _ensure_product_master_audit_columns(cur)
    cur.execute("""
        SELECT product_name, active_flag, added_by, added_at, modified_by, modified_at
        FROM raw_liver.product_master
        WHERE added_by IS NOT NULL
        ORDER BY added_at DESC NULLS LAST, product_name
    """)
    return cur.fetchall()


def create_product(cur, product_name: str, added_by: str) -> bool:
    """
    Insert a new product. Returns False (no insert) if a product with this
    name already exists -- checked explicitly rather than relying on a DB
    uniqueness constraint, since product_master's exact constraints (it
    pre-dates this feature) aren't guaranteed to include one.
    """
    _ensure_product_master_audit_columns(cur)
    cur.execute("SELECT 1 FROM raw_liver.product_master WHERE product_name = %s", (product_name,))
    if cur.fetchone() is not None:
        return False
    cur.execute("""
        INSERT INTO raw_liver.product_master
            (product_name, active_flag, added_by, added_at, modified_by, modified_at)
        VALUES (%s, 'Y', %s, CURRENT_TIMESTAMP, %s, CURRENT_TIMESTAMP)
    """, (product_name, added_by, added_by))
    return True


def update_product_name(cur, old_name: str, new_name: str, modified_by: str) -> int:
    """Rename a product. Returns rows affected (0 = old_name not found)."""
    _ensure_product_master_audit_columns(cur)
    cur.execute("""
        UPDATE raw_liver.product_master
        SET product_name = %s, modified_by = %s, modified_at = CURRENT_TIMESTAMP
        WHERE product_name = %s
    """, (new_name, modified_by, old_name))
    return cur.rowcount


def delete_product(cur, product_name: str) -> int:
    """Hard delete. Returns rows affected (0 = not found)."""
    cur.execute("DELETE FROM raw_liver.product_master WHERE product_name = %s", (product_name,))
    return cur.rowcount


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
    """Upsert the last applied filter for the market-events screen."""
    cur.execute("""
        INSERT INTO raw_liver.filter_state (ta_name, screen, selected_filter)
        VALUES (%s, 'market_events', %s::jsonb)
        ON CONFLICT (ta_name, screen)
        DO UPDATE SET
            selected_filter = EXCLUDED.selected_filter,
            updated_at      = CURRENT_TIMESTAMP
    """, (ta_name, json.dumps(selected_filter)))


def load_filter_state(cur, ta_name: str) -> dict | None:
    """Return the last saved filter for the market-events screen, or None."""
    cur.execute("""
        SELECT selected_filter
        FROM raw_liver.filter_state
        WHERE ta_name = %s AND screen = 'market_events'
    """, (ta_name,))
    row = cur.fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Impact curve configuration rows — persist each tab's configured events
#
# Requires this table (self-created on first save, no migration needed):
#   CREATE TABLE raw_liver.market_events_impact_rows (
#       ta_name       TEXT NOT NULL,
#       scenario_name TEXT NOT NULL,  -- 'BASE' or a real saved scenario name
#       tab           TEXT NOT NULL,  -- 'payer_event' | 'product_event' | 'overall_event'
#       rows          JSONB NOT NULL DEFAULT '[]',
#       updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#       PRIMARY KEY (ta_name, scenario_name, tab)
#   );
#
# Scoped per scenario (not just per ta_name/tab) because run_calculation now
# auto-saves its computed result into whichever named scenario is selected
# (see run_market_events_calculation) -- two different scenarios can have
# genuinely different event configurations for the same tab, and each must
# keep its own rows so reopening a scenario shows the events that actually
# produced its saved numbers, not whichever scenario was run most recently.
# ---------------------------------------------------------------------------

def _ensure_impact_rows_table(cur) -> None:
    """
    Idempotent/cheap -- called before every read and write below so a fresh
    DB (or the first-ever save for this feature) never hits a mid-transaction
    "relation does not exist" error, which would poison the caller's whole
    transaction rather than just this one query.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw_liver.market_events_impact_rows (
            ta_name       TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            tab           TEXT NOT NULL,
            rows          JSONB NOT NULL DEFAULT '[]',
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ta_name, scenario_name, tab)
        )
    """)

    # One-time fix-up for a table created by an earlier version of this
    # feature (2-column key: ta_name, tab, no scenario_name) -- CREATE TABLE
    # IF NOT EXISTS above is a no-op against an already-existing table even
    # with an incompatible old schema, so a leftover old table would
    # otherwise keep failing every query below with "column scenario_name
    # does not exist" forever. Gated on the column check so the DROP/ADD
    # CONSTRAINT dance (which briefly removes the uniqueness guarantee) only
    # ever runs once, not on every call.
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'raw_liver'
          AND table_name = 'market_events_impact_rows'
          AND column_name = 'scenario_name'
    """)
    if cur.fetchone() is not None:
        return

    cur.execute("""
        ALTER TABLE raw_liver.market_events_impact_rows
        ADD COLUMN scenario_name TEXT NOT NULL DEFAULT 'BASE'
    """)
    cur.execute("""
        ALTER TABLE raw_liver.market_events_impact_rows
        DROP CONSTRAINT IF EXISTS market_events_impact_rows_pkey
    """)
    cur.execute("""
        ALTER TABLE raw_liver.market_events_impact_rows
        ADD CONSTRAINT market_events_impact_rows_pkey
        PRIMARY KEY (ta_name, scenario_name, tab)
    """)


def save_impact_rows(cur, ta_name: str, scenario_name: str, tab: str, rows: list) -> None:
    """
    Persist the full set of configured event rows for one
    (ta_name, scenario_name, tab) -- whole-array replace, not per-event
    upsert: the frontend always resends the complete rows list for whichever
    tab it just ran (see run_market_events_calculation), never a single row
    to add/delete, so there is no per-row identity to key on here.
    """
    _ensure_impact_rows_table(cur)
    cur.execute("""
        INSERT INTO raw_liver.market_events_impact_rows
            (ta_name, scenario_name, tab, rows, updated_at)
        VALUES (%s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
        ON CONFLICT (ta_name, scenario_name, tab) DO UPDATE SET
            rows       = EXCLUDED.rows,
            updated_at = CURRENT_TIMESTAMP
    """, (ta_name, scenario_name, tab, json.dumps(rows)))


def load_impact_rows(cur, ta_name: str, scenario_name: str, tab: str) -> list:
    """
    Return the persisted event rows for one (ta_name, scenario_name, tab).
    Returns [] if nothing has been saved yet for this tab under this scenario.
    """
    _ensure_impact_rows_table(cur)
    cur.execute("""
        SELECT rows
        FROM raw_liver.market_events_impact_rows
        WHERE ta_name = %s AND scenario_name = %s AND tab = %s
    """, (ta_name, scenario_name, tab))
    row = cur.fetchone()
    return row[0] if row else []


def rename_product_in_impact_rows(cur, ta_name: str, old_name: str, new_name: str) -> int:
    """
    Cascade a product rename into every persisted event row, across every
    scenario and tab, that references it: products/payers/impacted_products/
    impacted_payers lists, source_percentages keys, and any event_name
    containing the old name as a substring (e.g. "Brand X Launch Event" ->
    "Brand X Renamed Launch Event"). Products are global (not scenario-
    scoped), so a rename must reach every scenario's saved rows, not just
    the active one. Returns the number of (scenario, tab) rows touched.
    """
    _ensure_impact_rows_table(cur)
    cur.execute("""
        SELECT scenario_name, tab, rows
        FROM raw_liver.market_events_impact_rows
        WHERE ta_name = %s
    """, (ta_name,))
    saved = cur.fetchall()

    touched = 0
    for scenario_name, tab, rows in saved:
        changed = False
        for row in rows:
            for key in ("payers", "products", "impacted_payers", "impacted_products"):
                vals = row.get(key)
                if isinstance(vals, list) and old_name in vals:
                    row[key] = [new_name if v == old_name else v for v in vals]
                    changed = True
            src = row.get("source_percentages")
            if isinstance(src, dict) and old_name in src:
                src[new_name] = src.pop(old_name)
                changed = True
            name = row.get("event_name")
            if isinstance(name, str) and old_name in name:
                row["event_name"] = name.replace(old_name, new_name)
                changed = True

        if changed:
            cur.execute("""
                UPDATE raw_liver.market_events_impact_rows
                SET rows = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s AND scenario_name = %s AND tab = %s
            """, (json.dumps(rows), ta_name, scenario_name, tab))
            touched += 1
    return touched


def delete_scenario_impact_rows(cur, ta_name: str, scenario_name: str) -> int:
    """Remove all market_events_impact_rows for a deleted scenario."""
    _ensure_impact_rows_table(cur)
    cur.execute(
        "DELETE FROM raw_liver.market_events_impact_rows WHERE ta_name = %s AND scenario_name = %s",
        (ta_name, scenario_name)
    )
    return cur.rowcount


def delete_product_from_impact_rows(cur, ta_name: str, product_name: str) -> dict:
    """
    Cascade a product deletion into every persisted event row, across every
    scenario: a product_event row whose OWN target is this product (its
    "launch event") is dropped entirely; every other row that merely
    references it (as context, an impacted entity, or a source_percentages
    weight) has just that reference stripped, not the whole row deleted.
    Returns {"deleted_rows": int, "updated_rows": int} across all scenarios.
    """
    _ensure_impact_rows_table(cur)
    cur.execute("""
        SELECT scenario_name, tab, rows
        FROM raw_liver.market_events_impact_rows
        WHERE ta_name = %s
    """, (ta_name,))
    saved = cur.fetchall()

    deleted_rows = 0
    updated_rows = 0
    for scenario_name, tab, rows in saved:
        new_rows = []
        table_changed = False
        for row in rows:
            if tab == "product_event":
                target_list = row.get("products") or []
                if target_list and target_list[0] == product_name:
                    deleted_rows += 1
                    table_changed = True
                    continue  # this row IS the product's own launch event

            row_changed = False
            for key in ("payers", "products", "impacted_payers", "impacted_products"):
                vals = row.get(key)
                if isinstance(vals, list) and product_name in vals:
                    row[key] = [v for v in vals if v != product_name]
                    row_changed = True
            src = row.get("source_percentages")
            if isinstance(src, dict) and product_name in src:
                src.pop(product_name)
                row_changed = True

            if row_changed:
                updated_rows += 1
                table_changed = True
            new_rows.append(row)

        if table_changed:
            cur.execute("""
                UPDATE raw_liver.market_events_impact_rows
                SET rows = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s AND scenario_name = %s AND tab = %s
            """, (json.dumps(new_rows), ta_name, scenario_name, tab))

    return {"deleted_rows": deleted_rows, "updated_rows": updated_rows}


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
