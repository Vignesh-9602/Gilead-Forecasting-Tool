from pprint import pprint

def populate_product_market_inputs(
    tree: dict,
    metrics: dict,
):
    """
    Preserve the original Product -> Market input shares.

    Database rows:

        ALL        | ALL | Biktarvy
            Product share of overall market.

        Retail     | ALL | Biktarvy
        Non-retail | ALL | Biktarvy
            Channel distribution within Biktarvy.
    """

    month_count = len(
        tree.get("months", [])
    )

    tree["product_market_inputs"] = {}

    rows = (
        metrics.get("market_share", [])
        or []
    )

    for row in rows:
        market = normalize_dimension(
            row.get("market")
        )
        source = normalize_dimension(
            row.get("source_of_market")
        )
        product = normalize_dimension(
            row.get("product")
        )

        if is_all(product):
            continue

        # Product-Channel input rows must have source = ALL.
        if not is_all(source):
            continue

        forecast = (
            row.get("forecast_data", {})
            or {}
        )

        values = (
            list(
                forecast.get(
                    "train_values",
                    [],
                )
                or []
            )
            + list(
                forecast.get(
                    "forecast_values",
                    [],
                )
                or []
            )
        )

        if len(values) != month_count:
            raise ValueError(
                "Product-market input length mismatch for "
                f"{market!r}|{product!r}. "
                f"Expected {month_count}, "
                f"received {len(values)}."
            )

        product_node = (
            tree["product_market_inputs"]
            .setdefault(
                product,
                {
                    "overall_share": [],
                    "markets": {},
                },
            )
        )

        if is_all(market):
            # ALL | ALL | Product
            product_node["overall_share"] = [
                float(value or 0)
                for value in values
            ]

        else:
            # Market | ALL | Product
            product_node["markets"][market] = [
                float(value or 0)
                for value in values
            ]

def build_calculation_tree(metrics):

    tree = {
        "months": [],
        "forecast_start_index": 0,
        "overall": {
            "volume": [],
        },
        "markets": {},
        "products": {},
        "product_market_inputs": {},
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

    # Preserve canonical Product-Channel input values.
    populate_product_market_inputs(
        tree,
        metrics,
    )

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

def normalize_dimension(value):
    if value is None:
        return "ALL"

    normalized = str(value).strip()

    if not normalized:
        return "ALL"

    return normalized


def is_all(value):
    return normalize_dimension(value).upper() == "ALL"

def populate_market_shares(tree, metrics):
    """
    Populate market-level shares.

    Market-level row:
        market != ALL
        source_of_market == ALL / None
        product == ALL
    """

    rows = metrics.get("market_share", [])

    for row in rows:
        market = normalize_dimension(
            row.get("market")
        )

        source = normalize_dimension(
            row.get("source_of_market")
        )

        product = normalize_dimension(
            row.get("product")
        )

        is_market_level = (
            not is_all(market)
            and is_all(source)
            and is_all(product)
        )

        if not is_market_level:
            continue

        forecast = row.get(
            "forecast_data",
            {}
        )

        values = (
            forecast.get("train_values", [])
            + forecast.get("forecast_values", [])
        )

        tree["markets"][market] = {
            "share": values,
            "volume": [],
            "sources": {},
        }

def populate_market_volumes(tree):
    """
    Market Volume = Overall Volume × Market Share / 100
    """

    overall_volume = (
        tree.get("overall", {})
        .get("volume", [])
    )

    if not overall_volume:
        return

    for market in tree.get(
        "markets",
        {}
    ).values():
        market_share = market.get(
            "share",
            []
        )

        market["volume"] = [
            round(
                overall * share / 100,
                2,
            )
            for overall, share in zip(
                overall_volume,
                market_share,
            )
        ]

def populate_source_shares(tree, metrics):
    """
    Populate sources under each market.

    Source-level row:
        market != ALL
        source_of_market != ALL
        product == ALL

    Product rows can also cause a missing source container
    to be created with a default 100% share.
    """

    month_count = len(tree["months"])

    rows = metrics.get("market_share", [])

    # First create sources from source-level rows.
    for row in rows:
        market = normalize_dimension(
            row.get("market")
        )

        source = normalize_dimension(
            row.get("source_of_market")
        )

        product = normalize_dimension(
            row.get("product")
        )

        if is_all(market):
            continue

        if market not in tree["markets"]:
            continue

        is_source_level = (
            not is_all(source)
            and is_all(product)
        )

        if not is_source_level:
            continue

        forecast = row.get(
            "forecast_data",
            {}
        )

        values = (
            forecast.get("train_values", [])
            + forecast.get("forecast_values", [])
        )

        tree["markets"][market][
            "sources"
        ][source] = {
            "share": values,
            "volume": [],
            "products": {},
        }

    # Then make sure product-only sources also exist.
    for row in rows:
        market = normalize_dimension(
            row.get("market")
        )

        source = normalize_dimension(
            row.get("source_of_market")
        )

        product = normalize_dimension(
            row.get("product")
        )

        if is_all(market) or is_all(product):
            continue

        if market not in tree["markets"]:
            continue

        # A product may be stored without an explicit source.
        if is_all(source):
            source = "Unknown"

        sources = tree["markets"][market][
            "sources"
        ]

        if source not in sources:
            sources[source] = {
                "share": [100.0] * month_count,
                "volume": [],
                "products": {},
            }

def populate_source_volumes(tree):
    """
    Source Volume = Market Volume × Source Share / 100
    """

    for market in tree.get(
        "markets",
        {}
    ).values():
        market_volume = market.get(
            "volume",
            []
        )

        for source in market.get(
            "sources",
            {}
        ).values():
            source_share = source.get(
                "share",
                []
            )

            source["volume"] = [
                round(
                    market_total
                    * share
                    / 100,
                    2,
                )
                for market_total, share in zip(
                    market_volume,
                    source_share,
                )
            ]

def populate_product_shares(tree, metrics):
    """
    Populate product shares under each source.

    Product-level row:
        market != ALL
        product != ALL
    """

    rows = metrics.get("market_share", [])

    for row in rows:
        market = normalize_dimension(
            row.get("market")
        )

        source = normalize_dimension(
            row.get("source_of_market")
        )

        product = normalize_dimension(
            row.get("product")
        )

        if is_all(market) or is_all(product):
            continue

        if is_all(source):
            source = "Unknown"

        if market not in tree["markets"]:
            continue

        sources = tree["markets"][market][
            "sources"
        ]

        if source not in sources:
            continue

        forecast = row.get(
            "forecast_data",
            {}
        )

        values = (
            forecast.get("train_values", [])
            + forecast.get("forecast_values", [])
        )

        product_node = {
            "share": values,
            "volume": [],
        }

        sources[source][
            "products"
        ][product] = product_node

        # Store a reference at the top level as well

def populate_product_volumes(tree):
    """
    Product Volume = Source Volume × Product Share / 100
    """

    for market in tree.get(
        "markets",
        {}
    ).values():
        for source in market.get(
            "sources",
            {}
        ).values():
            source_volume = source.get(
                "volume",
                []
            )

            for product in source.get(
                "products",
                {}
            ).values():
                product_share = product.get(
                    "share",
                    []
                )

                product["volume"] = [
                    round(
                        source_total
                        * share
                        / 100,
                        2,
                    )
                    for source_total, share in zip(
                        source_volume,
                        product_share,
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