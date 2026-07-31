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

def flatten_table_rows(rows):
    """
    Flatten hierarchical table rows.

    Example:

        Biktarvy
            Non-retail
            Retail

    becomes:

        Biktarvy
        Non-retail
        Retail
    """

    flattened_rows = []

    for row in rows or []:

        flattened_rows.append(
            row
        )

        children = get_row_value(
            row,
            "children",
            [],
        ) or []

        if children:
            flattened_rows.extend(
                flatten_table_rows(
                    children
                )
            )

    return flattened_rows

def normalize_label(value):
    """
    Normalize labels for case-insensitive comparisons.
    """

    if value is None:
        return ""

    return str(value).strip().casefold()

def get_product_market_distribution(
    *,
    tree: dict,
    product_name: str,
    month_index: int,
):
    """
    Return the distribution of one product across markets.

    For each product and month:

        sum(market shares) = 100
    """

    market_product_volumes = {}

    for market_name, market_node in tree.get(
        "markets",
        {},
    ).items():

        market_product_volume = (
            get_market_product_volume(
                market_node=market_node,
                product_name=product_name,
            )
        )

        if (
            market_product_volume is None
            or month_index >= len(
                market_product_volume
            )
        ):
            volume = 0.0
        else:
            volume = float(
                market_product_volume[
                    month_index
                ]
                or 0
            )

        market_product_volumes[
            market_name
        ] = volume

    product_total_volume = sum(
        market_product_volumes.values()
    )

    if product_total_volume == 0:
        return {
            market_name: 0.0
            for market_name
            in market_product_volumes
        }

    return {
        market_name: (
            market_volume
            / product_total_volume
            * 100
        )
        for market_name, market_volume
        in market_product_volumes.items()
    }

def get_product_market_share_from_matrix(
    *,
    matrix: dict[str, dict[str, list[float]]],
    product_name: str,
    market_name: str,
    market_names: list[str],
    month_index: int,
) -> float:
    """
    Product -> Market share:

        product volume in selected market
        ---------------------------------
        product volume across all markets
    """

    product_total_volume = sum(
        float(
            get_matrix_product_volume(
                matrix=matrix,
                market_name=current_market,
                product_name=product_name,
                month_index=month_index,
            )
            or 0
        )
        for current_market in market_names
    )

    selected_market_volume = float(
        get_matrix_product_volume(
            matrix=matrix,
            market_name=market_name,
            product_name=product_name,
            month_index=month_index,
        )
        or 0
    )

    if product_total_volume == 0:
        return 0.0

    return (
        selected_market_volume
        / product_total_volume
        * 100.0
    )

def recompute_product_market_inputs(
    tree: dict,
    selected_indexes: list[int],
    decimals: int = 2,
):
    """
    Rebuild Product->Market input shares from the
    latest tree volumes.

    This keeps product_market_inputs synchronized
    after Product-Market edits.
    """

    markets = tree.get("markets", {})
    products = tree.get("products", {})

    product_market_inputs = {}

    for product_name in products:

        overall_share = products[product_name]["share"]

        product_market_inputs[product_name] = {
            "overall_share": list(overall_share),
            "markets": {},
        }

        for month_index in selected_indexes:

            # -----------------------------------------
            # Product total volume
            # -----------------------------------------

            product_total = 0.0

            market_volumes = {}

            for market_name, market in markets.items():

                volume = 0.0

                for source in market.get("sources", {}).values():

                    product = (
                        source
                        .get("products", {})
                        .get(product_name)
                    )

                    if product is None:
                        continue

                    volume += float(
                        product["volume"][month_index] or 0
                    )

                market_volumes[market_name] = volume
                product_total += volume

            # -----------------------------------------
            # Convert to shares
            # -----------------------------------------

            for market_name, volume in market_volumes.items():

                share = (
                    round(
                        volume / product_total * 100,
                        decimals,
                    )
                    if product_total > 0
                    else 0.0
                )

                product_market_inputs[
                    product_name
                ]["markets"].setdefault(
                    market_name,
                    [0.0] * len(tree["months"])
                )[month_index] = share

    tree["product_market_inputs"] = product_market_inputs

    return tree

