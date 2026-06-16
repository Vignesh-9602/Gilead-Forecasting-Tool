from fastapi import HTTPException
from app.db.connection import get_connection
from datetime import datetime

# ---------------------------------------------------
# Avg_Vials per dose
# ---------------------------------------------------
def build_avg_vials_per_dose_table(
    cursor,
    ta_name: str,
    indication: str,
    brand: str,
    lots: list,
    months: list,
    use_assumptions: bool = False,
    scenario_name: str = None,
    lot_actual_scenario_map: dict = None
):
    avg_vials_table = []

    for lot in lots:
        actual_scenario_name = (
            lot_actual_scenario_map.get(lot, scenario_name)
            if lot_actual_scenario_map
            else scenario_name
        )
        if use_assumptions:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    avg_vials_per_dose
                FROM raw.vials_assumptions
                WHERE ta_name = %s
                  AND scenario_name = %s
                  AND indication = %s
                  AND brand = %s
                  AND lot = %s
                ORDER BY year, month
            """, (
                ta_name,
                actual_scenario_name,
                indication,
                brand,
                lot
            ))
        else:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    avg_vials_per_dose
                FROM raw.fact_vials_compliance
                WHERE ta = %s
                  AND indication = %s
                  AND brand = %s
                  AND lot = %s
                ORDER BY year, month
            """, (
                ta_name,
                indication,
                brand,
                lot
            ))

        rows = cursor.fetchall()

        if not rows:
            raise ValueError(
                f"No Avg Vials Per Dose data found for lot {lot}, brand {brand}"
            )

        avg_vials_map = {}
        latest_value = None

        for year, month, avg_vials in rows:
            month_key = f"{int(year)}-{int(month):02d}-01"

            value = float(avg_vials)
            if value.is_integer():
                value = int(value)

            avg_vials_map[month_key] = value
            latest_value = value

        values = [
            avg_vials_map.get(month, latest_value)
            for month in months
        ]

        avg_vials_table.append({
            "lot": lot,
            "children": [
                {
                    "label": f"{brand} - {lot} Avg Vials",
                    "values": values
                }
            ]
        })

    return avg_vials_table

def validate_compliance_value(compliance):
    try:
        compliance = float(compliance)
    except (TypeError, ValueError):
        raise ValueError(
            "Compliance must be a valid number"
        )

    if compliance < 0 or compliance > 100:
        raise ValueError(
            "Compliance must be between 0 and 100"
        )

    return compliance

