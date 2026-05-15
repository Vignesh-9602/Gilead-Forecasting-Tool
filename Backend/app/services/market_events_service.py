import json
from fastapi import HTTPException

from app.db.connection import get_connection
from app.services.market_events_calculation import generate_market_event_impact_percent


def get_market_event_filters_service(ta_name: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            WITH finalized AS (
                SELECT DISTINCT
                    indication,
                    selected_scenario_name AS scenario_name,
                    'finalized' AS display_name
                FROM raw.forecast_finalized_selections
                WHERE ta_name = %s
            ),

            created AS (
                SELECT DISTINCT
                    indication,
                    scenario_name,
                    scenario_name AS display_name
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
            ),

            combined AS (
                SELECT 
                    indication,
                    scenario_name,
                    display_name
                FROM finalized

                UNION ALL

                SELECT 
                    c.indication,
                    c.scenario_name,
                    c.display_name
                FROM created c
                LEFT JOIN finalized f
                  ON LOWER(c.indication) = LOWER(f.indication)
                 AND LOWER(c.scenario_name) = LOWER(f.scenario_name)
                WHERE f.scenario_name IS NULL
            )

            SELECT DISTINCT
                indication,
                display_name
            FROM combined
            ORDER BY indication, display_name
        """, (ta_name, ta_name))

        rows = cur.fetchall()

        data = {}

        for indication, display_name in rows:
            if indication not in data:
                data[indication] = {
                    "scenarios": []
                }

            if display_name not in data[indication]["scenarios"]:
                data[indication]["scenarios"].append(display_name)

        return {
            "ta_name": ta_name,
            "indications": list(data.keys()),
            "data": data
        }

    finally:
        cur.close()
        conn.close()

def split_train_forecast(values, forecast_start_index):
    return {
        "train_values": values[:forecast_start_index],
        "forecast_values": values[forecast_start_index:]
    }


def empty_market_event_apply_response(payload):
    return {
        "ta_name": payload.ta_name,
        "indication": payload.indication,
        "scenario_name": payload.scenario_name,

        "lots": [],
        "target_products": [],
        "source_products": [],

        "metric_filters": [
            {
                "label": "Market Share",
                "value": "market_share"
            },
            {
                "label": "Overall Market Volume",
                "value": "nps"
            }
        ],

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "scurve"
        ],

        "forecast_start_date": None,

        "metrics_data": {
            "market_share": {
                "chart": {
                    "months": [],
                    "forecast_start_index": 0,
                    "series": []
                },
                "table": []
            },
            "nps": {
                "table": []
            }
        }
    }


def apply_market_event_filters_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        selected_scenario = payload.scenario_name.strip()

        # =====================================================
        # 1. Resolve scenario per LOT
        # =====================================================

        lot_scenario_map = {}

        if selected_scenario.lower() == "finalized":

            cursor.execute("""
                SELECT DISTINCT
                    lot,
                    selected_scenario_name
                FROM raw.forecast_finalized_selections
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND selected_scenario_name IS NOT NULL
                ORDER BY lot
            """, (
                payload.ta_name,
                payload.indication
            ))

            finalized_rows = cursor.fetchall()

            for lot, scenario_name in finalized_rows:
                lot_scenario_map[lot] = scenario_name

        else:

            cursor.execute("""
                SELECT DISTINCT
                    lot
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND LOWER(scenario_name) = LOWER(%s)
                ORDER BY lot
            """, (
                payload.ta_name,
                payload.indication,
                selected_scenario
            ))

            lot_rows = cursor.fetchall()

            for row in lot_rows:
                lot = row[0]
                lot_scenario_map[lot] = selected_scenario

        if not lot_scenario_map:
            return empty_market_event_apply_response(payload)

        lots = list(lot_scenario_map.keys())

        # =====================================================
        # 2. Fetch products
        # =====================================================

        products = set()

        for lot, scenario_name in lot_scenario_map.items():

            cursor.execute("""
                SELECT DISTINCT
                    product
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(scenario_name) = LOWER(%s)
                  AND LOWER(metric) = 'market_share'
                  AND product IS NOT NULL
                ORDER BY product
            """, (
                payload.ta_name,
                payload.indication,
                lot,
                scenario_name
            ))

            product_rows = cursor.fetchall()

            for row in product_rows:
                products.add(row[0])

        products = sorted(list(products))

        # =====================================================
        # 3. Build combined chart and table data
        # =====================================================

        chart_months = None
        forecast_start_index = 0
        global_forecast_start_date = None

        market_share_chart_series = []

        nps_table = []
        market_share_table = []

        for lot, scenario_name in lot_scenario_map.items():

            # =====================================
            # Fetch NPS row
            # =====================================

            cursor.execute("""
                SELECT
                    chart
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(metric) = 'nps'
                  AND LOWER(scenario_name) = LOWER(%s)
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication,
                lot,
                scenario_name
            ))

            nps_row = cursor.fetchone()

            if not nps_row:
                continue

            nps_chart = nps_row[0]

            if not nps_chart:
                continue

            if chart_months is None:

                chart_months = nps_chart.get("months", [])

                forecast_start_index = nps_chart.get(
                    "forecast_start_index",
                    0
                )

                if (
                    chart_months
                    and forecast_start_index is not None
                    and 0 <= int(forecast_start_index) < len(chart_months)
                ):
                    global_forecast_start_date = (
                        chart_months[int(forecast_start_index)]
                    )

            overall_nps_values = (
                nps_chart.get("train_values", []) +
                nps_chart.get("forecast_values", [])
            )

            # =====================================
            # Fetch Market Share rows
            # =====================================

            cursor.execute("""
                SELECT
                    product,
                    chart
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(metric) = 'market_share'
                  AND LOWER(scenario_name) = LOWER(%s)
                  AND product IS NOT NULL
                ORDER BY product
            """, (
                payload.ta_name,
                payload.indication,
                lot,
                scenario_name
            ))

            ms_rows = cursor.fetchall()

            nps_children = []
            nps_total_values = [0] * len(overall_nps_values)

            market_share_children = []
            market_share_total_values = None

            for product, ms_chart in ms_rows:

                if not ms_chart:
                    continue

                ms_train_values = [
                    round(v, 2)
                    for v in ms_chart.get("train_values", [])
                ]

                ms_forecast_values = [
                    round(v, 2)
                    for v in ms_chart.get("forecast_values", [])
                ]

                market_share_values = (
                    ms_train_values +
                    ms_forecast_values
                )

                brand_nps_values = [
                    round((ms / 100.0) * nps, 0)
                    for ms, nps in zip(
                        market_share_values,
                        overall_nps_values
                    )
                ]

                nps_total_values = [
                    round(a + b, 0)
                    for a, b in zip(
                        nps_total_values,
                        brand_nps_values
                    )
                ]

                nps_children.append({
                    "label": product,
                    "values": brand_nps_values
                })

                if market_share_total_values is None:
                    market_share_total_values = (
                        [0] * len(market_share_values)
                    )

                market_share_total_values = [
                    round(a + b, 2)
                    for a, b in zip(
                        market_share_total_values,
                        market_share_values
                    )
                ]

                market_share_children.append({
                    "label": product,
                    "values": market_share_values
                })

                # Chart should be flat and only for market_share
                market_share_chart_series.append({
                    "lot": lot,
                    "label": product,
                    "train_values": ms_train_values,
                    "forecast_values": ms_forecast_values
                })

            nps_table.append({
                "lot": lot,
                "total": nps_total_values,
                "children": nps_children
            })

            market_share_table.append({
                "lot": lot,
                "total": market_share_total_values or [],
                "children": market_share_children
            })

        return {
        "ta_name": payload.ta_name,
        "indication": payload.indication,
        "scenario_name": payload.scenario_name,

        "lots": lots,
        "target_products": products,
        "source_products": products,

        "metric_filters": [
            {
                "label": "Market Share",
                "value": "market_share"
            },
            {
                "label": "Overall Market Volume",
                "value": "nps"
            }
        ],

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "scurve"
        ],

        "forecast_start_date": global_forecast_start_date,

        "metrics_data": {
            "market_share": {
                "chart": {
                    "months": chart_months or [],
                    "forecast_start_index": forecast_start_index,
                    "series": market_share_chart_series
                },
                "table": market_share_table
            },

            "nps": {
                "table": nps_table
            }
        }
    }

    finally:
        cursor.close()
        conn.close()



