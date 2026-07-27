from app.hiv_treat.services.chart_builder import *

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

def refresh_engine(payload):

    market_analysis = payload.market_analysis

    if payload.selected_tab == "total_market_volume":

        market_analysis = recompute_from_total_market_volume(
            market_analysis,
            payload.selected_filter,
        )

    elif payload.selected_tab == "market_distribution":

        market_analysis = recompute_from_market_distribution(
            market_analysis,
            payload.selected_metric,
            payload.edited_rows or [],
            payload.selected_filter,
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
def recompute_from_market_distribution(
    market_analysis,
    selected_metric,
    edited_rows,
    selected_filter
):

    if selected_metric == "market_volume":

        rebuild_market_distribution_from_market_volume_edit(
            market_analysis,
            edited_rows,
        )

        rebuild_market_distribution_share(
            market_analysis,
        )

    else:

        rebuild_market_distribution_from_market_share_edit(
            market_analysis,
            edited_rows,
        )

    # downstream tabs
    build_product_distribution(
        market_analysis,
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

#product_distribution

def recompute_from_product_distribution(
    market_analysis,
    selected_metric,
    edited_rows,
    selected_filter
):
    if selected_metric == "market_volume":

        rebuild_product_distribution_from_market_volume_edit(
            market_analysis,
            edited_rows,
        )

    else:

        rebuild_product_distribution_from_market_share_edit(
            market_analysis,
            edited_rows,
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

#market_product
def recompute_from_market_product(
    market_analysis,
    selected_metric,
    edited_rows,
    selected_filter
):

    if selected_metric == "market_volume":

        rebuild_market_product_from_market_volume_edit(
            market_analysis,
            edited_rows,
        )

        rebuild_product_market_from_market_volume_edit(
            market_analysis,
        )

    else:

        rebuild_market_product_from_market_share_edit(
            market_analysis,
            edited_rows,
        )

        rebuild_product_market_from_market_share_edit(
            market_analysis,
        )

    rebuild_all_monthly_charts(
        market_analysis,
    )

    rebuild_market_product_yearly(
    market_analysis,
    selected_filter,
    )

    rebuild_product_market_yearly(
    market_analysis,
    selected_filter,
    )

    return market_analysis

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

def rebuild_market_distribution_volume(market_analysis):

    print("\n--- Rebuilding Market Distribution Volume ---")

    # Total Market Volume
    tmv_values = (
        market_analysis["total_market_volume"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"][0]["values"]
    )

    # Market Distribution Volume
    volume_rows = (
        market_analysis["market_distribution"]
        ["market_volume"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    # Market Distribution Share
    share_rows = (
        market_analysis["market_distribution"]
        ["market_share"]
        ["monthly"]
        ["table"]
        ["rows"]
    )

    # -----------------------------
    # Overall
    # -----------------------------
    volume_rows[0]["values"] = tmv_values.copy()

    # -----------------------------
    # Retail & Non-retail
    # -----------------------------
    for row_index in [1, 2]:

        for month_index in range(len(tmv_values)):

            volume_rows[row_index]["values"][month_index] = round(
                tmv_values[month_index]
                * share_rows[row_index]["values"][month_index]
                / 100
            )

    # -----------------------------
    # Non-retail Children
    # -----------------------------
    parent_volume = volume_rows[2]["values"]

    children_volume = volume_rows[2]["children"]
    children_share = share_rows[2]["children"]

    for child_index in range(len(children_volume)):

        for month_index in range(len(parent_volume)):

            children_volume[child_index]["values"][month_index] = round(
                parent_volume[month_index]
                * children_share[child_index]["values"][month_index]
                / 100
            )

    # -----------------------------
    # Testing
    # -----------------------------
    print("Overall :", volume_rows[0]["values"][:5])
    print("Retail :", volume_rows[1]["values"][:5])
    print("Non-retail :", volume_rows[2]["values"][:5])

    print("Kaiser :", children_volume[0]["values"][:5])
    print("IQVIA :", children_volume[1]["values"][:5])
    print("ADAP :", children_volume[2]["values"][:5])
    print("Federal :", children_volume[3]["values"][:5])

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
    edited_rows,
):
    print("\n--- Rebuilding Market Distribution (Share Edit) ---")

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

    retail_share_row = find_row(share_rows, "Retail")
    non_retail_share_row = find_row(share_rows, "Non-retail")

    required_rows = {
        "Overall market volume": overall_volume_row,
        "Retail market volume": retail_volume_row,
        "Non-retail market volume": non_retail_volume_row,
        "Retail market share": retail_share_row,
        "Non-retail market share": non_retail_share_row,
    }

    for row_name, row in required_rows.items():
        if row is None:
            raise ValueError(f"{row_name} row is missing.")

    overall = overall_volume_row["values"]

    retail_volume = retail_volume_row["values"]
    non_retail_volume = non_retail_volume_row["values"]

    retail_share = retail_share_row["values"]
    non_retail_share = non_retail_share_row["values"]

    # --------------------------------------------------
    # Parent shares
    # --------------------------------------------------

    if "Retail" in edited_labels:

        for month_index in range(len(overall)):
            non_retail_share[month_index] = round(
                100 - retail_share[month_index],
                2,
            )

    elif "Non-retail" in edited_labels:

        for month_index in range(len(overall)):
            retail_share[month_index] = round(
                100 - non_retail_share[month_index],
                2,
            )

    # --------------------------------------------------
    # Parent volumes
    # --------------------------------------------------

    for month_index in range(len(overall)):

        retail_volume[month_index] = round(
            overall[month_index]
            * retail_share[month_index]
            / 100
        )

        non_retail_volume[month_index] = (
            overall[month_index]
            - retail_volume[month_index]
        )

    # --------------------------------------------------
    # Rebuild Non-retail children volumes
    # --------------------------------------------------

    children_volume = non_retail_volume_row.get(
        "children",
        [],
    )

    children_share = non_retail_share_row.get(
        "children",
        [],
    )

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

        for month_index in range(len(overall)):

            child_values[month_index] = round(
                non_retail_volume[month_index]
                * child_shares[month_index]
                / 100
            )

    rebuild_market_distribution_share(
        market_analysis
    )

    return market_analysis

from app.hiv_treat.services.chart_builder import build_chart_from_table

#charts rebuild
def rebuild_all_monthly_charts(market_analysis):

    for section_name, section in market_analysis.items():

        if not isinstance(section, dict):
            continue

        for metric in ["market_volume", "market_share"]:

            if metric not in section:
                continue

            metric_data = section[metric]

            if "monthly" not in metric_data:
                continue

            monthly = metric_data["monthly"]

            if "table" not in monthly:
                continue

            existing_chart = monthly.get("chart", {})

            monthly["chart"] = build_chart_from_table(
                monthly["table"],
                existing_chart,
            )

    return market_analysis

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

def rebuild_market_distribution_yearly(
    market_analysis,
    selected_filter,
):

    month_labels = get_month_labels(
        selected_filter["start_date"],
        len(
            market_analysis["market_distribution"]
            ["market_volume"]["monthly"]["table"]["rows"][0]["values"]
        ),
    )

    # ==========================================================
    # Yearly Market Volume
    # ==========================================================

    yearly_volume_table = build_yearly_table(
        market_analysis["market_distribution"]["market_volume"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["market_distribution"]["market_volume"]["yearly"]["table"] = (
        yearly_volume_table
    )

    market_analysis["market_distribution"]["market_volume"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_volume_table
        )
    )

    # ==========================================================
    # Yearly Market Share
    # ==========================================================

    yearly_share_table = build_yearly_table(
        market_analysis["market_distribution"]["market_share"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["market_distribution"]["market_share"]["yearly"]["table"] = (
        yearly_share_table
    )

    market_analysis["market_distribution"]["market_share"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_share_table
        )
    )

    return market_analysis

def rebuild_product_distribution_yearly(
    market_analysis,
    selected_filter,
):

    month_labels = get_month_labels(
        selected_filter["start_date"],
        len(
            market_analysis["product_distribution"]
            ["market_volume"]["monthly"]["table"]["rows"][0]["values"]
        ),
    )

    # ==========================================================
    # Yearly Market Volume
    # ==========================================================

    yearly_volume_table = build_yearly_table(
        market_analysis["product_distribution"]["market_volume"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["product_distribution"]["market_volume"]["yearly"]["table"] = (
        yearly_volume_table
    )

    market_analysis["product_distribution"]["market_volume"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_volume_table
        )
    )

    # ==========================================================
    # Yearly Market Share
    # ==========================================================

    yearly_share_table = build_yearly_table(
        market_analysis["product_distribution"]["market_share"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["product_distribution"]["market_share"]["yearly"]["table"] = (
        yearly_share_table
    )

    market_analysis["product_distribution"]["market_share"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_share_table
        )
    )

    return market_analysis

def rebuild_market_product_yearly(
    market_analysis,
    selected_filter,
):

    month_labels = get_month_labels(
        selected_filter["start_date"],
        len(
            market_analysis["market_product"]
            ["market_volume"]["monthly"]["table"]["rows"][0]["values"]
        ),
    )

    # ==========================================================
    # Yearly Market Volume
    # ==========================================================

    yearly_volume_table = build_yearly_table(
        market_analysis["market_product"]["market_volume"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["market_product"]["market_volume"]["yearly"]["table"] = (
        yearly_volume_table
    )

    market_analysis["market_product"]["market_volume"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_volume_table
        )
    )

    # ==========================================================
    # Yearly Market Share
    # ==========================================================

    yearly_share_table = build_yearly_table(
        market_analysis["market_product"]["market_share"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["market_product"]["market_share"]["yearly"]["table"] = (
        yearly_share_table
    )

    market_analysis["market_product"]["market_share"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_share_table
        )
    )

    return market_analysis

def rebuild_product_market_yearly(
    market_analysis,
    selected_filter,
):

    month_labels = get_month_labels(
        selected_filter["start_date"],
        len(
            market_analysis["product_market"]
            ["market_volume"]["monthly"]["table"]["rows"][0]["values"]
        ),
    )

    # ==========================================================
    # Yearly Market Volume
    # ==========================================================

    yearly_volume_table = build_yearly_table(
        market_analysis["product_market"]["market_volume"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["product_market"]["market_volume"]["yearly"]["table"] = (
        yearly_volume_table
    )

    market_analysis["product_market"]["market_volume"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_volume_table
        )
    )

    # ==========================================================
    # Yearly Market Share
    # ==========================================================

    yearly_share_table = build_yearly_table(
        market_analysis["product_market"]["market_share"]["monthly"]["table"],
        month_labels,
    )

    market_analysis["product_market"]["market_share"]["yearly"]["table"] = (
        yearly_share_table
    )

    market_analysis["product_market"]["market_share"]["yearly"]["chart"] = (
        build_yearly_chart_from_table(
            yearly_share_table
        )
    )

    return market_analysis
