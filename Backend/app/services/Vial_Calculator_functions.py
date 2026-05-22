from app.db.connection import get_connection

# ---------------------------------------------------
# Avg_Vials per dose
# ---------------------------------------------------
def build_avg_vials_per_dose_table(
    cursor,
    ta_name: str,
    indication: str,
    brand: str,
    lots: list,
    months: list
):
    avg_vials_table = []

# """
#     Builds Avg Vials Per Dose table.

#     Logic:
#     - Fetch available avg vials data from raw.fact_vials_compliance
#     - For selected months, use matching year/month value
#     - If selected month is future and not available in DB,
#       populate using latest available month value for that lot/brand
# """

    for lot in lots:
        cursor.execute("""
            SELECT
                year,
                month,
                avg_vials_per_dose
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
    avg_vials_per_dose_table: list
):
    demand_vials_table = []
    ex_factory_total = [0] * len(months)

    for lot in lots:

        # -------------------------------
        # Get New Patients from persistency table
        # -------------------------------
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

        # -------------------------------
        # Get Avg Vials from avg vials table
        # -------------------------------
        lot_avg_vials = next(
            (item for item in avg_vials_per_dose_table if item["lot"] == lot),
            None
        )

        if not lot_avg_vials:
            raise ValueError(f"Avg Vials data not found for lot {lot}")

        avg_vials = lot_avg_vials["children"][0]["values"]

        # -------------------------------
        # Get Compliance from DB
        # -------------------------------
        cursor.execute("""
            SELECT
                year,
                month,
                compliance
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
        latest_compliance = None

        for year, month, compliance in rows:
            month_key = f"{int(year)}-{int(month):02d}-01"

            value = float(compliance)
            if value.is_integer():
                value = int(value)

            compliance_map[month_key] = value
            latest_compliance = value

        compliance_values = [
            compliance_map.get(month, latest_compliance)
            for month in months
        ]

        # -------------------------------
        # Calculations
        # -------------------------------
        vials = [
            round(float(np_) * float(av))
            for np_, av in zip(total_patients, avg_vials)
        ]

        absolute_adjustment = [0] * len(months)
        adjustment_percent = [0] * len(months)

        after_adjustment = [
            round(
                vial * float(compliance) / 100
            )
            for vial, compliance in zip(vials, compliance_values)
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

    return demand_vials_table

def build_inventory_table(
    brand: str,
    demand_vials_table: list,
    stock_percentage: float = 1
):
    """
    Inventory Vials =
    Ex Factory Demand * stock_percentage / 100
    """

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