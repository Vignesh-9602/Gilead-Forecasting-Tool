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

from pprint import pprint

from fastapi import Depends, HTTPException



@router.post("/apply_market_event_filters")
def apply_market_event_filters(
    payload: ApplyFiltersRequest,
    db=Depends(get_connection),
):
    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )

    try:
        selected_filter = payload.selected_filter

        scenario_name = (
            selected_filter.scenario_name
            or ""
        ).strip()

        print("\n" + "=" * 90)
        print("APPLY MARKET EVENT FILTERS")
        print("=" * 90)

        # =====================================================
        # Request
        # =====================================================

        print("\n[REQUEST]")
        print("TA NAME:", repr(payload.ta_name))
        print("SCENARIO:", repr(scenario_name))
        print(
            "START DATE:",
            repr(selected_filter.start_date),
        )
        print(
            "END DATE:",
            repr(selected_filter.end_date),
        )
        print(
            "SELECTED MARKETS:",
            selected_filter.markets,
        )
        print(
            "SELECTED PRODUCTS:",
            selected_filter.products,
        )

        # Warn about placeholder date values.
        if str(
            selected_filter.start_date
        ).strip().lower() == "string":
            print(
                "WARNING: start_date contains the literal "
                "value 'string'."
            )

        if str(
            selected_filter.end_date
        ).strip().lower() == "string":
            print(
                "WARNING: end_date contains the literal "
                "value 'string'."
            )

        # =====================================================
        # 1. Metadata
        # =====================================================

        print("\n[1] LOADING METADATA")

        metadata = load_metadata(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
            start_date=selected_filter.start_date,
            end_date=selected_filter.end_date,
        )

        print(
            "METADATA TYPE:",
            type(metadata).__name__,
        )
        print("METADATA:")
        pprint(metadata)

        if not isinstance(metadata, dict):
            raise HTTPException(
                status_code=500,
                detail=(
                    "load_metadata() must return a dictionary. "
                    f"Received {type(metadata).__name__}."
                ),
            )

        available_scenarios = metadata.get(
            "available_scenarios",
            [],
        )

        print(
            "AVAILABLE SCENARIOS:",
            available_scenarios,
        )

        normalized_available_scenarios = {
            str(value).strip().lower()
            for value in available_scenarios
            if value is not None
        }

        if (
            scenario_name
            and scenario_name.lower()
            not in normalized_available_scenarios
        ):
            print(
                "WARNING: Selected scenario was not found "
                "in available_scenarios."
            )

        # =====================================================
        # 2. Forecast outputs
        # =====================================================

        print("\n[2] LOADING FORECAST OUTPUTS")

        metrics = load_forecast_outputs(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        debug_forecast_outputs(
            metrics=metrics,
        )

        if not metrics:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No forecast output data found for "
                    f"scenario {scenario_name!r}."
                ),
            )

        # =====================================================
        # 3. Build tree
        # =====================================================

        print("\n[3] BUILDING CALCULATION TREE")

        # Keep metrics in its original structure.
        # build_calculation_tree() already expects this format.
        tree = build_calculation_tree(
            metrics
        )

        debug_tree_summary(
            tree=tree,
            stage="AFTER BUILD",
        )

        # =====================================================
        # 4. Date filtering
        # =====================================================

        print("\n[4] FILTERING TREE BY DATE")

        tree = filter_tree_by_date(
            tree,
            selected_filter.start_date,
            selected_filter.end_date,
        )

        debug_tree_summary(
            tree=tree,
            stage="AFTER DATE FILTER",
        )

        # =====================================================
        # 5. Build events
        # =====================================================

        print("\n[5] BUILDING EVENTS")

        overall_event = build_overall_event(
            tree
        )

        debug_event_summary(
            event_name="overall_event",
            event=overall_event,
        )

        market_event = build_market_event(
            tree
        )

        debug_event_summary(
            event_name="market_event",
            event=market_event,
        )

        product_event = build_product_event(
            tree
        )

        debug_event_summary(
            event_name="product_event",
            event=product_event,
        )

        # =====================================================
        # 6. Response
        # =====================================================

        response = {
            "ta_name": payload.ta_name,

            "available_scenarios": metadata.get(
                "available_scenarios",
                [],
            ),

            "available_months": metadata.get(
                "available_months",
                [],
            ),

            "selected_filter": (
                selected_filter.model_dump()
            ),

            "metric_filters": metadata.get(
                "metric_filters",
                [
                    {
                        "label": "Market Share",
                        "value": "market_share",
                    },
                    {
                        "label": "Overall Market Volume",
                        "value": "market_volume",
                    },
                ],
            ),

            "event_tabs": {
                "overall_event": overall_event,
                "market_event": market_event,
                "product_event": product_event,
            },
        }

        print("\n[6] RESPONSE SUMMARY")

        for event_name, event_value in response[
            "event_tabs"
        ].items():
            print(
                event_name,
                {
                    "type": type(
                        event_value
                    ).__name__,
                    "present": bool(
                        event_value
                    ),
                    "keys": (
                        list(event_value.keys())
                        if isinstance(
                            event_value,
                            dict,
                        )
                        else None
                    ),
                },
            )

        print("=" * 90 + "\n")

        return response

    except HTTPException:
        raise

    except Exception as exc:
        print("\n[APPLY FILTERS ERROR]")
        print(
            "ERROR TYPE:",
            type(exc).__name__,
        )
        print(
            "ERROR MESSAGE:",
            str(exc),
        )

        raise

    finally:
        cursor.close()

