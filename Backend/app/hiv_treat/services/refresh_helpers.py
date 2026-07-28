from app.hiv_treat.services.chart_builder import *
import re
from copy import deepcopy

def round_market_volume_table(table):
    for row in table.get("rows", []):
        row["values"] = [
            round(float(value), 0)
            if value is not None
            else None
            for value in row.get("values", [])
        ]

        for child in row.get("children", []):
            child["values"] = [
                round(float(value), 0)
                if value is not None
                else None
                for value in child.get("values", [])
            ]

    return table

def round_all_market_volume_tables(
    market_analysis,
):
    sections = [
        "market_distribution",
        "product_distribution",
        "market_product",
        "product_market",
    ]

    for section_name in sections:
        section = market_analysis.get(section_name)

        if not section:
            continue

        market_volume = section.get("market_volume")

        if not market_volume:
            continue

        monthly = market_volume.get("monthly")

        if not monthly:
            continue

        table = monthly.get("table")

        if not table:
            continue

        round_market_volume_table(table)

    return market_analysis


def get_changed_indexes(
    original_values,
    submitted_values,
    tolerance=1e-9,
):
    if len(original_values) != len(submitted_values):
        raise ValueError(
            "Original and submitted value lengths do not match."
        )

    changed_indexes = []

    for index, (original, submitted) in enumerate(
        zip(original_values, submitted_values)
    ):
        if original is None and submitted is None:
            continue

        if original is None or submitted is None:
            changed_indexes.append(index)
            continue

        if abs(float(original) - float(submitted)) > tolerance:
            changed_indexes.append(index)

    return changed_indexes


def normalize_label(label):
    if label is None:
        return ""

    label = str(label).strip()

    # Removes suffixes such as:
    # Non-retail (Base) -> Non-retail
    # IQVIA (Base)      -> IQVIA
    label = re.sub(
        r"\s*\([^)]*\)\s*$",
        "",
        label,
    )

    return label.strip().lower()

def find_row_label(rows, label):
    target = normalize_label(label)

    for row in rows:
        if normalize_label(row.get("label")) == target:
            return row

    return None

def build_refresh_response(
    payload,
    market_analysis,
    factors,
    available_scenarios,
):

    return {
        "ta_name": payload.ta_name,
        "selected_filter": payload.selected_filter,

        "available_scenarios": available_scenarios,
        "active_scenario": payload.scenario_name,

        "scenarios": {
            payload.scenario_name: {
                "factors": factors,
                "market_analysis": market_analysis,
            }
        },
    }

def refresh_engine(
    payload,
    original_market_analysis=None,
):
    market_analysis = deepcopy(
        payload.market_analysis
    )

    if payload.selected_tab == "total_market_volume":

        market_analysis = recompute_from_total_market_volume(
            market_analysis,
            payload.selected_filter,
        )

    elif payload.selected_tab == "market_distribution":

        if original_market_analysis is None:
            raise ValueError(
                "original_market_analysis is required for "
                "market_distribution edits."
            )

        market_analysis = recompute_from_market_distribution(
            market_analysis=market_analysis,
            original_market_analysis=(
                original_market_analysis
            ),
            selected_metric=payload.selected_metric,
            edited_rows=payload.edited_rows or [],
            selected_filter=payload.selected_filter,
        )

    elif payload.selected_tab == "product_distribution":

        market_analysis = recompute_from_product_distribution(
            market_analysis,
            payload.selected_metric,
            payload.edited_rows or [],
            payload.selected_filter,
        )

    elif payload.selected_tab == "market_product":

        market_analysis = recompute_from_market_product(
            market_analysis,
            payload.selected_metric,
            payload.edited_rows or [],
            payload.selected_filter,
        )

    elif payload.selected_tab == "product_market":

        market_analysis = recompute_from_product_market(
            market_analysis,
            payload.selected_metric,
            payload.edited_rows or [],
            payload.selected_filter,
        )

    else:
        raise ValueError(
            f"Unsupported selected_tab: "
            f"{payload.selected_tab}"
        )

    return market_analysis

def is_overall_label(label):
    if not isinstance(label, str):
        return False

    normalized = label.strip().lower()

    return (
        normalized == "overall"
        or normalized.startswith("overall(")
        or normalized.startswith("overall (")
    )


def normalize_rows(rows):

    for row in rows or []:

        if is_overall_label(row.get("label")):
            row["label"] = "Overall"

        normalize_rows(
            row.get("children", [])
        )


def normalize_series(series_rows):

    for series in series_rows or []:

        if is_overall_label(series.get("label")):
            series["label"] = "Overall"

        normalize_series(
            series.get("children", [])
        )


def normalize_overall_labels(market_analysis):

    if not isinstance(market_analysis, dict):
        return market_analysis

    for section in market_analysis.values():

        if not isinstance(section, dict):
            continue

        for metric in section.values():

            if not isinstance(metric, dict):
                continue

            for period_name in ("monthly", "yearly"):

                period = metric.get(period_name)

                if not isinstance(period, dict):
                    continue

                table_rows = (
                    period
                    .get("table", {})
                    .get("rows", [])
                )

                chart_series = (
                    period
                    .get("chart", {})
                    .get("series", [])
                )

                normalize_rows(table_rows)
                normalize_series(chart_series)

    return market_analysis

def recompute_from_total_market_volume(
    market_analysis,
    selected_filter,
):

    print("selelcted",selected_filter)

    print(
        market_analysis["total_market_volume"]
        ["market_volume"]["monthly"]["table"]["rows"][0]["values"][0]
    )

    print("After apply:",
      market_analysis["total_market_volume"]["market_volume"]["monthly"]["table"]["rows"][0]["values"][0])

    build_total_market_volume_refresh(market_analysis,selected_filter)

    print("After build_total_market_volume:",
        market_analysis["total_market_volume"]["market_volume"]["monthly"]["table"]["rows"][0]["values"][0])

    build_market_distribution(market_analysis)

    print("After build_market_distribution:",
        market_analysis["market_distribution"]["market_volume"]["monthly"]["table"]["rows"][0]["values"][0])

    build_product_distribution(market_analysis)

    print("After build_product_distribution:",
        market_analysis["product_distribution"]["market_volume"]["monthly"]["table"]["rows"][0]["values"][0])

    build_market_product(market_analysis)

    print("After build_market_product:",
        market_analysis["market_product"]["market_volume"]["monthly"]["table"]["rows"][0]["values"][0])

    build_product_market(market_analysis)

    print("After build_product_market:",
        market_analysis["product_market"]["market_volume"]["monthly"]["table"]["rows"][0]["values"][0])
    
    rebuild_market_distribution_yearly(
    market_analysis,
    selected_filter,
    )

    rebuild_product_distribution_yearly(
    market_analysis,
    selected_filter,
    )

    rebuild_product_market_yearly(
    market_analysis,
    selected_filter,
    )

    rebuild_market_product_yearly(
    market_analysis,
    selected_filter,
    )

    return market_analysis

#market distribution
def filter_market_distribution_chart(
    market_analysis,
    selected_filter,
):
    if isinstance(selected_filter, dict):
        selected_markets = selected_filter.get(
            "markets",
            selected_filter.get(
                "market",
                [],
            ),
        )
    else:
        selected_markets = getattr(
            selected_filter,
            "markets",
            getattr(
                selected_filter,
                "market",
                [],
            ),
        )

    if isinstance(
        selected_markets,
        str,
    ):
        selected_markets = [
            selected_markets
        ]

    selected_market_keys = {
        normalize_chart_market_label(
            market
        )
        for market in (
            selected_markets or []
        )
        if market
    }

    if not selected_market_keys:
        return market_analysis

    section = market_analysis.get(
        "market_distribution",
        {},
    )

    for metric_data in section.values():
        if not isinstance(
            metric_data,
            dict,
        ):
            continue

        for period_name in (
            "monthly",
            "yearly",
        ):
            chart = (
                metric_data
                .get(period_name, {})
                .get("chart", {})
            )

            series = chart.get(
                "series",
                [],
            )

            if not isinstance(
                series,
                list,
            ):
                continue

            chart["series"] = [
                item
                for item in series
                if normalize_chart_market_label(
                    item.get(
                        "label",
                        item.get(
                            "name",
                            "",
                        ),
                    )
                ) in selected_market_keys
            ]

    return market_analysis


def normalize_chart_market_label(label):
    """
    Converts:
        Non-retail
        Non-retail (Base)
        Non-retail (test)

    into:
        non-retail
    """

    label = str(label or "").strip()

    label = re.sub(
        r"\s*\([^)]*\)\s*$",
        "",
        label,
    )

    return label.strip().lower()

def recompute_from_market_distribution(
    market_analysis,
    original_market_analysis,
    selected_metric,
    edited_rows,
    selected_filter,
):
    """
    Recompute market distribution and all dependent tabs.

    Rules:
        - Tables remain complete.
        - Market Distribution chart is filtered by selected market.
        - Product Distribution chart is filtered by selected product.
        - Channel-Product chart is filtered by selected market.
        - Product-Channel chart is filtered by selected product.
    """

    # ======================================================
    # 1. Recompute edited Market Distribution values
    # ======================================================

    if selected_metric == "market_volume":
        rebuild_market_distribution_from_market_volume_edit(
            market_analysis=market_analysis,
            original_market_analysis=original_market_analysis,
            edited_rows=edited_rows,
        )

        rebuild_market_distribution_share(
            market_analysis,
        )

    elif selected_metric == "market_share":
        rebuild_market_distribution_from_market_share_edit(
            market_analysis=market_analysis,
            original_market_analysis=original_market_analysis,
            edited_rows=edited_rows,
        )

        rebuild_market_distribution_volume(
            market_analysis,
        )

    else:
        raise ValueError(
            f"Unsupported selected_metric: {selected_metric}"
        )

    # ======================================================
    # 2. Recompute child source volumes
    # ======================================================

    rebuild_market_distribution_child_volumes(
        market_analysis,
    )

    # ======================================================
    # 3. Recompute dependent monthly tables
    # ======================================================

    build_product_distribution(
        market_analysis,
    )

    build_product_market(
        market_analysis,
    )

    build_market_product(
        market_analysis,
    )

    

    # ======================================================
    # 4. Round monthly market-volume tables
    # ======================================================

    round_all_market_volume_tables(
        market_analysis,
    )

    # ======================================================
    # 5. Rebuild all monthly charts
    #
    # market_product and product_market must use their
    # dedicated child-row chart builders inside this function.
    # ======================================================

    rebuild_all_monthly_charts(
        market_analysis,
    )

    # ======================================================
    # 6. Rebuild all yearly tables and charts
    # ======================================================

    rebuild_market_distribution_yearly(
        market_analysis,
        selected_filter,
    )

    rebuild_product_distribution_yearly(
        market_analysis,
        selected_filter,
    )

    

    rebuild_market_product_yearly(
        market_analysis,
        selected_filter,
    )

    import pprint

    table = (
        market_analysis["market_product"]
        ["market_volume"]
        ["yearly"]
        ["table"]
    )

    print("========== YEARLY MARKET PRODUCT ==========")
    pprint.pp(table)

    rebuild_product_market_yearly(
        market_analysis,
        selected_filter,
    )

    # ======================================================
    # 7. Apply chart filters last
    #
    # This must happen after both monthly and yearly chart
    # rebuilding. Otherwise a yearly rebuild can overwrite
    # the filtered series.
    # ======================================================

    filter_market_distribution_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    filter_product_distribution_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    

    filter_market_product_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    filter_product_market_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )
    

    return market_analysis

#product_distribution
def filter_product_distribution_chart(
    market_analysis,
    selected_filter,
):
    """
    Filter Product Distribution charts using selected products.

    The tables remain complete.
    """

    if isinstance(selected_filter, dict):
        selected_products = selected_filter.get(
            "products",
            selected_filter.get(
                "product",
                [],
            ),
        )
    else:
        selected_products = getattr(
            selected_filter,
            "products",
            getattr(
                selected_filter,
                "product",
                [],
            ),
        )

    if isinstance(
        selected_products,
        str,
    ):
        selected_products = [
            selected_products
        ]

    selected_product_keys = {
        normalize_chart_product_label(
            product
        )
        for product in (
            selected_products or []
        )
        if product
    }

    if not selected_product_keys:
        return market_analysis

    section = market_analysis.get(
        "product_distribution",
        {},
    )

    for metric_data in section.values():
        if not isinstance(
            metric_data,
            dict,
        ):
            continue

        for period_name in (
            "monthly",
            "yearly",
        ):
            chart = (
                metric_data
                .get(period_name, {})
                .get("chart", {})
            )

            series = chart.get(
                "series",
                [],
            )

            if not isinstance(
                series,
                list,
            ):
                continue

            chart["series"] = [
                item
                for item in series
                if normalize_chart_product_label(
                    item.get(
                        "label",
                        item.get(
                            "name",
                            "",
                        ),
                    )
                ) in selected_product_keys
            ]

    return market_analysis