def apply_product_market_level_edits(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
    decimals: int = 2,
):
    """
    Apply Product -> Market edits.

    Rules
    -----
    - Product total volume remains fixed.
    - Only values that differ from the current matrix are
      treated as actual edits.
    - Old rows remaining in payload.edited_rows are ignored
      when their submitted values match the latest matrix.
    - Unedited markets are normalized.
    - Matrix stores volumes.
    """

    if payload.selected_metric != "market_share":
        raise ValueError(
            "Product-Market Level currently supports "
            "market_share editing only."
        )

    if payload.selected_table_view != "product_market_level":
        raise ValueError(
            "Unsupported table view for Product-Market editing: "
            f"{payload.selected_table_view!r}."
        )

    if not selected_indexes:
        raise ValueError(
            "No selected month indexes were supplied."
        )

    markets = list(
        tree.get("markets", {}).keys()
    )

    products = list(
        tree.get("products", {}).keys()
    )

    if not markets:
        raise ValueError(
            "No markets exist in the calculation tree."
        )

    if not products:
        raise ValueError(
            "No products exist in the calculation tree."
        )

    if len(markets) < 2:
        raise ValueError(
            "Product-Market editing requires at least two markets."
        )

    submitted_rows = rows_by_label(
        payload.edited_table_rows or []
    )

    edited_rows = set(
        payload.edited_rows or []
    )

    if not edited_rows:
        raise ValueError(
            "No edited Product-Market rows were supplied."
        )

    calculation_precision = 6
    calculation_tolerance = 0.000001
    validation_tolerance = 10 ** (-decimals)

    actual_edits_detected = False

    for value_position, month_index in enumerate(
        selected_indexes
    ):
        for product_name in products:

            product_row = submitted_rows.get(
                product_name
            )

            if product_row is None:
                continue

            market_children = rows_by_label(
                product_row.children or []
            )

            current_market_values = [
                float(
                    matrix[market_name][product_name][
                        month_index
                    ]
                    or 0
                )
                for market_name in markets
            ]

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
                        "Edited Product-Market row was not found. "
                        f"Product={product_name!r}, "
                        f"market={market_name!r}."
                    )

                if value_position >= len(
                    child_row.values
                ):
                    raise ValueError(
                        "Edited value count does not match the "
                        "selected month count. "
                        f"Product={product_name!r}, "
                        f"market={market_name!r}, "
                        f"month_index={month_index}."
                    )

                raw_value = child_row.values[
                    value_position
                ]

                try:
                    submitted_share = float(
                        raw_value
                    )
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        "Invalid Product-Market share. "
                        f"Product={product_name!r}, "
                        f"market={market_name!r}, "
                        f"month_index={month_index}, "
                        f"value={raw_value!r}."
                    ) from exc

                if not 0 <= submitted_share <= 100:
                    raise ValueError(
                        "Product-Market share must be between "
                        "0 and 100. "
                        f"Product={product_name!r}, "
                        f"market={market_name!r}, "
                        f"month_index={month_index}, "
                        f"value={submitted_share}."
                    )

                # =============================================
                # Detect whether this is an actual new edit
                # =============================================

                current_market_volume = (
                    current_market_values[
                        market_position
                    ]
                )

                current_share = (
                    current_market_volume
                    / fixed_product_total
                    * 100.0
                    if fixed_product_total > 0
                    else 0.0
                )

                submitted_display_share = round(
                    submitted_share,
                    decimals,
                )

                current_display_share = round(
                    current_share,
                    decimals,
                )

                # Ignore rows retained from previous saves.
                if (
                    submitted_display_share
                    == current_display_share
                ):
                    continue

                submitted_volume = round(
                    fixed_product_total
                    * submitted_display_share
                    / 100.0,
                    calculation_precision,
                )

                edited_market_values[
                    market_position
                ] = submitted_volume

            if not edited_market_values:
                continue

            actual_edits_detected = True

            total_edited_volume = sum(
                edited_market_values.values()
            )

            if (
                total_edited_volume
                > fixed_product_total
                + calculation_tolerance
            ):
                edited_shares = {
                    markets[position]: round(
                        volume
                        / fixed_product_total
                        * 100.0,
                        decimals,
                    )
                    if fixed_product_total > 0
                    else 0.0
                    for position, volume
                    in edited_market_values.items()
                }

                raise ValueError(
                    "Changed Product-Market values exceed the "
                    "product total. This usually means multiple "
                    "markets were changed for the same product "
                    "and month and their shares exceed 100%. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}, "
                    f"edited_shares={edited_shares}."
                )

            redistributed_market_values = (
                redistribute_fixed_total(
                    current_values=current_market_values,
                    fixed_total=fixed_product_total,
                    edited_values=edited_market_values,
                )
            )

            for market_position, market_name in enumerate(
                markets
            ):
                matrix[market_name][product_name][
                    month_index
                ] = round(
                    float(
                        redistributed_market_values[
                            market_position
                        ]
                    ),
                    decimals,
                )

            # =============================================
            # Validate fixed product total
            # =============================================

            recalculated_product_total = sum(
                float(
                    matrix[market_name][product_name][
                        month_index
                    ]
                    or 0
                )
                for market_name in markets
            )

            total_rounding_tolerance = (
                len(markets)
                * validation_tolerance
            )

            if abs(
                recalculated_product_total
                - fixed_product_total
            ) > total_rounding_tolerance:
                raise ValueError(
                    "Product total changed during Product-Market "
                    "redistribution. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}, "
                    f"expected={fixed_product_total:.6f}, "
                    f"received={recalculated_product_total:.6f}."
                )

            # =============================================
            # Validate actual edited values
            # =============================================

            for (
                market_position,
                expected_volume,
            ) in edited_market_values.items():

                market_name = markets[
                    market_position
                ]

                actual_volume = float(
                    matrix[market_name][product_name][
                        month_index
                    ]
                    or 0
                )

                if round(
                    actual_volume,
                    decimals,
                ) != round(
                    expected_volume,
                    decimals,
                ):
                    raise ValueError(
                        "Edited Product-Market value was not "
                        "preserved. "
                        f"Product={product_name!r}, "
                        f"market={market_name!r}, "
                        f"month_index={month_index}, "
                        f"expected="
                        f"{expected_volume:.{decimals}f}, "
                        f"received="
                        f"{actual_volume:.{decimals}f}."
                    )

    if not actual_edits_detected:
        raise ValueError(
            "No changed Product-Market values were detected. "
            "The submitted values already match the current "
            "forecast."
        )

    return matrix


