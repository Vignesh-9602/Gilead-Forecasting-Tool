from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
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

        # --------------------------------------------------
        # Available Months — fetched from stored forecast_data,
        # not generated from start/end dates
        # --------------------------------------------------
        cursor.execute(
            """
            SELECT forecast_data
            FROM raw_hiv_treat.forecast_outputs
            WHERE ta_name = %s
              AND UPPER(TRIM(market)) = 'ALL'
              AND UPPER(TRIM(product)) = 'ALL'
            LIMIT 1
            """,
            (ta_name,),
        )

        row = cursor.fetchone()
        if not row or not row.get("forecast_data"):
            raise HTTPException(
                status_code=404,
                detail="No month data found."
            )

        months = row["forecast_data"].get("months", [])
        available_months = sorted(months)

        return {
            "ta_name": ta_name,
            "available_scenarios": scenarios,
            "markets": markets,
            "products": products,
            "available_months": available_months,
            "selected_filter": {
                "scenario_name": config["scenario_name"],
                "markets": config["market"],
                "products": config["product"],
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




def parse_events_payload(raw_payload):
    if raw_payload is None:
        return []

    if isinstance(raw_payload, list):
        return [
            event
            for event in raw_payload
            if isinstance(event, dict)
        ]

    if isinstance(raw_payload, dict):
        return [raw_payload]

    if isinstance(raw_payload, str):
        raw_payload = raw_payload.strip()

        if not raw_payload:
            return []

        parsed = json.loads(raw_payload)

        if isinstance(parsed, list):
            return [
                event
                for event in parsed
                if isinstance(event, dict)
            ]

        if isinstance(parsed, dict):
            return [parsed]

    return []

def load_scenario_events_payload(
    cursor,
    ta_name,
    scenario_name,
):
    cursor.execute(
        """
        SELECT events_payload
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name = %s
          AND events_payload IS NOT NULL
        """,
        (
            ta_name,
            scenario_name,
        ),
    )

    rows = cursor.fetchall() or []

    all_events = []
    seen_events = set()

    print(
        "[EVENT LOADER] DATABASE ROW COUNT:",
        len(rows),
    )

    for index, row in enumerate(rows):
        raw_payload = (
            row.get("events_payload")
            if isinstance(row, dict)
            else row[0]
        )

        print(
            f"[EVENT LOADER] ROW {index + 1} RAW:",
            raw_payload,
        )

        try:
            parsed_events = parse_events_payload(
                raw_payload
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid events_payload JSON for "
                f"scenario {scenario_name!r}: {exc}"
            ) from exc

        print(
            f"[EVENT LOADER] ROW {index + 1} "
            f"PARSED EVENT COUNT:",
            len(parsed_events),
        )

        for event in parsed_events:
            # Prevent repeated payloads from being returned
            # when forecast_outputs has multiple metric rows.
            signature = json.dumps(
                event,
                sort_keys=True,
                default=str,
            )

            if signature in seen_events:
                continue

            seen_events.add(signature)
            all_events.append(event)

    print(
        "[EVENT LOADER] UNIQUE EVENTS:",
        len(all_events),
    )

    pprint(all_events)

    return all_events

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
        # 3. Load saved event payload
        # =====================================================

        print("\n[3] LOADING SAVED EVENTS")

        saved_events = load_scenario_events_payload(
            cursor=cursor,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        print(
            "SAVED EVENTS COUNT:",
            len(saved_events),
        )

        print("SAVED EVENTS:")
        pprint(saved_events)

        # =====================================================
        # 4. Build tree
        # =====================================================

        print("\n[4] BUILDING CALCULATION TREE")

        tree = build_calculation_tree(
            metrics
        )

        print("\n===== PRODUCT TOTALS =====")

        overall = tree["overall"]["volume"][0]
        print("Overall:", overall)

        total = 0

        for product_name, product in tree["products"].items():
            volume = product["volume"][0]
            total += volume
            print(product_name, volume)

        print("Sum:", total)
        print("Difference:", total - overall)

        # validate_calculation_tree_totals(
        #     tree
        # )

        debug_tree_summary(
            tree=tree,
            stage="AFTER BUILD",
        )

        # =====================================================
        # 5. Date filtering
        # =====================================================

        print("\n[5] FILTERING TREE BY DATE")

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
        # 6. Build events
        # =====================================================

        print("\n[6] BUILDING EVENTS")

        # Pass events_payload into Overall Event.
        # build_overall_impact_curve_configuration()
        # will retain only overall-event rows.
        overall_event = build_overall_event(
            tree=tree,
            saved_events=saved_events,
        )

        debug_event_summary(
            event_name="overall_event",
            event=overall_event,
        )

        # Market and Product events are unchanged for now.
        market_event = build_market_event(
            tree=tree,
            selected_products=(
                selected_filter.products
            ),
            saved_events=saved_events,
        )

        debug_event_summary(
            event_name="market_event",
            event=market_event,
        )

        product_event = build_product_event(
            tree=tree,
            selected_markets=(
                selected_filter.markets
            ),
            saved_events=saved_events,
        )

        debug_event_summary(
            event_name="product_event",
            event=product_event,
        )

        # =====================================================
        # 7. Response
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

        print("\n[7] RESPONSE SUMMARY")

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

        overall_rows = (
            response
            .get("event_tabs", {})
            .get("overall_event", {})
            .get(
                "impact_curve_configuration",
                {},
            )
            .get("rows", [])
        )

        print(
            "OVERALL EVENT CONFIGURATION ROWS:"
        )
        pprint(overall_rows)

        print("=" * 90 + "\n")

        return response

    except HTTPException:
        raise

    except ValueError as exc:
        print("\n[APPLY FILTERS VALIDATION ERROR]")
        print(
            "ERROR TYPE:",
            type(exc).__name__,
        )
        print(
            "ERROR MESSAGE:",
            str(exc),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

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

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to apply market event filters: "
                f"{exc}"
            ),
        ) from exc

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
    cursor = db.cursor(
        cursor_factory=RealDictCursor
    )

    try:
        payload_dict = payload.model_dump(
            mode="json"
        )

        selected_filter = (
            payload.selected_filter.model_dump(
                mode="json"
            )
        )

        scenario_name = (
            payload.selected_filter.scenario_name
        )

        selected_market = (
            payload.selected_filter.markets
        )

        selected_product = (
            payload.selected_filter.products
        )

        selected_tab = payload.selected_tab
        selected_view = payload.selected_table_view
        selected_metric = payload.selected_metric

        # ================================================
        # 1. Defensive tab validation
        # ================================================

        if selected_tab not in {
            "market_event",
            "product_event",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Overall Event is read-only and "
                    "cannot be edited."
                ),
            )

        # ================================================
        # 2. Validate filters
        # ================================================

        if (
            payload.selected_filter.start_date
            > payload.selected_filter.end_date
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "start_date cannot be greater "
                    "than end_date."
                ),
            )

        # Market Event edits require a selected product.
        if (
            selected_tab == "market_event"
            and not selected_product
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "A product must be selected when "
                    "editing Market Event."
                ),
            )

        # Product Level represents products against Overall,
        # so a selected market is not required.
        if (
            selected_tab == "product_event"
            and selected_view != "product_level"
            and not selected_market
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "A market must be selected when "
                    "editing this Product Event view."
                ),
            )

        # ================================================
        # 3. Validate supported edit combinations
        # ================================================

        supported_views = {
            "market_event": {
                "market_level",
                "product_market_level",
            },
            "product_event": {
                "product_level",
                "market_product_level",
            },
        }

        if selected_view not in supported_views[
            selected_tab
        ]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported edit combination: "
                    f"{selected_tab!r} / "
                    f"{selected_view!r}."
                ),
            )

        if selected_metric not in {
            "market_share",
            "market_volume",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "selected_metric must be either "
                    "'market_share' or "
                    "'market_volume'."
                ),
            )

        # Product Level normalization is currently based
        # on product shares summing to 100%.
        if (
            selected_tab == "product_event"
            and selected_view == "product_level"
            and selected_metric != "market_share"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Product Level editing currently "
                    "supports Market Share only."
                ),
            )

        # ================================================
        # 4. Load complete unfiltered scenario data
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
                    "No market-share forecast data "
                    "was found."
                ),
            )

        if not original_metrics.get(
            "market_volume"
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "No market-volume forecast data "
                    "was found."
                ),
            )

        # ================================================
        # 5. Build calculation tree
        # ================================================

        tree = build_calculation_tree(
            original_metrics
        )

        # ================================================
        # 6. Resolve selected monthly range
        # ================================================

        selected_months, selected_indexes = (
            resolve_selected_months(
                tree=tree,
                payload=payload,
            )
        )

        if not selected_indexes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No months were resolved from the "
                    "selected date range."
                ),
            )

        # ================================================
        # 7. Validate submitted rows
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
        # 8. Apply edits
        # ================================================

        is_product_level_edit = (
            payload.selected_tab == "product_event"
            and payload.selected_table_view
            == "product_level"
        )

        is_product_market_level_edit = (
            payload.selected_tab == "market_event"
            and payload.selected_table_view
            == "product_market_level"
        )

        if is_product_level_edit:

            apply_product_level_edits(
                tree=tree,
                payload=payload.model_dump(
                    mode="json"
                ),
                selected_indexes=selected_indexes,
                decimals=2,
            )

        elif is_product_market_level_edit:

            matrix = (
                build_market_product_volume_matrix(
                    tree
                )
            )

            apply_product_market_level_edits(
                tree=tree,
                matrix=matrix,
                payload=payload,
                selected_indexes=selected_indexes,
                decimals=2,
            )

            apply_matrix_to_tree(
                tree=tree,
                matrix=matrix,
                selected_indexes=selected_indexes,
            )

            print("\n==== AFTER apply_matrix_to_tree ====")

            for market_name, market in tree["markets"].items():

                total = 0

                for source in market["sources"].values():

                    product = source["products"].get("Biktarvy")

                    if product:
                        total += product["volume"][selected_indexes[0]]

                print(market_name, total)

            recompute_tree(
                tree=tree,
                selected_indexes=selected_indexes,
            )

        else:

            matrix = (
                build_market_product_volume_matrix(
                    tree
                )
            )

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

            apply_matrix_to_tree(
                tree=tree,
                matrix=matrix,
                selected_indexes=selected_indexes,
            )

            recompute_tree(
                tree=tree,
                selected_indexes=selected_indexes,
            )

        # ================================================
        # 9. Save complete updated tree
        # ================================================

        save_tree_to_forecast_outputs(
            cursor=cursor,
            tree=tree,
            original_metrics=original_metrics,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        db.commit()

        # ================================================
        # 10. Return refreshed response
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
                "Unable to edit, normalize, "
                "recompute and save the forecast: "
                f"{exc}"
            ),
        ) from exc

    finally:
        cursor.close()


