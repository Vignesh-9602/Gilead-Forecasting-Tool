from fastapi import HTTPException
from app.hiv_treat.routes.market_events_models import *
from app.hiv_treat.services.calculation_tree_market_events import *
from app.hiv_treat.services.response_builder_market_events import *
from app.hiv_treat.services.generic_builders_market_events import *
from app.hiv_treat.services.market_event_helpers import *
import json

def resolve_selected_months(
    tree: dict,
    payload: EditSaveRequest,
) -> tuple[list[str], list[int]]:
    """
    Resolve every month between selected start_date and end_date.

    The order of row.values must match this chronological order.
    """

    all_months = tree.get("months", [])

    if not all_months:
        raise HTTPException(
            status_code=400,
            detail="The forecast contains no months.",
        )

    start_date = payload.selected_filter.start_date
    end_date = payload.selected_filter.end_date

    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date.",
        )

    selected_months = [
        month
        for month in all_months
        if start_date <= month <= end_date
    ]

    if not selected_months:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected date range contains no available "
                "forecast months."
            ),
        )

    selected_indexes = [
        all_months.index(month)
        for month in selected_months
    ]

    return selected_months, selected_indexes

def validate_edited_rows(
    rows: list[EditedTableRow],
    expected_value_count: int,
):
    """
    Validate every row recursively.

    Each row must contain one value for every selected month.
    """

    labels_at_level: set[str] = set()

    for row in rows:

        if row.label in labels_at_level:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate row label {row.label!r} "
                    "at the same hierarchy level."
                ),
            )

        labels_at_level.add(row.label)

        if len(row.values) != expected_value_count:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Row {row.label!r} contains "
                    f"{len(row.values)} values, but the selected "
                    f"date range requires {expected_value_count}."
                ),
            )

        for value in row.values:
            if value is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Row {row.label!r} contains a null value."
                    ),
                )

            if value < 0:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Row {row.label!r} contains a negative value."
                    ),
                )

        validate_edited_rows(
            rows=row.children,
            expected_value_count=expected_value_count,
        )

def validate_row_labels(
    tree: dict,
    payload: EditSaveRequest,
):
    """
    Validate submitted row hierarchy for the selected tab/view.

    Current structures:

    market_event
        market_level:
            Market

        product_market_level:
            Product
                Market

    product_event
        product_level:
            Product

        market_product_level:
            Market
                Product
    """

    market_names = set(tree["markets"])
    product_names = set(tree["products"])

    for row in payload.edited_table_rows:

        if row.label == "Overall":
            # Overall is always read-only.
            continue

        # =================================================
        # MARKET EVENT
        # =================================================

        if payload.selected_tab == "market_event":

            # ---------------------------------------------
            # Market Level
            #
            # Overall
            # Retail
            # Non-retail
            # ---------------------------------------------

            if payload.selected_table_view == "market_level":

                if row.label not in market_names:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Unexpected top-level row "
                            f"{row.label!r} for "
                            "'market_event/market_level'."
                        ),
                    )

                if row.children:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Row {row.label!r} must not contain "
                            "children for market_level."
                        ),
                    )

                continue

            # ---------------------------------------------
            # Product-Market Level
            #
            # Overall
            # Product
            #     Market
            # ---------------------------------------------

            if (
                payload.selected_table_view
                == "product_market_level"
            ):
                if row.label not in product_names:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Unexpected top-level row "
                            f"{row.label!r} for "
                            "'market_event/product_market_level'."
                        ),
                    )

                child_labels = set()

                for child in row.children:

                    if child.label in child_labels:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Duplicate child row "
                                f"{child.label!r} under "
                                f"{row.label!r}."
                            ),
                        )

                    child_labels.add(child.label)

                    if child.label not in market_names:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Unexpected child row "
                                f"{child.label!r} under product "
                                f"{row.label!r}. Expected a market."
                            ),
                        )

                    if child.children:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Child row {child.label!r} must "
                                "not contain another child level."
                            ),
                        )

                continue

        # =================================================
        # PRODUCT EVENT
        # =================================================

        if payload.selected_tab == "product_event":

            # ---------------------------------------------
            # Product Level
            #
            # Overall
            # Biktarvy
            # Descovy
            # Truvada
            # ---------------------------------------------

            if payload.selected_table_view == "product_level":

                if row.label not in product_names:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Unexpected top-level row "
                            f"{row.label!r} for "
                            "'product_event/product_level'."
                        ),
                    )

                if row.children:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Row {row.label!r} must not contain "
                            "children for product_level."
                        ),
                    )

                continue

            # ---------------------------------------------
            # Market-Product Level
            #
            # Overall
            # Market
            #     Product
            # ---------------------------------------------

            if (
                payload.selected_table_view
                == "market_product_level"
            ):
                if row.label not in market_names:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Unexpected top-level row "
                            f"{row.label!r} for "
                            "'product_event/market_product_level'."
                        ),
                    )

                child_labels = set()

                for child in row.children:

                    if child.label in child_labels:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Duplicate child row "
                                f"{child.label!r} under "
                                f"{row.label!r}."
                            ),
                        )

                    child_labels.add(child.label)

                    if child.label not in product_names:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Unexpected child row "
                                f"{child.label!r} under market "
                                f"{row.label!r}. Expected a product."
                            ),
                        )

                    if child.children:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Child row {child.label!r} must "
                                "not contain another child level."
                            ),
                        )

                continue

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported tab/view combination: "
                f"{payload.selected_tab}/"
                f"{payload.selected_table_view}."
            ),
        )
        
