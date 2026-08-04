from app.hiv_prep.services.response_builder_market_events import *
from app.hiv_prep.services.calculation_tree_market_events import normalize_dimension,is_all

from copy import deepcopy

def round_table_values(table, decimals=0):
    def round_rows(rows):
        for row in rows:
            if "values" in row:
                row["values"] = [
                    round(v, decimals) if isinstance(v, (int, float)) else v
                    for v in row["values"]
                ]

            if "children" in row:
                round_rows(row["children"])

    round_rows(table["rows"])
    return table

def exclude_overall_from_chart(table):
    """
    Return a copy of the table without total rows.

    The original table is not modified, so Overall remains
    visible in the UI table.
    """

    chart_table = deepcopy(table)

    excluded_labels = {
        "overall",
        "grand total",
        "total",
    }

    chart_table["rows"] = [
        row
        for row in chart_table.get("rows", [])
        if str(
            row.get("label", "")
        ).strip().lower() not in excluded_labels
    ]

    return chart_table

def build_overall_event(
    tree,
    saved_events=None,
):
    """
    Build Overall Event from the calculation tree.

    Provides one view:
        overall_level

    Saved overall events are returned inside:
        impact_curve_configuration.rows
    """

    months = tree["months"]
    forecast_start_index = tree[
        "forecast_start_index"
    ]

    overall_volume = tree["overall"]["volume"]
    overall_share = [
        100.0
    ] * len(months)

    view_options = [
        {
            "label": "Overall",
            "value": "overall_level",
        }
    ]

    # =====================================================
    # Monthly tables
    # =====================================================

    market_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=[
            {
                "label": "Overall",
                "values": overall_share,
            }
        ],
        hierarchy=False,
    )

    market_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=[
            {
                "label": "Overall",
                "values": overall_volume,
            }
        ],
        hierarchy=False,
    )

    market_share_monthly["type"] = "flat"
    market_share_monthly["editable"] = False

    market_volume_monthly["type"] = "flat"
    market_volume_monthly["editable"] = False

    # =====================================================
    # Yearly tables
    # =====================================================

    market_share_yearly = build_yearly_table(
        market_share_monthly,
        aggregation="average",
    )

    market_volume_yearly = build_yearly_table(
        market_volume_monthly,
        aggregation="sum",
    )

    market_share_yearly["type"] = "flat"
    market_share_yearly["editable"] = False

    market_volume_yearly["type"] = "flat"
    market_volume_yearly["editable"] = False

    # =====================================================
    # Response
    # =====================================================

    return {
        "impact_curve_configuration": (
            build_overall_impact_curve_configuration(
                tree=tree,
                saved_events=saved_events,
            )
        ),

        "metrics_views": {
            "market_share": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": "overall_level",

                    "overall_level": {
                        "chart": build_monthly_chart(
                            market_share_monthly
                        ),
                        "table": market_share_monthly,
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": "overall_level",

                    "overall_level": {
                        "chart": build_yearly_chart(
                            market_share_yearly
                        ),
                        "table": market_share_yearly,
                    },
                },
            },

            "market_volume": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": "overall_level",

                    "overall_level": {
                        "chart": build_monthly_chart(
                            market_volume_monthly
                        ),
                        "table": market_volume_monthly,
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": "overall_level",

                    "overall_level": {
                        "chart": build_yearly_chart(
                            market_volume_yearly
                        ),
                        "table": market_volume_yearly,
                    },
                },
            },
        },
    }

def build_product_rows(tree, metric):
    """
    Build Product Event hierarchy.

    Overall
        ├── Retail
        │      ├── Biktarvy
        │      ├── Descovy
        │      └── Truvada
        └── Non-retail
               ├── Biktarvy
               ├── Descovy
               └── Truvada

    For share:
        Market row = market share of overall market.
        Product child = product contribution to overall market
                        within that market.

    For volume:
        Market row = market volume.
        Product child = product volume within that market.
    """

    month_count = len(tree["months"])
    overall_volume = tree["overall"]["volume"]

    overall_values = (
        [100.0] * month_count
        if metric == "share"
        else overall_volume
    )

    rows = [
        {
            "label": "Overall",
            "values": overall_values,
        }
    ]

    for market_name, market in tree["markets"].items():

        market_row = {
            "label": market_name,
            "values": market[metric],
            "children": [],
        }

        for product_name in tree["products"]:

            # Sum this product's volume across all sources
            # belonging to the current market.
            product_market_volume = [0.0] * month_count

            for source in market["sources"].values():

                product_node = source["products"].get(product_name)

                if not product_node:
                    continue

                product_market_volume = [
                    round(current + value, 2)
                    for current, value in zip(
                        product_market_volume,
                        product_node["volume"],
                    )
                ]

            if metric == "volume":
                child_values = product_market_volume

            else:
                # Product's contribution to the overall market
                # from this particular market.
                child_values = [
                    round(product_volume / total_volume * 100, 2)
                    if total_volume
                    else 0.0
                    for product_volume, total_volume in zip(
                        product_market_volume,
                        overall_volume,
                    )
                ]

            market_row["children"].append(
                {
                    "label": product_name,
                    "values": child_values,
                }
            )

        rows.append(market_row)

    return rows

def build_market_product_chart(
    table,
    period_key,
):
    """
    Convert hierarchy:

        Market
            Product

    into chart labels:

        Market - Product
    """

    headers = list(
        table.get("headers") or []
    )

    if (
        headers
        and str(headers[0]).strip().lower()
        == "metric"
    ):
        headers = headers[1:]

    forecast_start_index = table.get(
        "forecast_start_index",
        len(headers),
    )

    series = []

    for market_row in table.get("rows", []):
        if not isinstance(market_row, dict):
            continue

        market_name = str(
            market_row.get("label", "")
        ).strip()

        if market_name.lower() in {
            "overall",
            "total",
            "all",
            "grand total",
        }:
            continue

        for product_row in (
            market_row.get("children") or []
        ):
            if not isinstance(product_row, dict):
                continue

            product_name = str(
                product_row.get("label", "")
            ).strip()

            if not product_name:
                continue

            values = list(
                product_row.get("values") or []
            )

            series.append(
                {
                    "label": (
                        f"{market_name} - "
                        f"{product_name}"
                    ),
                    "history": values[
                        :forecast_start_index
                    ],
                    "forecast": values[
                        forecast_start_index:
                    ],
                }
            )

    return {
        period_key: headers,
        "forecast_start_index":
            forecast_start_index,
        "series": series,
    }


