import json
import math
from datetime import datetime
from app.db.connection import get_connection
from app.schemas.Vial_Calculator_schema import PersistencyApplyCurveRequest, PersistencyCalculateApplyRequest
from app.services.Vial_Calculator_functions import build_avg_vials_per_dose_table, build_demand_vials_table, build_inventory_table

def _extract_brands_from_market_share_table(
    market_share_table
):
    if not market_share_table:
        return []

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


def get_persistency_filters_service(
    ta_name: str
):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT DISTINCT ON (
                indication,
                lot
            )
                indication,
                lot,
                market_share_table
            FROM raw.market_event_scenarios
            WHERE ta_name = %s
            ORDER BY
                indication,
                lot,
                updated_at DESC
        """, (ta_name,))

        rows = cursor.fetchall()

        data = {}

        for (
            indication,
            lot,
            market_share_table
        ) in rows:

            brands = (
                _extract_brands_from_market_share_table(
                    market_share_table
                )
            )

            data.setdefault(
                indication,
                {}
            )

            data[indication][lot] = brands

        return {
            "ta_name": ta_name,
            "data": data
        }

    finally:
        cursor.close()
        conn.close()


def normalize_to_month_start(date_str: str) -> str:
    dt = datetime.strptime(str(date_str), "%Y-%m-%d")
    return dt.strftime("%Y-%m-01")


def apply_persistency_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        indication = payload.indication
        lots = payload.lots
        brand = payload.brand

        start_date = normalize_to_month_start(payload.start_date)
        end_date = normalize_to_month_start(payload.end_date)

        response_months = None
        response_table = []

        for lot in lots:

            cursor.execute("""
                SELECT
                    market_share_chart,
                    nps_table
                FROM raw.market_event_scenarios
                WHERE ta_name = %s
                  AND indication = %s
                  AND lot = %s
                ORDER BY updated_at DESC
                LIMIT 1
            """, (
                ta_name,
                indication,
                lot
            ))

            row = cursor.fetchone()

            if not row:
                raise ValueError(
                    f"No market event data found for lot {lot}"
                )

            market_share_chart, nps_table = row

            months = market_share_chart.get("months", [])

            if not months:
                raise ValueError(
                    f"No months available for lot {lot}"
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
                    f"Brand {brand} not found in NPS table for lot {lot}"
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

            persistency_map = {
                int(month): float(persistency)
                for month, persistency in persistency_rows
            }

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

            # ---------------------------------------------------
            # Save / Update Persistency Output for Vial Calculation
            # ---------------------------------------------------
            cursor.execute("""
                INSERT INTO raw.persistency_outputs (
                    ta_name,
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
                    %s, %s, %s, %s,
                    %s,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb
                )
                ON CONFLICT (
                    ta_name,
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
        ############ inventory table ###############
        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

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

            # ---------------------------------------------------
            # Fetch latest market event data for LOT
            # ---------------------------------------------------
            cursor.execute("""
                SELECT
                    market_share_chart,
                    nps_table
                FROM raw.market_event_scenarios
                WHERE ta_name = %s
                  AND indication = %s
                  AND lot = %s
                ORDER BY updated_at DESC
                LIMIT 1
            """, (
                ta_name,
                indication,
                lot
            ))

            row = cursor.fetchone()

            if not row:
                raise ValueError(
                    f"No market event data found for lot {lot}"
                )

            market_share_chart, nps_table = row

            months = market_share_chart.get(
                "months",
                []
            )

            if not months:
                raise ValueError(
                    f"No months available for lot {lot}"
                )

            available_start_date = min(months)
            available_end_date = max(months)

            # ---------------------------------------------------
            # Validate dates
            # ---------------------------------------------------
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

            # ---------------------------------------------------
            # Extract NPS / New Patients for selected brand
            # ---------------------------------------------------
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
                    f"Brand {brand} not found in NPS table for lot {lot}"
                )

            new_patients = [
                round(float(x))
                for x in brand_values[
                    start_idx:end_idx + 1
                ]
            ]

            # ---------------------------------------------------
            # Fetch saved persistency curve from DB
            # ---------------------------------------------------
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

            # ---------------------------------------------------
            # Continuing Patients
            # Same existing logic
            # ---------------------------------------------------
            continuing_patients = []

            for current_month_idx in range(
                len(new_patients)
            ):

                continuing = 0.0

                # previous cohorts only
                for cohort_idx in range(
                    current_month_idx
                ):

                    # previous month uses persistency month 1
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

            # ---------------------------------------------------
            # Total Patients
            # Same existing logic
            # ---------------------------------------------------
            total_patients = [
                round(new_val + cont_val)
                for new_val, cont_val in zip(
                    new_patients,
                    continuing_patients
                )
            ]

            # ---------------------------------------------------
            # Save / Update Persistency Output for Vial Calculation
            # ---------------------------------------------------
            cursor.execute("""
                INSERT INTO raw.persistency_outputs (
                    ta_name,
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
                    %s, %s, %s, %s,
                    %s,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb,
                    %s::jsonb
                )
                ON CONFLICT (
                    ta_name,
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
                indication,
                brand,
                lot,
                curve_name,
                json.dumps(filtered_months),
                json.dumps(new_patients),
                json.dumps(continuing_patients),
                json.dumps(total_patients)
            ))

            # ---------------------------------------------------
            # LOT table
            # ---------------------------------------------------
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

        conn.commit()

        # ---------------------------------------------------
        # Fetch all LOT outputs from persistency_outputs
        # ---------------------------------------------------
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
              AND indication = %s
              AND brand = %s
            ORDER BY lot
        """, (
            ta_name,
            indication,
            brand
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