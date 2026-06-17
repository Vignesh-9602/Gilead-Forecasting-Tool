from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException

from app.db.connection import get_connection
from app.services.Retaining_Filters import get_saved_user_filter


def clean_scenario_name(scenario_name: str):
    return (
        scenario_name
        .replace(" (Finalised)", "")
        .replace("_Finalised", "")
        .replace("_finalised", "")
        .strip()
    )


def sort_lot_key(lot):
    lot = str(lot).replace("+", "").replace("L", "")
    try:
        return int(lot)
    except:
        return 999


def get_available_months_from_config(cur, ta_name: str):
    cur.execute("""
        SELECT config
        FROM raw.forecast_configurations
        WHERE config->>'ta_name' = %s
        ORDER BY updated_at DESC
        LIMIT 1
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
    cur_month = train_start

    while cur_month <= forecast_end:
        months.append(cur_month.strftime("%Y-%m-%d"))
        cur_month += relativedelta(months=1)

    return months


def get_output_filters_service(ta_name: str):

    conn = get_connection()
    cur = conn.cursor()

    try:
        # =====================================================
        # 1. Fetch scenario / indication / lot / brand
        # From vials_assumptions
        # =====================================================
        cur.execute("""
            SELECT DISTINCT
                scenario_name,
                indication,
                lot,
                brand
            FROM raw.vials_assumptions
            WHERE ta_name = %s
              AND scenario_name IS NOT NULL
              AND indication IS NOT NULL
              AND lot IS NOT NULL
              AND brand IS NOT NULL
            ORDER BY scenario_name, indication, lot, brand
        """, (ta_name,))

        rows = cur.fetchall()

        data = {}
        scenario_names = []

        for scenario_name, indication, lot, brand in rows:

            display_scenario = clean_scenario_name(scenario_name)

            if display_scenario not in scenario_names:
                scenario_names.append(display_scenario)

            data.setdefault(display_scenario, {})
            data[display_scenario].setdefault(indication, {})
            data[display_scenario][indication].setdefault(lot, [])

            if brand not in data[display_scenario][indication][lot]:
                data[display_scenario][indication][lot].append(brand)

        # =====================================================
        # 2. Add Finalised scenario
        # Finalised uses actual scenario rows from vials_assumptions
        # mapped via forecast_scenarios.is_finalized = TRUE
        # =====================================================
        cur.execute("""
            SELECT DISTINCT
                va.scenario_name,
                va.indication,
                va.lot,
                va.brand
            FROM raw.vials_assumptions va
            INNER JOIN raw.forecast_scenarios fs
                ON LOWER(fs.ta_name) = LOWER(va.ta_name)
               AND LOWER(fs.scenario_name) = LOWER(va.scenario_name)
               AND LOWER(fs.indication) = LOWER(va.indication)
               AND LOWER(fs.lot) = LOWER(va.lot)
            WHERE va.ta_name = %s
              AND fs.is_finalized = TRUE
              AND va.scenario_name IS NOT NULL
              AND va.indication IS NOT NULL
              AND va.lot IS NOT NULL
              AND va.brand IS NOT NULL
            ORDER BY va.indication, va.lot, va.brand
        """, (ta_name,))

        finalised_rows = cur.fetchall()

        if finalised_rows:

            if "Finalised" not in scenario_names:
                scenario_names.insert(0, "Finalised")

            data.setdefault("Finalised", {})

            for scenario_name, indication, lot, brand in finalised_rows:

                data["Finalised"].setdefault(indication, {})
                data["Finalised"][indication].setdefault(lot, [])

                if brand not in data["Finalised"][indication][lot]:
                    data["Finalised"][indication][lot].append(brand)

        # =====================================================
        # 3. Order scenarios
        # Finalised, BASE, others
        # =====================================================
        ordered_scenarios = []

        if "Finalised" in scenario_names:
            ordered_scenarios.append("Finalised")

        if "BASE" in scenario_names:
            ordered_scenarios.append("BASE")

        for scenario in sorted(scenario_names):
            if scenario not in ordered_scenarios:
                ordered_scenarios.append(scenario)

        scenario_names = ordered_scenarios

        # =====================================================
        # 4. Available months
        # =====================================================
        available_months = get_available_months_from_config(
            cur,
            ta_name
        )

        default_start_date = available_months[0] if available_months else ""
        default_end_date = available_months[-1] if available_months else ""

        # =====================================================
        # 5. Default scenario
        # =====================================================
        default_scenario_name = (
            "Finalised"
            if "Finalised" in scenario_names
            else "BASE"
            if "BASE" in scenario_names
            else scenario_names[0]
            if scenario_names
            else ""
        )

        # =====================================================
        # 6. Helper to get all indications, lots, brands
        # for a scenario
        # =====================================================
        def get_all_filter_values_for_scenario(scenario_name: str):

            scenario_data = data.get(scenario_name, {})

            indications = sorted(
                scenario_data.keys()
            )

            lots_set = set()
            brands_set = set()

            for indication_name, lots_map in scenario_data.items():

                for lot_name, brands in lots_map.items():

                    lots_set.add(lot_name)

                    for brand_name in brands:
                        brands_set.add(brand_name)

            lots = sorted(
                list(lots_set),
                key=sort_lot_key
            )

            brands = sorted(list(brands_set))

            return indications, lots, brands

        # =====================================================
        # 7. Default selected filter
        # Send all indications, lots, brands
        # =====================================================
        default_indications, default_lots, default_brands = (
            get_all_filter_values_for_scenario(default_scenario_name)
            if default_scenario_name
            else ([], [], [])
        )

        default_filter = {
            "scenario_name": default_scenario_name,
            "indications": default_indications,
            "lots": default_lots,
            "brands": default_brands,
            "start_date": default_start_date,
            "end_date": default_end_date
        }

        # =====================================================
        # 8. Saved selected filter
        # Scenario from preference, but indications/lots/brands all sent
        # =====================================================
        user_id = "system"

        saved_filter = get_saved_user_filter(
            cur,
            user_id,
            ta_name
        )

        if saved_filter:

            saved_scenario = (
                saved_filter.get("scenario_name")
                or default_scenario_name
            )

            if saved_scenario and saved_scenario.lower().endswith("_finalised"):
                saved_scenario = "Finalised"

            saved_scenario = clean_scenario_name(saved_scenario)

            if saved_scenario not in scenario_names:
                saved_scenario = default_scenario_name

            selected_indications, selected_lots, selected_brands = (
                get_all_filter_values_for_scenario(saved_scenario)
                if saved_scenario
                else ([], [], [])
            )

            selected_filter = {
                "scenario_name": saved_scenario,
                "indications": selected_indications,
                "lots": selected_lots,
                "brands": selected_brands,
                "start_date": saved_filter.get("start_date") or default_start_date,
                "end_date": saved_filter.get("end_date") or default_end_date
            }

        else:
            selected_filter = default_filter

        return {
            "ta_name": ta_name,
            "scenario_names": scenario_names,
            "data": data,
            "available_months": available_months,
            "selected_filter": selected_filter
        }

    finally:
        cur.close()
        conn.close()

def month_range(start_date: str, end_date: str):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    months = []
    cur = start

    while cur <= end:
        months.append(cur.strftime("%Y-%m-%d"))
        cur += relativedelta(months=1)

    return months


def clean_scenario_name(scenario_name: str):
    return (
        scenario_name
        .replace(" (Finalised)", "")
        .replace("_Finalised", "")
        .replace("_finalised", "")
        .strip()
    )


def get_last_history_month(cur, ta_name: str):

    cur.execute("""
        SELECT config->>'train_end_date'
        FROM raw.forecast_configurations
        WHERE config->>'ta_name' = %s
        ORDER BY updated_at DESC
        LIMIT 1
    """, (ta_name,))

    row = cur.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="No forecast configuration found for selected therapy area."
        )

    return datetime.strptime(row[0], "%Y-%m-%d").strftime("%Y-%m-%d")


def get_final_factor_map(
    cur,
    ta_name: str,
    scenario_name: str,
    brand: str,
    start_date: str,
    end_date: str
):

    cur.execute("""
        SELECT
            month_date,
            final_factor
        FROM raw.revenue_outputs
        WHERE ta_name = %s
          AND scenario_name = %s
          AND brand = %s
          AND month_date BETWEEN %s::date AND %s::date
    """, (
        ta_name,
        scenario_name,
        brand,
        start_date,
        end_date
    ))

    return {
        row[0].strftime("%Y-%m-%d"): float(row[1])
        for row in cur.fetchall()
        if row[1] is not None
    }


def calculate_adjustment(
    after_adjustment,
    absolute_adjustment,
    adjustment_percent
):
    after_adjustment = float(after_adjustment or 0)
    absolute_adjustment = float(absolute_adjustment or 0)
    adjustment_percent = float(adjustment_percent or 0)

    if absolute_adjustment != 0:
        return absolute_adjustment

    if adjustment_percent != 0:
        return after_adjustment * adjustment_percent / 100.0

    return 0


def get_output_apply_service(payload):

    conn = get_connection()
    cur = conn.cursor()

    try:
        ta_name = payload.ta_name
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)

        is_finalised_view = (
            display_scenario_name.lower() == "finalised"
        )

        indications = payload.indications or []
        lots = payload.lots or []
        brands = payload.brands or []

        start_date = payload.start_date
        end_date = payload.end_date

        months = month_range(start_date, end_date)

        last_history_month = get_last_history_month(
            cur,
            ta_name
        )

        # =====================================================
        # 1. Fetch demand rows
        # =====================================================
        if is_finalised_view:

            cur.execute("""
                SELECT
                    va.indication,
                    va.lot,
                    va.brand,
                    va.year,
                    va.month,
                    va.after_adjustment,
                    va.absolute_adjustment,
                    va.adjustment_percent
                FROM raw.vials_assumptions va
                WHERE va.ta_name = %s
                  AND va.indication = ANY(%s)
                  AND va.lot = ANY(%s)
                  AND va.brand = ANY(%s)
                  AND make_date(va.year, va.month, 1)
                        BETWEEN %s::date AND %s::date
                  AND EXISTS (
                        SELECT 1
                        FROM raw.forecast_scenarios fs
                        WHERE LOWER(fs.ta_name) = LOWER(va.ta_name)
                          AND LOWER(fs.scenario_name) = LOWER(va.scenario_name)
                          AND LOWER(fs.indication) = LOWER(va.indication)
                          AND LOWER(fs.lot) = LOWER(va.lot)
                          AND fs.is_finalized = TRUE
                  )
            """, (
                ta_name,
                indications,
                lots,
                brands,
                start_date,
                end_date
            ))

        else:

            cur.execute("""
                SELECT
                    indication,
                    lot,
                    brand,
                    year,
                    month,
                    after_adjustment,
                    absolute_adjustment,
                    adjustment_percent
                FROM raw.vials_assumptions
                WHERE ta_name = %s
                  AND scenario_name = %s
                  AND indication = ANY(%s)
                  AND lot = ANY(%s)
                  AND brand = ANY(%s)
                  AND make_date(year, month, 1)
                        BETWEEN %s::date AND %s::date
            """, (
                ta_name,
                db_scenario_name,
                indications,
                lots,
                brands,
                start_date,
                end_date
            ))

        rows = cur.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No demand data found for selected filters."
            )

        # =====================================================
        # 2. Final demand rows
        # final_factor from revenue_outputs
        # missing final_factor = 1
        # =====================================================
        final_demand_rows = []
        final_factor_cache = {}

        for (
            row_indication,
            row_lot,
            row_brand,
            year,
            month,
            after_adjustment,
            absolute_adjustment,
            adjustment_percent
        ) in rows:

            month_key = f"{int(year)}-{int(month):02d}-01"

            if row_brand not in final_factor_cache:
                final_factor_cache[row_brand] = get_final_factor_map(
                    cur=cur,
                    ta_name=ta_name,
                    scenario_name=display_scenario_name,
                    brand=row_brand,
                    start_date=start_date,
                    end_date=end_date
                )

            final_factor = final_factor_cache[row_brand].get(
                month_key,
                1
            )

            adjustment = calculate_adjustment(
                after_adjustment,
                absolute_adjustment,
                adjustment_percent
            )

            final_demand = (
                float(after_adjustment or 0) + adjustment
            ) * final_factor

            final_demand_rows.append({
                "indication": row_indication,
                "lot": row_lot,
                "brand": row_brand,
                "month": month_key,
                "final_demand": final_demand
            })

        # =====================================================
        # 3. Forecast start index
        # =====================================================
        forecast_start_index = len(months)

        for idx, month in enumerate(months):
            if month > last_history_month:
                forecast_start_index = idx
                break

        # =====================================================
        # 4. Indication view
        # Group by indication, children = brands
        # =====================================================
        indication_total_map = {
            month: 0
            for month in months
        }

        indication_row_map = {}

        for row in final_demand_rows:

            row_indication = row["indication"]
            row_brand = row["brand"]
            month = row["month"]

            indication_row_map.setdefault(row_indication, {
                "total": {m: 0 for m in months},
                "brands": {}
            })

            indication_row_map[row_indication]["brands"].setdefault(
                row_brand,
                {m: 0 for m in months}
            )

            indication_row_map[row_indication]["total"][month] += row["final_demand"]
            indication_row_map[row_indication]["brands"][row_brand][month] += row["final_demand"]
            indication_total_map[month] += row["final_demand"]

        indication_total_values = [
            round(indication_total_map.get(month, 0))
            for month in months
        ]

        indication_rows = []

        for indication_name in indications:

            if indication_name not in indication_row_map:
                continue

            total_map = indication_row_map[indication_name]["total"]
            brand_map = indication_row_map[indication_name]["brands"]

            children = []

            for brand_name in brands:

                if brand_name not in brand_map:
                    continue

                children.append({
                    "label": brand_name,
                    "values": [
                        round(brand_map[brand_name].get(month, 0))
                        for month in months
                    ]
                })

            indication_rows.append({
                "label": f"{indication_name} Total Demand",
                "values": [
                    round(total_map.get(month, 0))
                    for month in months
                ],
                "children": children
            })

        # =====================================================
        # 5. LOT view
        # Group by lot, children = brands
        # =====================================================
        lot_total_map = {
            month: 0
            for month in months
        }

        lot_row_map = {}

        for row in final_demand_rows:

            row_lot = row["lot"]
            row_brand = row["brand"]
            month = row["month"]

            lot_row_map.setdefault(row_lot, {
                "total": {m: 0 for m in months},
                "brands": {}
            })

            lot_row_map[row_lot]["brands"].setdefault(
                row_brand,
                {m: 0 for m in months}
            )

            lot_row_map[row_lot]["total"][month] += row["final_demand"]
            lot_row_map[row_lot]["brands"][row_brand][month] += row["final_demand"]
            lot_total_map[month] += row["final_demand"]

        lot_total_values = [
            round(lot_total_map.get(month, 0))
            for month in months
        ]

        lot_rows = []

        for lot_name in lots:

            if lot_name not in lot_row_map:
                continue

            total_map = lot_row_map[lot_name]["total"]
            brand_map = lot_row_map[lot_name]["brands"]

            children = []

            for brand_name in brands:

                if brand_name not in brand_map:
                    continue

                children.append({
                    "label": brand_name,
                    "values": [
                        round(brand_map[brand_name].get(month, 0))
                        for month in months
                    ]
                })

            lot_rows.append({
                "label": f"{lot_name} Total Demand",
                "values": [
                    round(total_map.get(month, 0))
                    for month in months
                ],
                "children": children
            })

        # =====================================================
        # 6. Save selected filter
        # Since DB has single indication/lot/product fields,
        # save first selected item only
        # =====================================================
        saved_indication = indications[0] if indications else None
        saved_lot = lots[0] if lots else None
        saved_brand = brands[0] if brands else None

        cur.execute("""
            UPDATE raw.user_filter_preferences
            SET
                scenario_name = %s,
                indication = %s,
                lot = %s,
                product = %s,
                start_date = %s,
                end_date = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
              AND ta_name = %s
        """, (
            display_scenario_name,
            saved_indication,
            saved_lot,
            saved_brand,
            start_date,
            end_date,
            "system",
            ta_name
        ))

        if cur.rowcount == 0:

            cur.execute("""
                INSERT INTO raw.user_filter_preferences (
                    user_id,
                    ta_name,
                    scenario_name,
                    indication,
                    lot,
                    product,
                    start_date,
                    end_date,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                )
            """, (
                "system",
                ta_name,
                display_scenario_name,
                saved_indication,
                saved_lot,
                saved_brand,
                start_date,
                end_date
            ))

        conn.commit()

        return {
            "ta_name": ta_name,
            "scenario_name": display_scenario_name,
            "indications": indications,
            "lots": lots,
            "brands": brands,
            "views": {
                "indication": {
                    "chart": {
                        "months": months,
                        "forecast_start_index": forecast_start_index,
                        "series": [
                            {
                                "label": "Demand Volume",
                                "train_values": indication_total_values[:forecast_start_index],
                                "forecast_values": indication_total_values[forecast_start_index:]
                            }
                        ]
                    },
                    "table": {
                        "hierarchy_label": "Total Aggregated Demand (By Indication)",
                        "months": months,
                        "total_values": indication_total_values,
                        "rows": indication_rows
                    }
                },
                "lot": {
                    "chart": {
                        "months": months,
                        "forecast_start_index": forecast_start_index,
                        "series": [
                            {
                                "label": "Demand Volume",
                                "train_values": lot_total_values[:forecast_start_index],
                                "forecast_values": lot_total_values[forecast_start_index:]
                            }
                        ]
                    },
                    "table": {
                        "hierarchy_label": "Total Aggregated Demand (By LOT)",
                        "months": months,
                        "total_values": lot_total_values,
                        "rows": lot_rows
                    }
                }
            }
        }

    finally:
        cur.close()
        conn.close()