def build_market_product_volume_matrix(
    tree: dict,
) -> dict[str, dict[str, list[float]]]:
    """
    Aggregate source-product volumes into market-product volumes.
    """

    month_count = len(tree["months"])
    product_names = list(tree["products"])

    matrix = {
        market_name: {
            product_name: [0.0] * month_count
            for product_name in product_names
        }
        for market_name in tree["markets"]
    }

    for market_name, market in tree["markets"].items():

        for source in market.get("sources", {}).values():

            for product_name, product in source.get(
                "products",
                {},
            ).items():

                matrix[market_name].setdefault(
                    product_name,
                    [0.0] * month_count,
                )

                product_volumes = product.get(
                    "volume",
                    [0.0] * month_count,
                )

                matrix[market_name][product_name] = [
                    round(current + value, 6)
                    for current, value in zip(
                        matrix[market_name][product_name],
                        product_volumes,
                    )
                ]

    return matrix


def rows_by_label(
    rows: list[EditedTableRow],
) -> dict[str, EditedTableRow]:
    return {
        row.label: row
        for row in rows
    }

def edited_value_to_volume(
    value: float,
    selected_metric: str,
    overall_volume: float,
) -> float:
    """
    Convert edited UI value to the canonical volume representation.
    """

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
    """
    Normalize values to target_total.

    locked_values:
        {
            position: edited value
        }

    Edited values remain unchanged. Unedited values absorb the
    remaining total according to their existing proportions.
    """

    locked_values = locked_values or {}

    result = [
        float(value)
        for value in current_values
    ]

    tolerance = 0.0001

    locked_total = sum(
        locked_values.values()
    )

    if locked_total > target_total + tolerance:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Edited values total {round(locked_total, 6)}, "
                f"which exceeds the required parent total "
                f"{round(target_total, 6)}."
            ),
        )

    for position, value in locked_values.items():

        if position < 0 or position >= len(result):
            raise HTTPException(
                status_code=500,
                detail="Invalid normalization position.",
            )

        result[position] = round(value, 6)

    unlocked_positions = [
        position
        for position in range(len(result))
        if position not in locked_values
    ]

    remaining_total = target_total - locked_total

    if not unlocked_positions:

        if abs(remaining_total) > tolerance:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The edited child values do not add up "
                    "to the edited parent value."
                ),
            )

        return result

    current_unlocked_total = sum(
        current_values[position]
        for position in unlocked_positions
    )

    if current_unlocked_total > 0:

        for position in unlocked_positions:

            proportion = (
                current_values[position]
                / current_unlocked_total
            )

            result[position] = round(
                remaining_total * proportion,
                6,
            )

    else:

        equal_value = (
            remaining_total
            / len(unlocked_positions)
        )

        for position in unlocked_positions:
            result[position] = round(
                equal_value,
                6,
            )

    # Correct rounding difference on the final unlocked item.
    difference = round(
        target_total - sum(result),
        6,
    )

    if difference:
        final_position = unlocked_positions[-1]

        result[final_position] = round(
            result[final_position] + difference,
            6,
        )

    return result

