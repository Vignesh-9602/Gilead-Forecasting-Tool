from app.db.connection import get_connection


def get_saved_user_filter(cur, user_id: str, ta_name: str):
    cur.execute("""
        SELECT
            scenario_name,
            indication,
            lot,
            metric,
            product,
            start_date,
            end_date
        FROM raw.user_filter_preferences
        WHERE user_id = %s
          AND ta_name = %s
    """, (user_id, ta_name))

    row = cur.fetchone()

    if not row:
        return None

    return {
        "scenario_name": row[0],
        "indication": row[1],
        "lot": row[2] or "",
        "metric": row[3] or "",
        "product": row[4] or "",
        "start_date": row[5].strftime("%Y-%m-%d") if row[5] else "",
        "end_date": row[6].strftime("%Y-%m-%d") if row[6] else ""
    }


def save_user_filter(
    cur,
    user_id: str,
    ta_name: str,
    scenario_name: str,
    indication: str,
    lot: str = "",
    metric: str = "",
    product: str = "",
    start_date: str = None,
    end_date: str = None
):
    cur.execute("""
        INSERT INTO raw.user_filter_preferences (
            user_id,
            ta_name,
            scenario_name,
            indication,
            lot,
            metric,
            product,
            start_date,
            end_date,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id)
        DO UPDATE SET
            ta_name = EXCLUDED.ta_name,
            scenario_name = EXCLUDED.scenario_name,
            indication = EXCLUDED.indication,
            lot = EXCLUDED.lot,
            metric = EXCLUDED.metric,
            product = EXCLUDED.product,
            start_date = Coalesce(EXCLUDED.start_date,raw.user_filter_preferences.start_date),
            end_date = Coalesce(EXCLUDED.end_date,raw.user_filter_preferences.end_date),
            updated_at = CURRENT_TIMESTAMP
    """, (
        user_id,
        ta_name,
        scenario_name,
        indication,
        lot or "",
        metric or "",
        product or "",
        start_date,
        end_date
    ))