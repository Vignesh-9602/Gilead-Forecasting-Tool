from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from psycopg2.extras import RealDictCursor
from app.hiv_prep.routes.market_events_models import *
from app.hiv_prep.services.market_event_helpers import *
from app.hiv_prep.services.calculation_tree_market_events import *
from app.hiv_prep.services.generic_builders_market_events import *
from app.hiv_prep.services.edit_helpers import *
from app.hiv_prep.services.HIV_prep_Retaining_Filters import save_user_configuration

router = APIRouter()

from app.db.connection import get_connection

router = APIRouter(prefix="/api/hiv_prep", tags=["hiv_prep_market_events"])


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
            FROM raw_hiv_prep.user_configurations
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
            FROM raw_hiv_prep.forecast_outputs
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

        # The previously-selected scenario may have since been deleted (see
        # DELETE /scenarios/{scenario_name} in api.py, which removes its rows
        # from forecast_outputs) -- user_configurations still has the stale
        # name, and returning it as-is would restore a selection that no
        # longer exists. Fall back to whatever "Base" row is actually present
        # (case-insensitive match, since casing has drifted before -- see
        # BASELINE_SCENARIO), or the literal default if even that is missing.
        scenario_lookup = {s.strip().upper(): s for s in scenarios}
        saved_scenario_name = (config["scenario_name"] or "").strip()
        effective_scenario_name = (
            scenario_lookup.get(saved_scenario_name.upper())
            or scenario_lookup.get(BASELINE_SCENARIO.upper())
            or BASELINE_SCENARIO
        )

        # Available Markets
        cursor.execute(
            """
            SELECT DISTINCT market
            FROM raw_hiv_prep.forecast_outputs
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
            SELECT DISTINCT product_id as product
            FROM raw_hiv_prep.product_master_hiv_prep
            WHERE ta_name = %s
            AND product_id IS NOT NULL
            AND UPPER(TRIM(product_id)) <> 'ALL'
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
            FROM raw_hiv_prep.forecast_outputs
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
                "scenario_name": effective_scenario_name,
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
        FROM raw_hiv_prep.forecast_outputs
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

def debug_product_volume_consistency(
    tree: dict,
):
    matrix = (
        build_market_product_volume_matrix(
            tree
        )
    )

    markets = list(
        tree.get(
            "markets",
            {}
        ).keys()
    )

    products = list(
        tree.get(
            "products",
            {}
        ).keys()
    )

    overall = (
        tree.get(
            "overall",
            {}
        ).get(
            "volume",
            []
        )
    )

    print(
        "\n===== PRODUCT VOLUME CONSISTENCY ====="
    )

    for month_index, month in enumerate(
        tree.get("months", [])
    ):

        product_totals = {}

        for product_name in products:

            product_totals[
                product_name
            ] = sum(
                float(
                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ]
                    or 0
                )
                for market_name in markets
            )

        matrix_total = sum(
            product_totals.values()
        )

        overall_volume = float(
            overall[month_index] or 0
        )

        print(
            month,
            {
                "overall": overall_volume,
                "products": product_totals,
                "product_total": matrix_total,
                "difference": (
                    matrix_total
                    - overall_volume
                ),
            },
        )

PRODUCT_MASTER_TABLE = "raw_hiv_prep.product_master_hiv_prep"

# Tabs that carry product pickers, and which keys in their
# impact_curve_configuration hold a product list. overall_event has neither.
PRODUCT_LIST_KEYS = {
    "market_event": ("products",),                     # Channel Event: Products column
    "product_event": ("products", "impact_products"),  # Product Event: Products + Impacted Products
}


def fetch_master_products(cursor, ta_name):
    """Every active product registered for the TA.

    product_id holds the display name here (product_name holds a short
    code, e.g. Truvada / Tru123), and product_id is also what
    forecast_outputs stores in its `product` column -- so it's the value
    the pickers must use. NULL active_flag counts as active: rows created
    before the flag was being set would otherwise disappear."""
    cursor.execute(
        f"""
        SELECT DISTINCT TRIM(product_id) AS product
        FROM {PRODUCT_MASTER_TABLE}
        WHERE ta_name = %s
          AND product_id IS NOT NULL
          AND UPPER(TRIM(product_id)) <> 'ALL'
          AND UPPER(COALESCE(NULLIF(TRIM(active_flag), ''), 'Y')) <> 'N'
        ORDER BY 1
        """,
        (ta_name,),
    )
    return [row["product"] for row in cursor.fetchall() if row["product"]]


def apply_master_products_to_events(event_tabs, master_products):
    """Union the master product list into each tab's pickers.

    Union rather than replace: a product that has forecast data but is
    missing from (or deactivated in) the master table stays selectable,
    so this can only ever add options, never silently remove one that
    already works."""
    if not master_products:
        return

    for tab_name, keys in PRODUCT_LIST_KEYS.items():
        config = (event_tabs.get(tab_name) or {}).get("impact_curve_configuration")
        if not isinstance(config, dict):
            continue
        for key in keys:
            existing = config.get(key) or []
            config[key] = sorted(set(existing) | set(master_products))

BASELINE_SCENARIO = "Base"   # module level, next to the table constants

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

        debug_product_volume_consistency(
            tree
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
        # 6b. Product pickers from the master table
        # =====================================================
        # The tree only knows products that have rows in forecast_outputs,
        # so a newly registered product never reaches the dropdowns. The
        # pickers list what's selectable, not what has data -- take them
        # from the master table instead.
        #
        # Except in Base. Nothing materializes a product there (seeding
        # skips the baseline) and nothing persists an event against it, so
        # offering a product with no rows would only produce a selection
        # that silently does nothing. Base shows what it actually has.

        is_baseline = scenario_name.strip().lower() == BASELINE_SCENARIO.lower()

        if is_baseline:
            print(
                "SKIPPING master product injection -- "
                f"scenario {scenario_name!r} is the baseline"
            )
        else:
            master_products = fetch_master_products(
                cursor=cursor,
                ta_name=payload.ta_name,
            )

            print("MASTER PRODUCTS:", master_products)

            apply_master_products_to_events(
                event_tabs={
                    "overall_event": overall_event,
                    "market_event": market_event,
                    "product_event": product_event,
                },
                master_products=master_products,
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

        # --------------------------------------------------
        # Persist the applied selection
        # --------------------------------------------------
        # So a later GET /get_market_event_filters (e.g. after navigating
        # away and back) restores this scenario/market/product instead of
        # whatever Model Input's own /applyfilter last saved -- this route
        # never wrote to user_configurations before, so the selection made
        # here was never actually the one that came back.
        save_user_configuration(
            cur=cursor,
            user_id="system",
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
            market=selected_filter.markets,
            product=selected_filter.products,
            start_date=selected_filter.start_date,
            end_date=selected_filter.end_date,
        )
        db.commit()

        return response

    except HTTPException:
        db.rollback()
        raise

    except ValueError as exc:
        db.rollback()

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
        db.rollback()

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
        selected_filter = (
            payload.selected_filter.model_dump(
                mode="json"
            )
        )

        scenario_name = (
            payload.selected_filter.scenario_name
        )

        # ==================================================
        # 1. Prevent edits/saves to BASE scenario
        # ==================================================

        if (
            str(scenario_name)
            .strip()
            .casefold()
            == "base"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot save changes in the BASE scenario. "
                    "Please create or select another scenario "
                    "before editing."
                ),
            )

        selected_market = (
            payload.selected_filter.markets
        )

        selected_product = (
            payload.selected_filter.products
        )

        selected_tab = (
            payload.selected_tab
        )

        selected_view = (
            payload.selected_table_view
        )

        selected_metric = (
            payload.selected_metric
        )

        # ==================================================
        # 1. Validate tab
        # ==================================================

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

        # ==================================================
        # 2. Validate dates
        # ==================================================

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

        # ==================================================
        # 3. Validate required filters
        # ==================================================

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

        # ==================================================
        # 4. Validate supported combinations
        # ==================================================

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

        if (
            selected_view
            not in supported_views[selected_tab]
        ):
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

        # ==================================================
        # 5. Load complete scenario data
        # ==================================================

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

        # ==================================================
        # 6. Build calculation tree
        # ==================================================

        tree = build_calculation_tree(
            original_metrics
        )

        # ==================================================
        # 7. Resolve selected months
        # ==================================================

        (
            selected_months,
            selected_indexes,
        ) = resolve_selected_months(
            tree=tree,
            payload=payload,
        )

        if not selected_indexes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No months were resolved from "
                    "the selected date range."
                ),
            )

        # ==================================================
        # 8. Validate submitted rows
        # ==================================================

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

        # ==================================================
        # 9. Resolve edit type
        # ==================================================

        is_product_level_edit = (
            selected_tab == "product_event"
            and selected_view == "product_level"
        )

        is_product_market_level_edit = (
            selected_tab == "market_event"
            and selected_view
            == "product_market_level"
        )

        is_market_product_level_edit = (
            selected_tab == "product_event"
            and selected_view
            == "market_product_level"
        )

        is_market_level_edit = (
            selected_tab == "market_event"
            and selected_view == "market_level"
        )

        # ==================================================
        # 10A. PRODUCT LEVEL
        #
        # Overall
        #     Biktarvy
        #     Descovy
        #     Truvada
        #
        # Product totals change.
        # Existing Product -> Market distribution is preserved.
        # ==================================================

        if is_product_level_edit:

            # IMPORTANT:
            # Build the current matrix BEFORE changing
            # top-level product totals.
            matrix = (
                build_market_product_volume_matrix(
                    tree
                )
            )

            # Apply Product Level edit.
            apply_product_level_edits(
                tree=tree,
                payload=payload.model_dump(
                    mode="json"
                ),
                selected_indexes=selected_indexes,
                decimals=2,
            )

            # Push new top-level product totals into
            # Retail / Non-retail while preserving each
            # product's existing market distribution.
            matrix = sync_product_level_to_matrix(
                tree=tree,
                matrix=matrix,
                selected_indexes=(
                    selected_indexes
                ),
            )

            # Push matrix back into canonical
            # Market -> Product source nodes.
            apply_matrix_to_tree(
                tree=tree,
                matrix=matrix,
                selected_indexes=(
                    selected_indexes
                ),
            )

            # Recompute all dependent values.
            recompute_tree(
                tree=tree,
                selected_indexes=(
                    selected_indexes
                ),
                matrix=matrix,
                normalize_matrix_to_overall=False,
            )

        # ==================================================
        # 10B. PRODUCT -> MARKET
        #
        # Biktarvy
        #     Retail
        #     Non-retail
        #
        # Product total stays fixed.
        # Markets normalize inside product.
        # ==================================================

        elif is_product_market_level_edit:

            matrix = (
                build_market_product_volume_matrix(
                    tree
                )
            )

            matrix = (
                apply_product_market_level_edits(
                    tree=tree,
                    matrix=matrix,
                    payload=payload,
                    selected_indexes=(
                        selected_indexes
                    ),
                    decimals=2,
                )
            )

            apply_matrix_to_tree(
                tree=tree,
                matrix=matrix,
                selected_indexes=(
                    selected_indexes
                ),
            )

            recompute_tree(
                tree=tree,
                selected_indexes=(
                    selected_indexes
                ),
                matrix=matrix,
                normalize_matrix_to_overall=False,
            )

        # ==================================================
        # 10C. MARKET -> PRODUCT
        #
        # Non-retail
        #     Biktarvy
        #     Descovy
        #     Truvada
        #
        # Market total stays fixed.
        # Edited product remains fixed.
        # Sibling products normalize.
        # ==================================================

        elif is_market_product_level_edit:

            matrix = (
                build_market_product_volume_matrix(
                    tree
                )
            )

            matrix = (
                apply_market_product_level_edits(
                    tree=tree,
                    matrix=matrix,
                    payload=payload,
                    selected_indexes=(
                        selected_indexes
                    ),
                    decimals=2,
                )
            )

            apply_matrix_to_tree(
                tree=tree,
                matrix=matrix,
                selected_indexes=(
                    selected_indexes
                ),
            )

            recompute_tree(
                tree=tree,
                selected_indexes=(
                    selected_indexes
                ),
                matrix=matrix,
                normalize_matrix_to_overall=False,
            )

        # ==================================================
        # 10D. MARKET LEVEL
        #
        # Overall
        #     Retail
        #     Non-retail
        #
        # Overall stays fixed.
        # Markets normalize.
        # ==================================================

        elif is_market_level_edit:

            matrix = (
                build_market_product_volume_matrix(
                    tree
                )
            )

            apply_market_event_edits(
                tree=tree,
                matrix=matrix,
                payload=payload,
                selected_indexes=(
                    selected_indexes
                ),
            )

            apply_matrix_to_tree(
                tree=tree,
                matrix=matrix,
                selected_indexes=(
                    selected_indexes
                ),
            )

            recompute_tree(
                tree=tree,
                selected_indexes=(
                    selected_indexes
                ),
                matrix=matrix,
                normalize_matrix_to_overall=False,
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unable to determine edit workflow "
                    f"for tab={selected_tab!r}, "
                    f"view={selected_view!r}."
                ),
            )

        # ==================================================
        # 11. Save complete updated tree
        # ==================================================

        save_tree_to_forecast_outputs(
            cursor=cursor,
            tree=tree,
            original_metrics=original_metrics,
            ta_name=payload.ta_name,
            scenario_name=scenario_name,
        )

        # ==================================================
        # 12. Commit
        # ==================================================

        db.commit()

        # ==================================================
        # 13. Return refreshed apply-filter response
        # ==================================================

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

        import traceback
        traceback.print_exc()

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
        UPDATE raw_hiv_prep.forecast_outputs
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

#new product

@router.get("/products")
def get_products(db=Depends(get_connection)):
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(
            """
            SELECT
                product_id,
                product_name,
                date_added,
                added_by,
                modified_by
            FROM raw_hiv_prep.product_master_hiv_prep
            ORDER BY product_name
            """
        )

        rows = cursor.fetchall()

        return {
            "products": [
                {
                    "product_id": row["product_id"],
                    "product_name": row["product_id"],
                    "date_added": row["date_added"].strftime("%Y-%m-%d")
                    if row.get("date_added")
                    else None,
                    "added_by": row["added_by"],
                    "modified_by": row["modified_by"],
                }
                for row in rows
            ]
        }

    finally:
        cursor.close()


PRODUCT_MASTER_TABLE = "raw_hiv_prep.product_master_hiv_prep"


class AddProductRequest(BaseModel):
    ta_name: str
    product_name: str
    company: Optional[str] = None


@router.post("/products")
def add_product(
    payload: AddProductRequest,
    db=Depends(get_connection)
):
    """Registers a product. Nothing is written to forecast_outputs here --
    the product is materialized into a scenario the first time
    run_calculation is called for it (see seed_missing_products in
    Market_Events_Run_Calculation), with zero history and zero forecast.

    That keeps creation cheap and scenario-agnostic: a product added today
    lands in scenarios that don't exist yet, without a backfill step.
    """
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        user_id = "system"  # Replace with actual logged-in user

        # product_id holds the display name in this table (product_name
        # holds a short code, e.g. Truvada / Tru123), so the uniqueness
        # check belongs on product_id -- it's also what forecast_outputs
        # stores in its `product` column.
        cursor.execute(
            f"""
            SELECT 1
            FROM {PRODUCT_MASTER_TABLE}
            WHERE ta_name = %s
              AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
            """,
            (payload.ta_name, payload.product_name)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Product already exists."
            )

        # active_flag is set explicitly -- left NULL, the product is
        # excluded by anything filtering on 'Y'.
        cursor.execute(
            f"""
            INSERT INTO {PRODUCT_MASTER_TABLE}
            (
                ta_name,
                product_id,
                product_name,
                active_flag,
                company,
                date_added,
                added_by,
                modified_by
            )
            VALUES (%s, %s, %s, 'Y', %s, CURRENT_DATE, %s, %s)
            RETURNING
                product_id,
                product_name,
                active_flag,
                company,
                date_added,
                added_by,
                modified_by
            """,
            (
                payload.ta_name,
                payload.product_name,
                payload.product_name,
                payload.company,
                user_id,
                user_id,
            )
        )

        product = cursor.fetchone()
        db.commit()

        return {
            "message": "Product added successfully",
            "product": {
                "product_id": product["product_id"],
                # product_id is the display name here.
                "product_name": product["product_id"],
                "product_code": product["product_name"],
                "active_flag": product["active_flag"],
                "company": product["company"],
                "date_added": product["date_added"].strftime("%Y-%m-%d"),
                "added_by": product["added_by"],
                "modified_by": product["modified_by"],
            },
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()


def sync_product_in_events_payload(
    cursor,
    ta_name,
    old_name,
    new_name=None,
    scenario_name=None,
):
    """Rename or remove a product across every saved event for this TA.

    A product name can appear in a saved event in three places: the
    'products' list (Market Event + Product Event), the
    'impacted_products' list (Product Event only), and as a key of
    'source_percentages' (Product Event only). Without this, renaming or
    deleting a product in product_master/forecast_outputs leaves those
    saved events pointing at a product name that no longer exists, so
    apply_market_event_filters keeps returning the stale name.

    new_name=None means "remove" (product_master delete); a string means
    "rename" (product_master update). scenario_name scopes the sync the
    same way delete_product scopes the forecast-row delete -- omit it to
    touch every scenario for the TA, which is what a TA-wide rename needs.

    Returns the number of forecast_outputs rows rewritten.
    """
    old_key = old_name.strip().upper()

    query = f"""
        SELECT id, events_payload
        FROM {FORECAST_TABLE}
        WHERE ta_name = %s
          AND events_payload IS NOT NULL
    """
    params = [ta_name]

    if scenario_name:
        query += " AND scenario_name = %s"
        params.append(scenario_name)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    rewritten = 0

    for row in rows:
        events = parse_events_payload(row["events_payload"])
        if not events:
            continue

        changed = False

        for event in events:
            if not isinstance(event, dict):
                continue

            for list_key in ("products", "impacted_products"):
                values = event.get(list_key)
                if not isinstance(values, list):
                    continue

                new_values = []
                for value in values:
                    if (
                        isinstance(value, str)
                        and value.strip().upper() == old_key
                    ):
                        changed = True
                        if new_name is not None:
                            new_values.append(new_name)
                        # else: drop it -- product was removed
                    else:
                        new_values.append(value)

                event[list_key] = new_values

            percentages = event.get("source_percentages")
            if isinstance(percentages, dict):
                matched_key = next(
                    (
                        key for key in percentages
                        if isinstance(key, str)
                        and key.strip().upper() == old_key
                    ),
                    None,
                )
                if matched_key is not None:
                    changed = True
                    value = percentages.pop(matched_key)
                    if new_name is not None:
                        percentages[new_name] = value

        if changed:
            cursor.execute(
                f"""
                UPDATE {FORECAST_TABLE}
                SET events_payload = %s::jsonb,
                    updated_at = now()
                WHERE id = %s
                """,
                (json.dumps(events), row["id"]),
            )
            rewritten += 1

    return rewritten


@router.put("/products")
def update_product(
    payload: UpdateProductRequest,
    db=Depends(get_connection)
):
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        user_id = "system"  # Replace with actual logged-in user

        # Check if existing product exists
        cursor.execute(
            """
            SELECT
                product_id,
                date_added,
                added_by
            FROM raw_hiv_prep.product_master_hiv_prep
            WHERE ta_name = %s
              AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
            """,
            (
                payload.ta_name,
                payload.product_name
            )
        )

        existing_product = cursor.fetchone()

        if not existing_product:
            raise HTTPException(
                status_code=404,
                detail="Product not found."
            )

        # Check if new product name already exists
        cursor.execute(
            """
            SELECT 1
            FROM raw_hiv_prep.product_master_hiv_prep
            WHERE ta_name = %s
              AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
            """,
            (
                payload.ta_name,
                payload.new_product_name
            )
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Product already exists."
            )

        # Update product
        cursor.execute(
            """
            UPDATE raw_hiv_prep.product_master_hiv_prep
            SET
                product_name = %s,
                product_id = %s,
                modified_by = %s
            WHERE ta_name = %s
              AND UPPER(TRIM(product_name)) = UPPER(TRIM(%s))
            RETURNING
                product_name,
                date_added,
                added_by,
                modified_by
            """,
            (
                payload.new_product_name,
                payload.new_product_name,  # product_id same as product_name
                user_id,
                payload.ta_name,
                payload.product_name
            )
        )

        updated_product = cursor.fetchone()

        # --------------------------------------------------
        # Keep forecast_outputs.product in sync
        # --------------------------------------------------
        # forecast_outputs.product holds the same value as
        # product_master.product_id -- if it isn't renamed here too, every
        # existing forecast row becomes orphaned from the renamed product.
        cursor.execute(
            f"""
            UPDATE {FORECAST_TABLE}
            SET product = %s,
                updated_at = now()
            WHERE ta_name = %s
              AND UPPER(TRIM(product)) = UPPER(TRIM(%s))
            """,
            (
                payload.new_product_name,
                payload.ta_name,
                payload.product_name
            )
        )

        # --------------------------------------------------
        # Keep saved market/product events in sync
        # --------------------------------------------------
        # apply_market_event_filters reads product names back out of
        # events_payload -- without this, a renamed product's events keep
        # showing the old name even though forecast_outputs.product above
        # was just updated.
        events_rows_updated = sync_product_in_events_payload(
            cursor,
            payload.ta_name,
            payload.product_name,
            new_name=payload.new_product_name,
        )

        # --------------------------------------------------
        # Keep the saved filter selection in sync
        # --------------------------------------------------
        # get_market_event_filters restores selected_filter.products straight
        # out of user_configurations -- without this, renaming the product
        # that's currently the saved selection leaves that row pointing at a
        # product_id that no longer exists in product_master.
        cursor.execute(
            """
            UPDATE raw_hiv_prep.user_configurations
            SET product = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE ta_name = %s
              AND UPPER(TRIM(product)) = UPPER(TRIM(%s))
            """,
            (
                payload.new_product_name,
                payload.ta_name,
                payload.product_name
            )
        )
        user_configurations_rows_updated = cursor.rowcount

        db.commit()

        return {
            "message": "Product updated successfully",
            "product": {
                "product_id": updated_product["product_name"],  # product_id same as product_name
                "product_name": updated_product["product_name"],
                "date_added": (
                    updated_product["date_added"].strftime("%Y-%m-%d")
                    if updated_product["date_added"]
                    else None
                ),
                "added_by": updated_product["added_by"],
                "modified_by": updated_product["modified_by"]
            },
            "events_payload_rows_updated": events_rows_updated,
            "user_configurations_rows_updated": user_configurations_rows_updated
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()


# @router.delete("/products")
# def delete_product(
#     payload: DeleteProductRequest,
#     db=Depends(get_connection)
# ):
#     cursor = db.cursor(cursor_factory=RealDictCursor)

#     try:
#         # Check if product exists
#         cursor.execute(
#             """
#             SELECT product_id
#             FROM raw_hiv_prep.product_master_hiv_prep
#             WHERE ta_name = %s
#               AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
#             """,
#             (
#                 payload.ta_name,
#                 payload.product_name
#             )
#         )

#         product = cursor.fetchone()

#         if not product:
#             raise HTTPException(
#                 status_code=404,
#                 detail="Product not found."
#             )

#         # Delete product
#         cursor.execute(
#             """
#             DELETE FROM raw_hiv_prep.product_master_hiv_prep
#             WHERE ta_name = %s
#               AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
#             """,
#             (
#                 payload.ta_name,
#                 payload.product_name
#             )
#         )

#         db.commit()

#         return {
#             "message": "Product deleted successfully",
#             "deleted_product": payload.product_name
#         }

#     except Exception:
#         db.rollback()
#         raise

#     finally:
#         cursor.close()


PRODUCT_MASTER_TABLE = "raw_hiv_prep.product_master_hiv_prep"
FORECAST_TABLE = "raw_hiv_prep.forecast_outputs"

SHARE_DECIMALS = 2


class DeleteProductRequest(BaseModel):
    ta_name: str
    product_name: str
    # Limit the removal to one scenario; omit to remove the product
    # everywhere, which is what "delete the product" normally means.
    scenario_name: Optional[str] = None


def _parse_forecast_data(raw) -> dict:
    if isinstance(raw, str):
        return json.loads(raw) if raw.strip() else {}
    return raw or {}


def normalize_shares_after_delete(cursor, ta_name: str,
                                  scenarios: Optional[List[str]] = None) -> int:
    """Rescale each group of sibling product shares back to 100.

    Deleting a product that held share leaves its siblings summing to less
    than 100. Every view reading these rows then shows a market that
    doesn't add up, and any view that normalizes children to their parent
    inflates whoever is left by an arbitrary amount instead.

    A "group" is one (scenario, metric, market, source_of_market): the set
    of products measured against the same whole. That covers per-market
    product shares, per-source shares, AND the market='ALL' portfolio
    shares, since all three are groups whose members sum to 100.

    market_share_pm is deliberately untouched -- it splits ONE product
    across markets, so removing a different product doesn't disturb it.

    Returns the number of rows rewritten.
    """
    query = f"""
        SELECT id, scenario_name, metric, market, product,
               COALESCE(NULLIF(source_of_market, ''), 'ALL') AS som,
               forecast_data
        FROM {FORECAST_TABLE}
        WHERE ta_name = %s
          AND metric = 'market_share'
          AND product IS NOT NULL
          AND UPPER(TRIM(product)) <> 'ALL'
    """
    params: List = [ta_name]

    if scenarios:
        query += " AND scenario_name = ANY(%s)"
        params.append(list(scenarios))

    cursor.execute(query, params)
    rows = cursor.fetchall()

    groups = {}
    for row in rows:
        key = (row["scenario_name"], row["metric"], row["market"], row["som"])
        groups.setdefault(key, []).append(row)

    rewritten = 0

    for key, members in groups.items():

        parsed = [
            (row, _parse_forecast_data(row["forecast_data"]))
            for row in members
        ]

        for field in ("train_values", "forecast_values"):

            length = max(
                (len(data.get(field) or []) for _, data in parsed),
                default=0,
            )

            for index in range(length):

                total = 0.0
                for _, data in parsed:
                    values = data.get(field) or []
                    if index < len(values):
                        total += float(values[index] or 0)

                # Every sibling is zero at this index -- nothing to scale,
                # and no basis for inventing a split.
                if total <= 0:
                    continue

                # Already sums to 100 (within storage rounding).
                if abs(total - 100.0) <= 0.01:
                    continue

                factor = 100.0 / total
                for _, data in parsed:
                    values = data.get(field) or []
                    if index < len(values):
                        values[index] = round(
                            float(values[index] or 0) * factor,
                            SHARE_DECIMALS,
                        )

        for row, data in parsed:
            cursor.execute(
                f"""
                UPDATE {FORECAST_TABLE}
                SET forecast_data = %s::jsonb,
                    updated_at = now()
                WHERE id = %s
                """,
                [json.dumps(data), row["id"]],
            )
            rewritten += cursor.rowcount

    return rewritten


@router.delete("/products")
def delete_product(
    payload: DeleteProductRequest,
    db=Depends(get_connection)
):
    cursor = db.cursor(cursor_factory=RealDictCursor)

    try:
        # Check if product exists
        cursor.execute(
            f"""
            SELECT product_id
            FROM {PRODUCT_MASTER_TABLE}
            WHERE ta_name = %s
              AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
            """,
            (payload.ta_name, payload.product_name),
        )

        product = cursor.fetchone()

        if not product:
            raise HTTPException(
                status_code=404,
                detail="Product not found.",
            )

        # The name as stored, not as typed -- forecast_outputs.product holds
        # the same value as product_master.product_id, and the lookup above
        # was case-insensitive.
        stored_name = product["product_id"]

        # --------------------------------------------------
        # Forecast rows
        # --------------------------------------------------
        # Deleted first and in the SAME transaction as the master row.
        # All metrics, markets, sources and scenarios go -- including Base,
        # or the product reappears the moment anyone runs a calculation,
        # since seeding models new products on whatever rows already exist.
        forecast_params = [payload.ta_name, stored_name]
        scenario_clause = ""
        if payload.scenario_name:
            scenario_clause = "AND scenario_name = %s"
            forecast_params.append(payload.scenario_name)

        cursor.execute(
            f"""
            DELETE FROM {FORECAST_TABLE}
            WHERE ta_name = %s
              AND UPPER(TRIM(product)) = UPPER(TRIM(%s))
              {scenario_clause}
            """,
            forecast_params,
        )
        forecast_rows_deleted = cursor.rowcount

        # --------------------------------------------------
        # Renormalize the survivors
        # --------------------------------------------------
        # The deleted product's share has to go somewhere: without this,
        # every group it belonged to now sums to less than 100.
        shares_renormalized = 0
        if forecast_rows_deleted:
            shares_renormalized = normalize_shares_after_delete(
                cursor,
                payload.ta_name,
                [payload.scenario_name] if payload.scenario_name else None,
            )

        # --------------------------------------------------
        # Master row
        # --------------------------------------------------
        # Kept when the caller scoped the delete to one scenario -- the
        # product still exists, it just no longer participates there.
        master_rows_deleted = 0
        if not payload.scenario_name:
            cursor.execute(
                f"""
                DELETE FROM {PRODUCT_MASTER_TABLE}
                WHERE ta_name = %s
                  AND UPPER(TRIM(product_id)) = UPPER(TRIM(%s))
                """,
                (payload.ta_name, payload.product_name),
            )
            master_rows_deleted = cursor.rowcount

        # --------------------------------------------------
        # Saved market/product events
        # --------------------------------------------------
        # apply_market_event_filters reads product names back out of
        # events_payload -- without this, a deleted product keeps showing
        # up in event rows even though its forecast/master rows are gone.
        # Scoped the same way the forecast-row delete above is: one
        # scenario when the caller asked for one, every scenario otherwise.
        events_rows_updated = sync_product_in_events_payload(
            cursor,
            payload.ta_name,
            stored_name,
            new_name=None,
            scenario_name=payload.scenario_name,
        )

        # --------------------------------------------------
        # Saved filter selection
        # --------------------------------------------------
        # get_market_event_filters restores selected_filter.products straight
        # out of user_configurations -- without this, deleting the product
        # that's currently the saved selection leaves that row pointing at a
        # product_id that no longer exists. Only relevant when the master row
        # itself was actually removed (master_rows_deleted): a scenario-scoped
        # delete leaves the product registered, so the saved selection is
        # still valid and shouldn't be disturbed.
        user_configurations_rows_updated = 0
        if master_rows_deleted:
            cursor.execute(
                f"""
                SELECT product_id
                FROM {PRODUCT_MASTER_TABLE}
                WHERE ta_name = %s
                  AND product_id IS NOT NULL
                  AND UPPER(TRIM(product_id)) <> 'ALL'
                ORDER BY product_id
                LIMIT 1
                """,
                (payload.ta_name,),
            )
            fallback_row = cursor.fetchone()
            # None when no products remain at all -- clears the stale
            # selection rather than leaving it pointing at nothing.
            fallback_product = fallback_row["product_id"] if fallback_row else None

            cursor.execute(
                """
                UPDATE raw_hiv_prep.user_configurations
                SET product = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE ta_name = %s
                  AND UPPER(TRIM(product)) = UPPER(TRIM(%s))
                """,
                (fallback_product, payload.ta_name, stored_name),
            )
            user_configurations_rows_updated = cursor.rowcount

        db.commit()

        return {
            "message": "Product deleted successfully",
            "deleted_product": stored_name,
            "scenario_name": payload.scenario_name,
            "forecast_rows_deleted": forecast_rows_deleted,
            "master_rows_deleted": master_rows_deleted,
            "share_rows_renormalized": shares_renormalized,
            "events_payload_rows_updated": events_rows_updated,
            "user_configurations_rows_updated": user_configurations_rows_updated,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        cursor.close()