def apply_market_event_edits(
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    """
    Apply edits made from Market Event.

    Supported views
    ---------------
    market_level:
        Overall
        Market

    product_market_level:
        Overall
        Product
            Market

    The canonical matrix is:

        matrix[market][product][month_index] = volume

    Notes
    -----
    - Overall is never edited.
    - Only values that differ from the current calculated value are
      treated as actual edits.
    - This is important because the frontend sends the full table,
      not only the changed cells.
    """

    markets = list(tree["markets"])
    products = list(tree["products"])

    overall_volumes = tree["overall"]["volume"]

    submitted_rows = rows_by_label(
        payload.edited_table_rows
    )

    tolerance = 0.0001

    # =====================================================
    # MARKET LEVEL
    #
    # Overall
    # Retail
    # Non-retail
    # =====================================================

    if payload.selected_table_view == "market_level":

        for value_position, month_index in enumerate(
            selected_indexes
        ):
            overall_volume = overall_volumes[month_index]

            current_market_totals = [
                sum(
                    matrix[market_name][product_name][month_index]
                    for product_name in products
                )
                for market_name in markets
            ]

            locked_market_totals: dict[int, float] = {}

            for market_position, market_name in enumerate(
                markets
            ):
                market_row = submitted_rows.get(market_name)

                if market_row is None:
                    continue

                submitted_volume = edited_value_to_volume(
                    value=market_row.values[value_position],
                    selected_metric=payload.selected_metric,
                    overall_volume=overall_volume,
                )

                current_volume = current_market_totals[
                    market_position
                ]

                # The complete table is submitted.
                # Treat the value as edited only when it changed.
                if abs(
                    submitted_volume - current_volume
                ) <= tolerance:
                    continue

                locked_market_totals[
                    market_position
                ] = submitted_volume

            normalized_market_totals = normalize_distribution(
                current_values=current_market_totals,
                target_total=overall_volume,
                locked_values=locked_market_totals,
            )

            # Preserve the existing product split inside each market.
            for market_position, market_name in enumerate(
                markets
            ):
                target_market_total = (
                    normalized_market_totals[
                        market_position
                    ]
                )

                current_product_values = [
                    matrix[market_name][product_name][month_index]
                    for product_name in products
                ]

                normalized_product_values = normalize_distribution(
                    current_values=current_product_values,
                    target_total=target_market_total,
                )

                for product_position, product_name in enumerate(
                    products
                ):
                    matrix[market_name][product_name][
                        month_index
                    ] = normalized_product_values[
                        product_position
                    ]

        return

    # =====================================================
    # PRODUCT-MARKET LEVEL
    #
    # Overall
    # Product
    #     Market
    # =====================================================

    if payload.selected_table_view == "product_market_level":

        explicitly_edited_rows = set(
            payload.edited_rows or []
        )

        for value_position, month_index in enumerate(
            selected_indexes
        ):
            overall_volume = overall_volumes[month_index]

            # Current total for every product across markets.
            current_product_totals = [
                sum(
                    matrix[market_name][product_name][month_index]
                    for market_name in markets
                )
                for product_name in products
            ]

            # Product totals that must remain fixed during normalization.
            locked_product_totals: dict[int, float] = {}

            # Edited market children that must remain fixed.
            edited_market_values_by_product: dict[
                int,
                dict[int, float],
            ] = {}

            for product_position, product_name in enumerate(
                products
            ):
                product_row = submitted_rows.get(product_name)

                if product_row is None:
                    continue

                market_children = rows_by_label(
                    product_row.children
                )

                locked_market_values: dict[int, float] = {}

                # ============================================
                # Detect explicitly edited market children
                # ============================================

                for market_position, market_name in enumerate(
                    markets
                ):
                    child_row = market_children.get(market_name)

                    if child_row is None:
                        continue

                    child_path = (
                        f"{product_name}|{market_name}"
                    )

                    # Lock only the row actually edited by the user.
                    if child_path not in explicitly_edited_rows:
                        continue

                    edited_child_volume = (
                        edited_value_to_volume(
                            value=child_row.values[
                                value_position
                            ],
                            selected_metric=(
                                payload.selected_metric
                            ),
                            overall_volume=overall_volume,
                        )
                    )

                    locked_market_values[
                        market_position
                    ] = edited_child_volume

                if locked_market_values:
                    edited_market_values_by_product[
                        product_position
                    ] = locked_market_values

                # ============================================
                # Determine the new product total
                # ============================================

                product_path = product_name

                if product_path in explicitly_edited_rows:
                    # Parent itself was edited.
                    submitted_product_total = (
                        edited_value_to_volume(
                            value=product_row.values[
                                value_position
                            ],
                            selected_metric=(
                                payload.selected_metric
                            ),
                            overall_volume=overall_volume,
                        )
                    )

                    locked_product_totals[
                        product_position
                    ] = submitted_product_total

                elif locked_market_values:
                    # A child was edited, so recompute the parent from:
                    #
                    # edited child values
                    # +
                    # existing untouched child values

                    recomputed_product_total = 0.0

                    for market_position, market_name in enumerate(
                        markets
                    ):
                        if market_position in locked_market_values:
                            recomputed_product_total += (
                                locked_market_values[
                                    market_position
                                ]
                            )
                        else:
                            recomputed_product_total += matrix[
                                market_name
                            ][product_name][month_index]

                    locked_product_totals[
                        product_position
                    ] = round(
                        recomputed_product_total,
                        6,
                    )

            # ================================================
            # Normalize product totals to Overall
            # ================================================

            normalized_product_totals = normalize_distribution(
                current_values=current_product_totals,
                target_total=overall_volume,
                locked_values=locked_product_totals,
            )

            # ================================================
            # Normalize markets within every product
            # ================================================

            for product_position, product_name in enumerate(
                products
            ):
                target_product_total = (
                    normalized_product_totals[
                        product_position
                    ]
                )

                current_market_values = [
                    matrix[market_name][product_name][month_index]
                    for market_name in markets
                ]

                locked_market_values = (
                    edited_market_values_by_product.get(
                        product_position,
                        {},
                    )
                )

                normalized_market_values = (
                    normalize_distribution(
                        current_values=current_market_values,
                        target_total=target_product_total,
                        locked_values=locked_market_values,
                    )
                )

                for market_position, market_name in enumerate(
                    markets
                ):
                    matrix[market_name][product_name][
                        month_index
                    ] = normalized_market_values[
                        market_position
                    ]

        return

    raise HTTPException(
        status_code=400,
        detail=(
            f"Unsupported Market Event table view: "
            f"{payload.selected_table_view!r}."
        ),
    )

def apply_product_event_edits(
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    """
    Apply edits made from Product Event.

    Supported views
    ---------------
    product_level:
        Overall
        Product

    market_product_level:
        Overall
        Market
            Product

    Canonical matrix
    ----------------
        matrix[market][product][month_index] = volume

    The frontend sends the complete visible table. Therefore, only
    rows listed in payload.edited_rows, or values that differ from the
    current calculated values, are treated as explicit edits.
    """

    markets = list(tree["markets"])
    products = list(tree["products"])

    overall_volumes = tree["overall"]["volume"]

    submitted_rows = rows_by_label(
        payload.edited_table_rows
    )

    explicitly_edited_labels = set(
        payload.edited_rows or []
    )

    tolerance = 0.0001

    # =====================================================
    # PRODUCT LEVEL
    #
    # Overall
    # Biktarvy
    # Descovy
    # Truvada
    # =====================================================

    if payload.selected_table_view == "product_level":

        for value_position, month_index in enumerate(
            selected_indexes
        ):
            overall_volume = overall_volumes[month_index]

            current_product_totals = [
                sum(
                    matrix[market_name][product_name][month_index]
                    for market_name in markets
                )
                for product_name in products
            ]

            locked_product_totals: dict[int, float] = {}

            for product_position, product_name in enumerate(
                products
            ):
                product_row = submitted_rows.get(product_name)

                if product_row is None:
                    continue

                submitted_volume = edited_value_to_volume(
                    value=product_row.values[value_position],
                    selected_metric=payload.selected_metric,
                    overall_volume=overall_volume,
                )

                current_volume = current_product_totals[
                    product_position
                ]

                row_was_explicitly_edited = (
                    product_name in explicitly_edited_labels
                )

                value_changed = (
                    abs(submitted_volume - current_volume)
                    > tolerance
                )

                if not row_was_explicitly_edited and not value_changed:
                    continue

                locked_product_totals[
                    product_position
                ] = submitted_volume

            normalized_product_totals = normalize_distribution(
                current_values=current_product_totals,
                target_total=overall_volume,
                locked_values=locked_product_totals,
            )

            # Preserve the existing market split inside each product.
            for product_position, product_name in enumerate(
                products
            ):
                target_product_total = (
                    normalized_product_totals[
                        product_position
                    ]
                )

                current_market_values = [
                    matrix[market_name][product_name][month_index]
                    for market_name in markets
                ]

                normalized_market_values = normalize_distribution(
                    current_values=current_market_values,
                    target_total=target_product_total,
                )

                for market_position, market_name in enumerate(
                    markets
                ):
                    matrix[market_name][product_name][
                        month_index
                    ] = normalized_market_values[
                        market_position
                    ]

        return

    # =====================================================
    # MARKET-PRODUCT LEVEL
    #
    # Overall
    # Non-retail
    #     Biktarvy
    #     Descovy
    #     Truvada
    # Retail
    #     Biktarvy
    #     Descovy
    #     Truvada
    # =====================================================

    if payload.selected_table_view == "market_product_level":

        for value_position, month_index in enumerate(
            selected_indexes
        ):
            overall_volume = overall_volumes[month_index]

            # -------------------------------------------------
            # Current market totals
            # -------------------------------------------------

            current_market_totals = [
                sum(
                    matrix[market_name][product_name][month_index]
                    for product_name in products
                )
                for market_name in markets
            ]

            locked_market_totals: dict[int, float] = {}

            # Explicitly edited products inside each market.
            #
            # {
            #     market_position: {
            #         product_position: edited_volume
            #     }
            # }
            edited_product_values_by_market: dict[
                int,
                dict[int, float],
            ] = {}

            # -------------------------------------------------
            # Detect parent market and child product edits
            # -------------------------------------------------

            for market_position, market_name in enumerate(
                markets
            ):
                market_row = submitted_rows.get(market_name)

                if market_row is None:
                    continue

                current_market_total = current_market_totals[
                    market_position
                ]

                submitted_market_total = edited_value_to_volume(
                    value=market_row.values[value_position],
                    selected_metric=payload.selected_metric,
                    overall_volume=overall_volume,
                )

                market_was_explicitly_edited = (
                    market_name in explicitly_edited_labels
                )

                parent_value_changed = (
                    abs(
                        submitted_market_total
                        - current_market_total
                    )
                    > tolerance
                )

                submitted_children = rows_by_label(
                    market_row.children
                )

                edited_product_values: dict[int, float] = {}

                for product_position, product_name in enumerate(
                    products
                ):
                    product_child = submitted_children.get(
                        product_name
                    )

                    if product_child is None:
                        continue

                    submitted_product_volume = (
                        edited_value_to_volume(
                            value=product_child.values[
                                value_position
                            ],
                            selected_metric=payload.selected_metric,
                            overall_volume=overall_volume,
                        )
                    )

                    current_product_volume = matrix[
                        market_name
                    ][product_name][month_index]

                    product_was_explicitly_edited = (
                        product_name in explicitly_edited_labels
                    )

                    child_value_changed = (
                        abs(
                            submitted_product_volume
                            - current_product_volume
                        )
                        > tolerance
                    )

                    if (
                        product_was_explicitly_edited
                        or child_value_changed
                    ):
                        edited_product_values[
                            product_position
                        ] = submitted_product_volume

                if edited_product_values:
                    edited_product_values_by_market[
                        market_position
                    ] = edited_product_values

                if (
                    market_was_explicitly_edited
                    or parent_value_changed
                ):
                    # Explicit parent value takes priority.
                    locked_market_totals[
                        market_position
                    ] = submitted_market_total

                elif edited_product_values:
                    # Parent was untouched, but one or more products
                    # inside the market changed. Recalculate the market
                    # total using edited children plus untouched children.
                    recomputed_market_total = 0.0

                    for product_position, product_name in enumerate(
                        products
                    ):
                        if (
                            product_position
                            in edited_product_values
                        ):
                            recomputed_market_total += (
                                edited_product_values[
                                    product_position
                                ]
                            )
                        else:
                            recomputed_market_total += matrix[
                                market_name
                            ][product_name][month_index]

                    locked_market_totals[
                        market_position
                    ] = round(
                        recomputed_market_total,
                        6,
                    )

            # -------------------------------------------------
            # Normalize markets to Overall
            # -------------------------------------------------

            normalized_market_totals = normalize_distribution(
                current_values=current_market_totals,
                target_total=overall_volume,
                locked_values=locked_market_totals,
            )

            # -------------------------------------------------
            # Normalize products inside each market
            # -------------------------------------------------

            for market_position, market_name in enumerate(
                markets
            ):
                target_market_total = (
                    normalized_market_totals[
                        market_position
                    ]
                )

                current_product_values = [
                    matrix[market_name][product_name][month_index]
                    for product_name in products
                ]

                locked_product_values = (
                    edited_product_values_by_market.get(
                        market_position,
                        {},
                    )
                )

                normalized_product_values = normalize_distribution(
                    current_values=current_product_values,
                    target_total=target_market_total,
                    locked_values=locked_product_values,
                )

                for product_position, product_name in enumerate(
                    products
                ):
                    matrix[market_name][product_name][
                        month_index
                    ] = normalized_product_values[
                        product_position
                    ]

        return

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported Product Event table view: "
            f"{payload.selected_table_view!r}."
        ),
    )

