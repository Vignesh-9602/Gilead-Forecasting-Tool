from fastapi import HTTPException
from app.hiv_treat.routes.market_events_models import *
from app.hiv_treat.services.calculation_tree_market_events import *
from app.hiv_treat.services.response_builder_market_events import *
from app.hiv_treat.services.generic_builders_market_events import *
from app.hiv_treat.services.market_event_helpers import *
import json

def resolve_edited_indexes(
    tree: dict,
    payload: EditSaveRequest,
) -> list[int]:
    months = tree["months"]

    invalid = [
        header
        for header in payload.edited_headers
        if header not in months
    ]

    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid edited headers",
                "headers": invalid,
            },
        )

    outside_range = [
        header
        for header in payload.edited_headers
        if not (
            payload.selected_filter.start_date
            <= header
            <= payload.selected_filter.end_date
        )
    ]

    if outside_range:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Edited headers are outside the selected range",
                "headers": outside_range,
            },
        )

    return [
        months.index(header)
        for header in payload.edited_headers
    ]

def validate_edited_rows(
    rows: list[EditedTableRow],
    expected_length: int,
):
    labels = set()

    for row in rows:
        if row.label in labels:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate row label {row.label!r}",
            )

        labels.add(row.label)

        if len(row.values) != expected_length:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Row {row.label!r} contains "
                    f"{len(row.values)} values; "
                    f"expected {expected_length}"
                ),
            )

        if any(value < 0 for value in row.values):
            raise HTTPException(
                status_code=400,
                detail=f"Row {row.label!r} contains negative values",
            )

        validate_edited_rows(
            row.children,
            expected_length,
        )

def build_market_product_volume_matrix(tree: dict) -> dict:
    month_count = len(tree["months"])

    matrix = {
        market_name: {
            product_name: [0.0] * month_count
            for product_name in tree["products"]
        }
        for market_name in tree["markets"]
    }

    for market_name, market in tree["markets"].items():
        for source in market["sources"].values():
            for product_name, product in source["products"].items():
                matrix[market_name].setdefault(
                    product_name,
                    [0.0] * month_count,
                )

                matrix[market_name][product_name] = [
                    round(current + value, 6)
                    for current, value in zip(
                        matrix[market_name][product_name],
                        product["volume"],
                    )
                ]

    return matrix

def edited_value_to_volume(
    value: float,
    selected_metric: str,
    overall_volume: float,
) -> float:
    if selected_metric == "market_volume":
        return round(float(value), 6)

    return round(
        overall_volume * float(value) / 100,
        6,
    )

def normalize_distribution(
    current_values: list[float],
    target_total: float,
    locked_values: dict[int, float] | None = None,
) -> list[float]:
    locked_values = locked_values or {}

    result = [float(value) for value in current_values]

    locked_total = sum(locked_values.values())
    tolerance = 0.0001

    if locked_total > target_total + tolerance:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Edited total {locked_total} exceeds "
                f"required total {target_total}"
            ),
        )

    for index, value in locked_values.items():
        result[index] = round(value, 6)

    unlocked_indexes = [
        index
        for index in range(len(result))
        if index not in locked_values
    ]

    remaining = target_total - locked_total

    if not unlocked_indexes:
        if abs(remaining) > tolerance:
            raise HTTPException(
                status_code=400,
                detail="Edited child rows do not equal the parent total",
            )

        return result

    current_unlocked_total = sum(
        current_values[index]
        for index in unlocked_indexes
    )

    if current_unlocked_total > 0:
        for index in unlocked_indexes:
            ratio = current_values[index] / current_unlocked_total
            result[index] = round(remaining * ratio, 6)
    else:
        equal_value = remaining / len(unlocked_indexes)

        for index in unlocked_indexes:
            result[index] = round(equal_value, 6)

    difference = round(target_total - sum(result), 6)

    if difference:
        result[unlocked_indexes[-1]] = round(
            result[unlocked_indexes[-1]] + difference,
            6,
        )

    return result

