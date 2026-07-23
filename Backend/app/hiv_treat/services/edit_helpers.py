from fastapi import HTTPException
from app.hiv_treat.routes.market_events_models import *
from app.hiv_treat.services.calculation_tree_market_events import *
from app.hiv_treat.services.response_builder_market_events import *
from app.hiv_treat.services.generic_builders_market_events import *
from app.hiv_treat.services.market_event_helpers import *
import json


def is_row_edited(
    *,
    edited_rows: set[str],
    parent_label: str | None = None,
    row_label: str,
) -> bool:
    """
    Check whether a submitted row was explicitly edited.

    Preferred child format:
        Biktarvy|Non-retail

    Legacy child format:
        Non-retail
    """

    if row_label in edited_rows:
        return True

    if parent_label:
        row_path = f"{parent_label}|{row_label}"

        if row_path in edited_rows:
            return True

    return False

def redistribute_fixed_total(
    *,
    current_values: list[float],
    fixed_total: float,
    edited_values: dict[int, float],
    precision: int = 2,
) -> list[float]:
    """
    Redistribute values while keeping their total fixed.

    Parameters
    ----------
    current_values:
        Current values of all children.

    fixed_total:
        Parent total that must remain unchanged.

    edited_values:
        Mapping:

            child_position -> submitted value

    Rules
    -----
    1. Negative edits become zero.
    2. Edited values cannot exceed the remaining parent total.
    3. Untouched children share the remainder according to their
       existing proportions.
    4. The returned values always sum to fixed_total.

    Example
    -------
    current_values:
        [24.59, 8.55]

    fixed_total:
        33.14

    edited_values:
        {0: 90}

    result:
        [33.14, 0]
    """

    if fixed_total is None:
        fixed_total = 0.0

    fixed_total = max(
        0.0,
        float(fixed_total),
    )

    value_count = len(current_values)

    if value_count == 0:
        return []

    current_values = [
        max(0.0, float(value or 0.0))
        for value in current_values
    ]

    if not edited_values:
        current_total = sum(current_values)

        if current_total <= 0:
            equal_value = fixed_total / value_count

            result = [
                round(equal_value, precision)
                for _ in current_values
            ]
        else:
            result = [
                round(
                    fixed_total * value / current_total,
                    precision,
                )
                for value in current_values
            ]

        difference = round(
            fixed_total - sum(result),
            precision,
        )

        if difference:
            result[-1] = round(
                result[-1] + difference,
                precision,
            )

        return result

    result = [0.0] * value_count

    valid_edits: dict[int, float] = {}

    for position, submitted_value in edited_values.items():

        if position < 0 or position >= value_count:
            raise ValueError(
                f"Invalid child position: {position}."
            )

        valid_edits[position] = max(
            0.0,
            float(submitted_value or 0.0),
        )

    # Apply edited values one by one while respecting the
    # remaining parent total.
    remaining_total = fixed_total

    for position, submitted_value in valid_edits.items():

        clamped_value = min(
            submitted_value,
            remaining_total,
        )

        result[position] = round(
            clamped_value,
            precision,
        )

        remaining_total = max(
            0.0,
            remaining_total - clamped_value,
        )

    untouched_positions = [
        position
        for position in range(value_count)
        if position not in valid_edits
    ]

    # Edited values consumed the entire parent total.
    if remaining_total <= 0:

        for position in untouched_positions:
            result[position] = 0.0

        return result

    # Every child was explicitly edited, but their total is below
    # the fixed parent. Add the difference to the last edited child.
    if not untouched_positions:

        last_edited_position = list(
            valid_edits.keys()
        )[-1]

        result[last_edited_position] = round(
            result[last_edited_position]
            + remaining_total,
            precision,
        )

        return result

    untouched_current_total = sum(
        current_values[position]
        for position in untouched_positions
    )

    if untouched_current_total > 0:

        for position in untouched_positions:

            current_ratio = (
                current_values[position]
                / untouched_current_total
            )

            result[position] = round(
                remaining_total * current_ratio,
                precision,
            )

    else:

        equal_value = (
            remaining_total
            / len(untouched_positions)
        )

        for position in untouched_positions:
            result[position] = round(
                equal_value,
                precision,
            )

    # Correct floating-point differences.
    difference = round(
        fixed_total - sum(result),
        precision,
    )

    if difference:

        correction_position = (
            untouched_positions[-1]
            if untouched_positions
            else list(valid_edits.keys())[-1]
        )

        result[correction_position] = round(
            result[correction_position]
            + difference,
            precision,
        )

    return result

def resize_market_products(
    *,
    matrix: dict[str, dict[str, list[float]]],
    market_name: str,
    products: list[str],
    month_index: int,
    target_market_total: float,
):
    """
    Resize all products inside one market while preserving
    their current proportions.
    """

    current_product_values = [
        matrix[market_name][product_name][month_index]
        for product_name in products
    ]

    resized_product_values = redistribute_fixed_total(
        current_values=current_product_values,
        fixed_total=target_market_total,
        edited_values={},
    )

    for product_position, product_name in enumerate(
        products
    ):
        matrix[market_name][product_name][
            month_index
        ] = resized_product_values[
            product_position
        ]

