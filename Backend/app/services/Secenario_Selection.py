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

# =========================================================
# EXISTING FUNCTION (UNCHANGED)
# =========================================================

def save_scenario(payload):
    conn = get_connection()
    cursor = conn.cursor()

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
    # 2. UPSERT selection
    # =============================
    upsert_scenario_selection(conn, payload, scenario_name)

    # =============================
    # 3. Fetch all saved selections
    # =============================
    rows = get_saved_selections(conn, payload)

    # =============================
    # 4. Build finalization status
    # =============================
    all_lots = ["1L", "2L", "3L+"]

    selected_map = {lot: True for lot, _ in rows}

    finalization_status = {
        lot: selected_map.get(lot, False)
        for lot in all_lots
    }

    can_finalize = all(finalization_status.values())

    # =============================
    # 5. Final Response
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