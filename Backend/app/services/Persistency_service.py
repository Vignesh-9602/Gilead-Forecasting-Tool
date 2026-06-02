import json
import math
from datetime import datetime
from app.db.connection import get_connection
from app.schemas.Vial_Calculator_schema import PersistencyApplyCurveRequest, PersistencyCalculateApplyRequest
from app.services.Vial_Calculator_functions import build_avg_vials_per_dose_table, build_demand_vials_table, build_inventory_table, save_ex_factory_output

def _extract_brands_from_market_share_table(
    market_share_table
):
    if not market_share_table:
        return []

    # Handle list response
    if isinstance(market_share_table, list):

        if not market_share_table:
            return []

        market_share_table = market_share_table[0]

    children = market_share_table.get(
        "children",
        []
    )

    brands = []

    for child in children:

        label = child.get("label")

        if label and label not in brands:
            brands.append(label)

    return brands


def get_persistency_filters_service(ta_name: str):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            WITH event_scenarios AS (
                SELECT DISTINCT
                    scenario_name
                FROM raw.market_event_scenarios
                WHERE ta_name = %s
                  AND scenario_name IS NOT NULL
            ),

            finalized AS (
                SELECT DISTINCT
                    selected_scenario_name AS scenario_name
                FROM raw.forecast_finalized_selections
                WHERE ta_name = %s
                  AND selected_scenario_name IS NOT NULL
            ),

            scenario_filters AS (

                -- 1. Highest priority: market event scenarios
                SELECT DISTINCT
                    es.scenario_name,
                    es.scenario_name AS display_scenario_name,
                    1 AS priority
                FROM event_scenarios es

                UNION ALL

                -- 2. Finalised scenarios only if not already present in market events
                SELECT DISTINCT
                    f.scenario_name,
                    f.scenario_name AS display_scenario_name,
                    2 AS priority
                FROM finalized f
                WHERE f.scenario_name NOT IN (
                    SELECT scenario_name
                    FROM event_scenarios
                )

                UNION ALL

                -- 3. Forecast scenarios only if not already present in events/finalised
                SELECT DISTINCT
                    fs.scenario_name,
                    fs.scenario_name AS display_scenario_name,
                    3 AS priority
                FROM raw.forecast_scenarios fs
                WHERE fs.ta_name = %s
                  AND fs.scenario_name IS NOT NULL
                  AND fs.scenario_name NOT IN (
                        SELECT scenario_name
                        FROM event_scenarios
                  )
                  AND fs.scenario_name NOT IN (
                        SELECT scenario_name
                        FROM finalized
                  )
            ),

            latest_event_data AS (
                SELECT DISTINCT ON (
                    sf.display_scenario_name,
                    mes.indication,
                    mes.lot
                )
                    sf.display_scenario_name AS scenario_name,
                    mes.indication,
                    mes.lot,
                    mes.nps_table
                FROM scenario_filters sf
                JOIN raw.market_event_scenarios mes
                  ON mes.ta_name = %s
                 AND mes.scenario_name = sf.scenario_name
                WHERE sf.priority = 1
                  AND mes.nps_table IS NOT NULL
                ORDER BY
                    sf.display_scenario_name,
                    mes.indication,
                    mes.lot,
                    mes.updated_at DESC
            ),

            latest_finalized_data AS (
                SELECT DISTINCT ON (
                    sf.display_scenario_name,
                    ffs.indication,
                    ffs.lot
                )
                    sf.display_scenario_name AS scenario_name,
                    ffs.indication,
                    ffs.lot,
                    ffs.table_data AS nps_table
                FROM scenario_filters sf
                JOIN raw.forecast_finalized_selections ffs
                  ON ffs.ta_name = %s
                 AND ffs.selected_scenario_name = sf.scenario_name
                WHERE sf.priority = 2
                  AND LOWER(ffs.metric) = 'nps'
                  AND ffs.table_data IS NOT NULL
                ORDER BY
                    sf.display_scenario_name,
                    ffs.indication,
                    ffs.lot,
                    ffs.updated_at DESC
            ),

            latest_forecast_data AS (
                SELECT DISTINCT ON (
                    sf.display_scenario_name,
                    fs.indication,
                    fs.lot
                )
                    sf.display_scenario_name AS scenario_name,
                    fs.indication,
                    fs.lot,
                    fs.table_data AS nps_table
                FROM scenario_filters sf
                JOIN raw.forecast_scenarios fs
                  ON fs.ta_name = %s
                 AND fs.scenario_name = sf.scenario_name
                WHERE sf.priority = 3
                  AND LOWER(fs.metric) = 'nps'
                  AND fs.table_data IS NOT NULL
                ORDER BY
                    sf.display_scenario_name,
                    fs.indication,
                    fs.lot,
                    fs.updated_at DESC
            ),

            latest_lot_data AS (
                SELECT * FROM latest_event_data
                UNION ALL
                SELECT * FROM latest_finalized_data
                UNION ALL
                SELECT * FROM latest_forecast_data
            )

            SELECT
                (
                    SELECT jsonb_agg(
                        display_scenario_name
                        ORDER BY priority, display_scenario_name
                    )
                    FROM scenario_filters
                ) AS scenario_names,
                scenario_name,
                indication,
                lot,
                nps_table
            FROM latest_lot_data
            ORDER BY
                scenario_name,
                indication,
                lot
        """, (
            ta_name,
            ta_name,
            ta_name,
            ta_name,
            ta_name,
            ta_name
        ))

        rows = cursor.fetchall()

        data = {}
        scenario_names = []

        for (
            scenario_name_list,
            scenario_name,
            indication,
            lot,
            nps_table
        ) in rows:

            if scenario_name_list:
                scenario_names = scenario_name_list

            brands = _extract_brands_from_market_share_table(
                nps_table
            )

            data.setdefault(scenario_name, {})
            data[scenario_name].setdefault(indication, {})
            data[scenario_name][indication][lot] = brands

        return {
            "ta_name": ta_name,
            "scenario_names": scenario_names,
            "data": data
        }

    finally:
        cursor.close()
        conn.close()

def normalize_to_month_start(date_str: str) -> str:
    dt = datetime.strptime(str(date_str), "%Y-%m-%d")
    return dt.strftime("%Y-%m-01")


def clean_scenario_name(scenario_name: str) -> str:
    return (
        scenario_name
        .replace(" (Finalised)", "")
        .strip()
    )


def _to_dict(value):
    if value is None:
        return None

    if isinstance(value, str):
        return json.loads(value)

    return value


def _get_chart_values(chart):
    chart = _to_dict(chart)

    if not chart:
        return [], []

    months = chart.get("months", [])

    if "train_values" in chart or "forecast_values" in chart:
        values = (
            chart.get("train_values", [])
            + chart.get("forecast_values", [])
        )
        return months, values

    series = chart.get("series", [])

    if series:
        selected_series = None

        for item in series:
            if str(item.get("label", "")).lower() == "total":
                selected_series = item
                break

        if selected_series is None:
            selected_series = series[0]

        values = (
            selected_series.get("train_values", [])
            + selected_series.get("forecast_values", [])
        )

        return months, values

    return months, []


def _normalize_nps_table(nps_table):
    nps_table = _to_dict(nps_table)

    if isinstance(nps_table, list):
        if not nps_table:
            return None

        return nps_table[0]

    return nps_table


def fetch_scenario_data(
    cursor,
    ta_name: str,
    scenario_name: str,
    indication: str,
    lot: str,
    brand: str
):
    base_scenario_name = clean_scenario_name(scenario_name)

    # ---------------------------------------------------
    # Priority 1: market_event_scenarios
    # Directly use nps_table
    # ---------------------------------------------------
    cursor.execute("""
        SELECT
            market_share_chart,
            nps_table
        FROM raw.market_event_scenarios
        WHERE ta_name = %s
          AND scenario_name = %s
          AND indication = %s
          AND lot = %s
          AND nps_table IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 1
    """, (
        ta_name,
        base_scenario_name,
        indication,
        lot
    ))

    row = cursor.fetchone()

    if row:
        chart, nps_table = row

        return {
            "source": "market_events",
            "chart": _to_dict(chart),
            "nps_table": _normalize_nps_table(nps_table)
        }

    # ---------------------------------------------------
    # Priority 2: finalized scenario
    # Directly use table_data
    # ---------------------------------------------------
    cursor.execute("""
        SELECT
            chart,
            table_data
        FROM raw.forecast_finalized_selections
        WHERE ta_name = %s
          AND selected_scenario_name = %s
          AND indication = %s
          AND lot = %s
          AND LOWER(metric) = 'nps'
          AND table_data IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 1
    """, (
        ta_name,
        base_scenario_name,
        indication,
        lot
    ))

    row = cursor.fetchone()

    if row:
        chart, table_data = row

        return {
            "source": "finalized",
            "chart": _to_dict(chart),
            "nps_table": _normalize_nps_table(table_data)
        }

    # ---------------------------------------------------
    # Priority 3: forecast_scenarios
    # Calculate product NPS:
    # total NPS * product market share / 100
    # ---------------------------------------------------

    # 3A. Get total NPS
    cursor.execute("""
        SELECT
            chart
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
          AND scenario_name = %s
          AND indication = %s
          AND lot = %s
          AND LOWER(metric) = 'nps'
          AND chart IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 1
    """, (
        ta_name,
        base_scenario_name,
        indication,
        lot
    ))

    nps_row = cursor.fetchone()

    if not nps_row:
        return None

    nps_chart = _to_dict(nps_row[0])
    nps_months, total_nps_values = _get_chart_values(nps_chart)

    # 3B. Get selected brand market share
    cursor.execute("""
        SELECT
            chart
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
          AND scenario_name = %s
          AND indication = %s
          AND lot = %s
          AND LOWER(metric) = 'market_share'
          AND LOWER(product) = LOWER(%s)
          AND chart IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 1
    """, (
        ta_name,
        base_scenario_name,
        indication,
        lot,
        brand
    ))

    market_share_row = cursor.fetchone()

    if not market_share_row:
        raise ValueError(
            f"No market share data found for brand {brand}, scenario {scenario_name}, lot {lot}"
        )

    market_share_chart = _to_dict(market_share_row[0])
    ms_months, market_share_values = _get_chart_values(market_share_chart)

    if nps_months != ms_months:
        raise ValueError(
            f"Month mismatch between NPS and market share for scenario {scenario_name}, lot {lot}"
        )

    brand_nps_values = [
        round(
            float(total_nps) * float(ms_value) / 100
        )
        for total_nps, ms_value in zip(
            total_nps_values,
            market_share_values
        )
    ]

    calculated_nps_table = {
        "lot": lot,
        "total": total_nps_values,
        "children": [
            {
                "label": brand,
                "values": brand_nps_values
            }
        ],
        "scenario": base_scenario_name
    }

    return {
        "source": "forecast_scenarios",
        "chart": {
            "months": nps_months
        },
        "nps_table": calculated_nps_table
    }


def apply_persistency_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        scenario_name = payload.scenario_name
        base_scenario_name = clean_scenario_name(scenario_name)

        indication = payload.indication
        lots = payload.lots
        brand = payload.brand

        start_date = normalize_to_month_start(payload.start_date)
        end_date = normalize_to_month_start(payload.end_date)

        response_months = None
        response_table = []

        for lot in lots:

            scenario_data = fetch_scenario_data(
                cursor=cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                indication=indication,
                lot=lot,
                brand=brand
            )

            if not scenario_data:
                raise ValueError(
                    f"No data found for scenario {scenario_name}, indication {indication}, lot {lot}"
                )

            chart = scenario_data["chart"]
            nps_table = scenario_data["nps_table"]

            months = chart.get("months", [])

            if not months:
                raise ValueError(
                    f"No months available for scenario {scenario_name}, lot {lot}"
                )

            available_start_date = min(months)
            available_end_date = max(months)

            if start_date not in months:
                raise ValueError(
                    f"Invalid start_date: {start_date}. "
                    f"Available range is {available_start_date} to {available_end_date}"
                )

            if end_date not in months:
                raise ValueError(
                    f"Invalid end_date: {end_date}. "
                    f"Available range is {available_start_date} to {available_end_date}"
                )

            start_idx = months.index(start_date)
            end_idx = months.index(end_date)

            if start_idx > end_idx:
                raise ValueError(
                    f"start_date cannot be greater than end_date. "
                    f"start_date={start_date}, end_date={end_date}"
                )

            if start_idx == end_idx:
                raise ValueError(
                    "start_date and end_date cannot be the same. Please select a valid range."
                )

            filtered_months = months[start_idx:end_idx + 1]

            if response_months is None:
                response_months = filtered_months

            children = nps_table.get("children", [])

            brand_values = None

            for child in children:
                child_label = child.get("label")

                if (
                    str(child_label).strip().lower()
                    == str(brand).strip().lower()
                ):
                    brand_values = child.get("values", [])
                    break

            if brand_values is None:
                raise ValueError(
                    f"Brand {brand} not found in NPS table for scenario {scenario_name}, lot {lot}"
                )

            new_patients = [
                round(float(x))
                for x in brand_values[start_idx:end_idx + 1]
            ]

            cursor.execute("""
                SELECT
                    month,
                    persistency
                FROM raw.fact_persistency
                WHERE ta = %s
                  AND indication = %s
                  AND lot = %s
                ORDER BY month
            """, (
                ta_name,
                indication,
                lot
            ))

            persistency_rows = cursor.fetchall()

            if not persistency_rows:
                raise ValueError(
                    f"No persistency curve found for lot {lot}"
                )

            persistency_map = {}

            current_value = 100

            for month_num in range(1, 25):
                persistency_map[month_num] = current_value

                current_value = max(
                    0,
                    current_value - 5
                )

            continuing_patients = []

            for current_month_idx in range(len(new_patients)):

                continuing = 0.0

                for cohort_idx in range(current_month_idx):

                    persist_month = max(
                        1,
                        current_month_idx - cohort_idx
                    )

                    persist_percent = persistency_map.get(
                        persist_month,
                        0
                    )

                    cohort_new_patients = new_patients[cohort_idx]

                    continuing += (
                        cohort_new_patients
                        * persist_percent
                        / 100.0
                    )

                continuing_patients.append(
                    round(continuing)
                )

            total_patients = [
                round(new_val + cont_val)
                for new_val, cont_val in zip(
                    new_patients,
                    continuing_patients
                )
            ]

            cursor.execute("""
                INSERT INTO raw.persistency_outputs (
                    ta_name,
                    scenario_name,
                    indication,
                    brand,
                    lot,
                    curve_name,
                    months,
                    new_patients,
                    continuing_patients,
                    total_patients
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb
                )
                ON CONFLICT (
                    ta_name,
                    scenario_name,
                    indication,
                    brand,
                    lot
                )
                DO UPDATE SET
                    curve_name = EXCLUDED.curve_name,
                    months = EXCLUDED.months,
                    new_patients = EXCLUDED.new_patients,
                    continuing_patients = EXCLUDED.continuing_patients,
                    total_patients = EXCLUDED.total_patients,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                ta_name,
                base_scenario_name,
                indication,
                brand,
                lot,
                None,
                json.dumps(filtered_months),
                json.dumps(new_patients),
                json.dumps(continuing_patients),
                json.dumps(total_patients)
            ))
            
            response_table.append({
                "lot": lot,
                "source": scenario_data["source"],
                "children": [
                    {
                        "label": "New Patients",
                        "values": new_patients
                    },
                    {
                        "label": "Continuing Patients",
                        "values": continuing_patients
                    },
                    {
                        "label": "Total Patients",
                        "values": total_patients
                    }
                ]
            })

        conn.commit()
        
        ############ avg_vials_per_dose helper fucnction ###############
        avg_vials_table = build_avg_vials_per_dose_table(
        cursor=cursor,
        ta_name=ta_name,
        indication=indication,
        brand=brand,
        lots=lots,
        months=response_months or [],
        use_assumptions=False
        )


        ############ ex factory demand helper fucnction ###############    
        demand_vials_table = build_demand_vials_table(
        cursor=cursor,
        ta_name=ta_name,
        indication=indication,
        brand=brand,
        lots=lots,
        months=response_months or [],
        persistency_table=response_table,
        avg_vials_per_dose_table=avg_vials_table
        )

        ############ save avg vials + compliance into raw.vials_assumptions ###############

        for lot_data in avg_vials_table:

            lot = lot_data.get("lot")

            avg_vials_values = []

            # Get Avg Vials from avg_vials_table
            for child in lot_data.get("children", []):
                label = str(child.get("label", "")).strip().lower()

                if "avg" in label and "vial" in label:
                    avg_vials_values = child.get("values", [])
                    break

            # Get Compliance from demand_vials_table
            compliance_values = []
            absolute_adjustment_values = []
            adjustment_percent_values = []

            demand_lot_data = next(
                (
                    item for item in demand_vials_table
                    if item.get("lot") == lot
                ),
                None
            )

            if demand_lot_data:
                for child in demand_lot_data.get("children", []):
                    label = str(child.get("label", "")).strip().lower()

                    if "compliance" in label:
                        compliance_values = child.get("values", [])

                    elif "absolute adjustment" in label:
                        absolute_adjustment_values = child.get("values", [])

                    elif "adjustment %" in label:
                        adjustment_percent_values = child.get("values", [])

            for idx, month_str in enumerate(response_months or []):

                month_dt = datetime.strptime(month_str, "%Y-%m-%d")
                year = month_dt.year
                month = month_dt.month

                avg_vials_value = (
                    avg_vials_values[idx]
                    if idx < len(avg_vials_values)
                    and avg_vials_values[idx] is not None
                    else 0
                )

                compliance_value = (
                    compliance_values[idx]
                    if idx < len(compliance_values)
                    and compliance_values[idx] is not None
                    else 0
                )

                absolute_adjustment_value = (
                    absolute_adjustment_values[idx]
                    if idx < len(absolute_adjustment_values)
                    and absolute_adjustment_values[idx] is not None
                    else 0
                )

                adjustment_percent_value = (
                    adjustment_percent_values[idx]
                    if idx < len(adjustment_percent_values)
                    and adjustment_percent_values[idx] is not None
                    else 0
                )

                cursor.execute("""
                    INSERT INTO raw.vials_assumptions (
                        ta_name,
                        scenario_name,
                        indication,
                        brand,
                        lot,
                        year,
                        month,
                        avg_vials_per_dose,
                        compliance,
                        absolute_adjustment,
                        adjustment_percent
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (
                        ta_name,
                        scenario_name,
                        indication,
                        brand,
                        lot,
                        year,
                        month
                    )
                    DO UPDATE SET
                        avg_vials_per_dose = EXCLUDED.avg_vials_per_dose,
                        compliance = EXCLUDED.compliance,
                        absolute_adjustment = EXCLUDED.absolute_adjustment,
                        adjustment_percent = EXCLUDED.adjustment_percent,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    ta_name,
                    base_scenario_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,
                    avg_vials_value,
                    compliance_value,
                    absolute_adjustment_value,
                    adjustment_percent_value
                ))

        ############ inventory table ###############
        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )
        save_ex_factory_output(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=scenario_name,
            indication=indication,
            brand=brand,
            months=response_months or [],
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        
        conn.commit()

        return {
            "ta_name": ta_name,
            "indication": indication,
            "brand": brand,
            "months": response_months or [],
            "persistency_table": response_table,
            "avg_vials_per_dose_table": avg_vials_table,
            "demand_vials_table": demand_vials_table,
            "inventory_table": inventory_table
        }

    finally:
        cursor.close()
        conn.close()


def calculate_apply_persistency_service(
    payload: PersistencyCalculateApplyRequest
):

    ta_name = payload.ta_name
    curve_name = payload.curve_name

    start_month = payload.start_month
    end_month = payload.end_month

    start_value = payload.start_value
    end_value = payload.end_value

    method = payload.method.lower().replace("_", "-")
    k = payload.k_factor

    if start_month >= end_month:
        raise ValueError(
            "start_month should be less than end_month"
        )

    # ---------------------------------
    # K FACTOR RULE
    # ---------------------------------
    if method == "linear":
        k = 0
    else:
        if k is None or k == 0:
            k = 1.0

    total_points = end_month - start_month

    values = []

    for idx in range(total_points + 1):

        progress = idx / total_points

        if method == "linear":

            value = start_value + (
                end_value - start_value
            ) * progress

        elif method == "s-curve":

            sigmoid = 1 / (
                1 + math.exp(
                    -k * (progress - 0.5) * 10
                )
            )

            min_sigmoid = 1 / (
                1 + math.exp(5 * k)
            )

            max_sigmoid = 1 / (
                1 + math.exp(-5 * k)
            )

            normalized = (
                sigmoid - min_sigmoid
            ) / (
                max_sigmoid - min_sigmoid
            )

            value = start_value + (
                end_value - start_value
            ) * normalized

        elif method == "exponential":

            normalized = (
                math.exp(k * progress) - 1
            ) / (
                math.exp(k) - 1
            )

            value = start_value + (
                end_value - start_value
            ) * normalized

        elif method == "logarithmic":

            normalized = math.log(
                1 + k * progress
            ) / math.log(
                1 + k
            )

            value = start_value + (
                end_value - start_value
            ) * normalized

        else:
            raise ValueError(
                f"Unsupported method: {payload.method}"
            )

        values.append(round(value, 1))

    months = [
        f"M{month}"
        for month in range(start_month, end_month + 1)
    ]

    curve_preview = {
        "months": months,
        "values": values
    }

    curve_values = {
        "months": months,
        "values": values
    }

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO raw.persistency_curve_master (
                ta_name,
                curve_name,
                curve_type,
                start_month,
                end_month,
                start_value,
                end_value,
                k_factor,
                curve_values
            )
            VALUES (
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s::jsonb
            )
            ON CONFLICT (
                ta_name,
                curve_name
            )
            DO UPDATE SET
                curve_type = EXCLUDED.curve_type,
                start_month = EXCLUDED.start_month,
                end_month = EXCLUDED.end_month,
                start_value = EXCLUDED.start_value,
                end_value = EXCLUDED.end_value,
                k_factor = EXCLUDED.k_factor,
                curve_values = EXCLUDED.curve_values,
                updated_at = CURRENT_TIMESTAMP
        """, (
            ta_name,
            curve_name,
            method,
            start_month,
            end_month,
            start_value,
            end_value,
            k,
            json.dumps(curve_values)
        ))

        conn.commit()

        cursor.execute("""
            SELECT
                curve_name,
                curve_type
            FROM raw.persistency_curve_master
            WHERE ta_name = %s
            ORDER BY updated_at desc
        """, (ta_name,))

        rows = cursor.fetchall()

        curve_list = [
            {
                "curve_name": row[0],
                "method": row[1]
            }
            for row in rows
        ]

    finally:
        cursor.close()
        conn.close()

    return {
        "message": "Curve saved successfully",

        "curve_details": {
            "curve_name": curve_name,
            "ta_name": ta_name,
            "start_month": start_month,
            "end_month": end_month,
            "start_value": start_value,
            "end_value": end_value,
            "method": method,
            "k_factor": k
        },

        "curve_preview": curve_preview,

        "curve_list": curve_list
    }