def normalize_single_selection(
    value,
    *,
    field_name: str,
):
    if isinstance(value, list):
        cleaned_values = [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

        if len(cleaned_values) != 1:
            raise ValueError(
                f"Exactly one {field_name} must be "
                "selected for this edit."
            )

        return cleaned_values[0]

    normalized_value = str(
        value or ""
    ).strip()

    if not normalized_value:
        raise ValueError(
            f"A {field_name} must be selected "
            "for this edit."
        )

    return normalized_value


def find_matching_key(
    mapping: dict,
    requested_key,
):
    requested_normalized = str(
        requested_key or ""
    ).strip().casefold()

    for actual_key in mapping:
        if (
            str(actual_key).strip().casefold()
            == requested_normalized
        ):
            return actual_key

    return None


def get_row_value(
    row,
    field_name: str,
    default=None,
):
    if isinstance(row, dict):
        return row.get(
            field_name,
            default,
        )

    return getattr(
        row,
        field_name,
        default,
    )


def parse_share_value(
    *,
    value,
    row_label: str,
    month_index: int,
):
    if value is None:
        raise ValueError(
            "Product-Market share cannot be null "
            f"for {row_label!r} at month index "
            f"{month_index}."
        )

    try:
        parsed_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Invalid Product-Market share for "
            f"{row_label!r} at month index "
            f"{month_index}: {value!r}."
        ) from exc

    if not 0 <= parsed_value <= 100:
        raise ValueError(
            "Product-Market share must be between "
            f"0 and 100. Received {parsed_value} "
            f"for {row_label!r}."
        )

    return parsed_value

def get_matrix_product_values(
    *,
    matrix: dict,
    market_name: str,
    product_name: str,
):
    actual_market = find_matching_key(
        matrix,
        market_name,
    )

    if actual_market is None:
        raise ValueError(
            f"Market {market_name!r} does not exist "
            "in the edit matrix."
        )

    market_products = matrix[
        actual_market
    ]

    actual_product = find_matching_key(
        market_products,
        product_name,
    )

    if actual_product is None:
        raise ValueError(
            f"Product {product_name!r} does not exist "
            f"under market {market_name!r} in the "
            "edit matrix."
        )

    product_values = market_products[
        actual_product
    ]

    # Support either:
    # matrix[market][product] = [...]
    #
    # or:
    # matrix[market][product] = {"volume": [...]}

    if isinstance(product_values, dict):
        product_values = product_values.get(
            "volume",
            [],
        )

    return product_values


def get_matrix_product_volume(
    *,
    matrix: dict,
    market_name: str,
    product_name: str,
    month_index: int,
):
    values = get_matrix_product_values(
        matrix=matrix,
        market_name=market_name,
        product_name=product_name,
    )

    if month_index >= len(values):
        raise ValueError(
            "Month index is outside the matrix values: "
            f"{month_index}."
        )

    return float(
        values[month_index] or 0
    )


def set_matrix_product_volume(
    *,
    matrix: dict,
    market_name: str,
    product_name: str,
    month_index: int,
    value: float,
):
    actual_market = find_matching_key(
        matrix,
        market_name,
    )

    if actual_market is None:
        raise ValueError(
            f"Market {market_name!r} does not exist "
            "in the edit matrix."
        )

    market_products = matrix[
        actual_market
    ]

    actual_product = find_matching_key(
        market_products,
        product_name,
    )

    if actual_product is None:
        raise ValueError(
            f"Product {product_name!r} does not exist "
            f"under market {market_name!r}."
        )

    product_node = market_products[
        actual_product
    ]

    if isinstance(product_node, dict):
        values = product_node.setdefault(
            "volume",
            [],
        )
    else:
        values = product_node

    if month_index >= len(values):
        raise ValueError(
            "Month index is outside the matrix values: "
            f"{month_index}."
        )

    values[month_index] = float(
        value
    )

def get_product_total_volume(
    *,
    tree: dict,
    matrix: dict,
    product_name: str,
    month_index: int,
):
    """
    Keep the current top-level Product total fixed.
    """

    products = tree.get(
        "products",
        {},
    )

    actual_product = find_matching_key(
        products,
        product_name,
    )

    if actual_product is not None:
        volumes = list(
            products[
                actual_product
            ].get(
                "volume",
                [],
            )
            or []
        )

        if month_index < len(volumes):
            return float(
                volumes[month_index] or 0
            )

    # Fallback: sum Product volume across markets.
    total = 0.0

    for market_name in tree.get(
        "markets",
        {},
    ):
        total += get_matrix_product_volume(
            matrix=matrix,
            market_name=market_name,
            product_name=product_name,
            month_index=month_index,
        )

    return total


def get_product_market_share(
    *,
    tree,
    matrix,
    product_name,
    market_name,
    month_index,
):
    product_total = get_product_total_volume(
        tree=tree,
        matrix=matrix,
        product_name=product_name,
        month_index=month_index,
    )

    product_market_volume = get_matrix_product_volume(
        matrix=matrix,
        market_name=market_name,
        product_name=product_name,
        month_index=month_index,
    )

    if product_total == 0:
        return 0.0

    return (
        product_market_volume
        / product_total
        * 100
    )

