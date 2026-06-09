import json
from fastapi import HTTPException
from app.db.connection import get_connection
from app.schemas.market_events_schema import DeleteMarketEventRequest
from app.services.Retaining_Filters import get_saved_user_filter, save_user_filter
from app.services.market_events_calculation import generate_market_event_impact_percent, generate_market_event_share_from_start_date
from dateutil.relativedelta import relativedelta
from datetime import datetime

def clean_scenario_name(scenario_name: str):
    if not scenario_name:
        return ""

    scenario_name = scenario_name.strip()

    if scenario_name.lower().endswith("_finalised"):
        scenario_name = scenario_name[:-10]

    return scenario_name


def get_display_scenario_name(cur, ta_name: str, indication: str, scenario_name: str):
    base_scenario_name = clean_scenario_name(scenario_name)

    cur.execute("""
        SELECT BOOL_OR(is_finalized = TRUE)
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
          AND indication = %s
          AND scenario_name = %s
    """, (
        ta_name,
        indication,
        base_scenario_name
    ))

    row = cur.fetchone()
    is_finalized = row[0] if row else False

    return (
    "Finalised"
    if is_finalized
    else base_scenario_name
        )


def get_default_date_range(cur, ta_name: str):
    cur.execute("""
        SELECT
            MAX(month_date)::date AS end_date,
            (MAX(month_date)::date - INTERVAL '1 year')::date AS start_date
        FROM (
            SELECT
                jsonb_array_elements_text(chart->'months')::date AS month_date
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND chart IS NOT NULL
              AND chart ? 'months'
        ) t
    """, (ta_name,))

    date_row = cur.fetchone()

    if date_row and date_row[0]:
        return (
            date_row[1].strftime("%Y-%m-%d"),
            date_row[0].strftime("%Y-%m-%d")
        )

    return "", ""

def validate_saved_dates(saved_filter, default_start_date, default_end_date, available_months):
    saved_start = saved_filter.get("start_date") if saved_filter else ""
    saved_end = saved_filter.get("end_date") if saved_filter else ""

    if (
        saved_start
        and saved_end
        and saved_start in available_months
        and saved_end in available_months
    ):
        return saved_start, saved_end

    return default_start_date, default_end_date

def get_available_months_from_config(cur, ta_name: str):
    cur.execute("""
        SELECT config
        FROM raw.forecast_configurations
        WHERE config->>'ta_name' = %s
    """, (ta_name,))

    row = cur.fetchone()

    if not row:
        return []

    config = row[0]

    train_start = datetime.fromisoformat(config["train_start_date"]).replace(day=1)
    train_end = datetime.fromisoformat(config["train_end_date"]).replace(day=1)
    forecast_periods = int(config.get("forecast_periods", 0))

    forecast_end = train_end + relativedelta(months=forecast_periods)

    months = []
    current = train_start

    while current <= forecast_end:
        months.append(current.strftime("%Y-%m-%d"))
        current = current + relativedelta(months=1)

    return months