def build_product_chart_rows(
    tree,
    metric,
    selected_markets=None,
):
    """
    Build rows for the Market-Product chart.

    Includes:
        - only selected markets
        - all products under those markets
    """

    months_count = len(tree["months"])
    overall_volume = tree["overall"]["volume"]

    selected_market_set = {
        str(market).strip().lower()
        for market in (selected_markets or [])
        if market
    }

    rows = []

    for market_name in sorted(tree["markets"]):
        normalized_market_name = (
            str(market_name)
            .strip()
            .lower()
        )

        if (
            selected_market_set
            and normalized_market_name
            not in selected_market_set
        ):
            continue

        market = tree["markets"][market_name]

        market_row = {
            "label": market_name,
            "values": [0.0] * months_count,
            "children": [],
        }

        for product_name in sorted(tree["products"]):
            market_product_volume = [
                0.0
            ] * months_count

            for source in market.get(
                "sources",
                {},
            ).values():
                product_node = (
                    source
                    .get("products", {})
                    .get(product_name)
                )

                if not product_node:
                    continue

                product_values = (
                    product_node.get("volume", [])
                )

                market_product_volume = [
                    round(current + value, 2)
                    for current, value in zip(
                        market_product_volume,
                        product_values,
                    )
                ]

            if metric == "volume":
                child_values = (
                    market_product_volume
                )
            else:
                child_values = [
                    round(
                        product_volume
                        / total_volume
                        * 100,
                        2,
                    )
                    if total_volume
                    else 0.0
                    for (
                        product_volume,
                        total_volume,
                    ) in zip(
                        market_product_volume,
                        overall_volume,
                    )
                ]

            market_row["children"].append(
                {
                    "label": product_name,
                    "values": child_values,
                }
            )

            market_row["values"] = [
                round(current + value, 2)
                for current, value in zip(
                    market_row["values"],
                    child_values,
                )
            ]

        if market_row["children"]:
            rows.append(market_row)

    return rows

def build_market_product_rows(
    tree: dict,
    metric: str = "share",
    decimals: int = 2,
) -> list:
    """
    Build Channel -> Product hierarchy matching the Model Input
    market_product table.

    Output:

        Overall

        Retail
            Biktarvy
            Truvada
            Descovy

        Non-retail
            Biktarvy
            Truvada
            Descovy

    Rules
    -----
    metric="share":
        Market parent = 100%.

        Product child share =
            product volume within market
            / total product volume within market
            * 100

    metric="volume":
        Product child = product volume within market.

        Market parent =
            sum of all product child volumes within that market.

    The function uses product volumes, not product shares, because
    the shares stored under the current calculation tree may represent
    contribution to the overall market rather than distribution within
    a channel.
    """

    if metric not in {"share", "volume"}:
        raise ValueError(
            "metric must be either 'share' or 'volume'. "
            f"Received {metric!r}."
        )

    months = list(
        tree.get("months", [])
        or []
    )
    month_count = len(months)

    markets = (
        tree.get("markets", {})
        or {}
    )

    top_level_products = (
        tree.get("products", {})
        or {}
    )

    # Preserve product order from tree["products"].
    product_order = list(
        top_level_products.keys()
    )

    # market_product_volumes[market][product] = monthly volumes
    market_product_volumes = {}

    # =====================================================
    # Build canonical Market x Product volume matrix
    # =====================================================

    for market_name, market_node in markets.items():
        sources = (
            market_node.get("sources", {})
            or {}
        )

        market_product_volumes.setdefault(
            market_name,
            {},
        )

        # -------------------------------------------------
        # Prefer direct Product-Channel rows under Unknown
        #
        # Example database row:
        #     Retail | ALL | Biktarvy
        #
        # Current calculation tree stores this as:
        #     Retail -> Unknown -> Biktarvy
        # -------------------------------------------------

        unknown_source = sources.get("Unknown")

        if unknown_source is not None:
            direct_products = (
                unknown_source.get("products", {})
                or {}
            )

            for product_name, product_node in (
                direct_products.items()
            ):
                volumes = list(
                    product_node.get("volume", [])
                    or []
                )

                if len(volumes) != month_count:
                    raise ValueError(
                        "Product-volume length mismatch for "
                        f"{market_name!r}|"
                        f"{product_name!r}. "
                        f"Expected {month_count}, "
                        f"received {len(volumes)}."
                    )

                market_product_volumes[
                    market_name
                ][product_name] = [
                    float(value or 0)
                    for value in volumes
                ]

                if product_name not in product_order:
                    product_order.append(product_name)

            # The Unknown source contains the direct
            # Market -> Product rows, so do not add the same
            # values again from other source nodes.
            if direct_products:
                continue

        # -------------------------------------------------
        # Fallback: aggregate products across real sources
        # -------------------------------------------------

        for source_name, source_node in sources.items():
            products = (
                source_node.get("products", {})
                or {}
            )

            for product_name, product_node in products.items():
                volumes = list(
                    product_node.get("volume", [])
                    or []
                )

                if len(volumes) != month_count:
                    raise ValueError(
                        "Product-volume length mismatch for "
                        f"{market_name!r}|"
                        f"{source_name!r}|"
                        f"{product_name!r}. "
                        f"Expected {month_count}, "
                        f"received {len(volumes)}."
                    )

                product_values = (
                    market_product_volumes[
                        market_name
                    ].setdefault(
                        product_name,
                        [0.0] * month_count,
                    )
                )

                for month_index, value in enumerate(volumes):
                    product_values[month_index] += float(
                        value or 0
                    )

                if product_name not in product_order:
                    product_order.append(product_name)

    # =====================================================
    # Build hierarchy rows
    # =====================================================

    rows = []

    overall_volume = list(
        tree.get("overall", {}).get(
            "volume",
            [],
        )
        or []
    )

    if metric == "share":
        overall_values = [
            100.0
        ] * month_count
    else:
        if len(overall_volume) != month_count:
            raise ValueError(
                "Overall-volume length mismatch. "
                f"Expected {month_count}, "
                f"received {len(overall_volume)}."
            )

        overall_values = [
            round(
                float(value or 0),
                decimals,
            )
            for value in overall_volume
        ]

    rows.append({
        "label": "Overall",
        "editable": False,
        "values": overall_values,
        "children": [],
    })

    # =====================================================
    # Market parents with product children
    # =====================================================

    for market_name in markets.keys():
        products_for_market = (
            market_product_volumes.get(
                market_name,
                {},
            )
        )

        if not products_for_market:
            continue

        # Total product volume within this channel.
        market_product_totals = [
            0.0
        ] * month_count

        for product_volumes in (
            products_for_market.values()
        ):
            for month_index, value in enumerate(
                product_volumes
            ):
                market_product_totals[
                    month_index
                ] += float(value or 0)

        children = []

        for product_name in product_order:
            product_volumes = (
                products_for_market.get(
                    product_name
                )
            )

            if product_volumes is None:
                continue

            if metric == "volume":
                child_values = [
                    round(
                        float(value or 0),
                        decimals,
                    )
                    for value in product_volumes
                ]

            else:
                child_values = [
                    round(
                        (
                            float(product_volume or 0)
                            / float(market_total or 0)
                            * 100
                        )
                        if float(market_total or 0) != 0
                        else 0.0,
                        decimals,
                    )
                    for product_volume, market_total in zip(
                        product_volumes,
                        market_product_totals,
                    )
                ]

            children.append({
                "label": product_name,
                "parent": market_name,
                "editable": True,
                "values": child_values,
                "children": [],
            })

        if metric == "share":
            parent_values = [
                100.0
            ] * month_count
        else:
            parent_values = [
                round(
                    float(value or 0),
                    decimals,
                )
                for value in market_product_totals
            ]

        rows.append({
            "label": market_name,
            "editable": False,
            "values": parent_values,
            "children": children,
        })

    return rows

from copy import deepcopy