def debug_forecast_outputs(
    *,
    metrics,
):
    """
    Safely inspect the result of load_forecast_outputs().

    Supports:
    - dictionary-based metric structures
    - lists of row dictionaries
    - unexpected values
    """

    print("\n[FORECAST OUTPUT SUMMARY]")

    print(
        "METRICS TYPE:",
        type(metrics).__name__,
    )

    if metrics is None:
        print("METRICS VALUE: None")
        return

    # =====================================================
    # Dictionary structure
    # =====================================================

    if isinstance(metrics, dict):
        print(
            "TOP-LEVEL KEY COUNT:",
            len(metrics),
        )
        print(
            "TOP-LEVEL KEYS:",
            list(metrics.keys()),
        )

        for key, value in metrics.items():
            print("\nMETRIC KEY:", repr(key))
            print(
                "VALUE TYPE:",
                type(value).__name__,
            )

            if isinstance(value, dict):
                print(
                    "NESTED KEYS:",
                    list(value.keys()),
                )

                debug_nested_metric_dict(
                    metric_name=str(key),
                    value=value,
                )

            elif isinstance(value, list):
                print(
                    "LIST LENGTH:",
                    len(value),
                )

                if value:
                    print(
                        "FIRST ITEM TYPE:",
                        type(
                            value[0]
                        ).__name__,
                    )
                    print(
                        "FIRST ITEM:"
                    )
                    pprint(value[0])

            else:
                print(
                    "VALUE:",
                    value,
                )

        return

    # =====================================================
    # List of rows
    # =====================================================

    if isinstance(metrics, list):
        print(
            "ROW COUNT:",
            len(metrics),
        )

        if not metrics:
            return

        item_types = sorted({
            type(item).__name__
            for item in metrics
        })

        print(
            "ITEM TYPES:",
            item_types,
        )

        dictionary_rows = [
            row
            for row in metrics
            if isinstance(row, dict)
        ]

        print(
            "DICTIONARY ROW COUNT:",
            len(dictionary_rows),
        )

        scenario_values = sorted({
            str(
                row.get("scenario_name")
            ).strip()
            for row in dictionary_rows
            if row.get(
                "scenario_name"
            ) is not None
        })

        markets_found = sorted({
            str(row.get("market")).strip()
            for row in dictionary_rows
            if row.get("market")
        })

        products_found = sorted({
            str(row.get("product")).strip()
            for row in dictionary_rows
            if row.get("product")
        })

        sources_found = sorted({
            str(
                row.get("source_of_market")
            ).strip()
            for row in dictionary_rows
            if row.get(
                "source_of_market"
            )
        })

        print(
            "SCENARIOS:",
            scenario_values,
        )
        print(
            "MARKETS:",
            markets_found,
        )
        print(
            "PRODUCTS:",
            products_found,
        )
        print(
            "SOURCES:",
            sources_found,
        )

        print("\nFIRST FIVE ROWS:")

        for index, row in enumerate(
            dictionary_rows[:5]
        ):
            print(
                f"ROW {index}:"
            )
            pprint(row)

        return

    # =====================================================
    # Unexpected structure
    # =====================================================

    print(
        "UNEXPECTED METRICS STRUCTURE:"
    )
    pprint(metrics)