def round_shares_to_100(
    *,
    shares: dict,
    ordered_labels: list,
    decimals: int = 2,
):
    if not ordered_labels:
        return {}

    rounded = {}
    running_total = 0.0

    for label in ordered_labels[:-1]:
        current_value = round(
            float(
                shares.get(
                    label,
                    0,
                )
            ),
            decimals,
        )

        rounded[label] = current_value
        running_total += current_value

    last_label = ordered_labels[-1]

    rounded[last_label] = round(
        100.0 - running_total,
        decimals,
    )

    return rounded
            
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

from copy import deepcopy


def apply_product_level_edits(
    tree: dict,
    payload: dict,
    selected_indexes: list[int],
    decimals: int = 2,
) -> dict:
    selected_metric = payload.get(
        "selected_metric"
    )

    selected_view = payload.get(
        "selected_table_view"
    )

    if selected_metric != "market_share":
        raise ValueError(
            "Product Level editing currently supports "
            "market_share only."
        )

    if selected_view != "product_level":
        raise ValueError(
            "Unsupported table view for Product Level "
            f"editing: {selected_view!r}."
        )

    months = list(
        tree.get("months", [])
        or []
    )

    products = (
        tree.get("products", {})
        or {}
    )

    if not products:
        raise ValueError(
            "No products exist in the calculation tree."
        )

    edited_rows = {
        str(label).strip()
        for label in (
            payload.get("edited_rows", [])
            or []
        )
        if str(label).strip()
    }

    submitted_rows = (
        payload.get("edited_table_rows", [])
        or []
    )

    if not edited_rows:
        raise ValueError(
            "No edited Product Level rows were supplied."
        )

    if not selected_indexes:
        raise ValueError(
            "No selected month indexes were supplied."
        )

    # edits_by_month[tree_month_index][product] = value
    edits_by_month: dict[
        int,
        dict[str, float],
    ] = {}

    tolerance = 0.000001

    for row in submitted_rows:
        if not isinstance(row, dict):
            continue

        product_name = str(
            row.get("label", "")
        ).strip()

        if product_name not in edited_rows:
            continue

        if product_name not in products:
            raise ValueError(
                "Edited product does not exist in the "
                f"calculation tree: {product_name!r}."
            )

        submitted_values = list(
            row.get("values", [])
            or []
        )

        if len(submitted_values) != len(
            selected_indexes
        ):
            raise ValueError(
                "Edited value count mismatch for "
                f"{product_name!r}. Expected "
                f"{len(selected_indexes)}, received "
                f"{len(submitted_values)}."
            )

        existing_shares = list(
            products[product_name].get(
                "share",
                [],
            )
            or []
        )

        for submitted_index, raw_value in enumerate(
            submitted_values
        ):
            tree_month_index = selected_indexes[
                submitted_index
            ]

            if tree_month_index >= len(
                existing_shares
            ):
                raise ValueError(
                    "Selected month index is outside the "
                    f"share array for {product_name!r}: "
                    f"{tree_month_index}."
                )

            if raw_value is None:
                raise ValueError(
                    "Product Level value cannot be null "
                    f"for {product_name!r} at "
                    f"{months[tree_month_index]!r}."
                )

            try:
                submitted_value = float(
                    raw_value
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Invalid Product Level value for "
                    f"{product_name!r} at "
                    f"{months[tree_month_index]!r}: "
                    f"{raw_value!r}."
                ) from exc

            if not 0 <= submitted_value <= 100:
                raise ValueError(
                    "Product Level share must be between "
                    f"0 and 100. Received "
                    f"{submitted_value} for "
                    f"{product_name!r}."
                )

            existing_value = float(
                existing_shares[
                    tree_month_index
                ]
                or 0
            )

            # Only treat the cell as edited when the
            # submitted value differs from the original.
            if abs(
                submitted_value - existing_value
            ) <= tolerance:
                continue

            edits_by_month.setdefault(
                tree_month_index,
                {},
            )[product_name] = (
                submitted_value
            )

    if not edits_by_month:
        raise ValueError(
            "No changed Product Level values were "
            "detected."
        )

    product_names = list(
        products.keys()
    )

    # Store old product volumes before recalculation.
    old_product_volumes = {
        product_name: list(
            product_node.get(
                "volume",
                [],
            )
            or []
        )
        for product_name, product_node
        in products.items()
    }

    # ================================================
    # Apply edits and normalize each affected month
    # ================================================

    for month_index, month_edits in (
        edits_by_month.items()
    ):
        edited_products = set(
            month_edits.keys()
        )

        edited_total = sum(
            month_edits.values()
        )

        if edited_total > 100 + tolerance:
            raise ValueError(
                "Edited Product Level shares exceed "
                f"100% for {months[month_index]!r}. "
                f"Edited total: {edited_total:.2f}%."
            )

        unedited_products = [
            product_name
            for product_name in product_names
            if product_name not in edited_products
        ]

        remaining_share = (
            100.0 - edited_total
        )

        if not unedited_products:
            if abs(remaining_share) > 0.01:
                raise ValueError(
                    "All products were edited for "
                    f"{months[month_index]!r}, but "
                    f"their total is "
                    f"{edited_total:.2f}%."
                )

        for product_name, edited_value in (
            month_edits.items()
        ):
            products[product_name]["share"][
                month_index
            ] = round(
                edited_value,
                decimals,
            )

        if unedited_products:
            current_unedited_total = sum(
                float(
                    products[product_name][
                        "share"
                    ][month_index]
                    or 0
                )
                for product_name in unedited_products
            )

            normalized_values = {}

            if current_unedited_total > 0:
                for product_name in (
                    unedited_products
                ):
                    current_value = float(
                        products[product_name][
                            "share"
                        ][month_index]
                        or 0
                    )

                    normalized_values[
                        product_name
                    ] = (
                        current_value
                        / current_unedited_total
                        * remaining_share
                    )
            else:
                equal_share = (
                    remaining_share
                    / len(unedited_products)
                )

                normalized_values = {
                    product_name: equal_share
                    for product_name
                    in unedited_products
                }

            running_total = edited_total

            for product_name in (
                unedited_products[:-1]
            ):
                normalized_value = round(
                    normalized_values[
                        product_name
                    ],
                    decimals,
                )

                products[product_name]["share"][
                    month_index
                ] = normalized_value

                running_total += normalized_value

            last_product = unedited_products[-1]

            products[last_product]["share"][
                month_index
            ] = round(
                100.0 - running_total,
                decimals,
            )

    # ================================================
    # Recalculate Product Level volumes
    # ================================================

    overall_volumes = list(
        tree.get("overall", {}).get(
            "volume",
            [],
        )
        or []
    )

    for product_name, product_node in (
        products.items()
    ):
        product_node["volume"] = [
            round(
                float(overall_volume or 0)
                * float(product_share or 0)
                / 100,
                decimals,
            )
            for overall_volume, product_share in zip(
                overall_volumes,
                product_node["share"],
            )
        ]

    # Preserve Product-Channel proportions.
    rescale_product_channel_volumes(
        tree=tree,
        old_product_volumes=(
            old_product_volumes
        ),
        decimals=decimals,
    )

    return tree