def get_persistency_curve_names_service(
    ta_name: str
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                curve_name,
                curve_type
            FROM raw.persistency_curve_master
            WHERE ta_name = %s
            order by updated_at desc
        """, (ta_name,))

        rows = cursor.fetchall()

        curve_list = [
            {
                "curve_name": row[0],
                "method": row[1]
            }
            for row in rows
        ]

        return {
            "curve_list": curve_list
        }

    finally:
        cursor.close()
        conn.close()

def get_persistency_curve_config_service(
    curve_name: str
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                ta_name,
                start_month,
                end_month,
                start_value,
                end_value,
                curve_type,
                k_factor,
                curve_values
            FROM raw.persistency_curve_master
            WHERE curve_name = %s
            LIMIT 1
        """, (
            curve_name,
        ))

        row = cursor.fetchone()

        if not row:
            raise ValueError(
                f"Curve '{curve_name}' not found"
            )

        (
            ta_name,
            start_month,
            end_month,
            start_value,
            end_value,
            curve_type,
            k_factor,
            curve_values
        ) = row

        return {

            "curve_details": {

                "curve_name": curve_name,

                "ta_name": ta_name,

                "start_month": start_month,

                "end_month": end_month,

                "start_value": float(start_value),

                "end_value": float(end_value),

                "method": curve_type,

                "k_factor": float(k_factor)
            },

            "curve_preview": {

                "months": curve_values.get(
                    "months",
                    []
                ),

                "values": curve_values.get(
                    "values",
                    []
                )
            }
        }

    finally:
        cursor.close()
        conn.close()