def debug_nested_metric_dict(
    *,
    metric_name: str,
    value: dict,
):
    """
    Inspect common dictionary-based forecast structures.
    """

    common_fields = [
        "months",
        "forecast_values",
        "actual_values",
        "market",
        "product",
        "source_of_market",
        "scenario_name",
    ]

    found_common_field = False

    for field_name in common_fields:
        if field_name not in value:
            continue

        found_common_field = True

        field_value = value[field_name]

        if isinstance(field_value, list):
            print(
                f"{field_name}:",
                {
                    "length": len(
                        field_value
                    ),
                    "sample": (
                        field_value[:5]
                    ),
                },
            )
        else:
            print(
                f"{field_name}:",
                field_value,
            )

    if found_common_field:
        return

    # It may be nested by market, source or product.
    print(
        f"NESTED STRUCTURE FOR "
        f"{metric_name!r}:"
    )

    for nested_key, nested_value in list(
        value.items()
    )[:10]:
        if isinstance(nested_value, dict):
            print(
                repr(nested_key),
                {
                    "type": "dict",
                    "keys": list(
                        nested_value.keys()
                    )[:10],
                },
            )

        elif isinstance(nested_value, list):
            print(
                repr(nested_key),
                {
                    "type": "list",
                    "length": len(
                        nested_value
                    ),
                    "sample": (
                        nested_value[:3]
                    ),
                },
            )

        else:
            print(
                repr(nested_key),
                {
                    "type": type(
                        nested_value
                    ).__name__,
                    "value": nested_value,
                },
            )

def debug_tree_summary(
    *,
    tree: dict,
    stage: str,
):
    print(
        f"\n[TREE SUMMARY: {stage}]"
    )

    if not isinstance(tree, dict):
        print(
            "Tree is not a dictionary:",
            type(tree).__name__,
        )
        return

    print(
        "TOP-LEVEL KEYS:",
        list(tree.keys()),
    )

    months = tree.get("months")

    if months is None:
        months = (
            tree.get("overall", {})
            .get("months")
        )

    print_collection_summary(
        label="MONTHS",
        value=months,
    )

    print_collection_summary(
        label="MARKETS",
        value=tree.get("markets"),
    )

    print_collection_summary(
        label="PRODUCTS",
        value=tree.get("products"),
    )

    overall = tree.get(
        "overall",
        {},
    )

    print(
        "OVERALL TYPE:",
        type(overall).__name__,
    )

    if isinstance(overall, dict):
        print(
            "OVERALL KEYS:",
            list(overall.keys()),
        )

        print_collection_summary(
            label="OVERALL VOLUME",
            value=overall.get("volume"),
        )

    tree_sections = [
        "market_distribution",
        "source_distribution",
        "product_distribution",
        "calculated_market_volume",
        "calculated_source_volume",
        "calculated_product_volume",
        "aggregated_product_volume",
        "aggregated_product_share",
    ]

    for section_name in tree_sections:
        section = tree.get(
            section_name
        )

        print(
            f"{section_name.upper()}:",
            summarize_value(section),
        )

def print_collection_summary(
    *,
    label: str,
    value,
):
    print(
        f"{label}:",
        summarize_value(value),
    )


def summarize_value(value):
    if value is None:
        return {
            "type": "None",
            "count": 0,
        }

    if isinstance(value, dict):
        return {
            "type": "dict",
            "count": len(value),
            "keys": list(
                value.keys()
            )[:20],
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "count": len(value),
            "sample": value[:5],
        }

    if isinstance(value, tuple):
        return {
            "type": "tuple",
            "count": len(value),
            "sample": list(
                value[:5]
            ),
        }

    if isinstance(value, set):
        sample = list(value)[:5]

        return {
            "type": "set",
            "count": len(value),
            "sample": sample,
        }

    return {
        "type": type(
            value
        ).__name__,
        "value": value,
    }