def run_market_event_calculation_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        selected_scenario = payload.scenario_name.strip()

        # =====================================================
        # 1. Resolve scenario per LOT
        # =====================================================

        lot_scenario_map = {}

        if selected_scenario.lower() == "finalized":

            cursor.execute("""
                SELECT DISTINCT
                    lot,
                    selected_scenario_name
                FROM raw.forecast_finalized_selections
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND selected_scenario_name IS NOT NULL
                ORDER BY lot
            """, (
                payload.ta_name,
                payload.indication
            ))

            for lot, scenario_name in cursor.fetchall():
                lot_scenario_map[lot] = scenario_name

        else:

            cursor.execute("""
                SELECT DISTINCT
                    lot
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND LOWER(scenario_name) = LOWER(%s)
                ORDER BY lot
            """, (
                payload.ta_name,
                payload.indication,
                selected_scenario
            ))

            for row in cursor.fetchall():
                lot_scenario_map[row[0]] = selected_scenario

        if not lot_scenario_map:
            return {
                "ta_name": payload.ta_name,
                "indication": payload.indication,
                "scenario_name": payload.scenario_name,
                "events_applied": 0,
                "metrics_data": {
                    "market_share": {
                        "chart": {
                            "months": [],
                            "forecast_start_index": 0,
                            "series": []
                        },
                        "table": []
                    },
                    "nps": {
                        "table": []
                    }
                }
            }

        # =====================================================
        # 2. Group events by LOT
        # =====================================================

        events_by_lot = {}
        for event in payload.events:
            events_by_lot.setdefault(event.lot, []).append(event)

        # =====================================================
        # 3. Prepare response objects
        # =====================================================

        chart_months = None
        forecast_start_index = 0

        market_share_chart_series = []
        market_share_table = []
        nps_table = []

        total_events_applied = 0

        # =====================================================
        # Helper: normalize product names
        # =====================================================

        def _norm(s):
            return str(s).strip().lower() if s is not None else ""

        # =====================================================
        # 4. Process each LOT
        # =====================================================

        for lot, scenario_name in lot_scenario_map.items():

            # =====================================
            # Fetch NPS row
            # =====================================

            cursor.execute("""
                SELECT chart
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(metric) = 'nps'
                  AND LOWER(scenario_name) = LOWER(%s)
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication,
                lot,
                scenario_name
            ))

            nps_row = cursor.fetchone()

            # If this LOT doesn't have NPS, skip this LOT (no DB save either)
            if not nps_row or not nps_row[0]:
                continue

            nps_chart = nps_row[0]

            if chart_months is None:
                chart_months = nps_chart.get("months", [])
                forecast_start_index = nps_chart.get("forecast_start_index", 0)

            months = nps_chart.get("months", [])

            overall_nps_values = (
                nps_chart.get("train_values", []) +
                nps_chart.get("forecast_values", [])
            )

            # =====================================
            # Fetch Market Share rows
            # =====================================

            cursor.execute("""
                SELECT
                    product,
                    chart
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(metric) = 'market_share'
                  AND LOWER(scenario_name) = LOWER(%s)
                  AND product IS NOT NULL
                ORDER BY product
            """, (
                payload.ta_name,
                payload.indication,
                lot,
                scenario_name
            ))

            ms_rows = cursor.fetchall()

            product_values_map = {}
            for product, ms_chart in ms_rows:
                if not ms_chart:
                    continue

                values = (
                    ms_chart.get("train_values", []) +
                    ms_chart.get("forecast_values", [])
                )
                product_values_map[product] = [float(v) for v in values]

            # If no market_share series exist for this LOT, skip this LOT (no DB save either)
            if not product_values_map:
                continue

            # =====================================
            # Product lookup for normalized names
            # =====================================

            product_lookup = {}
            for product in product_values_map.keys():
                product_lookup.setdefault(_norm(product), product)

            def resolve_product_name(name):
                return product_lookup.get(_norm(name))

            # =====================================================
            # 5. Apply events sequentially for this LOT
            # =====================================================

            lot_events = events_by_lot.get(lot, [])
            lot_events_applied = 0

            for event in lot_events:

                target_db_key = resolve_product_name(event.target_product)
                if not target_db_key:
                    continue

                event_start_date = str(event.start_date)
                if event_start_date not in months:
                    continue

                start_index = months.index(event_start_date)
                forecast_periods = len(months) - start_index

                impact_percents = generate_market_event_impact_percent(
                    forecast_periods=forecast_periods,
                    peak_percent=event.peak_percent,
                    duration=event.duration_months,
                    curve_type=event.curve_type,
                    k=event.k_value
                )

                resolved_source_percentages = {}

                for source_product, source_pct in (event.source_percentages or {}).items():

                    if _norm(source_product) == _norm(event.target_product):
                        continue

                    if source_pct is None or float(source_pct) <= 0:
                        continue

                    source_db_key = resolve_product_name(source_product)
                    if not source_db_key:
                        continue

                    resolved_source_percentages[source_db_key] = (
                        resolved_source_percentages.get(source_db_key, 0)
                        + float(source_pct)
                    )

                source_total = sum(resolved_source_percentages.values())
                if source_total <= 0:
                    continue

                for offset, impact_percent in enumerate(impact_percents):

                    idx = start_index + offset
                    if idx >= len(months):
                        break

                    # Target gain
                    product_values_map[target_db_key][idx] = round(
                        product_values_map[target_db_key][idx] + impact_percent,
                        2
                    )

                    # Source deductions
                    for source_db_key, source_pct in resolved_source_percentages.items():

                        deduction = impact_percent * (source_pct / source_total)

                        product_values_map[source_db_key][idx] = round(
                            product_values_map[source_db_key][idx] - deduction,
                            2
                        )

                        product_values_map[source_db_key][idx] = max(
                            product_values_map[source_db_key][idx],
                            0
                        )

                lot_events_applied += 1
                total_events_applied += 1

            # =====================================================
            # 6. Rebuild chart and table after all events for LOT
            # =====================================================

            lot_market_share_series = []
            market_share_children = []
            nps_children = []

            market_share_total_values = [0] * len(months)
            nps_total_values = [0] * len(months)

            for product, values in product_values_map.items():

                values = [round(v, 2) for v in values]

                train_values = values[:forecast_start_index]
                forecast_values = values[forecast_start_index:]

                series_obj = {
                    "lot": lot,
                    "label": product,
                    "train_values": train_values,
                    "forecast_values": forecast_values
                }

                lot_market_share_series.append(series_obj)
                market_share_chart_series.append(series_obj)

                market_share_children.append({
                    "label": product,
                    "values": values
                })

                market_share_total_values = [
                    round(a + b, 2)
                    for a, b in zip(market_share_total_values, values)
                ]

                brand_nps_values = [
                    round((ms / 100.0) * nps, 0)
                    for ms, nps in zip(values, overall_nps_values)
                ]

                nps_children.append({
                    "label": product,
                    "values": brand_nps_values
                })

                nps_total_values = [
                    round(a + b, 0)
                    for a, b in zip(nps_total_values, brand_nps_values)
                ]

            lot_market_share_table = {
                "lot": lot,
                "total": market_share_total_values,
                "children": market_share_children
            }

            lot_nps_table = {
                "lot": lot,
                "total": nps_total_values,
                "children": nps_children
            }

            market_share_table.append(lot_market_share_table)
            nps_table.append(lot_nps_table)

            # =====================================================
            # 7. Save THIS LOT output to DB (moved inside LOT loop)
            # =====================================================

            lot_market_share_chart = {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "series": lot_market_share_series
            }

            lot_events_payload = [event.dict() for event in lot_events]

            cursor.execute("""
                INSERT INTO raw.market_event_scenarios (
                    ta_name,
                    indication,
                    scenario_name,
                    lot,
                    events_payload,
                    events_applied,
                    market_share_chart,
                    market_share_table,
                    nps_table,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s::jsonb, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (ta_name, indication, scenario_name, lot)
                DO UPDATE SET
                    events_payload = EXCLUDED.events_payload,
                    events_applied = EXCLUDED.events_applied,
                    market_share_chart = EXCLUDED.market_share_chart,
                    market_share_table = EXCLUDED.market_share_table,
                    nps_table = EXCLUDED.nps_table,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                payload.ta_name,
                payload.indication,
                payload.scenario_name,
                lot,
                json.dumps(lot_events_payload),
                lot_events_applied,
                json.dumps(lot_market_share_chart),
                json.dumps(lot_market_share_table),
                json.dumps(lot_nps_table)
            ))

        # =====================================================
        # 8. Commit after all LOTs are processed
        # =====================================================

        conn.commit()

        # =====================================================
        # 9. Final response to frontend
        # =====================================================

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "scenario_name": payload.scenario_name,
            "events_applied": total_events_applied,
            "metrics_data": {
                "market_share": {
                    "chart": {
                        "months": chart_months or [],
                        "forecast_start_index": forecast_start_index,
                        "series": market_share_chart_series
                    },
                    "table": market_share_table
                },
                "nps": {
                    "table": nps_table
                }
            }
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()

