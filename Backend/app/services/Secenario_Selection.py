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

DEFAULT_USER_ID = "default_user"


def empty_chart_table():
    return {
        "chart": {
            "months": [],
            "forecast_start_index": 0,
            "series": []
        },
        "table_data": []
    }


def build_scenario_chart_table(conn, payload):
    cursor = conn.cursor()

    metric = "nps"
    scenario_name = payload.scenario_name.strip()

    try:
        # =============================
        # 1. Get NPS chart
        # =============================
        cursor.execute("""
            SELECT chart
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND lot = %s
              AND metric = 'nps'
              AND scenario_name = %s
            LIMIT 1
        """, (
            payload.ta_name,
            payload.indication,
            payload.lot,
            scenario_name
        ))

        nps_result = cursor.fetchone()

        if not nps_result:
            raise ValueError("NPS scenario not found")

        nps_chart = nps_result[0]

        # =============================
        # 2. Get market share for multiplication only
        # =============================
        cursor.execute("""
            SELECT product, chart
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND lot = %s
              AND metric = 'market_share'
              AND scenario_name = %s
            ORDER BY product
        """, (
            payload.ta_name,
            payload.indication,
            payload.lot,
            scenario_name
        ))

        ms_rows = cursor.fetchall()

        chart_months = nps_chart.get("months", [])
        forecast_start_index = nps_chart.get("forecast_start_index", 0)

        overall_nps_values = (
            nps_chart.get("train_values", []) +
            nps_chart.get("forecast_values", [])
        )

        total_values = [0] * len(overall_nps_values)
        children = []

        for product, ms_chart in ms_rows:

            if not ms_chart:
                continue

            ms_values = (
                ms_chart.get("train_values", []) +
                ms_chart.get("forecast_values", [])
            )

            # Brand NPS = Overall NPS * Market Share / 100
            brand_nps_values = [
                round((ms / 100.0) * nps, 0)
                for ms, nps in zip(ms_values, overall_nps_values)
            ]

            total_values = [
                round(a + b, 0)
                for a, b in zip(total_values, brand_nps_values)
            ]

            children.append({
                "label": product,
                "values": brand_nps_values
            })

        train_values = total_values[:forecast_start_index]
        forecast_values = total_values[forecast_start_index:]

        chart = {
            "months": chart_months,
            "forecast_start_index": forecast_start_index,
            "series": [
                {
                    "scenario": scenario_name,
                    "label": "Total",
                    "train_values": train_values,
                    "forecast_values": forecast_values
                }
            ]
        }

        table_data = [
            {
                "scenario": scenario_name,
                "total": total_values,
                "children": children
            }
        ]

        return {
            "chart": chart,
            "table_data": table_data
        }

    finally:
        cursor.close()


def upsert_finalized_selection(conn, payload, chart, table_data):
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO raw.forecast_finalized_selections (
                user_id,
                ta_name,
                indication,
                lot,
                metric,
                selected_scenario_name,
                chart,
                table_data,
                is_finalized
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, FALSE)
            ON CONFLICT (user_id, ta_name, indication, lot, metric)
            DO UPDATE SET
                selected_scenario_name = EXCLUDED.selected_scenario_name,
                chart = EXCLUDED.chart,
                table_data = EXCLUDED.table_data,
                is_finalized = FALSE,
                updated_at = CURRENT_TIMESTAMP
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            payload.lot,
            payload.metric.lower().strip(),
            payload.scenario_name.strip(),
            json.dumps(chart),
            json.dumps(table_data)
        ))

    finally:
        cursor.close()


def get_saved_selections(conn, payload):
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT lot, selected_scenario_name
            FROM raw.forecast_finalized_selections
            WHERE user_id = %s
              AND ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            payload.metric.lower().strip()
        ))

        return cursor.fetchall()

    finally:
        cursor.close()