def filter_market_product_rows_for_chart(
    *,
    rows: list,
    selected_markets=None,
) -> list:
    """
    Filter Channel -> Product hierarchy rows for chart use.

    The chart uses the exact same values as the table.

    Input
    -----
    Overall

    Non-retail
        Biktarvy
        Descovy
        Truvada

    Retail
        Biktarvy
        Descovy
        Truvada

    Output
    ------
    Only selected market parents and all product children.

    If no markets are selected, all markets are returned.
    """

    selected_market_set = {
        str(market).strip().lower()
        for market in (selected_markets or [])
        if (
            market
            and str(market).strip().lower() != "all"
        )
    }

    filtered_rows = []

    for row in rows or []:

        market_name = str(
            row.get("label", "")
        ).strip()

        # Overall is not needed in the Channel-Product chart.
        if market_name.lower() == "overall":
            continue

        if (
            selected_market_set
            and market_name.lower()
            not in selected_market_set
        ):
            continue

        filtered_row = deepcopy(row)

        filtered_row["editable"] = False

        for child in (
            filtered_row.get("children", [])
            or []
        ):
            child["editable"] = False
            child["parent"] = market_name

        filtered_rows.append(
            filtered_row
        )

    return filtered_rows

def build_product_event(
    tree,
    selected_markets=None,
    saved_events=None,
):
    """
    Build Product Event.

    Product-level view:
        Overall
        Biktarvy
        Descovy
        Truvada

    Market-product table:
        Overall
        Market
            Product

    Market-product chart:
        Includes only selected markets.
        Includes every product under those markets.

    Supports:
        selected_markets="Retail"
        selected_markets=["Retail"]
    """

    # =====================================================
    # Normalize selected markets
    # =====================================================

    if selected_markets is None:
        normalized_selected_markets = []

    elif isinstance(selected_markets, str):
        value = selected_markets.strip()

        normalized_selected_markets = (
            [value]
            if value and value.lower() != "all"
            else []
        )

    elif isinstance(
        selected_markets,
        (list, tuple, set),
    ):
        normalized_selected_markets = [
            str(market).strip()
            for market in selected_markets
            if market
            and str(market).strip().lower() != "all"
        ]

    else:
        value = str(selected_markets).strip()

        normalized_selected_markets = (
            [value]
            if value and value.lower() != "all"
            else []
        )

    months = tree["months"]
    forecast_start_index = tree[
        "forecast_start_index"
    ]

    view_options = [
        {
            "label": "Product Level",
            "value": "product_level",
        },
        {
            "label": "Channel-Product Level",
            "value": "market_product_level",
        },
    ]

    # =====================================================
    # Complete table rows
    # =====================================================

    product_level_share_rows = (
        build_product_level_rows(
            tree,
            metric="share",
        )
    )

    market_product_share_rows = (
        build_market_product_rows(
            tree=tree,
            metric="share",
            decimals=2,
        )
    )

    product_level_volume_rows = (
        build_product_level_rows(
            tree,
            metric="volume",
        )
    )

    market_product_volume_rows = (
        build_market_product_rows(
            tree=tree,
            metric="volume",
            decimals=2,
        )
    )

    # =====================================================
    # Chart-specific rows
    # =====================================================

    market_product_share_chart_rows = (
        filter_market_product_rows_for_chart(
            rows=market_product_share_rows,
            selected_markets=(
                normalized_selected_markets
            ),
        )
    )

    market_product_volume_chart_rows = (
        filter_market_product_rows_for_chart(
            rows=market_product_volume_rows,
            selected_markets=(
                normalized_selected_markets
            ),
        )
    )

    # =====================================================
    # Monthly response tables
    # =====================================================

    product_level_share_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=product_level_share_rows,
            hierarchy=False,
        )
    )

    market_product_share_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=market_product_share_rows,
            hierarchy=True,
        )
    )

    product_level_volume_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=product_level_volume_rows,
            hierarchy=False,
        )
    )

    market_product_volume_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=market_product_volume_rows,
            hierarchy=True,
        )
    )

    product_level_volume_monthly = (
        round_table_values(
            product_level_volume_monthly,
            decimals=0,
        )
    )

    market_product_volume_monthly = (
        round_table_values(
            market_product_volume_monthly,
            decimals=0,
        )
    )

    # =====================================================
    # Internal monthly chart tables
    # =====================================================

    market_product_share_chart_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=(
                market_product_share_chart_rows
            ),
            hierarchy=True,
        )
    )

    market_product_volume_chart_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=(
                market_product_volume_chart_rows
            ),
            hierarchy=True,
        )
    )

    product_level_share_monthly["type"] = "flat"
    product_level_share_monthly[
        "editable"
    ] = False

    product_level_volume_monthly["type"] = "flat"
    product_level_volume_monthly[
        "editable"
    ] = False

    # =====================================================
    # Yearly response tables
    # =====================================================

    product_level_share_yearly = (
        build_yearly_table(
            product_level_share_monthly,
            aggregation="average",
        )
    )

    market_product_share_yearly = (
        build_yearly_table(
            market_product_share_monthly,
            aggregation="average",
        )
    )

    product_level_volume_yearly = (
        build_yearly_table(
            product_level_volume_monthly,
            aggregation="sum",
        )
    )

    market_product_volume_yearly = (
        build_yearly_table(
            market_product_volume_monthly,
            aggregation="sum",
        )
    )

    product_level_volume_yearly = (
        round_table_values(
            product_level_volume_yearly,
            decimals=0,
        )
    )

    market_product_volume_yearly = (
        round_table_values(
            market_product_volume_yearly,
            decimals=0,
        )
    )

    # =====================================================
    # Internal yearly chart tables
    # =====================================================

    market_product_share_chart_yearly = (
        build_yearly_table(
            market_product_share_chart_monthly,
            aggregation="average",
        )
    )

    market_product_volume_chart_yearly = (
        build_yearly_table(
            market_product_volume_chart_monthly,
            aggregation="sum",
        )
    )

    product_level_share_yearly["type"] = "flat"
    product_level_share_yearly[
        "editable"
    ] = False

    product_level_volume_yearly["type"] = "flat"
    product_level_volume_yearly[
        "editable"
    ] = False

    # =====================================================
    # Build charts once
    # =====================================================

    monthly_share_market_product_chart = (
        build_market_product_chart(
            market_product_share_chart_monthly,
            period_key="months",
        )
    )

    yearly_share_market_product_chart = (
        build_market_product_chart(
            market_product_share_chart_yearly,
            period_key="years",
        )
    )

    monthly_volume_market_product_chart = (
        build_market_product_chart(
            market_product_volume_chart_monthly,
            period_key="months",
        )
    )

    yearly_volume_market_product_chart = (
        build_market_product_chart(
            market_product_volume_chart_yearly,
            period_key="years",
        )
    )

    print(
        "[PRODUCT EVENT SELECTED MARKETS]",
        normalized_selected_markets,
    )

    print(
        "[PRODUCT EVENT MONTHLY SHARE SERIES]",
        [
            item.get("label")
            for item in (
                monthly_share_market_product_chart
                .get("series", [])
            )
        ],
    )

    # =====================================================
    # Response
    # =====================================================

    return {
        "impact_curve_configuration": (
            build_product_impact_curve_configuration(
                tree=tree,
                saved_events=saved_events,
            )
        ),

        "metrics_views": {
            "market_share": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": (
                        "market_product_level"
                    ),

                    "product_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                product_level_share_monthly
                            )
                        ),
                        "table": (
                            product_level_share_monthly
                        ),
                    },

                    "market_product_level": {
                        "chart": (
                            monthly_share_market_product_chart
                        ),
                        "table": (
                            market_product_share_monthly
                        ),
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": (
                        "market_product_level"
                    ),

                    "product_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_share_yearly
                            )
                        ),
                        "table": (
                            product_level_share_yearly
                        ),
                    },

                    "market_product_level": {
                        "chart": (
                            yearly_share_market_product_chart
                        ),
                        "table": (
                            market_product_share_yearly
                        ),
                    },
                },
            },

            "market_volume": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": (
                        "market_product_level"
                    ),

                    "product_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                product_level_volume_monthly
                            )
                        ),
                        "table": (
                            product_level_volume_monthly
                        ),
                    },

                    "market_product_level": {
                        "chart": (
                            monthly_volume_market_product_chart
                        ),
                        "table": (
                            market_product_volume_monthly
                        ),
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": (
                        "market_product_level"
                    ),

                    "product_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_volume_yearly
                            )
                        ),
                        "table": (
                            product_level_volume_yearly
                        ),
                    },

                    "market_product_level": {
                        "chart": (
                            yearly_volume_market_product_chart
                        ),
                        "table": (
                            market_product_volume_yearly
                        ),
                    },
                },
            },
        },
    }

