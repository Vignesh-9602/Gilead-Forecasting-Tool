from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor

from app.db.connection import get_connection

router = APIRouter(prefix="/api/hiv_treat", tags=["hiv_treat_market_events"])


@router.get("/get_market_event_filters")
def get_market_event_filters(
    ta_name: str,
    db=Depends(get_connection)
):
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        user_id = "system"

        # Selected Filter
        cursor.execute(
            """
            SELECT
                scenario_name,
                market,
                product,
                start_date,
                end_date
            FROM raw_hiv_treat.user_configurations
            WHERE user_id = %s
              AND ta_name = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, ta_name),
        )

        config = cursor.fetchone()

        if not config:
            raise HTTPException(
                status_code=404,
                detail="No configuration found."
            )

        # Available Scenarios
        cursor.execute(
            """
            SELECT DISTINCT scenario_name
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
            ORDER BY scenario_name
            """,
            (ta_name,),
        )

        scenarios = [
            row["scenario_name"]
            for row in cursor.fetchall()
            if row["scenario_name"]
        ]

        # -----------------------------
        # Available Markets
        # -----------------------------
        cursor.execute(
            """
            SELECT DISTINCT market
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
            ORDER BY market
            """,
            (ta_name,),
        )

        markets = [
            row["market"]
            for row in cursor.fetchall()
            if row["market"]
        ]

        # Available Products
        cursor.execute(
            """
            SELECT DISTINCT product
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
            ORDER BY product
            """,
            (ta_name,),
        )

        products = [
            row["product"]
            for row in cursor.fetchall()
            if row["product"]
        ]

        # Available Months
        cursor.execute(
            """
            SELECT DISTINCT
                make_date(year, month, 1) AS month_date
            FROM raw_hiv_treat.volume
            WHERE ta = %s
            ORDER BY month_date
            """,
            (ta_name,),
        )

        available_months = [
            row["month_date"].strftime("%Y-%m-%d")
            for row in cursor.fetchall()
        ]

        return {
            "ta_name": ta_name,
            "available_scenarios": scenarios,
            "markets": markets,
            "products": products,
            "available_months": available_months,
            "selected_filter": {
                "scenario_name": config["scenario_name"],
                "markets": [config["market"]] if config["market"] else [],
                "products": [config["product"]] if config["product"] else [],
                "start_date": config["start_date"].strftime("%Y-%m-%d")
                if config["start_date"]
                else None,
                "end_date": config["end_date"].strftime("%Y-%m-%d")
                if config["end_date"]
                else None,
            },
        }

    finally:
        cursor.close()