def debug_event_summary(
    *,
    event_name: str,
    event,
):
    print(
        f"\n[EVENT SUMMARY: {event_name}]"
    )

    if not event:
        print("Event is empty.")
        return

    if not isinstance(event, dict):
        print(
            "Event is not a dictionary:",
            type(event).__name__,
        )
        return

    print(
        "EVENT KEYS:",
        list(event.keys()),
    )

    for period_name in [
        "monthly",
        "yearly",
    ]:
        period = event.get(
            period_name
        )

        print(
            f"{period_name.upper()}:",
            summarize_value(period),
        )

        if not isinstance(period, dict):
            continue

        for view_name, view_value in period.items():
            if not isinstance(
                view_value,
                dict,
            ):
                continue

            chart = view_value.get(
                "chart"
            )
            table = view_value.get(
                "table"
            )

            print(
                f"{period_name}.{view_name}:",
                {
                    "keys": list(
                        view_value.keys()
                    ),
                    "has_chart": bool(
                        chart
                    ),
                    "has_table": bool(
                        table
                    ),
                    "chart": (
                        summarize_value(chart)
                    ),
                    "table": (
                        summarize_value(table)
                    ),
                },
            )

#edits
@router.post("/edit_save")
def edit_save(
    payload: EditSaveRequest,
    db=Depends(get_connection),
):
    """
    Edit, normalize, recompute and save forecast data.

    Editable:
        market_event
        product_event

    Read-only:
        overall_event

    Response:
        Exactly the same structure as apply_filters.
    """

    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )

    try:
        selected_filter = (
            payload.selected_filter.model_dump()
        )

        scenario_name = (
            payload.selected_filter.scenario_name
        )

        # ================================================
        # 1. Defensive tab validation
        # ================================================

        if payload.selected_tab not in {
            "market_event",
            "product_event",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Overall Event is read-only and cannot be edited."
                ),
            )

        # ================================================
        # 2. Load complete unfiltered database data
        # ================================================

        original_metrics = load_forecast_outputs(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        if not original_metrics.get(
            "market_share"
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "No market-share forecast data was found."
                ),
            )

        if not original_metrics.get(
            "market_volume"
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "No market-volume forecast data was found."
                ),
            )

        # ================================================
        # 3. Build complete calculation tree
        # ================================================

        tree = build_calculation_tree(
            original_metrics
        )

        # Do not filter the tree before editing.
        # The DB save requires the complete timeline.

        # ================================================
        # 4. Resolve the selected monthly range
        # ================================================

        selected_months, selected_indexes = (
            resolve_selected_months(
                tree=tree,
                payload=payload,
            )
        )

        # ================================================
        # 5. Validate the submitted rows
        # ================================================

        validate_edited_rows(
            rows=payload.edited_table_rows,
            expected_value_count=len(
                selected_months
            ),
        )

        validate_row_labels(
            tree=tree,
            payload=payload,
        )

        # ================================================
        # 6. Build canonical market-product matrix
        # ================================================

        matrix = build_market_product_volume_matrix(
            tree
        )

        # ================================================
        # 7. Apply edits and normalize
        # ================================================

        if payload.selected_tab == "market_event":

            apply_market_event_edits(
                tree=tree,
                matrix=matrix,
                payload=payload,
                selected_indexes=selected_indexes,
            )

        elif payload.selected_tab == "product_event":

            apply_product_event_edits(
                tree=tree,
                matrix=matrix,
                payload=payload,
                selected_indexes=selected_indexes,
            )

        # ================================================
        # 8. Push normalized values into source products
        # ================================================

        apply_matrix_to_tree(
            tree=tree,
            matrix=matrix,
            selected_indexes=selected_indexes,
        )

        # ================================================
        # 9. Recompute both event orientations
        # ================================================

        recompute_tree(
            tree=tree,
            selected_indexes=selected_indexes,
        )

        # Both event tabs now use the same recomputed tree:
        #
        # build_market_event(tree)
        # build_product_event(tree)
        #
        # Yearly tables are regenerated from monthly data
        # by the existing event builders.

        # ================================================
        # 10. Save into forecast_outputs
        # ================================================

        save_tree_to_forecast_outputs(
            cursor=cursor,
            tree=tree,
            original_metrics=original_metrics,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        # Save all changes atomically.
        db.commit()

        # ================================================
        # 11. Reload DB and return Apply Filters response
        # ================================================

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
            detail=(
                "Unable to edit, normalize, recompute and "
                f"save the forecast: {exc}"
            ),
        ) from exc

    finally:
        cursor.close()