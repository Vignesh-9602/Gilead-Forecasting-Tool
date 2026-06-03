import json

from fastapi import HTTPException

from app.db.connection import get_connection
from app.services.market_events_calculation import generate_market_event_impact_percent, generate_market_event_share_from_start_date


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
        # -----------------------------------------------------
        # Default filter
        # -----------------------------------------------------

        default_indication = ""
        default_scenario_name = ""

        if data:

            default_indication = sorted(
                data.keys()
            )[0]

            indication_data = data.get(default_indication, {})

            scenarios = indication_data.get("scenarios", [])

            if scenarios:
                default_scenario_name = sorted(scenarios)[0]
        return {
            "ta_name": ta_name,
            "indications": list(data.keys()),
            "data": data,
             "default_filter": {
                    "indication": default_indication,
                    "scenario_name": default_scenario_name
                }
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
                
                # frontend needs ONLY forecast_start_index inside chart
                "chart": {
                    "forecast_start_index": 0
                },

                "table": []
            }
        }
    }


def apply_market_event_filters_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        selected_scenario = payload.scenario_name.strip()

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

        chart_months = None
        forecast_start_index = 0
        global_forecast_start_date = None

        market_share_chart_series = []

        nps_table = []
        market_share_table = []

        for lot, scenario_name in lot_scenario_map.items():

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

            # =====================================================
            # 1st pass: collect raw market share values
            # =====================================================

            all_market_share_data = []

            for product, ms_chart in ms_rows:

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

                all_market_share_data.append({
                    "product": product,
                    "values": raw_market_share_values
                })

            if not all_market_share_data:
                continue

            value_length = len(all_market_share_data[0]["values"])

            # =====================================================
            # Month-wise total before normalization
            # =====================================================

            month_totals = []

            for idx in range(value_length):

                total = sum(
                    item["values"][idx]
                    for item in all_market_share_data
                    if idx < len(item["values"])
                )

                month_totals.append(total)

            # =====================================================
            # 2nd pass: normalize values month-wise
            # =====================================================

            for item in all_market_share_data:

                product = item["product"]
                raw_values = item["values"]

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
                    "chart": {
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
        selected_scenario = payload.scenario_name.strip()

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
                        "chart": {"months": [], "forecast_start_index": 0, "series": []},
                        "table": []
                    },
                    "nps": {
                        
                        "chart": {
                                "forecast_start_index": 0
                            },

                        "table": []}
                }
            }

        events_by_lot = {}
        for event in payload.events:
            events_by_lot.setdefault(event.lot, []).append(event)

        chart_months = None
        forecast_start_index = 0

        market_share_chart_series = []
        market_share_table = []
        nps_table = []

        total_events_applied = 0

        def _norm(s):
            return str(s).strip().lower() if s is not None else ""

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

            if chart_months is None:
                chart_months = nps_chart.get("months", [])
                forecast_start_index = nps_chart.get("forecast_start_index", 0)

            months = nps_chart.get("months", [])

            overall_nps_values = (
                nps_chart.get("train_values", []) +
                nps_chart.get("forecast_values", [])
            )

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
            # =====================================
            # First pass -> collect all market share values
            # =====================================

            all_market_share_data = []

            for product, ms_chart in ms_rows:

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

                market_share_values = (
                    ms_train_values +
                    ms_forecast_values
                )

                all_market_share_data.append({
                    "product": product,
                    "values": market_share_values
                })

            # =====================================
            # Normalize month-wise totals to 100
            # =====================================

            month_totals = [
                sum(
                    item["values"][idx]
                    for item in all_market_share_data
                )
                for idx in range(len(all_market_share_data[0]["values"]))
            ]


            for item in all_market_share_data:

                product = item["product"]

                market_share_values = []

                for idx, val in enumerate(item["values"]):

                    total = month_totals[idx]

                    if total == 0:
                        normalized_val = 0
                    else:
                        normalized_val = round((val / total) * 100, 2)

                    market_share_values.append(normalized_val)

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
                if event_start_date not in months:
                    continue

                start_index = months.index(event_start_date)
                forecast_periods = len(months) - start_index

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
                        resolved_source_percentages.get(source_db_key, 0.0) + float(source_pct)
                    )

                source_total_weight = sum(resolved_source_percentages.values())
                if source_total_weight <= 0:
                    continue

                current_ms_series = []
                for prod, vals in product_values_map.items():
                    vals = [float(x) for x in vals]
                    current_ms_series.append({
                        "label": prod,
                        "train_values": vals[:forecast_start_index],
                        "forecast_values": vals[forecast_start_index:],
                    })

                current_market_share_chart = {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
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

                    active = {k for k in resolved_source_percentages.keys()}
                    avail = {k: float(product_values_map[k][idx]) for k in active}

                    total_w = sum(float(resolved_source_percentages[k]) for k in active)
                    if total_w <= 0:
                        return 0.0, {}

                    weights = {k: float(resolved_source_percentages[k]) / total_w for k in active}

                    taken = {k: 0.0 for k in active}
                    remaining = need

                    while remaining > 1e-9 and active:
                        wsum = sum(weights[k] for k in active)
                        if wsum <= 0:
                            break

                        allocation = {k: remaining * (weights[k] / wsum) for k in active}

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
                            float(product_values_map[s_key][idx]) + (give * weight)
                        )

                def _normalize_month_to_100(idx: int):
                    keys = list(product_values_map.keys())

                    for k in keys:
                        product_values_map[k][idx] = max(
                            0.0,
                            min(100.0, float(product_values_map[k][idx]))
                        )

                    total_now = sum(float(product_values_map[k][idx]) for k in keys)

                    if abs(total_now - 100.0) < 1e-6:
                        for k in keys:
                            product_values_map[k][idx] = round(float(product_values_map[k][idx]), 2)
                        return

                    if total_now > 100.0:
                        excess = total_now - 100.0

                        reducible = [
                            k for k in keys
                            if k != target_db_key and float(product_values_map[k][idx]) > 0
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
                                    float(product_values_map[k][idx]) + equal_add
                                )

                    for k in keys:
                        product_values_map[k][idx] = round(
                            max(0.0, min(100.0, float(product_values_map[k][idx]))),
                            2
                        )

                for offset, desired_target in enumerate(desired_target_shares):
                    idx = start_index + offset

                    if idx >= len(months):
                        break

                    desired_target = max(0.0, min(100.0, float(desired_target)))

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
                                float(product_values_map[s_key][idx]) - float(taken_amt)
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
                "forecast_start_index": forecast_start_index,
                "total": nps_total_values,
                "children": nps_children
            }

            market_share_table.append(lot_market_share_table)
            nps_table.append(lot_nps_table)

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

        conn.commit()

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
                "forecast_start_index": existing_nps_table.get("forecast_start_index", 0),
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
                "forecast_start_index": forecast_start_index,
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
                    
                    "chart": {
                              "forecast_start_index": response_forecast_start_index
                             },

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