def save_market_event_changes_service(payload):

    metric = payload.metric.lower().strip()

    if metric not in ["market_share", "nps"]:
        raise HTTPException(
            status_code=400,
            detail="Save supports only market_share or nps"
        )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        updated_lots = [lot_group.lot for lot_group in payload.table]

        if not updated_lots:
            raise HTTPException(
                status_code=400,
                detail="No LOT data received from frontend"
            )

        # =====================================================
        # Helper functions
        # =====================================================

        def build_chart_from_table(lot_table, months, forecast_start_index):
            series = []

            for child in lot_table["children"]:
                values = [round(float(v), 2) for v in child["values"]]

                series.append({
                    "lot": lot_table["lot"],
                    "label": child["label"],
                    "train_values": values[:forecast_start_index],
                    "forecast_values": values[forecast_start_index:]
                })

            return {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "series": series
            }

        def recalc_nps_from_market_share(ms_table, existing_nps_table):
            nps_total = existing_nps_table.get("total", [])

            nps_children = []

            for ms_child in ms_table["children"]:
                ms_values = ms_child["values"]

                brand_nps_values = [
                    round((ms / 100.0) * nps, 0)
                    for ms, nps in zip(ms_values, nps_total)
                ]

                nps_children.append({
                    "label": ms_child["label"],
                    "values": brand_nps_values
                })

            return {
                "lot": ms_table["lot"],
                "total": nps_total,
                "children": nps_children
            }

        def recalc_market_share_from_nps(nps_table):
            ms_children = []

            for child in nps_table["children"]:
                ms_values = []

                for brand_nps, total_nps in zip(child["values"], nps_table["total"]):
                    if total_nps == 0:
                        ms_values.append(0)
                    else:
                        ms_values.append(round((brand_nps / total_nps) * 100, 2))

                ms_children.append({
                    "label": child["label"],
                    "values": ms_values
                })

            return {
                "lot": nps_table["lot"],
                "total": [100.0] * len(nps_table["total"]),
                "children": ms_children
            }

        # =====================================================
        # 1. Fetch existing saved market event rows
        # =====================================================

        cursor.execute("""
            SELECT
                lot,
                events_applied,
                market_share_chart,
                market_share_table,
                nps_table
            FROM raw.market_event_scenarios
            WHERE ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND LOWER(scenario_name) = LOWER(%s)
        """, (
            payload.ta_name,
            payload.indication,
            payload.scenario_name
        ))

        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Market event scenario not found"
            )

        existing_by_lot = {
            lot.lower(): {
                "lot": lot,
                "events_applied": events_applied,
                "market_share_chart": market_share_chart,
                "market_share_table": market_share_table,
                "nps_table": nps_table
            }
            for lot, events_applied, market_share_chart, market_share_table, nps_table in rows
        }

        # =====================================================
        # 2. Update selected metric for each LOT
        # =====================================================

        for lot_group in payload.table:

            lot_key = lot_group.lot.lower()

            if lot_key not in existing_by_lot:
                raise HTTPException(
                    status_code=404,
                    detail=f"Market event scenario not found for LOT: {lot_group.lot}"
                )

            existing = existing_by_lot[lot_key]

            existing_market_share_chart = existing["market_share_chart"] or {}
            existing_market_share_table = existing["market_share_table"] or {}
            existing_nps_table = existing["nps_table"] or {}

            months = existing_market_share_chart.get("months", [])
            forecast_start_index = existing_market_share_chart.get("forecast_start_index", 0)

            if not months:
                raise HTTPException(
                    status_code=400,
                    detail=f"Months not found in existing chart for LOT: {lot_group.lot}"
                )

            updated_input_table = {
                "lot": lot_group.lot,
                "total": [round(float(v), 2) for v in lot_group.total],
                "children": [
                    {
                        "label": child.label,
                        "values": [round(float(v), 2) for v in child.values]
                    }
                    for child in lot_group.children
                ]
            }

            if metric == "market_share":
                updated_market_share_table = updated_input_table

                updated_market_share_chart = build_chart_from_table(
                    updated_market_share_table,
                    months,
                    forecast_start_index
                )

                updated_nps_table = recalc_nps_from_market_share(
                    updated_market_share_table,
                    existing_nps_table
                )

            else:
                updated_nps_table = updated_input_table

                updated_market_share_table = recalc_market_share_from_nps(
                    updated_nps_table
                )

                updated_market_share_chart = build_chart_from_table(
                    updated_market_share_table,
                    months,
                    forecast_start_index
                )

            cursor.execute("""
                UPDATE raw.market_event_scenarios
                SET
                    market_share_chart = %s::jsonb,
                    market_share_table = %s::jsonb,
                    nps_table = %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND LOWER(scenario_name) = LOWER(%s)
                  AND LOWER(lot) = LOWER(%s)
            """, (
                json.dumps(updated_market_share_chart),
                json.dumps(updated_market_share_table),
                json.dumps(updated_nps_table),
                payload.ta_name,
                payload.indication,
                payload.scenario_name,
                lot_group.lot
            ))

        conn.commit()

        # =====================================================
        # 3. Fetch updated rows again and return full data
        # =====================================================

        cursor.execute("""
            SELECT
                lot,
                events_applied,
                market_share_chart,
                market_share_table,
                nps_table
            FROM raw.market_event_scenarios
            WHERE ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND LOWER(scenario_name) = LOWER(%s)
            ORDER BY lot
        """, (
            payload.ta_name,
            payload.indication,
            payload.scenario_name
        ))

        updated_rows = cursor.fetchall()

        all_market_share_series = []
        all_market_share_table = []
        all_nps_table = []

        response_months = []
        response_forecast_start_index = 0
        total_events_applied = 0

        for lot, events_applied, ms_chart, ms_table, nps_table in updated_rows:

            total_events_applied += events_applied or 0

            if ms_chart and not response_months:
                response_months = ms_chart.get("months", [])
                response_forecast_start_index = ms_chart.get("forecast_start_index", 0)

            if ms_chart:
                all_market_share_series.extend(ms_chart.get("series", []))

            if ms_table:
                all_market_share_table.append(ms_table)

            if nps_table:
                all_nps_table.append(nps_table)

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "scenario_name": payload.scenario_name,
            "metric": metric,
            "events_applied": total_events_applied,
            "metrics_data": {
                "market_share": {
                    "chart": {
                        "months": response_months,
                        "forecast_start_index": response_forecast_start_index,
                        "series": all_market_share_series
                    },
                    "table": all_market_share_table
                },
                "nps": {
                    "table": all_nps_table
                }
            }
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()