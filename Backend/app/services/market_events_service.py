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
        "therapy_area": payload.ta_name,
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
        "therapy_area": payload.ta_name,
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
                "chart": {
                    "months": [],
                    "forecast_start_index": 0,
                    "series": []
                },
                "table": {
                    "nps": [],
                    "market_share": []
                }
            }

        # =====================================================
        # 2. Group events by LOT
        # =====================================================

        events_by_lot = {}

        for event in payload.events:
            events_by_lot.setdefault(event.lot, []).append(event)

        # =====================================================
        # 3. Prepare final response objects
        # =====================================================

        chart_months = None
        forecast_start_index = 0

        market_share_chart_series = []
        nps_table = []
        market_share_table = []

        total_events_applied = 0

        # =====================================================
        # 4. Process each LOT
        # =====================================================

        for lot, scenario_name in lot_scenario_map.items():

            # Fetch NPS
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

            # Fetch Market Share
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

                product_values_map[product] = (
                    ms_chart.get("train_values", []) +
                    ms_chart.get("forecast_values", [])
                )

            # =====================================================
            # 5. Apply events sequentially for this LOT
            # =====================================================

            lot_events = events_by_lot.get(lot, [])

            for event in lot_events:

                if event.target_product not in product_values_map:
                    continue

                if event.start_date not in months:
                    continue

                start_index = months.index(event.start_date)
                forecast_periods = len(months) - start_index

                impact_percents = generate_market_event_impact_percent(
                    forecast_periods=forecast_periods,
                    peak_percent=event.peak_percent,
                    duration=event.duration_months,
                    curve_type=event.curve_type,
                    k=event.k_value
                )

                source_total = sum(event.source_percentages.values())

                if source_total <= 0:
                    continue

                for offset, impact_percent in enumerate(impact_percents):

                    idx = start_index + offset

                    if idx >= len(months):
                        continue

                    # Target product gain
                    product_values_map[event.target_product][idx] = round(
                        product_values_map[event.target_product][idx] + impact_percent,
                        2
                    )

                    # Source products lose based on contribution %
                    for source_product, source_pct in event.source_percentages.items():

                        if source_product not in product_values_map:
                            continue

                        deduction = impact_percent * (source_pct / source_total)

                        product_values_map[source_product][idx] = round(
                            product_values_map[source_product][idx] - deduction,
                            2
                        )

                        # Avoid negative market share
                        product_values_map[source_product][idx] = max(
                            product_values_map[source_product][idx],
                            0
                        )

                total_events_applied += 1

            # =====================================================
            # 6. Rebuild chart/table after events
            # =====================================================

            market_share_chart_children = []
            market_share_children = []
            nps_children = []

            market_share_total_values = [0] * len(months)
            nps_total_values = [0] * len(months)

            for product, values in product_values_map.items():

                values = [round(v, 2) for v in values]

                train_values = values[:forecast_start_index]
                forecast_values = values[forecast_start_index:]

                market_share_chart_children.append({
                    "label": product,
                    "train_values": train_values,
                    "forecast_values": forecast_values
                })

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

            market_share_chart_series.append({
                "lot": lot,
                "children": market_share_chart_children
            })

            market_share_table.append({
                "lot": lot,
                "total": market_share_total_values,
                "children": market_share_children
            })

            nps_table.append({
                "lot": lot,
                "total": nps_total_values,
                "children": nps_children
            })

        # =====================================================
        # 7. Final response
        # =====================================================

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "scenario_name": payload.scenario_name,
            "events_applied": total_events_applied,
            "chart": {
                "months": chart_months or [],
                "forecast_start_index": forecast_start_index,
                "series": market_share_chart_series
            },
            "table": {
                "nps": nps_table,
                "market_share": market_share_table
            }
        }

    finally:
        cursor.close()
        conn.close()