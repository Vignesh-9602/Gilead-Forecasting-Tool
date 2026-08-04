from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor
from copy import deepcopy
from datetime import date, datetime
from app.hiv_prep.routes.output_models import *
from app.hiv_prep.routes.market_events import generate_months
from app.hiv_prep.services.market_event_helpers import *
from app.hiv_prep.services.calculation_tree_market_events import *
from app.hiv_prep.services.generic_builders_market_events import *
from app.hiv_prep.services.edit_helpers import *
from app.hiv_prep.services.output_helpers import *


router = APIRouter()

from app.db.connection import get_connection

router = APIRouter(prefix="/api/hiv_prep", tags=["outputs_hiv_prep"])

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
            FROM raw_hiv_prep.user_configurations
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
                FROM raw_hiv_prep.forecast_outputs
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
            FROM raw_hiv_prep.forecast_outputs
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
            FROM raw_hiv_prep.forecast_outputs
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

#apply filters

@router.post("/output-screen/apply-filters")
def apply_output_screen_filters(
    payload: ApplyOutputScreenFiltersRequest,
):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        ta_name = payload.ta_name.strip()

        if not ta_name:
            raise HTTPException(
                status_code=400,
                detail="ta_name is required.",
            )

        selected_filter = payload.selected_filter

        start_date = selected_filter.start_date
        end_date = selected_filter.end_date

        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail=(
                    "start_date cannot be greater "
                    "than end_date."
                ),
            )

        selected_markets = normalize_dimension_filter(
            selected_filter.markets
        )

        selected_products = normalize_dimension_filter(
            selected_filter.products
        )

        available_scenarios = get_scenarios(
            cursor,
            ta_name,
        )

        if not available_scenarios:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No scenarios found for TA "
                    f"{ta_name!r}."
                ),
            )

        selected_scenarios = resolve_selected_scenarios(
            requested_scenarios=(
                selected_filter.scenario_names
            ),
            available_scenarios=(
                available_scenarios
            ),
        )

        # =================================================
        # Build and merge output tabs
        # =================================================

        output_tabs = {}

        for scenario in selected_scenarios:
            market_analysis = build_scenario_market_analysis(
                cursor,
                ta_name,
                scenario,
                start_date,
                end_date,
                selected_markets,
                selected_products,
            )

            merge_total_market_volume(
                output_tabs=output_tabs,
                market_analysis=market_analysis,
                scenario_name=scenario,
            )

            merge_market_distribution(
                output_tabs=output_tabs,
                market_analysis=market_analysis,
                scenario_name=scenario,
            )

            merge_product_distribution(
                output_tabs=output_tabs,
                market_analysis=market_analysis,
                scenario_name=scenario,
            )

            merge_market_product(
                output_tabs=output_tabs,
                market_analysis=market_analysis,
                scenario_name=scenario,
            )

            merge_product_market(
                output_tabs,
                market_analysis,
                scenario,
            )

        return {
            "ta_name": ta_name,

            "selected_filter": {
                "scenario_names": selected_scenarios,
                "start_date": start_date,
                "end_date": end_date,
                "markets": selected_markets,
                "products": selected_products,
            },

            "selected_metric":
                payload.selected_metric,

            "selected_view":
                payload.selected_view,

            "available_scenarios":
                available_scenarios,

            "metric_filters": [
                {
                    "label": "Market Volume",
                    "value": "market_volume",
                },
                {
                    "label": "Market Share",
                    "value": "market_share",
                },
            ],

            "view_options": [
                {
                    "label": "Monthly",
                    "value": "monthly",
                },
                {
                    "label": "Yearly",
                    "value": "yearly",
                },
            ],

            "output_tabs": output_tabs,
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(
            "[OUTPUT SCREEN APPLY FILTERS ERROR]",
            type(exc).__name__,
            str(exc),
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()