def build_market_rows(tree, metric):
    """
    Build Market Event hierarchy:

    Overall
        Product
            Market
    """

    months_count = len(tree["months"])
    overall_volume = tree["overall"]["volume"]

    overall_values = (
        [100.0] * months_count
        if metric == "share"
        else overall_volume
    )

    rows = [
        {
            "label": "Overall",
            "values": overall_values,
        }
    ]

    for product_name in sorted(tree["products"]):

        product = tree["products"][product_name]

        product_row = {
            "label": product_name,
            "values": product[metric],
            "children": [],
        }

        for market_name in sorted(tree["markets"]):

            market = tree["markets"][market_name]

            # Sum this product's volume across sources in this market
            market_product_volume = [0.0] * months_count

            for source in market["sources"].values():

                product_node = source["products"].get(product_name)

                if not product_node:
                    continue

                market_product_volume = [
                    round(current + value, 2)
                    for current, value in zip(
                        market_product_volume,
                        product_node["volume"],
                    )
                ]

            if metric == "volume":
                child_values = market_product_volume

            else:
                # Market contribution to the overall product share
                child_values = [
                    round(product_volume / total_volume * 100, 2)
                    if total_volume
                    else 0.0
                    for product_volume, total_volume in zip(
                        market_product_volume,
                        overall_volume,
                    )
                ]

            product_row["children"].append(
                {
                    "label": market_name,
                    "values": child_values,
                }
            )

        rows.append(product_row)

    return rows

def build_product_market_chart(
    table,
    period_key,
):
    headers = list(
        table.get("headers") or []
    )

    if (
        headers
        and str(headers[0]).strip().lower()
        == "metric"
    ):
        headers = headers[1:]

    forecast_start_index = table.get(
        "forecast_start_index",
        len(headers),
    )

    series = []

    for product_row in table.get("rows", []):
        if not isinstance(product_row, dict):
            continue

        product_name = str(
            product_row.get("label", "")
        ).strip()

        if product_name.lower() in {
            "overall",
            "total",
            "grand total",
            "all",
        }:
            continue

        for market_row in (
            product_row.get("children") or []
        ):
            if not isinstance(market_row, dict):
                continue

            market_name = str(
                market_row.get("label", "")
            ).strip()

            if not market_name:
                continue

            values = list(
                market_row.get("values") or []
            )

            series.append(
                {
                    "label": (
                        f"{product_name} - "
                        f"{market_name}"
                    ),
                    "history": values[
                        :forecast_start_index
                    ],
                    "forecast": values[
                        forecast_start_index:
                    ],
                }
            )

    return {
        period_key: headers,
        "forecast_start_index":
            forecast_start_index,
        "series": series,
    }