def rescale_product_channel_volumes(
    tree: dict,
    old_product_volumes: dict,
    decimals: int = 2,
):
    """
    Rescale Product-Channel volumes after a Product Level edit.

    Example:

        Old Biktarvy total = 27,365
        New Biktarvy total = 34,837

        Existing channel distribution is preserved:
            Retail      26.44%
            Non-retail  73.56%
    """

    products = (
        tree.get("products", {})
        or {}
    )

    markets = (
        tree.get("markets", {})
        or {}
    )

    month_count = len(
        tree.get("months", [])
        or []
    )

    for product_name, product_node in (
        products.items()
    ):
        old_totals = list(
            old_product_volumes.get(
                product_name,
                [],
            )
            or []
        )

        new_totals = list(
            product_node.get(
                "volume",
                [],
            )
            or []
        )

        if (
            len(old_totals) != month_count
            or len(new_totals) != month_count
        ):
            continue

        scale_factors = []

        for old_total, new_total in zip(
            old_totals,
            new_totals,
        ):
            old_total = float(
                old_total or 0
            )
            new_total = float(
                new_total or 0
            )

            if old_total != 0:
                scale_factors.append(
                    new_total / old_total
                )
            else:
                scale_factors.append(None)

        for market_name, market_node in (
            markets.items()
        ):
            sources = (
                market_node.get(
                    "sources",
                    {},
                )
                or {}
            )

            for source_node in sources.values():
                source_products = (
                    source_node.get(
                        "products",
                        {},
                    )
                    or {}
                )

                underlying_product = (
                    source_products.get(
                        product_name
                    )
                )

                if not underlying_product:
                    continue

                old_channel_volumes = list(
                    underlying_product.get(
                        "volume",
                        [],
                    )
                    or []
                )

                if (
                    len(old_channel_volumes)
                    != month_count
                ):
                    continue

                new_channel_volumes = []

                for month_index, old_value in (
                    enumerate(
                        old_channel_volumes
                    )
                ):
                    factor = scale_factors[
                        month_index
                    ]

                    if factor is None:
                        # Cannot infer a distribution when
                        # the previous product total was zero.
                        new_value = float(
                            old_value or 0
                        )
                    else:
                        new_value = (
                            float(old_value or 0)
                            * factor
                        )

                    new_channel_volumes.append(
                        round(
                            new_value,
                            decimals,
                        )
                    )

                underlying_product["volume"] = (
                    new_channel_volumes
                )

def update_product_level_metric_rows(
    metrics: dict,
    tree: dict,
):
    """
    Update raw metric rows after Product Level editing.

    Updates:

        market_share:
            ALL | ALL | Product

        market_volume:
            ALL | ALL | Product, when those rows exist
    """

    products = (
        tree.get("products", {})
        or {}
    )

    # =====================================================
    # Update market_share rows
    # =====================================================

    for row in (
        metrics.get("market_share", [])
        or []
    ):
        market = normalize_dimension(
            row.get("market")
        )
        source = normalize_dimension(
            row.get("source_of_market")
        )
        product = normalize_dimension(
            row.get("product")
        )

        is_product_level_row = (
            is_all(market)
            and is_all(source)
            and not is_all(product)
        )

        if not is_product_level_row:
            continue

        if product not in products:
            continue

        replace_forecast_values(
            forecast_data=row.get(
                "forecast_data",
                {},
            ),
            complete_values=products[
                product
            ]["share"],
        )

    # =====================================================
    # Update market_volume rows, if present
    # =====================================================

    for row in (
        metrics.get("market_volume", [])
        or []
    ):
        market = normalize_dimension(
            row.get("market")
        )
        source = normalize_dimension(
            row.get("source_of_market")
        )
        product = normalize_dimension(
            row.get("product")
        )

        is_product_level_row = (
            is_all(market)
            and is_all(source)
            and not is_all(product)
        )

        if not is_product_level_row:
            continue

        if product not in products:
            continue

        replace_forecast_values(
            forecast_data=row.get(
                "forecast_data",
                {},
            ),
            complete_values=products[
                product
            ]["volume"],
        )

    return metrics

