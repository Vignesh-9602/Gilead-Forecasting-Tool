from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor
from app.hiv_treat.routes.output_models import *
from app.hiv_treat.routes.market_events import generate_months


router = APIRouter()

from app.db.connection import get_connection

router = APIRouter(prefix="/api/hiv_treat", tags=["outputs"])

def format_date(value):
    if value is None:
        return None

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    return str(value)

@router.get("/get_output_screen_filters")
def get_output_screen_filters(
    ta_name: str,
    db=Depends(get_connection),
):
    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )

    try:
        user_id = "system"

        # --------------------------------------------------
        # Selected Filter
        # Latest saved system configuration
        # --------------------------------------------------

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
            (
                user_id,
                ta_name,
            ),
        )

        config = cursor.fetchone()

        if not config:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No output screen configuration "
                    "was found for the selected TA."
                ),
            )

        # --------------------------------------------------
        # Available Scenarios
        # BASE first, then alphabetical
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT scenario_name
            FROM (
                SELECT DISTINCT
                    TRIM(scenario_name) AS scenario_name
                FROM raw_hiv_treat.forecast_outputs
                WHERE ta_name = %s
                  AND scenario_name IS NOT NULL
                  AND TRIM(scenario_name) <> ''
            ) AS scenario_list
            ORDER BY
                CASE
                    WHEN UPPER(scenario_name) = 'BASE'
                    THEN 0
                    ELSE 1
                END,
                scenario_name
            """,
            (ta_name,),
        )

        scenarios = [
            row["scenario_name"]
            for row in cursor.fetchall()
            if row.get("scenario_name")
        ]

        # --------------------------------------------------
        # Available Markets
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT DISTINCT
                TRIM(market) AS market
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND market IS NOT NULL
              AND TRIM(market) <> ''
              AND UPPER(TRIM(market)) <> 'ALL'
            ORDER BY market
            """,
            (ta_name,),
        )

        markets = [
            row["market"]
            for row in cursor.fetchall()
            if row.get("market")
        ]

        # --------------------------------------------------
        # Available Products
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT DISTINCT
                TRIM(product) AS product
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND product IS NOT NULL
              AND TRIM(product) <> ''
              AND UPPER(TRIM(product)) <> 'ALL'
            ORDER BY product
            """,
            (ta_name,),
        )

        products = [
            row["product"]
            for row in cursor.fetchall()
            if row.get("product")
        ]

        # --------------------------------------------------
        # Available Months
        # --------------------------------------------------

        available_months = generate_months(
            config.get("start_date"),
            config.get("end_date"),
        )

        # --------------------------------------------------
        # Selected values
        # --------------------------------------------------

        selected_scenario = (
            str(config.get("scenario_name")).strip()
            if config.get("scenario_name")
            else "BASE"
        )

        selected_market = config.get("market")
        selected_product = config.get("product")

        selected_markets = (
            [str(selected_market).strip()]
            if selected_market
            and str(selected_market).strip().upper() != "ALL"
            else []
        )

        selected_products = (
            [str(selected_product).strip()]
            if selected_product
            and str(selected_product).strip().upper() != "ALL"
            else []
        )

        start_date = format_date(
            config.get("start_date")
        )

        end_date = format_date(
            config.get("end_date")
        )

        # --------------------------------------------------
        # Response
        # --------------------------------------------------

        return {
            "ta_name": ta_name,
            "available_scenarios": scenarios,
            "markets": markets,
            "products": products,
            "available_months": available_months,
            "selected_filter": {
                "scenario_names": [
                    selected_scenario
                ],
                "markets": selected_markets,
                "products": selected_products,
                "start_date": start_date,
                "end_date": end_date,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        cursor.close()