def build_demand_vials_table(
    cursor,
    ta_name: str,
    indication: str,
    brand: str,
    lots: list,
    months: list,
    persistency_table: list,
    avg_vials_per_dose_table: list,
    use_assumptions: bool = False,
    scenario_name: str = None,
    lot_actual_scenario_map: dict = None
):
    demand_vials_table = []
    ex_factory_total = [0] * len(months)

    for lot in lots:
        actual_scenario_name = (
            lot_actual_scenario_map.get(lot, scenario_name)
            if lot_actual_scenario_map
            else scenario_name
        )
        lot_persistency = next(
            (item for item in persistency_table if item["lot"] == lot),
            None
        )

        if not lot_persistency:
            raise ValueError(f"Persistency data not found for lot {lot}")

        total_patients = next(
            (
                child["values"]
                for child in lot_persistency["children"]
                if child["label"] == "Total Patients"
            ),
            None
        )

        if total_patients is None:
            raise ValueError(f"Total Patients not found for lot {lot}")

        lot_avg_vials = next(
            (item for item in avg_vials_per_dose_table if item["lot"] == lot),
            None
        )

        if not lot_avg_vials:
            raise ValueError(f"Avg Vials data not found for lot {lot}")

        avg_vials = lot_avg_vials["children"][0]["values"]

        if use_assumptions:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    compliance,
                    absolute_adjustment,
                    adjustment_percent
                FROM raw.vials_assumptions
                WHERE ta_name = %s
                  AND indication = %s
                  AND scenario_name = %s
                  AND brand = %s
                  AND lot = %s
                ORDER BY year, month
            """, (
                ta_name,
                indication,
                actual_scenario_name,
                brand,
                lot
            ))
        else:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    compliance,
                    0 AS absolute_adjustment,
                    0 AS adjustment_percent
                FROM raw.fact_vials_compliance
                WHERE ta = %s
                  AND indication = %s
                  AND lot = %s
                  AND brand = %s
                ORDER BY year, month
            """, (
                ta_name,
                indication,
                lot,
                brand
            ))

        rows = cursor.fetchall()

        if not rows:
            raise ValueError(
                f"No compliance data found for lot {lot}, brand {brand}"
            )

        compliance_map = {}
        absolute_adjustment_map = {}
        adjustment_percent_map = {}

        latest_compliance = None

        for year, month, compliance, absolute_adjustment, adjustment_percent in rows:
            month_key = f"{int(year)}-{int(month):02d}-01"

            compliance_value = float(
                    compliance if compliance is not None else 100
                )
            absolute_value = float(absolute_adjustment)
            percent_value = float(adjustment_percent)

            if compliance_value.is_integer():
                compliance_value = int(compliance_value)

            if absolute_value.is_integer():
                absolute_value = int(absolute_value)

            if percent_value.is_integer():
                percent_value = int(percent_value)

            compliance_map[month_key] = compliance_value
            absolute_adjustment_map[month_key] = absolute_value
            adjustment_percent_map[month_key] = percent_value

            latest_compliance = compliance_value

        compliance_values = []

        for month in months:
            value = compliance_map.get(month)

            if value is None:
                value = latest_compliance if latest_compliance is not None else 90

            compliance_values.append(value)

        vials = [
            round(float(tp) * float(av))
            for tp, av in zip(total_patients, avg_vials)
        ]

        absolute_adjustment = [
            absolute_adjustment_map.get(month, 0)
            for month in months
        ]

        adjustment_percent = [
            adjustment_percent_map.get(month, 0)
            for month in months
        ]

        after_adjustment = []

        for vial, compliance, abs_adj, pct_adj in zip(
            vials,
            compliance_values,
            absolute_adjustment,
            adjustment_percent
        ):
            base_adjusted = float(vial) * float(compliance) / 100

            if float(abs_adj) != 0:
                final_value = base_adjusted + float(abs_adj)

            elif float(pct_adj) != 0:
                final_value = base_adjusted + (
                    float(pct_adj) * float(vial) / 100
                )

            else:
                final_value = base_adjusted

            after_adjustment.append(round(final_value))

        ex_factory_total = [
            total + adjusted
            for total, adjusted in zip(
                ex_factory_total,
                after_adjustment
            )
        ]

        demand_vials_table.append({
            "lot": lot,
            "children": [
                {
                    "label": f"{brand} - {lot} Vials",
                    "values": vials
                },
                {
                    "label": "Compliance %",
                    "values": compliance_values
                },
                {
                    "label": "(+) Absolute Adjustment",
                    "values": absolute_adjustment
                },
                {
                    "label": "(x) Adjustment %",
                    "values": adjustment_percent
                },
                {
                    "label": "After Adjustment",
                    "values": after_adjustment
                }
            ]
        })

    demand_vials_table.append({
        "lot": "Total",
        "children": [
            {
                "label": f"{brand} - Ex Factory Demand",
                "values": ex_factory_total
            }
        ]
    })

    return demand_vials_table

def get_child_values(children, label):
    for child in children:
        if child.label.strip().lower() == label.strip().lower():
            return child.values
    return None

