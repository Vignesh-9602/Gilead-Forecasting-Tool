import json
import math
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from app.db.connection import get_connection
from app.schemas.Vial_Calculator_schema import PersistencyApplyCurveRequest, PersistencyCalculateApplyRequest
from app.services.Retaining_Filters import get_saved_user_filter, save_user_filter
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





def sort_lot_key(lot):
    match = re.search(r"\d+", str(lot))
    return int(match.group()) if match else 999

def get_available_months_from_config(cur, ta_name: str):
    cur.execute("""
        SELECT config
        FROM raw.forecast_configurations
        WHERE LOWER(config->>'ta_name') = LOWER(%s)
    """, (ta_name,))

    row = cur.fetchone()

    if row:
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

    # fallback when config does not exist
    cur.execute("""
        SELECT DISTINCT
            jsonb_array_elements_text(chart->'months')::date AS month_date
        FROM raw.forecast_scenarios
        WHERE LOWER(ta_name) = LOWER(%s)
          AND chart IS NOT NULL
          AND chart ? 'months'
        ORDER BY month_date
    """, (ta_name,))

    return [
        r[0].strftime("%Y-%m-%d")
        for r in cur.fetchall()
    ]

def get_persistency_filters_service(ta_name: str):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT
                fs.indication,
                fs.lot,
                fs.product,
                fs.scenario_name,
                EXISTS (
                    SELECT 1
                    FROM raw.forecast_scenarios fs2
                    WHERE fs2.ta_name = fs.ta_name
                    AND LOWER(fs2.indication) = LOWER(fs.indication)
                    AND fs2.is_finalized = TRUE
                ) AS is_finalized
            FROM raw.forecast_scenarios fs
            WHERE fs.ta_name = %s
            AND LOWER(fs.metric) = 'market_share'
            AND fs.product IS NOT NULL
            AND fs.scenario_name IS NOT NULL
            ORDER BY
                fs.indication,
                fs.lot,
                fs.product,
                fs.scenario_name
        """, (ta_name,))

        rows = cursor.fetchall()

        data = {}
        scenario_names_set = set()

        for indication, lot, product, scenario_name, is_finalized in rows:

            # Always add the actual scenario name
            scenario_names_set.add(scenario_name)

            data.setdefault(scenario_name, {})
            data[scenario_name].setdefault(indication, {})
            data[scenario_name][indication].setdefault(lot, [])

            if product not in data[scenario_name][indication][lot]:
                data[scenario_name][indication][lot].append(product)

            # Add generic Finalised option once if any scenario is finalized
            if is_finalized:
                scenario_names_set.add("Finalised")

                data.setdefault("Finalised", {})
                data["Finalised"].setdefault(indication, {})
                data["Finalised"][indication].setdefault(lot, [])

                if product not in data["Finalised"][indication][lot]:
                    data["Finalised"][indication][lot].append(product)

        scenario_names = sorted(
            list(scenario_names_set),
            key=lambda x: (
                0 if x == "Finalised" else
                1 if x == "BASE" else
                2,
                x
            )
        )

        # -----------------------------------------------------
        # Default filter
        # -----------------------------------------------------

        default_scenario_name = ""
        default_indication = ""
        default_lots = []
        default_brand = ""
        default_start_date = ""
        default_end_date = ""

        if scenario_names:
            default_scenario_name = (
                "Finalised"
                if "Finalised" in scenario_names
                else "BASE"
                if "BASE" in scenario_names
                else scenario_names[0]
            )
        if default_scenario_name in data and data[default_scenario_name]:

            default_indication = sorted(
                data[default_scenario_name].keys()
            )[0]

            lots_map = data[default_scenario_name][default_indication]

            default_lots = sorted(
                lots_map.keys(),
                key=sort_lot_key
            )

            if default_lots:
                first_lot = default_lots[0]
                brands = lots_map.get(first_lot, [])

                default_brand = (
                    "Trodelvy"
                    if "Trodelvy" in brands
                    else brands[0] if brands else ""
                )

        # -----------------------------------------------------
        # Date range from forecast_scenarios chart months
        # latest month - 1 year
        # -----------------------------------------------------

        cursor.execute("""
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

        date_row = cursor.fetchone()

        if date_row and date_row[0]:
            default_end_date = date_row[0].strftime("%Y-%m-%d")
            default_start_date = date_row[1].strftime("%Y-%m-%d")

        user_id = "system"

        saved_filter = get_saved_user_filter(
            cursor,
            user_id,
            ta_name
        )

        default_filter = {
            "scenario_name": default_scenario_name,
            "indication": default_indication,
            "lots": default_lots,
            "brand": default_brand,
            "start_date": default_start_date,
            "end_date": default_end_date
        }

        if saved_filter:
            selected_scenario = saved_filter.get("scenario_name") or default_scenario_name

            if selected_scenario.lower().endswith("_finalised"):
                selected_scenario = "Finalised"

            if selected_scenario not in data:
                selected_scenario = default_scenario_name

            selected_indication = saved_filter.get("indication") or default_indication

            if selected_indication not in data.get(selected_scenario, {}):
                selected_indication = default_indication

            selected_lots_map = (
                data
                .get(selected_scenario, {})
                .get(selected_indication, {})
            )

            selected_lots = sorted(
                selected_lots_map.keys(),
                key=sort_lot_key
            )

            selected_filter = {
                "scenario_name": selected_scenario,
                "indication": selected_indication,
                "lots": selected_lots,
                "brand": saved_filter.get("product") or default_brand,
                "start_date": saved_filter.get("start_date") or default_start_date,
                "end_date": saved_filter.get("end_date") or default_end_date
            }
        else:
            selected_filter = default_filter
        available_months = get_available_months_from_config(
            cursor,
            ta_name
        )
        return {
            "ta_name": ta_name,
            "scenario_names": scenario_names,
            "data": data,
            "available_months": available_months,
            "selected_filter": selected_filter

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

    if base_scenario_name.lower().endswith("_finalised"):
        base_scenario_name = base_scenario_name[:-10]

    # ---------------------------------------------------
    # Single source: forecast_scenarios
    # Get selected brand market share + patient metrics
    # ---------------------------------------------------
    cursor.execute("""
        SELECT
            chart,
            table_data,
            patient_metrics,
            scenario_name
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
          AND LOWER(scenario_name) = LOWER(%s)
          AND LOWER(indication) = LOWER(%s)
          AND LOWER(lot) = LOWER(%s)
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

    row = cursor.fetchone()

    if not row:
        raise ValueError(
            f"No market share/patient metrics data found for brand {brand}, "
            f"scenario {scenario_name}, lot {lot}"
        )

    market_share_chart, table_data, patient_metrics, actual_scenario_name = row

    market_share_chart = _to_dict(market_share_chart)
    patient_metrics = _to_dict(patient_metrics)

    if not patient_metrics:
        raise ValueError(
            f"No patient_metrics found for brand {brand}, "
            f"scenario {scenario_name}, lot {lot}"
        )

    months = market_share_chart.get("months", [])

    brand_patient_values = patient_metrics.get(
        "final_patient_share",
        []
    )

    total_nps_values = patient_metrics.get(
        "final_nps",
        []
    )

    if not months:
        raise ValueError(
            f"No months found for brand {brand}, "
            f"scenario {scenario_name}, lot {lot}"
        )

    if len(months) != len(brand_patient_values):
        raise ValueError(
            f"Month and patient_metrics length mismatch for brand {brand}, "
            f"scenario {scenario_name}, lot {lot}"
        )

    calculated_nps_table = {
        "lot": lot,
        "total": total_nps_values,
        "children": [
            {
                "label": brand,
                "values": [
                    round(float(v or 0))
                    for v in brand_patient_values
                ]
            }
        ],
        "scenario": actual_scenario_name
    }

    return {
        "source": "forecast_scenarios",
        "chart": {
            "months": months
        },
        "nps_table": calculated_nps_table,
        "actual_scenario_name": actual_scenario_name
    }


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
    
def get_actual_scenario_for_finalised_lot(
    cursor,
    ta_name: str,
    indication: str,
    lot: str,
    brand: str = None
):
    cursor.execute("""
        SELECT scenario_name
        FROM raw.forecast_scenarios
        WHERE LOWER(ta_name) = LOWER(%s)
          AND LOWER(indication) = LOWER(%s)
          AND LOWER(lot) = LOWER(%s)
          AND is_finalized = TRUE
          AND scenario_name IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 1
    """, (
        ta_name,
        indication,
        lot
    ))

    row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No finalised scenario found for lot {lot}."
        )

    return row[0]

def apply_persistency_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        validate_date_range(
            payload.start_date,
            payload.end_date
        )
        ta_name = payload.ta_name
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)
        is_finalised_view = db_scenario_name.strip().upper() == "FINALISED"
        indication = payload.indication
        lots = payload.lots
        brand = payload.brand

        start_date = normalize_to_month_start(payload.start_date)
        end_date = normalize_to_month_start(payload.end_date)

        response_months = None
        response_table = []
        lot_actual_scenario_map = {}

        for lot in lots:
            actual_scenario_name = (
            get_actual_scenario_for_finalised_lot(
                cursor=cursor,
                ta_name=ta_name,
                indication=indication,
                lot=lot,
                brand=brand
            )
            if is_finalised_view
            else db_scenario_name
            )
            scenario_data = fetch_scenario_data(
                cursor=cursor,
                ta_name=ta_name,
                scenario_name=actual_scenario_name,
                indication=indication,
                lot=lot,
                brand=brand
            )

           
            if not scenario_data:
                raise ValueError(
                    f"No data found for scenario {display_scenario_name}, indication {indication}, lot {lot}"
                )
            actual_scenario_name = scenario_data["actual_scenario_name"]
            lot_actual_scenario_map[lot] = actual_scenario_name
            chart = scenario_data["chart"]
            nps_table = scenario_data["nps_table"]

            months = chart.get("months", [])

            if not months:
                raise ValueError(
                    f"No months available for scenario {display_scenario_name}, lot {lot}"
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
                    f"Brand {brand} not found in NPS table for scenario {display_scenario_name}, lot {lot}"
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
                actual_scenario_name,
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

        
        ############ avg_vials_per_dose helper fucnction ###############
        avg_vials_table = build_avg_vials_per_dose_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months or [],
            use_assumptions=True,
            scenario_name=db_scenario_name,
            lot_actual_scenario_map=lot_actual_scenario_map
        )


        ############ ex factory demand helper fucnction ###############    
        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months,
            persistency_table=response_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True,
            scenario_name=db_scenario_name,
            lot_actual_scenario_map=lot_actual_scenario_map
        )
        

        ############ save avg vials + compliance into raw.vials_assumptions ###############

        def get_child_values(table_item, expected_label):
            expected_label = expected_label.strip().lower()

            for child in table_item.get("children", []):
                label = str(child.get("label", "")).strip().lower()

                if expected_label in label:
                    return child.get("values", [])

            return []


        # ================================
        # SAVE AVG VIALS + DEMAND VALUES
        # ================================
        for lot_data in avg_vials_table:

            lot = lot_data.get("lot")
            actual_scenario_name = lot_actual_scenario_map.get(
                lot,
                db_scenario_name
            )
            avg_vials_values = get_child_values(
                lot_data,
                "Avg Vials"
            )

            demand_lot_data = next(
                (
                    item for item in demand_vials_table
                    if item.get("lot") == lot
                ),
                None
            )

            compliance_values = []
            absolute_adjustment_values = []
            adjustment_percent_values = []
            after_adjustment_values = []

            if demand_lot_data:
                compliance_values = get_child_values(
                    demand_lot_data,
                    "Compliance %"
                )

                absolute_adjustment_values = get_child_values(
                    demand_lot_data,
                    "(+) Absolute Adjustment"
                )

                adjustment_percent_values = get_child_values(
                    demand_lot_data,
                    "(x) Adjustment %"
                )

                after_adjustment_values = get_child_values(
                    demand_lot_data,
                    "After Adjustment"
                )

            for idx, month_str in enumerate(response_months or []):

                month_dt = datetime.strptime(month_str, "%Y-%m-%d")
                year = month_dt.year
                month = month_dt.month

                avg_vials_value = (
                    avg_vials_values[idx]
                    if idx < len(avg_vials_values)
                    else 0
                )

                compliance_value = (
                    compliance_values[idx]
                    if idx < len(compliance_values)
                    else 0
                )

                absolute_adjustment_value = (
                    absolute_adjustment_values[idx]
                    if idx < len(absolute_adjustment_values)
                    else 0
                )

                adjustment_percent_value = (
                    adjustment_percent_values[idx]
                    if idx < len(adjustment_percent_values)
                    else 0
                )

                after_adjustment_value = (
                    after_adjustment_values[idx]
                    if idx < len(after_adjustment_values)
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
                        adjustment_percent,
                        after_adjustment
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s, %s
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
                        after_adjustment = EXCLUDED.after_adjustment,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    ta_name,
                    actual_scenario_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,
                    avg_vials_value,
                    compliance_value,
                    absolute_adjustment_value,
                    adjustment_percent_value,
                    after_adjustment_value
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
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            months=response_months or [],
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )
        
        save_user_filter(
            cur=cursor,
            user_id="system",
            ta_name=ta_name,
            scenario_name=display_scenario_name,
            indication=indication,
            lot=lots[0] if lots else "",
            metric="nps",
            product=brand,
            start_date=start_date,
            end_date=end_date
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

def get_persistency_curve_names_service(ta_name: str):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                curve_name
            FROM raw.persistency_curve_master
            WHERE ta_name = %s
            ORDER BY updated_at DESC
        """, (ta_name,))

        rows = cursor.fetchall()

        curve_list = [
            {"curve_name": row[0]}
            for row in rows
        ]

        return {
            "curve_list": curve_list
        }

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_persistency_curve_config_service(curve_name: str):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                ta_name,
                curve_values
            FROM raw.persistency_curve_master
            WHERE curve_name = %s
            LIMIT 1
        """, (curve_name,))

        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Curve '{curve_name}' not found")

        ta_name, curve_values = row

        months = curve_values.get("months", [])
        values = curve_values.get("values", [])

        return {
            "curve_details": {
                "curve_name": curve_name,
                "ta_name": ta_name,
                "start_month": months[0] if months else None,
                "end_month": months[-1] if months else None,
                "start_value": float(values[0]) if values else None,
                "end_value": float(values[-1]) if values else None
                # "method": None,      # not currently stored - see note below
                # "k_factor": None,    # not currently stored - see note below
            },
            "curve_preview": {
                "curve_name": curve_name,
                "months": months,
                "values": values,
            }
        }

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def delete_persistency_curve_service(curve_name: str):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ta_name
            FROM raw.persistency_curve_master
            WHERE curve_name = %s
        """, (curve_name,))

        existing = cursor.fetchone()

        if not existing:
            raise ValueError(f"Curve '{curve_name}' not found")

        ta_name = existing[0]

        cursor.execute("""
            DELETE FROM raw.persistency_curve_master
            WHERE curve_name = %s
        """, (curve_name,))

        conn.commit()

        cursor.execute("""
            SELECT curve_name
            FROM raw.persistency_curve_master
            WHERE ta_name = %s
            ORDER BY updated_at DESC
        """, (ta_name,))

        rows = cursor.fetchall()

        curve_list = [
            {"curve_name": row[0]}
            for row in rows
        ]

        return {
            "message": "Curve deleted successfully",
            "curve_list": curve_list
        }

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def fetch_curve_values_map(cursor, ta_name, curve_names):
    cursor.execute("""
        SELECT
            curve_name,
            curve_values
        FROM raw.persistency_curve_master
        WHERE ta_name = %s
          AND curve_name = ANY(%s)
    """, (
        ta_name,
        curve_names
    ))

    rows = cursor.fetchall()

    curve_values_map = {}

    for curve_name, curve_values in rows:
        values = curve_values.get("values", [])

        if not values:
            raise ValueError(
                f"No persistency values found for curve '{curve_name}'"
            )

        curve_values_map[curve_name] = {
            idx + 1: float(value)
            for idx, value in enumerate(values)
        }

    missing_curves = set(curve_names) - set(curve_values_map.keys())

    if missing_curves:
        raise ValueError(
            f"Persistency curve(s) not found: {', '.join(missing_curves)}"
        )

    return curve_values_map


