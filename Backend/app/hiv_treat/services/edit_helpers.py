import json
from fastapi import HTTPException
from app.hiv_treat.routes.market_events_models import *
from app.hiv_treat.services.response_builder_market_events import *
from app.hiv_treat.services.generic_builders_market_events import *
from app.hiv_treat.services.market_event_helpers import *
from app.hiv_treat.services.calculation_tree_market_events import *
from app.hiv_treat.services.common_helpers import *


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

def rebuild_product_market_matrix(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    decimals: int = 6,
) -> dict[str, dict[str, list[float]]]:
    """
    Rebuild the Product -> Market volume matrix from:

        tree["products"][product]["volume"]
        tree["product_market_inputs"][product]["markets"][market]

    This prevents source-level double-counting.

    Rules
    -----
    - Each product total remains equal to tree["products"][product]["volume"].
    - Product -> Market shares are normalized to 100%.
    - The last market receives the residual volume to preserve
      the exact product total.
    """

    months = list(tree.get("months", []) or [])
    month_count = len(months)

    markets = list(
        (tree.get("markets", {}) or {}).keys()
    )

    products = tree.get("products", {}) or {}

    product_market_inputs = (
        tree.get("product_market_inputs", {}) or {}
    )

    if not markets:
        raise ValueError(
            "No markets exist in the calculation tree."
        )

    rebuilt_matrix = {
        market_name: {
            product_name: [0.0] * month_count
            for product_name in products
        }
        for market_name in markets
    }

    for product_name, product_node in products.items():

        product_volumes = list(
            product_node.get("volume", []) or []
        )

        if len(product_volumes) != month_count:
            raise ValueError(
                "Top-level product volume length mismatch. "
                f"Product={product_name!r}, "
                f"expected={month_count}, "
                f"received={len(product_volumes)}."
            )

        product_input = (
            product_market_inputs.get(product_name, {}) or {}
        )

        input_markets = (
            product_input.get("markets", {}) or {}
        )

        for month_index in range(month_count):

            fixed_product_total = float(
                product_volumes[month_index] or 0
            )

            market_shares = []

            for market_name in markets:

                matching_market = next(
                    (
                        key
                        for key in input_markets
                        if (
                            str(key).strip().lower()
                            == str(market_name).strip().lower()
                        )
                    ),
                    None,
                )

                share_values = (
                    list(
                        input_markets.get(
                            matching_market,
                            [],
                        )
                        or []
                    )
                    if matching_market is not None
                    else []
                )

                share = (
                    float(
                        share_values[month_index] or 0
                    )
                    if month_index < len(share_values)
                    else 0.0
                )

                market_shares.append(
                    max(0.0, share)
                )

            share_total = sum(market_shares)

            # Fallback to the existing matrix distribution
            # if Product-Market input shares are unavailable.
            if share_total <= 0:

                current_volumes = [
                    float(
                        matrix
                        .get(market_name, {})
                        .get(product_name, [0.0] * month_count)[
                            month_index
                        ]
                        or 0
                    )
                    for market_name in markets
                ]

                current_total = sum(current_volumes)

                if current_total > 0:
                    market_shares = [
                        volume / current_total * 100.0
                        for volume in current_volumes
                    ]
                else:
                    market_shares = [
                        100.0 / len(markets)
                    ] * len(markets)

            else:
                # Normalize stored shares in case of rounding.
                market_shares = [
                    share / share_total * 100.0
                    for share in market_shares
                ]

            allocated_volume = 0.0

            for market_position, market_name in enumerate(
                markets
            ):

                if market_position == len(markets) - 1:
                    # Residual preserves the exact product total.
                    market_volume = round(
                        fixed_product_total
                        - allocated_volume,
                        decimals,
                    )
                else:
                    market_volume = round(
                        fixed_product_total
                        * market_shares[market_position]
                        / 100.0,
                        decimals,
                    )

                    allocated_volume += market_volume

                rebuilt_matrix[market_name][product_name][
                    month_index
                ] = market_volume

    return rebuilt_matrix

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

    Example
    -------
    Biktarvy
        Retail       <- edited
        Non-retail   <- normalized

    Rules
    -----
    - Product total remains FIXED.
    - Edited market share remains EXACTLY fixed.
    - Only unedited sibling markets are normalized.
    - Existing unedited market proportions are preserved.
    - Market volumes under each product sum exactly to
      the fixed Product total.
    - Matrix always stores high precision VOLUMES.
    """

    # =====================================================
    # 1. Validation
    # =====================================================

    if payload.selected_metric != "market_share":
        raise ValueError(
            "Product-Market Level currently supports "
            "market_share editing only."
        )

    if (
        payload.selected_table_view
        != "product_market_level"
    ):
        raise ValueError(
            "Unsupported table view for Product-Market "
            f"editing: {payload.selected_table_view!r}."
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
            "Product-Market editing requires at least "
            "two markets."
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

    comparison_tolerance = (
        10 ** (-(decimals + 1))
    )

    validation_tolerance = 0.000001

    actual_edits_detected = False

    # =====================================================
    # 2. Selected months
    # =====================================================

    for value_position, month_index in enumerate(
        selected_indexes
    ):

        # =================================================
        # 3. Each Product independently
        # =================================================

        for product_name in products:

            product_row = submitted_rows.get(
                product_name
            )

            if product_row is None:
                continue

            market_children = rows_by_label(
                product_row.children or []
            )

            # =============================================
            # Current Product -> Market volumes
            # =============================================

            current_market_values = []

            for market_name in markets:

                product_values = (
                    matrix
                    .get(market_name, {})
                    .get(product_name, [])
                    or []
                )

                if (
                    month_index
                    >= len(product_values)
                ):
                    raise ValueError(
                        "Matrix series length mismatch. "
                        f"Product={product_name!r}, "
                        f"Market={market_name!r}, "
                        f"month_index={month_index}."
                    )

                current_market_values.append(
                    round(
                        max(
                            0.0,
                            float(
                                product_values[
                                    month_index
                                ]
                                or 0
                            ),
                        ),
                        calculation_precision,
                    )
                )

            # =============================================
            # Fixed Product total
            # =============================================

            fixed_product_total = round(
                sum(current_market_values),
                calculation_precision,
            )

            # Product total remains fixed.
            if fixed_product_total < 0:
                raise ValueError(
                    "Product total cannot be negative. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}."
                )

            # =============================================
            # Detect actual edited market occurrences
            # =============================================

            edited_market_values = {}
            edited_market_positions = set()
            submitted_share_values = {}

            for (
                market_position,
                market_name,
            ) in enumerate(markets):

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
                        "Edited Product-Market row "
                        "was not found. "
                        f"Product={product_name!r}, "
                        f"Market={market_name!r}."
                    )

                if (
                    value_position
                    >= len(child_row.values)
                ):
                    raise ValueError(
                        "Edited value count does not "
                        "match selected months. "
                        f"Product={product_name!r}, "
                        f"Market={market_name!r}, "
                        f"position={value_position}."
                    )

                raw_value = (
                    child_row.values[
                        value_position
                    ]
                )

                try:
                    submitted_share = float(
                        raw_value
                    )

                except (
                    TypeError,
                    ValueError,
                ) as exc:

                    raise ValueError(
                        "Invalid Product-Market share. "
                        f"Product={product_name!r}, "
                        f"Market={market_name!r}, "
                        f"value={raw_value!r}."
                    ) from exc

                if not (
                    0
                    <= submitted_share
                    <= 100
                ):
                    raise ValueError(
                        "Product-Market share must be "
                        "between 0 and 100. "
                        f"Product={product_name!r}, "
                        f"Market={market_name!r}, "
                        f"value={submitted_share}."
                    )

                current_volume = (
                    current_market_values[
                        market_position
                    ]
                )

                current_share = (
                    current_volume
                    / fixed_product_total
                    * 100.0
                    if fixed_product_total
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

                # -----------------------------------------
                # Ignore stale edited_rows entries.
                # -----------------------------------------

                if (
                    abs(
                        submitted_display_share
                        - current_display_share
                    )
                    <= comparison_tolerance
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

                edited_market_positions.add(
                    market_position
                )

                submitted_share_values[
                    market_position
                ] = submitted_display_share

            if not edited_market_values:
                continue

            actual_edits_detected = True

            # =============================================
            # Validate edited values
            # =============================================

            edited_total = round(
                sum(
                    edited_market_values.values()
                ),
                calculation_precision,
            )

            if (
                edited_total
                > fixed_product_total
                + validation_tolerance
            ):
                raise ValueError(
                    "Edited Product-Market values exceed "
                    "the fixed Product total. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}, "
                    f"Edited={edited_total:.6f}, "
                    f"ProductTotal="
                    f"{fixed_product_total:.6f}."
                )

            # =============================================
            # Remaining volume belongs ONLY to unedited
            # markets.
            # =============================================

            remaining_volume = round(
                fixed_product_total
                - edited_total,
                calculation_precision,
            )

            unedited_positions = [
                position
                for position in range(
                    len(markets)
                )
                if position
                not in edited_market_positions
            ]

            redistributed_values = list(
                current_market_values
            )

            # =============================================
            # LOCK edited markets
            # =============================================

            for (
                position,
                edited_volume,
            ) in edited_market_values.items():

                redistributed_values[
                    position
                ] = round(
                    edited_volume,
                    calculation_precision,
                )

            # =============================================
            # Normalize ONLY unedited markets
            # =============================================

            if unedited_positions:

                current_unedited_total = round(
                    sum(
                        current_market_values[
                            position
                        ]
                        for position
                        in unedited_positions
                    ),
                    calculation_precision,
                )

                allocated = 0.0

                for (
                    list_position,
                    market_position,
                ) in enumerate(
                    unedited_positions
                ):

                    is_last = (
                        list_position
                        == len(
                            unedited_positions
                        ) - 1
                    )

                    if is_last:

                        normalized_volume = round(
                            remaining_volume
                            - allocated,
                            calculation_precision,
                        )

                    elif (
                        current_unedited_total
                        > 0
                    ):

                        ratio = (
                            current_market_values[
                                market_position
                            ]
                            / current_unedited_total
                        )

                        normalized_volume = round(
                            remaining_volume
                            * ratio,
                            calculation_precision,
                        )

                    else:

                        normalized_volume = round(
                            remaining_volume
                            / len(
                                unedited_positions
                            ),
                            calculation_precision,
                        )

                    redistributed_values[
                        market_position
                    ] = normalized_volume

                    allocated = round(
                        allocated
                        + normalized_volume,
                        calculation_precision,
                    )

            else:

                if (
                    abs(
                        edited_total
                        - fixed_product_total
                    )
                    > validation_tolerance
                ):
                    raise ValueError(
                        "All Product-Market children "
                        "were edited, but their total "
                        "does not equal the Product total. "
                        f"Product={product_name!r}, "
                        f"month_index={month_index}."
                    )

            # =============================================
            # Write HIGH PRECISION volumes to matrix
            #
            # IMPORTANT:
            # Do NOT round matrix to UI decimals.
            # =============================================

            for (
                market_position,
                market_name,
            ) in enumerate(markets):

                matrix[
                    market_name
                ][
                    product_name
                ][
                    month_index
                ] = round(
                    redistributed_values[
                        market_position
                    ],
                    calculation_precision,
                )

            # =============================================
            # Validate Product total remained fixed
            # =============================================

            recalculated_total = round(
                sum(
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
                    for market_name
                    in markets
                ),
                calculation_precision,
            )

            if (
                abs(
                    recalculated_total
                    - fixed_product_total
                )
                > validation_tolerance
            ):
                raise ValueError(
                    "Product total changed during "
                    "Product-Market redistribution. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}, "
                    f"Expected="
                    f"{fixed_product_total:.6f}, "
                    f"Calculated="
                    f"{recalculated_total:.6f}."
                )

            # =============================================
            # Validate edited shares stayed exact
            # =============================================

            if fixed_product_total > 0:

                for (
                    market_position,
                    expected_share,
                ) in (
                    submitted_share_values.items()
                ):

                    market_name = markets[
                        market_position
                    ]

                    actual_volume = float(
                        matrix[
                            market_name
                        ][
                            product_name
                        ][
                            month_index
                        ]
                        or 0
                    )

                    actual_share = (
                        actual_volume
                        / fixed_product_total
                        * 100.0
                    )

                    if (
                        abs(
                            actual_share
                            - expected_share
                        )
                        > 0.0001
                    ):
                        raise ValueError(
                            "Edited Product-Market share "
                            "was not preserved. "
                            f"Product={product_name!r}, "
                            f"Market={market_name!r}, "
                            f"Submitted="
                            f"{expected_share:.6f}%, "
                            f"Calculated="
                            f"{actual_share:.6f}%."
                        )

            # =============================================
            # Validate shares sum to 100%
            # =============================================

            if fixed_product_total > 0:

                share_total = sum(
                    (
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
                        / fixed_product_total
                        * 100.0
                    )
                    for market_name
                    in markets
                )

                if (
                    abs(
                        share_total
                        - 100.0
                    )
                    > 0.0001
                ):
                    raise ValueError(
                        "Product-Market shares do not "
                        "total 100%. "
                        f"Product={product_name!r}, "
                        f"month_index={month_index}, "
                        f"Total={share_total:.6f}%."
                    )

    if not actual_edits_detected:
        raise ValueError(
            "No changed Product-Market values were "
            "detected. The submitted values already "
            "match the current forecast."
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

    Example
    -------
    Non-retail
        Biktarvy = edited
        Descovy  = normalized
        Truvada  = normalized

    Business rules
    --------------
    - Market total remains fixed.
    - Edited product value remains EXACTLY fixed.
    - Only unedited sibling products are normalized.
    - Unedited products preserve their existing proportions.
    - Products inside each market total exactly 100%.
    """

    # =====================================================
    # 1. Validate request
    # =====================================================

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
        for label in (
            payload.edited_rows or []
        )
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

    # =====================================================
    # 2. Process selected months
    # =====================================================

    for value_position, month_index in enumerate(
        selected_indexes
    ):

        # =================================================
        # 3. Process each market independently
        # =================================================

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
            # 4. Read current product volumes
            # =================================================

            current_product_volumes = []

            for product_name in products:

                product_values = (
                    matrix
                    .get(market_name, {})
                    .get(product_name, [])
                    or []
                )

                if month_index >= len(
                    product_values
                ):
                    raise ValueError(
                        "Matrix product series length mismatch. "
                        f"Market={market_name!r}, "
                        f"Product={product_name!r}, "
                        f"month_index={month_index}."
                    )

                current_product_volumes.append(
                    round(
                        max(
                            0.0,
                            float(
                                product_values[
                                    month_index
                                ]
                                or 0
                            ),
                        ),
                        calculation_precision,
                    )
                )

            # =================================================
            # 5. Fixed parent market total
            # =================================================

            fixed_market_total = round(
                sum(
                    current_product_volumes
                ),
                calculation_precision,
            )

            if fixed_market_total < 0:
                raise ValueError(
                    "Market total cannot be negative. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}."
                )

            # =================================================
            # 6. Detect actual edited products
            # =================================================

            edited_product_values: dict[
                int,
                float,
            ] = {}

            edited_product_positions: set[int] = set()

            submitted_share_values: dict[
                int,
                float,
            ] = {}

            for (
                product_position,
                product_name,
            ) in enumerate(products):

                # Product not flagged by UI as edited.
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
                    raise ValueError(
                        "Missing submitted value. "
                        f"Market={market_name!r}, "
                        f"Product={product_name!r}, "
                        f"position={value_position}."
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
                        "Invalid submitted value. "
                        f"Market={market_name!r}, "
                        f"Product={product_name!r}, "
                        f"value="
                        f"{raw_submitted_value!r}."
                    ) from exc

                if submitted_value < 0:
                    raise ValueError(
                        "Submitted value cannot be negative. "
                        f"Market={market_name!r}, "
                        f"Product={product_name!r}, "
                        f"value={submitted_value}."
                    )

                current_product_volume = (
                    current_product_volumes[
                        product_position
                    ]
                )

                # =============================================
                # SHARE edit
                # =============================================

                if (
                    payload.selected_metric
                    == "market_share"
                ):

                    if submitted_value > 100:
                        raise ValueError(
                            "Market-Product share cannot "
                            "exceed 100%. "
                            f"Market={market_name!r}, "
                            f"Product={product_name!r}, "
                            f"value={submitted_value}."
                        )

                    current_share = (
                        (
                            current_product_volume
                            / fixed_market_total
                            * 100.0
                        )
                        if fixed_market_total
                        else 0.0
                    )

                    value_changed = (
                        abs(
                            submitted_value
                            - current_share
                        )
                        > comparison_tolerance
                    )

                    if not value_changed:
                        continue

                    # IMPORTANT:
                    # This exact volume corresponds to the
                    # submitted share.
                    submitted_volume = round(
                        fixed_market_total
                        * submitted_value
                        / 100.0,
                        calculation_precision,
                    )

                    submitted_share_values[
                        product_position
                    ] = submitted_value

                # =============================================
                # VOLUME edit
                # =============================================

                else:

                    value_changed = (
                        abs(
                            submitted_value
                            - current_product_volume
                        )
                        > comparison_tolerance
                    )

                    if not value_changed:
                        continue

                    submitted_volume = round(
                        submitted_value,
                        calculation_precision,
                    )

                edited_product_values[
                    product_position
                ] = submitted_volume

                edited_product_positions.add(
                    product_position
                )

            # Nothing actually changed in this market/month.
            if not edited_product_values:
                continue

            changes_detected = True

            # =================================================
            # 7. Validate edited total
            # =================================================

            edited_total = round(
                sum(
                    edited_product_values.values()
                ),
                calculation_precision,
            )

            if (
                edited_total
                > fixed_market_total
                + validation_tolerance
            ):
                raise ValueError(
                    "Edited product values exceed the "
                    "fixed market total. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}, "
                    f"edited_total={edited_total:.6f}, "
                    f"market_total="
                    f"{fixed_market_total:.6f}."
                )

            # =================================================
            # 8. Remaining volume belongs ONLY to unedited
            #    products
            # =================================================

            remaining_volume = round(
                fixed_market_total
                - edited_total,
                calculation_precision,
            )

            unedited_positions = [
                position
                for position in range(
                    len(products)
                )
                if position
                not in edited_product_positions
            ]

            # Start from existing values.
            redistributed_values = list(
                current_product_volumes
            )

            # =================================================
            # 9. LOCK edited products
            #
            # They are written first and NEVER touched again.
            # =================================================

            for (
                position,
                edited_volume,
            ) in edited_product_values.items():

                redistributed_values[
                    position
                ] = round(
                    edited_volume,
                    calculation_precision,
                )

            # =================================================
            # 10. Normalize ONLY unedited products
            # =================================================

            if unedited_positions:

                current_unedited_total = round(
                    sum(
                        current_product_volumes[
                            position
                        ]
                        for position
                        in unedited_positions
                    ),
                    calculation_precision,
                )

                allocated_total = 0.0

                for list_position, product_position in enumerate(
                    unedited_positions
                ):

                    # Last unedited product receives any
                    # floating-point residual.
                    is_last = (
                        list_position
                        == len(
                            unedited_positions
                        ) - 1
                    )

                    if is_last:

                        normalized_volume = round(
                            remaining_volume
                            - allocated_total,
                            calculation_precision,
                        )

                    elif current_unedited_total > 0:

                        existing_ratio = (
                            current_product_volumes[
                                product_position
                            ]
                            / current_unedited_total
                        )

                        normalized_volume = round(
                            remaining_volume
                            * existing_ratio,
                            calculation_precision,
                        )

                    else:

                        # Defensive fallback when all
                        # unedited products are zero.
                        normalized_volume = round(
                            remaining_volume
                            / len(
                                unedited_positions
                            ),
                            calculation_precision,
                        )

                    redistributed_values[
                        product_position
                    ] = normalized_volume

                    allocated_total = round(
                        allocated_total
                        + normalized_volume,
                        calculation_precision,
                    )

            # =================================================
            # 11. Special case:
            #     User edited every product
            # =================================================

            else:

                if (
                    abs(
                        edited_total
                        - fixed_market_total
                    )
                    > validation_tolerance
                ):
                    raise ValueError(
                        "All products were edited, but "
                        "their values do not equal the "
                        "fixed market total. "
                        f"Market={market_name!r}, "
                        f"month_index={month_index}, "
                        f"EditedTotal="
                        f"{edited_total:.6f}, "
                        f"MarketTotal="
                        f"{fixed_market_total:.6f}."
                    )

            # =================================================
            # 12. Write values into matrix
            # =================================================

            for (
                product_position,
                product_name,
            ) in enumerate(products):

                matrix[
                    market_name
                ][
                    product_name
                ][
                    month_index
                ] = round(
                    redistributed_values[
                        product_position
                    ],
                    calculation_precision,
                )

            # =================================================
            # 13. CRITICAL:
            #     Validate edited products remained exact
            # =================================================

            for (
                product_position,
                expected_volume,
            ) in edited_product_values.items():

                product_name = products[
                    product_position
                ]

                actual_volume = float(
                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ]
                    or 0
                )

                if (
                    abs(
                        actual_volume
                        - expected_volume
                    )
                    > validation_tolerance
                ):
                    raise ValueError(
                        "Edited Market-Product volume "
                        "was changed during normalization. "
                        f"Market={market_name!r}, "
                        f"Product={product_name!r}, "
                        f"Expected="
                        f"{expected_volume:.6f}, "
                        f"Actual="
                        f"{actual_volume:.6f}."
                    )

            # =================================================
            # 14. Validate submitted SHARE stayed exact
            # =================================================

            if (
                payload.selected_metric
                == "market_share"
                and fixed_market_total > 0
            ):

                for (
                    product_position,
                    submitted_share,
                ) in submitted_share_values.items():

                    product_name = products[
                        product_position
                    ]

                    actual_volume = float(
                        matrix[
                            market_name
                        ][
                            product_name
                        ][
                            month_index
                        ]
                        or 0
                    )

                    actual_share = (
                        actual_volume
                        / fixed_market_total
                        * 100.0
                    )

                    if (
                        abs(
                            actual_share
                            - submitted_share
                        )
                        > 0.0001
                    ):
                        raise ValueError(
                            "Edited Market-Product share "
                            "was not preserved. "
                            f"Market={market_name!r}, "
                            f"Product={product_name!r}, "
                            f"Submitted="
                            f"{submitted_share:.6f}%, "
                            f"Calculated="
                            f"{actual_share:.6f}%."
                        )

            # =================================================
            # 15. Validate market total unchanged
            # =================================================

            recalculated_market_total = round(
                sum(
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
                    for product_name
                    in products
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
                    "Market total changed during "
                    "Market-Product redistribution. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}, "
                    f"Expected="
                    f"{fixed_market_total:.6f}, "
                    f"Calculated="
                    f"{recalculated_market_total:.6f}."
                )

            # =================================================
            # 16. Validate shares total 100%
            # =================================================

            if fixed_market_total > 0:

                calculated_share_total = sum(
                    (
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
                        / fixed_market_total
                        * 100.0
                    )
                    for product_name in products
                )

                if (
                    abs(
                        calculated_share_total
                        - 100.0
                    )
                    > 0.0001
                ):
                    raise ValueError(
                        "Market-Product shares do not "
                        "total 100%. "
                        f"Market={market_name!r}, "
                        f"month_index={month_index}, "
                        f"CalculatedTotal="
                        f"{calculated_share_total:.6f}%."
                    )

    # =====================================================
    # 17. Make sure something actually changed
    # =====================================================

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

def get_canonical_sources(
    market: dict,
) -> dict:
    """
    Return the source nodes that should be used when
    calculating Market x Product totals.

    Current tree structure
    ----------------------
    Retail:
        Unknown

    Non-retail:
        ADAP
        Federal
        IQVIA
        Kaiser
        Unknown

    In this model, Unknown represents the complete market-level
    Product distribution.

    Therefore, when Unknown exists, named sources must NOT be
    added on top of it.
    """

    sources = market.get("sources", {}) or {}

    if "Unknown" in sources:
        return {
            "Unknown": sources["Unknown"]
        }

    return sources

def build_market_product_volume_matrix(
    tree: dict,
) -> dict[str, dict[str, list[float]]]:
    """
    Build canonical:

        Market -> Product -> Monthly Volume

    Rules
    -----
    1. Market volume in tree["markets"][market]["volume"]
       is the authoritative parent total.

    2. If "Unknown" exists, use its product volumes only
       to determine the product distribution within that market.

    3. Product volumes are normalized so that:

           sum(products in market) == market volume

    4. If no "Unknown" exists, product volumes are aggregated
       from the real source rows and then normalized to the
       market volume.

    This is important for Market -> Product editing because
    the selected market total must remain fixed.
    """

    months = tree.get("months", []) or []
    markets = tree.get("markets", {}) or {}
    products = tree.get("products", {}) or {}

    month_count = len(months)

    market_names = list(markets.keys())
    product_names = list(products.keys())

    calculation_precision = 6
    validation_tolerance = 0.05

    if not month_count:
        raise ValueError(
            "No months exist in the calculation tree."
        )

    if not market_names:
        raise ValueError(
            "No markets exist in the calculation tree."
        )

    if not product_names:
        raise ValueError(
            "No products exist in the calculation tree."
        )

    # =====================================================
    # 1. Initialize matrix
    # =====================================================

    matrix = {
        market_name: {
            product_name: [0.0] * month_count
            for product_name in product_names
        }
        for market_name in market_names
    }

    # =====================================================
    # 2. Build raw product distribution for each market
    # =====================================================

    for market_name, market in markets.items():

        sources = (
            market.get("sources", {})
            or {}
        )

        # -------------------------------------------------
        # If Unknown exists, it is the canonical
        # Market -> Product representation.
        # -------------------------------------------------

        if "Unknown" in sources:

            sources_to_use = {
                "Unknown": sources["Unknown"]
            }

        else:

            sources_to_use = sources

        for source_name, source in sources_to_use.items():

            source_products = (
                source.get("products", {})
                or {}
            )

            for product_name in product_names:

                product_node = (
                    source_products.get(product_name)
                )

                if product_node is None:
                    continue

                product_volumes = (
                    product_node.get("volume", [])
                    or []
                )

                for month_index in range(month_count):

                    if month_index >= len(product_volumes):
                        continue

                    value = float(
                        product_volumes[month_index]
                        or 0
                    )

                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ] = round(
                        matrix[
                            market_name
                        ][
                            product_name
                        ][
                            month_index
                        ]
                        + value,
                        calculation_precision,
                    )

    # =====================================================
    # 3. Normalize products INSIDE each market
    #
    # market["volume"] is authoritative.
    # =====================================================

    for market_name, market in markets.items():

        market_volumes = (
            market.get("volume", [])
            or []
        )

        if len(market_volumes) < month_count:
            raise ValueError(
                "Market volume series is shorter than "
                f"month series. Market={market_name!r}."
            )

        for month_index in range(month_count):

            target_market_volume = round(
                float(
                    market_volumes[
                        month_index
                    ]
                    or 0
                ),
                calculation_precision,
            )

            current_product_values = [
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
                        or 0
                    ),
                )
                for product_name in product_names
            ]

            current_product_total = round(
                sum(current_product_values),
                calculation_precision,
            )

            # ---------------------------------------------
            # Zero market
            # ---------------------------------------------

            if target_market_volume == 0:

                normalized_values = [
                    0.0
                    for _ in product_names
                ]

            # ---------------------------------------------
            # We have a product distribution.
            # Scale it to the authoritative market volume.
            # ---------------------------------------------

            elif current_product_total > 0:

                scale_factor = (
                    target_market_volume
                    / current_product_total
                )

                normalized_values = [
                    round(
                        value * scale_factor,
                        calculation_precision,
                    )
                    for value in current_product_values
                ]

            else:

                raise ValueError(
                    "Cannot build Market-Product matrix. "
                    "Market volume is positive but its "
                    "product total is zero. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}, "
                    f"market_volume="
                    f"{target_market_volume:.6f}."
                )

            # ---------------------------------------------
            # Correct floating-point / rounding residual.
            # ---------------------------------------------

            normalized_total = round(
                sum(normalized_values),
                calculation_precision,
            )

            residual = round(
                target_market_volume
                - normalized_total,
                calculation_precision,
            )

            if normalized_values:

                # Adjust the largest product, not an edited
                # product -- there are no edits at this stage.
                correction_position = max(
                    range(len(normalized_values)),
                    key=lambda index: (
                        normalized_values[index]
                    ),
                )

                normalized_values[
                    correction_position
                ] = round(
                    normalized_values[
                        correction_position
                    ]
                    + residual,
                    calculation_precision,
                )

            # ---------------------------------------------
            # Write normalized values back.
            # ---------------------------------------------

            for product_position, product_name in enumerate(
                product_names
            ):

                matrix[
                    market_name
                ][
                    product_name
                ][
                    month_index
                ] = normalized_values[
                    product_position
                ]

            # ---------------------------------------------
            # Validate this market.
            # ---------------------------------------------

            final_market_total = round(
                sum(
                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ]
                    for product_name in product_names
                ),
                calculation_precision,
            )

            if (
                abs(
                    final_market_total
                    - target_market_volume
                )
                > validation_tolerance
            ):
                raise ValueError(
                    "Unable to normalize products to "
                    "market volume. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}, "
                    f"Products={final_market_total:.6f}, "
                    f"MarketVolume="
                    f"{target_market_volume:.6f}."
                )

    # =====================================================
    # 4. Validate markets against Overall
    #
    # IMPORTANT:
    # We validate here but DO NOT change market totals.
    # Market totals are parent values for Channel->Product.
    # =====================================================

    overall_volumes = (
        tree.get("overall", {}).get(
            "volume",
            [],
        )
        or []
    )

    if len(overall_volumes) < month_count:
        raise ValueError(
            "Overall volume series is shorter "
            "than the month series."
        )

    for month_index in range(month_count):

        matrix_total = round(
            sum(
                matrix[
                    market_name
                ][
                    product_name
                ][
                    month_index
                ]
                for market_name in market_names
                for product_name in product_names
            ),
            calculation_precision,
        )

        overall_volume = round(
            float(
                overall_volumes[
                    month_index
                ]
                or 0
            ),
            calculation_precision,
        )

        difference = abs(
            matrix_total
            - overall_volume
        )

        # Small DB/rounding differences are acceptable here.
        # The actual edit must not change parent market totals.
        if difference > 20.0:

            market_breakdown = {
                market_name: round(
                    sum(
                        matrix[
                            market_name
                        ][
                            product_name
                        ][
                            month_index
                        ]
                        for product_name in product_names
                    ),
                    calculation_precision,
                )
                for market_name in market_names
            }

            raise ValueError(
                "Market totals materially differ from "
                "overall volume before editing. "
                f"Month={month_index}, "
                f"Markets={matrix_total:.6f}, "
                f"Overall={overall_volume:.6f}, "
                f"Difference={difference:.6f}, "
                f"Breakdown={market_breakdown}."
            )

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
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    selected_indexes: list[int],
):
    """
    Push Market x Product matrix back into the tree.

    Behaviour
    ---------
    1. If Unknown exists:
       - Unknown receives the exact canonical Market-Product value.

    2. Named sources such as:
           ADAP
           Federal
           IQVIA
           Kaiser

       are ALSO updated proportionally.

       This keeps Model Input and Market Event consistent.

    3. Existing source proportions for each product are preserved.

    4. The final source absorbs rounding residual.

    Important:
        Unknown is NOT included in the named-source redistribution
        because it represents the aggregate Market-Product row.
    """

    markets = (
        tree.get("markets", {})
        or {}
    )

    products = (
        tree.get("products", {})
        or {}
    )

    month_count = len(
        tree.get("months", [])
    )

    precision = 6

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

        market_matrix = (
            matrix.get(
                market_name,
                {},
            )
            or {}
        )

        unknown_source = (
            sources.get("Unknown")
        )

        # Named/real sources only.
        real_sources = {
            source_name: source_node
            for source_name, source_node
            in sources.items()
            if str(source_name).strip().lower()
            != "unknown"
        }

        for product_name in products:

            matrix_values = (
                market_matrix.get(
                    product_name
                )
            )

            if matrix_values is None:
                continue

            # =================================================
            # 1. Update canonical Unknown product
            # =================================================

            if unknown_source is not None:

                unknown_product = (
                    unknown_source
                    .get(
                        "products",
                        {},
                    )
                    .get(
                        product_name
                    )
                )

                if unknown_product is not None:

                    unknown_volumes = (
                        unknown_product.setdefault(
                            "volume",
                            [0.0] * month_count,
                        )
                    )

                    for month_index in (
                        selected_indexes
                    ):

                        if (
                            month_index
                            >= len(matrix_values)
                        ):
                            continue

                        unknown_volumes[
                            month_index
                        ] = round(
                            float(
                                matrix_values[
                                    month_index
                                ]
                                or 0
                            ),
                            precision,
                        )

            # =================================================
            # 2. Collect real source-product nodes
            # =================================================

            source_product_nodes = []

            for (
                source_name,
                source_node,
            ) in real_sources.items():

                product_node = (
                    source_node
                    .get(
                        "products",
                        {},
                    )
                    .get(
                        product_name
                    )
                )

                if product_node is None:
                    continue

                source_product_nodes.append(
                    (
                        source_name,
                        product_node,
                    )
                )

            # Retail may have only Unknown.
            # In that case there is nothing else to sync.
            if not source_product_nodes:
                continue

            # =================================================
            # 3. Redistribute canonical product volume across
            #    real sources proportionally
            # =================================================

            for month_index in (
                selected_indexes
            ):

                if (
                    month_index
                    >= len(matrix_values)
                ):
                    continue

                target_market_product_volume = (
                    round(
                        float(
                            matrix_values[
                                month_index
                            ]
                            or 0
                        ),
                        precision,
                    )
                )

                existing_source_values = []

                for (
                    source_name,
                    product_node,
                ) in source_product_nodes:

                    volume_values = (
                        product_node.get(
                            "volume",
                            [],
                        )
                        or []
                    )

                    existing_value = (
                        float(
                            volume_values[
                                month_index
                            ]
                            or 0
                        )
                        if month_index
                        < len(volume_values)
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
                ) in enumerate(
                    existing_source_values
                ):

                    volume_values = (
                        product_node.setdefault(
                            "volume",
                            [0.0] * month_count,
                        )
                    )

                    is_last = (
                        position
                        == len(
                            existing_source_values
                        ) - 1
                    )

                    if is_last:

                        allocated_value = round(
                            target_market_product_volume
                            - allocated_total,
                            precision,
                        )

                    elif existing_total > 0:

                        ratio = (
                            existing_value
                            / existing_total
                        )

                        allocated_value = round(
                            target_market_product_volume
                            * ratio,
                            precision,
                        )

                    else:

                        allocated_value = round(
                            target_market_product_volume
                            / len(
                                existing_source_values
                            ),
                            precision,
                        )

                    volume_values[
                        month_index
                    ] = allocated_value

                    allocated_total = round(
                        allocated_total
                        + allocated_value,
                        precision,
                    )

    return tree

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
    matrix: dict[str, dict[str, list[float]]] | None = None,
    normalize_matrix_to_overall: bool = False,
):
    """
    Recompute the calculation tree after edits.

    Canonical source
    ----------------
    When matrix is supplied:

        matrix[market][product][month]

    is the source of truth.

    Important rules
    ---------------
    1. Never sum Unknown + named sources to calculate market totals.

    2. Market totals come from the Market x Product matrix.

    3. Top-level product totals come from the same matrix.

    4. If Unknown exists, it represents the canonical
       Market -> Product structure.

    5. When normalize_matrix_to_overall=True, all matrix cells for
       a month are scaled by ONE common factor so that:

           sum(matrix) == overall

       This preserves all percentages exactly.

       Example:
           Non-retail -> Biktarvy = 25%

       remains 25% after global scaling.
    """

    if not selected_indexes:
        return tree

    markets = (
        tree.get("markets", {})
        or {}
    )

    top_products = (
        tree.get("products", {})
        or {}
    )

    overall_volumes = (
        tree.get("overall", {}).get(
            "volume",
            [],
        )
        or []
    )

    market_names = list(
        markets.keys()
    )

    product_names = list(
        top_products.keys()
    )

    calculation_precision = 6
    validation_tolerance = 0.05

    # =====================================================
    # Local helpers
    # =====================================================

    def percentage(
        numerator: float,
        denominator: float,
    ) -> float:
        if not denominator:
            return 0.0

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            calculation_precision,
        )

    def get_matrix_volume(
        market_name: str,
        product_name: str,
        month_index: int,
    ) -> float:

        if matrix is None:
            return 0.0

        values = (
            matrix
            .get(market_name, {})
            .get(product_name, [])
            or []
        )

        if month_index >= len(values):
            return 0.0

        return float(
            values[month_index]
            or 0
        )

    def get_sources_to_use(
        market: dict,
    ) -> dict:
        """
        Unknown is the canonical representation when present.
        """

        sources = (
            market.get("sources", {})
            or {}
        )

        if "Unknown" in sources:
            return {
                "Unknown": sources["Unknown"]
            }

        return sources

    # =====================================================
    # Process selected months
    # =====================================================

    for month_index in selected_indexes:

        if month_index >= len(
            overall_volumes
        ):
            raise ValueError(
                "Selected month index is outside "
                "the overall-volume range. "
                f"month_index={month_index}, "
                f"length={len(overall_volumes)}."
            )

        overall_volume = round(
            float(
                overall_volumes[
                    month_index
                ]
                or 0
            ),
            calculation_precision,
        )

        # =================================================
        # 1. Optional global reconciliation
        #
        # This is safe for SHARE edits because every matrix
        # cell is multiplied by the SAME factor.
        #
        # Therefore:
        #
        #     Biktarvy / Non-retail
        #
        # remains exactly the same percentage.
        # =================================================

        if (
            matrix is not None
            and normalize_matrix_to_overall
        ):

            current_matrix_total = round(
                sum(
                    get_matrix_volume(
                        market_name=market_name,
                        product_name=product_name,
                        month_index=month_index,
                    )
                    for market_name in market_names
                    for product_name in product_names
                ),
                calculation_precision,
            )

            if (
                overall_volume > 0
                and current_matrix_total > 0
                and abs(
                    current_matrix_total
                    - overall_volume
                ) > validation_tolerance
            ):

                scale_factor = (
                    overall_volume
                    / current_matrix_total
                )

                # -----------------------------------------
                # Scale every Market x Product cell by
                # exactly the same factor.
                # -----------------------------------------

                for market_name in market_names:

                    for product_name in product_names:

                        values = (
                            matrix
                            .get(
                                market_name,
                                {},
                            )
                            .get(
                                product_name,
                                [],
                            )
                        )

                        if (
                            values is None
                            or month_index
                            >= len(values)
                        ):
                            continue

                        values[
                            month_index
                        ] = round(
                            float(
                                values[
                                    month_index
                                ]
                                or 0
                            )
                            * scale_factor,
                            calculation_precision,
                        )

                # -----------------------------------------
                # Correct tiny rounding residual.
                # -----------------------------------------

                normalized_total = round(
                    sum(
                        get_matrix_volume(
                            market_name=market_name,
                            product_name=product_name,
                            month_index=month_index,
                        )
                        for market_name
                        in market_names
                        for product_name
                        in product_names
                    ),
                    calculation_precision,
                )

                residual = round(
                    overall_volume
                    - normalized_total,
                    calculation_precision,
                )

                if (
                    abs(residual) > 0
                    and market_names
                    and product_names
                ):

                    # Put only the microscopic rounding
                    # residual on the largest matrix cell.

                    largest_market = None
                    largest_product = None
                    largest_value = -1.0

                    for market_name in market_names:

                        for product_name in product_names:

                            value = (
                                get_matrix_volume(
                                    market_name=market_name,
                                    product_name=product_name,
                                    month_index=month_index,
                                )
                            )

                            if value > largest_value:
                                largest_value = value
                                largest_market = (
                                    market_name
                                )
                                largest_product = (
                                    product_name
                                )

                    if (
                        largest_market is not None
                        and largest_product is not None
                    ):

                        matrix[
                            largest_market
                        ][
                            largest_product
                        ][
                            month_index
                        ] = round(
                            matrix[
                                largest_market
                            ][
                                largest_product
                            ][
                                month_index
                            ]
                            + residual,
                            calculation_precision,
                        )

        # =================================================
        # 2. Recompute market totals FROM MATRIX
        # =================================================

        for market_name, market in (
            markets.items()
        ):

            if matrix is not None:

                market_volume = round(
                    sum(
                        get_matrix_volume(
                            market_name=market_name,
                            product_name=product_name,
                            month_index=month_index,
                        )
                        for product_name
                        in product_names
                    ),
                    calculation_precision,
                )

            else:

                canonical_sources = (
                    get_sources_to_use(
                        market
                    )
                )

                market_volume = round(
                    sum(
                        float(
                            (
                                source.get(
                                    "volume",
                                    [],
                                )
                                or []
                            )[month_index]
                            or 0
                        )
                        for source
                        in canonical_sources.values()
                        if month_index
                        < len(
                            source.get(
                                "volume",
                                [],
                            )
                            or []
                        )
                    ),
                    calculation_precision,
                )

            market_volumes = (
                market.get(
                    "volume",
                    [],
                )
                or []
            )

            market_shares = (
                market.get(
                    "share",
                    [],
                )
                or []
            )

            if (
                month_index
                >= len(market_volumes)
                or month_index
                >= len(market_shares)
            ):
                raise ValueError(
                    "Market series length mismatch. "
                    f"Market={market_name!r}, "
                    f"month_index={month_index}."
                )

            market["volume"][
                month_index
            ] = market_volume

            market["share"][
                month_index
            ] = percentage(
                market_volume,
                overall_volume,
            )

        # =================================================
        # Synchronize source level
        # =================================================

        for market_name, market in markets.items():

            sources = (
                market.get("sources", {})
                or {}
            )

            market_volume = float(
                market["volume"][month_index]
                or 0
            )

            # =================================================
            # 1. Update canonical Unknown source
            # =================================================

            unknown_source = sources.get(
                "Unknown"
            )

            if unknown_source is not None:

                unknown_volumes = (
                    unknown_source.get(
                        "volume",
                        [],
                    )
                    or []
                )

                unknown_shares = (
                    unknown_source.get(
                        "share",
                        [],
                    )
                    or []
                )

                if month_index < len(
                    unknown_volumes
                ):
                    unknown_source[
                        "volume"
                    ][
                        month_index
                    ] = round(
                        market_volume,
                        calculation_precision,
                    )

                if month_index < len(
                    unknown_shares
                ):
                    unknown_source[
                        "share"
                    ][
                        month_index
                    ] = (
                        100.0
                        if market_volume
                        else 0.0
                    )

                unknown_products = (
                    unknown_source.get(
                        "products",
                        {},
                    )
                    or {}
                )

                for product_name in product_names:

                    product_node = (
                        unknown_products.get(
                            product_name
                        )
                    )

                    if product_node is None:
                        continue

                    product_volumes = (
                        product_node.get(
                            "volume",
                            [],
                        )
                        or []
                    )

                    product_shares = (
                        product_node.get(
                            "share",
                            [],
                        )
                        or []
                    )

                    if (
                        month_index
                        >= len(product_volumes)
                    ):
                        continue

                    # Matrix is canonical for Market -> Product.
                    if matrix is not None:

                        product_volume = round(
                            get_matrix_volume(
                                market_name=market_name,
                                product_name=product_name,
                                month_index=month_index,
                            ),
                            calculation_precision,
                        )

                        product_node[
                            "volume"
                        ][
                            month_index
                        ] = product_volume

                    else:

                        product_volume = float(
                            product_volumes[
                                month_index
                            ]
                            or 0
                        )

                    if (
                        month_index
                        < len(product_shares)
                    ):

                        product_node[
                            "share"
                        ][
                            month_index
                        ] = percentage(
                            product_volume,
                            market_volume,
                        )

            # =================================================
            # 2. IMPORTANT:
            # Recompute REAL named sources too
            #
            # ADAP / Federal / IQVIA / Kaiser
            #
            # apply_matrix_to_tree() has already changed their
            # product volumes. Now their totals and shares must
            # be recalculated before saving.
            # =================================================

            real_sources = {
                source_name: source_node
                for source_name, source_node
                in sources.items()
                if (
                    str(source_name)
                    .strip()
                    .lower()
                    != "unknown"
                )
            }

            for (
                source_name,
                source_node,
            ) in real_sources.items():

                source_products = (
                    source_node.get(
                        "products",
                        {},
                    )
                    or {}
                )

                # ---------------------------------------------
                # Source total =
                # sum(updated product volumes)
                # ---------------------------------------------

                source_volume = round(
                    sum(
                        float(
                            (
                                product_node.get(
                                    "volume",
                                    [],
                                )
                                or []
                            )[month_index]
                            or 0
                        )
                        for product_node
                        in source_products.values()
                        if (
                            month_index
                            < len(
                                product_node.get(
                                    "volume",
                                    [],
                                )
                                or []
                            )
                        )
                    ),
                    calculation_precision,
                )

                source_volumes = (
                    source_node.get(
                        "volume",
                        [],
                    )
                    or []
                )

                source_shares = (
                    source_node.get(
                        "share",
                        [],
                    )
                    or []
                )

                if (
                    month_index
                    < len(source_volumes)
                ):
                    source_node[
                        "volume"
                    ][
                        month_index
                    ] = source_volume

                # ---------------------------------------------
                # Source share within market
                # ---------------------------------------------

                if (
                    month_index
                    < len(source_shares)
                ):
                    source_node[
                        "share"
                    ][
                        month_index
                    ] = percentage(
                        source_volume,
                        market_volume,
                    )

                # ---------------------------------------------
                # Product share within source
                # ---------------------------------------------

                for (
                    product_name,
                    product_node,
                ) in source_products.items():

                    product_volumes = (
                        product_node.get(
                            "volume",
                            [],
                        )
                        or []
                    )

                    product_shares = (
                        product_node.get(
                            "share",
                            [],
                        )
                        or []
                    )

                    if (
                        month_index
                        >= len(product_volumes)
                        or month_index
                        >= len(product_shares)
                    ):
                        continue

                    product_volume = float(
                        product_volumes[
                            month_index
                        ]
                        or 0
                    )

                    product_node[
                        "share"
                    ][
                        month_index
                    ] = percentage(
                        product_volume,
                        source_volume,
                    )

        # =================================================
        # 4. Recompute top-level products FROM MATRIX
        # =================================================

        for product_name, top_product in (
            top_products.items()
        ):

            if matrix is not None:

                total_volume = round(
                    sum(
                        get_matrix_volume(
                            market_name=market_name,
                            product_name=product_name,
                            month_index=month_index,
                        )
                        for market_name
                        in market_names
                    ),
                    calculation_precision,
                )

            else:

                total_volume = 0.0

                for market in (
                    markets.values()
                ):

                    canonical_sources = (
                        get_sources_to_use(
                            market
                        )
                    )

                    for source in (
                        canonical_sources.values()
                    ):

                        product_node = (
                            source.get(
                                "products",
                                {},
                            )
                            or {}
                        ).get(
                            product_name
                        )

                        if product_node is None:
                            continue

                        volumes = (
                            product_node.get(
                                "volume",
                                [],
                            )
                            or []
                        )

                        if (
                            month_index
                            >= len(volumes)
                        ):
                            continue

                        total_volume += float(
                            volumes[
                                month_index
                            ]
                            or 0
                        )

                total_volume = round(
                    total_volume,
                    calculation_precision,
                )

            top_product_volumes = (
                top_product.get(
                    "volume",
                    [],
                )
                or []
            )

            top_product_shares = (
                top_product.get(
                    "share",
                    [],
                )
                or []
            )

            if (
                month_index
                >= len(top_product_volumes)
                or month_index
                >= len(top_product_shares)
            ):
                raise ValueError(
                    "Top-level product series "
                    "length mismatch. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}."
                )

            top_product[
                "volume"
            ][
                month_index
            ] = total_volume

            top_product[
                "share"
            ][
                month_index
            ] = percentage(
                total_volume,
                overall_volume,
            )

        # =================================================
        # 5. Validate Markets == Overall
        # =================================================

        recomputed_market_total = round(
            sum(
                float(
                    market.get(
                        "volume",
                        [],
                    )[month_index]
                    or 0
                )
                for market
                in markets.values()
            ),
            calculation_precision,
        )

        market_difference = abs(
            recomputed_market_total
            - overall_volume
        )

        if (
            market_difference
            > validation_tolerance
        ):

            market_breakdown = {
                market_name: round(
                    float(
                        market.get(
                            "volume",
                            [],
                        )[month_index]
                        or 0
                    ),
                    calculation_precision,
                )
                for (
                    market_name,
                    market,
                ) in markets.items()
            }

            raise ValueError(
                "Market totals do not match "
                "overall volume. "
                f"Month index={month_index}, "
                f"Markets="
                f"{recomputed_market_total:.6f}, "
                f"Overall="
                f"{overall_volume:.6f}, "
                f"Difference="
                f"{market_difference:.6f}, "
                f"Breakdown="
                f"{market_breakdown}."
            )

        # =================================================
        # 6. Validate Products == Overall
        # =================================================

        recomputed_product_total = round(
            sum(
                float(
                    product_node.get(
                        "volume",
                        [],
                    )[month_index]
                    or 0
                )
                for product_node
                in top_products.values()
            ),
            calculation_precision,
        )

        product_difference = abs(
            recomputed_product_total
            - overall_volume
        )

        if (
            product_difference
            > validation_tolerance
        ):

            product_breakdown = {
                product_name: round(
                    float(
                        product_node.get(
                            "volume",
                            [],
                        )[month_index]
                        or 0
                    ),
                    calculation_precision,
                )
                for (
                    product_name,
                    product_node,
                ) in top_products.items()
            }

            raise ValueError(
                "Product totals do not match "
                "overall volume. "
                f"Month index={month_index}, "
                f"Products="
                f"{recomputed_product_total:.6f}, "
                f"Overall="
                f"{overall_volume:.6f}, "
                f"Difference="
                f"{product_difference:.6f}, "
                f"Breakdown="
                f"{product_breakdown}."
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
        Return canonical Market -> Product volume.

        Rules
        -----
        If "Unknown" exists, it represents the canonical
        Market -> Product level.

        Therefore:

            market / ALL / product

        must use:

            market -> Unknown -> product

        and must NOT sum:

            Unknown + ADAP + Federal + IQVIA + Kaiser

        If Unknown does not exist, fall back to aggregating
        the real sources.
        """

        sources = (
            market_node.get(
                "sources",
                {},
            )
            or {}
        )

        # =====================================================
        # Canonical Market -> Product node
        # =====================================================

        unknown_source = sources.get(
            "Unknown"
        )

        if unknown_source is not None:

            product_node = get_product_node(
                source_node=unknown_source,
                product_name=product_name,
            )

            if product_node is None:
                return None

            return [
                float(value or 0)
                for value in (
                    product_node.get(
                        "volume",
                        [],
                    )
                    or []
                )
            ]

        # =====================================================
        # Fallback:
        # no Unknown source exists
        # =====================================================

        market_volume = list(
            market_node.get(
                "volume",
                [],
            )
            or []
        )

        month_count = len(
            market_volume
        )

        aggregated_product_volume = [
            0.0
        ] * month_count

        product_found = False

        for source_node in sources.values():

            product_node = get_product_node(
                source_node=source_node,
                product_name=product_name,
            )

            if product_node is None:
                continue

            product_found = True

            product_volume = (
                product_node.get(
                    "volume",
                    [],
                )
                or []
            )

            for index in range(
                month_count
            ):

                if index >= len(
                    product_volume
                ):
                    continue

                aggregated_product_volume[
                    index
                ] += float(
                    product_volume[
                        index
                    ]
                    or 0
                )

        if not product_found:
            return None

        return [
            round(value, 6)
            for value
            in aggregated_product_volume
        ]

    def get_market_product_share(
        market_node,
        product_name,
    ):
        """
        Return canonical Market -> Product share.

        Preferred source:

            market -> Unknown -> product -> share

        This is important because Market -> Product edits are
        written into the Unknown product node and recompute_tree()
        has already calculated the exact edited share there.

        Example:

            Non-retail -> Biktarvy = 30%

        must be saved as exactly 30%, not recalculated by summing
        overlapping source rows.
        """

        sources = (
            market_node.get(
                "sources",
                {},
            )
            or {}
        )

        # =====================================================
        # Preferred canonical path
        # =====================================================

        unknown_source = sources.get(
            "Unknown"
        )

        if unknown_source is not None:

            product_node = get_product_node(
                source_node=unknown_source,
                product_name=product_name,
            )

            if product_node is not None:

                product_shares = (
                    product_node.get(
                        "share",
                        [],
                    )
                    or []
                )

                if product_shares:
                    return [
                        float(value or 0)
                        for value
                        in product_shares
                    ]

        # =====================================================
        # Fallback: calculate from canonical product volume
        # =====================================================

        market_volume = (
            market_node.get(
                "volume",
                [],
            )
            or []
        )

        product_volume = (
            get_market_product_volume(
                market_node=market_node,
                product_name=product_name,
            )
        )

        if product_volume is None:
            return None

        result = []

        for index, market_value in enumerate(
            market_volume
        ):

            market_value = float(
                market_value or 0
            )

            current_product_volume = (
                float(
                    product_volume[
                        index
                    ]
                    or 0
                )
                if index
                < len(product_volume)
                else 0.0
            )

            if market_value == 0:
                result.append(
                    0.0
                )

            else:
                result.append(
                    round(
                        current_product_volume
                        / market_value
                        * 100.0,
                        6,
                    )
                )

        return result

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
        sources = (
            market_node.get(
                "sources",
                {},
            )
            or {}
        )

        if "Unknown" in sources:

            return sorted(
                (
                    sources[
                        "Unknown"
                    ].get(
                        "products",
                        {},
                    )
                    or {}
                ).keys()
            )

        product_names = set()

        for source_node in sources.values():

            product_names.update(
                (
                    source_node.get(
                        "products",
                        {},
                    )
                    or {}
                ).keys()
            )

        return sorted(
            product_names
        )

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
    

    # # ============================================================
    # # Persist complete recalculated source hierarchy
    # #
    # # IMPORTANT:
    # # Model Input reconstructs Product -> Market from these rows.
    # #
    # # Do not rely only on original_metrics rows because a custom
    # # scenario may be missing source/product rows and the Model
    # # Input code will otherwise fall back to BASE.
    # # ============================================================

    # original_row_lookup = {}

    # for row in original_share_rows:

    #     key = (
    #         normalize_label(
    #             row.get("market")
    #         ),
    #         normalize_label(
    #             row.get("source_of_market")
    #         ),
    #         normalize_label(
    #             row.get("product")
    #         ),
    #     )

    #     original_row_lookup[key] = row


    # def get_original_forecast_data(
    #     market_name,
    #     source_name,
    #     product_name,
    # ):
    #     """
    #     Return existing scenario forecast_data if the row exists.

    #     If it does not exist in the scenario, use a compatible
    #     existing forecast_data structure as the date template.
    #     """

    #     key = (
    #         normalize_label(market_name),
    #         normalize_label(source_name),
    #         normalize_label(product_name),
    #     )

    #     existing = original_row_lookup.get(
    #         key
    #     )

    #     if existing is not None:
    #         return existing.get(
    #             "forecast_data"
    #         )

    #     # --------------------------------------------------------
    #     # Need a date/template structure for a brand-new scenario
    #     # row.
    #     #
    #     # Any market-share row should have the same monthly dates.
    #     # --------------------------------------------------------

    #     if original_share_rows:
    #         return original_share_rows[
    #             0
    #         ].get(
    #             "forecast_data"
    #         )

    #     return None


    # # ============================================================
    # # A. Market totals
    # #
    # # Retail / ALL / ALL
    # # Non-retail / ALL / ALL
    # # ============================================================

    # for market_name, market_node in (
    #     tree.get(
    #         "markets",
    #         {},
    #     ).items()
    # ):

    #     original_forecast_data = (
    #         get_original_forecast_data(
    #             market_name,
    #             "ALL",
    #             "ALL",
    #         )
    #     )

    #     upsert_forecast_output(
    #         cursor,
    #         ta_name=ta_name,
    #         scenario_name=scenario_name,
    #         metric="market_share",
    #         market=market_name,
    #         source_of_market="ALL",
    #         product="ALL",
    #         forecast_data=build_updated_forecast_data(
    #             original_forecast_data=(
    #                 original_forecast_data
    #             ),
    #             full_values=(
    #                 market_node.get(
    #                     "share",
    #                     [],
    #                 )
    #             ),
    #         ),
    #     )

    #     sources = (
    #         market_node.get(
    #             "sources",
    #             {},
    #         )
    #         or {}
    #     )

    #     # ========================================================
    #     # B. Aggregate Market -> Product rows
    #     #
    #     # Retail / ALL / Biktarvy
    #     # Non-retail / ALL / Biktarvy
    #     #
    #     # Prefer Unknown because it is our canonical
    #     # Market -> Product representation.
    #     # ========================================================

    #     unknown_source = (
    #         sources.get(
    #             "Unknown"
    #         )
    #     )

    #     if unknown_source is not None:

    #         for (
    #             product_name,
    #             product_node,
    #         ) in (
    #             unknown_source.get(
    #                 "products",
    #                 {},
    #             )
    #             or {}
    #         ).items():

    #             original_forecast_data = (
    #                 get_original_forecast_data(
    #                     market_name,
    #                     "ALL",
    #                     product_name,
    #                 )
    #             )

    #             upsert_forecast_output(
    #                 cursor,
    #                 ta_name=ta_name,
    #                 scenario_name=scenario_name,
    #                 metric="market_share",
    #                 market=market_name,
    #                 source_of_market="ALL",
    #                 product=product_name,
    #                 forecast_data=build_updated_forecast_data(
    #                     original_forecast_data=(
    #                         original_forecast_data
    #                     ),
    #                     full_values=(
    #                         product_node.get(
    #                             "share",
    #                             [],
    #                         )
    #                     ),
    #                 ),
    #             )

    #     # ========================================================
    #     # C. REAL source rows
    #     #
    #     # Non-retail / ADAP / ALL
    #     # Non-retail / Federal / ALL
    #     # ...
    #     # ========================================================

    #     for source_name, source_node in (
    #         sources.items()
    #     ):

    #         # Unknown is our aggregate representation.
    #         # Do not persist it as a real source unless your DB
    #         # intentionally stores an Unknown source row.
    #         if (
    #             str(source_name)
    #             .strip()
    #             .lower()
    #             == "unknown"
    #         ):
    #             continue

    #         original_forecast_data = (
    #             get_original_forecast_data(
    #                 market_name,
    #                 source_name,
    #                 "ALL",
    #             )
    #         )

    #         upsert_forecast_output(
    #             cursor,
    #             ta_name=ta_name,
    #             scenario_name=scenario_name,
    #             metric="market_share",
    #             market=market_name,
    #             source_of_market=source_name,
    #             product="ALL",
    #             forecast_data=build_updated_forecast_data(
    #                 original_forecast_data=(
    #                     original_forecast_data
    #                 ),
    #                 full_values=(
    #                     source_node.get(
    #                         "share",
    #                         [],
    #                     )
    #                 ),
    #             ),
    #         )

    #         # ====================================================
    #         # D. REAL Source -> Product rows
    #         #
    #         # Non-retail / ADAP / Biktarvy
    #         # Non-retail / Federal / Biktarvy
    #         # Non-retail / IQVIA / Biktarvy
    #         # Non-retail / Kaiser / Biktarvy
    #         # ====================================================

    #         for (
    #             product_name,
    #             product_node,
    #         ) in (
    #             source_node.get(
    #                 "products",
    #                 {},
    #             )
    #             or {}
    #         ).items():

    #             original_forecast_data = (
    #                 get_original_forecast_data(
    #                     market_name,
    #                     source_name,
    #                     product_name,
    #                 )
    #             )

    #             upsert_forecast_output(
    #                 cursor,
    #                 ta_name=ta_name,
    #                 scenario_name=scenario_name,
    #                 metric="market_share",
    #                 market=market_name,
    #                 source_of_market=source_name,
    #                 product=product_name,
    #                 forecast_data=build_updated_forecast_data(
    #                     original_forecast_data=(
    #                         original_forecast_data
    #                     ),
    #                     full_values=(
    #                         product_node.get(
    #                             "share",
    #                             [],
    #                         )
    #                     ),
    #                 ),
    #             )
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

    Both APIs return the same filtered response structure.

    Filtering rules
    ---------------
    Market Event:
        - Tables contain all products / markets.
        - Product-Market charts are filtered using
          selected_filter["products"].

    Product Event:
        - Tables contain all markets / products.
        - Market-Product charts are filtered using
          selected_filter["markets"].

    Date filtering:
        - Entire tree is filtered using start_date/end_date.
    """

    # =====================================================
    # 1. Read selected filters
    # =====================================================

    scenario_name = selected_filter[
        "scenario_name"
    ]

    start_date = selected_filter[
        "start_date"
    ]

    end_date = selected_filter[
        "end_date"
    ]

    selected_markets = selected_filter.get(
        "markets"
    )

    selected_products = selected_filter.get(
        "products"
    )

    # =====================================================
    # 2. Metadata
    # =====================================================

    metadata = load_metadata(
        cursor=cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
        start_date=start_date,
        end_date=end_date,
    )

    # =====================================================
    # 3. Load complete scenario data
    # =====================================================

    metrics = load_forecast_outputs(
        cursor=cursor,
        ta_name=ta_name,
        scenario_name=scenario_name,
    )

    if not metrics.get(
        "market_share"
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "No market-share forecast data "
                "was found."
            ),
        )

    if not metrics.get(
        "market_volume"
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "No market-volume forecast data "
                "was found."
            ),
        )

    # =====================================================
    # 4. Build calculation tree
    # =====================================================

    tree = build_calculation_tree(
        metrics
    )

    # =====================================================
    # 5. Filter tree by selected date range
    # =====================================================

    tree = filter_tree_by_date(
        tree=tree,
        start_date=start_date,
        end_date=end_date,
    )

    # =====================================================
    # 6. Build tabs
    #
    # IMPORTANT:
    #
    # Market Event chart:
    #     filter by selected PRODUCTS
    #
    # Product Event chart:
    #     filter by selected MARKETS
    #
    # Tables remain complete because filtering is handled
    # only inside the chart-specific row builders.
    # =====================================================

    overall_event = (
        build_overall_event(
            tree
        )
    )

    market_event = (
        build_market_event(
            tree=tree,
            selected_products=(
                selected_products
            ),
        )
    )

    product_event = (
        build_product_event(
            tree=tree,
            selected_markets=(
                selected_markets
            ),
        )
    )

    # =====================================================
    # 7. Response
    # =====================================================

    return {
        "ta_name": ta_name,

        "available_scenarios": (
            metadata[
                "available_scenarios"
            ]
        ),

        "available_months": (
            metadata[
                "available_months"
            ]
        ),

        "metric_filters": (
            metadata[
                "metric_filters"
            ]
        ),

        "forecast_start_date": (
            metadata[
                "forecast_start_date"
            ]
        ),

        "selected_filter": (
            selected_filter
        ),

        "event_tabs": {
            "overall_event": (
                overall_event
            ),

            "market_event": (
                market_event
            ),

            "product_event": (
                product_event
            ),
        },
    }


def sync_product_level_to_matrix(
    *,
    tree: dict,
    matrix: dict[str, dict[str, list[float]]],
    selected_indexes: list[int],
):
    """
    Synchronize top-level Product edits into the
    Market x Product matrix.

    Product Level controls:

        Overall -> Product

    Product -> Market distribution is preserved proportionally.

    Example
    -------
    Before:

        Biktarvy total = 100
        Non-retail     = 60
        Retail         = 40

    Product Level changes Biktarvy total to 200.

    After:

        Non-retail = 120
        Retail     = 80

    Existing 60:40 market distribution is preserved.
    """

    markets = list(
        tree.get("markets", {}).keys()
    )

    products = (
        tree.get("products", {})
        or {}
    )

    calculation_precision = 6

    for product_name, product_node in (
        products.items()
    ):

        product_volumes = (
            product_node.get(
                "volume",
                [],
            )
            or []
        )

        for month_index in selected_indexes:

            if month_index >= len(
                product_volumes
            ):
                raise ValueError(
                    "Top-level product-volume length mismatch. "
                    f"Product={product_name!r}, "
                    f"month_index={month_index}."
                )

            new_product_total = round(
                float(
                    product_volumes[
                        month_index
                    ]
                    or 0
                ),
                calculation_precision,
            )

            # =============================================
            # Current Product -> Market volumes
            # =============================================

            current_market_values = []

            for market_name in markets:

                product_values = (
                    matrix
                    .get(
                        market_name,
                        {},
                    )
                    .get(
                        product_name,
                        [],
                    )
                    or []
                )

                current_value = (
                    float(
                        product_values[
                            month_index
                        ]
                        or 0
                    )
                    if month_index
                    < len(product_values)
                    else 0.0
                )

                current_market_values.append(
                    current_value
                )

            current_product_total = round(
                sum(
                    current_market_values
                ),
                calculation_precision,
            )

            # =============================================
            # New product total is zero
            # =============================================

            if new_product_total == 0:

                for market_name in markets:

                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ] = 0.0

                continue

            # =============================================
            # Preserve existing market distribution
            # =============================================

            if current_product_total > 0:

                allocated_total = 0.0

                for position, market_name in (
                    enumerate(markets)
                ):

                    is_last = (
                        position
                        == len(markets) - 1
                    )

                    if is_last:

                        allocated_value = round(
                            new_product_total
                            - allocated_total,
                            calculation_precision,
                        )

                    else:

                        ratio = (
                            current_market_values[
                                position
                            ]
                            / current_product_total
                        )

                        allocated_value = round(
                            new_product_total
                            * ratio,
                            calculation_precision,
                        )

                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ] = allocated_value

                    allocated_total = round(
                        allocated_total
                        + allocated_value,
                        calculation_precision,
                    )

            # =============================================
            # Defensive fallback
            # =============================================

            else:

                market_count = len(
                    markets
                )

                if market_count == 0:
                    continue

                allocated_total = 0.0

                for position, market_name in (
                    enumerate(markets)
                ):

                    if (
                        position
                        == market_count - 1
                    ):

                        allocated_value = round(
                            new_product_total
                            - allocated_total,
                            calculation_precision,
                        )

                    else:

                        allocated_value = round(
                            new_product_total
                            / market_count,
                            calculation_precision,
                        )

                    matrix[
                        market_name
                    ][
                        product_name
                    ][
                        month_index
                    ] = allocated_value

                    allocated_total = round(
                        allocated_total
                        + allocated_value,
                        calculation_precision,
                    )

    return matrix

