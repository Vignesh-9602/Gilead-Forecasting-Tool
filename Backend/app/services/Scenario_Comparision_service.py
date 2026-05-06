# service.py
from collections import defaultdict
from app.db.connection import get_connection


def get_filter_data(ta_name: str):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        query = """
            SELECT
                scenario_name,
                indication,
                lot,
                product,
                metric
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
            ORDER BY indication, lot, scenario_name, product
        """

        cursor.execute(query, (ta_name,))
        rows = cursor.fetchall()

        data = defaultdict(lambda: defaultdict(lambda: {
            "products": set(),
            "available_scenarios": {}
        }))

        metrics = set()

        for scenario_name, indication, lot, product, metric in rows:

            if metric:
                metrics.add(metric)

            lot_entry = data[indication][lot]

            if product:
                lot_entry["products"].add(product)

            if scenario_name not in lot_entry["available_scenarios"]:
                lot_entry["available_scenarios"][scenario_name] = {
                    "scenario_id": (
                        "Base Case" if scenario_name == "BASE" else scenario_name    
                    ),
                    "scenario_name": scenario_name
                }

        final_data = {}

        for indication, lots in data.items():
            final_data[indication] = {}

            for lot, values in lots.items():
                final_data[indication][lot] = {
                    "products": sorted(list(values["products"])),
                    "available_scenarios": list(
                        values["available_scenarios"].values()
                    )
                }

        metric_map = {
            "nps": "Overall Market Volume",
            "market_share": "Market Share"
        }

        metric_filters = [
            {
                "label": metric_map.get(metric, metric),
                "value": metric
            }
            for metric in sorted(metrics)
        ]

        return {
            "ta_name": ta_name,
            "data": final_data,
            "metric_filters": metric_filters
        }

    finally:
        cursor.close()
        conn.close()


def empty_response(payload):
    return {
        "therapy_area": payload.ta_name,
        "indication": payload.indication,
        "lot": payload.lot,
        "metric": payload.metric,
        "product": payload.product,
        "chart": {},
        "table": []
    }


def split_train_forecast(values, forecast_start_index):
    return {
        "train_values": values[:forecast_start_index],
        "forecast_values": values[forecast_start_index:]
    }


def apply_filters(payload):

    conn = get_connection()
    cursor = conn.cursor()

    metric = payload.metric.lower().strip()
    scenario_names = payload.scenario_names or []
    selected_product = payload.product.strip() if payload.product else None

    if not scenario_names:
        cursor.close()
        conn.close()
        return empty_response(payload)

    try:
        # =====================================================
        # CASE 1: NPS
        # Chart = Total Brand NPS across all products
        # Brand NPS = Overall Market Volume * Market Share / 100
        # =====================================================
        if metric == "nps":

            cursor.execute("""
                SELECT 
                    scenario_name,
                    chart
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND indication = %s
                  AND lot = %s
                  AND metric = 'nps'
                  AND scenario_name = ANY(%s)
                ORDER BY scenario_name
            """, (
                payload.ta_name,
                payload.indication,
                payload.lot,
                scenario_names
            ))

            nps_rows = cursor.fetchall()

            if not nps_rows:
                return empty_response(payload)

            cursor.execute("""
                SELECT 
                    scenario_name,
                    product,
                    chart
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND indication = %s
                  AND lot = %s
                  AND metric = 'market_share'
                  AND scenario_name = ANY(%s)
                ORDER BY scenario_name, product
            """, (
                payload.ta_name,
                payload.indication,
                payload.lot,
                scenario_names
            ))

            ms_rows = cursor.fetchall()

            market_share_map = {}

            for scenario_name, product, chart_json in ms_rows:
                market_share_map.setdefault(scenario_name, []).append({
                    "product": product,
                    "chart": chart_json
                })

            chart_months = None
            forecast_start_index = 0
            chart_series = []
            table = []

            for scenario_name, nps_chart in nps_rows:

                if not nps_chart:
                    continue

                if chart_months is None:
                    chart_months = nps_chart.get("months", [])
                    forecast_start_index = nps_chart.get("forecast_start_index", 0)

                overall_nps_values = (
                    nps_chart.get("train_values", []) +
                    nps_chart.get("forecast_values", [])
                )

                product_rows = market_share_map.get(scenario_name, [])

                children = []
                total_values = [0] * len(overall_nps_values)

                for product_row in product_rows:
                    product = product_row["product"]
                    ms_chart = product_row["chart"]

                    if not ms_chart:
                        continue

                    ms_values = (
                        ms_chart.get("train_values", []) +
                        ms_chart.get("forecast_values", [])
                    )

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

                split_values = split_train_forecast(total_values, forecast_start_index)

                chart_series.append({
                    "scenario": scenario_name,
                    "label": "Total",
                    "train_values": split_values["train_values"],
                    "forecast_values": split_values["forecast_values"]
                })

                table.append({
                    "scenario": scenario_name,
                    "total": total_values,
                    "children": children
                })

            return {
                "therapy_area": payload.ta_name,
                "indication": payload.indication,
                "lot": payload.lot,
                "metric": payload.metric,
                "product": selected_product,
                "chart": {
                    "months": chart_months or [],
                    "forecast_start_index": forecast_start_index,
                    "series": chart_series
                },
                "table": table
            }

        # =====================================================
        # CASE 2: MARKET SHARE
        # Chart = selected product only
        # Table = all products
        # =====================================================
        if metric == "market_share" and not selected_product:
            raise ValueError("product is required for market_share")

        cursor.execute("""
            SELECT 
                scenario_name,
                product,
                chart
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND indication = %s
              AND lot = %s
              AND metric = 'market_share'
              AND scenario_name = ANY(%s)
            ORDER BY scenario_name, product
        """, (
            payload.ta_name,
            payload.indication,
            payload.lot,
            scenario_names
        ))

        rows = cursor.fetchall()

        if not rows:
            return empty_response(payload)

        chart_months = None
        forecast_start_index = 0
        chart_series = []
        table_map = {}

        for scenario_name, product, chart_json in rows:

            if not chart_json:
                continue

            if chart_months is None:
                chart_months = chart_json.get("months", [])
                forecast_start_index = chart_json.get("forecast_start_index", 0)

            train_values = [
                round(v, 2)
                for v in chart_json.get("train_values", [])
            ]

            forecast_values = [
                round(v, 2)
                for v in chart_json.get("forecast_values", [])
            ]

            values = train_values + forecast_values

            if product == selected_product:
                chart_series.append({
                    "scenario": scenario_name,
                    "label": product,
                    "train_values": train_values,
                    "forecast_values": forecast_values
                })

            if scenario_name not in table_map:
                table_map[scenario_name] = {
                    "scenario": scenario_name,
                    "total": [0] * len(values),
                    "children": []
                }

            table_map[scenario_name]["total"] = [
                round(a + b, 2)
                for a, b in zip(table_map[scenario_name]["total"], values)
            ]

            table_map[scenario_name]["children"].append({
                "label": product,
                "values": values
            })

        return {
            "therapy_area": payload.ta_name,
            "indication": payload.indication,
            "lot": payload.lot,
            "metric": payload.metric,
            "product": selected_product,
            "chart": {
                "months": chart_months or [],
                "forecast_start_index": forecast_start_index,
                "series": chart_series
            },
            "table": list(table_map.values())
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()