def normalize_chart_product_label(label):
    """
    Examples:
        Biktarvy          -> biktarvy
        Biktarvy (Base)   -> biktarvy
        Biktarvy (test)   -> biktarvy
    """

    label = str(label or "").strip()

    if "(" in label:
        label = label.split("(", 1)[0]

    return label.strip().lower()

def recompute_from_product_distribution(
    market_analysis,
    selected_metric,
    edited_rows,
    selected_filter,
):
    if selected_metric == "market_volume":

        rebuild_product_distribution_from_market_volume_edit(
            market_analysis,
            edited_rows,
        )

    elif selected_metric == "market_share":

        rebuild_product_distribution_from_market_share_edit(
            market_analysis,
            edited_rows,
        )

    else:
        raise ValueError(
            f"Unsupported selected_metric: {selected_metric}"
        )

    build_market_product(
        market_analysis,
    )

    build_product_market(
        market_analysis,
    )

    rebuild_all_monthly_charts(
        market_analysis,
    )

    # Keep the full product-distribution table, but filter
    # the chart to the selected products.
    filter_product_distribution_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    rebuild_product_distribution_yearly(
        market_analysis,
        selected_filter,
    )

    rebuild_product_market_yearly(
        market_analysis,
        selected_filter,
    )

    rebuild_market_product_yearly(
        market_analysis,
        selected_filter,
    )

    # Yearly charts are rebuilt above, so filter again
    # after yearly recomputation.
    filter_product_distribution_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    return market_analysis

#market_product
def recompute_from_market_product(
    market_analysis,
    selected_metric,
    edited_rows,
    selected_filter,
):
    if selected_metric == "market_volume":

        rebuild_market_product_from_market_volume_edit(
            market_analysis,
            edited_rows,
        )

        rebuild_product_market_from_market_volume_edit(
            market_analysis,
        )

    elif selected_metric == "market_share":

        rebuild_market_product_from_market_share_edit(
            market_analysis,
            edited_rows,
        )

        rebuild_product_market_from_market_share_edit(
            market_analysis,
        )

    else:
        raise ValueError(
            f"Unsupported selected_metric: "
            f"{selected_metric}"
        )

    rebuild_all_monthly_charts(
        market_analysis,
    )

    # Filter Channel-Product monthly chart
    # by selected markets.
    filter_market_product_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    rebuild_market_product_yearly(
        market_analysis,
        selected_filter,
    )

    rebuild_product_market_yearly(
        market_analysis,
        selected_filter,
    )

    # Yearly rebuild may recreate the chart.
    filter_market_product_chart(
        market_analysis=market_analysis,
        selected_filter=selected_filter,
    )

    return market_analysis

def filter_market_product_chart(
    market_analysis,
    selected_filter,
):
    """
    Filters the Channel-Product chart by selected markets.

    Example:
        selected markets = ["Retail"]

    Keeps:
        Retail - Biktarvy
        Retail - Descovy
        Retail - Truvada

    The table remains complete.
    """

    if isinstance(selected_filter, dict):
        selected_markets = selected_filter.get(
            "markets",
            selected_filter.get(
                "market",
                [],
            ),
        )
    else:
        selected_markets = getattr(
            selected_filter,
            "markets",
            getattr(
                selected_filter,
                "market",
                [],
            ),
        )

    if isinstance(selected_markets, str):
        selected_markets = [selected_markets]

    selected_market_keys = {
        normalize_chart_market_label(market)
        for market in (selected_markets or [])
        if market
    }

    if not selected_market_keys:
        return market_analysis

    market_product = market_analysis.get(
        "market_product",
        {},
    )

    for metric_data in market_product.values():

        if not isinstance(metric_data, dict):
            continue

        for period_name in (
            "monthly",
            "yearly",
        ):
            chart = (
                metric_data
                .get(period_name, {})
                .get("chart", {})
            )

            series = chart.get(
                "series",
                [],
            )

            if not isinstance(series, list):
                continue

            chart["series"] = [
                item
                for item in series
                if extract_market_from_market_product_label(
                    item.get("label", "")
                ) in selected_market_keys
            ]

    return market_analysis

def extract_market_from_market_product_label(
    label,
):
    """
    Converts:

        Retail - Biktarvy
        Retail - Descovy (Base)
        Non-retail - Truvada (test)

    into:

        retail
        retail
        non-retail
    """

    label = str(label or "").strip()

    # Remove scenario suffix.
    if "(" in label:
        label = label.split("(", 1)[0].strip()

    if " - " not in label:
        return ""

    market, _ = label.split(
        " - ",
        1,
    )

    return normalize_chart_market_label(
        market
    )

def normalize_chart_market_label(label):
    label = str(label or "").strip()

    if "(" in label:
        label = label.split("(", 1)[0]

    return label.strip().lower()

#product_market
def recompute_from_product_market(
    market_analysis,
    selected_metric,
    edited_rows,
    selected_filter
):

    if selected_metric == "market_volume":

        rebuild_product_market_tab_from_market_volume_edit(
            market_analysis,
            edited_rows,
        )

    else:

        rebuild_product_market_tab_from_market_share_edit(
            market_analysis,
            edited_rows,
        )

    rebuild_all_monthly_charts(
        market_analysis,
    )

    rebuild_product_market_yearly(
    market_analysis,
    selected_filter,
    )

    rebuild_market_product_yearly(
    market_analysis,
    selected_filter,
    )

    return market_analysis

# def build_market_distribution(
#     market_analysis,
# ):

#     print("Building Market Distribution")

#     # Edited Total Market Volume
#     tmv_values = (
#         market_analysis["total_market_volume"]
#         ["market_volume"]
#         ["monthly"]
#         ["table"]
#         ["rows"][0]["values"]
#     )

#     # Market Distribution Volume rows
#     volume_rows = (
#         market_analysis["market_distribution"]
#         ["market_volume"]
#         ["monthly"]
#         ["table"]
#         ["rows"]
#     )

#     # Market Distribution Share rows
#     share_rows = (
#         market_analysis["market_distribution"]
#         ["market_share"]
#         ["monthly"]
#         ["table"]
#         ["rows"]
#     )


#         # Update Overall Market Distribution
#     volume_rows[0]["values"] = tmv_values.copy()
#     for row_index in range(1, len(volume_rows)):

#         share_values = share_rows[row_index]["values"]
#         volume_values = volume_rows[row_index]["values"]

#         for month_index in range(len(tmv_values)):

#             volume_values[month_index] = round(
#                 tmv_values[month_index]
#                 * share_values[month_index]
#                 / 100
#             )
#         # Recompute Non-retail children

#     non_retail_volume = volume_rows[2]["values"]

#     non_retail_children_volume = volume_rows[2]["children"]
#     non_retail_children_share = share_rows[2]["children"]

#     for child_index in range(len(non_retail_children_volume)):

#         child_volume = non_retail_children_volume[child_index]["values"]
#         child_share = non_retail_children_share[child_index]["values"]

#         for month_index in range(len(non_retail_volume)):

#             child_volume[month_index] = round(
#                 non_retail_volume[month_index]
#                 * child_share[month_index]
#                 / 100
#             )

#     # -------------------------
# # Recompute Market Shares
# # -------------------------

#     overall_volume = volume_rows[0]["values"]
#     overall_share = share_rows[0]["values"]

#     # Overall = 100%
#     for i in range(len(overall_share)):
#         overall_share[i] = 100

#     # Retail & Non-retail
#     for row_index in [1, 2]:

#         volume = volume_rows[row_index]["values"]
#         share = share_rows[row_index]["values"]

#         for month_index in range(len(volume)):

#             if overall_volume[month_index] == 0:
#                 share[month_index] = 0
#             else:
#                 share[month_index] = round(
#                     volume[month_index]
#                     / overall_volume[month_index]
#                     * 100,
#                     2,
#                 )
#     # Children share inside Non-retail

#     parent_volume = volume_rows[2]["values"]

#     children_volume = volume_rows[2]["children"]
#     children_share = share_rows[2]["children"]

#     for child_index in range(len(children_volume)):

#         volume = children_volume[child_index]["values"]
#         share = children_share[child_index]["values"]

#         for month_index in range(len(volume)):

#             if parent_volume[month_index] == 0:
#                 share[month_index] = 0
#             else:
#                 share[month_index] = round(
#                     volume[month_index]
#                     / parent_volume[month_index]
#                     * 100,
#                     2,
#                 )

#     print("Updated Overall :", volume_rows[0]["values"][:5])
#     print("TMV :", tmv_values[:5])
#     print("Overall :", volume_rows[0]["values"][:5])
#     print("Retail volume :", share_rows[1]["values"][:5])
#     print("Non-Retail volume :", share_rows[2]["values"][:5])
#     print(volume_values)
#     print(non_retail_children_volume[0]["values"][:5])
#     print("Retail Share :", share_rows[1]["values"][:5])
#     print("Non-retail Share :", share_rows[2]["values"][:5])
#     print("Kaiser Share :", share_rows[2]["children"][0]["values"][:5])

#     return market_analysis