def rows_by_label(rows: list[EditedTableRow]) -> dict:
    return {
        row.label: row
        for row in rows
    }

def apply_market_event_edits(
    tree: dict,
    matrix: dict,
    payload: EditSaveRequest,
    edited_indexes: list[int],
):
    markets = list(tree["markets"])
    products = list(tree["products"])
    overall_volumes = tree["overall"]["volume"]

    edited_product_rows = rows_by_label(
        payload.edited_table_rows
    )

    for value_position, month_index in enumerate(edited_indexes):
        overall_volume = overall_volumes[month_index]

        current_product_totals = [
            sum(
                matrix[market_name][product_name][month_index]
                for market_name in markets
            )
            for product_name in products
        ]

        locked_product_totals = {}

        for product_position, product_name in enumerate(products):
            product_row = edited_product_rows.get(product_name)

            if product_row is None or not product_row.editable:
                continue

            locked_product_totals[product_position] = (
                edited_value_to_volume(
                    product_row.values[value_position],
                    payload.selected_metric,
                    overall_volume,
                )
            )

        normalized_product_totals = normalize_distribution(
            current_values=current_product_totals,
            target_total=overall_volume,
            locked_values=locked_product_totals,
        )

        for product_position, product_name in enumerate(products):
            target_product_total = normalized_product_totals[
                product_position
            ]

            current_market_values = [
                matrix[market_name][product_name][month_index]
                for market_name in markets
            ]

            locked_market_values = {}
            product_row = edited_product_rows.get(product_name)

            if (
                product_row is not None
                and payload.selected_table_view
                == "product_market_level"
            ):
                child_rows = rows_by_label(product_row.children)

                for market_position, market_name in enumerate(markets):
                    child = child_rows.get(market_name)

                    if child is None or not child.editable:
                        continue

                    locked_market_values[market_position] = (
                        edited_value_to_volume(
                            child.values[value_position],
                            payload.selected_metric,
                            overall_volume,
                        )
                    )

            normalized_market_values = normalize_distribution(
                current_values=current_market_values,
                target_total=target_product_total,
                locked_values=locked_market_values,
            )

            for market_position, market_name in enumerate(markets):
                matrix[market_name][product_name][month_index] = (
                    normalized_market_values[market_position]
                )

def apply_product_event_edits(
    tree: dict,
    matrix: dict,
    payload: EditSaveRequest,
    edited_indexes: list[int],
):
    markets = list(tree["markets"])
    products = list(tree["products"])
    overall_volumes = tree["overall"]["volume"]

    edited_market_rows = rows_by_label(
        payload.edited_table_rows
    )

    for value_position, month_index in enumerate(edited_indexes):
        overall_volume = overall_volumes[month_index]

        current_market_totals = [
            sum(
                matrix[market_name][product_name][month_index]
                for product_name in products
            )
            for market_name in markets
        ]

        locked_market_totals = {}

        for market_position, market_name in enumerate(markets):
            market_row = edited_market_rows.get(market_name)

            if market_row is None or not market_row.editable:
                continue

            locked_market_totals[market_position] = (
                edited_value_to_volume(
                    market_row.values[value_position],
                    payload.selected_metric,
                    overall_volume,
                )
            )

        normalized_market_totals = normalize_distribution(
            current_values=current_market_totals,
            target_total=overall_volume,
            locked_values=locked_market_totals,
        )

        for market_position, market_name in enumerate(markets):
            target_market_total = normalized_market_totals[
                market_position
            ]

            current_product_values = [
                matrix[market_name][product_name][month_index]
                for product_name in products
            ]

            locked_product_values = {}
            market_row = edited_market_rows.get(market_name)

            if (
                market_row is not None
                and payload.selected_table_view
                == "market_product_level"
            ):
                child_rows = rows_by_label(market_row.children)

                for product_position, product_name in enumerate(products):
                    child = child_rows.get(product_name)

                    if child is None or not child.editable:
                        continue

                    locked_product_values[product_position] = (
                        edited_value_to_volume(
                            child.values[value_position],
                            payload.selected_metric,
                            overall_volume,
                        )
                    )

            normalized_product_values = normalize_distribution(
                current_values=current_product_values,
                target_total=target_market_total,
                locked_values=locked_product_values,
            )

            for product_position, product_name in enumerate(products):
                matrix[market_name][product_name][month_index] = (
                    normalized_product_values[product_position]
                )

