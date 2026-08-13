from app.db.connection import get_connection

def get_user_configuration(
    cur,
    user_id: str,
    ta_name: str
):
    cur.execute("""
        SELECT
            scenario_name,
            market,
            product,
            start_date,
            end_date
        FROM raw_hiv_treat.user_configurations
        WHERE user_id = %s
          AND ta_name = %s
    """, (user_id, ta_name))

    row = cur.fetchone()

    if not row:
        return None

    return {
        "scenario_name": row[0],
        "market": row[1],
        "product": row[2],
        "start_date": (
            row[3].strftime("%Y-%m-%d")
            if row[3] else None
        ),
        "end_date": (
            row[4].strftime("%Y-%m-%d")
            if row[4] else None
        )
    }

def save_user_configuration(
    cur,
    user_id: str,
    ta_name: str,
    market: str,
    product: str,
    start_date: str,
    end_date: str,
    scenario_name: str = None
):
    """
    Upsert the last-applied filter for a (user, ta_name), shared across every
    hiv_treat screen that reads it back (Model Input's /applyfilter here, and
    Market Events' /get_market_event_filters). scenario_name defaults to None
    so callers with no scenario concept (Model Input) don't have to pass one --
    but they also won't touch whatever scenario_name Market Events last saved,
    since a NULL value would otherwise clobber it on every Model Input apply.
    """
    cur.execute("""
        INSERT INTO raw_hiv_treat.user_configurations (
            user_id,
            ta_name,
            scenario_name,
            market,
            product,
            start_date,
            end_date,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (user_id, ta_name)
        DO UPDATE SET
            scenario_name = COALESCE(EXCLUDED.scenario_name, raw_hiv_treat.user_configurations.scenario_name),
            market = EXCLUDED.market,
            product = EXCLUDED.product,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            updated_at = CURRENT_TIMESTAMP
    """, (
        user_id,
        ta_name,
        scenario_name,
        market,
        product,
        start_date,
        end_date
    ))