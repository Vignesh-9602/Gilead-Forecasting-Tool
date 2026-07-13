from app.hiv_treat.services.response_builder_market_events import *

def build_overall_event(tree):
    """
    Build Overall Event from the calculation tree.
    """

    months = tree["months"]
    forecast_start_index = tree["forecast_start_index"]

    overall_volume = tree["overall"]["volume"]

    overall_share = [100] * len(months)

    # ----------------------------------------------------
    # Monthly Tables
    # ----------------------------------------------------

    market_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=[
            {
                "label": "Overall",
                "values": overall_share,
            }
        ],
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
    )

    # ----------------------------------------------------
    # Yearly Tables
    # ----------------------------------------------------

    market_share_yearly = build_yearly_table(
        market_share_monthly,
        aggregation="average",
    )

    market_volume_yearly = build_yearly_table(
        market_volume_monthly,
        aggregation="sum",
    )

    # ----------------------------------------------------
    # Response
    # ----------------------------------------------------

    return {

        "impact_curve_configuration": build_overall_impact_curve_configuration(tree),

        "metrics_views": {

            "market_share": {

                "monthly": {
                    "chart": build_monthly_chart(
                        market_share_monthly
                    ),
                    "table": market_share_monthly,
                },

                "yearly": {
                    "chart": build_yearly_chart(
                        market_share_yearly
                    ),
                    "table": market_share_yearly,
                },
            },

            "market_volume": {

                "monthly": {
                    "chart": build_monthly_chart(
                        market_volume_monthly
                    ),
                    "table": market_volume_monthly,
                },

                "yearly": {
                    "chart": build_yearly_chart(
                        market_volume_yearly
                    ),
                    "table": market_volume_yearly,
                },
            },
        }
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

def build_product_event(tree):
    """
    Build Product Event.

    Hierarchy:
        Overall
            Market
                Product
    """

    months = tree["months"]
    forecast_start_index = tree["forecast_start_index"]

    # ---------------------------------------
    # Monthly rows
    # ---------------------------------------

    share_rows = build_product_rows(
        tree,
        metric="share",
    )

    volume_rows = build_product_rows(
        tree,
        metric="volume",
    )

    # ---------------------------------------
    # Monthly tables
    # ---------------------------------------

    market_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=share_rows,
        hierarchy=True,
    )

    market_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=volume_rows,
        hierarchy=True,
    )

    # ---------------------------------------
    # Yearly tables
    # ---------------------------------------

    market_share_yearly = build_yearly_table(
        market_share_monthly,
        aggregation="average",
    )

    market_volume_yearly = build_yearly_table(
        market_volume_monthly,
        aggregation="sum",
    )

    # ---------------------------------------
    # Response
    # ---------------------------------------

    return {
        "impact_curve_configuration":
            build_product_impact_curve_configuration(tree),

        "metrics_views": {
            "market_share": {
                "monthly": {
                    "chart": build_monthly_chart(
                        market_share_monthly
                    ),
                    "table": market_share_monthly,
                },
                "yearly": {
                    "chart": build_yearly_chart(
                        market_share_yearly
                    ),
                    "table": market_share_yearly,
                },
            },

            "market_volume": {
                "monthly": {
                    "chart": build_monthly_chart(
                        market_volume_monthly
                    ),
                    "table": market_volume_monthly,
                },
                "yearly": {
                    "chart": build_yearly_chart(
                        market_volume_yearly
                    ),
                    "table": market_volume_yearly,
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

def build_market_event(tree):
    """
    Build Market Event.
    """

    months = tree["months"]
    forecast_start_index = tree["forecast_start_index"]


    # ---------------------------------------
    # Monthly Rows
    # ---------------------------------------

    share_rows = build_market_rows(
        tree,
        "share",
    )

    volume_rows = build_market_rows(
        tree,
        "volume",
    )

    # ---------------------------------------
    # Monthly Tables
    # ---------------------------------------

    market_share_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=share_rows,
        hierarchy=True,
    )

    market_volume_monthly = build_monthly_table(
        headers=months,
        forecast_start_index=forecast_start_index,
        rows=volume_rows,
        hierarchy=True,
    )

    # ---------------------------------------
    # Yearly Tables
    # ---------------------------------------

    market_share_yearly = build_yearly_table(
        market_share_monthly,
        aggregation="average",
    )

    market_volume_yearly = build_yearly_table(
        market_volume_monthly,
        aggregation="sum",
    )

    # ---------------------------------------
    # Response
    # ---------------------------------------

    return {

        "impact_curve_configuration": build_market_impact_curve_configuration(tree),

        "metrics_views": {

            "market_share": {

                "monthly": {
                    "chart": build_monthly_chart(
                        market_share_monthly
                    ),
                    "table": market_share_monthly,
                },

                "yearly": {
                    "chart": build_yearly_chart(
                        market_share_yearly
                    ),
                    "table": market_share_yearly,
                },
            },

            "market_volume": {

                "monthly": {
                    "chart": build_monthly_chart(
                        market_volume_monthly
                    ),
                    "table": market_volume_monthly,
                },

                "yearly": {
                    "chart": build_yearly_chart(
                        market_volume_yearly
                    ),
                    "table": market_volume_yearly,
                },
            },
        }
    }

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

