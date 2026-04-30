# service.py
from collections import defaultdict
from app.db.connection import get_connection

def get_filter_data(ta_name: str):

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT DISTINCT
            id,
            scenario_name,
            indication,
            lot,
            product,
            metric
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
    """

    cursor.execute(query, (ta_name,))
    rows = cursor.fetchall()

    # Structure:
    # indication -> lot -> {products, scenarios}
    data = defaultdict(lambda: defaultdict(lambda: {
        "products": set(),
        "available_scenarios": {}
    }))

    metrics = set()

    for row in rows:
        scenario_id, scenario_name, indication, lot, product, metric = row

        lot_entry = data[indication][lot]

        # Products
        if product:
            lot_entry["products"].add(product)

        # Scenarios (avoid duplicates)
        lot_entry["available_scenarios"][scenario_id] = {
            "scenario_id": scenario_id,
            "scenario_name": scenario_name
        }

        # Metrics
        if metric:
            metrics.add(metric)

    # Convert sets → list
    final_data = {}
    for indication, lots in data.items():
        final_data[indication] = {}
        for lot, values in lots.items():
            final_data[indication][lot] = {
                "products": list(values["products"]),
                "available_scenarios": list(values["available_scenarios"].values())
            }

    # Metric mapping (you can also externalize this)
    metric_map = {
        "market_share": "Market Share",
        "nps": "New Patient Start"
    }

    metric_filters = [
        {"label": metric_map.get(m, m), "value": m}
        for m in metrics
    ]

    return {
        "ta_name": ta_name,
        "data": final_data,
        "metric_filters": metric_filters
    }

def apply_filters(payload):

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            id,
            scenario_name,
            chart,
            table_data
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
          AND indication = %s
          AND metric = %s
          AND id = ANY(%s)
    """

    cursor.execute(query, (
        payload.ta_name,
        payload.indication,
        payload.metric,
        payload.scenario_ids
    ))

    rows = cursor.fetchall()

    if not rows:
        return {
            "therapy_area": payload.ta_name,
            "indication": payload.indication,
            "lot": payload.lot,
            "metric": payload.metric,
            "chart": {},
            "table": []
        }

    chart_months = None
    forecast_index = None
    series = []
    table = []

    selected_lot = payload.lot
    metric = payload.metric

    for row in rows:
        scenario_id, scenario_name, chart_json, table_json = row

        chart_data = chart_json
        table_data = table_json

        # =============================
        # COMMON: months + forecast index
        # =============================
        if chart_months is None:
            chart_months = chart_data.get("months", [])
            forecast_index = chart_data.get("forecast_start_index", 0)

        # =====================================================
        # 🔹 CASE: NPS (DERIVED FROM MS * TOTAL NPS)
        # =====================================================
        if metric == "nps":

            chart_series = chart_data.get("series", [])

            # Filter selected LOT
            lot_series = [
                s for s in chart_series if s.get("lot") == selected_lot
            ]

            # Get TOTAL NPS series (LOT level)
            # assuming stored like: train_values + forecast_values
            total_nps_series = chart_data.get("train_values", []) + chart_data.get("forecast_values", [])

            children = []
            total = [0] * len(total_nps_series)

            for s in lot_series:
                train_vals = s.get("train_values", [])
                forecast_vals = s.get("forecast_values", [])
                ms_values = (train_vals or []) + (forecast_vals or [])

                # CORE LOGIC
                product_nps = [
                    (ms / 100.0) * nps   # if MS stored as %
                    for ms, nps in zip(ms_values, total_nps_series)
                ]

                children.append({
                    "label": s.get("label"),
                    "values": product_nps
                })

                # aggregate total
                total = [a + b for a, b in zip(total, product_nps)]

            # 👉 Chart
            series.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "values": total
            })

            # 👉 Table
            table.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "total": total,
                "children": children
            })

        # =====================================================
        # 🔹 CASE 2: MARKET SHARE
        # =====================================================
        else:
            chart_series = chart_data.get("series", [])

            # 👉 Filter only selected LOT
            lot_series = [
                s for s in chart_series if s.get("lot") == selected_lot
            ]

            children = []
            total = None

            for s in lot_series:
                train_vals = s.get("train_values", [])
                forecast_vals = s.get("forecast_values", [])
                values = (train_vals or []) + (forecast_vals or [])

                children.append({
                    "label": s.get("label"),
                    "values": values
                })

                # Build total dynamically
                if total is None:
                    total = values.copy()
                else:
                    total = [a + b for a, b in zip(total, values)]

            # 👉 Chart → aggregated total line
            series.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "values": total if total else []
            })

            # 👉 Table
            table.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "total": total if total else [],
                "children": children
            })

    # =============================
    # FINAL RESPONSE
    # =============================
    return {
        "therapy_area": payload.ta_name,
        "indication": payload.indication,
        "lot": payload.lot,
        "metric": payload.metric,
        "chart": {
            "months": chart_months,
            "forecast_start_index": forecast_index,
            "series": series
        },
        "table": table
    }