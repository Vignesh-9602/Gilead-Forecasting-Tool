from app.db.connection import get_connection
def upsert_scenario_selection(conn, payload, scenario_name):
    cursor = conn.cursor()

    DEFAULT_USER = "default_user"

    query = """
    INSERT INTO raw.scenario_selections
    (user_id, ta_name, indication, metric, lot, scenario_id, scenario_name)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id, ta_name, indication, metric, lot)
    DO UPDATE SET
        scenario_id = EXCLUDED.scenario_id,
        scenario_name = EXCLUDED.scenario_name,
        updated_at = CURRENT_TIMESTAMP
    """

    cursor.execute(query, (
        DEFAULT_USER,
        payload.ta_name,
        payload.indication,
        payload.metric,
        payload.lot,
        payload.scenario_id,
        scenario_name
    ))

    conn.commit()


def get_saved_selections(conn, payload):
    cursor = conn.cursor()

    DEFAULT_USER = "default_user"

    query = """
        SELECT lot, scenario_id
        FROM raw.scenario_selections
        WHERE user_id = %s
          AND ta_name = %s
          AND indication = %s
          AND metric = %s
    """

    cursor.execute(query, (
        DEFAULT_USER,
        payload.ta_name,
        payload.indication,
        payload.metric
    ))

    return cursor.fetchall()