def build_product_market_rows(
    tree: dict,
    metric: str = "share",
    decimals: int = 2,
) -> list:
    """
    Build Product -> Channel rows.

    Data priority:

    1. Use tree["product_market_inputs"] when available.
       This preserves the original Product-Channel input shares.

    2. Fall back to Product-Channel volumes stored under:
           market -> source -> product
       and calculate:
           channel share = channel volume / product total volume * 100

    This supports both Base and saved scenarios.
    """

    if metric not in {"share", "volume"}:
        raise ValueError(
            "metric must be either 'share' or 'volume'. "
            f"Received {metric!r}."
        )

    months = list(
        tree.get("months", [])
        or []
    )
    month_count = len(months)

    overall_volume = list(
        tree.get("overall", {}).get(
            "volume",
            [],
        )
        or []
    )

    if len(overall_volume) != month_count:
        raise ValueError(
            "Overall-volume length mismatch. "
            f"Expected {month_count}, "
            f"received {len(overall_volume)}."
        )

    markets = (
        tree.get("markets", {})
        or {}
    )

    market_order = list(markets.keys())

    # matrix[product][market] = monthly volumes
    product_market_volumes = {}

    # input_shares[product][market] = original input shares
    input_shares = {}

    # overall_product_shares[product] = overall product shares
    overall_product_shares = {}

    product_order = []

    # =====================================================
    # 1. Read preserved Product-Channel inputs
    # =====================================================

    product_market_inputs = (
        tree.get("product_market_inputs", {})
        or {}
    )

    for product_name, product_input in (
        product_market_inputs.items()
    ):
        if product_name not in product_order:
            product_order.append(product_name)

        overall_share = list(
            product_input.get(
                "overall_share",
                [],
            )
            or []
        )

        if len(overall_share) == month_count:
            overall_product_shares[
                product_name
            ] = [
                float(value or 0)
                for value in overall_share
            ]

        markets_for_product = (
            product_input.get(
                "markets",
                {},
            )
            or {}
        )

        for market_name, shares in (
            markets_for_product.items()
        ):
            shares = list(shares or [])

            if len(shares) != month_count:
                continue

            input_shares.setdefault(
                product_name,
                {},
            )[market_name] = [
                float(value or 0)
                for value in shares
            ]

    # =====================================================
    # 2. Build Product x Market volume matrix from tree
    # =====================================================

    for market_name, market_node in markets.items():

        sources = (
            market_node.get("sources", {})
            or {}
        )

        unknown_source = sources.get("Unknown")

        # Direct Product-Channel rows are normally stored
        # under the synthetic Unknown source.
        if unknown_source is not None:
            products = (
                unknown_source.get(
                    "products",
                    {},
                )
                or {}
            )

            for product_name, product_node in (
                products.items()
            ):
                volumes = list(
                    product_node.get(
                        "volume",
                        [],
                    )
                    or []
                )

                if len(volumes) != month_count:
                    raise ValueError(
                        "Product-volume length mismatch for "
                        f"{market_name!r}|"
                        f"{product_name!r}. "
                        f"Expected {month_count}, "
                        f"received {len(volumes)}."
                    )

                if product_name not in product_order:
                    product_order.append(product_name)

                product_market_volumes.setdefault(
                    product_name,
                    {},
                )[market_name] = [
                    float(value or 0)
                    for value in volumes
                ]

            continue

        # Fallback for real sources.
        for source_name, source_node in sources.items():

            products = (
                source_node.get(
                    "products",
                    {},
                )
                or {}
            )

            for product_name, product_node in (
                products.items()
            ):
                volumes = list(
                    product_node.get(
                        "volume",
                        [],
                    )
                    or []
                )

                if len(volumes) != month_count:
                    raise ValueError(
                        "Product-volume length mismatch for "
                        f"{market_name!r}|"
                        f"{source_name!r}|"
                        f"{product_name!r}. "
                        f"Expected {month_count}, "
                        f"received {len(volumes)}."
                    )

                if product_name not in product_order:
                    product_order.append(product_name)

                market_values = (
                    product_market_volumes
                    .setdefault(
                        product_name,
                        {},
                    )
                    .setdefault(
                        market_name,
                        [0.0] * month_count,
                    )
                )

                for index, value in enumerate(volumes):
                    market_values[index] += float(
                        value or 0
                    )

    # Preserve top-level product order.
    top_level_order = list(
        (
            tree.get("products", {})
            or {}
        ).keys()
    )

    ordered_products = [
        product_name
        for product_name in top_level_order
        if (
            product_name in product_market_volumes
            or product_name in input_shares
        )
    ]

    ordered_products.extend(
        product_name
        for product_name in product_order
        if product_name not in ordered_products
    )

    # =====================================================
    # Build response rows
    # =====================================================

    rows = []

    rows.append({
        "label": "Overall",
        "editable": False,
        "values": (
            [100.0] * month_count
            if metric == "share"
            else [
                round(
                    float(value or 0),
                    decimals,
                )
                for value in overall_volume
            ]
        ),
        "children": [],
    })

    for product_name in ordered_products:

        market_volume_map = (
            product_market_volumes.get(
                product_name,
                {},
            )
        )

        product_input_shares = (
            input_shares.get(
                product_name,
                {},
            )
        )

        available_markets = set(
            market_volume_map.keys()
        ) | set(
            product_input_shares.keys()
        )

        if not available_markets:
            continue

        ordered_markets = [
            market_name
            for market_name in market_order
            if market_name in available_markets
        ]

        ordered_markets.extend(
            market_name
            for market_name in available_markets
            if market_name not in ordered_markets
        )

        # -----------------------------------------------
        # Calculate product total volume
        # -----------------------------------------------

        product_total_volumes = [
            0.0
        ] * month_count

        if market_volume_map:
            for market_values in (
                market_volume_map.values()
            ):
                for index, value in enumerate(
                    market_values
                ):
                    product_total_volumes[
                        index
                    ] += float(value or 0)

        elif product_name in overall_product_shares:
            product_total_volumes = [
                float(total or 0)
                * float(share or 0)
                / 100
                for total, share in zip(
                    overall_volume,
                    overall_product_shares[
                        product_name
                    ],
                )
            ]

        children = []

        for market_name in ordered_markets:

            channel_volumes = market_volume_map.get(
                market_name
            )

            original_channel_shares = (
                product_input_shares.get(
                    market_name
                )
            )

            # -------------------------------------------
            # Share values
            # -------------------------------------------

            if metric == "share":

                # Always derive shares from the latest tree volumes.
                if channel_volumes is not None:

                    child_values = []

                    for channel_volume, product_total in zip(
                        channel_volumes,
                        product_total_volumes,
                    ):

                        if float(product_total or 0) == 0:
                            child_values.append(0.0)
                        else:
                            child_values.append(
                                round(
                                    float(channel_volume or 0)
                                    / float(product_total or 0)
                                    * 100,
                                    decimals,
                                )
                            )

                # Fallback only when volumes are unavailable.
                elif original_channel_shares is not None:

                    child_values = [
                        round(
                            float(value or 0),
                            decimals,
                        )
                        for value in original_channel_shares
                    ]

                else:

                    child_values = [
                        0.0
                    ] * month_count

            # -------------------------------------------
            # Volume values
            # -------------------------------------------

            else:

                if channel_volumes is not None:

                    child_values = [
                        round(
                            float(value or 0),
                            decimals,
                        )
                        for value in channel_volumes
                    ]

                elif original_channel_shares is not None:

                    child_values = [
                        round(
                            float(product_total or 0)
                            * float(channel_share or 0)
                            / 100,
                            decimals,
                        )
                        for (
                            product_total,
                            channel_share,
                        ) in zip(
                            product_total_volumes,
                            original_channel_shares,
                        )
                    ]

                else:

                    child_values = [
                        0.0
                    ] * month_count

            children.append({
                "label": market_name,
                "parent": product_name,
                "editable": True,
                "values": child_values,
                "children": [],
            })

        parent_values = (
            [100.0] * month_count
            if metric == "share"
            else [
                round(
                    float(value or 0),
                    decimals,
                )
                for value in product_total_volumes
            ]
        )

        rows.append({
            "label": product_name,
            "editable": False,
            "values": parent_values,
            "children": children,
        })

    return rows

from copy import deepcopy


def filter_product_market_rows_for_chart(
    *,
    rows: list,
    selected_products=None,
) -> list:
    """
    Filter Product -> Market hierarchy rows for chart use.

    The chart uses the exact same values as the table.

    Input hierarchy
    ---------------
    Overall

    Biktarvy
        Non-retail
        Retail

    Descovy
        Non-retail
        Retail

    Output
    ------
    Only selected product parents and their market children.

    If no products are selected, all products are returned.
    """

    selected_product_set = {
        str(product).strip().lower()
        for product in (selected_products or [])
        if (
            product
            and str(product).strip().lower() != "all"
        )
    }

    filtered_rows = []

    for row in rows or []:

        product_name = str(
            row.get("label", "")
        ).strip()

        # Overall is not required in the Product-Market chart.
        if product_name.lower() == "overall":
            continue

        if (
            selected_product_set
            and product_name.lower()
            not in selected_product_set
        ):
            continue

        filtered_row = deepcopy(row)

        filtered_row["editable"] = False

        for child in (
            filtered_row.get("children", [])
            or []
        ):
            child["editable"] = False
            child["parent"] = product_name

        filtered_rows.append(filtered_row)

    return filtered_rows