def get_market_event_filters_service(ta_name: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT DISTINCT
                indication,
                scenario_name,
                BOOL_OR(is_finalized = TRUE) AS is_finalized
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND scenario_name IS NOT NULL
              AND indication IS NOT NULL
            GROUP BY indication, scenario_name
            ORDER BY indication, scenario_name
        """, (ta_name,))

        rows = cur.fetchall()

        data = {}

        for indication, scenario_name, is_finalized in rows:

            data.setdefault(indication, {"scenarios": []})

            # Add actual scenario
            if scenario_name not in data[indication]["scenarios"]:
                data[indication]["scenarios"].append(scenario_name)

            # Add Finalised option once per indication
            if (
                is_finalized
                and "Finalised" not in data[indication]["scenarios"]
            ):
                data[indication]["scenarios"].append("Finalised")

        default_indication = ""
        default_scenario_name = ""

        if data:
            default_indication = sorted(data.keys())[0]
            scenarios = data[default_indication].get("scenarios", [])

            if scenarios:
                default_scenario_name = (
                    "Finalised"
                    if "Finalised" in scenarios
                    else "BASE"
                    if "BASE" in scenarios
                    else sorted(scenarios)[0]
                )
        default_start_date, default_end_date = get_default_date_range(
            cur,
            ta_name
        )
        available_months = get_available_months_from_config(
            cur,
            ta_name
        )
        default_filter = {
            "scenario_name": default_scenario_name,
            "indication": default_indication,
            "lot": "",
            "metric": "",
            "product": "",
            "start_date": default_start_date,
            "end_date": default_end_date
        }

        user_id = "system"

        saved_filter = get_saved_user_filter(
            cur,
            user_id,
            ta_name
        )

        if saved_filter:
            selected_indication = (
                saved_filter.get("indication")
                or default_indication
            )

            selected_scenario = get_display_scenario_name(
                cur,
                ta_name,
                selected_indication,
                saved_filter.get("scenario_name", "")
            )

            selected_filter = {
                "scenario_name": selected_scenario,
                "indication": selected_indication,
                "lot": saved_filter.get("lot", ""),
                "metric": saved_filter.get("metric", ""),
                "product": saved_filter.get("product", ""),
                "start_date": saved_filter.get("start_date") or default_start_date,
                "end_date": saved_filter.get("end_date") or default_end_date
            }
        else:
            selected_filter = default_filter

        return {
            "ta_name": ta_name,
            "indications": list(data.keys()),
            "data": data,
            "available_months": available_months,
            "selected_filter": selected_filter
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
        "start_date": payload.start_date,
        "end_date": payload.end_date,
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

                # frontend needs ONLY forecast_start_index inside chart
                "chart": {
                    "forecast_start_index": 0
                },

                "table": []
            }
        }
    }


def clean_scenario_name(scenario_name: str):
    if not scenario_name:
        return ""

    scenario_name = scenario_name.strip()

    if scenario_name.lower().endswith("_finalised"):
        scenario_name = scenario_name[:-10]

    return scenario_name


def get_filtered_indices(months, start_date, end_date):
    if not months:
        return []

    if not start_date or not end_date:
        return list(range(len(months)))

    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

    indices = []

    for idx, month in enumerate(months):
        month_dt = datetime.strptime(month, "%Y-%m-%d").date()

        if start_dt <= month_dt <= end_dt:
            indices.append(idx)

    return indices


def filter_values_by_indices(values, indices):
    return [
        values[idx]
        for idx in indices
        if idx < len(values)
    ]


def get_new_forecast_start_index(filtered_months, global_forecast_start_date):
    if not filtered_months or not global_forecast_start_date:
        return 0

    forecast_dt = datetime.strptime(
        global_forecast_start_date,
        "%Y-%m-%d"
    ).date()

    count = 0

    for month in filtered_months:
        month_dt = datetime.strptime(month, "%Y-%m-%d").date()

        if month_dt < forecast_dt:
            count += 1

    return count


def validate_date_range(start_date, end_date):
    if not start_date or not end_date:
        return

    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

    if start_dt > end_dt:
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be greater than end date."
        )
def apply_market_event_filters_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        validate_date_range(
            payload.start_date,
            payload.end_date
        )
        selected_scenario = clean_scenario_name(payload.scenario_name)

        is_finalised_selected = selected_scenario.lower() == "finalised"
        display_scenario_name = payload.scenario_name.strip()
        selected_scenario = clean_scenario_name(display_scenario_name)

        if is_finalised_selected:
            cursor.execute("""
                SELECT scenario_name
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                AND LOWER(indication) = LOWER(%s)
                AND is_finalized = TRUE
                AND scenario_name IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication
            ))

            finalised_row = cursor.fetchone()

            if not finalised_row:
                return empty_market_event_apply_response(payload)

            selected_scenario = finalised_row[0]



        lot_scenario_map = {}

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

        products = set()
        saved_events = []
        event_id = 1

        for lot, scenario_name in lot_scenario_map.items():

            cursor.execute("""
                SELECT event_payload
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(scenario_name) = LOWER(%s)
                  AND event_payload IS NOT NULL
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication,
                lot,
                scenario_name
            ))

            event_row = cursor.fetchone()

            if event_row and event_row[0]:
                event_payload = event_row[0]

                for event in event_payload:
                    event["event_id"] = event_id
                    saved_events.append(event)
                    event_id += 1

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

        chart_months = None
        filtered_months = []
        forecast_start_index = 0
        global_forecast_start_date = None

        market_share_chart_series = []

        nps_table = []
        market_share_table = []

        for lot, scenario_name in lot_scenario_map.items():

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

            if not nps_row:
                continue

            nps_chart = nps_row[0]

            if not nps_chart:
                continue

            original_months = nps_chart.get("months", [])
            original_forecast_start_index = nps_chart.get(
                "forecast_start_index",
                0
            )

            if (
                original_months
                and original_forecast_start_index is not None
                and 0 <= int(original_forecast_start_index) < len(original_months)
            ):
                global_forecast_start_date = original_months[
                    int(original_forecast_start_index)
                ]

            selected_indices = get_filtered_indices(
                original_months,
                payload.start_date,
                payload.end_date
            )

            if chart_months is None:
                chart_months = original_months
                filtered_months = filter_values_by_indices(
                    original_months,
                    selected_indices
                )

                forecast_start_index = get_new_forecast_start_index(
                    filtered_months,
                    global_forecast_start_date
                )

            overall_nps_values = (
                nps_chart.get("train_values", []) +
                nps_chart.get("forecast_values", [])
            )

            overall_nps_values = filter_values_by_indices(
                overall_nps_values,
                selected_indices
            )

            cursor.execute("""
                SELECT
                    product,
                    chart,
                    patient_metrics
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

            all_market_share_data = []

            for product, ms_chart, patient_metrics in ms_rows:

                if not ms_chart:
                    continue

                ms_train_values = [
                    float(v or 0)
                    for v in ms_chart.get("train_values", [])
                ]

                ms_forecast_values = [
                    float(v or 0)
                    for v in ms_chart.get("forecast_values", [])
                ]

                raw_market_share_values = (
                    ms_train_values +
                    ms_forecast_values
                )

                raw_market_share_values = filter_values_by_indices(
                    raw_market_share_values,
                    selected_indices
                )

                patient_metrics = patient_metrics or {}

                raw_brand_nps_values = [
                    round(float(v or 0), 0)
                    for v in patient_metrics.get("final_patient_share", [])
                ]

                brand_nps_values = filter_values_by_indices(
                    raw_brand_nps_values,
                    selected_indices
                )

                if not brand_nps_values:
                    brand_nps_values = [0] * len(raw_market_share_values)

                all_market_share_data.append({
                    "product": product,
                    "values": raw_market_share_values,
                    "brand_nps_values": brand_nps_values
                })

            if not all_market_share_data:
                continue

            value_length = len(all_market_share_data[0]["values"])

            month_totals = []

            for idx in range(value_length):
                total = sum(
                    item["values"][idx]
                    for item in all_market_share_data
                    if idx < len(item["values"])
                )

                month_totals.append(total)

            for item in all_market_share_data:

                product = item["product"]
                raw_values = item["values"]
                brand_nps_values = item["brand_nps_values"]

                market_share_values = []

                for idx, val in enumerate(raw_values):

                    total = month_totals[idx]

                    if total == 0:
                        normalized_val = 0
                    else:
                        normalized_val = round(
                            (val / total) * 100,
                            2
                        )

                    market_share_values.append(normalized_val)

                ms_train_values = market_share_values[:forecast_start_index]
                ms_forecast_values = market_share_values[forecast_start_index:]

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
                    market_share_total_values = [0] * len(market_share_values)

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

                market_share_chart_series.append({
                    "lot": lot,
                    "label": product,
                    "train_values": ms_train_values,
                    "forecast_values": ms_forecast_values
                })

            market_share_total_values = [
                round(v, 2)
                for v in market_share_total_values
            ]

            nps_table.append({
                "lot": lot,
                "forecast_start_index": forecast_start_index,
                "total": nps_total_values,
                "children": nps_children
            })

            market_share_table.append({
                "lot": lot,
                "total": market_share_total_values or [],
                "children": market_share_children
            })

        save_user_filter(
            cur=cursor,
            user_id="system",
            ta_name=payload.ta_name,
            scenario_name=display_scenario_name,
            indication=payload.indication,
            lot=lots[0] if lots else "",
            metric="nps",
            product="",
            start_date=payload.start_date,
            end_date=payload.end_date
        )

        conn.commit()

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "scenario_name": payload.scenario_name,
            "start_date": payload.start_date,
            "end_date": payload.end_date,

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
            "saved_events": saved_events,

            "metrics_data": {
                "market_share": {
                    "chart": {
                        "months": filtered_months,
                        "forecast_start_index": forecast_start_index,
                        "series": market_share_chart_series
                    },
                    "table": market_share_table
                },

                "nps": {
                    "chart": {
                        "months": filtered_months,
                        "forecast_start_index": forecast_start_index
                    },
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
        if not payload.events:
            raise HTTPException(
                status_code=400,
                detail="Please add at least one market event before running calculation."
            )

        for event in payload.events:
            if not getattr(event, "event_name", None) or not str(event.event_name).strip():
                raise HTTPException(
                    status_code=400,
                    detail="Event name is required before running calculation."
                )       
        # selected_scenario = payload.scenario_name.strip()
        display_scenario_name = payload.scenario_name.strip()
        selected_scenario = display_scenario_name

        if selected_scenario.lower().endswith("_finalised"):
            selected_scenario = selected_scenario[:-10]
            display_scenario_name = "Finalised"

        if selected_scenario.strip().upper() == "BASE":
            raise HTTPException(
                status_code=400,
                detail=(
                    "BASE scenario is read-only. "
                    "Please select another scenario before running Market Events."
                )
            )

        if selected_scenario.strip().upper() == "FINALISED":
            cursor.execute("""
                SELECT scenario_name
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                AND LOWER(indication) = LOWER(%s)
                AND is_finalized = TRUE
                AND scenario_name IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication
            ))

            finalised_row = cursor.fetchone()

            if not finalised_row:
                raise HTTPException(
                    status_code=404,
                    detail="No finalised scenario found for the selected indication."
                )

            selected_scenario = finalised_row[0]

        lot_scenario_map = {}

        cursor.execute("""
            SELECT DISTINCT lot
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
                "saved_events": [],
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
                        "chart": {
                            "forecast_start_index": 0
                        },
                        "table": []
                    }
                }
            }

        events_by_lot = {}

        for event in payload.events:
            events_by_lot.setdefault(event.lot, []).append(event)

        chart_months = None
        filtered_months = []
        forecast_start_index = 0
        global_forecast_start_date = None

        market_share_chart_series = []
        market_share_table = []
        nps_table = []

        total_events_applied = 0

        def _norm(s):
            return str(s).strip().lower() if s is not None else ""
        saved_events = []
        event_id = 1
        for lot, scenario_name in lot_scenario_map.items():

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

            if not nps_row or not nps_row[0]:
                continue

            nps_chart = nps_row[0]

            original_months = nps_chart.get("months", [])
            original_forecast_start_index = nps_chart.get("forecast_start_index", 0)

            if (
                original_months
                and original_forecast_start_index is not None
                and 0 <= int(original_forecast_start_index) < len(original_months)
            ):
                global_forecast_start_date = original_months[int(original_forecast_start_index)]

            selected_indices = get_filtered_indices(
                original_months,
                payload.start_date,
                payload.end_date
            )

            months = original_months

            if chart_months is None:
                chart_months = original_months

                filtered_months = filter_values_by_indices(
                    original_months,
                    selected_indices
                )

                forecast_start_index = get_new_forecast_start_index(
                    filtered_months,
                    global_forecast_start_date
                )

            original_forecast_start_index = nps_chart.get("forecast_start_index", 0)

            overall_nps_values = (
                nps_chart.get("train_values", []) +
                nps_chart.get("forecast_values", [])
            )

            cursor.execute("""
                SELECT product, chart
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

            all_market_share_data = []

            for product, ms_chart in ms_rows:

                if not ms_chart:
                    continue

                market_share_values = (
                    [float(v or 0) for v in ms_chart.get("train_values", [])] +
                    [float(v or 0) for v in ms_chart.get("forecast_values", [])]
                )

                all_market_share_data.append({
                    "product": product,
                    "values": market_share_values
                })

            if not all_market_share_data:
                continue

            month_totals = [
                sum(
                    item["values"][idx]
                    for item in all_market_share_data
                    if idx < len(item["values"])
                )
                for idx in range(len(all_market_share_data[0]["values"]))
            ]

            for item in all_market_share_data:

                product = item["product"]
                market_share_values = []

                for idx, val in enumerate(item["values"]):
                    total = month_totals[idx]

                    market_share_values.append(
                        round((val / total) * 100, 2)
                        if total > 0 else 0
                    )

                product_values_map[product] = market_share_values

            if not product_values_map:
                continue

            product_lookup = {}

            for product in product_values_map.keys():
                product_lookup.setdefault(_norm(product), product)

            def resolve_product_name(name):
                return product_lookup.get(_norm(name))

            lot_events = events_by_lot.get(lot, [])
            lot_events_applied = 0

            for event in lot_events:

                target_db_key = resolve_product_name(event.target_product)

                if not target_db_key:
                    continue

                event_start_date = str(event.start_date)

                if event_start_date not in filtered_months:
                    continue

                start_index = original_months.index(event_start_date)

                selected_end_index = selected_indices[-1]
                forecast_periods = selected_end_index - start_index + 1

                if forecast_periods <= 0:
                    continue

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
                        resolved_source_percentages.get(source_db_key, 0.0)
                        + float(source_pct)
                    )

                source_total_weight = sum(
                    resolved_source_percentages.values()
                )

                if source_total_weight <= 0:
                    continue

                current_ms_series = []

                for prod, vals in product_values_map.items():
                    vals = [float(x) for x in vals]

                    current_ms_series.append({
                        "label": prod,
                        "train_values": vals[:forecast_start_index],
                        "forecast_values": vals[forecast_start_index:]
                    })

                current_market_share_chart = {
                    "months": original_months,
                    "forecast_start_index": original_forecast_start_index,
                    "series": current_ms_series
                }

                desired_target_shares = generate_market_event_share_from_start_date(
                    forecast_periods=forecast_periods,
                    peak_percent=float(event.peak_percent),
                    duration=int(event.duration_months),
                    curve_type=str(event.curve_type),
                    start_date=event_start_date,
                    target_product=target_db_key,
                    market_share_chart=current_market_share_chart,
                    k=getattr(event, "k_value", None)
                )

                def _take_from_sources(idx: int, need: float):
                    need = float(need)

                    if need <= 0:
                        return 0.0, {}

                    active = set(resolved_source_percentages.keys())

                    avail = {
                        k: float(product_values_map[k][idx])
                        for k in active
                    }

                    total_w = sum(
                        float(resolved_source_percentages[k])
                        for k in active
                    )

                    if total_w <= 0:
                        return 0.0, {}

                    weights = {
                        k: float(resolved_source_percentages[k]) / total_w
                        for k in active
                    }

                    taken = {k: 0.0 for k in active}
                    remaining = need

                    while remaining > 1e-9 and active:

                        wsum = sum(weights[k] for k in active)

                        if wsum <= 0:
                            break

                        allocation = {
                            k: remaining * (weights[k] / wsum)
                            for k in active
                        }

                        round_taken = 0.0
                        exhausted = set()

                        for k in active:
                            can_take = avail[k] - taken[k]
                            take_k = min(allocation[k], can_take)

                            if take_k > 0:
                                taken[k] += take_k
                                round_taken += take_k

                            if (avail[k] - taken[k]) <= 1e-9:
                                exhausted.add(k)

                        remaining -= round_taken

                        for k in exhausted:
                            active.remove(k)

                        if round_taken <= 1e-12:
                            break

                    return sum(taken.values()), taken

                def _give_to_sources_by_event_weights(idx: int, give: float):
                    give = float(give)

                    if give <= 0:
                        return

                    for s_key, w in resolved_source_percentages.items():
                        weight = float(w) / source_total_weight

                        product_values_map[s_key][idx] = (
                            float(product_values_map[s_key][idx])
                            + (give * weight)
                        )

                def _normalize_month_to_100(idx: int):
                    keys = list(product_values_map.keys())

                    for k in keys:
                        product_values_map[k][idx] = max(
                            0.0,
                            min(100.0, float(product_values_map[k][idx]))
                        )

                    total_now = sum(
                        float(product_values_map[k][idx])
                        for k in keys
                    )

                    if abs(total_now - 100.0) < 1e-6:
                        for k in keys:
                            product_values_map[k][idx] = round(
                                float(product_values_map[k][idx]),
                                2
                            )
                        return

                    if total_now > 100.0:
                        excess = total_now - 100.0

                        reducible = [
                            k for k in keys
                            if k != target_db_key
                            and float(product_values_map[k][idx]) > 0
                        ]

                        if not reducible:
                            reducible = [
                                k for k in keys
                                if float(product_values_map[k][idx]) > 0
                            ]

                        while excess > 1e-9 and reducible:
                            reducible_total = sum(
                                float(product_values_map[k][idx])
                                for k in reducible
                            )

                            if reducible_total <= 0:
                                break

                            reduced_total = 0.0

                            for k in list(reducible):
                                cur = float(product_values_map[k][idx])
                                reduce_amt = excess * (cur / reducible_total)
                                reduce_amt = min(reduce_amt, cur)

                                product_values_map[k][idx] = cur - reduce_amt
                                reduced_total += reduce_amt

                                if float(product_values_map[k][idx]) <= 1e-9:
                                    reducible.remove(k)

                            excess -= reduced_total

                            if reduced_total <= 1e-12:
                                break

                    else:
                        remainder = 100.0 - total_now

                        candidates = [
                            k for k in keys
                            if k != target_db_key
                        ]

                        if not candidates:
                            candidates = keys

                        candidate_total = sum(
                            max(0.0, float(product_values_map[k][idx]))
                            for k in candidates
                        )

                        if candidate_total > 0:
                            for k in candidates:
                                cur = float(product_values_map[k][idx])
                                weight = cur / candidate_total
                                product_values_map[k][idx] = cur + (remainder * weight)
                        else:
                            equal_add = remainder / len(candidates)

                            for k in candidates:
                                product_values_map[k][idx] = (
                                    float(product_values_map[k][idx])
                                    + equal_add
                                )

                    for k in keys:
                        product_values_map[k][idx] = round(
                            max(
                                0.0,
                                min(100.0, float(product_values_map[k][idx]))
                            ),
                            2
                        )

                for offset, desired_target in enumerate(desired_target_shares):
                    idx = start_index + offset

                    if idx > selected_end_index:
                        break

                    desired_target = max(
                        0.0,
                        min(100.0, float(desired_target))
                    )

                    current_target = float(product_values_map[target_db_key][idx])
                    current_target = max(0.0, min(100.0, current_target))

                    delta = desired_target - current_target

                    if abs(delta) < 1e-9:
                        _normalize_month_to_100(idx)
                        continue

                    if delta > 0:
                        taken_total, taken_by_source = _take_from_sources(
                            idx,
                            need=delta
                        )

                        product_values_map[target_db_key][idx] = min(
                            100.0,
                            current_target + taken_total
                        )

                        for s_key, taken_amt in taken_by_source.items():
                            product_values_map[s_key][idx] = max(
                                0.0,
                                float(product_values_map[s_key][idx])
                                - float(taken_amt)
                            )

                    else:
                        give = -delta
                        give = min(give, current_target)

                        product_values_map[target_db_key][idx] = max(
                            0.0,
                            current_target - give
                        )

                        _give_to_sources_by_event_weights(idx, give)

                    _normalize_month_to_100(idx)

                lot_events_applied += 1
                total_events_applied += 1

            lot_market_share_series = []
            market_share_children = []
            nps_children = []

            market_share_total_values = [0] * len(filtered_months)
            nps_total_values = [0] * len(filtered_months)

            lot_events_payload = [
                event.model_dump()
                if hasattr(event, "model_dump")
                else event.dict()
                for event in lot_events
            ]
            for event_payload in lot_events_payload:
                event_copy = dict(event_payload)
                event_copy["event_id"] = event_id
                saved_events.append(event_copy)
                event_id += 1
            for product, values in product_values_map.items():

                values = [
                    round(float(v or 0), 2)
                    for v in values
                ]

                filtered_values = filter_values_by_indices(
                    values,
                    selected_indices
                )

                train_values = filtered_values[:forecast_start_index]
                forecast_values = filtered_values[forecast_start_index:]

                filtered_nps_values = filter_values_by_indices(
                    overall_nps_values,
                    selected_indices
                )

                brand_nps_values = [
                    round((ms / 100.0) * nps, 0)
                    for ms, nps in zip(filtered_values, filtered_nps_values)
                ]

                patient_metrics = {
                    "final_nps": overall_nps_values,
                    "final_market_share": values,
                    "final_patient_share": [
                        round(
                            float(nps or 0) * (float(ms or 0) / 100),
                            2
                        )
                        for nps, ms in zip(overall_nps_values, values)
                    ]
                }

                series_obj = {
                    "lot": lot,
                    "label": product,
                    "months": filtered_months,
                    "forecast_start_index": forecast_start_index,
                    "train_values": train_values,
                    "forecast_values": forecast_values
                }

                lot_market_share_series.append(series_obj)
                market_share_chart_series.append(series_obj)

                market_share_children.append({
                    "label": product,
                    "values": filtered_values
                })

                market_share_total_values = [
                    round(a + b, 2)
                    for a, b in zip(market_share_total_values, filtered_values)
                ]

                nps_children.append({
                    "label": product,
                    "values": brand_nps_values
                })

                nps_total_values = [
                    round(a + b, 0)
                    for a, b in zip(nps_total_values, brand_nps_values)
                ]

                row_chart = {
                    "months": original_months,
                    "forecast_start_index": original_forecast_start_index,
                    "train_values": values[:original_forecast_start_index],
                    "forecast_values": values[original_forecast_start_index:]
                }

                product_table = [{
                    "lot": lot,
                    "total": [100.0] * len(months),
                    "children": [
                        {
                            "label": product,
                            "values": values
                        }
                    ]
                }]

                cursor.execute("""
                    UPDATE raw.forecast_scenarios
                    SET
                        chart = %s::jsonb,
                        table_data = %s::jsonb,
                        patient_metrics = %s::jsonb,
                        event_payload = %s::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ta_name = %s
                      AND LOWER(indication) = LOWER(%s)
                      AND lot = %s
                      AND LOWER(scenario_name) = LOWER(%s)
                      AND LOWER(metric) = 'market_share'
                      AND LOWER(product) = LOWER(%s)
                """, (
                    json.dumps(row_chart),
                    json.dumps(product_table),
                    json.dumps(patient_metrics),
                    json.dumps(lot_events_payload),
                    payload.ta_name,
                    payload.indication,
                    lot,
                    selected_scenario,
                    product
                ))

            lot_market_share_table = {
                "lot": lot,
                "total": market_share_total_values,
                "children": market_share_children
            }

            lot_nps_table = {
                "lot": lot,
                "forecast_start_index": forecast_start_index,
                "total": nps_total_values,
                "children": nps_children
            }

            market_share_table.append(lot_market_share_table)
            nps_table.append(lot_nps_table)

            cursor.execute("""
                UPDATE raw.forecast_scenarios
                SET
                    table_data = %s::jsonb,
                    event_payload = %s::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND lot = %s
                  AND LOWER(scenario_name) = LOWER(%s)
                  AND LOWER(metric) = 'nps'
            """, (
                json.dumps([lot_nps_table]),
                json.dumps(lot_events_payload),
                payload.ta_name,
                payload.indication,
                lot,
                selected_scenario
            ))

        conn.commit()

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "scenario_name": payload.scenario_name,
            "events_applied": total_events_applied,
             "saved_events": saved_events,
            "metrics_data": {
                "market_share": {
                    "chart": {
                        "months": filtered_months,
                        "forecast_start_index": forecast_start_index,
                        "series": market_share_chart_series
                    },
                    "table": market_share_table
                },
                "nps": {
                    "chart": {
                        "forecast_start_index": forecast_start_index
                    },
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

def merge_selected_values(full_values, selected_values, selected_indices):
    full_values = list(full_values)

    for pos, idx in enumerate(selected_indices):
        if pos < len(selected_values) and idx < len(full_values):
            full_values[idx] = selected_values[pos]

    return full_values

def align_values(values, target_len, default=0):
    values = list(values or [])
    values = values[:target_len]

    if len(values) < target_len:
        values += [default] * (target_len - len(values))

    return values


def sum_lists(a, b, target_len, decimals=2):
    a = align_values(a, target_len, 0)
    b = align_values(b, target_len, 0)

    return [
        round(float(a[i] or 0) + float(b[i] or 0), decimals)
        for i in range(target_len)
    ]

def merge_edited_values(existing_values, edited_values, selected_indices, full_len):
    """
    Keeps full DB month length.
    Replaces only selected date-range indices with edited frontend values.
    """
    merged = align_values(existing_values, full_len, 0)

    for i, idx in enumerate(selected_indices):
        if i < len(edited_values) and idx < full_len:
            merged[idx] = round(float(edited_values[i] or 0), 2)

    return merged
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
        scenario_name = payload.scenario_name.strip()

        if scenario_name.lower().endswith("_finalised"):
            scenario_name = scenario_name[:-10]

        if scenario_name.strip().upper() == "BASE":
            raise HTTPException(
                status_code=400,
                detail=(
                    "BASE scenario is read-only Please select another scenario before running Market Events."
                )
            )

        if scenario_name.strip().upper() == "FINALISED":
            cursor.execute("""
                SELECT scenario_name
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                AND LOWER(indication) = LOWER(%s)
                AND is_finalized = TRUE
                AND scenario_name IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication
            ))

            finalised_row = cursor.fetchone()

            if not finalised_row:
                raise HTTPException(
                    status_code=404,
                    detail="No finalised scenario found for the selected indication."
                )

            scenario_name = finalised_row[0]
        saved_filter = get_saved_user_filter(
            cursor,
            "system",
            payload.ta_name
        )

        start_date = payload.start_date or (
            saved_filter.get("start_date", "")
            if saved_filter else ""
        )

        end_date = payload.end_date or (
            saved_filter.get("end_date", "")
            if saved_filter else ""
        )

        updated_lots = [lot_group.lot for lot_group in payload.table]

        if not updated_lots:
            raise HTTPException(
                status_code=400,
                detail="No LOT data received from frontend"
            )

        # =====================================================
        # 1. Fetch existing scenario rows from forecast_scenarios
        # =====================================================

        cursor.execute("""
            SELECT
                lot,
                metric,
                product,
                chart,
                table_data,
                patient_metrics,
                event_payload
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND LOWER(scenario_name) = LOWER(%s)
              AND LOWER(lot) = ANY(%s)
              AND LOWER(metric) IN ('market_share', 'nps')
        """, (
            payload.ta_name,
            payload.indication,
            scenario_name,
            [lot.lower() for lot in updated_lots]
        ))

        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Scenario data not found"
            )

        existing_by_lot = {}

        for lot, row_metric, product, chart, table_data, patient_metrics, event_payload in rows:

            lot_key = lot.lower()

            existing_by_lot.setdefault(lot_key, {
                "lot": lot,
                "nps": None,
                "market_share": {},
                "event_payload": event_payload or []
            })

            if row_metric.lower() == "nps":
                existing_by_lot[lot_key]["nps"] = {
                    "chart": chart or {},
                    "table_data": table_data or []
                }

            elif row_metric.lower() == "market_share":
                existing_by_lot[lot_key]["market_share"][product] = {
                    "chart": chart or {},
                    "table_data": table_data or [],
                    "patient_metrics": patient_metrics or {}
                }

        # =====================================================
        # Helper functions
        # =====================================================

        def build_chart_from_values(months, forecast_start_index, lot, product, values):
            return {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "train_values": values[:forecast_start_index],
                "forecast_values": values[forecast_start_index:]
            }

        def build_patient_metrics(nps_values, ms_values):
            target_len = max(len(nps_values or []), len(ms_values or []))

            nps_values = align_values(nps_values, target_len, 0)
            ms_values = align_values(ms_values, target_len, 0)

            return {
                "final_nps": [
                    round(float(x or 0), 2)
                    for x in nps_values
                ],
                "final_market_share": [
                    round(float(x or 0), 2)
                    for x in ms_values
                ],
                "final_patient_share": [
                    round(
                        float(nps_values[i] or 0) * (float(ms_values[i] or 0) / 100),
                        2
                    )
                    for i in range(target_len)
                ]
            }

        def normalize_market_share_children(children):
            if not children:
                return children

            value_len = len(children[0]["values"])

            month_totals = []

            for idx in range(value_len):
                month_total = sum(
                    float(child["values"][idx] or 0)
                    for child in children
                    if idx < len(child["values"])
                )
                month_totals.append(month_total)

            normalized_children = []

            for child in children:
                values = []

                for idx, val in enumerate(child["values"]):
                    total = month_totals[idx]

                    if total == 0:
                        values.append(0)
                    else:
                        values.append(
                            round((float(val or 0) / total) * 100, 2)
                        )

                normalized_children.append({
                    "label": child["label"],
                    "values": values
                })

            return normalized_children

        # =====================================================
        # 2. Update selected LOTs
        # =====================================================

        for lot_group in payload.table:

            lot_key = lot_group.lot.lower()

            if lot_key not in existing_by_lot:
                raise HTTPException(
                    status_code=404,
                    detail=f"Scenario data not found for LOT: {lot_group.lot}"
                )

            existing = existing_by_lot[lot_key]

            nps_row = existing.get("nps")

            if not nps_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"NPS row not found for LOT: {lot_group.lot}"
                )

            nps_chart = nps_row["chart"] or {}

            months = nps_chart.get("months", [])
            forecast_start_index = nps_chart.get("forecast_start_index", 0)

            selected_indices_for_save = get_filtered_indices(
                months,
                start_date,
                end_date
            )

            if not selected_indices_for_save:
                selected_indices_for_save = list(range(len(months)))

            if not months:
                raise HTTPException(
                    status_code=400,
                    detail=f"Months not found for LOT: {lot_group.lot}"
                )

            existing_nps_values = (
                nps_chart.get("train_values", []) +
                nps_chart.get("forecast_values", [])
            )

            input_children = []

            for child in lot_group.children:
                product = child.label

                existing_values = []

                if metric == "market_share":
                    existing_product_row = existing["market_share"].get(product)

                    if existing_product_row and existing_product_row.get("chart"):
                        existing_values = (
                            existing_product_row["chart"].get("train_values", []) +
                            existing_product_row["chart"].get("forecast_values", [])
                        )
                else:
                    existing_values = [0] * len(months)

                edited_values = [
                    round(float(v or 0), 2)
                    for v in child.values
                ]

                final_values = merge_edited_values(
                    existing_values,
                    edited_values,
                    selected_indices_for_save,
                    len(months)
                )

                input_children.append({
                    "label": product,
                    "values": final_values
                })

            # =================================================
            # CASE 1: User edited MARKET SHARE
            # =================================================
            if metric == "market_share":

                updated_ms_children = normalize_market_share_children(
                    input_children
                )

                updated_ms_total = [100.0] * len(months)

                updated_nps_children = []
                updated_nps_total = [0] * len(months)

                for child in updated_ms_children:

                    product = child["label"]
                    ms_values = child["values"]

                    patient_metrics = build_patient_metrics(
                        existing_nps_values,
                        ms_values
                    )

                    brand_patient_values = [
                        round(float(v or 0), 0)
                        for v in patient_metrics["final_patient_share"]
                    ]

                    updated_nps_children.append({
                        "label": product,
                        "values": brand_patient_values
                    })

                    updated_nps_total = sum_lists(
                        updated_nps_total,
                        brand_patient_values,
                        len(months),
                        decimals=0
                    )

                    row_chart = build_chart_from_values(
                        months,
                        forecast_start_index,
                        lot_group.lot,
                        product,
                        ms_values
                    )

                    row_table = [{
                        "lot": lot_group.lot,
                        "total": updated_ms_total,
                        "children": [child]
                    }]

                    cursor.execute("""
                        UPDATE raw.forecast_scenarios
                        SET
                            chart = %s::jsonb,
                            table_data = %s::jsonb,
                            patient_metrics = %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE ta_name = %s
                          AND LOWER(indication) = LOWER(%s)
                          AND LOWER(scenario_name) = LOWER(%s)
                          AND LOWER(lot) = LOWER(%s)
                          AND LOWER(metric) = 'market_share'
                          AND LOWER(product) = LOWER(%s)
                    """, (
                        json.dumps(row_chart),
                        json.dumps(row_table),
                        json.dumps(patient_metrics),
                        payload.ta_name,
                        payload.indication,
                        scenario_name,
                        lot_group.lot,
                        product
                    ))

                updated_nps_table = {
                    "lot": lot_group.lot,
                    "forecast_start_index": forecast_start_index,
                    "total": updated_nps_total,
                    "children": updated_nps_children
                }

                cursor.execute("""
                    UPDATE raw.forecast_scenarios
                    SET
                        table_data = %s::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ta_name = %s
                      AND LOWER(indication) = LOWER(%s)
                      AND LOWER(scenario_name) = LOWER(%s)
                      AND LOWER(lot) = LOWER(%s)
                      AND LOWER(metric) = 'nps'
                """, (
                    json.dumps([updated_nps_table]),
                    payload.ta_name,
                    payload.indication,
                    scenario_name,
                    lot_group.lot
                ))

            # =================================================
            # CASE 2: User edited NPS / patient volume table
            # =================================================
            else:

                updated_nps_children = input_children

                updated_nps_total = merge_edited_values(
                    existing_nps_values,
                    [round(float(v or 0), 2) for v in lot_group.total],
                    selected_indices_for_save,
                    len(months)
                )

                if not updated_nps_total:
                    updated_nps_total = [0] * len(months)

                    for child in updated_nps_children:
                        updated_nps_total = sum_lists(
                            updated_nps_total,
                            child["values"],
                            len(months),
                            decimals=2
                        )

                updated_ms_children = []

                for child in updated_nps_children:

                    product = child["label"]
                    brand_patient_values = child["values"]

                    ms_values = []

                    for brand_patient, total_nps in zip(
                        brand_patient_values,
                        updated_nps_total
                    ):
                        if float(total_nps or 0) == 0:
                            ms_values.append(0)
                        else:
                            ms_values.append(
                                round(
                                    (float(brand_patient or 0) / float(total_nps))
                                    * 100,
                                    2
                                )
                            )

                    updated_ms_children.append({
                        "label": product,
                        "values": ms_values
                    })

                    patient_metrics = build_patient_metrics(
                        updated_nps_total,
                        ms_values
                    )

                    row_chart = build_chart_from_values(
                        months,
                        forecast_start_index,
                        lot_group.lot,
                        product,
                        ms_values
                    )

                    row_table = [{
                        "lot": lot_group.lot,
                        "total": [100.0] * len(months),
                        "children": [{
                            "label": product,
                            "values": ms_values
                        }]
                    }]

                    cursor.execute("""
                        UPDATE raw.forecast_scenarios
                        SET
                            chart = %s::jsonb,
                            table_data = %s::jsonb,
                            patient_metrics = %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE ta_name = %s
                          AND LOWER(indication) = LOWER(%s)
                          AND LOWER(scenario_name) = LOWER(%s)
                          AND LOWER(lot) = LOWER(%s)
                          AND LOWER(metric) = 'market_share'
                          AND LOWER(product) = LOWER(%s)
                    """, (
                        json.dumps(row_chart),
                        json.dumps(row_table),
                        json.dumps(patient_metrics),
                        payload.ta_name,
                        payload.indication,
                        scenario_name,
                        lot_group.lot,
                        product
                    ))

                updated_nps_table = {
                    "lot": lot_group.lot,
                    "forecast_start_index": forecast_start_index,
                    "total": updated_nps_total,
                    "children": updated_nps_children
                }

                cursor.execute("""
                    UPDATE raw.forecast_scenarios
                    SET
                        table_data = %s::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ta_name = %s
                      AND LOWER(indication) = LOWER(%s)
                      AND LOWER(scenario_name) = LOWER(%s)
                      AND LOWER(lot) = LOWER(%s)
                      AND LOWER(metric) = 'nps'
                """, (
                    json.dumps([updated_nps_table]),
                    payload.ta_name,
                    payload.indication,
                    scenario_name,
                    lot_group.lot
                ))

        save_user_filter(
            cur=cursor,
            user_id="system",
            ta_name=payload.ta_name,
            scenario_name=payload.scenario_name,
            indication=payload.indication,
            lot=updated_lots[0] if updated_lots else "",
            metric=metric,
            product="",
            start_date=start_date,
            end_date=end_date
            )

        conn.commit()

        # =====================================================
        # 3. Fetch updated full response from forecast_scenarios
        # =====================================================

        cursor.execute("""
            SELECT
                lot,
                metric,
                product,
                chart,
                table_data,
                patient_metrics,
                event_payload
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND LOWER(scenario_name) = LOWER(%s)
              AND LOWER(metric) IN ('market_share', 'nps')
            ORDER BY lot, metric, product
        """, (
            payload.ta_name,
            payload.indication,
            scenario_name
        ))

        updated_rows = cursor.fetchall()

        market_share_series = []
        market_share_table_map = {}
        nps_table_map = {}

        response_months = []
        filtered_response_months = []
        selected_indices = []
        response_forecast_start_index = 0


        saved_events = []
        event_id = 1

        for lot, row_metric, product, chart, table_data, patient_metrics, event_payload in updated_rows:

            if chart and not response_months:
                response_months = chart.get("months", [])
                original_forecast_start_index = chart.get("forecast_start_index", 0)

                selected_indices = get_filtered_indices(
                    response_months,
                    start_date,
                    end_date
                )

                filtered_response_months = filter_values_by_indices(
                    response_months,
                    selected_indices
                )

                response_forecast_start_index = get_new_forecast_start_index(
                    filtered_response_months,
                    response_months[original_forecast_start_index]
                    if original_forecast_start_index < len(response_months)
                    else None
                )
            if event_payload:
                for event in event_payload:
                    event_copy = dict(event)
                    event_copy["event_id"] = event_id
                    saved_events.append(event_copy)
                    event_id += 1

            if row_metric.lower() == "market_share":

                values = []
                if chart:
                    values = (
                        chart.get("train_values", []) +
                        chart.get("forecast_values", [])
                    )

                    values = filter_values_by_indices(
                        values,
                        selected_indices
                    )

                    market_share_series.append({
                        "lot": lot,
                        "label": product,
                        "train_values": values[:response_forecast_start_index],
                        "forecast_values": values[response_forecast_start_index:]
                    })

                market_share_table_map.setdefault(lot, {
                    "lot": lot,
                    "total": [100.0] * len(values),
                    "children": []
                })

                market_share_table_map[lot]["children"].append({
                    "label": product,
                    "values": values
                })

                if patient_metrics:
                    brand_values = [
                        round(float(v or 0), 0)
                        for v in patient_metrics.get(
                            "final_patient_share",
                            []
                        )
                    ]
                    brand_values = filter_values_by_indices(
                            brand_values,
                            selected_indices
                        )

                    nps_table_map.setdefault(lot, {
                        "lot": lot,
                        "forecast_start_index": response_forecast_start_index,
                        "total": [0] * len(brand_values),
                        "children": []
                    })

                    nps_table_map[lot]["children"].append({
                        "label": product,
                        "values": brand_values
                    })

                    nps_table_map[lot]["total"] = sum_lists(
                        nps_table_map[lot]["total"],
                        brand_values,
                        len(filtered_response_months),
                        decimals=0
                    )

        return {
            "ta_name": payload.ta_name,
            "indication": payload.indication,
            "scenario_name": payload.scenario_name,
            "metric": metric,
            "start_date": start_date,
            "end_date": end_date,
            "saved_events": saved_events,
            "metrics_data": {
                "market_share": {
                    "chart": {
                        "months": filtered_response_months,
                        "forecast_start_index": response_forecast_start_index,
                        "series": market_share_series
                    },
                    "table": list(market_share_table_map.values())
                },
                "nps": {
                    "chart": {
                        "forecast_start_index": response_forecast_start_index
                    },
                    "table": list(nps_table_map.values())
                }
            }
        }

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()

