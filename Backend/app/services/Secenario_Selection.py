from app.db.connection import get_connection
from app.repository.Scenario_selection import (
    upsert_scenario_selection,
    get_saved_selections
)
import json


# =========================================================
# BASE SCENARIO FUNCTIONS (NEW)
# =========================================================

def get_base_scenario(ta: str, metric: str):
    """
    Fetch BASE scenario for a TA + metric.
    BASE is global and stored with indication = 'ALL'.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT chart, table_data, factors
            FROM raw.forecast_scenarios
            WHERE scenario_name = 'BASE'
              AND ta_name = %s
              AND indication = 'ALL'
              AND metric = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (ta, metric))

        row = cur.fetchone()
        if not row:
            return None

        chart, table_data, factors = row
        return {
            "chart": chart,
            "table": table_data,
            "factors": factors
        }

    finally:
        cur.close()
        conn.close()



def save_base_scenario( ta: str,
    indication: str,
    lot: str,
    metric: str,
    product: str | None,
    chart: dict,
    factors: dict
):
    conn = get_connection()
    cur = conn.cursor()

    # ✅ Preserve case, normalize only whitespace
    indication_db = indication.strip()
    lot_db = lot.strip()
    product_db = product.strip() if product else None

    try:
        cur.execute("""
            INSERT INTO raw.forecast_scenarios (
                scenario_name,
                user_id,
                ta_name,
                indication,
                lot,
                metric,
                product,
                model_type,
                factors,
                chart
            )
            VALUES (
                'BASE',
                'system',
                %s,
                %s,
                %s,
                %s,
                %s,
                'ETS',
                %s,
                %s
            )
            ON CONFLICT (
                scenario_name,
                ta_name,
                indication,
                lot,
                metric,
                product
            )
            WHERE scenario_name = 'BASE'
            DO UPDATE SET
                chart = EXCLUDED.chart,
                factors = EXCLUDED.factors,
                updated_at = CURRENT_TIMESTAMP
        """, (
            ta,
            indication_db,
            lot_db,
            metric,
            product_db,
            json.dumps(factors),
            json.dumps(chart)
        ))

        conn.commit()

    finally:
        cur.close()
        conn.close()

def upsert_finalized_selection(conn, payload, scenario_name):
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO raw.forecast_finalized_selections (
            ta_name,
            indication,
            lot,
            metric,
            selected_scenario_id,
            selected_scenario_name,
            chart,
            table_data,
            is_finalized
        )
        VALUES  %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ta_name, indication, lot, metric)
        DO UPDATE SET
            selected_scenario_id = EXCLUDED.selected_scenario_id,
            selected_scenario_name = EXCLUDED.selected_scenario_name,
            chart = COALESCE(EXCLUDED.chart, raw.forecast_finalized_selections.chart),
            table_data = COALESCE(EXCLUDED.table_data, raw.forecast_finalized_selections.table_data),
            is_finalized = EXCLUDED.is_finalized,
            updated_at = CURRENT_TIMESTAMP
    """, (
        payload.ta_name,
        payload.indication,
        payload.lot,
        payload.metric,
        payload.scenario_id,
        scenario_name,
        payload.chart,
        payload.table_data,
        payload.finalize   # ✅ now used
    ))

    conn.commit()
    cursor.close()

def get_saved_selections(conn, payload):
    cursor = conn.cursor()

    cursor.execute("""
        SELECT lot, selected_scenario_id, selected_scenario_name
        FROM raw.forecast_finalized_selections
          AND ta_name = %s
          AND indication = %s
          AND metric = %s
    """, (
        payload.ta_name,
        payload.indication,
        payload.metric
    ))

    rows = cursor.fetchall()
    cursor.close()
    return rows

def save_scenario(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # =============================
        # 1. Get scenario name
        # =============================
        cursor.execute("""
            SELECT scenario_name
            FROM raw.forecast_scenarios
            WHERE id = %s
        """, (payload.scenario_id,))

        result = cursor.fetchone()

        if not result:
            return {"message": "Scenario not found"}

        scenario_name = result[0]

        # =============================
        # 2. Save selection
        # =============================
        upsert_finalized_selection(conn, payload, scenario_name)

        # =============================
        # 3. Fetch saved selections
        # =============================
        rows = get_saved_selections(conn, payload)

        # =============================
        # 4. Get all LOTs
        # =============================
        cursor.execute("""
            SELECT DISTINCT lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            payload.ta_name,
            payload.indication,
            payload.metric
        ))

        all_lots = [row[0] for row in cursor.fetchall()]

        # =============================
        # 5. Build boolean map
        # =============================
        selected_map = {row[0]: True for row in rows}

        finalization_status = {
            lot: selected_map.get(lot, False)
            for lot in all_lots
        }

        can_finalize = all(finalization_status.values())

        # =============================
        # 6. Response
        # =============================
        return {
            "message": "Scenario saved successfully",
            "saved_selection": {
                "lot": payload.lot,
                "scenario_id": payload.scenario_id,
                "scenario_name": scenario_name
            },
            "finalization_status": finalization_status,
            "can_finalize": can_finalize
        }

    finally:
        cursor.close()
        conn.close()

def finalize_scenarios(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Get all LOTs for selected metric
        cursor.execute("""
            SELECT DISTINCT lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            payload.ta_name,
            payload.indication,
            payload.metric
        ))

        all_lots = [row[0] for row in cursor.fetchall()]

        if not all_lots:
            return {
                "message": "No LOTs found for selected metric",
                "finalized": False,
                "finalized_selections": {}
            }

        # 2. Get saved selections
        cursor.execute("""
            SELECT 
                lot,
                selected_scenario_id,
                selected_scenario_name
            FROM raw.forecast_finalized_selections
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            payload.ta_name,
            payload.indication,
            payload.metric
        ))

        rows = cursor.fetchall()

        selected_map = {
            row[0]: {
                "scenario_id": row[1],
                "scenario_name": row[2]
            }
            for row in rows
        }

        # 3. Check missing LOTs
        missing_lots = [
            lot for lot in all_lots
            if lot not in selected_map
        ]

        if missing_lots:
            return {
                "message": f"Cannot finalize. Missing selections for LOTs: {missing_lots}",
                "finalized": False,
                "finalized_selections": selected_map
            }

        # 4. Mark finalized
        cursor.execute("""
            UPDATE raw.forecast_finalized_selections
            SET is_finalized = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            payload.ta_name,
            payload.indication,
            payload.metric
        ))

        conn.commit()

        return {
            "message": "All scenarios finalized successfully",
            "finalized": True,
            "finalized_selections": selected_map
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()