from datetime import datetime
from dateutil.relativedelta import relativedelta
from app.db.connection import get_connection
from fastapi import HTTPException

from app.services.Retaining_Filters import get_saved_user_filter, save_user_filter


def month_range(start_date: str, end_date: str):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    months = []
    cur = start

    while cur <= end:
        months.append(cur.strftime("%Y-%m-%d"))
        cur += relativedelta(months=1)

    return months

def clean_scenario_name(scenario_name: str) -> str:
    return (
        scenario_name
        .replace(" (Finalised)", "")
        .strip()
    )
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

def get_net_revenue_filters_service(ta_name: str):

    conn = get_connection()
    cur = conn.cursor()

    try:
        # =============================
        # 1. Get scenario names + Finalised
        # =============================
        cur.execute("""
            SELECT
                scenario_name,
                BOOL_OR(is_finalized = TRUE) AS is_finalized
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND scenario_name IS NOT NULL
            GROUP BY scenario_name
            ORDER BY scenario_name
        """, (
            ta_name,
        ))

        scenario_rows = cur.fetchall()

        scenario_names = []

        for scenario_name, is_finalized in scenario_rows:

            if scenario_name not in scenario_names:
                scenario_names.append(scenario_name)

            if (
                is_finalized
                and "Finalised" not in scenario_names
            ):
                scenario_names.append("Finalised")

        # =============================
        # 2. Products by scenario
        # From forecast_scenarios because all scenarios exist here
        # =============================
        cur.execute("""
            SELECT DISTINCT
                scenario_name,
                product
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND scenario_name IS NOT NULL
              AND product IS NOT NULL
            ORDER BY scenario_name, product
        """, (
            ta_name,
        ))

        product_rows = cur.fetchall()

        products_by_scenario = {}

        for scenario_name, product in product_rows:

            products_by_scenario.setdefault(scenario_name, [])

            if product not in products_by_scenario[scenario_name]:
                products_by_scenario[scenario_name].append(product)

        # =============================
        # 3. Add Finalised products
        # Latest finalized scenario products
        # =============================
        cur.execute("""
            SELECT scenario_name
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
              AND is_finalized = TRUE
              AND scenario_name IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
        """, (
            ta_name,
        ))

        finalised_row = cur.fetchone()

        if finalised_row:
            finalised_db_scenario = finalised_row[0]

            products_by_scenario["Finalised"] = products_by_scenario.get(
                finalised_db_scenario,
                []
            )

        # =============================
        # 4. Available months
        # =============================
        available_months = get_available_months_from_config(
            cur,
            ta_name
        )

        default_start_date = (
            available_months[0]
            if available_months
            else ""
        )

        default_end_date = (
            available_months[-1]
            if available_months
            else ""
        )

        # =============================
        # 5. Default scenario
        # =============================
        default_scenario_name = (
            "Finalised"
            if "Finalised" in scenario_names
            else "BASE"
            if "BASE" in scenario_names
            else scenario_names[0]
            if scenario_names
            else ""
        )

        # =============================
        # 6. Default product
        # =============================
        default_products = products_by_scenario.get(
            default_scenario_name,
            []
        )

        default_product = (
            "Trodelvy"
            if "Trodelvy" in default_products
            else default_products[0]
            if default_products
            else ""
        )

        # =============================
        # 7. Selected filter from saved preference
        # =============================
        default_filter = {
            "scenario_name": default_scenario_name,
            "indication": "",
            "lot": "",
            "metric": "revenue",
            "product": default_product,
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

            saved_scenario_name = (
                saved_filter.get("scenario_name")
                or default_scenario_name
            )

            saved_indication = (
                saved_filter.get("indication")
                or ""
            )

            selected_scenario = saved_scenario_name

            if selected_scenario and selected_scenario.lower().endswith("_finalised"):
                selected_scenario = "Finalised"

            if selected_scenario not in scenario_names:
                selected_scenario = default_scenario_name

            selected_filter = {
                "scenario_name": selected_scenario or default_scenario_name,
                "indication": saved_indication,
                "lot": saved_filter.get("lot", ""),
                "metric": saved_filter.get("metric", "revenue"),
                "product": saved_filter.get("product") or default_product,
                "start_date": saved_filter.get("start_date") or default_start_date,
                "end_date": saved_filter.get("end_date") or default_end_date
            }

        else:
            selected_filter = default_filter

        return {
            "ta_name": ta_name,
            "scenario_names": scenario_names,
            "products_by_scenario": products_by_scenario,
            "available_months": available_months,
            "selected_filter": selected_filter
        }

    finally:
        cur.close()
        conn.close()

def get_revenue_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)
        is_finalised_view = display_scenario_name.strip().lower() == "finalised"
        product = payload.product
        start_date = payload.start_date
        end_date = payload.end_date

        months = month_range(start_date, end_date)

        # =============================
        # 1. Forecast configuration
        # =============================
        cursor.execute("""
            SELECT config->>'train_end_date'
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (ta_name,))

        config_row = cursor.fetchone()

        if not config_row:
            raise HTTPException(
                status_code=404,
                detail="No forecast configuration found for selected therapy area."
            )

        last_history_month = datetime.strptime(
            config_row[0],
            "%Y-%m-%d"
        ).strftime("%Y-%m-%d")

        # =============================
        # 2. Forecasted demand
        # =============================
        if is_finalised_view:
            cursor.execute("""
                SELECT
                    va.year,
                    va.month,
                    SUM(COALESCE(va.after_adjustment, 0)) AS forecasted_demand,
                    SUM(
                        CASE
                            WHEN COALESCE(va.absolute_adjustment, 0) <> 0
                                THEN COALESCE(va.absolute_adjustment, 0)

                            WHEN COALESCE(va.adjustment_percent, 0) <> 0
                                THEN COALESCE(va.after_adjustment, 0)
                                    * COALESCE(va.adjustment_percent, 0) / 100.0

                            ELSE 0
                        END
                    ) AS adjustment
                FROM raw.vials_assumptions va
                WHERE va.ta_name = %s
                AND va.brand = %s
                AND make_date(va.year, va.month, 1)
                        BETWEEN %s::date AND %s::date
                AND EXISTS (
                    SELECT 1
                    FROM raw.forecast_scenarios nps
                    WHERE LOWER(nps.ta_name) = LOWER(va.ta_name)
                    AND LOWER(nps.scenario_name) = LOWER(va.scenario_name)
                    AND LOWER(nps.indication) = LOWER(va.indication)
                    AND LOWER(nps.lot) = LOWER(va.lot)
                    AND LOWER(nps.metric) = 'nps'
                    AND nps.is_finalized = TRUE
                )
                GROUP BY va.year, va.month
                ORDER BY va.year, va.month
            """, (
                ta_name,
                product,
                start_date,
                end_date
            ))
        else:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    SUM(COALESCE(after_adjustment, 0)) AS forecasted_demand,
                    SUM(
                        CASE
                            WHEN COALESCE(absolute_adjustment, 0) <> 0
                                THEN COALESCE(absolute_adjustment, 0)

                            WHEN COALESCE(adjustment_percent, 0) <> 0
                                THEN COALESCE(after_adjustment, 0)
                                    * COALESCE(adjustment_percent, 0) / 100.0

                            ELSE 0
                        END
                    ) AS adjustment
                FROM raw.vials_assumptions
                WHERE ta_name = %s
                AND scenario_name = %s
                AND brand = %s
                AND make_date(year, month, 1)
                        BETWEEN %s::date AND %s::date
                GROUP BY year, month
                ORDER BY year, month
            """, (
                ta_name,
                db_scenario_name,
                product,
                start_date,
                end_date
            ))

        forecast_map = {}
        adjustment_map = {}

        for year, month, forecasted_demand, adjustment in cursor.fetchall():
            month_key = f"{int(year)}-{int(month):02d}-01"

            forecast_map[month_key] = float(forecasted_demand or 0)
            adjustment_map[month_key] = float(adjustment or 0)

        # =============================
        # 3. Inventory from vial_outputs
        # =============================
        cursor.execute("""
            SELECT
                year,
                month,
                SUM(COALESCE(inventory_vials, 0)) AS inventory
            FROM raw.vials_outputs
            WHERE ta_name = %s
              AND scenario_name = %s
              AND brand = %s
              AND make_date(year, month, 1)
                    BETWEEN %s::date AND %s::date
            GROUP BY year, month
            ORDER BY year, month
        """, (
            ta_name,
            db_scenario_name,
            product,
            start_date,
            end_date
        ))

        inventory_map = {
            f"{int(year)}-{int(month):02d}-01": float(value or 0)
            for year, month, value in cursor.fetchall()
        }

        # =============================
        # 4. Actual demand + WAC + GTN
        # =============================
        cursor.execute("""
            SELECT
                year,
                month,
                actual_demand,
                wac_price_usd,
                gtn
            FROM raw.fact_demand_pricing
            WHERE ta_name = %s
              AND brand = %s
              AND make_date(year, month, 1) <= %s::date
            ORDER BY year, month
        """, (
            ta_name,
            product,
            end_date
        ))

        pricing_rows = cursor.fetchall()

        pricing_map = {
            f"{int(year)}-{int(month):02d}-01": {
                "actual_demand": float(actual_demand or 0),
                "wac_price_usd": float(wac_price_usd or 0),
                "gtn": float(gtn or 0)
            }
            for year, month, actual_demand, wac_price_usd, gtn in pricing_rows
        }

        if not pricing_map:
            raise HTTPException(
                status_code=404,
                detail="No demand pricing data found for selected product."
            )
        cursor.execute("""
            SELECT
                month_date,
                final_factor,
                wac_price_usd,
                price_increase,
                gtn
            FROM raw.revenue_outputs
            WHERE ta_name = %s
            AND scenario_name = %s
            AND brand = %s
            AND month_date BETWEEN %s::date AND %s::date
        """, (
            ta_name,
            display_scenario_name,
            product,
            start_date,
            end_date
        ))

        override_map = {
            row[0].strftime("%Y-%m-%d"): {
                "final_factor": float(row[1]) if row[1] is not None else None,
                "wac_price_usd": float(row[2]) if row[2] is not None else None,
                "price_increase": float(row[3]) if row[3] is not None else None,
                "gtn": float(row[4]) if row[4] is not None else None
            }
            for row in cursor.fetchall()
        }
        # =============================
        # 5. Last known WAC / GTN up to history end
        # =============================
        last_wac_price = 0
        last_gtn = 0

        for month_key in sorted(pricing_map.keys()):
            if month_key <= last_history_month:
                last_wac_price = pricing_map[month_key]["wac_price_usd"]
                last_gtn = pricing_map[month_key]["gtn"]

        # =============================
        # 6. Build response rows
        # =============================
        forecasted_demand_values = []
        adjustment_values = []
        actual_demand_values = []
        derived_factor_values = []
        final_factor_values = []
        final_demand_values = []
        inventory_values = []
        wac_price_values = []
        price_increase_values = []
        gtn_values = []
        net_price_values = []
        net_demand_revenue_values = []
        net_revenue_values = []

        previous_wac_price = None
        historical_derived_factors = []

        for month_str in months:

            forecasted_demand = forecast_map.get(month_str, 0)
            inventory = inventory_map.get(month_str, 0)

            is_history = month_str <= last_history_month
            pricing = pricing_map.get(month_str)

            if is_history:
                actual_demand = pricing["actual_demand"] if pricing else 0
                wac_price = pricing["wac_price_usd"] if pricing else last_wac_price
                gtn = pricing["gtn"] if pricing else last_gtn

                if actual_demand > 0 and forecasted_demand > 0:
                    derived_factor = actual_demand / forecasted_demand
                    historical_derived_factors.append(derived_factor)
                else:
                    last_3 = historical_derived_factors[-3:]
                    derived_factor = (
                        sum(last_3) / len(last_3)
                        if last_3
                        else 1
                    )

                last_wac_price = wac_price
                last_gtn = gtn

            else:
                actual_demand = 0
                wac_price = last_wac_price
                gtn = last_gtn

                last_3 = historical_derived_factors[-3:]
                derived_factor = (
                    sum(last_3) / len(last_3)
                    if last_3
                    else 1
                )

            # Price increase derived from WAC movement
            price_increase = 0

            # previous_wac_price = wac_price

            adjustment = adjustment_map.get(month_str, 0)
            override = override_map.get(month_str, {})

            final_factor = (
                override.get("final_factor")
                if override.get("final_factor") is not None
                else 1
            )

            price_increase = (
                override.get("price_increase")
                if override.get("price_increase") is not None
                else 0
            )

            if override.get("gtn") is not None:
                gtn = override["gtn"]

            if override.get("wac_price_usd") is not None:
                wac_price = override["wac_price_usd"]

            final_demand = (
                forecasted_demand + adjustment
            ) * final_factor

            net_price = wac_price * (1 - gtn / 100.0)

            net_demand_revenue = final_demand * net_price

            net_revenue = (
                final_demand + inventory
            ) * net_price
            cursor.execute("""
                INSERT INTO raw.revenue_outputs (
                    ta_name,
                    scenario_name,
                    brand,
                    month_date,
                    forecasted_demand,
                    adjustment,
                    actual_demand,
                    derived_factor,
                    final_factor,
                    final_demand,
                    inventory_vials,
                    wac_price_usd,
                    price_increase,
                    gtn,
                    net_price,
                    net_demand_revenue,
                    net_revenue
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (
                    ta_name,
                    scenario_name,
                    brand,
                    month_date
                )
                DO UPDATE SET
                    forecasted_demand = EXCLUDED.forecasted_demand,
                    adjustment = EXCLUDED.adjustment,
                    actual_demand = EXCLUDED.actual_demand,
                    derived_factor = EXCLUDED.derived_factor,
                    final_factor = EXCLUDED.final_factor,
                    final_demand = EXCLUDED.final_demand,
                    inventory_vials = EXCLUDED.inventory_vials,
                    wac_price_usd = EXCLUDED.wac_price_usd,
                    price_increase = EXCLUDED.price_increase,
                    gtn = EXCLUDED.gtn,
                    net_price = EXCLUDED.net_price,
                    net_demand_revenue = EXCLUDED.net_demand_revenue,
                    net_revenue = EXCLUDED.net_revenue,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                ta_name,
                display_scenario_name,
                product,
                month_str,
                forecasted_demand,
                adjustment,
                actual_demand,
                derived_factor,
                final_factor,
                final_demand,
                inventory,
                wac_price,
                price_increase,
                gtn,
                net_price,
                net_demand_revenue,
                net_revenue
            ))
            forecasted_demand_values.append(round(forecasted_demand))
            adjustment_values.append(round(adjustment))
            actual_demand_values.append(round(actual_demand))
            derived_factor_values.append(round(derived_factor, 2))
            final_factor_values.append(round(final_factor, 2))
            final_demand_values.append(round(final_demand))
            inventory_values.append(round(inventory, 1))
            wac_price_values.append(round(wac_price, 2))
            price_increase_values.append(round(price_increase, 2))
            gtn_values.append(round(gtn, 2))
            net_price_values.append(round(net_price, 2))
            net_demand_revenue_values.append(round(net_demand_revenue))
            net_revenue_values.append(round(net_revenue))

        # =============================
        # 7. Forecast start index
        # =============================
        forecast_start_index = len(months)

        for idx, month_str in enumerate(months):
            if month_str > last_history_month:
                forecast_start_index = idx
                break

        # =============================
        # 8. Save selected filter
        # =============================
        cursor.execute("""
            UPDATE raw.user_filter_preferences
            SET
                scenario_name = %s,
                product = %s,
                start_date = %s,
                end_date = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
              AND ta_name = %s
        """, (
            display_scenario_name,
            product,
            start_date,
            end_date,
            "system",
            ta_name
        ))

        conn.commit()

        return {
            "therapy_area": ta_name,
            "scenario_name": display_scenario_name,
            "product": product,
            "start_date": start_date,
            "end_date": end_date,
            "chart": {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "series": [
                    {
                        "scenario": display_scenario_name,
                        "label": "Net Revenue",
                        "train_values": net_revenue_values[:forecast_start_index],
                        "forecast_values": net_revenue_values[forecast_start_index:]
                    }
                ]
            },
            "table": {
                "months": months,
                "rows": [
                    {
                        "metric": "Forecasted Demand",
                        "values": forecasted_demand_values
                    },
                    {
                        "metric": "Adjustment",
                        "values": adjustment_values
                    },
                    {
                        "metric": "Actual Demand",
                        "values": actual_demand_values
                    },
                    {
                        "metric": "Derived Factor",
                        "values": derived_factor_values
                    },
                    {
                        "metric": "Final Factor",
                        "values": final_factor_values
                    },
                    {
                        "metric": "Final Demand",
                        "values": final_demand_values
                    },
                    {
                        "metric": "Inventory",
                        "values": inventory_values
                    },
                    {
                        "metric": "WAC Price ($)",
                        "values": wac_price_values
                    },
                    {
                        "metric": "Price Increase (%)",
                        "values": price_increase_values
                    },
                    {
                        "metric": "GTN (%)",
                        "values": gtn_values
                    },
                    {
                        "metric": "Net Price",
                        "values": net_price_values
                    },
                    {
                        "metric": "Net Demand Revenue",
                        "values": net_demand_revenue_values
                    },
                    {
                        "metric": "Net Revenue",
                        "values": net_revenue_values
                    }
                ]
            }
        }

    finally:
        cursor.close()
        conn.close()

def get_row_values(rows, metric_name, months, default=0):
    for row in rows:

        if isinstance(row, dict):
            metric = row.get("metric")
            values = row.get("values", [])
        else:
            metric = row.metric
            values = row.values

        if metric == metric_name:
            return [
                float(values[i] or 0)
                if i < len(values)
                else default
                for i in range(len(months))
            ]

    return [default for _ in months]

def edit_revenue_service(payload):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ta_name = payload.ta_name
        display_scenario_name = payload.scenario_name.strip()
        db_scenario_name = clean_scenario_name(display_scenario_name)
        is_finalised_view = display_scenario_name.strip().lower() == "finalised"
        product = payload.product
        months = payload.months
        rows = payload.rows or []

        start_date = months[0]
        end_date = months[-1]

        # =============================
        # 1. Forecast configuration
        # =============================
        cursor.execute("""
            SELECT config->>'train_end_date'
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (ta_name,))

        config_row = cursor.fetchone()

        if not config_row:
            raise HTTPException(
                status_code=404,
                detail="No forecast configuration found for selected therapy area."
            )

        last_history_month = datetime.strptime(
            config_row[0],
            "%Y-%m-%d"
        ).strftime("%Y-%m-%d")

        # =============================
        # 2. Forecasted demand from DB
        # =============================
        if is_finalised_view:
            cursor.execute("""
                SELECT
                    va.year,
                    va.month,
                    SUM(COALESCE(va.after_adjustment, 0)) AS forecasted_demand
                FROM raw.vials_assumptions va
                WHERE va.ta_name = %s
                AND va.brand = %s
                AND make_date(va.year, va.month, 1)
                        BETWEEN %s::date AND %s::date
                AND EXISTS (
                    SELECT 1
                    FROM raw.forecast_scenarios nps
                    WHERE LOWER(nps.ta_name) = LOWER(va.ta_name)
                    AND LOWER(nps.scenario_name) = LOWER(va.scenario_name)
                    AND LOWER(nps.indication) = LOWER(va.indication)
                    AND LOWER(nps.lot) = LOWER(va.lot)
                    AND LOWER(nps.metric) = 'nps'
                    AND nps.is_finalized = TRUE
                )
                GROUP BY va.year, va.month
                ORDER BY va.year, va.month
            """, (
                ta_name,
                product,
                start_date,
                end_date
            ))
        else:
            cursor.execute("""
                SELECT
                    year,
                    month,
                    SUM(COALESCE(after_adjustment, 0)) AS forecasted_demand
                FROM raw.vials_assumptions
                WHERE ta_name = %s
                AND scenario_name = %s
                AND brand = %s
                AND make_date(year, month, 1)
                        BETWEEN %s::date AND %s::date
                GROUP BY year, month
                ORDER BY year, month
            """, (
                ta_name,
                db_scenario_name,
                product,
                start_date,
                end_date
            ))

        forecast_map = {
            f"{int(year)}-{int(month):02d}-01": float(value or 0)
            for year, month, value in cursor.fetchall()
        }

        # =============================
        # 3. Inventory from vial_outputs
        # =============================
        cursor.execute("""
            SELECT
                year,
                month,
                SUM(COALESCE(inventory_vials, 0)) AS inventory
            FROM raw.vials_outputs
            WHERE ta_name = %s
              AND scenario_name = %s
              AND brand = %s
              AND make_date(year, month, 1)
                    BETWEEN %s::date AND %s::date
            GROUP BY year, month
            ORDER BY year, month
        """, (
            ta_name,
            db_scenario_name,
            product,
            start_date,
            end_date
        ))

        inventory_map = {
            f"{int(year)}-{int(month):02d}-01": float(value or 0)
            for year, month, value in cursor.fetchall()
        }

        # =============================
        # 4. Actual demand + default pricing from DB
        # =============================
        cursor.execute("""
            SELECT
                year,
                month,
                actual_demand,
                wac_price_usd,
                gtn
            FROM raw.fact_demand_pricing
            WHERE ta_name = %s
              AND brand = %s
              AND make_date(year, month, 1) <= %s::date
            ORDER BY year, month
        """, (
            ta_name,
            product,
            end_date
        ))

        pricing_rows = cursor.fetchall()

        pricing_map = {
            f"{int(year)}-{int(month):02d}-01": {
                "actual_demand": float(actual_demand or 0),
                "wac_price_usd": float(wac_price_usd or 0),
                "gtn": float(gtn or 0)
            }
            for year, month, actual_demand, wac_price_usd, gtn in pricing_rows
        }

        if not pricing_map:
            raise HTTPException(
                status_code=404,
                detail="No demand pricing data found for selected product."
            )

        # =============================
        # 5. Editable rows from FE
        # =============================
        final_factor_input = get_row_values(
            rows,
            "Final Factor",
            months,
            default=1
        )

        wac_price_input = get_row_values(
            rows,
            "WAC Price ($)",
            months,
            default=0
        )

        price_increase_input = get_row_values(
            rows,
            "Price Increase (%)",
            months,
            default=0
        )

        gtn_input = get_row_values(
            rows,
            "GTN (%)",
            months,
            default=0
        )

        # =============================
        # 6. Build response rows
        # =============================
        forecasted_demand_values = []
        adjustment_values = []
        actual_demand_values = []
        derived_factor_values = []
        final_factor_values = []
        final_demand_values = []
        inventory_values = []
        wac_price_values = []
        price_increase_values = []
        gtn_values = []
        net_price_values = []
        net_demand_revenue_values = []
        net_revenue_values = []

        historical_derived_factors = []

        previous_wac_price = None

        for idx, month_str in enumerate(months):

            forecasted_demand = forecast_map.get(month_str, 0)
            inventory = inventory_map.get(month_str, 0)

            pricing = pricing_map.get(month_str)

            actual_demand = (
                pricing["actual_demand"]
                if pricing
                else 0
            )

            # =============================
            # Derived Factor
            # If actual_demand is 0, use last 3 valid avg
            # =============================
            if actual_demand > 0 and forecasted_demand > 0:
                derived_factor = actual_demand / forecasted_demand
                historical_derived_factors.append(derived_factor)
            else:
                last_3 = historical_derived_factors[-3:]
                derived_factor = (
                    sum(last_3) / len(last_3)
                    if last_3
                    else 1
                )

            adjustment = 0
            final_factor = final_factor_input[idx]

            # =============================
            # WAC logic
            # Month 1 uses FE WAC/base WAC
            # Future months use price increase on previous month WAC
            # =============================
            if idx == 0:
                wac_price = wac_price_input[idx]

                if not wac_price:
                    wac_price = (
                        pricing["wac_price_usd"]
                        if pricing
                        else 0
                    )

            else:
                price_increase = price_increase_input[idx]

                wac_price = previous_wac_price * (
                    1 + price_increase / 100.0
                )

            previous_wac_price = wac_price

            price_increase = price_increase_input[idx]
            gtn = gtn_input[idx]

            if not gtn and pricing:
                gtn = pricing["gtn"]

            final_demand = (
                forecasted_demand + adjustment
            ) * final_factor

            net_price = wac_price * (1 - gtn / 100.0)

            net_demand_revenue = final_demand * net_price

            net_revenue = (
                final_demand + inventory
            ) * net_price
            cursor.execute("""
                INSERT INTO raw.revenue_outputs (
                    ta_name,
                    scenario_name,
                    brand,
                    month_date,
                    forecasted_demand,
                    adjustment,
                    actual_demand,
                    derived_factor,
                    final_factor,
                    final_demand,
                    inventory_vials,
                    wac_price_usd,
                    price_increase,
                    gtn,
                    net_price,
                    net_demand_revenue,
                    net_revenue
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (
                    ta_name,
                    scenario_name,
                    brand,
                    month_date
                )
                DO UPDATE SET
                    forecasted_demand = EXCLUDED.forecasted_demand,
                    adjustment = EXCLUDED.adjustment,
                    actual_demand = EXCLUDED.actual_demand,
                    derived_factor = EXCLUDED.derived_factor,
                    final_factor = EXCLUDED.final_factor,
                    final_demand = EXCLUDED.final_demand,
                    inventory_vials = EXCLUDED.inventory_vials,
                    wac_price_usd = EXCLUDED.wac_price_usd,
                    price_increase = EXCLUDED.price_increase,
                    gtn = EXCLUDED.gtn,
                    net_price = EXCLUDED.net_price,
                    net_demand_revenue = EXCLUDED.net_demand_revenue,
                    net_revenue = EXCLUDED.net_revenue,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                ta_name,
                display_scenario_name,
                product,
                month_str,
                forecasted_demand,
                adjustment,
                actual_demand,
                derived_factor,
                final_factor,
                final_demand,
                inventory,
                wac_price,
                price_increase,
                gtn,
                net_price,
                net_demand_revenue,
                net_revenue
            ))
            forecasted_demand_values.append(round(forecasted_demand))
            adjustment_values.append(round(adjustment))
            actual_demand_values.append(round(actual_demand))
            derived_factor_values.append(round(derived_factor, 2))
            final_factor_values.append(round(final_factor, 2))
            final_demand_values.append(round(final_demand))
            inventory_values.append(round(inventory, 1))
            wac_price_values.append(round(wac_price, 2))
            price_increase_values.append(round(price_increase, 2))
            gtn_values.append(round(gtn, 2))
            net_price_values.append(round(net_price, 2))
            net_demand_revenue_values.append(round(net_demand_revenue))
            net_revenue_values.append(round(net_revenue))

        # =============================
        # 7. Forecast start index
        # =============================
        forecast_start_index = len(months)

        for idx, month_str in enumerate(months):
            if month_str > last_history_month:
                forecast_start_index = idx
                break
        
        conn.commit()
        return {
            "therapy_area": ta_name,
            "scenario_name": display_scenario_name,
            "product": product,
            "start_date": start_date,
            "end_date": end_date,
            "chart": {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "series": [
                    {
                        "scenario": display_scenario_name,
                        "label": "Net Revenue",
                        "train_values": net_revenue_values[:forecast_start_index],
                        "forecast_values": net_revenue_values[forecast_start_index:]
                    }
                ]
            },
            "table": {
                "months": months,
                "rows": [
                    {
                        "metric": "Forecasted Demand",
                        "values": forecasted_demand_values
                    },
                    {
                        "metric": "Adjustment",
                        "values": adjustment_values
                    },
                    {
                        "metric": "Actual Demand",
                        "values": actual_demand_values
                    },
                    {
                        "metric": "Derived Factor",
                        "values": derived_factor_values
                    },
                    {
                        "metric": "Final Factor",
                        "values": final_factor_values
                    },
                    {
                        "metric": "Final Demand",
                        "values": final_demand_values
                    },
                    {
                        "metric": "Inventory",
                        "values": inventory_values
                    },
                    {
                        "metric": "WAC Price ($)",
                        "values": wac_price_values
                    },
                    {
                        "metric": "Price Increase (%)",
                        "values": price_increase_values
                    },
                    {
                        "metric": "GTN (%)",
                        "values": gtn_values
                    },
                    {
                        "metric": "Net Price",
                        "values": net_price_values
                    },
                    {
                        "metric": "Net Demand Revenue",
                        "values": net_demand_revenue_values
                    },
                    {
                        "metric": "Net Revenue",
                        "values": net_revenue_values
                    }
                ]
            }
        }

    finally:
        cursor.close()
        conn.close()