def build_market_event(
    tree,
    selected_products=None,
    saved_events=None,
):
    """
    Build Market Event.

    Table behaviour:
        Includes all products and all market cuts.

    Product-Market chart behaviour:
        Includes only selected products.
        Includes all markets for those selected products.

    Supports:
        selected_products="Biktarvy"
        selected_products=["Biktarvy"]
    """

    # =====================================================
    # Normalize selected products
    # =====================================================

    if selected_products is None:
        normalized_selected_products = []

    elif isinstance(selected_products, str):
        value = selected_products.strip()

        normalized_selected_products = (
            [value]
            if value and value.lower() != "all"
            else []
        )

    elif isinstance(
        selected_products,
        (list, tuple, set),
    ):
        normalized_selected_products = [
            str(product).strip()
            for product in selected_products
            if product
            and str(product).strip().lower() != "all"
        ]

    else:
        value = str(selected_products).strip()

        normalized_selected_products = (
            [value]
            if value and value.lower() != "all"
            else []
        )

    months = tree["months"]
    forecast_start_index = tree[
        "forecast_start_index"
    ]

    view_options = [
        {
            "label": "Channel Level",
            "value": "market_level",
        },
        {
            "label": "Product-Channel Level",
            "value": "product_market_level",
        },
    ]

    # =====================================================
    # Complete table rows
    # =====================================================

    market_level_share_rows = (
        build_market_level_rows(
            tree,
            metric="share",
        )
    )

    # Full Product -> Market hierarchy for table
    product_market_share_rows = (
        build_product_market_rows(
            tree=tree,
            metric="share",
            decimals=2,
        )
    )

    market_level_volume_rows = (
        build_market_level_rows(
            tree,
            metric="volume",
        )
    )

    # Full Product -> Market hierarchy for table
    product_market_volume_rows = (
        build_product_market_rows(
            tree=tree,
            metric="volume",
            decimals=2,
        )
    )

    # =====================================================
    # Filtered Product-Market chart rows
    # =====================================================

    product_market_share_chart_rows = (
        filter_product_market_rows_for_chart(
            rows=product_market_share_rows,
            selected_products=(
                normalized_selected_products
            ),
        )
    )

    product_market_volume_chart_rows = (
        filter_product_market_rows_for_chart(
            rows=product_market_volume_rows,
            selected_products=(
                normalized_selected_products
            ),
        )
    )

    # =====================================================
    # Monthly response tables
    # =====================================================

    market_level_share_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=market_level_share_rows,
            hierarchy=False,
        )
    )

    product_market_share_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=product_market_share_rows,
            hierarchy=True,
        )
    )

    market_level_volume_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=market_level_volume_rows,
            hierarchy=False,
        )
    )

    product_market_volume_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=product_market_volume_rows,
            hierarchy=True,
        )
    )

    # =====================================================
    # Internal monthly chart tables
    # =====================================================

    product_market_share_chart_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=(
                product_market_share_chart_rows
            ),
            hierarchy=True,
        )
    )

    product_market_volume_chart_monthly = (
        build_monthly_table(
            headers=months,
            forecast_start_index=(
                forecast_start_index
            ),
            rows=(
                product_market_volume_chart_rows
            ),
            hierarchy=True,
        )
    )

    market_level_share_monthly["type"] = "flat"
    market_level_share_monthly[
        "editable"
    ] = False

    market_level_volume_monthly["type"] = "flat"
    market_level_volume_monthly[
        "editable"
    ] = False

    # =====================================================
    # Yearly response tables
    # =====================================================

    product_level_share_yearly = (
        build_yearly_table(
            market_level_share_monthly,
            aggregation="average",
        )
    )

    product_market_share_yearly = (
        build_yearly_table(
            product_market_share_monthly,
            aggregation="average",
        )
    )

    product_level_volume_yearly = (
        build_yearly_table(
            market_level_volume_monthly,
            aggregation="sum",
        )
    )

    product_market_volume_yearly = (
        build_yearly_table(
            product_market_volume_monthly,
            aggregation="sum",
        )
    )

    # =====================================================
    # Internal yearly chart tables
    # =====================================================

    product_market_share_chart_yearly = (
        build_yearly_table(
            product_market_share_chart_monthly,
            aggregation="average",
        )
    )

    product_market_volume_chart_yearly = (
        build_yearly_table(
            product_market_volume_chart_monthly,
            aggregation="sum",
        )
    )

    product_level_share_yearly["type"] = "flat"
    product_level_share_yearly[
        "editable"
    ] = False

    product_level_volume_yearly["type"] = "flat"
    product_level_volume_yearly[
        "editable"
    ] = False

    # =====================================================
    # Round volume tables
    # =====================================================

    market_level_volume_monthly = (
        round_table_values(
            market_level_volume_monthly
        )
    )

    product_market_volume_monthly = (
        round_table_values(
            product_market_volume_monthly
        )
    )

    product_level_volume_yearly = (
        round_table_values(
            product_level_volume_yearly
        )
    )

    product_market_volume_yearly = (
        round_table_values(
            product_market_volume_yearly
        )
    )

    # =====================================================
    # Build charts once
    # =====================================================

    monthly_share_product_market_chart = (
        build_product_market_chart(
            product_market_share_chart_monthly,
            period_key="months",
        )
    )

    yearly_share_product_market_chart = (
        build_product_market_chart(
            product_market_share_chart_yearly,
            period_key="years",
        )
    )

    monthly_volume_product_market_chart = (
        build_product_market_chart(
            product_market_volume_chart_monthly,
            period_key="months",
        )
    )

    yearly_volume_product_market_chart = (
        build_product_market_chart(
            product_market_volume_chart_yearly,
            period_key="years",
        )
    )

    # Temporary debugging
    print(
        "[MARKET EVENT SELECTED PRODUCTS]",
        normalized_selected_products,
    )

    print(
        "[MARKET EVENT MONTHLY SHARE SERIES]",
        [
            item.get("label")
            for item in (
                monthly_share_product_market_chart
                .get("series", [])
            )
        ],
    )

    # =====================================================
    # Response
    # =====================================================

    return {
        "impact_curve_configuration": (
            build_market_impact_curve_configuration(
                tree=tree,
                saved_events=saved_events,
            )
        ),

        "metrics_views": {
            "market_share": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": (
                        "product_market_level"
                    ),

                    "market_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                market_level_share_monthly
                            )
                        ),
                        "table": (
                            market_level_share_monthly
                        ),
                    },

                    "product_market_level": {
                        "chart": (
                            monthly_share_product_market_chart
                        ),
                        "table": (
                            product_market_share_monthly
                        ),
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": (
                        "product_market_level"
                    ),

                    "market_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_share_yearly
                            )
                        ),
                        "table": (
                            product_level_share_yearly
                        ),
                    },

                    "product_market_level": {
                        "chart": (
                            yearly_share_product_market_chart
                        ),
                        "table": (
                            product_market_share_yearly
                        ),
                    },
                },
            },

            "market_volume": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": (
                        "product_market_level"
                    ),

                    "market_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                market_level_volume_monthly
                            )
                        ),
                        "table": (
                            market_level_volume_monthly
                        ),
                    },

                    "product_market_level": {
                        "chart": (
                            monthly_volume_product_market_chart
                        ),
                        "table": (
                            product_market_volume_monthly
                        ),
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": (
                        "product_market_level"
                    ),

                    "market_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_volume_yearly
                            )
                        ),
                        "table": (
                            product_level_volume_yearly
                        ),
                    },

                    "product_market_level": {
                        "chart": (
                            yearly_volume_product_market_chart
                        ),
                        "table": (
                            product_market_volume_yearly
                        ),
                    },
                },
            },
        },
    }