def save_scenario_comparision(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        metric = payload.metric.lower().strip()
        scenario_name = payload.scenario_name.strip()

        # =============================
        # 1. Check existing saved scenario for same LOT
        # =============================
        cursor.execute("""
            SELECT selected_scenario_name
            FROM raw.forecast_finalized_selections
            WHERE user_id = %s
              AND ta_name = %s
              AND indication = %s
              AND lot = %s
              AND metric = %s
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            payload.lot,
            metric
        ))

        existing = cursor.fetchone()

        # =============================
        # 2. Build chart + table from backend
        # =============================
        output = build_scenario_chart_table(conn, payload)

        chart = output["chart"]
        table_data = output["table_data"]

        # =============================
        # 3. Save / overwrite selection
        # =============================
        upsert_finalized_selection(
            conn=conn,
            payload=payload,
            chart=chart,
            table_data=table_data
        )

        # =============================
        # 4. Fetch saved selections
        # =============================
        rows = get_saved_selections(conn, payload)

        selected_map = {
            row[0]: row[1]
            for row in rows
        }

        # =============================
        # 5. Get all LOTs
        # =============================
        cursor.execute("""
            SELECT DISTINCT lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
            ORDER BY lot
        """, (
            payload.ta_name,
            payload.indication,
            metric
        ))

        all_lots = [row[0] for row in cursor.fetchall()]

        finalization_status = {
            lot: {
                "finalized": lot in selected_map,
                "scenario_name": selected_map.get(lot)
            }
            for lot in all_lots
        }

        can_finalize = all(
            status["finalized"]
            for status in finalization_status.values()
        )

        conn.commit()

        # =============================
        # 6. Message
        # =============================
        if existing and existing[0] != scenario_name:
            message = "Scenario selection updated successfully"
        else:
            message = "Scenario saved successfully"

        return {
            "message": message,
            "saved_selection": {
                "lot": payload.lot,
                "scenario_name": scenario_name
            },
            "finalization_status": finalization_status,
            "can_finalize": can_finalize
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()

def finalize_scenarios(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        metric = "nps"

        # =============================
        # 1. Get all LOTs
        # =============================
        cursor.execute("""
            SELECT DISTINCT lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
            ORDER BY lot
        """, (
            payload.ta_name,
            payload.indication,
            metric
        ))

        all_lots = [row[0] for row in cursor.fetchall()]

        if not all_lots:
            return {
                "message": "No LOTs found for selected metric",
                "finalized": False,
                "finalized_selections": {}
            }

        # =============================
        # 2. Get saved selections + scenario_id
        # =============================
        cursor.execute("""
            SELECT 
                fs.lot,
                fs.selected_scenario_name,
                sc.id AS scenario_id
            FROM raw.forecast_finalized_selections fs
            LEFT JOIN raw.forecast_scenarios sc
              ON sc.ta_name = fs.ta_name
             AND sc.indication = fs.indication
             AND sc.lot = fs.lot
             AND sc.metric = fs.metric
             AND sc.scenario_name = fs.selected_scenario_name
            WHERE fs.user_id = %s
              AND fs.ta_name = %s
              AND fs.indication = %s
              AND fs.metric = %s
              AND fs.selected_scenario_name IS NOT NULL
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            metric
        ))

        rows = cursor.fetchall()

        selected_map = {
            row[0]: {
                "scenario_id": row[2],
                "scenario_name": row[1]
            }
            for row in rows
        }

        # =============================
        # 3. Check missing LOTs
        # =============================
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

        # =============================
        # 4. Mark finalized
        # =============================
        cursor.execute("""
            UPDATE raw.forecast_finalized_selections
            SET is_finalized = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
              AND ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            metric
        ))

        conn.commit()

        return {
            "message": "All scenarios finalized successfully",
            "finalized_selections": selected_map,
            "can_finalize": True

        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()

def get_scenario_status(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        metric = payload.metric.lower().strip()

        # =============================
        # 1. Get all LOTs
        # =============================
        cursor.execute("""
            SELECT DISTINCT lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
            ORDER BY lot
        """, (
            payload.ta_name,
            payload.indication,
            metric
        ))

        all_lots = [row[0] for row in cursor.fetchall()]

        # =============================
        # 2. Get saved selections
        # =============================
        cursor.execute("""
            SELECT lot, selected_scenario_name
            FROM raw.forecast_finalized_selections
            WHERE user_id = %s
              AND ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            metric
        ))

        rows = cursor.fetchall()

        selected_map = {
            row[0]: row[1]
            for row in rows
        }

        # =============================
        # 3. Build status
        # =============================
        finalization_status = {
            lot: {
                "finalized": lot in selected_map,
                "scenario_name": selected_map.get(lot)
            }
            for lot in all_lots
        }

        can_finalize = all(
            status["finalized"]
            for status in finalization_status.values()
        )

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "metric": metric,
            "finalization_status": finalization_status,
            "can_finalize": can_finalize
        }

    finally:
        cursor.close()
        conn.close()

def clear_scenario_selections(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        metric = "nps"

        # =============================
        # 1. Get all LOTs before clearing
        # =============================
        cursor.execute("""
            SELECT DISTINCT lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND metric = %s
            ORDER BY lot
        """, (
            payload.ta_name,
            payload.indication,
            metric
        ))

        all_lots = [row[0] for row in cursor.fetchall()]

        # =============================
        # 2. Clear only selected TA + indication + metric
        # =============================
        cursor.execute("""
            DELETE FROM raw.forecast_finalized_selections
            WHERE user_id = %s
              AND ta_name = %s
              AND indication = %s
              AND metric = %s
        """, (
            DEFAULT_USER_ID,
            payload.ta_name,
            payload.indication,
            metric
        ))

        conn.commit()

        # =============================
        # 3. Build cleared status response
        # =============================
        finalization_status = {
            lot: {
                "finalized": False,
                "scenario_name": None
            }
            for lot in all_lots
        }

        return {
            "success": True,
            "message": "Scenario selections reset successfully",
            "finalization_status": finalization_status,
            "can_finalize": False
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()