def apply_matrix_to_tree(
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    selected_indexes: list[int],
):
    """
    Distribute each market-product total across existing sources.

    The existing source proportions are preserved.
    """

    product_names = list(tree["products"])

    for market_name, market in tree[
        "markets"
    ].items():

        source_nodes = list(
            market.get("sources", {}).values()
        )

        for product_name in product_names:

            for month_index in selected_indexes:

                target_volume = matrix[
                    market_name
                ][product_name][month_index]

                available_product_nodes = []

                for source in source_nodes:

                    product_node = source.get(
                        "products",
                        {},
                    ).get(product_name)

                    if product_node is not None:
                        available_product_nodes.append(
                            product_node
                        )

                if target_volume > 0 and not available_product_nodes:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "No source-product forecast row exists for "
                            f"{market_name}/{product_name}."
                        ),
                    )

                if not available_product_nodes:
                    continue

                current_source_volumes = [
                    product_node["volume"][month_index]
                    for product_node in available_product_nodes
                ]

                allocated_volumes = normalize_distribution(
                    current_values=current_source_volumes,
                    target_total=target_volume,
                )

                for product_node, allocated_volume in zip(
                    available_product_nodes,
                    allocated_volumes,
                ):
                    product_node["volume"][
                        month_index
                    ] = allocated_volume

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
    selected_indexes: list[int],
):
    """
    Recompute all dependent values for the edited months.

    Product volumes
        ↓
    Product shares inside source
        ↓
    Source volumes
        ↓
    Source shares inside market
        ↓
    Market volumes
        ↓
    Market shares
        ↓
    Top-level product totals

    Both Market Event and Product Event builders use this same tree.
    """

    overall_volumes = tree["overall"]["volume"]

    for month_index in selected_indexes:

        # ================================================
        # Recompute sources from product volumes
        # ================================================

        for market in tree["markets"].values():

            for source in market.get(
                "sources",
                {},
            ).values():

                products = source.get(
                    "products",
                    {},
                )

                source_volume = sum(
                    product["volume"][month_index]
                    for product in products.values()
                )

                source["volume"][month_index] = round(
                    source_volume,
                    6,
                )

                for product in products.values():

                    product["share"][month_index] = (
                        calculate_percentage(
                            numerator=product["volume"][
                                month_index
                            ],
                            denominator=source_volume,
                        )
                    )

        # ================================================
        # Recompute markets from sources
        # ================================================

        for market in tree["markets"].values():

            sources = market.get(
                "sources",
                {},
            )

            market_volume = sum(
                source["volume"][month_index]
                for source in sources.values()
            )

            market["volume"][month_index] = round(
                market_volume,
                6,
            )

            market["share"][month_index] = (
                calculate_percentage(
                    numerator=market_volume,
                    denominator=overall_volumes[
                        month_index
                    ],
                )
            )

            for source in sources.values():

                source["share"][month_index] = (
                    calculate_percentage(
                        numerator=source["volume"][
                            month_index
                        ],
                        denominator=market_volume,
                    )
                )

    # Rebuild overall products from source-product volumes.
    aggregate_products(tree)

    # build_market_event(tree)
    # build_product_event(tree)