def apply_market_level_edits(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    """
    Edit market totals while keeping Overall fixed.

    Example
    -------
    Overall:
        100

    Current:
        Non-retail = 70
        Retail = 30

    Edit:
        Non-retail = 90

    Result:
        Non-retail = 90
        Retail = 10
    """

    markets = list(tree["markets"])
    products = list(tree["products"])

    overall_volumes = tree["overall"]["volume"]

    submitted_rows = rows_by_label(
        payload.edited_table_rows
    )

    edited_rows = set(
        payload.edited_rows or []
    )

    for value_position, month_index in enumerate(
        selected_indexes
    ):
        overall_volume = overall_volumes[
            month_index
        ]

        current_market_totals = [
            sum(
                matrix[market_name][product_name][
                    month_index
                ]
                for product_name in products
            )
            for market_name in markets
        ]

        edited_market_values: dict[int, float] = {}

        for market_position, market_name in enumerate(
            markets
        ):
            if not is_row_edited(
                edited_rows=edited_rows,
                row_label=market_name,
            ):
                continue

            market_row = submitted_rows.get(
                market_name
            )

            if market_row is None:
                raise ValueError(
                    f"Edited market row {market_name!r} "
                    "was not found in edited_table_rows."
                )

            submitted_volume = edited_value_to_volume(
                value=market_row.values[
                    value_position
                ],
                selected_metric=payload.selected_metric,
                overall_volume=overall_volume,
            )

            edited_market_values[
                market_position
            ] = submitted_volume

        if not edited_market_values:
            continue

        normalized_market_totals = (
            redistribute_fixed_total(
                current_values=current_market_totals,
                fixed_total=overall_volume,
                edited_values=edited_market_values,
            )
        )

        # Resize products inside every market according to
        # the newly calculated market total.
        for market_position, market_name in enumerate(
            markets
        ):
            resize_market_products(
                matrix=matrix,
                market_name=market_name,
                products=products,
                month_index=month_index,
                target_market_total=(
                    normalized_market_totals[
                        market_position
                    ]
                ),
            )

def apply_product_market_level_edits(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    """
    Move each product between markets while keeping the
    product's total fixed.

    Example
    -------
    Biktarvy total:
        33.14

    Current:
        Non-retail = 24.59
        Retail = 8.55

    Submitted edit:
        Non-retail = 90

    Result:
        Non-retail = 33.14
        Retail = 0
    """

    markets = list(tree["markets"])
    products = list(tree["products"])

    overall_volumes = tree["overall"]["volume"]

    submitted_rows = rows_by_label(
        payload.edited_table_rows
    )

    edited_rows = set(
        payload.edited_rows or []
    )

    for value_position, month_index in enumerate(
        selected_indexes
    ):
        overall_volume = overall_volumes[
            month_index
        ]

        for product_name in products:

            product_row = submitted_rows.get(
                product_name
            )

            if product_row is None:
                continue

            market_children = rows_by_label(
                product_row.children
            )

            current_market_values = [
                matrix[market_name][product_name][
                    month_index
                ]
                for market_name in markets
            ]

            # This total is captured before applying the edit.
            # It must never change in this view.
            fixed_product_total = sum(
                current_market_values
            )

            edited_market_values: dict[int, float] = {}

            for market_position, market_name in enumerate(
                markets
            ):
                if not is_row_edited(
                    edited_rows=edited_rows,
                    parent_label=product_name,
                    row_label=market_name,
                ):
                    continue

                child_row = market_children.get(
                    market_name
                )

                if child_row is None:
                    raise ValueError(
                        f"Edited row "
                        f"{product_name!r}|{market_name!r} "
                        "was not found in edited_table_rows."
                    )

                submitted_volume = edited_value_to_volume(
                    value=child_row.values[
                        value_position
                    ],
                    selected_metric=payload.selected_metric,
                    overall_volume=overall_volume,
                )

                edited_market_values[
                    market_position
                ] = submitted_volume

            if not edited_market_values:
                continue

            redistributed_market_values = (
                redistribute_fixed_total(
                    current_values=(
                        current_market_values
                    ),
                    fixed_total=(
                        fixed_product_total
                    ),
                    edited_values=(
                        edited_market_values
                    ),
                )
            )

            for market_position, market_name in enumerate(
                markets
            ):
                matrix[market_name][product_name][
                    month_index
                ] = (
                    redistributed_market_values[
                        market_position
                    ]
                )

            # Defensive verification.
            recalculated_product_total = sum(
                matrix[market_name][product_name][
                    month_index
                ]
                for market_name in markets
            )

            if abs(
                recalculated_product_total
                - fixed_product_total
            ) > 0.001:
                raise ValueError(
                    f"Product total changed for "
                    f"{product_name!r}. Expected "
                    f"{fixed_product_total}, received "
                    f"{recalculated_product_total}."
                )
            
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

        Overall remains fixed. Editing one market redistributes
        the remaining volume across other markets.

    product_market_level:
        Overall
        Product
            Market

        Each product total remains fixed. Editing one market
        child moves that product between markets.
    """

    if payload.selected_table_view == "market_level":

        apply_market_level_edits(
            tree=tree,
            matrix=matrix,
            payload=payload,
            selected_indexes=selected_indexes,
        )

        return

    if (
        payload.selected_table_view
        == "product_market_level"
    ):

        apply_product_market_level_edits(
            tree=tree,
            matrix=matrix,
            payload=payload,
            selected_indexes=selected_indexes,
        )

        return

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported Market Event table view: "
            f"{payload.selected_table_view!r}."
        ),
    )

#product_event
def is_product_event_row_edited(
    *,
    edited_rows: set[str],
    market_name: str,
    product_name: str,
) -> bool:
    """
    Check whether a product row under a market was explicitly edited.

    Preferred format
    ----------------
        Retail|Biktarvy
        Non-retail|Descovy

    The plain product name is also supported temporarily for
    backward compatibility, but unique paths should be used.
    """

    unique_path = f"{market_name}|{product_name}"

    return (
        unique_path in edited_rows
        or product_name in edited_rows
    )

def redistribute_fixed_product_total(
    *,
    current_market_values: list[float],
    fixed_product_total: float,
    edited_market_values: dict[int, float],
    precision: int = 6,
) -> list[float]:
    """
    Redistribute one product across markets while keeping
    its total fixed.

    Parameters
    ----------
    current_market_values:
        Current product volumes across markets.

        Example:
            [24.59, 8.55]

    fixed_product_total:
        Product total that must remain unchanged.

        Example:
            33.14

    edited_market_values:
        Mapping of:

            market_position -> submitted volume

        Example:
            {1: 90}

    Rules
    -----
    - Negative edits are clamped to zero.
    - A single edited market cannot exceed the product total.
    - If an edited value consumes the complete product total,
      every untouched market becomes zero.
    - Remaining volume is distributed across untouched markets
      using their current proportions.
    - Returned values always sum to fixed_product_total.
    """

    fixed_product_total = max(
        0.0,
        float(fixed_product_total or 0.0),
    )

    value_count = len(current_market_values)

    if value_count == 0:
        return []

    current_market_values = [
        max(0.0, float(value or 0.0))
        for value in current_market_values
    ]

    if not edited_market_values:
        return current_market_values.copy()

    valid_edits: dict[int, float] = {}

    for market_position, submitted_value in (
        edited_market_values.items()
    ):
        if not 0 <= market_position < value_count:
            raise ValueError(
                "Invalid market position "
                f"{market_position}. Expected a value between "
                f"0 and {value_count - 1}."
            )

        valid_edits[market_position] = max(
            0.0,
            float(submitted_value or 0.0),
        )

    result = [0.0] * value_count

    # Single edited market:
    #
    # Clamp directly to the product total.
    if len(valid_edits) == 1:
        edited_position, submitted_value = next(
            iter(valid_edits.items())
        )

        clamped_value = min(
            submitted_value,
            fixed_product_total,
        )

        result[edited_position] = round(
            clamped_value,
            precision,
        )

        remaining_total = max(
            0.0,
            fixed_product_total - clamped_value,
        )

        untouched_positions = [
            position
            for position in range(value_count)
            if position != edited_position
        ]

        distribute_remaining_to_untouched_markets(
            result=result,
            current_market_values=current_market_values,
            untouched_positions=untouched_positions,
            remaining_total=remaining_total,
            precision=precision,
        )

        correct_fixed_total_rounding(
            values=result,
            fixed_total=fixed_product_total,
            preferred_positions=untouched_positions,
            fallback_position=edited_position,
            precision=precision,
        )

        return result

    # Multiple simultaneous edits.
    submitted_edited_total = sum(
        valid_edits.values()
    )

    # If edited values exceed the product total, scale the edited
    # values proportionally and set all untouched markets to zero.
    if submitted_edited_total >= fixed_product_total:

        if submitted_edited_total == 0:
            return result

        scale_factor = (
            fixed_product_total
            / submitted_edited_total
        )

        for market_position, submitted_value in (
            valid_edits.items()
        ):
            result[market_position] = round(
                submitted_value * scale_factor,
                precision,
            )

        correct_fixed_total_rounding(
            values=result,
            fixed_total=fixed_product_total,
            preferred_positions=list(valid_edits),
            fallback_position=list(valid_edits)[-1],
            precision=precision,
        )

        return result

    # Apply all edited values as submitted.
    for market_position, submitted_value in (
        valid_edits.items()
    ):
        result[market_position] = round(
            submitted_value,
            precision,
        )

    remaining_total = max(
        0.0,
        fixed_product_total - sum(result),
    )

    untouched_positions = [
        position
        for position in range(value_count)
        if position not in valid_edits
    ]

    # Every market was edited, but edited values do not fill
    # the fixed product total. Assign the difference to the
    # final edited market.
    if not untouched_positions:
        correction_position = list(valid_edits)[-1]

        result[correction_position] = round(
            result[correction_position]
            + remaining_total,
            precision,
        )

        return result

    distribute_remaining_to_untouched_markets(
        result=result,
        current_market_values=current_market_values,
        untouched_positions=untouched_positions,
        remaining_total=remaining_total,
        precision=precision,
    )

    correct_fixed_total_rounding(
        values=result,
        fixed_total=fixed_product_total,
        preferred_positions=untouched_positions,
        fallback_position=list(valid_edits)[-1],
        precision=precision,
    )

    return result

def distribute_remaining_to_untouched_markets(
    *,
    result: list[float],
    current_market_values: list[float],
    untouched_positions: list[int],
    remaining_total: float,
    precision: int = 6,
):
    """
    Distribute remaining product volume across untouched markets.

    Existing proportions are preserved whenever possible.
    """

    if not untouched_positions:
        return

    remaining_total = max(
        0.0,
        float(remaining_total or 0.0),
    )

    if remaining_total == 0:
        for position in untouched_positions:
            result[position] = 0.0

        return

    current_untouched_total = sum(
        current_market_values[position]
        for position in untouched_positions
    )

    if current_untouched_total > 0:
        for position in untouched_positions:
            current_ratio = (
                current_market_values[position]
                / current_untouched_total
            )

            result[position] = round(
                remaining_total * current_ratio,
                precision,
            )

        return

    equal_value = (
        remaining_total
        / len(untouched_positions)
    )

    for position in untouched_positions:
        result[position] = round(
            equal_value,
            precision,
        )

def correct_fixed_total_rounding(
    *,
    values: list[float],
    fixed_total: float,
    preferred_positions: list[int],
    fallback_position: int,
    precision: int = 6,
):
    """
    Correct floating-point differences so values sum exactly
    to the fixed total.
    """

    difference = round(
        fixed_total - sum(values),
        precision,
    )

    if difference == 0:
        return

    correction_position = (
        preferred_positions[-1]
        if preferred_positions
        else fallback_position
    )

    corrected_value = (
        values[correction_position]
        + difference
    )

    values[correction_position] = round(
        max(0.0, corrected_value),
        precision,
    )

def apply_product_level_edits(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    """
    Apply Product Event edits at product_level.

    Structure
    ---------
    Overall
    Biktarvy
    Descovy
    Truvada

    Rule
    ----
    Overall remains fixed.

    Only products listed in payload.edited_rows are treated
    as edited.

    The remaining Overall value is redistributed across
    untouched products according to their existing proportions.

    The market split inside every product is preserved.
    """

    markets = list(tree["markets"])
    products = list(tree["products"])

    overall_volumes = tree["overall"]["volume"]

    submitted_rows = rows_by_label(
        payload.edited_table_rows
    )

    edited_product_labels = set(
        payload.edited_rows or []
    )

    for value_position, month_index in enumerate(
        selected_indexes
    ):
        overall_volume = overall_volumes[
            month_index
        ]

        current_product_totals = [
            sum(
                matrix[market_name][product_name][
                    month_index
                ]
                for market_name in markets
            )
            for product_name in products
        ]

        edited_product_values: dict[int, float] = {}

        for product_position, product_name in enumerate(
            products
        ):
            # Important:
            # Only rows explicitly listed by the frontend
            # are treated as edited.
            if product_name not in edited_product_labels:
                continue

            product_row = submitted_rows.get(
                product_name
            )

            if product_row is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Edited product row "
                        f"{product_name!r} was not found "
                        "in edited_table_rows."
                    ),
                )

            if value_position >= len(
                product_row.values
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Missing submitted value for "
                        f"{product_name!r} at position "
                        f"{value_position}."
                    ),
                )

            submitted_volume = edited_value_to_volume(
                value=product_row.values[
                    value_position
                ],
                selected_metric=payload.selected_metric,
                overall_volume=overall_volume,
            )

            edited_product_values[
                product_position
            ] = submitted_volume

        if not edited_product_values:
            continue

        redistributed_product_totals = (
            redistribute_within_fixed_total(
                current_values=current_product_totals,
                fixed_total=overall_volume,
                edited_values=edited_product_values,
            )
        )

        # Preserve each product's existing market split.
        for product_position, product_name in enumerate(
            products
        ):
            target_product_total = (
                redistributed_product_totals[
                    product_position
                ]
            )

            current_market_values = [
                matrix[market_name][product_name][
                    month_index
                ]
                for market_name in markets
            ]

            resized_market_values = resize_values_to_total(
                current_values=current_market_values,
                target_total=target_product_total,
            )

            for market_position, market_name in enumerate(
                markets
            ):
                matrix[market_name][product_name][
                    month_index
                ] = resized_market_values[
                    market_position
                ]

        recalculated_overall = sum(
            sum(
                matrix[market_name][product_name][
                    month_index
                ]
                for market_name in markets
            )
            for product_name in products
        )

        if abs(
            recalculated_overall - overall_volume
        ) > 0.001:
            raise ValueError(
                "Overall total changed during product "
                "redistribution. "
                f"month_index={month_index}, "
                f"expected={overall_volume}, "
                f"calculated={recalculated_overall}."
            )

def redistribute_within_fixed_total(
    *,
    current_values: list[float],
    fixed_total: float,
    edited_values: dict[int, float],
    precision: int = 6,
) -> list[float]:
    """
    Keep the parent total fixed while applying edits to
    selected child values.

    Edited values are clamped to the parent total.

    Remaining value is redistributed proportionally across
    untouched children.
    """

    fixed_total = max(
        0.0,
        float(fixed_total or 0.0),
    )

    current_values = [
        max(0.0, float(value or 0.0))
        for value in current_values
    ]

    value_count = len(current_values)

    if value_count == 0:
        return []

    if not edited_values:
        return current_values.copy()

    valid_edits: dict[int, float] = {}

    for position, submitted_value in (
        edited_values.items()
    ):
        if not 0 <= position < value_count:
            raise ValueError(
                f"Invalid edited position: {position}."
            )

        valid_edits[position] = max(
            0.0,
            float(submitted_value or 0.0),
        )

    result = [0.0] * value_count

    submitted_edited_total = sum(
        valid_edits.values()
    )

    # Edited values consume or exceed the entire parent total.
    if submitted_edited_total >= fixed_total:
        if submitted_edited_total <= 0:
            return result

        if len(valid_edits) == 1:
            edited_position = next(
                iter(valid_edits)
            )

            result[edited_position] = round(
                fixed_total,
                precision,
            )

            return result

        scale_factor = (
            fixed_total / submitted_edited_total
        )

        for position, submitted_value in (
            valid_edits.items()
        ):
            result[position] = round(
                submitted_value * scale_factor,
                precision,
            )

        difference = round(
            fixed_total - sum(result),
            precision,
        )

        if difference:
            correction_position = list(
                valid_edits
            )[-1]

            result[correction_position] = round(
                result[correction_position]
                + difference,
                precision,
            )

        return result

    # Keep explicitly edited values exactly as submitted.
    for position, submitted_value in (
        valid_edits.items()
    ):
        result[position] = round(
            submitted_value,
            precision,
        )

    remaining_total = max(
        0.0,
        fixed_total - sum(result),
    )

    untouched_positions = [
        position
        for position in range(value_count)
        if position not in valid_edits
    ]

    if not untouched_positions:
        correction_position = list(
            valid_edits
        )[-1]

        result[correction_position] = round(
            result[correction_position]
            + remaining_total,
            precision,
        )

        return result

    current_untouched_total = sum(
        current_values[position]
        for position in untouched_positions
    )

    if current_untouched_total > 0:
        for position in untouched_positions:
            proportion = (
                current_values[position]
                / current_untouched_total
            )

            result[position] = round(
                remaining_total * proportion,
                precision,
            )
    else:
        equal_value = (
            remaining_total
            / len(untouched_positions)
        )

        for position in untouched_positions:
            result[position] = round(
                equal_value,
                precision,
            )

    difference = round(
        fixed_total - sum(result),
        precision,
    )

    if difference:
        correction_position = (
            untouched_positions[-1]
        )

        result[correction_position] = round(
            result[correction_position]
            + difference,
            precision,
        )

    return result

def resize_values_to_total(
    *,
    current_values: list[float],
    target_total: float,
    precision: int = 6,
) -> list[float]:
    """
    Resize values to a new total while preserving their
    existing proportions.
    """

    target_total = max(
        0.0,
        float(target_total or 0.0),
    )

    clean_values = [
        max(0.0, float(value or 0.0))
        for value in current_values
    ]

    value_count = len(clean_values)

    if value_count == 0:
        return []

    current_total = sum(clean_values)

    if current_total > 0:
        result = [
            round(
                target_total
                * value
                / current_total,
                precision,
            )
            for value in clean_values
        ]
    else:
        equal_value = (
            target_total / value_count
        )

        result = [
            round(equal_value, precision)
            for _ in clean_values
        ]

    difference = round(
        target_total - sum(result),
        precision,
    )

    if difference:
        result[-1] = round(
            result[-1] + difference,
            precision,
        )

    return result

def apply_product_event_edits(
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    if payload.selected_table_view == "product_level":
        apply_product_level_edits(
            tree=tree,
            matrix=matrix,
            payload=payload,
            selected_indexes=selected_indexes,
        )
        return

    if (
        payload.selected_table_view
        == "market_product_level"
    ):
        apply_market_product_level_edits(
            tree=tree,
            matrix=matrix,
            payload=payload,
            selected_indexes=selected_indexes,
        )
        return

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported Product Event table view: "
            f"{payload.selected_table_view!r}."
        ),
    )

# def resize_values_to_total(
#     *,
#     current_values: list[float],
#     target_total: float,
#     precision: int = 6,
# ) -> list[float]:
#     """
#     Resize values to a target total while preserving their
#     current proportions.
#     """

#     target_total = max(
#         0.0,
#         float(target_total or 0.0),
#     )

#     value_count = len(current_values)

#     if value_count == 0:
#         return []

#     clean_values = [
#         max(0.0, float(value or 0.0))
#         for value in current_values
#     ]

#     current_total = sum(clean_values)

#     if current_total > 0:
#         result = [
#             round(
#                 target_total * value / current_total,
#                 precision,
#             )
#             for value in clean_values
#         ]
#     else:
#         equal_value = target_total / value_count

#         result = [
#             round(equal_value, precision)
#             for _ in clean_values
#         ]

#     difference = round(
#         target_total - sum(result),
#         precision,
#     )

#     if difference:
#         result[-1] = round(
#             result[-1] + difference,
#             precision,
#         )

#     return result

def detect_market_product_edits(
    *,
    markets: list[str],
    products: list[str],
    matrix: dict[str, dict[str, list[float]]],
    submitted_rows: dict,
    edited_rows: set[str],
    payload: EditSaveRequest,
    overall_volume: float,
    value_position: int,
    month_index: int,
    tolerance: float = 0.0001,
) -> dict[str, dict[int, float]]:
    """
    Detect edited products under markets.

    Returns
    -------
    {
        "Biktarvy": {
            0: edited_volume
        }
    }

    The integer key is the market position.
    """

    edits_by_product: dict[
        str,
        dict[int, float],
    ] = {}

    for market_position, market_name in enumerate(
        markets
    ):
        market_row = submitted_rows.get(
            market_name
        )

        if market_row is None:
            continue

        submitted_children = rows_by_label(
            market_row.children
        )

        for product_name in products:
            product_child = submitted_children.get(
                product_name
            )

            if product_child is None:
                continue

            submitted_volume = edited_value_to_volume(
                value=product_child.values[
                    value_position
                ],
                selected_metric=payload.selected_metric,
                overall_volume=overall_volume,
            )

            current_volume = matrix[
                market_name
            ][product_name][month_index]

            explicitly_edited = (
                is_product_event_row_edited(
                    edited_rows=edited_rows,
                    market_name=market_name,
                    product_name=product_name,
                )
            )

            value_changed = (
                abs(submitted_volume - current_volume)
                > tolerance
            )

            if not explicitly_edited and not value_changed:
                continue

            edits_by_product.setdefault(
                product_name,
                {},
            )[market_position] = submitted_volume

    return edits_by_product

def redistribute_within_market(
    *,
    current_product_values: list[float],
    fixed_market_total: float,
    edited_product_values: dict[int, float],
    precision: int = 6,
) -> list[float]:
    """
    Keep the market total fixed while applying product edits.

    The edited product is clamped to the market total.
    The remaining market value is distributed proportionally
    across untouched products.
    """

    fixed_market_total = max(
        0.0,
        float(fixed_market_total or 0.0),
    )

    current_product_values = [
        max(0.0, float(value or 0.0))
        for value in current_product_values
    ]

    product_count = len(current_product_values)

    if product_count == 0:
        return []

    if not edited_product_values:
        return current_product_values.copy()

    result = [0.0] * product_count

    valid_edits: dict[int, float] = {}

    for product_position, submitted_value in (
        edited_product_values.items()
    ):
        if not 0 <= product_position < product_count:
            raise ValueError(
                f"Invalid product position: "
                f"{product_position}."
            )

        valid_edits[product_position] = max(
            0.0,
            float(submitted_value or 0.0),
        )

    submitted_edited_total = sum(
        valid_edits.values()
    )

    # Edited values consume or exceed the entire market.
    if submitted_edited_total >= fixed_market_total:
        if submitted_edited_total <= 0:
            return result

        # For one edited product this directly clamps it
        # to the complete market total.
        if len(valid_edits) == 1:
            edited_position = next(
                iter(valid_edits)
            )

            result[edited_position] = round(
                fixed_market_total,
                precision,
            )

            return result

        # Multiple edited products: preserve their submitted
        # proportions while fitting them into the market total.
        scale_factor = (
            fixed_market_total
            / submitted_edited_total
        )

        for product_position, submitted_value in (
            valid_edits.items()
        ):
            result[product_position] = round(
                submitted_value * scale_factor,
                precision,
            )

        difference = round(
            fixed_market_total - sum(result),
            precision,
        )

        if difference:
            correction_position = list(
                valid_edits
            )[-1]

            result[correction_position] = round(
                result[correction_position]
                + difference,
                precision,
            )

        return result

    # Keep edited values exactly as submitted.
    for product_position, submitted_value in (
        valid_edits.items()
    ):
        result[product_position] = round(
            submitted_value,
            precision,
        )

    remaining_total = max(
        0.0,
        fixed_market_total - sum(result),
    )

    untouched_positions = [
        position
        for position in range(product_count)
        if position not in valid_edits
    ]

    if not untouched_positions:
        correction_position = list(
            valid_edits
        )[-1]

        result[correction_position] = round(
            result[correction_position]
            + remaining_total,
            precision,
        )

        return result

    current_untouched_total = sum(
        current_product_values[position]
        for position in untouched_positions
    )

    if current_untouched_total > 0:
        for position in untouched_positions:
            proportion = (
                current_product_values[position]
                / current_untouched_total
            )

            result[position] = round(
                remaining_total * proportion,
                precision,
            )
    else:
        equal_value = (
            remaining_total
            / len(untouched_positions)
        )

        for position in untouched_positions:
            result[position] = round(
                equal_value,
                precision,
            )

    # Correct rounding so the values exactly equal
    # the fixed market total.
    difference = round(
        fixed_market_total - sum(result),
        precision,
    )

    if difference:
        correction_position = untouched_positions[-1]

        result[correction_position] = round(
            result[correction_position]
            + difference,
            precision,
        )

    return result

def force_values_to_exact_total(
    *,
    values: list[float],
    target_total: float,
    correction_position: int | None = None,
    precision: int = 2,
) -> list[float]:
    """
    Force child values to sum exactly to target_total.

    The rounding difference is added to one selected child.
    """

    if not values:
        return []

    result = [
        round(max(0.0, float(value or 0.0)), precision)
        for value in values
    ]

    target_total = round(
        max(0.0, float(target_total or 0.0)),
        precision,
    )

    if correction_position is None:
        correction_position = len(result) - 1

    if not 0 <= correction_position < len(result):
        correction_position = len(result) - 1

    difference = round(
        target_total - sum(result),
        precision,
    )

    result[correction_position] = round(
        result[correction_position] + difference,
        precision,
    )

    # Defensive second correction.
    remaining_difference = round(
        target_total - sum(result),
        precision,
    )

    if remaining_difference:
        result[correction_position] = round(
            result[correction_position]
            + remaining_difference,
            precision,
        )

    return result

def apply_market_product_level_edits(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
):
    """
    Apply Product Event edits for market_product_level.

    Table hierarchy
    ---------------
    Overall
        Non-retail
            Biktarvy
            Descovy
            Truvada
        Retail
            Biktarvy
            Descovy
            Truvada

    Frontend edited_rows format
    ---------------------------
        ["Biktarvy"]

    Because the same product appears under multiple markets,
    the edited market is identified by comparing the submitted
    product value with the current matrix value.

    Business rule
    -------------
    Editing a product redistributes the remaining value across
    other products within the same market.

    The submitted market parent total remains fixed.
    """

    markets = list(tree["markets"])
    products = list(tree["products"])

    overall_volumes = tree["overall"]["volume"]

    submitted_rows = rows_by_label(
        payload.edited_table_rows
    )

    edited_product_labels = set(
        payload.edited_rows or []
    )

    comparison_tolerance = 0.011
    calculation_precision = 6
    validation_tolerance = 0.000001

    for value_position, month_index in enumerate(
        selected_indexes
    ):
        overall_volume = overall_volumes[
            month_index
        ]

        for market_name in markets:
            market_row = submitted_rows.get(
                market_name
            )

            if market_row is None:
                continue

            submitted_product_rows = rows_by_label(
                market_row.children
            )

            current_product_values = [
                round(
                    max(
                        0.0,
                        float(
                            matrix[market_name][product_name][
                                month_index
                            ]
                            or 0.0
                        ),
                    ),
                    calculation_precision,
                )
                for product_name in products
            ]

            # ================================================
            # Use the submitted market parent as the fixed total
            # ================================================

            if value_position < len(market_row.values):
                submitted_market_value = (
                    market_row.values[value_position]
                )

                fixed_market_total = edited_value_to_volume(
                    value=submitted_market_value,
                    selected_metric=payload.selected_metric,
                    overall_volume=overall_volume,
                )
            else:
                # Defensive fallback.
                fixed_market_total = sum(
                    current_product_values
                )

            fixed_market_total = round(
                max(
                    0.0,
                    float(fixed_market_total or 0.0),
                ),
                calculation_precision,
            )

            edited_product_values: dict[int, float] = {}

            # Used to select where any rounding difference
            # should be applied.
            edited_product_positions: set[int] = set()

            for product_position, product_name in enumerate(
                products
            ):
                # Only product rows listed in edited_rows
                # can be treated as edits.
                if (
                    product_name
                    not in edited_product_labels
                ):
                    continue

                submitted_product_row = (
                    submitted_product_rows.get(
                        product_name
                    )
                )

                if submitted_product_row is None:
                    continue

                if value_position >= len(
                    submitted_product_row.values
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Missing submitted value for "
                            f"{market_name!r} -> "
                            f"{product_name!r} at position "
                            f"{value_position}."
                        ),
                    )

                submitted_product_volume = (
                    edited_value_to_volume(
                        value=(
                            submitted_product_row.values[
                                value_position
                            ]
                        ),
                        selected_metric=(
                            payload.selected_metric
                        ),
                        overall_volume=overall_volume,
                    )
                )

                submitted_product_volume = round(
                    max(
                        0.0,
                        float(
                            submitted_product_volume
                            or 0.0
                        ),
                    ),
                    calculation_precision,
                )

                current_product_volume = (
                    current_product_values[
                        product_position
                    ]
                )

                # The same product appears under Retail and
                # Non-retail. Only the occurrence whose value
                # differs is considered edited.
                value_changed = (
                    abs(
                        submitted_product_volume
                        - current_product_volume
                    )
                    > comparison_tolerance
                )

                if not value_changed:
                    continue

                edited_product_values[
                    product_position
                ] = submitted_product_volume

                edited_product_positions.add(
                    product_position
                )

            if not edited_product_values:
                continue

            redistributed_product_values = (
                redistribute_within_market(
                    current_product_values=(
                        current_product_values
                    ),
                    fixed_market_total=(
                        fixed_market_total
                    ),
                    edited_product_values=(
                        edited_product_values
                    ),
                    precision=calculation_precision,
                )
            )

            # Apply rounding correction to an untouched product
            # whenever possible, so the explicitly edited value
            # remains exactly as entered.
            untouched_positions = [
                product_position
                for product_position in range(
                    len(products)
                )
                if product_position
                not in edited_product_positions
            ]

            if untouched_positions:
                correction_position = (
                    untouched_positions[-1]
                )
            else:
                correction_position = (
                    len(products) - 1
                )

            redistributed_product_values = (
                force_values_to_exact_total(
                    values=(
                        redistributed_product_values
                    ),
                    target_total=(
                        fixed_market_total
                    ),
                    correction_position=(
                        correction_position
                    ),
                    precision=calculation_precision,
                )
            )

            # ================================================
            # Write values back into the matrix
            # ================================================

            for product_position, product_name in enumerate(
                products
            ):
                matrix[market_name][product_name][
                    month_index
                ] = round(
                    redistributed_product_values[
                        product_position
                    ],
                    calculation_precision,
                )

            # ================================================
            # Validate fixed market total
            # ================================================

            recalculated_market_total = round(
                sum(
                    matrix[market_name][product_name][
                        month_index
                    ]
                    for product_name in products
                ),
                calculation_precision,
            )

            if (
                abs(
                    recalculated_market_total
                    - fixed_market_total
                )
                > validation_tolerance
            ):
                raise ValueError(
                    "Market total changed during product "
                    "redistribution. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}, "
                    f"expected={fixed_market_total}, "
                    f"calculated="
                    f"{recalculated_market_total}."
                )



def validate_fixed_product_total(
    *,
    matrix: dict[str, dict[str, list[float]]],
    markets: list[str],
    product_name: str,
    month_index: int,
    expected_total: float,
    tolerance: float = 0.001,
):
    """
    Confirm that product redistribution did not change
    the product total.
    """

    recalculated_total = sum(
        matrix[market_name][product_name][month_index]
        for market_name in markets
    )

    if abs(
        recalculated_total - expected_total
    ) > tolerance:
        raise ValueError(
            "Product total changed during redistribution. "
            f"Product={product_name!r}, "
            f"month_index={month_index}, "
            f"expected={expected_total}, "
            f"calculated={recalculated_total}."
        )



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



def apply_matrix_to_tree(
    tree,
    matrix,
    selected_indexes,
):
    """
    Push the normalized market-product matrix back into
    the existing source-product nodes.

    The matrix is at:

        market -> product -> monthly values

    The database/tree is at:

        market -> source -> product -> monthly values

    Therefore, each market-product value must be distributed
    across the existing source rows.

    Existing source proportions are preserved.
    """

    for market_name, market_node in tree["markets"].items():

        sources = market_node.get("sources", {})

        for product_name in tree["products"]:

            matrix_values = (
                matrix
                .get(market_name, {})
                .get(product_name)
            )

            if matrix_values is None:
                continue

            # Find only real source-product nodes that already exist.
            source_product_nodes = []

            for source_name, source_node in sources.items():

                product_node = (
                    source_node
                    .get("products", {})
                    .get(product_name)
                )

                if product_node is None:
                    continue

                source_product_nodes.append(
                    (
                        source_name,
                        product_node,
                    )
                )

            if not source_product_nodes:
                raise ValueError(
                    "No existing source-product rows were found "
                    f"for market '{market_name}' and product "
                    f"'{product_name}'."
                )

            for month_index in selected_indexes:

                new_market_product_volume = float(
                    matrix_values[month_index]
                )

                # Existing source volumes for this product/month.
                existing_source_values = []

                for source_name, product_node in (
                    source_product_nodes
                ):
                    volume_values = product_node.get(
                        "volume",
                        [],
                    )

                    existing_value = (
                        float(volume_values[month_index])
                        if month_index < len(volume_values)
                        else 0.0
                    )

                    existing_source_values.append(
                        (
                            source_name,
                            product_node,
                            existing_value,
                        )
                    )

                existing_total = sum(
                    value
                    for _, _, value
                    in existing_source_values
                )

                allocated_total = 0.0

                for position, (
                    source_name,
                    product_node,
                    existing_value,
                ) in enumerate(existing_source_values):

                    volume_values = product_node.setdefault(
                        "volume",
                        [0.0] * len(tree["months"]),
                    )

                    # Assign rounding difference to the final source.
                    if position == len(existing_source_values) - 1:
                        allocated_value = round(
                            new_market_product_volume
                            - allocated_total,
                            6,
                        )

                    elif existing_total > 0:
                        source_ratio = (
                            existing_value / existing_total
                        )

                        allocated_value = round(
                            new_market_product_volume
                            * source_ratio,
                            6,
                        )

                    else:
                        # When all source values are zero, split evenly.
                        source_count = len(
                            existing_source_values
                        )

                        allocated_value = round(
                            new_market_product_volume
                            / source_count,
                            6,
                        )

                    volume_values[month_index] = (
                        allocated_value
                    )

                    allocated_total += allocated_value

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
    Save recalculated values back to existing forecast_outputs rows.

    Supported market_share hierarchy:

        Overall product:
            Overall / ALL / product

        Market total:
            market / ALL / ALL

        Market product:
            market / ALL / product

        Source total:
            market / source / ALL

        Source product:
            market / source / product

    Notes:
        - NULL, blank and "ALL" are treated as aggregate source markers.
        - "Unknown" remains a valid real source.
        - Existing database hierarchy values are preserved exactly.
        - Only rows already present in forecast_outputs are updated.
    """

    original_share_rows = original_metrics.get(
        "market_share",
        [],
    )

    if not original_share_rows:
        raise ValueError(
            "No original market-share rows were found."
        )

    # =====================================================
    # Helpers
    # =====================================================

    def normalize_label(value):
        if value is None:
            return ""

        return str(value).strip().casefold()

    def is_blank_source(value):
        return (
            value is None
            or not str(value).strip()
        )

    def is_all_source(value):
        return normalize_label(value) == "all"

    def is_aggregate_source(value):
        return (
            is_blank_source(value)
            or is_all_source(value)
        )

    def is_all_product(value):
        return normalize_label(value) == "all"

    def is_overall_market(value):
        return normalize_label(value) == "overall"

    def find_actual_key(mapping, requested_key):
        requested_normalized = normalize_label(
            requested_key
        )

        for actual_key in mapping:
            if (
                normalize_label(actual_key)
                == requested_normalized
            ):
                return actual_key

        return None

    def get_market_node(market_name):
        markets = tree.get(
            "markets",
            {},
        )

        actual_market_name = find_actual_key(
            markets,
            market_name,
        )

        if actual_market_name is None:
            return None

        return markets[actual_market_name]

    def get_source_node(
        market_node,
        source_name,
    ):
        sources = market_node.get(
            "sources",
            {},
        )

        actual_source_name = find_actual_key(
            sources,
            source_name,
        )

        if actual_source_name is None:
            return None

        return sources[actual_source_name]

    def get_product_node(
        source_node,
        product_name,
    ):
        products = source_node.get(
            "products",
            {},
        )

        actual_product_name = find_actual_key(
            products,
            product_name,
        )

        if actual_product_name is None:
            return None

        return products[actual_product_name]

    def get_market_product_volume(
        market_node,
        product_name,
    ):
        """
        Sum a product's volume across every real source
        inside one market.
        """

        market_volume = list(
            market_node.get(
                "volume",
                [],
            )
        )

        month_count = len(market_volume)

        aggregated_product_volume = [
            0.0
        ] * month_count

        product_found = False

        for source_node in market_node.get(
            "sources",
            {},
        ).values():

            product_node = get_product_node(
                source_node=source_node,
                product_name=product_name,
            )

            if product_node is None:
                continue

            product_found = True

            product_volume = list(
                product_node.get(
                    "volume",
                    [],
                )
            )

            for index in range(month_count):
                if index >= len(product_volume):
                    continue

                aggregated_product_volume[index] += float(
                    product_volume[index] or 0
                )

        if not product_found:
            return None

        return aggregated_product_volume

    def get_market_product_share(
        market_node,
        product_name,
    ):
        """
        Calculate product share inside a market.

        product share =
            product volume across market sources
            ------------------------------------ * 100
                       market volume
        """

        market_volume = list(
            market_node.get(
                "volume",
                [],
            )
        )

        product_volume = get_market_product_volume(
            market_node=market_node,
            product_name=product_name,
        )

        if product_volume is None:
            return None

        market_product_share = []

        for index, current_market_volume in enumerate(
            market_volume
        ):
            current_market_volume = float(
                current_market_volume or 0
            )

            current_product_volume = (
                float(product_volume[index] or 0)
                if index < len(product_volume)
                else 0.0
            )

            if current_market_volume == 0:
                market_product_share.append(0.0)
            else:
                market_product_share.append(
                    (
                        current_product_volume
                        / current_market_volume
                    )
                    * 100
                )

        return market_product_share

    def get_overall_product_share(product_name):
        """
        Calculate product share across all markets.

        overall product share =
            product volume across all markets
            --------------------------------- * 100
                     overall volume
        """

        overall_volume = list(
            tree.get(
                "overall",
                {},
            ).get(
                "volume",
                [],
            )
        )

        month_count = len(overall_volume)

        overall_product_volume = [
            0.0
        ] * month_count

        product_found = False

        for market_node in tree.get(
            "markets",
            {},
        ).values():

            market_product_volume = (
                get_market_product_volume(
                    market_node=market_node,
                    product_name=product_name,
                )
            )

            if market_product_volume is None:
                continue

            product_found = True

            for index in range(month_count):
                if index >= len(market_product_volume):
                    continue

                overall_product_volume[index] += float(
                    market_product_volume[index] or 0
                )

        if not product_found:
            return None

        overall_product_share = []

        for index, current_overall_volume in enumerate(
            overall_volume
        ):
            current_overall_volume = float(
                current_overall_volume or 0
            )

            current_product_volume = float(
                overall_product_volume[index] or 0
            )

            if current_overall_volume == 0:
                overall_product_share.append(0.0)
            else:
                overall_product_share.append(
                    (
                        current_product_volume
                        / current_overall_volume
                    )
                    * 100
                )

        return overall_product_share

    def get_available_market_products(
        market_node,
    ):
        product_names = set()

        for source_node in market_node.get(
            "sources",
            {},
        ).values():
            product_names.update(
                source_node.get(
                    "products",
                    {},
                ).keys()
            )

        return sorted(product_names)

    def get_available_overall_products():
        product_names = set()

        for market_node in tree.get(
            "markets",
            {},
        ).values():
            product_names.update(
                get_available_market_products(
                    market_node
                )
            )

        return sorted(product_names)

    # =====================================================
    # Save all existing market-share rows
    # =====================================================

    for original_row in original_share_rows:

        market_name = original_row.get(
            "market"
        )

        database_source = original_row.get(
            "source_of_market"
        )

        product_name = original_row.get(
            "product"
        )

        original_forecast_data = original_row.get(
            "forecast_data"
        )

        # =================================================
        # Case 0: Overall rows
        #
        # Overall / ALL / Biktarvy
        # Overall / ALL / Descovy
        # Overall / ALL / Truvada
        # =================================================

        if is_overall_market(market_name):

            if not is_aggregate_source(
                database_source
            ):
                raise ValueError(
                    "An Overall market-share row contains "
                    "a non-aggregate source: "
                    f"{market_name}/"
                    f"{database_source}/"
                    f"{product_name}."
                )

            # Support Overall / ALL / ALL if it is ever added.
            if is_all_product(product_name):
                overall_values = [
                    100.0
                ] * len(
                    tree.get(
                        "overall",
                        {},
                    ).get(
                        "volume",
                        [],
                    )
                )

            else:
                overall_values = (
                    get_overall_product_share(
                        product_name
                    )
                )

                if overall_values is None:
                    raise ValueError(
                        "The Overall product could not be "
                        "resolved in the calculation tree: "
                        f"{market_name}/"
                        f"{database_source}/"
                        f"{product_name}. "
                        f"Available products: "
                        f"{get_available_overall_products()}."
                    )

            upsert_forecast_output(
                cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                metric="market_share",
                market=market_name,
                source_of_market=database_source,
                product=product_name,
                forecast_data=build_updated_forecast_data(
                    original_forecast_data=(
                        original_forecast_data
                    ),
                    full_values=overall_values,
                ),
            )

            continue

        # =================================================
        # Resolve a real market
        # =================================================

        market_node = get_market_node(
            market_name
        )

        if market_node is None:
            raise ValueError(
                "Market from forecast_outputs does not exist "
                "in the calculation tree: "
                f"{market_name}. "
                f"Available markets: "
                f"{list(tree.get('markets', {}).keys())}."
            )

        # =================================================
        # Case 1: Market total
        #
        # Non-retail / ALL / ALL
        # Retail     / ALL / ALL
        # =================================================

        if (
            is_aggregate_source(database_source)
            and is_all_product(product_name)
        ):
            upsert_forecast_output(
                cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                metric="market_share",
                market=market_name,
                source_of_market=database_source,
                product=product_name,
                forecast_data=build_updated_forecast_data(
                    original_forecast_data=(
                        original_forecast_data
                    ),
                    full_values=market_node["share"],
                ),
            )

            continue

        # =================================================
        # Case 2: Market product
        #
        # Non-retail / ALL / Biktarvy
        # Retail     / ALL / Descovy
        # =================================================

        if is_aggregate_source(database_source):

            market_product_share = (
                get_market_product_share(
                    market_node=market_node,
                    product_name=product_name,
                )
            )

            if market_product_share is None:
                raise ValueError(
                    "The market-product row could not be "
                    "resolved in the calculation tree: "
                    f"{market_name}/"
                    f"{database_source}/"
                    f"{product_name}. "
                    f"Available products: "
                    f"{get_available_market_products(market_node)}."
                )

            upsert_forecast_output(
                cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                metric="market_share",
                market=market_name,
                source_of_market=database_source,
                product=product_name,
                forecast_data=build_updated_forecast_data(
                    original_forecast_data=(
                        original_forecast_data
                    ),
                    full_values=market_product_share,
                ),
            )

            continue

        # =================================================
        # Resolve a real source
        # =================================================

        source_node = get_source_node(
            market_node=market_node,
            source_name=database_source,
        )

        if source_node is None:
            available_sources = list(
                market_node.get(
                    "sources",
                    {},
                ).keys()
            )

            raise ValueError(
                "The original forecast-output source could "
                "not be resolved in the calculation tree: "
                f"{market_name}/{database_source}. "
                f"Available sources: "
                f"{available_sources}."
            )

        # =================================================
        # Case 3: Source total
        #
        # Non-retail / ADAP    / ALL
        # Non-retail / Federal / ALL
        # =================================================

        if is_all_product(product_name):
            upsert_forecast_output(
                cursor,
                ta_name=ta_name,
                scenario_name=scenario_name,
                metric="market_share",
                market=market_name,
                source_of_market=database_source,
                product=product_name,
                forecast_data=build_updated_forecast_data(
                    original_forecast_data=(
                        original_forecast_data
                    ),
                    full_values=source_node["share"],
                ),
            )

            continue

        # =================================================
        # Case 4: Source product
        #
        # Retained for compatibility if these rows are
        # introduced later.
        # =================================================

        product_node = get_product_node(
            source_node=source_node,
            product_name=product_name,
        )

        if product_node is None:
            available_products = list(
                source_node.get(
                    "products",
                    {},
                ).keys()
            )

            raise ValueError(
                "The original forecast-output product could "
                "not be resolved in the calculation tree: "
                f"{market_name}/"
                f"{database_source}/"
                f"{product_name}. "
                f"Available products: "
                f"{available_products}."
            )

        upsert_forecast_output(
            cursor,
            ta_name=ta_name,
            scenario_name=scenario_name,
            metric="market_share",
            market=market_name,
            source_of_market=database_source,
            product=product_name,
            forecast_data=build_updated_forecast_data(
                original_forecast_data=(
                    original_forecast_data
                ),
                full_values=product_node["share"],
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
        market=original_volume_row.get(
            "market"
        ),
        source_of_market=original_volume_row.get(
            "source_of_market"
        ),
        product=original_volume_row.get(
            "product"
        ),
        forecast_data=build_updated_forecast_data(
            original_forecast_data=(
                original_volume_row["forecast_data"]
            ),
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