def save_demand_vials_values(
    cursor,
    ta_name,
    scenario_name,
    indication,
    brand,
    months,
    demand_vials_table,
    lot_actual_scenario_map=None
):
    for lot_data in demand_vials_table:

        lot = lot_data.get("lot")
        actual_scenario_name = (
            lot_actual_scenario_map.get(lot, scenario_name)
            if lot_actual_scenario_map
            else scenario_name
        )

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
                actual_scenario_name,
                indication,
                brand,
                lot,
                year,
                month
            ))
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
def save_demand_adjustments_service(payload):

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

        for lot_item in payload.demand_vials_table:

            lot = lot_item.lot
            children = lot_item.children
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

            compliance_values = get_child_values(
                children,
                "Compliance %"
            )

            absolute_adjustment_values = get_child_values(
                children,
                "(+) Absolute Adjustment"
            )

            adjustment_percent_values = get_child_values(
                children,
                "(x) Adjustment %"
            )

            if compliance_values is None:
                raise ValueError(
                    f"Compliance % row missing for lot {lot}"
                )

            if absolute_adjustment_values is None:
                absolute_adjustment_values = [0] * len(months)

            if adjustment_percent_values is None:
                adjustment_percent_values = [0] * len(months)

            if not (
                len(compliance_values)
                == len(absolute_adjustment_values)
                == len(adjustment_percent_values)
                == len(months)
            ):
                raise ValueError(
                    f"Values length mismatch for lot {lot}"
                )

            for (
                month_str,
                compliance,
                absolute_adjustment,
                adjustment_percent
            ) in zip(
                months,
                compliance_values,
                absolute_adjustment_values,
                adjustment_percent_values
            ):

                month_dt = datetime.strptime(
                    month_str,
                    "%Y-%m-%d"
                )
                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    SELECT avg_vials_per_dose
                    FROM raw.vials_assumptions
                    WHERE ta_name = %s
                      AND scenario_name = %s
                      AND indication = %s
                      AND brand = %s
                      AND lot = %s
                      AND year = %s
                      AND month = %s
                    LIMIT 1
                """, (
                    ta_name,
                    actual_scenario_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month
                ))

                assumption_row = cursor.fetchone()

                if assumption_row:
                    avg_vials_value = assumption_row[0]
                else:
                    cursor.execute("""
                        SELECT avg_vials_per_dose
                        FROM raw.fact_vials_compliance
                        WHERE ta = %s
                          AND indication = %s
                          AND brand = %s
                          AND lot = %s
                          AND year = %s
                          AND month = %s
                        LIMIT 1
                    """, (
                        ta_name,
                        indication,
                        brand,
                        lot,
                        year,
                        month
                    ))

                    fact_row = cursor.fetchone()

                    avg_vials_value = (
                        fact_row[0]
                        if fact_row
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
                        compliance = EXCLUDED.compliance,
                        absolute_adjustment = EXCLUDED.absolute_adjustment,
                        adjustment_percent = EXCLUDED.adjustment_percent,
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
                    compliance,
                    absolute_adjustment,
                    adjustment_percent
                ))

        response_lots = [
            item.lot
            for item in payload.demand_vials_table
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
            months=months,
            use_assumptions=True,
            lot_actual_scenario_map=lot_actual_scenario_map
            
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            persistency_table=persistency_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True,
            lot_actual_scenario_map=lot_actual_scenario_map
        )
        save_demand_vials_values(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            months=months,
            demand_vials_table=demand_vials_table,
            lot_actual_scenario_map=lot_actual_scenario_map
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
            months=months,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
            "indication": indication,
            "brand": brand,
            "months": months,
            "demand_vials_table": demand_vials_table,
            "inventory_table": inventory_table
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()

def build_inventory_table(
    brand: str,
    demand_vials_table: list,
    stock_percentage: float = 1
):
    total_row = next(
        (
            item for item in demand_vials_table
            if item["lot"] == "Total"
        ),
        None
    )

    if not total_row:
        raise ValueError(
            "Total row not found in demand_vials_table"
        )

    ex_factory_values = total_row["children"][0]["values"]

    inventory_values = [
        round(
            float(value)
            * float(stock_percentage)
            / 100
        )
        for value in ex_factory_values
    ]

    return {
        "stock_percentage": stock_percentage,
        "children": [
            {
                "label": f"{brand} Inventory",
                "values": inventory_values
            }
        ]
    }

def get_compliance_configuration_service(
    ta_name: str,
    indication: str,
    brand: str,
    lots: list
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                lot,
                compliance
            FROM raw.fact_vials_compliance
            WHERE ta = %s
              AND indication = %s
              AND brand = %s
              AND lot = ANY(%s)
            ORDER BY lot, year DESC, month DESC
        """, (
            ta_name,
            indication,
            brand,
            lots
        ))

        rows = cursor.fetchall()

        if not rows:
            raise ValueError("No compliance data found")

        seen_lots = set()
        compliance_configuration = []

        for lot, compliance in rows:
            if lot in seen_lots:
                continue

            value = float(compliance)
            if value.is_integer():
                value = int(value)

            compliance_configuration.append({
                "lot": lot,
                "compliance_percentage": value
            })

            seen_lots.add(lot)

        return {
            "ta_name": ta_name,
            "indication": indication,
            "brand": brand,
            "lots": lots,
            "compliance_configuration": compliance_configuration
        }

    finally:
        cursor.close()
        conn.close()


