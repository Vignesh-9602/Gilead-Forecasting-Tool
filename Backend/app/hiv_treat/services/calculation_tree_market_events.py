from pprint import pprint

def build_calculation_tree(metrics):

    tree = {
        "months": [],
        "forecast_start_index": 0,
        "overall": {
            "volume": []
        },
        "markets": {},
        "products": {},
    }

    populate_metadata(tree, metrics)

    populate_overall_volume(tree, metrics)

    populate_market_shares(tree, metrics)

    populate_market_volumes(tree)

    populate_source_shares(tree, metrics)

    populate_source_volumes(tree)

    populate_product_shares(tree, metrics)

    populate_product_volumes(tree)

    aggregate_products(tree)

    return tree

def populate_metadata(tree, metrics):
    """
    Populate:
        - months
        - forecast_start_index

    Uses the first available forecast_data.
    """

    for metric_rows in metrics.values():

        if not metric_rows:
            continue

        forecast = metric_rows[0]["forecast_data"]

        tree["months"] = forecast["months"]
        tree["forecast_start_index"] = forecast["forecast_start_index"]
        # print(["forecast_start_index"].value)

        return
    
def populate_overall_volume(tree, metrics):
    """
    Populate the overall market volume.

    Uses the single row from market_volume.
    """

    rows = metrics.get("market_volume", [])

    if not rows:
        return

    forecast = rows[0]["forecast_data"]

    tree["overall"]["volume"] = (
        forecast["train_values"]
        + forecast["forecast_values"]
    )

def populate_market_shares(tree, metrics):
    """
    Populate market shares.

    Market-level rows are identified by:
        product == "ALL"
        source_of_market is None
    """

    for row in metrics["market_share"]:

        # Only market-level rows
        if row["product"] != "ALL":
            continue

        if row["source_of_market"] is not None:
            continue

        market = row["market"]

        if market == "ALL":
            continue

        forecast = row["forecast_data"]

        values = (
            forecast["train_values"] +
            forecast["forecast_values"]
        )

        tree["markets"][market] = {
            "share": values,
            "volume": [],
            "sources": {}
        }

def populate_market_volumes(tree):
    """
    Calculate the market volumes from the market shares.

    Formula:
        Market Volume = Overall Volume × Market Share / 100
    """

    overall_volume = tree["overall"]["volume"]

    if not overall_volume:
        return

    for market in tree["markets"].values():

        market["volume"] = [

            round(
                overall * share / 100,
                2,
            )

            for overall, share in zip(
                overall_volume,
                market["share"],
            )
        ]

def populate_source_shares(tree, metrics):
    """
    Populate sources under each market.

    Source-level ALL rows provide source shares.

    When a source exists only on product rows, such as
    Retail / Unknown / Biktarvy, create the source with
    a default share of 100%.
    """

    month_count = len(tree["months"])

    for row in metrics.get("market_share", []):
        market = row["market"]
        raw_source = row["source_of_market"]
        product = row["product"]

        if market == "ALL":
            continue

        if market not in tree["markets"]:
            continue

        # Market-level row: Retail / None / ALL
        if raw_source is None:
            continue

        source = raw_source or "Unknown"

        sources = tree["markets"][market]["sources"]

        if source not in sources:
            sources[source] = {
                "share": [100.0] * month_count,
                "volume": [],
                "products": {},
            }

        # An ALL product row contains the actual source share
        if product == "ALL":
            forecast = row["forecast_data"]

            sources[source]["share"] = (
                forecast["train_values"]
                + forecast["forecast_values"]
            )

def populate_source_volumes(tree):
    """
    Source Volume = Market Volume × Source Share / 100
    """

    for market in tree["markets"].values():

        market_volume = market["volume"]

        for source in market["sources"].values():

            source["volume"] = [
                round(market_total * source_share / 100, 2)
                for market_total, source_share in zip(
                    market_volume,
                    source["share"],
                )
            ]

def populate_product_shares(tree, metrics):
    """
    Populate product shares under each source.
    """

    for row in metrics.get("market_share", []):

        if row["product"] == "ALL":
            continue

        market = row["market"]
        source = row["source_of_market"] or "Unknown"
        product = row["product"]

        if market not in tree["markets"]:
            continue

        if source not in tree["markets"][market]["sources"]:
            continue

        forecast = row["forecast_data"]

        values = (
            forecast["train_values"]
            + forecast["forecast_values"]
        )

        tree["markets"][market]["sources"][source]["products"][product] = {
            "share": values,
            "volume": [],
        }

        # Store a reference at the top level as well

def populate_product_volumes(tree):
    """
    Product Volume = Source Volume × Product Share / 100
    """

    for market in tree["markets"].values():

        for source in market["sources"].values():

            source_volume = source["volume"]

            for product in source["products"].values():

                product["volume"] = [
                    round(source_total * product_share / 100, 2)
                    for source_total, product_share in zip(
                        source_volume,
                        product["share"],
                    )
                ]

def aggregate_products(tree):
    """
    Sum product volumes across markets and sources,
    then derive each product's overall market share.
    """

    month_count = len(tree["months"])

    tree["products"] = {}

    for market in tree["markets"].values():

        for source in market["sources"].values():

            for product_name, product in source["products"].items():

                if product_name not in tree["products"]:
                    tree["products"][product_name] = {
                        "share": [0.0] * month_count,
                        "volume": [0.0] * month_count,
                    }

                tree["products"][product_name]["volume"] = [
                    round(current + value, 2)
                    for current, value in zip(
                        tree["products"][product_name]["volume"],
                        product["volume"],
                    )
                ]

    overall_volume = tree["overall"]["volume"]

    for product in tree["products"].values():

        product["share"] = [
            round(product_volume / total_volume * 100, 2)
            if total_volume
            else 0.0
            for product_volume, total_volume in zip(
                product["volume"],
                overall_volume,
            )
        ]

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