def build_market_chart_rows(
    tree,
    metric,
    selected_products=None,
):
    """
    Build Product-Market chart rows.

    Includes:
        - only selected products
        - every market for those products
    """

    months_count = len(tree["months"])
    overall_volume = tree["overall"]["volume"]

    selected_product_set = {
        str(product).strip().lower()
        for product in (selected_products or [])
        if product
    }

    rows = []

    for product_name in sorted(tree["products"]):
        normalized_product_name = (
            str(product_name)
            .strip()
            .lower()
        )

        if (
            selected_product_set
            and normalized_product_name
            not in selected_product_set
        ):
            continue

        product_row = {
            "label": product_name,
            "values": [0.0] * months_count,
            "children": [],
        }

        # No selected-market filtering here.
        # Every market is included for the selected product.
        for market_name in sorted(tree["markets"]):
            market = tree["markets"][market_name]

            market_product_volume = [0.0] * months_count

            for source in market.get("sources", {}).values():
                product_node = (
                    source
                    .get("products", {})
                    .get(product_name)
                )

                if not product_node:
                    continue

                product_values = product_node.get(
                    "volume",
                    [],
                )

                market_product_volume = [
                    round(current + value, 2)
                    for current, value in zip(
                        market_product_volume,
                        product_values,
                    )
                ]

            if metric == "volume":
                child_values = market_product_volume

            else:
                child_values = [
                    round(
                        product_volume
                        / total_volume
                        * 100,
                        2,
                    )
                    if total_volume
                    else 0.0
                    for product_volume, total_volume in zip(
                        market_product_volume,
                        overall_volume,
                    )
                ]

            product_row["children"].append(
                {
                    "label": market_name,
                    "values": child_values,
                }
            )

            product_row["values"] = [
                round(current + value, 2)
                for current, value in zip(
                    product_row["values"],
                    child_values,
                )
            ]

        if product_row["children"]:
            rows.append(product_row)

    return rows

def normalize_overall_event(event):
    """
    Normalize one saved Overall Event row.

    Overall events are identified by the absence of:
        impacted_markets
        impacted_products
    """

    if not isinstance(event, dict):
        return None

    if "impacted_markets" in event:
        return None

    if "impacted_products" in event:
        return None

    return {
        "event_id": event.get("event_id"),

        "event_name": str(
            event.get("event_name", "") or ""
        ),

        "start_date": event.get("start_date"),

        "peak_percent": float(
            event.get("peak_percent", 0) or 0
        ),

        "months": int(
            event.get("months", 0) or 0
        ),

        "curve_type": str(
            event.get("curve_type", "Linear")
            or "Linear"
        ),

        "factor": float(
            event.get("factor", 0) or 0
        ),

        "enable_coverage": bool(
            event.get("enable_coverage", False)
        ),

        "coverage_peak_percent": float(
            event.get(
                "coverage_peak_percent",
                0,
            )
            or 0
        ),

        "coverage_peak_months": int(
            event.get(
                "coverage_peak_months",
                0,
            )
            or 0
        ),

        "coverage_curve_type": str(
            event.get(
                "coverage_curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "coverage_factor": float(
            event.get(
                "coverage_factor",
                0,
            )
            or 0
        ),
    }

def build_overall_impact_curve_configuration(
    tree,
    saved_events=None,
):
    """
    Build Overall Event impact-curve configuration.

    saved_events may contain overall, market, and product events.
    Only overall events are included here.
    """

    normalized_rows = []

    for event in saved_events or []:
        normalized_event = normalize_overall_event(
            event
        )

        if normalized_event is not None:
            normalized_rows.append(
                normalized_event
            )

    return {
        "products": list(
            tree["products"].keys()
        ),

        "markets": list(
            tree["markets"].keys()
        ),

        "impact_markets": [
            "Overall"
        ],

        "forecast_start_date": (
            tree["months"][
                tree["forecast_start_index"]
            ]
            if (
                tree["forecast_start_index"]
                < len(tree["months"])
            )
            else None
        ),

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "SCurve",
        ],

        "rows": normalized_rows,
    }

