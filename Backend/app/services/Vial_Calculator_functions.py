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
    use_assumptions: bool = False
):
    avg_vials_table = []

    for lot in lots:

        if use_assumptions:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    avg_vials_per_dose
                FROM raw.vials_assumptions
                WHERE ta_name = %s
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

def build_demand_vials_table(
    cursor,
    ta_name: str,
    indication: str,
    brand: str,
    lots: list,
    months: list,
    persistency_table: list,
    avg_vials_per_dose_table: list,
    use_assumptions: bool = False
):
    demand_vials_table = []
    ex_factory_total = [0] * len(months)

    for lot in lots:

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
                  AND brand = %s
                  AND lot = %s
                ORDER BY year, month
            """, (
                ta_name,
                indication,
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

            compliance_value = float(compliance)
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
                if use_assumptions:
                    raise ValueError(
                        f"Compliance not found in assumptions for lot {lot}, month {month}"
                    )
                value = latest_compliance

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


def save_demand_adjustments_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        indication = payload.indication
        brand = payload.brand
        months = payload.months

        for lot_item in payload.demand_vials_table:

            lot = lot_item.lot
            children = lot_item.children

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

                month_dt = datetime.strptime(month_str, "%Y-%m-%d")
                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    INSERT INTO raw.vials_assumptions (
                        ta_name,
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
                        %s, %s, %s, %s,
                        %s, %s,
                        COALESCE(
                            (
                                SELECT avg_vials_per_dose
                                FROM raw.vials_assumptions
                                WHERE ta_name = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            (
                                SELECT avg_vials_per_dose
                                FROM raw.fact_vials_compliance
                                WHERE ta = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            0
                        ),
                        %s,
                        %s,
                        %s
                    )
                    ON CONFLICT (
                        ta_name,
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
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    compliance,
                    absolute_adjustment,
                    adjustment_percent
                ))
        response_lots = [
                item.lot
                for item in payload.demand_vials_table
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
              AND indication = %s
              AND brand = %s
            AND lot = ANY(%s)
            ORDER BY lot
        """, (
            ta_name,
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
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            use_assumptions=True
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            persistency_table=persistency_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True
        )

        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )
        save_ex_factory_output(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            months=months,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )
        conn.commit()

        return {
            "ta_name": ta_name,
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
        indication = payload.indication
        brand = payload.brand
        response_lots = [
                config.lot
                for config in payload.compliance_configuration
            ]
        # Fetch current persistency output to get months
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
            AND lot = ANY(%s)
            ORDER BY lot
        """, (
            ta_name,
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

        # Save same compliance % to all months for each lot
        for config in payload.compliance_configuration:

            lot = config.lot
            compliance_value = config.compliance_percentage

            for month_str in months:
                month_dt = datetime.strptime(month_str, "%Y-%m-%d")
                year = month_dt.year
                month = month_dt.month

                cursor.execute("""
                    INSERT INTO raw.vials_assumptions (
                        ta_name,
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
                        %s, %s, %s, %s,
                        %s, %s,
                        COALESCE(
                            (
                                SELECT avg_vials_per_dose
                                FROM raw.vials_assumptions
                                WHERE ta_name = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            (
                                SELECT avg_vials_per_dose
                                FROM raw.fact_vials_compliance
                                WHERE ta = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            0
                        ),
                        %s,
                        COALESCE(
                            (
                                SELECT absolute_adjustment
                                FROM raw.vials_assumptions
                                WHERE ta_name = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            0
                        ),
                        COALESCE(
                            (
                                SELECT adjustment_percent
                                FROM raw.vials_assumptions
                                WHERE ta_name = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            0
                        )
                    )
                    ON CONFLICT (
                        ta_name,
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
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    compliance_value,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month
                ))

        lots = [
            item["lot"]
            for item in persistency_table
        ]

        avg_vials_table = build_avg_vials_per_dose_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            use_assumptions=True
        )

        demand_vials_table = build_demand_vials_table(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            persistency_table=persistency_table,
            avg_vials_per_dose_table=avg_vials_table,
            use_assumptions=True
        )

        inventory_table = build_inventory_table(
            brand=brand,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )
        save_ex_factory_output(
            cursor=cursor,
            ta_name=ta_name,
            indication=indication,
            brand=brand,
            months=months,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )
        conn.commit()

        return {
            "ta_name": ta_name,
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

def apply_edit_row_values_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        indication = payload.indication
        brand = payload.brand

        config = payload.edit_values_configuration
        selected_lots = config.selected_lots
        start_month = config.start_month
        percentage_change_per_month = config.percentage_change_per_month
        number_of_months = config.number_of_months
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
              AND indication = %s
              AND brand = %s
            AND lot = ANY(%s)
            ORDER BY lot
        """, (
            ta_name,
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
            indication=indication,
            brand=brand,
            lots=lots,
            months=months,
            use_assumptions=True
        )

        demand_vials_table = []
        ex_factory_total = [0] * len(months)

        for lot in lots:

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
                    percent_to_apply = percentage_change_per_month

                    updated_compliance = (
                            float(base_compliance)
                            + float(percent_to_apply)
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
                    INSERT INTO raw.vials_assumptions (
                        ta_name,
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
                        %s, %s, %s, %s,
                        %s, %s,
                        COALESCE(
                            (
                                SELECT avg_vials_per_dose
                                FROM raw.vials_assumptions
                                WHERE ta_name = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            (
                                SELECT avg_vials_per_dose
                                FROM raw.fact_vials_compliance
                                WHERE ta = %s
                                  AND indication = %s
                                  AND brand = %s
                                  AND lot = %s
                                  AND year = %s
                                  AND month = %s
                            ),
                            0
                        ),
                        %s,
                        0,
                        0
                    )
                    ON CONFLICT (
                        ta_name,
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
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

                    ta_name,
                    indication,
                    brand,
                    lot,
                    year,
                    month,

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
            indication=indication,
            brand=brand,
            months=months,
            demand_vials_table=demand_vials_table,
            stock_percentage=1
        )

        conn.commit()

        return {
            "ta_name": ta_name,
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
                indication,
                brand,
                year,
                month,
                ex_factory_demand,
                stock_percentage,
                inventory_vials
            )
            VALUES (
                %s, %s, %s,
                %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (
                ta_name,
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
                  AND indication = %s
                  AND brand = %s
                  AND year = %s
                  AND month = %s
            """, (
                ta_name,
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
                  AND indication = %s
                  AND brand = %s
                  AND year = %s
                  AND month = %s
            """, (
                stock_percentage,
                inventory_value,
                ta_name,
                indication,
                brand,
                year,
                month
            ))

        conn.commit()

        return {
            "ta_name": ta_name,
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