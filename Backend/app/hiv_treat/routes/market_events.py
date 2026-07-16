from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor
from app.hiv_treat.routes.market_events_models import *
from app.hiv_treat.services.market_event_helpers import *
from app.hiv_treat.services.calculation_tree_market_events import *
from app.hiv_treat.services.generic_builders_market_events import *
from app.hiv_treat.services.edit_helpers import *

router = APIRouter()

from app.db.connection import get_connection

router = APIRouter(prefix="/api/hiv_treat", tags=["hiv_treat_market_events"])


def generate_months(start_date: date, end_date: date):
    """
    Generate a list of months between start_date and end_date (inclusive).
    Format: YYYY-MM-01
    """
    months = []

    current = start_date.replace(day=1)
    end = end_date.replace(day=1)

    while current <= end:
        months.append(current.strftime("%Y-%m-%d"))

        if current.month == 12:
            current = current.replace(
                year=current.year + 1,
                month=1
            )
        else:
            current = current.replace(
                month=current.month + 1
            )

    return months


@router.get("/get_market_event_filters")
def get_market_event_filters(
    ta_name: str,
    db=Depends(get_connection)
):
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        user_id = "system"

        # Selected Filter (System Configuration)
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

        # --------------------------------------------------
        # Available Scenarios
        # --------------------------------------------------
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

        # Available Markets
        cursor.execute(
            """
            SELECT DISTINCT market
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
            AND market IS NOT NULL
            AND UPPER(TRIM(market)) <> 'ALL'
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
            AND product IS NOT NULL
            AND UPPER(TRIM(product)) <> 'ALL'
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
        # Generated from configured start & end dates
        available_months = generate_months(
            config["start_date"],
            config["end_date"]
        )

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

#apply filter

@router.post("/apply_market_event_filters")
def apply_market_event_filters(
    payload: ApplyFiltersRequest,
    db=Depends(get_connection),
):

    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:

        # -----------------------------------------
        # Load metadata
        # -----------------------------------------

        metadata = load_metadata(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=payload.selected_filter.scenario_name,
            start_date=payload.selected_filter.start_date,
            end_date=payload.selected_filter.end_date,
        )

        # -----------------------------------------
        # Load forecast outputs
        # -----------------------------------------

        metrics = load_forecast_outputs(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=payload.selected_filter.scenario_name,
        )

        # -----------------------------------------
        # Build calculation tree
        # -----------------------------------------

        tree = build_calculation_tree(metrics)

        tree = filter_tree_by_date(
            tree,
            payload.selected_filter.start_date,
            payload.selected_filter.end_date,
        )

        # -----------------------------------------
        # Build Events
        # -----------------------------------------

        overall_event = build_overall_event(tree)

        market_event = build_market_event(tree)

        product_event = build_product_event(tree)

        # -----------------------------------------
        # Response
        # -----------------------------------------

        print(metadata)
        print(type(metadata))

        return {

            "ta_name": payload.ta_name,

            "available_scenarios": metadata["available_scenarios"],

            "available_months": metadata["available_months"],

            "selected_filter": payload.selected_filter.model_dump(),

            "metric_filters": [
                {
                    "label": "Market Share",
                    "value": "market_share",
                },
                {
                    "label": "Overall Market Volume",
                    "value": "market_volume",
                },
            ],

            "event_tabs": {

                "overall_event": overall_event,

                "market_event": market_event,

                "product_event": product_event,

            },
        }

    finally:
        cursor.close()

#edits
@router.post("/edit_save")
def edit_save(
    payload: EditSaveRequest,
    db=Depends(get_connection),
):
    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )

    try:
        scenario_name = payload.selected_filter.scenario_name
        selected_filter = payload.selected_filter.model_dump()

        original_metrics = load_forecast_outputs(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        if not original_metrics.get("market_share"):
            raise HTTPException(
                status_code=404,
                detail="No market-share forecast data was found",
            )

        if not original_metrics.get("market_volume"):
            raise HTTPException(
                status_code=404,
                detail="No market-volume forecast data was found",
            )

        tree = build_calculation_tree(original_metrics)

        edited_indexes = resolve_edited_indexes(
            tree,
            payload,
        )

        validate_edited_rows(
            payload.edited_table_rows,
            len(payload.edited_headers),
        )

        matrix = build_market_product_volume_matrix(tree)

        if payload.selected_tab == "market_event":
            apply_market_event_edits(
                tree,
                matrix,
                payload,
                edited_indexes,
            )
        else:
            apply_product_event_edits(
                tree,
                matrix,
                payload,
                edited_indexes,
            )

        apply_matrix_to_tree(
            tree,
            matrix,
            edited_indexes,
        )

        recompute_tree(
            tree,
            edited_indexes,
        )

        save_tree_to_forecast_outputs(
            cursor,
            tree=tree,
            original_metrics=original_metrics,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        db.commit()

        return build_apply_filters_response(
            cursor=cursor,
            ta_name=payload.ta_name,
            selected_filter=selected_filter,
        )

    except HTTPException:
        db.rollback()
        raise

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Unable to save forecast edits: {exc}",
        ) from exc

    finally:
        cursor.close()