def apply_matrix_to_tree(
    tree: dict,
    matrix: dict,
    edited_indexes: list[int],
):
    products = list(tree["products"])

    for market_name, market in tree["markets"].items():
        sources = list(market["sources"].values())

        for product_name in products:
            for month_index in edited_indexes:
                target_volume = matrix[
                    market_name
                ][product_name][month_index]

                product_nodes = [
                    source["products"][product_name]
                    for source in sources
                    if product_name in source["products"]
                ]

                if target_volume > 0 and not product_nodes:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"No source-product row exists for "
                            f"{market_name}/{product_name}"
                        ),
                    )

                if not product_nodes:
                    continue

                current_source_values = [
                    node["volume"][month_index]
                    for node in product_nodes
                ]

                allocated = normalize_distribution(
                    current_values=current_source_values,
                    target_total=target_volume,
                )

                for node, value in zip(product_nodes, allocated):
                    node["volume"][month_index] = value

def calculate_percentage(
    numerator: float,
    denominator: float,
) -> float:
    if not denominator:
        return 0.0

    return round(
        numerator / denominator * 100,
        6,
    )

def recompute_tree(
    tree: dict,
    edited_indexes: list[int],
):
    overall_volumes = tree["overall"]["volume"]

    for month_index in edited_indexes:
        for market in tree["markets"].values():
            for source in market["sources"].values():
                source_volume = sum(
                    product["volume"][month_index]
                    for product in source["products"].values()
                )

                source["volume"][month_index] = round(
                    source_volume,
                    6,
                )

                for product in source["products"].values():
                    product["share"][month_index] = (
                        calculate_percentage(
                            product["volume"][month_index],
                            source_volume,
                        )
                    )

        for market in tree["markets"].values():
            market_volume = sum(
                source["volume"][month_index]
                for source in market["sources"].values()
            )

            market["volume"][month_index] = round(
                market_volume,
                6,
            )

            market["share"][month_index] = calculate_percentage(
                market_volume,
                overall_volumes[month_index],
            )

            for source in market["sources"].values():
                source["share"][month_index] = (
                    calculate_percentage(
                        source["volume"][month_index],
                        market_volume,
                    )
                )

    aggregate_products(tree)




def build_updated_forecast_data(
    original_forecast_data: dict,
    values: list[float],
) -> dict:
    months = original_forecast_data["months"]
    forecast_start_index = original_forecast_data[
        "forecast_start_index"
    ]

    if len(values) != len(months):
        raise ValueError(
            "Calculated values do not match the forecast timeline"
        )

    return {
        **original_forecast_data,
        "train_values": [
            round(value, 6)
            for value in values[:forecast_start_index]
        ],
        "forecast_values": [
            round(value, 6)
            for value in values[forecast_start_index:]
        ],
    }