def apply_compliance_configuration_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        # scenario_name = payload.scenario_name
        indication = payload.indication
        brand = payload.brand

        response_lots = [
            config.lot
            for config in payload.compliance_configuration
        ]
        
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)

        is_finalised_view = db_scenario_name.strip().upper() == "FINALISED"
        lot_actual_scenario_map = {}

        for lot in response_lots:
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
        months = None

        for (
            lot,
            curve_name,
            saved_months,
            new_patients,
            continuing_patients,
            total_patients
        ) in output_rows:

            if months is None:
                months = saved_months

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

        for config in payload.compliance_configuration:

            lot = config.lot
            compliance_value = config.compliance_percentage
            actual_scenario_name = lot_actual_scenario_map.get(
                lot,
                db_scenario_name
            )

            for month_str in months:

                month_dt = datetime.strptime(
                    month_str,
                    "%Y-%m-%d"
                )
                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    SELECT
                        avg_vials_per_dose,
                        absolute_adjustment,
                        adjustment_percent
                    FROM raw.vials_assumptions
                    WHERE ta_name = %s
                      AND scenario_name = %s
                      AND indication = %s
                      AND brand = %s
                      AND lot = %s
                      AND year = %s
                      AND month = %s
                    LIMIT 1
                """, (
                    ta_name,
                    actual_scenario_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month
                ))

                assumption_row = cursor.fetchone()

                if assumption_row:
                    avg_vials_value = assumption_row[0]
                    absolute_adjustment_value = assumption_row[1] or 0
                    adjustment_percent_value = assumption_row[2] or 0
                else:
                    cursor.execute("""
                        SELECT avg_vials_per_dose
                        FROM raw.fact_vials_compliance
                        WHERE ta = %s
                          AND indication = %s
                          AND brand = %s
                          AND lot = %s
                          AND year = %s
                          AND month = %s
                        LIMIT 1
                    """, (
                        ta_name,
                        indication,
                        brand,
                        lot,
                        year,
                        month
                    ))

                    fact_row = cursor.fetchone()

                    avg_vials_value = (
                        fact_row[0]
                        if fact_row
                        else 0
                    )

                    absolute_adjustment_value = 0
                    adjustment_percent_value = 0

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
                        compliance = EXCLUDED.compliance,
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
                    adjustment_percent_value
                ))

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
            months=months,
            use_assumptions=True,
            lot_actual_scenario_map=lot_actual_scenario_map
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            persistency_table=persistency_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True,
            lot_actual_scenario_map=lot_actual_scenario_map
        )
        save_demand_vials_values(
            cursor=cursor,
            ta_name=ta_name,
            scenario_name=db_scenario_name,
            indication=indication,
            brand=brand,
            months=months,
            demand_vials_table=demand_vials_table,
            lot_actual_scenario_map=lot_actual_scenario_map
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
            months=months,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
            "indication": indication,
            "brand": brand,
            "months": months,
            "demand_vials_table": demand_vials_table,
            "inventory_table": inventory_table
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()

def clean_scenario_name(scenario_name: str) -> str:
    return (
        scenario_name
        .replace(" (Finalised)", "")
        .strip()
    )
def apply_edit_row_values_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        # scenario_name = payload.scenario_name
        indication = payload.indication
        brand = payload.brand

        config = payload.edit_values_configuration
        selected_lots = config.selected_lots
        start_month = config.start_month
        percentage_change_per_month = config.percentage_change_per_month
        number_of_months = config.number_of_months
        response_lots = payload.lots
        
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)
        is_finalised_view = db_scenario_name.strip().upper() == "FINALISED"
        lot_actual_scenario_map = {}

        for lot in response_lots:
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
        months = None

        for (
            lot,
            curve_name,
            saved_months,
            new_patients,
            continuing_patients,
            total_patients
        ) in output_rows:

            if months is None:
                months = saved_months

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

        if start_month not in months:
            raise ValueError(
                f"start_month {start_month} not found in available months"
            )

        start_idx = months.index(start_month)

        end_idx = min(
            start_idx + number_of_months,
            len(months)
        )

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
            months=months,
            use_assumptions=True,
            lot_actual_scenario_map=lot_actual_scenario_map
        )

        demand_vials_table = []
        ex_factory_total = [0] * len(months)

        for lot in lots:
            
            actual_scenario_name = lot_actual_scenario_map.get(
                lot,
                db_scenario_name
            )

            lot_persistency = next(
                (
                    item for item in persistency_table
                    if item["lot"] == lot
                ),
                None
            )

            lot_avg_vials = next(
                (
                    item for item in avg_vials_table
                    if item["lot"] == lot
                ),
                None
            )

            if not lot_persistency:
                raise ValueError(
                    f"Persistency data not found for lot {lot}"
                )

            if not lot_avg_vials:
                raise ValueError(
                    f"Avg vials data not found for lot {lot}"
                )

            total_patients = next(
                (
                    child["values"]
                    for child in lot_persistency["children"]
                    if child["label"] == "Total Patients"
                ),
                None
            )

            if total_patients is None:
                raise ValueError(
                    f"Total Patients not found for lot {lot}"
                )

            avg_vials = lot_avg_vials["children"][0]["values"]

            cursor.execute("""
                SELECT
                    year,
                    month,
                    compliance
                FROM raw.vials_assumptions
                WHERE ta_name = %s
                AND scenario_name = %s
                AND indication = %s
                AND brand = %s
                AND lot = %s
                ORDER BY year, month
            """, (
                ta_name,
                actual_scenario_name,
                indication,
                brand,
                lot
            ))

            compliance_rows = cursor.fetchall()

            if not compliance_rows:
                cursor.execute("""
                    SELECT
                        year,
                        month,
                        compliance
                    FROM raw.fact_vials_compliance
                    WHERE ta = %s
                    AND indication = %s
                    AND brand = %s
                    AND lot = %s
                    ORDER BY year, month
                """, (
                    ta_name,
                    indication,
                    brand,
                    lot
                ))


                compliance_rows = cursor.fetchall()

            if not compliance_rows:
                raise ValueError(
                    f"No compliance data found for lot {lot}"
                )

            compliance_map = {}
            latest_compliance = 100

            for year, month, compliance in compliance_rows:
                month_key = f"{int(year)}-{int(month):02d}-01"
                value = float(compliance)

                if value.is_integer():
                    value = int(value)

                compliance_map[month_key] = value
                latest_compliance = value

            base_compliance_values = [
                compliance_map.get(month, latest_compliance)
                for month in months
            ]

            compliance_values = []

            for idx, base_compliance in enumerate(base_compliance_values):

                if (
                    lot in selected_lots
                    and start_idx <= idx < end_idx
                ):
                    updated_compliance = (
                        float(base_compliance)
                        + float(percentage_change_per_month)
                    )
                else:
                    updated_compliance = float(base_compliance)

                compliance_values.append(
                    round(updated_compliance, 2)
                )

            for month_str, compliance_value in zip(
                months,
                compliance_values
            ):

                month_dt = datetime.strptime(
                    month_str,
                    "%Y-%m-%d"
                )

                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    SELECT avg_vials_per_dose
                    FROM raw.vials_assumptions
                    WHERE ta_name = %s
                      AND scenario_name = %s
                      AND indication = %s
                      AND brand = %s
                      AND lot = %s
                      AND year = %s
                      AND month = %s
                    LIMIT 1
                """, (
                    ta_name,
                    actual_scenario_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month
                ))

                assumption_row = cursor.fetchone()

                if assumption_row:
                    avg_vials_value = assumption_row[0]
                else:
                    cursor.execute("""
                        SELECT avg_vials_per_dose
                        FROM raw.fact_vials_compliance
                        WHERE ta = %s
                          AND indication = %s
                          AND brand = %s
                          AND lot = %s
                          AND year = %s
                          AND month = %s
                        LIMIT 1
                    """, (
                        ta_name,
                        indication,
                        brand,
                        lot,
                        year,
                        month
                    ))

                    fact_row = cursor.fetchone()

                    avg_vials_value = (
                        fact_row[0]
                        if fact_row
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
                        %s, %s,
                        0, 0
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
                        compliance = EXCLUDED.compliance,
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
                    compliance_value
                ))

            vials = [
                round(float(tp) * float(av))
                for tp, av in zip(total_patients, avg_vials)
            ]

            absolute_adjustment = [0] * len(months)
            adjustment_percent = [0] * len(months)

            after_adjustment = [
                round(
                    float(vial)
                    * float(compliance)
                    / 100
                )
                for vial, compliance in zip(
                    vials,
                    compliance_values
                )
            ]
            for month_str, after_adjustment_value in zip(
                months,
                after_adjustment
            ):
                month_dt = datetime.strptime(month_str, "%Y-%m-%d")
                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    UPDATE raw.vials_assumptions
                    SET
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
                    after_adjustment_value,
                    ta_name,
                    actual_scenario_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month
                ))
            ex_factory_total = [
                total + adjusted
                for total, adjusted in zip(
                    ex_factory_total,
                    after_adjustment
                )
            ]

            demand_vials_table.append({
                "lot": lot,
                "children": [
                    {
                        "label": f"{brand} - {lot} Vials",
                        "values": vials
                    },
                    {
                        "label": "Compliance %",
                        "values": compliance_values
                    },
                    {
                        "label": "(+) Absolute Adjustment",
                        "values": absolute_adjustment
                    },
                    {
                        "label": "(x) Adjustment %",
                        "values": adjustment_percent
                    },
                    {
                        "label": "After Adjustment",
                        "values": after_adjustment
                    }
                ]
            })

        demand_vials_table.append({
            "lot": "Total",
            "children": [
                {
                    "label": f"{brand} - Ex Factory Demand",
                    "values": ex_factory_total
                }
            ]
        })

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
            months=months,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
            "indication": indication,
            "brand": brand,
            "months": months,
            "demand_vials_table": demand_vials_table,
            "inventory_table": inventory_table
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()