def build_updated_forecast_data(
    original_forecast_data: dict,
    full_values: list[float],
) -> dict:
    """
    Preserve:
        months
        forecast_start_index
        factors
        model configuration

    Replace:
        train_values
        forecast_values
    """

    months = original_forecast_data.get(
        "months",
        [],
    )

    forecast_start_index = original_forecast_data.get(
        "forecast_start_index",
        0,
    )

    if len(full_values) != len(months):
        raise ValueError(
            "Calculated values length does not match "
            "the forecast month count."
        )

    return {
        **original_forecast_data,

        "train_values": [
            round(float(value), 6)
            for value in full_values[
                :forecast_start_index
            ]
        ],

        "forecast_values": [
            round(float(value), 6)
            for value in full_values[
                forecast_start_index:
            ]
        ],
    }

def source_candidates(
    source_name: str | None,
) -> list[str | None]:
    """
    Return possible database source values for a tree source.
    """

    if source_name == "Unknown":
        return [
            "Unknown",
            None,
        ]

    if source_name is None:
        return [
            None,
            "Unknown",
        ]

    return [source_name]

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
    """
    Update the existing dimensional row.

    Insert a new row when no matching row exists.
    """

    serialized_data = json.dumps(
        forecast_data
    )

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
            serialized_data,
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
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s::jsonb
        )
        """,
        (
            ta_name,
            scenario_name,
            metric,
            market,
            source_of_market,
            product,
            serialized_data,
        ),
    )

def find_original_share_row(
    original_rows: dict,
    market_name: str,
    source_name: str | None,
    product_name: str,
) -> tuple[dict | None, str | None]:
    """
    Find the original forecast_data and its database source value.
    """

    for candidate in source_candidates(source_name):

        key = (
            market_name,
            candidate,
            product_name,
        )

        row = original_rows.get(key)

        if row is not None:
            return row, candidate

    return None, source_name

def save_tree_to_forecast_outputs(
    cursor,
    *,
    tree: dict,
    original_metrics: dict,
    ta_name: str,
    scenario_name: str,
):
    """
    Save recalculated forecast values.

    Database data stored:
        market-level market shares
        source-level market shares
        product shares within each source
        overall market volume
    """

    original_share_rows = {
        (
            row["market"],
            row["source_of_market"],
            row["product"],
        ): row["forecast_data"]
        for row in original_metrics.get(
            "market_share",
            [],
        )
    }

    if not original_share_rows:
        raise ValueError(
            "No original market-share rows were found."
        )

    default_share_template = next(
        iter(original_share_rows.values())
    )

    # =====================================================
    # Market share hierarchy
    # =====================================================

    for market_name, market in tree[
        "markets"
    ].items():

        # Market-level row:
        # market / NULL / ALL
        market_template = original_share_rows.get(
            (
                market_name,
                None,
                "ALL",
            ),
            default_share_template,
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
                original_forecast_data=market_template,
                full_values=market["share"],
            ),
        )

        # Source and product rows
        for source_name, source in market.get(
            "sources",
            {},
        ).items():

            source_template, database_source = (
                find_original_share_row(
                    original_rows=original_share_rows,
                    market_name=market_name,
                    source_name=source_name,
                    product_name="ALL",
                )
            )

            # Do not automatically create an ALL source row when the
            # original data model has no such source-level row.
            if source_template is not None:

                upsert_forecast_output(
                    cursor,
                    ta_name=ta_name,
                    scenario_name=scenario_name,
                    metric="market_share",
                    market=market_name,
                    source_of_market=database_source,
                    product="ALL",
                    forecast_data=build_updated_forecast_data(
                        original_forecast_data=source_template,
                        full_values=source["share"],
                    ),
                )

            for product_name, product in source.get(
                "products",
                {},
            ).items():

                product_template, product_database_source = (
                    find_original_share_row(
                        original_rows=original_share_rows,
                        market_name=market_name,
                        source_name=source_name,
                        product_name=product_name,
                    )
                )

                if product_template is None:
                    raise ValueError(
                        "No original forecast-output row exists for "
                        f"{market_name}/{source_name}/{product_name}."
                    )

                upsert_forecast_output(
                    cursor,
                    ta_name=ta_name,
                    scenario_name=scenario_name,
                    metric="market_share",
                    market=market_name,
                    source_of_market=product_database_source,
                    product=product_name,
                    forecast_data=build_updated_forecast_data(
                        original_forecast_data=product_template,
                        full_values=product["share"],
                    ),
                )

    # =====================================================
    # Overall market volume
    # =====================================================

    volume_rows = original_metrics.get(
        "market_volume",
        [],
    )

    if not volume_rows:
        raise ValueError(
            "No overall market-volume row was found."
        )

    original_volume_row = volume_rows[0]

    upsert_forecast_output(
        cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
        metric="market_volume",
        market=original_volume_row["market"],
        source_of_market=original_volume_row[
            "source_of_market"
        ],
        product=original_volume_row["product"],
        forecast_data=build_updated_forecast_data(
            original_forecast_data=original_volume_row[
                "forecast_data"
            ],
            full_values=tree["overall"]["volume"],
        ),
    )

def build_apply_filters_response(
    cursor,
    *,
    ta_name: str,
    selected_filter: dict,
) -> dict:
    """
    Shared response builder for:

        apply_market_event_filters
        edit_save

    Both APIs therefore return the same response structure.
    """

    scenario_name = selected_filter[
        "scenario_name"
    ]

    start_date = selected_filter[
        "start_date"
    ]

    end_date = selected_filter[
        "end_date"
    ]

    metadata = load_metadata(
        cursor=cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
        start_date=start_date,
        end_date=end_date,
    )

    metrics = load_forecast_outputs(
        cursor=cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
    )

    if not metrics.get("market_share"):
        raise HTTPException(
            status_code=404,
            detail="No market-share forecast data was found.",
        )

    if not metrics.get("market_volume"):
        raise HTTPException(
            status_code=404,
            detail="No market-volume forecast data was found.",
        )

    tree = build_calculation_tree(
        metrics
    )

    tree = filter_tree_by_date(
        tree=tree,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "ta_name": ta_name,

        "available_scenarios":
            metadata["available_scenarios"],

        "available_months":
            metadata["available_months"],

        "metric_filters":
            metadata["metric_filters"],

        "forecast_start_date":
            metadata["forecast_start_date"],

        "selected_filter":
            selected_filter,

        "event_tabs": {
            "overall_event":
                build_overall_event(tree),

            "market_event":
                build_market_event(tree),

            "product_event":
                build_product_event(tree),
        },
    }