def normalize_market_event(event):
    """
    Normalize one saved Market Event row.

    A Market Event is identified by the presence of:
        impacted_markets
    """

    if not isinstance(event, dict):
        return None

    if "impacted_markets" not in event:
        return None

    markets = event.get("markets") or []
    products = event.get("products") or []
    impacted_markets = (
        event.get("impacted_markets") or []
    )

    if isinstance(markets, str):
        markets = [markets]

    if isinstance(products, str):
        products = [products]

    if isinstance(impacted_markets, str):
        impacted_markets = [
            impacted_markets
        ]

    source_percentages = (
        event.get("source_percentages") or {}
    )

    return {
        "event_id": event.get("event_id"),

        "event_name": str(
            event.get("event_name", "") or ""
        ),

        "markets": markets,

        "products": products,

        "impacted_markets": impacted_markets,

        "start_date": event.get(
            "start_date"
        ),

        "peak_percent": float(
            event.get(
                "peak_percent",
                0,
            )
            or 0
        ),

        "months": int(
            event.get(
                "months",
                0,
            )
            or 0
        ),

        "curve_type": str(
            event.get(
                "curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "factor": float(
            event.get(
                "factor",
                0,
            )
            or 0
        ),

        "enable_coverage": bool(
            event.get(
                "enable_coverage",
                False,
            )
        ),

        "source_percentages": {
            str(market): float(
                percentage or 0
            )
            for market, percentage
            in source_percentages.items()
        },

        "coverage_peak_percent": float(
            event.get(
                "coverage_peak_percent",
                0,
            )
            or 0
        ),

        "coverage_peak_months": int(
            event.get(
                "coverage_peak_months",
                0,
            )
            or 0
        ),

        "coverage_curve_type": str(
            event.get(
                "coverage_curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "coverage_factor": float(
            event.get(
                "coverage_factor",
                0,
            )
            or 0
        ),
    }

def build_market_impact_curve_configuration(
    tree,
    saved_events=None,
):
    """
    Build Market Event impact-curve configuration.

    saved_events may contain overall, market,
    and product events. Only market events are
    returned in rows.
    """

    saved_events = saved_events or []

    rows = []

    for event in saved_events:
        normalized_event = normalize_market_event(
            event
        )

        if normalized_event is not None:
            rows.append(normalized_event)

    print(
        "[MARKET CONFIG] RECEIVED EVENTS:",
        len(saved_events),
    )

    print(
        "[MARKET CONFIG] MARKET ROWS:",
        len(rows),
    )

    return {
        "products": list(
            tree["products"].keys()
        ),

        "markets": list(
            tree["markets"].keys()
        ),

        "impact_markets": list(
            tree["markets"].keys()
        ),

        "forecast_start_date": (
            tree["months"][
                tree["forecast_start_index"]
            ]
            if (
                tree["forecast_start_index"]
                < len(tree["months"])
            )
            else None
        ),

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "SCurve",
        ],

        "rows": rows,
    }

def normalize_product_event(event):
    """
    Normalize one saved Product Event row.

    Product Events are identified by the presence of:
        impacted_products

    Key presence is used because impacted_products
    can validly be an empty list.
    """

    if not isinstance(event, dict):
        return None

    if "impacted_products" not in event:
        return None

    markets = event.get("markets") or []
    products = event.get("products") or []
    impacted_products = (
        event.get("impacted_products") or []
    )

    if isinstance(markets, str):
        markets = [markets]

    if isinstance(products, str):
        products = [products]

    if isinstance(impacted_products, str):
        impacted_products = [
            impacted_products
        ]

    source_percentages = (
        event.get("source_percentages") or {}
    )

    if not isinstance(source_percentages, dict):
        source_percentages = {}

    return {
        "event_id": event.get("event_id"),

        "event_name": str(
            event.get("event_name", "") or ""
        ),

        "markets": markets,

        "products": products,

        "impacted_products": impacted_products,

        "start_date": event.get(
            "start_date"
        ),

        "peak_percent": float(
            event.get(
                "peak_percent",
                0,
            )
            or 0
        ),

        "months": int(
            event.get(
                "months",
                0,
            )
            or 0
        ),

        "curve_type": str(
            event.get(
                "curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "factor": float(
            event.get(
                "factor",
                0,
            )
            or 0
        ),

        "enable_coverage": bool(
            event.get(
                "enable_coverage",
                False,
            )
        ),

        "source_percentages": {
            str(product): float(
                percentage or 0
            )
            for product, percentage
            in source_percentages.items()
        },

        "coverage_peak_percent": float(
            event.get(
                "coverage_peak_percent",
                0,
            )
            or 0
        ),

        "coverage_peak_months": int(
            event.get(
                "coverage_peak_months",
                0,
            )
            or 0
        ),

        "coverage_curve_type": str(
            event.get(
                "coverage_curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "coverage_factor": float(
            event.get(
                "coverage_factor",
                0,
            )
            or 0
        ),
    }

def build_product_impact_curve_configuration(
    tree,
    saved_events=None,
):
    """
    Build Product Event impact-curve configuration.

    saved_events can contain events from all tabs.
    Only events containing impacted_products are
    returned in rows.
    """

    saved_events = saved_events or []

    rows = []

    for event in saved_events:
        normalized_event = (
            normalize_product_event(event)
        )

        if normalized_event is not None:
            rows.append(normalized_event)

    forecast_start_index = tree[
        "forecast_start_index"
    ]

    forecast_start_date = (
        tree["months"][forecast_start_index]
        if forecast_start_index
        < len(tree["months"])
        else None
    )

    print(
        "[PRODUCT CONFIG] RECEIVED EVENTS:",
        len(saved_events),
    )

    print(
        "[PRODUCT CONFIG] PRODUCT ROWS:",
        len(rows),
    )

    return {
        "products": list(
            tree["products"].keys()
        ),

        "markets": list(
            tree["markets"].keys()
        ),

        "impact_products": list(
            tree["products"].keys()
        ),

        "forecast_start_date": (
            forecast_start_date
        ),

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "SCurve",
        ],

        "rows": rows,
    }

# def build_impact_curve_configuration(tree):
#     """
#     Build Impact Curve Configuration.
#     """

#     return {
#         "products": sorted(tree["products"].keys()),

#         "markets": sorted(tree["markets"].keys()),

#         "impact_markets": sorted(tree["markets"].keys()),

#         "forecast_start_date": tree["months"][tree["forecast_start_index"]],

#         "curve_types": [
#             "Linear",
#             "Exponential",
#             "Logarithmic",
#             "SCurve",
#         ],

#         "rows": [],
#     }

def build_product_level_rows(
    tree: dict,
    metric: str = "share",
    decimals: int = 2,
) -> list:
    """
    Build Product Level rows.

    Structure
    ---------
    Overall
    Biktarvy
    Descovy
    Truvada

    Canonical values
    ----------------
    Volume:
        tree["products"][product]["volume"]

    Share:
        product volume / overall volume * 100

    IMPORTANT:
        Never aggregate source-product nodes here because
        markets may contain overlapping source representations
        such as:

            ADAP
            Federal
            IQVIA
            Kaiser
            Unknown

        tree["products"] contains the canonical overall
        product totals produced by recompute_tree().
    """

    if metric not in {
        "share",
        "volume",
    }:
        raise ValueError(
            "metric must be either 'share' or 'volume'."
        )

    months = tree.get(
        "months",
        [],
    )

    overall_values = list(
        tree.get(
            "overall",
            {},
        ).get(
            "volume",
            [],
        )
        or []
    )

    products = tree.get(
        "products",
        {},
    )

    rows = []

    # =====================================================
    # Overall
    # =====================================================

    if metric == "share":

        rows.append(
            {
                "label": "Overall",
                "editable": False,
                "values": [
                    100.0
                    if float(value or 0) > 0
                    else 0.0
                    for value in overall_values
                ],
            }
        )

    else:

        rows.append(
            {
                "label": "Overall",
                "editable": False,
                "values": [
                    round(
                        float(value or 0),
                        decimals,
                    )
                    for value in overall_values
                ],
            }
        )

    # =====================================================
    # Products
    # =====================================================

    for product_name, product_node in (
        products.items()
    ):

        product_volumes = list(
            product_node.get(
                "volume",
                [],
            )
            or []
        )

        values = []

        for month_index in range(
            len(months)
        ):

            product_volume = (
                float(
                    product_volumes[
                        month_index
                    ]
                    or 0
                )
                if month_index
                < len(product_volumes)
                else 0.0
            )

            if metric == "volume":

                value = round(
                    product_volume,
                    decimals,
                )

            else:

                overall_volume = (
                    float(
                        overall_values[
                            month_index
                        ]
                        or 0
                    )
                    if month_index
                    < len(overall_values)
                    else 0.0
                )

                if overall_volume == 0:
                    value = 0.0
                else:
                    value = round(
                        product_volume
                        / overall_volume
                        * 100.0,
                        decimals,
                    )

            values.append(
                value
            )

        rows.append(
            {
                "label": product_name,
                "editable": True,
                "values": values,
            }
        )

    return rows

def build_market_level_rows(tree, metric):
    """
    Overall
    Retail
    Non-retail
    """

    overall_values = (
        [100] * len(tree["months"])
        if metric == "share"
        else tree["overall"]["volume"]
    )

    rows = [
        {
            "label": "Overall",
            "values": overall_values,
        }
    ]

    for market_name in sorted(tree["markets"]):

        rows.append(
            {
                "label": market_name,
                "values": tree["markets"][market_name][metric],
            }
        )

    return rows

# def build_market_product_rows(tree, metric):
#     """
#     Overall

#         Retail
#             Biktarvy
#             Descovy
#             Truvada

#         Non-retail
#             Biktarvy
#             Descovy
#             Truvada
#     """

#     overall_values = (
#         [100] * len(tree["months"])
#         if metric == "share"
#         else tree["overall"]["volume"]
#     )

#     rows = [
#         {
#             "label": "Overall",
#             "values": overall_values,
#         }
#     ]

#     for market_name in sorted(tree["markets"]):

#         market = tree["markets"][market_name]

#         market_row = {
#             "label": market_name,
#             "values": market[metric],
#             "children": [],
#         }

#         product_totals = {}

#         for source in market["sources"].values():

#             for product_name, product in source["products"].items():

#                 if product_name not in product_totals:

#                     product_totals[product_name] = [0] * len(product[metric])

#                 product_totals[product_name] = [

#                     round(a + b, 2)

#                     for a, b in zip(
#                         product_totals[product_name],
#                         product[metric],
#                     )
#                 ]

#         for product_name in sorted(product_totals):

#             market_row["children"].append(
#                 {
#                     "label": product_name,
#                     "values": product_totals[product_name],
#                 }
#             )

#         rows.append(market_row)

#     return rows