def upsert_forecast_output(
    cursor,
    *,
    ta_name: str,
    scenario_name: str,
    metric: str,
    market: str,
    source_of_market: str | None,
    product: str,
    forecast_data: dict,
):
    serialized = json.dumps(forecast_data)

    cursor.execute(
        """
        UPDATE raw_hiv_treat.forecast_outputs
        SET forecast_data = %s::jsonb
        WHERE ta_name = %s
          AND scenario_name = %s
          AND metric = %s
          AND market = %s
          AND source_of_market IS NOT DISTINCT FROM %s
          AND product = %s
        """,
        (
            serialized,
            ta_name,
            scenario_name,
            metric,
            market,
            source_of_market,
            product,
        ),
    )

    if cursor.rowcount > 0:
        return

    cursor.execute(
        """
        INSERT INTO raw_hiv_treat.forecast_outputs (
            ta_name,
            scenario_name,
            metric,
            market,
            source_of_market,
            product,
            forecast_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            ta_name,
            scenario_name,
            metric,
            market,
            source_of_market,
            product,
            serialized,
        ),
    )

def save_tree_to_forecast_outputs(
    cursor,
    *,
    tree: dict,
    original_metrics: dict,
    ta_name: str,
    scenario_name: str,
):
    original_share_rows = {
        (
            row["market"],
            row["source_of_market"],
            row["product"],
        ): row["forecast_data"]
        for row in original_metrics.get("market_share", [])
    }

    if not original_share_rows:
        raise ValueError("No market-share rows were found")

    default_template = next(iter(original_share_rows.values()))

    for market_name, market in tree["markets"].items():
        market_template = original_share_rows.get(
            (market_name, None, "ALL"),
            default_template,
        )

        upsert_forecast_output(
            cursor,
            ta_name=ta_name,
            scenario_name=scenario_name,
            metric="market_share",
            market=market_name,
            source_of_market=None,
            product="ALL",
            forecast_data=build_updated_forecast_data(
                market_template,
                market["share"],
            ),
        )

        for source_name, source in market["sources"].items():
            source_template = original_share_rows.get(
                (market_name, source_name, "ALL"),
                market_template,
            )

            upsert_forecast_output(
                cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                metric="market_share",
                market=market_name,
                source_of_market=source_name,
                product="ALL",
                forecast_data=build_updated_forecast_data(
                    source_template,
                    source["share"],
                ),
            )

            for product_name, product in source["products"].items():
                product_template = original_share_rows.get(
                    (
                        market_name,
                        source_name,
                        product_name,
                    ),
                    source_template,
                )

                upsert_forecast_output(
                    cursor,
                    ta_name=ta_name,
                    scenario_name=scenario_name,
                    metric="market_share",
                    market=market_name,
                    source_of_market=source_name,
                    product=product_name,
                    forecast_data=build_updated_forecast_data(
                        product_template,
                        product["share"],
                    ),
                )

    volume_rows = original_metrics.get("market_volume", [])

    if not volume_rows:
        raise ValueError("No market-volume row was found")

    volume_row = volume_rows[0]

    upsert_forecast_output(
        cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
        metric="market_volume",
        market=volume_row["market"],
        source_of_market=volume_row["source_of_market"],
        product=volume_row["product"],
        forecast_data=build_updated_forecast_data(
            volume_row["forecast_data"],
            tree["overall"]["volume"],
        ),
    )

def build_apply_filters_response(
    cursor,
    *,
    ta_name: str,
    selected_filter: dict,
) -> dict:
    scenario_name = selected_filter["scenario_name"]

    metadata = load_metadata(
        cursor=cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
        start_date=selected_filter["start_date"],
        end_date=selected_filter["end_date"],
    )

    metrics = load_forecast_outputs(
        cursor=cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
    )

    tree = build_calculation_tree(metrics)

    tree = filter_tree_by_date(
        tree,
        selected_filter["start_date"],
        selected_filter["end_date"],
    )

    return {
        "ta_name": ta_name,
        "available_scenarios": metadata["available_scenarios"],
        "available_months": metadata["available_months"],
        "metric_filters": metadata["metric_filters"],
        "forecast_start_date": metadata["forecast_start_date"],
        "selected_filter": selected_filter,
        "event_tabs": {
            "overall_event": build_overall_event(tree),
            "market_event": build_market_event(tree),
            "product_event": build_product_event(tree),
        },
    }