def delete_market_event_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        scenario_name = payload.scenario_name.strip()
        if scenario_name.lower().endswith("_finalised"):
            scenario_name = scenario_name[:-10]

        if scenario_name.strip().upper() == "BASE":
            raise HTTPException(
                status_code=400,
                detail=(
                    "BASE scenario is read-only. "
                    "Please select another scenario before deleting Market Events."
                )
            )

        if scenario_name.strip().upper() == "FINALISED":
            cursor.execute("""
                SELECT scenario_name
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
                AND LOWER(indication) = LOWER(%s)
                AND is_finalized = TRUE
                AND scenario_name IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
            """, (
                payload.ta_name,
                payload.indication
            ))

            finalised_row = cursor.fetchone()

            if not finalised_row:
                raise HTTPException(
                    status_code=404,
                    detail="No finalised scenario found for the selected indication."
                )

            scenario_name = finalised_row[0]

        cursor.execute("""
            SELECT DISTINCT
                lot,
                event_payload
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND LOWER(scenario_name) = LOWER(%s)
              AND event_payload IS NOT NULL
              AND event_payload <> '[]'::jsonb
            ORDER BY lot
        """, (
            payload.ta_name,
            payload.indication,
            scenario_name
        ))

        rows = cursor.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No saved events found for this scenario"
            )

        global_event_id = 1
        target_lot = None
        target_index = None
        target_events = None

        for lot, event_payload in rows:
            for idx, event in enumerate(event_payload):
                if global_event_id == payload.event_id:
                    target_lot = lot
                    target_index = idx
                    target_events = event_payload
                    break

                global_event_id += 1

            if target_lot:
                break

        if target_lot is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid event_id"
            )

        updated_events = [
            event
            for idx, event in enumerate(target_events)
            if idx != target_index
        ]

        cursor.execute("""
            UPDATE raw.forecast_scenarios
            SET
                event_payload = %s::jsonb,
                updated_at = CURRENT_TIMESTAMP
            WHERE ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND LOWER(scenario_name) = LOWER(%s)
              AND lot = %s
        """, (
            json.dumps(updated_events),
            payload.ta_name,
            payload.indication,
            scenario_name,
            target_lot
        ))

        conn.commit()

        return {
            "message": "Event deleted successfully",
            "saved_events": [
                {
                    **dict(event),
                    "event_id": idx + 1
                }
                for idx, event in enumerate(updated_events)
            ]
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()