def build_month_curve_map(filtered_months, lot_curve):
    """
    Builds month-wise curve assignment for one LOT.

    Example:
    Jan-25 to Oct-25 -> Linear Curve
    Nov-25 to Jun-26 -> S Curve

    If same month gets two curves, API fails.
    If any selected month has no curve, API fails.
    """

    month_curve_map = {}

    if not lot_curve.curves:
        raise ValueError(
            f"No curves provided for lot {lot_curve.lot}"
        )

    for curve_config in lot_curve.curves:
        curve_name = curve_config.curve_name

        curve_start_date = normalize_to_month_start(
            curve_config.start_date
        )
        curve_end_date = normalize_to_month_start(
            curve_config.end_date
        )

        if curve_start_date > curve_end_date:
            raise ValueError(
                f"Invalid curve period for lot {lot_curve.lot}, curve {curve_name}. "
                f"start_date cannot be greater than end_date."
            )

        for month in filtered_months:
            if curve_start_date <= month <= curve_end_date:

                if month in month_curve_map:
                    raise ValueError(
                        f"Overlapping curve dates found for lot {lot_curve.lot}. "
                        f"Month {month} is assigned to both "
                        f"'{month_curve_map[month]}' and '{curve_name}'."
                    )

                month_curve_map[month] = curve_name

    missing_months = [
        month
        for month in filtered_months
        if month not in month_curve_map
    ]

    if missing_months:
        raise ValueError(
            f"Curve not assigned for lot {lot_curve.lot} for months: "
            + ", ".join(missing_months)
        )

    return month_curve_map