def delete_persistency_curve_service(
    curve_name: str
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT 1
            FROM raw.persistency_curve_master
            WHERE curve_name = %s
        """, (
            curve_name,
        ))

        existing = cursor.fetchone()

        if not existing:
            raise ValueError(
                f"Curve '{curve_name}' not found"
            )

        cursor.execute("""
            DELETE FROM raw.persistency_curve_master
            WHERE curve_name = %s
        """, (
            curve_name,
        ))

        conn.commit()

        cursor.execute("""
            SELECT
                curve_name,
                curve_type
            FROM raw.persistency_curve_master
            ORDER BY updated_at
        """)

        rows = cursor.fetchall()

        curve_list = [
            {
                "curve_name": row[0],
                "method": row[1]
            }
            for row in rows
        ]

        return {
            "message": "Curve deleted successfully",
            "curve_list": curve_list
        }

    finally:
        cursor.close()
        conn.close()


def apply_persistency_curve_service(
    payload: PersistencyApplyCurveRequest
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        scenario_name = payload.scenario_name
        base_scenario_name = clean_scenario_name(
            scenario_name
        )

        indication = payload.indication
        brand = payload.brand

        start_date = normalize_to_month_start(
            payload.start_date
        )
        end_date = normalize_to_month_start(
            payload.end_date
        )

        response_months = None
        response_table = []

        for lot_curve in payload.lot_curve_mapping:

            lot = lot_curve.lot
            curve_name = lot_curve.curve_name

            scenario_data = fetch_scenario_data(
                cursor=cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                indication=indication,
                lot=lot,
                brand=brand
            )

            if not scenario_data:
                raise ValueError(
                    f"No data found for scenario {scenario_name}, indication {indication}, lot {lot}"
                )

            chart = scenario_data["chart"]
            nps_table = scenario_data["nps_table"]

            months = chart.get(
                "months",
                []
            )

            if not months:
                raise ValueError(
                    f"No months available for scenario {scenario_name}, lot {lot}"
                )

            available_start_date = min(months)
            available_end_date = max(months)

            if start_date not in months:
                raise ValueError(
                    f"Invalid start_date: {start_date}. "
                    f"Available range is {available_start_date} to {available_end_date}"
                )

            if end_date not in months:
                raise ValueError(
                    f"Invalid end_date: {end_date}. "
                    f"Available range is {available_start_date} to {available_end_date}"
                )

            start_idx = months.index(start_date)
            end_idx = months.index(end_date)

            if start_idx > end_idx:
                raise ValueError(
                    f"start_date cannot be greater than end_date. "
                    f"start_date={start_date}, end_date={end_date}"
                )

            if start_idx == end_idx:
                raise ValueError(
                    "start_date and end_date cannot be the same. Please select a valid range."
                )

            filtered_months = months[
                start_idx:end_idx + 1
            ]

            if response_months is None:
                response_months = filtered_months

            children = nps_table.get(
                "children",
                []
            )

            brand_values = None

            for child in children:

                child_label = child.get(
                    "label"
                )

                if (
                    str(child_label).strip().lower()
                    == str(brand).strip().lower()
                ):
                    brand_values = child.get(
                        "values",
                        []
                    )
                    break

            if brand_values is None:
                raise ValueError(
                    f"Brand {brand} not found in NPS table for scenario {scenario_name}, lot {lot}"
                )

            new_patients = [
                round(float(x))
                for x in brand_values[
                    start_idx:end_idx + 1
                ]
            ]

            cursor.execute("""
                SELECT
                    curve_values
                FROM raw.persistency_curve_master
                WHERE ta_name = %s
                  AND curve_name = %s
                LIMIT 1
            """, (
                ta_name,
                curve_name
            ))

            curve_row = cursor.fetchone()

            if not curve_row:
                raise ValueError(
                    f"Persistency curve '{curve_name}' not found"
                )

            curve_values = curve_row[0]

            persistency_values = curve_values.get(
                "values",
                []
            )

            if not persistency_values:
                raise ValueError(
                    f"No persistency values found for curve '{curve_name}'"
                )

            persistency_map = {
                idx + 1: float(value)
                for idx, value in enumerate(
                    persistency_values
                )
            }

            continuing_patients = []

            for current_month_idx in range(
                len(new_patients)
            ):

                continuing = 0.0

                for cohort_idx in range(
                    current_month_idx
                ):

                    persist_month = max(
                        1,
                        current_month_idx - cohort_idx
                    )

                    persist_percent = persistency_map.get(
                        persist_month,
                        0
                    )

                    cohort_new_patients = new_patients[
                        cohort_idx
                    ]

                    continuing += (
                        cohort_new_patients
                        * persist_percent
                        / 100.0
                    )

                continuing_patients.append(
                    round(continuing)
                )

            total_patients = [
                round(new_val + cont_val)
                for new_val, cont_val in zip(
                    new_patients,
                    continuing_patients
                )
            ]

            cursor.execute("""
                INSERT INTO raw.persistency_outputs (
                    ta_name,
                    scenario_name,
                    indication,
                    brand,
                    lot,
                    curve_name,
                    months,
                    new_patients,
                    continuing_patients,
                    total_patients
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb
                )
                ON CONFLICT (
                    ta_name,
                    scenario_name,
                    indication,
                    brand,
                    lot
                )
                DO UPDATE SET
                    curve_name = EXCLUDED.curve_name,
                    months = EXCLUDED.months,
                    new_patients = EXCLUDED.new_patients,
                    continuing_patients = EXCLUDED.continuing_patients,
                    total_patients = EXCLUDED.total_patients,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                ta_name,
                base_scenario_name,
                indication,
                brand,
                lot,
                curve_name,
                json.dumps(filtered_months),
                json.dumps(new_patients),
                json.dumps(continuing_patients),
                json.dumps(total_patients)
            ))

        conn.commit()

        response_lots = payload.lots

        cursor.execute("""
            SELECT
                lot,
                curve_name,
                months,
                new_patients,
                continuing_patients,
                total_patients
            FROM raw.persistency_outputs
            WHERE ta_name = %s
              AND scenario_name = %s
              AND indication = %s
              AND brand = %s
              AND lot = ANY(%s)
            ORDER BY lot
        """, (
            ta_name,
            base_scenario_name,
            indication,
            brand,
            response_lots
        ))

        output_rows = cursor.fetchall()

        response_table = []
        response_months = None

        for (
            lot,
            curve_name,
            months,
            new_patients,
            continuing_patients,
            total_patients
        ) in output_rows:

            if response_months is None:
                response_months = months

            month_count = len(response_months)

            months = months[:month_count]
            new_patients = new_patients[:month_count]
            continuing_patients = continuing_patients[:month_count]
            total_patients = total_patients[:month_count]

            response_table.append({
                "lot": lot,
                "curve_name": curve_name,
                "children": [
                    {
                        "label": "New Patients",
                        "values": new_patients
                    },
                    {
                        "label": "Continuing Patients",
                        "values": continuing_patients
                    },
                    {
                        "label": "Total Patients",
                        "values": total_patients
                    }
                ]
            })

        lots = [
            item["lot"]
            for item in response_table
        ]

        avg_vials_table = build_avg_vials_per_dose_table(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=base_scenario_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months or []
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months or [],
            persistency_table=response_table,
            avg_vials_per_dose_table=avg_vials_table
        )

        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        return {
            "ta_name": ta_name,
            "scenario_name": scenario_name,
            "indication": indication,
            "brand": brand,
            "months": response_months or [],
            "persistency_table": response_table,
            "avg_vials_per_dose_table": avg_vials_table,
            "demand_vials_table": demand_vials_table,
            "inventory_table": inventory_table
        }

    finally:
        cursor.close()
        conn.close()