#delete

def delete_event_from_db(
    ta_name: str,
    scenario_name: str,
    tab: str,
    event_name: str,
) -> int:

    query = """
        UPDATE raw_hiv_treat.forecast_outputs
        SET events_payload =
            COALESCE(
                (
                    SELECT jsonb_agg(event_item)
                    FROM jsonb_array_elements(
                        COALESCE(
                            events_payload,
                            '[]'::jsonb
                        )
                    ) AS event_item
                    WHERE NOT (
                        event_item ->> 'event_name' = %s
                        AND
                        CASE
                            WHEN event_item ? 'impacted_markets'
                                THEN 'market_event'

                            WHEN event_item ? 'impacted_products'
                                THEN 'product_event'

                            ELSE 'overall_event'
                        END = %s
                    )
                ),
                '[]'::jsonb
            ),
            updated_at = CURRENT_TIMESTAMP
        WHERE ta_name = %s
          AND scenario_name = %s
          AND EXISTS (
              SELECT 1
              FROM jsonb_array_elements(
                  COALESCE(
                      events_payload,
                      '[]'::jsonb
                  )
              ) AS existing_event
              WHERE existing_event ->> 'event_name' = %s
                AND
                CASE
                    WHEN existing_event ? 'impacted_markets'
                        THEN 'market_event'

                    WHEN existing_event ? 'impacted_products'
                        THEN 'product_event'

                    ELSE 'overall_event'
                END = %s
          )
        RETURNING scenario_name;
    """

    params = (
        event_name,
        tab,
        ta_name,
        scenario_name,
        event_name,
        tab,
    )

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                params,
            )

            updated_row = cursor.fetchone()

        connection.commit()

        return 1 if updated_row else 0

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