def replace_forecast_values(
    forecast_data: dict,
    complete_values: list,
):
    """
    Split a complete monthly array back into train and
    forecast values using forecast_start_index.
    """

    if not isinstance(
        forecast_data,
        dict,
    ):
        raise ValueError(
            "forecast_data must be a dictionary."
        )

    forecast_start_index = int(
        forecast_data.get(
            "forecast_start_index",
            0,
        )
        or 0
    )

    if (
        forecast_start_index < 0
        or forecast_start_index
        > len(complete_values)
    ):
        raise ValueError(
            "Invalid forecast_start_index: "
            f"{forecast_start_index}."
        )

    forecast_data["train_values"] = list(
        complete_values[
            :forecast_start_index
        ]
    )

    forecast_data["forecast_values"] = list(
        complete_values[
            forecast_start_index:
        ]
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

def recompute_top_level_products(
    tree: dict,
    month_index: int,
):
    """
    Recompute overall product totals from all markets/sources.

    This drives the Product -> Market table.
    """

    overall_volume = tree["overall"]["volume"][month_index]

    for product_name, top_product in tree["products"].items():

        total_volume = 0.0

        for market in tree["markets"].values():

            for source in market.get("sources", {}).values():

                products = source.get("products", {})

                actual_product = find_matching_key(
                    products,
                    product_name,
                )

                if actual_product is None:
                    continue

                total_volume += float(
                    products[actual_product]["volume"][month_index]
                    or 0
                )

        top_product["volume"][month_index] = round(
            total_volume,
            6,
        )

        top_product["share"][month_index] = calculate_percentage(
            numerator=total_volume,
            denominator=overall_volume,
        )

def apply_market_product_level_edits(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    payload: EditSaveRequest,
    selected_indexes: list[int],
    decimals: int = 2,
):
    """
    Apply Market -> Product edits.

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

    Business rules
    --------------
    - The selected market total remains fixed.
    - Edited product values remain fixed.
    - Unedited products are normalized proportionally.
    - Product shares within each market total exactly 100%.
    - Updating this matrix causes Product -> Market values
      to be recomputed later from the updated volumes.
    """

    if payload.selected_table_view != "market_product_level":
        raise ValueError(
            "Unsupported table view for Market-Product editing: "
            f"{payload.selected_table_view!r}."
        )

    if payload.selected_metric not in {
        "market_share",
        "market_volume",
    }:
        raise ValueError(
            "Market-Product Level supports only "
            "'market_share' and 'market_volume'."
        )

    markets = list(
        tree.get("markets", {}).keys()
    )

    products = list(
        tree.get("products", {}).keys()
    )

    if not markets:
        raise ValueError(
            "No markets exist in the calculation tree."
        )

    if not products:
        raise ValueError(
            "No products exist in the calculation tree."
        )

    if not selected_indexes:
        raise ValueError(
            "No selected month indexes were supplied."
        )

    submitted_rows = rows_by_label(
        payload.edited_table_rows or []
    )

    edited_product_labels = {
        normalize_label(label)
        for label in (payload.edited_rows or [])
        if normalize_label(label)
    }

    if not edited_product_labels:
        raise ValueError(
            "No edited Market-Product rows were supplied."
        )

    calculation_precision = 6
    comparison_tolerance = 0.011
    validation_tolerance = 0.000001

    changes_detected = False

    for value_position, month_index in enumerate(
        selected_indexes
    ):

        for market_name in markets:

            market_row = submitted_rows.get(
                market_name
            )

            if market_row is None:
                continue

            submitted_product_rows = rows_by_label(
                market_row.children or []
            )

            # =================================================
            # Current product volumes within this market
            # =================================================

            current_product_volumes = [
                round(
                    max(
                        0.0,
                        float(
                            matrix[
                                market_name
                            ][
                                product_name
                            ][
                                month_index
                            ]
                            or 0.0
                        ),
                    ),
                    calculation_precision,
                )
                for product_name in products
            ]

            current_market_total = round(
                sum(current_product_volumes),
                calculation_precision,
            )

            # The market total must remain fixed while products
            # inside the market are redistributed.
            fixed_market_total = current_market_total

            if fixed_market_total < 0:
                raise ValueError(
                    "Market total cannot be negative. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}."
                )

            edited_product_values: dict[int, float] = {}
            edited_product_positions: set[int] = set()

            # =================================================
            # Detect edited product occurrence
            # =================================================

            for product_position, product_name in enumerate(
                products
            ):

                if (
                    normalize_label(product_name)
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

                raw_submitted_value = (
                    submitted_product_row.values[
                        value_position
                    ]
                )

                try:
                    submitted_value = float(
                        raw_submitted_value
                    )
                except (
                    TypeError,
                    ValueError,
                ) as exc:
                    raise ValueError(
                        "Invalid submitted value for "
                        f"{market_name!r} -> "
                        f"{product_name!r} at position "
                        f"{value_position}: "
                        f"{raw_submitted_value!r}."
                    ) from exc

                if submitted_value < 0:
                    raise ValueError(
                        "Submitted value cannot be negative. "
                        f"Market={market_name!r}, "
                        f"product={product_name!r}, "
                        f"value={submitted_value}."
                    )

                current_product_volume = (
                    current_product_volumes[
                        product_position
                    ]
                )

                # =============================================
                # Market Share
                #
                # Child percentage is relative to the selected
                # market total, not the overall market volume.
                # =============================================

                if payload.selected_metric == "market_share":

                    if submitted_value > 100:
                        raise ValueError(
                            "Market-Product share cannot exceed "
                            "100. "
                            f"Market={market_name!r}, "
                            f"product={product_name!r}, "
                            f"value={submitted_value}."
                        )

                    current_value = (
                        calculate_percentage(
                            numerator=current_product_volume,
                            denominator=fixed_market_total,
                        )
                    )

                    value_changed = (
                        abs(
                            submitted_value
                            - current_value
                        )
                        > comparison_tolerance
                    )

                    submitted_product_volume = round(
                        fixed_market_total
                        * submitted_value
                        / 100.0,
                        calculation_precision,
                    )

                # =============================================
                # Market Volume
                # =============================================

                else:

                    current_value = current_product_volume

                    value_changed = (
                        abs(
                            submitted_value
                            - current_value
                        )
                        > comparison_tolerance
                    )

                    submitted_product_volume = round(
                        submitted_value,
                        calculation_precision,
                    )

                # The same product exists under multiple
                # markets. Only the occurrence whose submitted
                # value differs is treated as edited.
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

            changes_detected = True

            edited_total = sum(
                edited_product_values.values()
            )

            if (
                edited_total
                > fixed_market_total
                + validation_tolerance
            ):
                raise ValueError(
                    "Edited product values exceed the fixed "
                    "market total. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}, "
                    f"edited_total={edited_total:.6f}, "
                    f"market_total={fixed_market_total:.6f}."
                )

            # =================================================
            # Normalize unedited products proportionally
            # =================================================

            redistributed_product_values = (
                redistribute_within_market(
                    current_product_values=(
                        current_product_volumes
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

            # Apply any tiny rounding residual to an untouched
            # product so explicitly edited values remain fixed.
            untouched_positions = [
                position
                for position in range(len(products))
                if position
                not in edited_product_positions
            ]

            if untouched_positions:
                correction_position = (
                    untouched_positions[-1]
                )
            else:
                correction_position = len(products) - 1

            redistributed_product_values = (
                force_values_to_exact_total(
                    values=redistributed_product_values,
                    target_total=fixed_market_total,
                    correction_position=(
                        correction_position
                    ),
                    precision=calculation_precision,
                )
            )

            # =================================================
            # Write updated product volumes into matrix
            # =================================================

            for product_position, product_name in enumerate(
                products
            ):
                matrix[
                    market_name
                ][
                    product_name
                ][
                    month_index
                ] = round(
                    redistributed_product_values[
                        product_position
                    ],
                    calculation_precision,
                )

            # =================================================
            # Validate market total
            # =================================================

            recalculated_market_total = round(
                sum(
                    matrix[
                        market_name
                    ][
                        product_name
                    ][
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
                    f"expected={fixed_market_total:.6f}, "
                    f"calculated="
                    f"{recalculated_market_total:.6f}."
                )

            # =================================================
            # Validate product shares total 100%
            # =================================================

            if fixed_market_total > 0:

                calculated_shares = [
                    (
                        matrix[
                            market_name
                        ][
                            product_name
                        ][
                            month_index
                        ]
                        / fixed_market_total
                        * 100.0
                    )
                    for product_name in products
                ]

                calculated_share_total = sum(
                    calculated_shares
                )

                if abs(
                    calculated_share_total - 100.0
                ) > 0.0001:
                    raise ValueError(
                        "Market-Product shares do not total "
                        "100%. "
                        f"Market={market_name!r}, "
                        f"month_index={month_index}, "
                        f"calculated_total="
                        f"{calculated_share_total:.6f}."
                    )

    if not changes_detected:
        raise ValueError(
            "No changed Market-Product Level values were "
            "detected. The submitted values matched the "
            "current calculated values."
        )

    return matrix



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

def get_product_market_distribution(
    *,
    tree: dict,
    product_name: str,
    month_index: int,
):
    """
    Returns

    {
        "Retail": 58.33,
        "Non-retail": 41.67
    }

    Shares always sum to 100.
    """

    market_volumes = {}

    total_product_volume = 0.0

    for market_name, market in tree["markets"].items():

        market_product_volume = 0.0

        for source in market.get("sources", {}).values():

            products = source.get("products", {})

            actual_product = find_matching_key(
                products,
                product_name,
            )

            if actual_product is None:
                continue

            market_product_volume += float(
                products[actual_product]["volume"][month_index]
                or 0
            )

        market_volumes[market_name] = market_product_volume

        total_product_volume += market_product_volume

    distribution = {}

    for market_name, volume in market_volumes.items():

        distribution[market_name] = calculate_percentage(
            numerator=volume,
            denominator=total_product_volume,
        )

    return distribution

def recompute_tree(
    tree: dict,
    selected_indexes: list[int],
):
    """
    Recompute dependent values after an edit.

    Order
    -----
    Product volumes
        ↓
    Source volumes & shares
        ↓
    Market volumes & shares
        ↓
    Overall product volumes & shares
    """

    overall_volumes = tree["overall"]["volume"]

    for month_index in selected_indexes:

        # =====================================================
        # 1. Recompute sources from product volumes
        # =====================================================

        for market in tree["markets"].values():

            for source in market.get("sources", {}).values():

                products = source.get("products", {})

                source_volume = round(
                    sum(
                        float(
                            product["volume"][month_index] or 0
                        )
                        for product in products.values()
                    ),
                    6,
                )

                source["volume"][month_index] = source_volume

                for product in products.values():

                    product["share"][month_index] = (
                        calculate_percentage(
                            numerator=float(
                                product["volume"][month_index] or 0
                            ),
                            denominator=source_volume,
                        )
                    )

        # =====================================================
        # 2. Recompute markets from sources
        # =====================================================

        for market in tree["markets"].values():

            sources = market.get("sources", {})

            market_volume = round(
                sum(
                    float(
                        source["volume"][month_index] or 0
                    )
                    for source in sources.values()
                ),
                6,
            )

            market["volume"][month_index] = market_volume

            market["share"][month_index] = (
                calculate_percentage(
                    numerator=market_volume,
                    denominator=float(
                        overall_volumes[month_index] or 0
                    ),
                )
            )

            for source in sources.values():

                source["share"][month_index] = (
                    calculate_percentage(
                        numerator=float(
                            source["volume"][month_index] or 0
                        ),
                        denominator=market_volume,
                    )
                )

        # =====================================================
        # 3. Recompute overall product totals
        # =====================================================

        for product_name, top_product in tree.get(
            "products",
            {},
        ).items():

            total_volume = 0.0

            for market in tree["markets"].values():

                for source in market.get(
                    "sources",
                    {},
                ).values():

                    product = source.get(
                        "products",
                        {},
                    ).get(product_name)

                    if product is None:
                        continue

                    total_volume += float(
                        product["volume"][month_index] or 0
                    )

            total_volume = round(
                total_volume,
                6,
            )

            top_product["volume"][month_index] = total_volume

            top_product["share"][month_index] = (
                calculate_percentage(
                    numerator=total_volume,
                    denominator=float(
                        overall_volumes[month_index] or 0
                    ),
                )
            )

        # =====================================================
        # 4. Optional validation (debug only)
        # =====================================================

        recomputed_market_total = round(
            sum(
                float(
                    market["volume"][month_index] or 0
                )
                for market in tree["markets"].values()
            ),
            6,
        )

        expected_overall = round(
            float(
                overall_volumes[month_index] or 0
            ),
            6,
        )

        difference = abs(
            recomputed_market_total
            - expected_overall
        )

        # Allow small rounding differences
        if difference > 0.05:
            raise ValueError(
                "Market totals do not match overall volume. "
                f"Month index={month_index}, "
                f"Markets={recomputed_market_total:.6f}, "
                f"Overall={expected_overall:.6f}, "
                f"Difference={difference:.6f}"
            )

    return tree

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
        """
        Aggregate market markers used for Product Level rows.

        Supported database values:
            ALL
            Overall
            NULL
            blank
        """

        normalized = normalize_label(value)

        return normalized in {
            "",
            "all",
            "overall",
        }
    
    def get_overall_product_node(
        product_name,
    ):
        """
        Resolve a top-level product from tree["products"].
        """

        products = tree.get(
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

    def get_overall_product_share(
        product_name,
    ):
        """
        Return the canonical top-level Product share.

        Product Level rows are stored in:
            tree["products"][product]["share"]

        Falls back to volume-based calculation only when the
        top-level product share is unavailable.
        """

        product_node = get_overall_product_node(
            product_name
        )

        if product_node is not None:
            product_shares = list(
                product_node.get(
                    "share",
                    [],
                )
                or []
            )

            if product_shares:
                return [
                    float(value or 0)
                    for value in product_shares
                ]

        # Fallback for older calculation trees that do not
        # contain top-level Product nodes.
        overall_volume = list(
            tree.get(
                "overall",
                {},
            ).get(
                "volume",
                [],
            )
            or []
        )

        month_count = len(
            overall_volume
        )

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

            for index in range(
                month_count
            ):
                if index >= len(
                    market_product_volume
                ):
                    continue

                overall_product_volume[
                    index
                ] += float(
                    market_product_volume[
                        index
                    ]
                    or 0
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
                overall_product_volume[
                    index
                ]
                or 0
            )

            if current_overall_volume == 0:
                overall_product_share.append(
                    0.0
                )
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
        product_names = set(
            tree.get(
                "products",
                {},
            ).keys()
        )

        # Backward-compatible fallback.
        if not product_names:
            for market_node in tree.get(
                "markets",
                {},
            ).values():
                product_names.update(
                    get_available_market_products(
                        market_node
                    )
                )

        return sorted(
            product_names
        )

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


