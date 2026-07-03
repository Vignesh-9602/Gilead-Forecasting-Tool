from app.db.connection import get_connection

def get_user_configuration(
    cur,
    user_id: str,
    ta_name: str
):
    cur.execute("""
        SELECT
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
        "market": row[0],
        "product": row[1],
        "start_date": (
            row[2].strftime("%Y-%m-%d")
            if row[2] else None
        ),
        "end_date": (
            row[3].strftime("%Y-%m-%d")
            if row[3] else None
        )
    }

def save_user_configuration(
    cur,
    user_id: str,
    ta_name: str,
    market: str,
    product: str,
    start_date: str,
    end_date: str
):
    cur.execute("""
        INSERT INTO raw_hiv_treat.user_configurations (
            user_id,
            ta_name,
            market,
            product,
            start_date,
            end_date,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (user_id, ta_name)
        DO UPDATE SET
            market = EXCLUDED.market,
            product = EXCLUDED.product,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            updated_at = CURRENT_TIMESTAMP
    """, (
        user_id,
        ta_name,
        market,
        product,
        start_date,
        end_date
    ))