def build_total_market_volume_refresh(market_analysis,selected_filter):

    # ==========================================================
    # Monthly Volume
    # ==========================================================

    total_volume_rows = (
        market_analysis["total_market_volume"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    overall = total_volume_rows[0]["values"]

    monthly = market_analysis["total_market_volume"]["market_volume"]["monthly"]

    monthly["chart"] = build_chart_from_table(
        monthly["table"],
        monthly["chart"],      # pass the existing chart
    )

    # ==========================================================
    # Monthly Share
    # ==========================================================

    total_share_rows = (
        market_analysis["total_market_volume"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    total_share_rows[0]["values"] = [100] * len(overall)

    monthly10 = market_analysis["total_market_volume"]["market_share"]["monthly"]

    monthly10["chart"] = build_chart_from_table(
        monthly10["table"],
        monthly10["chart"],      # pass the existing chart
    )

    # ==========================================================
    # Yearly Volume
    # ==========================================================

    

    month_labels = get_month_labels(
        selected_filter["start_date"],
        len(overall),
    )

    yearly_table = build_yearly_table(
        market_analysis["total_market_volume"]["market_volume"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["total_market_volume"]["market_volume"]["yearly"]["table"] = (
        yearly_table
    )

    market_analysis["total_market_volume"]["market_volume"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(yearly_table)
    )

    # ==========================================================
    # Yearly Share
    # ==========================================================

    yearly_share_table = build_yearly_table(
        market_analysis["total_market_volume"]["market_share"]["monthly"]["table"],
        month_labels,
    )

    # Total Market share is always 100%
    yearly_share_table["rows"][0]["values"] = [
        100
    ] * len(yearly_share_table["rows"][0]["values"])

    market_analysis["total_market_volume"]["market_share"]["yearly"]["table"] = (
        yearly_share_table
    )

    market_analysis["total_market_volume"]["market_share"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(yearly_share_table)
    )

    return market_analysis

def build_market_distribution(market_analysis):

    print("\n==============================")
    print("Building Market Distribution")
    print("==============================")

    rebuild_market_distribution_volume(market_analysis)

    rebuild_market_distribution_share(market_analysis)

    monthly = market_analysis["market_distribution"]["market_volume"]["monthly"]

    monthly["chart"] = build_chart_from_table(
        monthly["table"],
        monthly["chart"],      # pass the existing chart
    )

    monthly10 = market_analysis["market_distribution"]["market_share"]["monthly"]

    monthly10["chart"] = build_chart_from_table(
        monthly10["table"],
        monthly10["chart"],      # pass the existing chart
    )

    return market_analysis

def rebuild_market_distribution_volume(
    market_analysis,
):
    market_distribution = (
        market_analysis["market_distribution"]
    )

    total_volume_rows = (
        market_analysis["total_market_volume"]
        ["market_volume"]["monthly"]
        ["table"]["rows"]
    )

    market_share_rows = (
        market_distribution["market_share"]
        ["monthly"]["table"]["rows"]
    )

    market_volume_rows = (
        market_distribution["market_volume"]
        ["monthly"]["table"]["rows"]
    )

    overall_row = find_row(
        total_volume_rows,
        "Overall",
    )

    if not overall_row and total_volume_rows:
        overall_row = total_volume_rows[0]

    if not overall_row:
        raise ValueError(
            "Overall market volume row not found"
        )

    total_values = overall_row.get(
        "values",
        [],
    )

    for share_row in market_share_rows:

        label = normalize_label(
            share_row.get("label")
        )

        if label == "overall":
            continue

        volume_row = find_row(
            market_volume_rows,
            share_row.get("label"),
        )

        if not volume_row:
            continue

        share_values = share_row.get(
            "values",
            [],
        )

        recalculated_values = []

        for total_value, share_value in zip(
            total_values,
            share_values,
        ):
            if (
                total_value is None
                or share_value is None
            ):
                recalculated_values.append(None)
                continue

            volume = (
                float(total_value)
                * float(share_value)
                / 100
            )

            recalculated_values.append(volume)

        volume_row["values"] = recalculated_values

    return market_analysis

def rebuild_market_distribution_share(market_analysis):

    print("\n--- Rebuilding Market Distribution Share ---")

    volume_rows = (
        market_analysis["market_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    share_rows = (
        market_analysis["market_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    overall_volume = volume_rows[0]["values"]

    # -----------------------------
    # Overall
    # -----------------------------
    for month_index in range(len(overall_volume)):
        share_rows[0]["values"][month_index] = 100

    # -----------------------------
    # Retail & Non-retail
    # -----------------------------
    for row_index in [1, 2]:

        for month_index in range(len(overall_volume)):

            if overall_volume[month_index] == 0:
                share_rows[row_index]["values"][month_index] = 0
            else:
                share_rows[row_index]["values"][month_index] = round(
                    volume_rows[row_index]["values"][month_index]
                    / overall_volume[month_index]
                    * 100,
                    2,
                )

    # -----------------------------
    # Children
    # -----------------------------
    parent_volume = volume_rows[2]["values"]

    children_volume = volume_rows[2]["children"]
    children_share = share_rows[2]["children"]

    for child_index in range(len(children_volume)):

        for month_index in range(len(parent_volume)):

            if parent_volume[month_index] == 0:
                children_share[child_index]["values"][month_index] = 0
            else:
                children_share[child_index]["values"][month_index] = round(
                    children_volume[child_index]["values"][month_index]
                    / parent_volume[month_index]
                    * 100,
                    2,
                )

    # -----------------------------
    # Testing
    # -----------------------------
    print("Overall Share :", share_rows[0]["values"][:5])
    print("Retail Share :", share_rows[1]["values"][:5])
    print("Non-retail Share :", share_rows[2]["values"][:5])

    print("Kaiser Share :", children_share[0]["values"][:5])
    print("IQVIA Share :", children_share[1]["values"][:5])
    print("ADAP Share :", children_share[2]["values"][:5])
    print("Federal Share :", children_share[3]["values"][:5])

def build_product_distribution(market_analysis):

    print("\n==============================")
    print("Building Product Distribution")
    print("==============================")

    rebuild_product_distribution_volume(market_analysis)

    rebuild_product_distribution_share(market_analysis)
    
    monthly = market_analysis["product_distribution"]["market_volume"]["monthly"]

    monthly["chart"] = build_chart_from_table(
        monthly["table"],
        monthly["chart"],      # pass the existing chart
    )

    monthly10 = market_analysis["product_distribution"]["market_share"]["monthly"]

    monthly10["chart"] = build_chart_from_table(
        monthly10["table"],
        monthly10["chart"],      # pass the existing chart
    )

    return market_analysis

def rebuild_product_distribution_volume(market_analysis):

    print("\n--- Rebuilding Product Distribution Volume ---")

    # Parent = Overall from Market Distribution
    parent_values = (
        market_analysis["market_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"][0]["values"]
    )

    volume_rows = (
        market_analysis["product_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    share_rows = (
        market_analysis["product_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    # -------------------------
    # Overall
    # -------------------------
    volume_rows[0]["values"] = parent_values.copy()

    # -------------------------
    # Products
    # -------------------------
    for row_index in range(1, len(volume_rows)):

        volume_values = volume_rows[row_index]["values"]
        share_values = share_rows[row_index]["values"]

        for month_index in range(len(parent_values)):

            volume_values[month_index] = round(
                parent_values[month_index]
                * share_values[month_index]
                / 100
            )

    # -------------------------
    # Testing
    # -------------------------
    print("Overall :", volume_rows[0]["values"][:5])

    for row in volume_rows[1:]:
        print(row["label"], ":", row["values"][:5])

def rebuild_product_distribution_share(market_analysis):

    print("\n--- Rebuilding Product Distribution Share ---")

    volume_rows = (
        market_analysis["product_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    share_rows = (
        market_analysis["product_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    overall_values = volume_rows[0]["values"]

    # -------------------------
    # Overall
    # -------------------------
    for month_index in range(len(overall_values)):
        share_rows[0]["values"][month_index] = 100

    # -------------------------
    # Products
    # -------------------------
    for row_index in range(1, len(volume_rows)):

        volume_values = volume_rows[row_index]["values"]
        share_values = share_rows[row_index]["values"]

        for month_index in range(len(overall_values)):

            if overall_values[month_index] == 0:
                share_values[month_index] = 0
            else:
                share_values[month_index] = round(
                    volume_values[month_index]
                    / overall_values[month_index]
                    * 100,
                    2,
                )

    # -------------------------
    # Testing
    # -------------------------
    print("Overall Share :", share_rows[0]["values"][:5])

    for row in share_rows[1:]:
        print(row["label"], ":", row["values"][:5])

def build_market_product(market_analysis):

    print("\n==============================")
    print("Building Market → Product")
    print("==============================")

    rebuild_market_product_volume(
        market_analysis
    )

    rebuild_market_product_share(
        market_analysis
    )

    monthly = market_analysis["market_product"]["market_volume"]["monthly"]

    monthly["chart"] = build_chart_from_table(
        monthly["table"],
        monthly["chart"],      # pass the existing chart
    )

    monthly10 = market_analysis["market_product"]["market_share"]["monthly"]

    monthly10["chart"] = build_chart_from_table(
        monthly10["table"],
        monthly10["chart"],      # pass the existing chart
    )

    return market_analysis

def rebuild_market_product_volume(market_analysis):

    print("\n--- Rebuilding Market → Product Volume ---")

    market_rows = (
        market_analysis["market_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    product_share_rows = (
        market_analysis["product_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    market_product_rows = (
        market_analysis["market_product"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    retail_row = find_row(
        market_rows,
        "Retail",
    )

    non_retail_row = find_row(
        market_rows,
        "Non-retail",
    )

    if retail_row is None:
        raise ValueError(
            "Retail row is missing from market distribution."
        )

    if non_retail_row is None:
        raise ValueError(
            "Non-retail row is missing from market distribution."
        )

    market_values_map = {
        "Retail": retail_row["values"],
        "Non-retail": non_retail_row["values"],
    }

    product_share_map = {
        row.get("label"): row.get("values", [])
        for row in product_share_rows
        if row.get("label") != "Overall"
    }

    print("Market-product row labels:")

    for row in market_product_rows:
        print(row.get("label"))

    for row in market_product_rows:

        label = row.get("label", "")

        if " - " not in label:
            continue

        market_name, product_name = label.split(
            " - ",
            1,
        )

        market_values = market_values_map.get(
            market_name
        )

        product_shares = product_share_map.get(
            product_name
        )

        if market_values is None:
            continue

        if product_shares is None:
            continue

        row_values = row.get("values", [])

        month_count = min(
            len(market_values),
            len(product_shares),
            len(row_values),
        )

        for month_index in range(month_count):

            row_values[month_index] = round(
                market_values[month_index]
                * product_shares[month_index]
                / 100
            )

    return market_analysis

def rebuild_market_product_share(market_analysis):

    print("\n--- Rebuilding Market → Product Share ---")

    volume_rows = (
        market_analysis["market_product"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    share_rows = (
        market_analysis["market_product"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    for market_index in range(len(volume_rows)):

        parent_volume = volume_rows[market_index]["values"]

        for child_index in range(len(volume_rows[market_index]["children"])):

            child_volume = (
                volume_rows[market_index]
                ["children"][child_index]
                ["values"]
            )

            child_share = (
                share_rows[market_index]
                ["children"][child_index]
                ["values"]
            )

            for month_index in range(len(parent_volume)):

                if parent_volume[month_index] == 0:
                    child_share[month_index] = 0
                else:
                    child_share[month_index] = round(
                        child_volume[month_index]
                        / parent_volume[month_index]
                        * 100,
                        2,
                    )

    # ----------------------------
    # Testing
    # ----------------------------

    print("Retail Shares")

    for child in share_rows[0]["children"]:
        print(child["label"], child["values"][:5])

    print()

    print("Non-retail Shares")

    for child in share_rows[1]["children"]:
        print(child["label"], child["values"][:5])

def build_product_market(market_analysis):

    rebuild_product_market_volume(market_analysis)
    rebuild_product_market_share(market_analysis)

    monthly = market_analysis["product_market"]["market_volume"]["monthly"]

    monthly["chart"] = build_chart_from_table(
        monthly["table"],
        monthly["chart"],      # pass the existing chart
    )

    monthly10 = market_analysis["product_market"]["market_share"]["monthly"]

    monthly10["chart"] = build_chart_from_table(
        monthly10["table"],
        monthly10["chart"],      # pass the existing chart
    )

    return market_analysis

def rebuild_product_market_volume(market_analysis):

    # Overall product volumes
    overall_rows = (
        market_analysis["product_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    # Product Market volumes
    pm_rows = (
        market_analysis["product_market"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    # Product Market shares
    share_rows = (
        market_analysis["product_market"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    for product_index in range(len(pm_rows)):

        overall = overall_rows[product_index + 1]["values"]

        retail_share = share_rows[product_index]["children"][0]["values"]
        non_retail_share = share_rows[product_index]["children"][1]["values"]

        retail_values = []
        non_retail_values = []

        for month in range(len(overall)):

            retail = round(
                overall[month] * retail_share[month] / 100
            )

            non_retail = overall[month] - retail

            retail_values.append(retail)
            non_retail_values.append(non_retail)

        pm_rows[product_index]["values"] = overall.copy()

        pm_rows[product_index]["children"][0]["values"] = retail_values
        pm_rows[product_index]["children"][1]["values"] = non_retail_values

def rebuild_product_market_share(market_analysis):

    print("\n--- Rebuilding Product → Market Share ---")

    volume_rows = (
        market_analysis["product_market"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    share_rows = (
        market_analysis["product_market"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    for product_index in range(len(volume_rows)):

        parent_values = volume_rows[product_index]["values"]

        volume_children = volume_rows[product_index]["children"]
        share_children = share_rows[product_index]["children"]

        for child_index in range(len(volume_children)):

            child_values = volume_children[child_index]["values"]
            share_values = share_children[child_index]["values"]

            for month_index in range(len(parent_values)):

                if parent_values[month_index] == 0:
                    share_values[month_index] = 0
                else:
                    share_values[month_index] = round(
                        child_values[month_index]
                        / parent_values[month_index]
                        * 100,
                        2,
                    )

    # -------------------------
    # Testing
    # -------------------------

    for row in share_rows:

        print(row["label"])

        for child in row["children"]:
            print("   ", child["label"], child["values"][:5])

def find_row(rows, label):
    return next(
        (
            row
            for row in rows
            if row.get("label") == label
        ),
        None,
    )


def get_edited_labels(edited_rows):
    labels = set()

    for row in edited_rows or []:
        if isinstance(row, str):
            labels.add(row)
        elif isinstance(row, dict) and row.get("label"):
            labels.add(row["label"])

    return labels

def rebuild_market_distribution_from_market_volume_edit(
    market_analysis,
    edited_rows,
):
    print("\n--- Rebuilding Market Distribution (Volume Edit) ---")

    edited_labels = get_edited_labels(edited_rows)

    volume_rows = (
        market_analysis["market_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    share_rows = (
        market_analysis["market_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    overall_volume_row = find_row(volume_rows, "Overall")
    retail_volume_row = find_row(volume_rows, "Retail")
    non_retail_volume_row = find_row(volume_rows, "Non-retail")

    non_retail_share_row = find_row(share_rows, "Non-retail")

    if not overall_volume_row:
        raise ValueError(
            "Overall row is missing from market volume rows."
        )

    if not retail_volume_row:
        raise ValueError(
            "Retail row is missing from market volume rows."
        )

    if not non_retail_volume_row:
        raise ValueError(
            "Non-retail row is missing from market volume rows."
        )

    if not non_retail_share_row:
        raise ValueError(
            "Non-retail row is missing from market share rows."
        )

    overall = overall_volume_row["values"]
    retail = retail_volume_row["values"]
    non_retail = non_retail_volume_row["values"]

    children_volume = non_retail_volume_row.get("children", [])
    children_share = non_retail_share_row.get("children", [])

    # --------------------------------------------------
    # Retail edited
    # --------------------------------------------------

    if "Retail" in edited_labels:

        for month_index in range(len(overall)):
            non_retail[month_index] = (
                overall[month_index]
                - retail[month_index]
            )

    # --------------------------------------------------
    # Non-retail edited
    # --------------------------------------------------

    elif "Non-retail" in edited_labels:

        for month_index in range(len(overall)):
            retail[month_index] = (
                overall[month_index]
                - non_retail[month_index]
            )

    # --------------------------------------------------
    # Non-retail child edited
    # --------------------------------------------------

    elif edited_labels.intersection(
        {"Kaiser", "IQVIA", "ADAP", "Federal"}
    ):

        if not children_volume:
            raise ValueError(
                "Non-retail children are missing from "
                "market volume rows."
            )

        for month_index in range(len(overall)):

            non_retail[month_index] = sum(
                child["values"][month_index]
                for child in children_volume
            )

            retail[month_index] = (
                overall[month_index]
                - non_retail[month_index]
            )

    # --------------------------------------------------
    # Rebuild children only if parent changed
    # --------------------------------------------------

    if (
        "Retail" in edited_labels
        or "Non-retail" in edited_labels
    ):

        share_by_label = {
            child.get("label"): child
            for child in children_share
        }

        for child_volume in children_volume:

            child_label = child_volume.get("label")
            child_share_row = share_by_label.get(child_label)

            if not child_share_row:
                continue

            child_values = child_volume["values"]
            child_shares = child_share_row["values"]

            for month_index in range(len(non_retail)):

                child_values[month_index] = round(
                    non_retail[month_index]
                    * child_shares[month_index]
                    / 100
                )

    print("Overall :", overall[:5])
    print("Retail :", retail[:5])
    print("Non-retail :", non_retail[:5])

    return market_analysis

def rebuild_market_distribution_from_market_share_edit(
    market_analysis,
    original_market_analysis,
    edited_rows,
):
    submitted_rows = (
        market_analysis["market_distribution"]
        ["market_share"]["monthly"]
        ["table"]["rows"]
    )

    original_rows = (
        original_market_analysis["market_distribution"]
        ["market_share"]["monthly"]
        ["table"]["rows"]
    )

    submitted_overall = find_row_label(
        submitted_rows,
        "Overall",
    )

    original_overall = find_row_label(
        original_rows,
        "Overall",
    )

    if submitted_overall is None:
        raise ValueError(
            "Submitted Overall row was not found."
        )

    if original_overall is None:
        raise ValueError(
            "Original Overall row was not found."
        )

    for edited_label in edited_rows:

        # --------------------------------------------------
        # 1. Check whether the edited row is a top-level row
        #    such as Retail or Non-retail.
        # --------------------------------------------------
        submitted_top_level = find_row_label(
            submitted_rows,
            edited_label,
        )

        original_top_level = find_row_label(
            original_rows,
            edited_label,
        )

        if (
            submitted_top_level is not None
            and submitted_top_level is not submitted_overall
        ):
            if original_top_level is None:
                raise ValueError(
                    f"Original edited row not found: "
                    f"{edited_label}"
                )

            changed_indexes = get_changed_indexes(
                original_values=original_top_level.get(
                    "values",
                    [],
                ),
                submitted_values=submitted_top_level.get(
                    "values",
                    [],
                ),
            )

            if not changed_indexes:
                continue

            market_rows = [
                row
                for row in submitted_rows
                if str(
                    row.get("label", "")
                ).strip().lower()
                in {
                    "retail",
                    "non-retail",
                }
            ]

            logical_overall_parent = {
                "label": submitted_overall.get(
                    "label",
                    "Overall",
                ),
                "values": submitted_overall.get(
                    "values",
                    [],
                ),
                "children": market_rows,
            }

            # 1. Keep the edited market fixed and recalculate
            #    the other top-level market.
            #
            #    Non-retail = 90
            #    Retail = 10
            normalize_children_to_parent(
                parent_row=logical_overall_parent,
                edited_child=submitted_top_level,
                edited_indexes=changed_indexes,
            )

            # 2. Scale the edited market's children so they
            #    add up to the new market value.
            #
            #    IQVIA + Kaiser + ADAP + Federal = 90
            normalize_all_children_to_parent(
                parent_row=submitted_top_level,
                edited_indexes=changed_indexes,
            )

            continue

        # --------------------------------------------------
        # 2. Otherwise search inside market children.
        #    Example: IQVIA, Kaiser, ADAP, Federal.
        # --------------------------------------------------
        submitted_parent = None
        submitted_child = None
        original_child = None

        for parent_row in submitted_rows:
            child = find_row_label(
                parent_row.get("children", []),
                edited_label,
            )

            if child is not None:
                submitted_parent = parent_row
                submitted_child = child
                break

        for parent_row in original_rows:
            child = find_row_label(
                parent_row.get("children", []),
                edited_label,
            )

            if child is not None:
                original_child = child
                break

        if submitted_child is None:
            raise ValueError(
                f"Submitted edited row not found: "
                f"{edited_label}"
            )

        if original_child is None:
            raise ValueError(
                f"Original edited row not found: "
                f"{edited_label}"
            )

        changed_indexes = get_changed_indexes(
            original_values=original_child.get(
                "values",
                [],
            ),
            submitted_values=submitted_child.get(
                "values",
                [],
            ),
        )

        if not changed_indexes:
            continue

        normalize_children_to_parent(
            parent_row=submitted_parent,
            edited_child=submitted_child,
            edited_indexes=changed_indexes,
        )

    return market_analysis

from app.hiv_treat.services.chart_builder import build_chart_from_table

#charts rebuild
def rebuild_all_monthly_charts(
    market_analysis,
):
    for section_name, section in (
        market_analysis.items()
    ):
        if not isinstance(section, dict):
            continue

        for metric in (
            "market_volume",
            "market_share",
        ):
            if metric not in section:
                continue

            metric_data = section[metric]

            if "monthly" not in metric_data:
                continue

            monthly = metric_data["monthly"]

            if "table" not in monthly:
                continue

            existing_chart = monthly.get(
                "chart",
                {},
            )

            if section_name == "market_product":
                monthly["chart"] = (
                    build_market_product_chart_from_table(
                        table=monthly["table"],
                        existing_chart=existing_chart,
                    )
                )

            elif section_name == "product_market":
                monthly["chart"] = (
                    build_product_market_chart_from_table(
                        table=monthly["table"],
                        existing_chart=existing_chart,
                    )
                )

            else:
                monthly["chart"] = build_chart_from_table(
                    monthly["table"],
                    existing_chart,
                )

    return market_analysis

def build_market_product_chart_from_table(
    table,
    existing_chart,
):
    """
    Builds Channel-Product chart series.

    Table:
        Retail
            Biktarvy
            Descovy
            Truvada

        Non-retail
            Biktarvy
            Descovy
            Truvada

    Chart:
        Retail - Biktarvy
        Retail - Descovy
        Retail - Truvada
        Non-retail - Biktarvy
        Non-retail - Descovy
        Non-retail - Truvada
    """

    forecast_start_index = existing_chart.get(
        "forecast_start_index",
        0,
    )

    series = []

    for market_row in table.get("rows", []):
        market_label = market_row.get(
            "label",
            "",
        )

        if normalize_row_label(
            market_label
        ) == "overall":
            continue

        for product_row in market_row.get(
            "children",
            [],
        ):
            product_label = product_row.get(
                "label",
                "",
            )

            values = product_row.get(
                "values",
                [],
            )

            history = values[
                :forecast_start_index
            ]

            forecast = values[
                forecast_start_index:
            ]

            series.append(
                {
                    "label": (
                        f"{market_label} - "
                        f"{product_label}"
                    ),
                    "history": history,
                    "forecast": forecast,
                }
            )

    return {
        **existing_chart,
        "series": series,
    }

def build_product_market_chart_from_table(
    table,
    existing_chart,
):
    """
    Builds Product-Channel chart series.

    Table:
        Biktarvy
            Retail
            Non-retail

    Chart:
        Biktarvy - Retail
        Biktarvy - Non-retail
    """

    forecast_start_index = existing_chart.get(
        "forecast_start_index",
        0,
    )

    series = []

    for product_row in table.get("rows", []):
        product_label = product_row.get(
            "label",
            "",
        )

        if normalize_row_label(
            product_label
        ) == "overall":
            continue

        for market_row in product_row.get(
            "children",
            [],
        ):
            market_label = market_row.get(
                "label",
                "",
            )

            values = market_row.get(
                "values",
                [],
            )

            history = values[
                :forecast_start_index
            ]

            forecast = values[
                forecast_start_index:
            ]

            series.append(
                {
                    "label": (
                        f"{product_label} - "
                        f"{market_label}"
                    ),
                    "history": history,
                    "forecast": forecast,
                }
            )

    return {
        **existing_chart,
        "series": series,
    }

def rebuild_market_distribution_child_volumes(
    market_analysis,
):
    """
    Recalculate child/source volumes.

    Child shares are stored as overall-market percentages.

    Example:

        Overall volume = 1000
        Non-retail share = 80%
        IQVIA share = 30%

        Non-retail volume = 1000 * 80 / 100 = 800
        IQVIA volume = 1000 * 30 / 100 = 300

    Children must sum to the parent volume because their shares
    sum to the parent share.
    """

    market_distribution = (
        market_analysis["market_distribution"]
    )

    total_volume_rows = (
        market_analysis["total_market_volume"]
        ["market_volume"]["monthly"]
        ["table"]["rows"]
    )

    volume_rows = (
        market_distribution["market_volume"]
        ["monthly"]["table"]["rows"]
    )

    share_rows = (
        market_distribution["market_share"]
        ["monthly"]["table"]["rows"]
    )

    overall_row = find_row(
        total_volume_rows,
        "Overall",
    )

    if not overall_row and total_volume_rows:
        overall_row = total_volume_rows[0]

    if not overall_row:
        raise ValueError(
            "Overall market volume row not found."
        )

    total_values = overall_row.get("values", [])

    for volume_parent in volume_rows:
        parent_label = normalize_label(
            volume_parent.get("label")
        )

        if parent_label == "overall":
            continue

        volume_children = volume_parent.get(
            "children",
            [],
        )

        if not volume_children:
            continue

        share_parent = find_row_label(
            share_rows,
            volume_parent.get("label"),
        )

        if not share_parent:
            continue

        share_children = share_parent.get(
            "children",
            [],
        )

        for volume_child in volume_children:
            share_child = find_row_label(
                share_children,
                volume_child.get("label"),
            )

            if not share_child:
                continue

            child_shares = share_child.get(
                "values",
                [],
            )

            recalculated_values = []

            for total_value, child_share in zip(
                total_values,
                child_shares,
            ):
                if (
                    total_value is None
                    or child_share is None
                ):
                    recalculated_values.append(None)
                    continue

                child_volume = round(
                    float(total_value)
                    * float(child_share)
                    / 100,
                    0,
                )

                recalculated_values.append(
                    child_volume
                )

            volume_child["values"] = (
                recalculated_values
            )

    return market_analysis

def rebuild_market_distribution_child_shares(
    market_analysis,
):
    """
    Convert child shares from parent-level percentages into
    overall-market percentages.

    Example:
        Non-retail = 80%
        IQVIA internal share = 21.27%

        IQVIA overall share = 80 * 21.27 / 100
    """

    rows = (
        market_analysis["market_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    for parent_row in rows:
        parent_label = normalize_label(
            parent_row.get("label")
        )

        if parent_label == "overall":
            continue

        children = parent_row.get("children", [])

        if not children:
            continue

        parent_values = parent_row.get("values", [])

        for child in children:
            # Preserve the source's original internal split.
            internal_values = child.get(
                "_internal_share_values"
            )

            if internal_values is None:
                internal_values = list(
                    child.get("values", [])
                )

                child["_internal_share_values"] = (
                    internal_values
                )

            child["values"] = [
                (
                    float(parent_share)
                    * float(internal_share)
                    / 100
                )
                if (
                    parent_share is not None
                    and internal_share is not None
                )
                else None
                for parent_share, internal_share in zip(
                    parent_values,
                    internal_values,
                )
            ]

    return market_analysis

def normalize_children_to_parent(
    parent_row,
    edited_child,
    edited_indexes,
):
    """
    Keeps the edited child fixed.

    Redistributes the remaining parent share proportionally
    across the other children only for the edited months.

    All values are rounded to 2 decimal places.

    For every edited month:
        sum(children) == parent value
    """

    children = parent_row.get("children", [])
    parent_values = parent_row.get("values", [])
    edited_values = edited_child.get("values", [])

    siblings = [
        child
        for child in children
        if child is not edited_child
    ]

    if len(parent_values) != len(edited_values):
        raise ValueError(
            f"Parent and edited child value lengths do not match "
            f"for {edited_child.get('label')}."
        )

    for index in edited_indexes:
        if index < 0 or index >= len(parent_values):
            raise ValueError(
                f"Invalid edited index {index} for "
                f"{edited_child.get('label')}."
            )

        parent_value = parent_values[index]
        edited_value = edited_values[index]

        if parent_value is None or edited_value is None:
            continue

        parent_value = round(float(parent_value), 2)
        edited_value = round(float(edited_value), 2)

        if edited_value < 0:
            raise ValueError(
                f"{edited_child.get('label')} cannot be negative."
            )

        if edited_value > parent_value:
            raise ValueError(
                f"{edited_child.get('label')} value "
                f"{edited_value} cannot exceed parent "
                f"{parent_row.get('label')} value "
                f"{parent_value}."
            )

        # Keep the edited cell fixed.
        edited_child["values"][index] = edited_value

        remaining_value = round(
            parent_value - edited_value,
            2,
        )

        if not siblings:
            if abs(remaining_value) > 0.01:
                raise ValueError(
                    f"{edited_child.get('label')} must equal "
                    f"its parent value."
                )

            continue

        sibling_total = sum(
            float(
                sibling.get("values", [])[index] or 0
            )
            for sibling in siblings
        )

        if sibling_total <= 0:
            equal_value = round(
                remaining_value / len(siblings),
                2,
            )

            for sibling in siblings:
                sibling["values"][index] = equal_value

        else:
            for sibling in siblings:
                old_value = float(
                    sibling.get("values", [])[index] or 0
                )

                recalculated_value = (
                    old_value
                    / sibling_total
                    * remaining_value
                )

                sibling["values"][index] = round(
                    recalculated_value,
                    2,
                )

        # Correct rounding difference using the final sibling.
        current_sibling_total = round(
            sum(
                float(sibling["values"][index])
                for sibling in siblings
            ),
            2,
        )

        rounding_difference = round(
            remaining_value - current_sibling_total,
            2,
        )

        siblings[-1]["values"][index] = round(
            float(siblings[-1]["values"][index])
            + rounding_difference,
            2,
        )

        # Final safety correction.
        final_children_total = round(
            float(edited_child["values"][index])
            + sum(
                float(sibling["values"][index])
                for sibling in siblings
            ),
            2,
        )

        final_difference = round(
            parent_value - final_children_total,
            2,
        )

        if final_difference != 0:
            siblings[-1]["values"][index] = round(
                float(siblings[-1]["values"][index])
                + final_difference,
                2,
            )

    return parent_row

def normalize_all_children_to_parent(
    parent_row,
    edited_indexes,
):
    """
    Redistributes all children proportionally so their total
    equals the parent value for the specified month indexes.

    Example:
        Old parent = 80
        Children = [30, 20, 20, 10]

        New parent = 90
        Children = [33.75, 22.50, 22.50, 11.25]
    """

    children = parent_row.get("children", [])
    parent_values = parent_row.get("values", [])

    if not children:
        return parent_row

    for index in edited_indexes:
        if index < 0 or index >= len(parent_values):
            raise ValueError(
                f"Invalid edited index {index} for "
                f"{parent_row.get('label')}."
            )

        parent_value = parent_values[index]

        if parent_value is None:
            continue

        parent_value = round(
            float(parent_value),
            2,
        )

        if parent_value < 0:
            raise ValueError(
                f"{parent_row.get('label')} cannot be negative."
            )

        child_total = 0.0

        for child in children:
            child_values = child.get("values", [])

            if index >= len(child_values):
                raise ValueError(
                    f"Child value length does not match parent "
                    f"for {child.get('label')}."
                )

            child_total += float(
                child_values[index] or 0
            )

        # When all existing child values are zero,
        # distribute the parent equally.
        if child_total <= 0:
            equal_value = round(
                parent_value / len(children),
                2,
            )

            for child in children:
                child["values"][index] = equal_value

        else:
            for child in children:
                old_value = float(
                    child["values"][index] or 0
                )

                recalculated_value = (
                    old_value
                    / child_total
                    * parent_value
                )

                child["values"][index] = round(
                    recalculated_value,
                    2,
                )

        # Correct rounding difference using the last child.
        current_total = round(
            sum(
                float(child["values"][index])
                for child in children
            ),
            2,
        )

        rounding_difference = round(
            parent_value - current_total,
            2,
        )

        children[-1]["values"][index] = round(
            float(children[-1]["values"][index])
            + rounding_difference,
            2,
        )

        # Final validation.
        final_total = round(
            sum(
                float(child["values"][index])
                for child in children
            ),
            2,
        )

        if final_total != parent_value:
            final_difference = round(
                parent_value - final_total,
                2,
            )

            children[-1]["values"][index] = round(
                float(children[-1]["values"][index])
                + final_difference,
                2,
            )

    return parent_row

#product distribution rebuild
def rebuild_product_distribution_from_market_volume_edit(
    market_analysis,
    edited_rows,
):

    print("\n--- Rebuilding Product Distribution (Volume Edit) ---")

    volume_rows = (
        market_analysis["product_distribution"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    overall = volume_rows[0]["values"]
    product_rows = volume_rows[1:]

    months = len(overall)

    # ------------------------------------------------------
    # Map label -> row index
    # ------------------------------------------------------

    row_map = {
        row["label"]: idx
        for idx, row in enumerate(product_rows)
    }

    edited_indices = [
        row_map[label]
        for label in edited_rows
        if label in row_map
    ]

    remaining_indices = [
        i
        for i in range(len(product_rows))
        if i not in edited_indices
    ]

    # ------------------------------------------------------
    # Recompute month by month
    # ------------------------------------------------------

    for m in range(months):

        # Sum of edited products
        edited_total = sum(
            product_rows[i]["values"][m]
            for i in edited_indices
        )

        target_remaining = overall[m] - edited_total

        current_remaining = sum(
            product_rows[i]["values"][m]
            for i in remaining_indices
        )

        if current_remaining == 0:
            continue

        factor = target_remaining / current_remaining

        # ----------------------------------------
        # Scale remaining products
        # ----------------------------------------

        for i in remaining_indices:

            product_rows[i]["values"][m] = round(
                product_rows[i]["values"][m] * factor
            )

        # ----------------------------------------
        # Fix rounding
        # ----------------------------------------

        actual_total = (
            edited_total +
            sum(
                product_rows[i]["values"][m]
                for i in remaining_indices
            )
        )

        diff = overall[m] - actual_total

        if remaining_indices:
            product_rows[remaining_indices[-1]]["values"][m] += diff

    # ------------------------------------------------------
    # Debug
    # ------------------------------------------------------

    print("Overall :", overall[:5])

    for row in product_rows:
        print(row["label"], row["values"][:5])

    return market_analysis

def rebuild_product_distribution_from_market_share_edit(
    market_analysis,
    edited_rows,
):

    print("\n--- Rebuilding Product Distribution (Share Edit) ---")

    edited_rows = set(edited_rows or [])

    volume_rows = (
        market_analysis["product_distribution"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    share_rows = (
        market_analysis["product_distribution"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    overall = volume_rows[0]["values"]

    products = volume_rows[1:]
    shares = share_rows[1:]

    product_names = [row["label"] for row in products]

    edited_index = None

    for i, name in enumerate(product_names):
        if name in edited_rows:
            edited_index = i
            break

    if edited_index is None:
        return market_analysis

    edited_share = shares[edited_index]["values"]

    remaining_indexes = [
        i for i in range(len(products))
        if i != edited_index
    ]

    for month in range(len(overall)):

        remaining_share = (
            100 - edited_share[month]
        )

        old_remaining = sum(
            shares[i]["values"][month]
            for i in remaining_indexes
        )

        if old_remaining == 0:

            equal = (
                remaining_share / len(remaining_indexes)
                if remaining_indexes else 0
            )

            for i in remaining_indexes:
                shares[i]["values"][month] = round(equal, 2)

        else:

            for i in remaining_indexes:

                ratio = (
                    shares[i]["values"][month]
                    / old_remaining
                )

                shares[i]["values"][month] = round(
                    remaining_share * ratio,
                    2,
                )

    rebuild_product_distribution_volume(
        market_analysis
    )

    rebuild_product_distribution_share(
        market_analysis
    )

    return market_analysis

def rebuild_market_product_from_market_volume_edit(
    market_analysis,
    edited_rows,
):

    print("\n--- Rebuilding Market Product (Volume Edit) ---")

    volume_rows = (
        market_analysis["market_product"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    share_rows = (
        market_analysis["market_product"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    months = len(volume_rows[0]["values"])

    # --------------------------------------------------
    # Process Retail and Non-retail independently
    # --------------------------------------------------

    for market_index in range(len(volume_rows)):

        parent = volume_rows[market_index]
        parent_total = parent["values"]

        children = parent["children"]

        edited = [
            child
            for child in children
            if child["label"] in edited_rows
        ]

        untouched = [
            child
            for child in children
            if child["label"] not in edited_rows
        ]

        for m in range(months):

            edited_total = sum(
                child["values"][m]
                for child in edited
            )

            remaining = parent_total[m] - edited_total

            untouched_total = sum(
                child["values"][m]
                for child in untouched
            )

            if untouched_total == 0:
                continue

            factor = remaining / untouched_total

            for child in untouched:

                child["values"][m] = round(
                    child["values"][m] * factor
                )

            actual = sum(
                child["values"][m]
                for child in children
            )

            diff = parent_total[m] - actual

            children[-1]["values"][m] += diff

    rebuild_market_product_share(market_analysis)

    return market_analysis

def rebuild_market_product_from_market_share_edit(
    market_analysis,
    edited_rows,
):

    print("\n--- Rebuilding Market Product (Share Edit) ---")

    volume_rows = (
        market_analysis["market_product"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    share_rows = (
        market_analysis["market_product"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    months = len(volume_rows[0]["values"])

    for market_index in range(len(volume_rows)):

        parent = volume_rows[market_index]

        parent_total = parent["values"]

        volume_children = parent["children"]
        share_children = share_rows[market_index]["children"]

        edited = [
            i
            for i, child in enumerate(volume_children)
            if child["label"] in edited_rows
        ]

        untouched = [
            i
            for i, child in enumerate(volume_children)
            if child["label"] not in edited_rows
        ]

        for m in range(months):

            edited_volume = 0

            for idx in edited:

                volume_children[idx]["values"][m] = round(
                    parent_total[m]
                    * share_children[idx]["values"][m]
                    / 100
                )

                edited_volume += volume_children[idx]["values"][m]

            remaining = parent_total[m] - edited_volume

            untouched_share = sum(
                share_children[idx]["values"][m]
                for idx in untouched
            )

            if untouched_share == 0:
                continue

            for idx in untouched:

                pct = (
                    share_children[idx]["values"][m]
                    / untouched_share
                )

                volume_children[idx]["values"][m] = round(
                    remaining * pct
                )

            actual = sum(
                child["values"][m]
                for child in volume_children
            )

            diff = parent_total[m] - actual

            volume_children[-1]["values"][m] += diff

    rebuild_market_product_share(market_analysis)

    return market_analysis

def rebuild_product_market_from_market_volume_edit(
    market_analysis,
):

    print("\n--- Rebuilding Product Market (Volume Edit) ---")

    market_product_rows = (
        market_analysis["market_product"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    product_market_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    months = len(product_market_rows[0]["values"])
    product_count = len(product_market_rows)

    retail_children = market_product_rows[0]["children"]
    non_children = market_product_rows[1]["children"]

    # ============================================
    # Copy values from Market Product
    # ============================================

    for p in range(product_count):

        retail_values = retail_children[p]["values"]
        non_values = non_children[p]["values"]

        pm_retail = product_market_rows[p]["children"][0]["values"]
        pm_non = product_market_rows[p]["children"][1]["values"]
        pm_total = product_market_rows[p]["values"]

        for m in range(months):

            pm_retail[m] = retail_values[m]
            pm_non[m] = non_values[m]

            pm_total[m] = (
                retail_values[m]
                + non_values[m]
            )

    # ============================================
    # Refresh shares
    # ============================================

    rebuild_product_market_share(
        market_analysis
    )

    # ============================================
    # Validation
    # ============================================

    print("\nValidation")

    for m in range(months):

        overall = 0

        for row in product_market_rows:

            retail = row["children"][0]["values"][m]
            non = row["children"][1]["values"][m]
            total = row["values"][m]

            if total != retail + non:
                print(
                    f"{row['label']} Month {m+1}: "
                    f"{total} != {retail + non}"
                )

            overall += total

        print(
            f"Month {m+1}: Overall={overall}"
        )

    return market_analysis

def rebuild_product_market_from_market_share_edit(
    market_analysis,
):

    print("\n--- Rebuilding Product Market (Share Edit) ---")

    rebuild_product_market_from_market_volume_edit(
        market_analysis
    )

    return market_analysis

def rebuild_market_product_from_product_market_volume(
    market_analysis,
):

    print("\n--- Rebuilding Market Product from Product Market ---")

    source_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    target_rows = (
        market_analysis["market_product"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    months = len(source_rows[0]["values"])

    retail = target_rows[0]["children"]
    non = target_rows[1]["children"]

    for p in range(len(source_rows)):

        for m in range(months):

            retail[p]["values"][m] = (
                source_rows[p]["children"][0]["values"][m]
            )

            non[p]["values"][m] = (
                source_rows[p]["children"][1]["values"][m]
            )

    rebuild_market_product_share(
        market_analysis
    )

def rebuild_market_product_from_product_market_share(
    market_analysis,
):

    print("\n--- Rebuilding Market Product Shares from Product Market ---")

    source_rows = (
        market_analysis["product_market"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    target_rows = (
        market_analysis["market_product"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    months = len(source_rows[0]["values"])

    retail = target_rows[0]["children"]
    non = target_rows[1]["children"]

    for p in range(len(source_rows)):

        for m in range(months):

            retail[p]["values"][m] = (
                source_rows[p]["children"][0]["values"][m]
            )

            non[p]["values"][m] = (
                source_rows[p]["children"][1]["values"][m]
            )

    rebuild_market_product_volume(
        market_analysis
    )


def rebuild_market_product_from_product_market(
    market_analysis,
):

    product_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    market_rows = (
        market_analysis["market_product"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    retail = market_rows[0]
    non = market_rows[1]

    months = len(retail["values"])

    # parent totals stay unchanged

    for p, product in enumerate(product_rows):

        retail["children"][p]["values"] = (
            product["children"][0]["values"].copy()
        )

        non["children"][p]["values"] = (
            product["children"][1]["values"].copy()
        )

    rebuild_market_product_share(
        market_analysis
    )

def rebuild_product_market_tab_from_market_volume_edit(
    market_analysis,
    edited_rows,
):

    print("\n--- Rebuilding Product Market (Volume Edit) ---")

    volume_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    months = len(volume_rows[0]["values"])

    edited_retail = "Retail" in edited_rows
    edited_non = "Non-retail" in edited_rows

    # ----------------------------------------------------
    # STEP 1
    # Preserve product totals
    # ----------------------------------------------------

    for row in volume_rows:

        total = row["values"]

        retail = row["children"][0]["values"]
        non = row["children"][1]["values"]

        for m in range(months):

            if edited_non:
                retail[m] = total[m] - non[m]

            elif edited_retail:
                non[m] = total[m] - retail[m]

    # ----------------------------------------------------
    # STEP 2
    # Redistribute untouched products
    # ----------------------------------------------------

    redistribute_product_market(
        market_analysis,
        edited_rows,
    )

    # ----------------------------------------------------
    # STEP 3
    # Recompute sibling again after redistribution
    # ----------------------------------------------------

    for row in volume_rows:

        total = row["values"]

        retail = row["children"][0]["values"]
        non = row["children"][1]["values"]

        for m in range(months):

            if edited_non:
                retail[m] = total[m] - non[m]

            elif edited_retail:
                non[m] = total[m] - retail[m]

    # ----------------------------------------------------
    # STEP 4
    # Push into Market Product
    # ----------------------------------------------------

    rebuild_product_market_share(market_analysis)

    rebuild_market_product_tab_from_product_market(
        market_analysis,
    )

    return market_analysis

def redistribute_product_market(
    market_analysis,
    edited_rows,
):

    print("\n--- Redistributing Product Market ---")

    product_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    market_rows = (
        market_analysis["market_distribution"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    retail_total = market_rows[1]["values"]
    non_total = market_rows[2]["values"]

    months = len(retail_total)

    # ----------------------------------------------------
    # Which market was edited?
    # ----------------------------------------------------

    edited_market = (
        "Retail"
        if "Retail" in edited_rows
        else "Non-retail"
    )

    # ----------------------------------------------------
    # Find edited product automatically
    # (the edited value will be the only one no longer
    # matching Product Total = Retail + NonRetail)
    # ----------------------------------------------------

    edited_product = None

    for row in product_rows:

        total = row["values"]
        retail = row["children"][0]["values"]
        non = row["children"][1]["values"]

        for m in range(months):

            if retail[m] + non[m] != total[m]:
                edited_product = row["label"]
                break

        if edited_product:
            break

    if edited_product is None:
        print("No edited product detected.")
        return

    print(f"Edited Product : {edited_product}")
    print(f"Edited Market  : {edited_market}")

    # =====================================================
    # Redistribute ONLY Retail
    # =====================================================

    if edited_market == "Retail":

        for m in range(months):

            edited = 0
            untouched = 0

            for row in product_rows:

                value = row["children"][0]["values"][m]

                if row["label"] == edited_product:
                    edited += value
                else:
                    untouched += value

            remaining = retail_total[m] - edited

            if untouched:

                factor = remaining / untouched

                for row in product_rows:

                    if row["label"] == edited_product:
                        continue

                    row["children"][0]["values"][m] = round(
                        row["children"][0]["values"][m] * factor
                    )

            actual = sum(
                r["children"][0]["values"][m]
                for r in product_rows
            )

            diff = retail_total[m] - actual

            product_rows[-1]["children"][0]["values"][m] += diff

    # =====================================================
    # Redistribute ONLY Non Retail
    # =====================================================

    else:

        for m in range(months):

            edited = 0
            untouched = 0

            for row in product_rows:

                value = row["children"][1]["values"][m]

                if row["label"] == edited_product:
                    edited += value
                else:
                    untouched += value

            remaining = non_total[m] - edited

            if untouched:

                factor = remaining / untouched

                for row in product_rows:

                    if row["label"] == edited_product:
                        continue

                    row["children"][1]["values"][m] = round(
                        row["children"][1]["values"][m] * factor
                    )

            actual = sum(
                r["children"][1]["values"][m]
                for r in product_rows
            )

            diff = non_total[m] - actual

            product_rows[-1]["children"][1]["values"][m] += diff

def rebuild_product_market_tab_from_market_share_edit(
    market_analysis,
    edited_rows,
):

    print("\n--- Rebuilding Product Market (Share Edit) ---")

    volume_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    share_rows = (
        market_analysis["product_market"]
        ["market_share"]["monthly"]["table"]["rows"]
    )

    months = len(volume_rows[0]["values"])

    for product_index in range(len(volume_rows)):

        parent = volume_rows[product_index]
        parent_total = parent["values"]

        volume_children = parent["children"]
        share_children = share_rows[product_index]["children"]

        # ---------------------------------------
        # Which child was edited?
        # ---------------------------------------

        edited_index = None

        for i, child in enumerate(volume_children):
            if child["label"] in edited_rows:
                edited_index = i
                break

        if edited_index is None:
            continue

        other_index = 1 - edited_index

        # ---------------------------------------
        # Month loop
        # ---------------------------------------

        for m in range(months):

            # Edited share -> volume

            edited_volume = round(
                parent_total[m]
                * share_children[edited_index]["values"][m]
                / 100
            )

            volume_children[edited_index]["values"][m] = edited_volume

            # Remaining volume

            volume_children[other_index]["values"][m] = (
                parent_total[m]
                - edited_volume
            )

            # Remaining share

            share_children[other_index]["values"][m] = round(
                volume_children[other_index]["values"][m]
                / parent_total[m]
                * 100,
                2,
            )

            # Edited share (normalize)

            share_children[edited_index]["values"][m] = round(
                volume_children[edited_index]["values"][m]
                / parent_total[m]
                * 100,
                2,
            )

    # --------------------------------------------------
    # Push changes back to Market Product
    # --------------------------------------------------

    rebuild_market_product_tab_from_product_market(
        market_analysis
    )

    rebuild_market_product_share(
        market_analysis
    )

    return market_analysis

def rebuild_market_product_tab_from_product_market(
    market_analysis,
):

    pm_rows = (
        market_analysis["product_market"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    mp_rows = (
        market_analysis["market_product"]
        ["market_volume"]["monthly"]["table"]["rows"]
    )

    # Retail
    for i, row in enumerate(pm_rows):
        mp_rows[0]["children"][i]["values"] = (
            row["children"][0]["values"].copy()
        )

    # Non Retail
    for i, row in enumerate(pm_rows):
        mp_rows[1]["children"][i]["values"] = (
            row["children"][1]["values"].copy()
        )

    rebuild_market_product_share(
        market_analysis
    )

from copy import deepcopy


def rebuild_market_distribution_yearly(
    market_analysis,
    selected_filter,
):
    """
    Rebuilds yearly Market Distribution.

    Yearly volume:
        Sum monthly volumes by year.

    Yearly share:
        Overall = 100

        Retail / Non-retail:
            yearly market volume
            -------------------- × 100
            yearly overall volume

        Child sources:
            yearly source volume
            -------------------- × 100
            yearly parent-market volume
    """

    if isinstance(selected_filter, dict):
        start_date = selected_filter.get(
            "start_date"
        )
    else:
        start_date = getattr(
            selected_filter,
            "start_date",
            None,
        )

    section = market_analysis.get(
        "market_distribution",
        {},
    )

    monthly_volume_table = (
        section
        .get("market_volume", {})
        .get("monthly", {})
        .get("table", {})
    )

    month_count = get_table_month_count(
        monthly_volume_table
    )

    if month_count == 0:
        return market_analysis

    month_labels = get_month_labels(
        start_date,
        month_count,
    )

    # ======================================================
    # 1. Yearly market volume
    # ======================================================

    yearly_volume_table = build_yearly_table(
        monthly_volume_table,
        month_labels,
    )

    volume_metric = section.setdefault(
        "market_volume",
        {},
    )

    volume_yearly = volume_metric.setdefault(
        "yearly",
        {},
    )

    existing_volume_chart = deepcopy(
        volume_yearly.get(
            "chart",
            {},
        )
    )

    volume_yearly["table"] = yearly_volume_table

    volume_yearly["chart"] = (
        rebuild_market_distribution_yearly_chart(
            yearly_table=yearly_volume_table,
            existing_chart=existing_volume_chart,
        )
    )

    # ======================================================
    # 2. Yearly market share from yearly volume
    # ======================================================

    yearly_share_table = (
        build_market_distribution_yearly_share_table(
            yearly_volume_table
        )
    )

    share_metric = section.setdefault(
        "market_share",
        {},
    )

    share_yearly = share_metric.setdefault(
        "yearly",
        {},
    )

    existing_share_chart = deepcopy(
        share_yearly.get(
            "chart",
            {},
        )
    )

    share_yearly["table"] = yearly_share_table

    share_yearly["chart"] = (
        rebuild_market_distribution_yearly_chart(
            yearly_table=yearly_share_table,
            existing_chart=existing_share_chart,
        )
    )

    return market_analysis

def build_market_distribution_yearly_share_table(
    yearly_volume_table,
):
    """
    Creates the yearly Market Distribution share hierarchy.

    Example:

        Overall = 100

        Retail =
            Retail volume / Overall volume × 100

        Non-retail =
            Non-retail volume / Overall volume × 100

        IQVIA =
            IQVIA volume / Non-retail volume × 100
    """

    volume_rows = yearly_volume_table.get(
        "rows",
        [],
    )

    if not volume_rows:
        return {
            "type": "hierarchy",
            "rows": [],
        }

    overall_row = find_table_row(
        volume_rows,
        "Overall",
    )

    if overall_row is None:
        raise ValueError(
            "Overall row not found in yearly "
            "Market Distribution volume table."
        )

    overall_values = list(
        overall_row.get(
            "values",
            [],
        )
    )

    year_count = len(overall_values)

    share_rows = [
        {
            "label": "Overall",
            "values": [
                100.0
                for _ in range(year_count)
            ],
            "children": [],
        }
    ]

    for market_row in volume_rows:
        market_label = str(
            market_row.get(
                "label",
                "",
            )
        ).strip()

        if normalize_chart_market_label(
            market_label
        ) == "overall":
            continue

        market_values = list(
            market_row.get(
                "values",
                [],
            )
        )

        market_share_values = calculate_percentage_values(
            numerator_values=market_values,
            denominator_values=overall_values,
        )

        market_share_row = {
            "label": market_label,
            "values": market_share_values,
            "children": [],
        }

        for source_row in market_row.get(
            "children",
            [],
        ):
            source_label = str(
                source_row.get(
                    "label",
                    "",
                )
            ).strip()

            source_values = list(
                source_row.get(
                    "values",
                    [],
                )
            )

            source_share_values = (
                calculate_percentage_values(
                    numerator_values=source_values,
                    denominator_values=market_values,
                )
            )

            market_share_row["children"].append(
                {
                    "label": source_label,
                    "values": source_share_values,
                }
            )

        share_rows.append(
            market_share_row
        )

    return {
        "type": "hierarchy",
        "rows": share_rows,
    }

def calculate_percentage_values(
    numerator_values,
    denominator_values,
    decimals=2,
):
    result = []

    value_count = max(
        len(numerator_values),
        len(denominator_values),
    )

    for index in range(value_count):
        numerator = (
            numerator_values[index]
            if index < len(numerator_values)
            else 0
        )

        denominator = (
            denominator_values[index]
            if index < len(denominator_values)
            else 0
        )

        if denominator in (
            None,
            0,
        ):
            result.append(0.0)
            continue

        percentage = (
            float(numerator)
            / float(denominator)
            * 100
        )

        result.append(
            round(
                percentage,
                decimals,
            )
        )

    return result


def find_table_row(
    rows,
    target_label,
):
    target_key = normalize_chart_market_label(
        target_label
    )

    for row in rows:
        row_key = normalize_chart_market_label(
            row.get(
                "label",
                "",
            )
        )

        if row_key == target_key:
            return row

    return None

def rebuild_market_distribution_yearly_chart(
    yearly_table,
    existing_chart,
):
    """
    Updates Market Distribution yearly chart values while
    preserving frontend chart metadata.

    Chart series:
        Overall
        Retail
        Non-retail

    Child sources remain only in the table.
    """

    chart = deepcopy(
        existing_chart or {}
    )

    calculated_series = {}

    for row in yearly_table.get(
        "rows",
        [],
    ):
        row_label = str(
            row.get(
                "label",
                "",
            )
        ).strip()

        if not row_label:
            continue

        calculated_series[
            normalize_chart_market_label(
                row_label
            )
        ] = {
            "label": row_label,
            "values": list(
                row.get(
                    "values",
                    [],
                )
            ),
        }

    existing_series = chart.get(
        "series",
        [],
    )

    rebuilt_series = []

    for existing_item in existing_series:
        if not isinstance(
            existing_item,
            dict,
        ):
            continue

        existing_label = existing_item.get(
            "label",
            existing_item.get(
                "name",
                "",
            ),
        )

        market_key = normalize_chart_market_label(
            existing_label
        )

        calculated_item = calculated_series.get(
            market_key
        )

        if calculated_item is None:
            continue

        rebuilt_item = deepcopy(
            existing_item
        )

        update_chart_series_values(
            series_item=rebuilt_item,
            values=calculated_item["values"],
        )

        rebuilt_series.append(
            rebuilt_item
        )

    # Fallback if the existing chart contains no series.
    if not rebuilt_series:
        for calculated_item in (
            calculated_series.values()
        ):
            rebuilt_series.append(
                {
                    "label": calculated_item[
                        "label"
                    ],
                    "values": calculated_item[
                        "values"
                    ],
                }
            )

    chart["series"] = rebuilt_series

    return chart

from collections import OrderedDict
from datetime import datetime

def correct_children_to_parent(
    children,
    parent_values,
):
    """
    Ensures rounded child values add up exactly to the parent
    value for every yearly column.

    The last child absorbs any rounding difference.
    """

    if not children:
        return children

    for index, parent_value in enumerate(parent_values):
        parent_value = round(
            float(parent_value or 0),
            2,
        )

        current_total = 0.0

        for child in children:
            child_values = child.get("values", [])

            if index >= len(child_values):
                raise ValueError(
                    f"Value length mismatch for child "
                    f"'{child.get('label')}'."
                )

            current_total += float(
                child_values[index] or 0
            )

        current_total = round(
            current_total,
            2,
        )

        difference = round(
            parent_value - current_total,
            2,
        )

        last_child = children[-1]

        last_child["values"][index] = round(
            float(
                last_child["values"][index] or 0
            )
            + difference,
            2,
        )

        # Final safety check.
        final_total = round(
            sum(
                float(
                    child["values"][index] or 0
                )
                for child in children
            ),
            2,
        )

        if final_total != parent_value:
            final_difference = round(
                parent_value - final_total,
                2,
            )

            last_child["values"][index] = round(
                float(
                    last_child["values"][index] or 0
                )
                + final_difference,
                2,
            )

    return children


def group_month_indexes_by_year(
    month_labels,
):
    """
    Groups indexes by calendar year.

    Supports labels such as:
        Jan-24
        2024-01-01
        2024-01
    """

    year_groups = OrderedDict()

    for index, month_label in enumerate(
        month_labels
    ):
        year = extract_year_from_month_label(
            month_label
        )

        year_groups.setdefault(
            year,
            [],
        ).append(index)

    return year_groups

def extract_year_from_month_label(
    month_label,
):
    if hasattr(month_label, "year"):
        return str(
            month_label.year
        )

    value = str(
        month_label
    ).strip()

    for date_format in (
        "%b-%y",
        "%Y-%m-%d",
        "%Y-%m",
        "%b %Y",
    ):
        try:
            parsed_date = datetime.strptime(
                value,
                date_format,
            )

            return str(
                parsed_date.year
            )

        except ValueError:
            continue

    raise ValueError(
        f"Unsupported month label: "
        f"{month_label}"
    )

def aggregate_values_by_year(
    values,
    year_groups,
):
    yearly_values = []

    for indexes in year_groups.values():
        yearly_total = sum(
            float(
                values[index] or 0
            )
            for index in indexes
            if index < len(values)
        )

        yearly_values.append(
            yearly_total
        )

    return yearly_values

def find_row_by_label(
    rows,
    label,
):
    target = normalize_row_label(
        label
    )

    for row in rows:
        if normalize_row_label(
            row.get("label")
        ) == target:
            return row

    return None

def normalize_row_label(
    label,
):
    label = str(
        label or ""
    ).strip()

    if "(" in label:
        label = label.split(
            "(",
            1,
        )[0]

    return label.strip().lower()

from copy import deepcopy


def rebuild_product_distribution_yearly(
    market_analysis,
    selected_filter,
):
    """
    Rebuild yearly Product Distribution.

    Rules:
        - Yearly volume is the sum of monthly volume.
        - Yearly share is calculated from yearly volume.
        - Overall share is always 100.
        - The complete table remains available.
        - The existing chart structure is preserved.
    """

    if isinstance(selected_filter, dict):
        start_date = selected_filter.get(
            "start_date"
        )
    else:
        start_date = getattr(
            selected_filter,
            "start_date",
            None,
        )

    section = market_analysis.get(
        "product_distribution",
        {},
    )

    monthly_volume_table = (
        section
        .get("market_volume", {})
        .get("monthly", {})
        .get("table", {})
    )

    month_count = get_table_month_count(
        monthly_volume_table
    )

    if month_count == 0:
        return market_analysis

    month_labels = get_month_labels(
        start_date,
        month_count,
    )

    # ======================================================
    # 1. Yearly product volume
    # ======================================================

    yearly_volume_table = build_yearly_table(
        monthly_volume_table,
        month_labels,
    )

    volume_metric = section.setdefault(
        "market_volume",
        {},
    )

    volume_yearly = volume_metric.setdefault(
        "yearly",
        {},
    )

    existing_volume_chart = deepcopy(
        volume_yearly.get(
            "chart",
            {},
        )
    )

    volume_yearly["table"] = yearly_volume_table

    volume_yearly["chart"] = (
        rebuild_product_distribution_yearly_chart(
            yearly_table=yearly_volume_table,
            existing_chart=existing_volume_chart,
        )
    )

    # ======================================================
    # 2. Yearly product share from yearly volume
    # ======================================================

    yearly_share_table = (
        build_product_distribution_yearly_share_table(
            yearly_volume_table
        )
    )

    share_metric = section.setdefault(
        "market_share",
        {},
    )

    share_yearly = share_metric.setdefault(
        "yearly",
        {},
    )

    existing_share_chart = deepcopy(
        share_yearly.get(
            "chart",
            {},
        )
    )

    share_yearly["table"] = yearly_share_table

    share_yearly["chart"] = (
        rebuild_product_distribution_yearly_chart(
            yearly_table=yearly_share_table,
            existing_chart=existing_share_chart,
        )
    )

    return market_analysis

def build_product_distribution_yearly_share_table(
    yearly_volume_table,
):
    """
    Calculate yearly Product Distribution shares.

    Overall = 100

    Product share =
        yearly product volume
        --------------------- × 100
        yearly overall volume
    """

    volume_rows = yearly_volume_table.get(
        "rows",
        [],
    )

    if not volume_rows:
        return {
            "type": yearly_volume_table.get(
                "type",
                "flat",
            ),
            "rows": [],
        }

    overall_row = find_row_by_normalized_label(
        volume_rows,
        "overall",
    )

    if overall_row is None:
        raise ValueError(
            "Overall row not found in yearly "
            "Product Distribution volume table."
        )

    overall_values = list(
        overall_row.get(
            "values",
            [],
        )
    )

    yearly_share_rows = []

    for row in volume_rows:
        row_label = str(
            row.get(
                "label",
                "",
            )
        ).strip()

        row_key = normalize_chart_product_label(
            row_label
        )

        if row_key == "overall":
            yearly_share_rows.append(
                {
                    **row,
                    "values": [
                        100.0
                        for _ in overall_values
                    ],
                }
            )
            continue

        product_values = list(
            row.get(
                "values",
                [],
            )
        )

        share_values = calculate_percentage_values(
            numerator_values=product_values,
            denominator_values=overall_values,
            decimals=2,
        )

        yearly_share_rows.append(
            {
                **row,
                "values": share_values,
            }
        )

    return {
        **yearly_volume_table,
        "rows": yearly_share_rows,
    }

def find_row_by_normalized_label(
    rows,
    target_label,
):
    target_key = str(
        target_label or ""
    ).strip().lower()

    for row in rows:
        row_key = normalize_chart_product_label(
            row.get(
                "label",
                "",
            )
        )

        if row_key == target_key:
            return row

    return None

def rebuild_product_distribution_yearly_chart(
    yearly_table,
    existing_chart,
):
    """
    Preserve existing Product Distribution chart metadata and
    update only its yearly series values.
    """

    chart = deepcopy(
        existing_chart or {}
    )

    calculated_series = {}

    for row in yearly_table.get(
        "rows",
        [],
    ):
        label = str(
            row.get(
                "label",
                "",
            )
        ).strip()

        if not label:
            continue

        key = normalize_chart_product_label(
            label
        )

        calculated_series[key] = {
            "label": label,
            "values": list(
                row.get(
                    "values",
                    [],
                )
            ),
        }

    existing_series = chart.get(
        "series",
        [],
    )

    rebuilt_series = []

    for existing_item in existing_series:
        if not isinstance(
            existing_item,
            dict,
        ):
            continue

        existing_label = existing_item.get(
            "label",
            existing_item.get(
                "name",
                "",
            ),
        )

        series_key = normalize_chart_product_label(
            existing_label
        )

        calculated_item = calculated_series.get(
            series_key
        )

        if calculated_item is None:
            continue

        rebuilt_item = deepcopy(
            existing_item
        )

        update_chart_series_values(
            series_item=rebuilt_item,
            values=calculated_item["values"],
        )

        rebuilt_series.append(
            rebuilt_item
        )

    # Fallback when no existing series is available.
    if not rebuilt_series:
        for item in calculated_series.values():
            rebuilt_series.append(
                {
                    "label": item["label"],
                    "values": item["values"],
                }
            )

    chart["series"] = rebuilt_series

    return chart

def correct_product_shares_to_100(
    product_rows,
):
    """
    Ensures product shares total exactly 100% for every year.

    The last product absorbs the rounding difference.
    """

    if not product_rows:
        return product_rows

    number_of_years = len(
        product_rows[0].get(
            "values",
            [],
        )
    )

    for year_index in range(number_of_years):
        current_total = round(
            sum(
                float(
                    row["values"][year_index]
                    or 0
                )
                for row in product_rows
            ),
            2,
        )

        difference = round(
            100.0 - current_total,
            2,
        )

        product_rows[-1][
            "values"
        ][year_index] = round(
            float(
                product_rows[-1]["values"][
                    year_index
                ] or 0
            )
            + difference,
            2,
        )

    return product_rows

def build_market_product_yearly_chart_from_table(
    table,
    existing_chart=None,
):
    """
    Build yearly Channel-Product chart from hierarchical rows.

    Output labels:
        Retail - Biktarvy
        Retail - Descovy
        Retail - Truvada
        Non-retail - Biktarvy
        Non-retail - Descovy
        Non-retail - Truvada
    """

    existing_chart = existing_chart or {}

    existing_series = existing_chart.get(
        "series",
        [],
    )

    existing_series_map = {
        normalize_market_product_series_label(
            item.get("label", "")
        ): item
        for item in existing_series
        if isinstance(item, dict)
    }

    rebuilt_series = []

    for market_row in table.get("rows", []):
        market_label = str(
            market_row.get("label", "")
        ).strip()

        if normalize_chart_market_label(
            market_label
        ) == "overall":
            continue

        for product_row in market_row.get(
            "children",
            [],
        ):
            product_label = str(
                product_row.get("label", "")
            ).strip()

            series_label = (
                f"{market_label} - {product_label}"
            )

            values = list(
                product_row.get("values", [])
            )

            series_key = (
                normalize_market_product_series_label(
                    series_label
                )
            )

            previous_series = existing_series_map.get(
                series_key,
                {},
            )

            rebuilt_item = {
                **previous_series,
                "label": series_label,
                "values": values,
            }

            rebuilt_series.append(
                rebuilt_item
            )

    return {
        **existing_chart,
        "series": rebuilt_series,
    }

def build_product_market_yearly_chart_from_table(
    yearly_table,
):
    """
    Converts:

        Biktarvy
            Retail
            Non-retail

    into chart series:

        Biktarvy - Retail
        Biktarvy - Non-retail

    The original yearly table is not modified.
    """

    chart_rows = []

    for product_row in yearly_table.get(
        "rows",
        [],
    ):
        product_label = str(
            product_row.get("label", "")
        ).strip()

        if not product_label:
            continue

        if normalize_chart_product_label(
            product_label
        ) == "overall":
            continue

        for market_row in product_row.get(
            "children",
            [],
        ):
            market_label = str(
                market_row.get("label", "")
            ).strip()

            if not market_label:
                continue

            chart_rows.append(
                {
                    "label": (
                        f"{product_label} - "
                        f"{market_label}"
                    ),
                    "values": list(
                        market_row.get(
                            "values",
                            [],
                        )
                    ),
                }
            )

    flattened_table = {
        "type": "flat",
        "rows": chart_rows,
    }

    return build_yearly_chart_from_table(
        flattened_table
    )

def normalize_market_product_series_label(
    label,
):
    label = str(label or "").strip()

    if "(" in label:
        label = label.split(
            "(",
            1,
        )[0].strip()

    return " ".join(
        label.lower().split()
    )

def rebuild_market_product_yearly(
    market_analysis,
    selected_filter,
):
    if isinstance(selected_filter, dict):
        start_date = selected_filter.get("start_date")
    else:
        start_date = getattr(
            selected_filter,
            "start_date",
            None,
        )

    market_product = market_analysis.get(
        "market_product",
        {},
    )

    monthly_volume_table = (
        market_product
        .get("market_volume", {})
        .get("monthly", {})
        .get("table", {})
    )

    monthly_rows = monthly_volume_table.get(
        "rows",
        [],
    )

    if not monthly_rows:
        return market_analysis

    month_count = len(
        monthly_rows[0].get("values", [])
    )

    month_labels = get_month_labels(
        start_date,
        month_count,
    )

    for metric_name in (
        "market_volume",
        "market_share",
    ):
        metric_data = market_product.get(
            metric_name,
            {},
        )

        monthly_table = (
            metric_data
            .get("monthly", {})
            .get("table", {})
        )

        yearly_table = build_yearly_table(
            monthly_table,
            month_labels,
        )

        yearly_data = metric_data.setdefault(
            "yearly",
            {},
        )

        yearly_data["table"] = yearly_table

        existing_chart = yearly_data.get(
            "chart",
            {},
        )

        yearly_data["chart"] = (
            build_market_product_yearly_chart_from_table(
                table=yearly_table,
                existing_chart=existing_chart,
            )
        )

    return market_analysis

def rebuild_product_market_yearly(
    market_analysis,
    selected_filter,
):
    if isinstance(selected_filter, dict):
        start_date = selected_filter.get("start_date")
    else:
        start_date = getattr(
            selected_filter,
            "start_date",
            None,
        )

    section = market_analysis.get(
        "product_market",
        {},
    )

    monthly_volume_table = (
        section
        .get("market_volume", {})
        .get("monthly", {})
        .get("table", {})
    )

    month_count = get_table_month_count(
        monthly_volume_table
    )

    if month_count == 0:
        return market_analysis

    month_labels = get_month_labels(
        start_date,
        month_count,
    )

    for metric_name in (
        "market_volume",
        "market_share",
    ):
        metric_data = section.get(
            metric_name,
            {},
        )

        monthly_table = (
            metric_data
            .get("monthly", {})
            .get("table", {})
        )

        if not monthly_table.get("rows"):
            continue

        yearly_data = metric_data.setdefault(
            "yearly",
            {},
        )

        # Preserve the working chart schema before replacing
        # the yearly table.
        existing_chart = deepcopy(
            yearly_data.get("chart", {})
        )

        yearly_table = build_yearly_table(
            monthly_table,
            month_labels,
        )

        # Keep the complete hierarchical table.
        yearly_data["table"] = yearly_table

        # Preserve chart metadata and update only series.
        yearly_data["chart"] = (
            rebuild_product_market_yearly_chart(
                yearly_table=yearly_table,
                existing_chart=existing_chart,
            )
        )

    return market_analysis

def rebuild_product_market_yearly_chart(
    yearly_table,
    existing_chart,
):
    """
    Preserves the existing yearly chart structure and updates
    the Product-Channel series values.

    Table remains:

        Biktarvy
            Retail
            Non-retail

    Chart series remain:

        Biktarvy - Retail
        Biktarvy - Non-retail
    """

    chart = deepcopy(existing_chart or {})

    calculated_values = {}

    for product_row in yearly_table.get("rows", []):
        product_label = str(
            product_row.get("label", "")
        ).strip()

        if not product_label:
            continue

        if normalize_chart_product_label(
            product_label
        ) == "overall":
            continue

        for market_row in product_row.get(
            "children",
            [],
        ):
            market_label = str(
                market_row.get("label", "")
            ).strip()

            if not market_label:
                continue

            series_label = (
                f"{product_label} - {market_label}"
            )

            series_key = normalize_product_market_series_label(
                series_label
            )

            calculated_values[series_key] = list(
                market_row.get("values", [])
            )

    existing_series = chart.get(
        "series",
        [],
    )

    rebuilt_series = []

    # Preserve every field expected by the frontend.
    for existing_item in existing_series:
        if not isinstance(existing_item, dict):
            continue

        existing_label = existing_item.get(
            "label",
            existing_item.get("name", ""),
        )

        series_key = normalize_product_market_series_label(
            existing_label
        )

        values = calculated_values.get(series_key)

        if values is None:
            continue

        rebuilt_item = deepcopy(existing_item)

        update_chart_series_values(
            series_item=rebuilt_item,
            values=values,
        )

        rebuilt_series.append(rebuilt_item)

    # Fallback when the old chart has no existing series.
    if not rebuilt_series:
        for series_key, values in calculated_values.items():
            rebuilt_series.append(
                {
                    "label": restore_product_market_label(
                        series_key
                    ),
                    "values": values,
                }
            )

    chart["series"] = rebuilt_series

    return chart

def normalize_product_market_series_label(label):
    label = str(label or "").strip()

    # Remove scenario suffix:
    # Biktarvy - Retail (Base)
    # becomes Biktarvy - Retail
    if "(" in label:
        label = label.split("(", 1)[0].strip()

    return " ".join(
        label.lower().split()
    )


def restore_product_market_label(normalized_label):
    """
    Fallback only. Normally the original label is preserved
    from existing_chart.
    """

    if " - " not in normalized_label:
        return normalized_label.title()

    product, market = normalized_label.split(
        " - ",
        1,
    )

    return (
        f"{product.title()} - "
        f"{market.capitalize()}"
    )

def update_chart_series_values(
    series_item,
    values,
):
    """
    Updates values without destroying the existing chart-series
    schema.

    Supports common chart structures:
        values
        data
        historical_values / forecast_values
        history / forecast
    """

    values = list(values or [])

    if "values" in series_item:
        series_item["values"] = values

    if "data" in series_item:
        series_item["data"] = values

    # Some chart payloads divide actual and forecast data.
    if (
        "historical_values" in series_item
        or "forecast_values" in series_item
    ):
        historical_count = len(
            series_item.get(
                "historical_values",
                [],
            )
        )

        if historical_count <= 0:
            historical_count = max(
                len(values) - 1,
                0,
            )

        series_item["historical_values"] = (
            values[:historical_count]
        )

        series_item["forecast_values"] = (
            values[historical_count:]
        )

    if (
        "history" in series_item
        or "forecast" in series_item
    ):
        history_count = len(
            series_item.get("history", [])
        )

        if history_count <= 0:
            history_count = max(
                len(values) - 1,
                0,
            )

        series_item["history"] = (
            values[:history_count]
        )

        series_item["forecast"] = (
            values[history_count:]
        )

    # Fallback for simple chart schemas.
    if not any(
        key in series_item
        for key in (
            "values",
            "data",
            "historical_values",
            "forecast_values",
            "history",
            "forecast",
        )
    ):
        series_item["values"] = values

def get_table_month_count(
    table,
):
    for row in table.get(
        "rows",
        [],
    ):
        values = row.get(
            "values",
            [],
        )

        if values:
            return len(values)

        for child in row.get(
            "children",
            [],
        ):
            child_values = child.get(
                "values",
                [],
            )

            if child_values:
                return len(child_values)

    return 0

def filter_product_market_chart(
    market_analysis,
    selected_filter,
):
    """
    Filters Product-Channel charts by selected products.

    Example:
        selected products = ["Biktarvy"]

    Keeps:
        Biktarvy - Retail
        Biktarvy - Non-retail

    Tables remain complete.
    """

    if isinstance(selected_filter, dict):
        selected_products = selected_filter.get(
            "products",
            selected_filter.get(
                "product",
                [],
            ),
        )
    else:
        selected_products = getattr(
            selected_filter,
            "products",
            getattr(
                selected_filter,
                "product",
                [],
            ),
        )

    if isinstance(selected_products, str):
        selected_products = [selected_products]

    selected_product_keys = {
        normalize_chart_product_label(product)
        for product in (selected_products or [])
        if product
    }

    if not selected_product_keys:
        return market_analysis

    product_market = market_analysis.get(
        "product_market",
        {},
    )

    for metric_data in product_market.values():
        if not isinstance(metric_data, dict):
            continue

        for period_name in (
            "monthly",
            "yearly",
        ):
            chart = (
                metric_data
                .get(period_name, {})
                .get("chart", {})
            )

            series = chart.get(
                "series",
                [],
            )

            if not isinstance(series, list):
                continue

            chart["series"] = [
                item
                for item in series
                if extract_product_from_product_market_label(
                    item.get("label", "")
                ) in selected_product_keys
            ]

    return market_analysis

def extract_product_from_product_market_label(
    label,
):
    """
    Converts:

        Biktarvy - Retail
        Biktarvy - Non-retail (Base)

    into:

        biktarvy
    """

    label = str(label or "").strip()

    if "(" in label:
        label = label.split("(", 1)[0].strip()

    if " - " not in label:
        return ""

    product, _ = label.split(
        " - ",
        1,
    )

    return normalize_chart_product_label(
        product
    )

def build_yearly_child_chart_from_table(
    table,
    parent_type,
    existing_chart=None,
):
    """
    Builds yearly chart series from hierarchy child rows.

    parent_type="market_product":
        Retail - Biktarvy

    parent_type="product_market":
        Biktarvy - Retail
    """

    existing_chart = existing_chart or {}

    rows = table.get("rows", [])
    series = []

    for parent_row in rows:
        parent_label = str(
            parent_row.get("label", "")
        ).strip()

        if normalize_row_label(parent_label) == "overall":
            continue

        children = parent_row.get("children", [])

        for child_row in children:
            child_label = str(
                child_row.get("label", "")
            ).strip()

            if parent_type == "market_product":
                series_label = (
                    f"{parent_label} - {child_label}"
                )

            elif parent_type == "product_market":
                series_label = (
                    f"{parent_label} - {child_label}"
                )

            else:
                raise ValueError(
                    f"Unsupported parent_type: "
                    f"{parent_type}"
                )

            series.append(
                {
                    "label": series_label,
                    "values": child_row.get(
                        "values",
                        [],
                    ),
                }
            )

    return {
        **existing_chart,
        "series": series,
    }