VALID_EVENT_TABS = {
    "overall_event",
    "market_event",
    "product_event",
}


def delete_event(
    payload: Dict[str, Any],
) -> dict:

    ta_name = payload["ta_name"].strip()
    scenario_name = payload["scenario_name"].strip()
    tab = payload["tab"]
    event_name = payload["event_name"].strip()

    if tab not in VALID_EVENT_TABS:
        raise ValueError(
            f"Invalid event tab: {tab}"
        )

    if not event_name:
        raise ValueError(
            "event_name is required"
        )

    deleted_count = delete_event_from_db(
        ta_name=ta_name,
        scenario_name=scenario_name,
        tab=tab,
        event_name=event_name,
    )

    if deleted_count == 0:
        raise ValueError(
            f"Event '{event_name}' was not found "
            f"for scenario '{scenario_name}' "
            f"in tab '{tab}'."
        )

    return {
        "status": "success",
        "message": (
            f"Event '{event_name}' deleted successfully."
        ),
        "ta_name": ta_name,
        "scenario_name": scenario_name,
        "tab": tab,
        "event_name": event_name,
        "deleted_count": deleted_count,
    }

@router.delete("/delete-event")
def delete_event_endpoint(
    payload: DeleteEventRequest,
):
    try:
        return delete_event(
            payload.model_dump()
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete event: {str(exc)}",
        )