def save_ex_factory_output(
    cursor,
    ta_name: str,
    scenario_name: str,
    indication: str,
    brand: str,
    months: list,
    demand_vials_table: list,
    stock_percentage: float = 1
):
    total_row = next(
        (
            item for item in demand_vials_table
            if item["lot"] == "Total"
        ),
        None
    )

    if not total_row:
        raise ValueError(
            "Total row not found in demand_vials_table"
        )

    ex_factory_values = total_row["children"][0]["values"]

    if len(ex_factory_values) != len(months):
        raise ValueError(
            "Ex factory values length does not match months"
        )

    for month_str, ex_factory_value in zip(
        months,
        ex_factory_values
    ):
        month_dt = datetime.strptime(
            month_str,
            "%Y-%m-%d"
        )

        year = month_dt.year
        month = month_dt.month

        inventory_value = round(
            float(ex_factory_value)
            * float(stock_percentage)
            / 100
        )

        cursor.execute("""
            INSERT INTO raw.vials_outputs (
                ta_name,
                scenario_name,
                indication,
                brand,
                year,
                month,
                ex_factory_demand,
                stock_percentage,
                inventory_vials
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (
                ta_name,
                scenario_name,
                indication,
                brand,
                year,
                month
            )
            DO UPDATE SET
                ex_factory_demand = EXCLUDED.ex_factory_demand,
                stock_percentage = EXCLUDED.stock_percentage,
                inventory_vials = EXCLUDED.inventory_vials,
                updated_at = CURRENT_TIMESTAMP
        """, (
            ta_name,
            scenario_name,
            indication,
            brand,
            year,
            month,
            ex_factory_value,
            stock_percentage,
            inventory_value
        ))


