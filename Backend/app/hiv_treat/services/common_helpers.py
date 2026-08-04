def filter_tree_by_date(
    tree: dict,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Trim the complete calculation tree to the selected date range.

    This must slice:
        - overall volume
        - market share and volume
        - source share and volume
        - product share and volume
        - top-level aggregated products
    """

    months = tree.get("months", [])

    if not months:
        return tree

    selected_indexes = [
        index
        for index, month in enumerate(months)
        if start_date <= month <= end_date
    ]

    if not selected_indexes:
        tree["months"] = []
        tree["forecast_start_index"] = 0

        filter_node_by_date(
            node=tree,
            start_index=0,
            end_index=0,
        )

        return tree

    start_index = selected_indexes[0]
    end_index = selected_indexes[-1] + 1

    original_forecast_start_index = tree.get(
        "forecast_start_index",
        0,
    )

    # Slice all arrays before replacing the month list.
    filter_node_by_date(
        node=tree,
        start_index=start_index,
        end_index=end_index,
    )

    tree["months"] = months[
        start_index:end_index
    ]

    new_month_count = len(tree["months"])

    adjusted_forecast_index = (
        original_forecast_start_index
        - start_index
    )

    # Cases:
    # adjusted <= 0            -> all selected data is forecast
    # adjusted >= month count  -> all selected data is history
    tree["forecast_start_index"] = max(
        0,
        min(
            adjusted_forecast_index,
            new_month_count,
        ),
    )

    return tree

def filter_node_by_date(
    node,
    start_index: int,
    end_index: int,
):
    if not isinstance(node, dict):
        return

    time_series_keys = {
        "values",
        "history",
        "forecast",
        "share",
        "volume",
    }

    for key, value in node.items():

        if (
            key in time_series_keys
            and isinstance(value, list)
        ):
            node[key] = value[
                start_index:end_index
            ]

        elif isinstance(value, dict):
            filter_node_by_date(
                node=value,
                start_index=start_index,
                end_index=end_index,
            )