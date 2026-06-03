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
        # -----------------------------------------------------
        # Default filter
        # -----------------------------------------------------

        default_indication = ""
        default_lot = ""

        if final_data:

            default_indication = sorted(
                final_data.keys()
            )[0]

            indication_lots = final_data.get(default_indication, {})

            if indication_lots:

                default_lot = sorted(
                    indication_lots.keys()
                )[0]

        return {
            "ta_name": ta_name,
            "data": final_data,
            "metric_filters": metric_filters,
            "default_filter": {
                    "indication": default_indication,
                    "lot": default_lot
                }
        }

    finally:
        cursor.close()
        conn.close()


def empty_response(payload):
    return {
        "therapy_area": payload.ta_name,
        "indication": payload.indication,
        "lot": payload.lot,
        "metric": "nps",
        "product": None,
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


def split_train_forecast(values, forecast_start_index):
    return {
        "train_values": values[:forecast_start_index],
        "forecast_values": values[forecast_start_index:]
    }


def apply_filters(payload):

    conn = get_connection()
    cursor = conn.cursor()

    # frontend sends metric, but backend always treats it as nps
    metric = "nps"

    scenario_names = payload.scenario_names or []
    selected_product = None

    if not scenario_names:
        cursor.close()
        conn.close()
        return empty_response(payload)

    try:
        # =============================
        # 1. Fetch NPS rows
        # =============================
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

        # =============================
        # 2. Fetch Market Share rows
        # =============================
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
        nps_table = []
        market_share_table = []

        # =============================
        # 3. Build chart and tables
        # =============================
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

            nps_children = []
            nps_total_values = [0] * len(overall_nps_values)

            market_share_children = []
            market_share_total_values = None

            for product_row in product_rows:
                product = product_row["product"]
                ms_chart = product_row["chart"]

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

                market_share_values = ms_train_values + ms_forecast_values

                # Brand NPS = Overall NPS * Market Share / 100
                brand_nps_values = [
                    round((ms / 100.0) * nps, 0)
                    for ms, nps in zip(market_share_values, overall_nps_values)
                ]

                nps_total_values = [
                    round(a + b, 0)
                    for a, b in zip(nps_total_values, brand_nps_values)
                ]

                nps_children.append({
                    "label": product,
                    "values": brand_nps_values
                })

                if market_share_total_values is None:
                    market_share_total_values = [0] * len(market_share_values)

                market_share_total_values = [
                    round(a + b, 2)
                    for a, b in zip(market_share_total_values, market_share_values)
                ]

                market_share_children.append({
                    "label": product,
                    "values": market_share_values
                })

            split_values = split_train_forecast(
                nps_total_values,
                forecast_start_index
            )

            # =============================
            # Chart: only NPS Total
            # =============================
            chart_series.append({
                "scenario": scenario_name,
                "label": "Total",
                "train_values": split_values["train_values"],
                "forecast_values": split_values["forecast_values"]
            })

            # =============================
            # Table: NPS
            # =============================
            nps_table.append({
                "scenario": scenario_name,
                "total": nps_total_values,
                "children": nps_children
            })

            # =============================
            # Table: Market Share
            # =============================
            market_share_table.append({
                "scenario": scenario_name,
                "total": market_share_total_values or [],
                "children": market_share_children
            })

        return {
            "therapy_area": payload.ta_name,
            "indication": payload.indication,
            "lot": payload.lot,
            "metric": "nps",
            "product": selected_product,
            "chart": {
                "months": chart_months or [],
                "forecast_start_index": forecast_start_index,
                "series": chart_series
            },
            "table": {
                "nps": nps_table,
                "market_share": market_share_table
            }
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()