def update_inventory_stock_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        indication = payload.indication
        brand = payload.brand
        months = payload.months
        stock_percentage = payload.stock_percentage
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)

        

        inventory_values = []

        for month_str in months:

            month_dt = datetime.strptime(
                month_str,
                "%Y-%m-%d"
            )

            year = month_dt.year
            month = month_dt.month

            cursor.execute("""
                SELECT
                    ex_factory_demand
                FROM raw.vials_outputs
                WHERE ta_name = %s
                  AND scenario_name = %s
                  AND indication = %s
                  AND brand = %s
                  AND year = %s
                  AND month = %s
            """, (
                ta_name,
                db_scenario_name,
                indication,
                brand,
                year,
                month
            ))

            row = cursor.fetchone()

            if not row:
                raise ValueError(
                    f"No ex-factory demand found for month {month_str}. Please run apply/recalculate first."
                )

            ex_factory_demand = row[0]

            inventory_value = round(
                float(ex_factory_demand)
                * float(stock_percentage)
                / 100
            )

            inventory_values.append(inventory_value)

            cursor.execute("""
                UPDATE raw.vials_outputs
                SET
                    stock_percentage = %s,
                    inventory_vials = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s
                  AND scenario_name = %s
                  AND indication = %s
                  AND brand = %s
                  AND year = %s
                  AND month = %s
            """, (
                stock_percentage,
                inventory_value,
                ta_name,
                db_scenario_name,
                indication,
                brand,
                year,
                month
            ))

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
            "indication": indication,
            "brand": brand,
            "months": months,
            "inventory_table": {
                "stock_percentage": stock_percentage,
                "children": [
                    {
                        "label": f"{brand} Inventory",
                        "values": inventory_values
                    }
                ]
            }
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()