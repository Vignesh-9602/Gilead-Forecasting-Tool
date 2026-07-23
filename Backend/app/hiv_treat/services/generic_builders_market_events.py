from app.hiv_treat.services.response_builder_market_events import *

from copy import deepcopy


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

def build_overall_event(tree):
    """
    Build Overall Event from the calculation tree.

    Provides one view:
        overall_level
    """

    months = tree["months"]
    forecast_start_index = tree["forecast_start_index"]

    overall_volume = tree["overall"]["volume"]
    overall_share = [100.0] * len(months)

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

    # Overall-level tables are flat and non-editable
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
        "impact_curve_configuration":
            build_overall_impact_curve_configuration(tree),

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



def build_product_event(
    tree,
    selected_markets=None,
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

    Example:
        selected_markets = ["Non-retail"]

        Chart:
            Non-retail - Biktarvy
            Non-retail - Descovy
            Non-retail - Truvada

        Table:
            Overall
            Retail
                Biktarvy
                Descovy
                Truvada
            Non-retail
                Biktarvy
                Descovy
                Truvada
    """

    months = tree["months"]
    forecast_start_index = tree["forecast_start_index"]

    view_options = [
        {
            "label": "Product Level",
            "value": "product_level",
        },
        {
            "label": "Market-Product Level",
            "value": "market_product_level",
        },
    ]

    # =====================================================
    # Complete table rows
    # =====================================================

    product_level_share_rows = build_product_level_rows(
        tree,
        metric="share",
    )

    # Complete table: all markets and all products.
    market_product_share_rows = build_product_rows(
        tree,
        metric="share",
    )

    product_level_volume_rows = build_product_level_rows(
        tree,
        metric="volume",
    )

    # Complete table: all markets and all products.
    market_product_volume_rows = build_product_rows(
        tree,
        metric="volume",
    )

    # =====================================================
    # Chart-specific rows
    # =====================================================

    # Selected markets + all products.
    market_product_share_chart_rows = (
        build_product_chart_rows(
            tree=tree,
            metric="share",
            selected_markets=selected_markets,
        )
    )

    market_product_volume_chart_rows = (
        build_product_chart_rows(
            tree=tree,
            metric="volume",
            selected_markets=selected_markets,
        )
    )

    # =====================================================
    # Monthly response tables
    # =====================================================

    product_level_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=product_level_share_rows,
        hierarchy=False,
    )

    market_product_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=market_product_share_rows,
        hierarchy=True,
    )

    product_level_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=product_level_volume_rows,
        hierarchy=False,
    )

    market_product_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=market_product_volume_rows,
        hierarchy=True,
    )

    # =====================================================
    # Internal monthly chart tables
    # =====================================================

    market_product_share_chart_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=market_product_share_chart_rows,
        hierarchy=True,
    )

    market_product_volume_chart_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=market_product_volume_chart_rows,
        hierarchy=True,
    )

    # Flat views should be non-editable.
    product_level_share_monthly["type"] = "flat"
    product_level_share_monthly["editable"] = False

    product_level_volume_monthly["type"] = "flat"
    product_level_volume_monthly["editable"] = False

    # =====================================================
    # Yearly response tables
    # =====================================================

    product_level_share_yearly = build_yearly_table(
        product_level_share_monthly,
        aggregation="average",
    )

    market_product_share_yearly = build_yearly_table(
        market_product_share_monthly,
        aggregation="average",
    )

    product_level_volume_yearly = build_yearly_table(
        product_level_volume_monthly,
        aggregation="sum",
    )

    market_product_volume_yearly = build_yearly_table(
        market_product_volume_monthly,
        aggregation="sum",
    )

    # =====================================================
    # Internal yearly chart tables
    # =====================================================

    market_product_share_chart_yearly = build_yearly_table(
        market_product_share_chart_monthly,
        aggregation="average",
    )

    market_product_volume_chart_yearly = build_yearly_table(
        market_product_volume_chart_monthly,
        aggregation="sum",
    )

    # Preserve flat/non-editable configuration.
    product_level_share_yearly["type"] = "flat"
    product_level_share_yearly["editable"] = False

    product_level_volume_yearly["type"] = "flat"
    product_level_volume_yearly["editable"] = False

    # =====================================================
    # Response
    # =====================================================

    return {
        "impact_curve_configuration":
            build_product_impact_curve_configuration(tree),

        "metrics_views": {
            "market_share": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view":
                        "market_product_level",

                    "product_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                product_level_share_monthly
                            )
                        ),
                        "table":
                            product_level_share_monthly,
                    },

                    "market_product_level": {
                        # Selected markets + all products.
                        "chart":
                            build_market_product_chart(
                                market_product_share_chart_monthly,
                                period_key="months",
                            ),

                        # Complete table with all cuts.
                        "table":
                            market_product_share_monthly,
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view":
                        "market_product_level",

                    "product_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_share_yearly
                            )
                        ),
                        "table":
                            product_level_share_yearly,
                    },

                    "market_product_level": {
                        # Selected markets + all products.
                        "chart":
                            build_market_product_chart(
                                market_product_share_chart_yearly,
                                period_key="years",
                            ),

                        # Complete table with all cuts.
                        "table":
                            market_product_share_yearly,
                    },
                },
            },

            "market_volume": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view":
                        "market_product_level",

                    "product_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                product_level_volume_monthly
                            )
                        ),
                        "table":
                            product_level_volume_monthly,
                    },

                    "market_product_level": {
                        # Selected markets + all products.
                        "chart":
                            build_market_product_chart(
                                market_product_volume_chart_monthly,
                                period_key="months",
                            ),

                        # Complete table with all cuts.
                        "table":
                            market_product_volume_monthly,
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view":
                        "market_product_level",

                    "product_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_volume_yearly
                            )
                        ),
                        "table":
                            product_level_volume_yearly,
                    },

                    "market_product_level": {
                        # Selected markets + all products.
                        "chart":
                            build_market_product_chart(
                                market_product_volume_chart_yearly,
                                period_key="years",
                            ),

                        # Complete table with all cuts.
                        "table":
                            market_product_volume_yearly,
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

def build_market_event(
    tree,
    selected_products=None,
):
    """
    Build Market Event.

    Table behaviour:
        Includes all products and all market cuts.

    Product-Market chart behaviour:
        Includes only selected products.
        Includes all markets for those selected products.

    Example:
        selected_products = ["Biktarvy"]

        Chart:
            Retail - Biktarvy
            Non-retail - Biktarvy

        Table:
            Overall
            Biktarvy
                Retail
                Non-retail
            Descovy
                Retail
                Non-retail
            Truvada
                Retail
                Non-retail
    """

    months = tree["months"]
    forecast_start_index = tree["forecast_start_index"]

    view_options = [
        {
            "label": "Market Level",
            "value": "market_level",
        },
        {
            "label": "Product-Market Level",
            "value": "product_market_level",
        },
    ]

    # =====================================================
    # Complete table rows
    # =====================================================

    market_level_share_rows = build_market_level_rows(
        tree,
        metric="share",
    )

    # Table contains every product and every market.
    product_market_share_rows = build_market_rows(
        tree,
        metric="share",
    )

    market_level_volume_rows = build_market_level_rows(
        tree,
        metric="volume",
    )

    # Table contains every product and every market.
    product_market_volume_rows = build_market_rows(
        tree,
        metric="volume",
    )

    # =====================================================
    # Product-Market chart rows
    # =====================================================

    # Chart contains selected products across every market.
    product_market_share_chart_rows = build_market_chart_rows(
        tree=tree,
        metric="share",
        selected_products=selected_products,
    )

    product_market_volume_chart_rows = build_market_chart_rows(
        tree=tree,
        metric="volume",
        selected_products=selected_products,
    )

    # =====================================================
    # Monthly response tables
    # =====================================================

    market_level_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=market_level_share_rows,
        hierarchy=False,
    )

    product_market_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=product_market_share_rows,
        hierarchy=True,
    )

    market_level_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=market_level_volume_rows,
        hierarchy=False,
    )

    product_market_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=product_market_volume_rows,
        hierarchy=True,
    )

    # =====================================================
    # Internal monthly chart tables
    # =====================================================

    # These objects are used only to generate chart series.
    # They are not returned as the displayed table.
    product_market_share_chart_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=product_market_share_chart_rows,
        hierarchy=True,
    )

    product_market_volume_chart_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=product_market_volume_chart_rows,
        hierarchy=True,
    )

    # Market-level tables are flat and non-editable.
    market_level_share_monthly["type"] = "flat"
    market_level_share_monthly["editable"] = False

    market_level_volume_monthly["type"] = "flat"
    market_level_volume_monthly["editable"] = False

    # =====================================================
    # Yearly response tables
    # =====================================================

    product_level_share_yearly = build_yearly_table(
        market_level_share_monthly,
        aggregation="average",
    )

    product_market_share_yearly = build_yearly_table(
        product_market_share_monthly,
        aggregation="average",
    )

    product_level_volume_yearly = build_yearly_table(
        market_level_volume_monthly,
        aggregation="sum",
    )

    product_market_volume_yearly = build_yearly_table(
        product_market_volume_monthly,
        aggregation="sum",
    )

    # =====================================================
    # Internal yearly chart tables
    # =====================================================

    product_market_share_chart_yearly = build_yearly_table(
        product_market_share_chart_monthly,
        aggregation="average",
    )

    product_market_volume_chart_yearly = build_yearly_table(
        product_market_volume_chart_monthly,
        aggregation="sum",
    )

    # Preserve flat/non-editable settings.
    product_level_share_yearly["type"] = "flat"
    product_level_share_yearly["editable"] = False

    product_level_volume_yearly["type"] = "flat"
    product_level_volume_yearly["editable"] = False

    # =====================================================
    # Response
    # =====================================================

    return {
        "impact_curve_configuration":
            build_market_impact_curve_configuration(tree),

        "metrics_views": {
            "market_share": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": "product_market_level",

                    "market_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                market_level_share_monthly
                            )
                        ),
                        "table": market_level_share_monthly,
                    },

                    "product_market_level": {
                        # Selected products across all markets.
                        "chart": build_product_market_chart(
                            product_market_share_chart_monthly,
                            period_key="months",
                        ),

                        # Complete table with all cuts.
                        "table": product_market_share_monthly,
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": "product_market_level",

                    "market_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_share_yearly
                            )
                        ),
                        "table": product_level_share_yearly,
                    },

                    "product_market_level": {
                        # Selected products across all markets.
                        "chart": build_product_market_chart(
                            product_market_share_chart_yearly,
                            period_key="years",
                        ),

                        # Complete table with all cuts.
                        "table": product_market_share_yearly,
                    },
                },
            },

            "market_volume": {
                "monthly": {
                    "view_options": view_options,
                    "selected_view": "product_market_level",

                    "market_level": {
                        "chart": build_monthly_chart(
                            exclude_overall_from_chart(
                                market_level_volume_monthly
                            )
                        ),
                        "table": market_level_volume_monthly,
                    },

                    "product_market_level": {
                        # Selected products across all markets.
                        "chart": build_product_market_chart(
                            product_market_volume_chart_monthly,
                            period_key="months",
                        ),

                        # Complete table with all cuts.
                        "table": product_market_volume_monthly,
                    },
                },

                "yearly": {
                    "view_options": view_options,
                    "selected_view": "product_market_level",

                    "market_level": {
                        "chart": build_yearly_chart(
                            exclude_overall_from_chart(
                                product_level_volume_yearly
                            )
                        ),
                        "table": product_level_volume_yearly,
                    },

                    "product_market_level": {
                        # Selected products across all markets.
                        "chart": build_product_market_chart(
                            product_market_volume_chart_yearly,
                            period_key="years",
                        ),

                        # Complete table with all cuts.
                        "table": product_market_volume_yearly,
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

def build_overall_impact_curve_configuration(tree):

    return {
        "products": list(tree["products"].keys()),

        "markets": list(tree["markets"].keys()),

        "impact_markets": ["Overall"],

        "forecast_start_date": (
            tree["months"][tree["forecast_start_index"]]
            if tree["forecast_start_index"] < len(tree["months"])
            else None
        ),

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "SCurve",
        ],

        "rows": [],
    }

def build_market_impact_curve_configuration(tree):

    return {
        "products": list(tree["products"].keys()),

        "markets": list(tree["markets"].keys()),

        "impact_markets": list(tree["markets"].keys()),

        "forecast_start_date": (
            tree["months"][tree["forecast_start_index"]]
            if tree["forecast_start_index"] < len(tree["months"])
            else None
        ),

        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "SCurve",
        ],

        "rows": [],
    }

def build_product_impact_curve_configuration(tree):
    forecast_start_index = tree["forecast_start_index"]

    forecast_start_date = (
        tree["months"][forecast_start_index]
        if forecast_start_index < len(tree["months"])
        else None
    )

    return {
        "products": list(tree["products"].keys()),
        "markets": list(tree["markets"].keys()),
        "impact_products": list(tree["products"].keys()),
        "forecast_start_date": forecast_start_date,
        "curve_types": [
            "Linear",
            "Exponential",
            "Logarithmic",
            "SCurve",
        ],
        "rows": [],
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

def build_product_level_rows(tree, metric):

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

    for product_name in sorted(tree["products"]):

        rows.append(
            {
                "label": product_name,
                "values": tree["products"][product_name][metric],
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

def build_market_product_rows(tree, metric):
    """
    Overall

        Retail
            Biktarvy
            Descovy
            Truvada

        Non-retail
            Biktarvy
            Descovy
            Truvada
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

        market = tree["markets"][market_name]

        market_row = {
            "label": market_name,
            "values": market[metric],
            "children": [],
        }

        product_totals = {}

        for source in market["sources"].values():

            for product_name, product in source["products"].items():

                if product_name not in product_totals:

                    product_totals[product_name] = [0] * len(product[metric])

                product_totals[product_name] = [

                    round(a + b, 2)

                    for a, b in zip(
                        product_totals[product_name],
                        product[metric],
                    )
                ]

        for product_name in sorted(product_totals):

            market_row["children"].append(
                {
                    "label": product_name,
                    "values": product_totals[product_name],
                }
            )

        rows.append(market_row)

    return rows