def save_avg_vials_per_dose_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        indication = payload.indication
        brand = payload.brand
        months = payload.months
        scenario_name = payload.scenario_name
        base_scenario_name = clean_scenario_name(scenario_name)

        for lot_item in payload.avg_vials_per_dose_table:

            lot = lot_item.lot
            values = lot_item.values

            if len(values) != len(months):
                raise ValueError(
                    f"Values length mismatch for lot {lot}"
                )

            for month_str, avg_vial_value in zip(months, values):

                month_dt = datetime.strptime(month_str, "%Y-%m-%d")
                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    SELECT compliance
                    FROM raw.vials_assumptions
                    WHERE ta_name = %s
                      AND scenario_name = %s
                      AND indication = %s
                      AND lot = %s
                      AND brand = %s
                      AND year = %s
                      AND month = %s
                    LIMIT 1
                """, (
                    ta_name,
                    base_scenario_name,
                    indication,
                    lot,
                    brand,
                    year,
                    month
                ))

                compliance_row = cursor.fetchone()

                compliance_value = (
                    compliance_row[0]
                    if compliance_row
                    else 100
                )

                cursor.execute("""
                    INSERT INTO raw.vials_assumptions (
                        ta_name,
                        scenario_name,
                        indication,
                        lot,
                        brand,
                        year,
                        month,
                        avg_vials_per_dose,
                        compliance
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (
                        ta_name,
                        scenario_name,
                        indication,
                        brand,
                        lot,
                        year,
                        month
                    )
                    DO UPDATE SET
                        avg_vials_per_dose = EXCLUDED.avg_vials_per_dose
                """, (
                    ta_name,
                    base_scenario_name,
                    indication,
                    lot,
                    brand,
                    year,
                    month,
                    avg_vial_value,
                    compliance_value
                ))

        response_lots = [
            item.lot
            for item in payload.avg_vials_per_dose_table
        ]

        cursor.execute("""
            SELECT
                lot,
                curve_name,
                months,
                new_patients,
                continuing_patients,
                total_patients
            FROM raw.persistency_outputs
            WHERE ta_name = %s
              AND scenario_name = %s
              AND indication = %s
              AND brand = %s
              AND lot = ANY(%s)
            ORDER BY lot
        """, (
            ta_name,
            base_scenario_name,
            indication,
            brand,
            response_lots
        ))

        output_rows = cursor.fetchall()

        if not output_rows:
            raise ValueError(
                "No persistency output found. Please run apply first."
            )

        persistency_table = []
        response_months = months

        for (
            lot,
            curve_name,
            saved_months,
            new_patients,
            continuing_patients,
            total_patients
        ) in output_rows:

            persistency_table.append({
                "lot": lot,
                "curve_name": curve_name,
                "children": [
                    {
                        "label": "New Patients",
                        "values": new_patients
                    },
                    {
                        "label": "Continuing Patients",
                        "values": continuing_patients
                    },
                    {
                        "label": "Total Patients",
                        "values": total_patients
                    }
                ]
            })

        lots = [
            item["lot"]
            for item in persistency_table
        ]

        avg_vials_table = build_avg_vials_per_dose_table(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=base_scenario_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months,
            use_assumptions=True
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months,
            persistency_table=persistency_table,
            avg_vials_per_dose_table=avg_vials_table
        )

        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        save_ex_factory_output(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=base_scenario_name,
            indication=indication,
            brand=brand,
            months=response_months or [],
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": scenario_name,
            "indication": indication,
            "brand": brand,
            "months": response_months,
            "avg_vials_per_dose_table": avg_vials_table,
            "demand_vials_table": demand_vials_table,
            "inventory_table": inventory_table
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()