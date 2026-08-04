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

def normalize_market_volumes_to_overall(
    tree: dict,
    precision: int = 6,
):
    """
    Normalize market volumes so that, for every month:

        sum(markets) == overall

    Existing market proportions are preserved.

    Overall volume is treated as authoritative.
    """

    overall_volumes = (
        tree.get("overall", {}).get("volume", [])
        or []
    )

    markets = (
        tree.get("markets", {})
        or {}
    )

    market_names = list(markets.keys())

    if not market_names:
        return tree

    month_count = len(overall_volumes)

    for month_index in range(month_count):

        overall_volume = round(
            float(
                overall_volumes[month_index]
                or 0
            ),
            precision,
        )

        current_market_values = []

        for market_name in market_names:

            values = (
                markets[
                    market_name
                ].get("volume", [])
                or []
            )

            current_value = (
                float(
                    values[month_index]
                    or 0
                )
                if month_index < len(values)
                else 0.0
            )

            current_market_values.append(
                max(0.0, current_value)
            )

        current_total = round(
            sum(current_market_values),
            precision,
        )

        # ---------------------------------------------
        # Overall is zero
        # ---------------------------------------------

        if overall_volume == 0:

            normalized_values = [
                0.0
                for _ in market_names
            ]

        # ---------------------------------------------
        # Preserve existing market proportions
        # ---------------------------------------------

        elif current_total > 0:

            scale_factor = (
                overall_volume
                / current_total
            )

            normalized_values = [
                round(
                    value * scale_factor,
                    precision,
                )
                for value in current_market_values
            ]

        else:

            raise ValueError(
                "Cannot normalize market volumes because "
                "Overall is positive but market total is zero. "
                f"Month={month_index}, "
                f"Overall={overall_volume:.6f}."
            )

        # ---------------------------------------------
        # Fix rounding residual
        # ---------------------------------------------

        normalized_total = round(
            sum(normalized_values),
            precision,
        )

        residual = round(
            overall_volume
            - normalized_total,
            precision,
        )

        if normalized_values:

            correction_position = max(
                range(len(normalized_values)),
                key=lambda i: normalized_values[i],
            )

            normalized_values[
                correction_position
            ] = round(
                normalized_values[
                    correction_position
                ]
                + residual,
                precision,
            )

        # ---------------------------------------------
        # Write back market volumes + shares
        # ---------------------------------------------

        for position, market_name in enumerate(
            market_names
        ):

            normalized_volume = (
                normalized_values[position]
            )

            markets[
                market_name
            ]["volume"][
                month_index
            ] = normalized_volume

            markets[
                market_name
            ]["share"][
                month_index
            ] = (
                round(
                    normalized_volume
                    / overall_volume
                    * 100.0,
                    precision,
                )
                if overall_volume
                else 0.0
            )

    return tree

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

    normalize_market_volumes_to_overall(tree)

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


def calculate_percentage(
    numerator: float,
    denominator: float,
    decimals: int = 6,
) -> float:
    """
    Safely calculate percentage.

    Returns:
        numerator / denominator * 100

    If denominator is 0, returns 0.
    """

    if denominator == 0:
        return 0.0

    return round(
        (float(numerator) / float(denominator)) * 100.0,
        decimals,
    )

from app.hiv_treat.services.edit_helpers import get_canonical_sources

def aggregate_products(
    tree: dict,
):
    """
    Aggregate product volumes across markets and calculate
    overall Product share.

    If Unknown exists under a market, only Unknown is used
    for market-level product aggregation.
    """

    month_count = len(
        tree.get("months", [])
    )

    tree["products"] = {}

    for market_name, market in (
        tree.get("markets", {}).items()
    ):

        sources_to_use = get_canonical_sources(
            market
        )

        for source_name, source in (
            sources_to_use.items()
        ):

            source_products = (
                source.get("products", {})
                or {}
            )

            for (
                product_name,
                product,
            ) in source_products.items():

                if product_name not in tree[
                    "products"
                ]:
                    tree[
                        "products"
                    ][
                        product_name
                    ] = {
                        "share": (
                            [0.0] * month_count
                        ),
                        "volume": (
                            [0.0] * month_count
                        ),
                    }

                product_volumes = (
                    product.get("volume", [])
                    or []
                )

                for month_index in range(
                    month_count
                ):

                    if month_index >= len(
                        product_volumes
                    ):
                        continue

                    current = float(
                        tree[
                            "products"
                        ][
                            product_name
                        ][
                            "volume"
                        ][
                            month_index
                        ]
                        or 0
                    )

                    incoming = float(
                        product_volumes[
                            month_index
                        ]
                        or 0
                    )

                    tree[
                        "products"
                    ][
                        product_name
                    ][
                        "volume"
                    ][
                        month_index
                    ] = round(
                        current + incoming,
                        6,
                    )

    overall_volumes = (
        tree.get("overall", {}).get(
            "volume",
            [],
        )
        or []
    )

    for product_name, product in (
        tree["products"].items()
    ):

        for month_index in range(
            month_count
        ):

            product_volume = float(
                product["volume"][
                    month_index
                ]
                or 0
            )

            overall_volume = (
                float(
                    overall_volumes[
                        month_index
                    ]
                    or 0
                )
                if month_index
                < len(overall_volumes)
                else 0.0
            )

            product["share"][
                month_index
            ] = calculate_percentage(
                numerator=product_volume,
                denominator=overall_volume,
            )