def calculate_persistency_with_curve_periods(
    new_patients,
    filtered_months,
    month_curve_map,
    curve_values_map
):
    """
    Excel logic:
    - Cohort gets curve based on cohort entry month.
    - Cohort continues with same curve M1-M24.
    """

    continuing_patients = []

    for current_month_idx in range(len(new_patients)):

        continuing = 0.0

        for cohort_idx in range(current_month_idx):

            cohort_month = filtered_months[cohort_idx]
            cohort_curve_name = month_curve_map[cohort_month]

            persistency_map = curve_values_map[cohort_curve_name]

            persist_month = current_month_idx - cohort_idx

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

    return continuing_patients, total_patients

def apply_persistency_curve_service(
    payload: PersistencyApplyCurveRequest
):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name

        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)
        is_finalised_view = db_scenario_name.strip().upper() == "FINALISED"

        indication = payload.indication
        brand = payload.brand

        start_date = normalize_to_month_start(
            payload.start_date
        )
        end_date = normalize_to_month_start(
            payload.end_date
        )

        response_months = None
        lot_actual_scenario_map = {}
        all_lots = payload.lots or []

        # -------------------------------------------------
        # Finalised scenario mapping per LOT
        # -------------------------------------------------
        for lot in all_lots:
            actual_scenario_name = (
                get_actual_scenario_for_finalised_lot(
                    cursor=cursor,
                    ta_name=ta_name,
                    indication=indication,
                    lot=lot,
                    brand=brand
                )
                if is_finalised_view
                else db_scenario_name
            )

            lot_actual_scenario_map[lot] = actual_scenario_name

        # -------------------------------------------------
        # Apply persistency curve per LOT
        # -------------------------------------------------
        for lot_curve in payload.lot_curve_mapping:

            lot = lot_curve.lot

            actual_scenario_name = lot_actual_scenario_map.get(
                lot,
                db_scenario_name
            )

            scenario_data = fetch_scenario_data(
                cursor=cursor,
                ta_name=ta_name,
                scenario_name=actual_scenario_name,
                indication=indication,
                lot=lot,
                brand=brand
            )

            if not scenario_data:
                raise ValueError(
                    f"No data found for scenario {display_scenario_name}, indication {indication}, lot {lot}"
                )

            chart = scenario_data["chart"]
            nps_table = scenario_data["nps_table"]

            months = chart.get(
                "months",
                []
            )

            if not months:
                raise ValueError(
                    f"No months available for scenario {display_scenario_name}, lot {lot}"
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
                    f"Brand {brand} not found in NPS table for scenario {display_scenario_name}, lot {lot}"
                )

            new_patients = [
                round(float(x))
                for x in brand_values[
                    start_idx:end_idx + 1
                ]
            ]

            # -------------------------------------------------
            # Build month-wise curve map
            # Example:
            # Jan-25 -> Linear Curve
            # Feb-25 -> Linear Curve
            # Nov-25 -> S Curve
            # -------------------------------------------------
            month_curve_map = build_month_curve_map(
                filtered_months=filtered_months,
                lot_curve=lot_curve
            )

            curve_names = list(
                set(month_curve_map.values())
            )

            curve_values_map = fetch_curve_values_map(
                cursor=cursor,
                ta_name=ta_name,
                curve_names=curve_names
            )

            continuing_patients, total_patients = calculate_persistency_with_curve_periods(
                new_patients=new_patients,
                filtered_months=filtered_months,
                month_curve_map=month_curve_map,
                curve_values_map=curve_values_map
            )

            curve_name_for_output = ", ".join(
                sorted(curve_names)
            )

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
                actual_scenario_name,
                indication,
                brand,
                lot,
                curve_name_for_output,
                json.dumps(filtered_months),
                json.dumps(new_patients),
                json.dumps(continuing_patients),
                json.dumps(total_patients)
            ))

        # -------------------------------------------------
        # Build response
        # -------------------------------------------------
        response_lots = payload.lots

        output_rows = []

        for lot in response_lots:
            actual_scenario_name = lot_actual_scenario_map.get(
                lot,
                db_scenario_name
            )

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
                  AND lot = %s
                LIMIT 1
            """, (
                ta_name,
                actual_scenario_name,
                indication,
                brand,
                lot
            ))

            row = cursor.fetchone()

            if row:
                output_rows.append(row)
        lot_curve_payload_map = {
            item.lot: [
                {
                    "curve_name": curve.curve_name,
                    "start_date": normalize_to_month_start(curve.start_date),
                    "end_date": normalize_to_month_start(curve.end_date)
                }
                for curve in item.curves
            ]
            for item in payload.lot_curve_mapping
        }
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
                "curve_mapping": lot_curve_payload_map.get(lot, []),
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
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months or [],
            use_assumptions=True,
            scenario_name=db_scenario_name,
            lot_actual_scenario_map=lot_actual_scenario_map
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months,
            persistency_table=response_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True,
            scenario_name=db_scenario_name,
            lot_actual_scenario_map=lot_actual_scenario_map
        )

        save_ex_factory_output(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=display_scenario_name,
            indication=indication,
            brand=brand,
            months=response_months or [],
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
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


def save_demand_vials_values(
    cursor,
    ta_name,
    scenario_name,
    indication,
    brand,
    months,
    demand_vials_table
):
    for lot_data in demand_vials_table:

        lot = lot_data.get("lot")

        if lot == "Total":
            continue

        children = lot_data.get("children", [])

        def get_values(label_name):
            for child in children:
                label = str(child.get("label", "")).strip().lower()

                if label == label_name.strip().lower():
                    return child.get("values", [])

            return []

        compliance_values = get_values("Compliance %")
        absolute_adjustment_values = get_values("(+) Absolute Adjustment")
        adjustment_percent_values = get_values("(x) Adjustment %")
        after_adjustment_values = get_values("After Adjustment")

        for idx, month_str in enumerate(months):

            month_dt = datetime.strptime(month_str, "%Y-%m-%d")
            year = month_dt.year
            month = month_dt.month

            compliance_value = (
                compliance_values[idx]
                if idx < len(compliance_values)
                else 100
            )

            absolute_adjustment_value = (
                absolute_adjustment_values[idx]
                if idx < len(absolute_adjustment_values)
                else 0
            )

            adjustment_percent_value = (
                adjustment_percent_values[idx]
                if idx < len(adjustment_percent_values)
                else 0
            )

            after_adjustment_value = (
                after_adjustment_values[idx]
                if idx < len(after_adjustment_values)
                else 0
            )

            cursor.execute("""
                UPDATE raw.vials_assumptions
                SET
                    compliance = %s,
                    absolute_adjustment = %s,
                    adjustment_percent = %s,
                    after_adjustment = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s
                  AND scenario_name = %s
                  AND indication = %s
                  AND brand = %s
                  AND lot = %s
                  AND year = %s
                  AND month = %s
            """, (
                compliance_value,
                absolute_adjustment_value,
                adjustment_percent_value,
                after_adjustment_value,
                ta_name,
                scenario_name,
                indication,
                brand,
                lot,
                year,
                month
            ))
def save_avg_vials_per_dose_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        indication = payload.indication
        brand = payload.brand
        months = payload.months
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)
        is_finalised_view = db_scenario_name.strip().upper() == "FINALISED"
        lot_actual_scenario_map = {}

        for lot_item in payload.avg_vials_per_dose_table:

            lot = lot_item.lot
            values = lot_item.values
            actual_scenario_name = (
            get_actual_scenario_for_finalised_lot(
                cursor=cursor,
                ta_name=ta_name,
                indication=indication,
                lot=lot,
                brand=brand
            )
            if is_finalised_view
            else db_scenario_name
        )

            lot_actual_scenario_map[lot] = actual_scenario_name

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
                    FROM raw.vials_assumptions va
                    WHERE va.ta_name = %s
                    AND va.scenario_name = %s
                    AND va.indication = %s
                    AND va.lot = %s
                    AND va.brand = %s
                    AND va.year = %s
                    AND va.month = %s
                    LIMIT 1
                """, (
                    ta_name,
                    actual_scenario_name,
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
                    actual_scenario_name,
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

        output_rows = []

        for lot in response_lots:
            actual_scenario_name = lot_actual_scenario_map.get(
                lot,
                db_scenario_name
            )

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
                AND lot = %s
                LIMIT 1
            """, (
                ta_name,
                actual_scenario_name,
                indication,
                brand,
                lot
            ))

            row = cursor.fetchone()

            if row:
                output_rows.append(row)

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
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months,
            use_assumptions=True,
            lot_actual_scenario_map=lot_actual_scenario_map
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=response_months,
            persistency_table=persistency_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True,
            scenario_name=db_scenario_name,
            lot_actual_scenario_map=lot_actual_scenario_map
        )
        save_demand_vials_values(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            months=response_months,
            demand_vials_table=demand_vials_table
        )
        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        save_ex_factory_output(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            months=response_months or [],
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
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