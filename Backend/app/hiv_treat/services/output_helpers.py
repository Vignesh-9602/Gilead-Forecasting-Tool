from copy import deepcopy
from fastapi import HTTPException
from app.hiv_treat.services.Model_Input_Service import *

def normalize_filter_values(values):
    if not values:
        return []

    normalized = []
    seen = set()

    for value in values:
        if value is None:
            continue

        cleaned = str(value).strip()

        if not cleaned:
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            normalized.append(cleaned)

    return normalized

def normalize_dimension_filter(values):
    values = normalize_filter_values(values)

    if any(
        value.lower() in {
            "all",
            "overall",
        }
        for value in values
    ):
        return []

    return values

def resolve_selected_scenarios(
    requested_scenarios,
    available_scenarios,
):
    available_lookup = {
        str(scenario).strip().lower(): scenario
        for scenario in available_scenarios
    }

    requested_scenarios = normalize_filter_values(
        requested_scenarios
    )

    if not requested_scenarios:
        return [available_scenarios[0]]

    resolved = []

    for requested in requested_scenarios:
        key = requested.lower()

        if key not in available_lookup:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Scenario {requested!r} is not available."
                ),
            )

        resolved.append(
            available_lookup[key]
        )

    return resolved

def build_scenario_market_analysis(
    cur,
    ta,
    scenario,
    start,
    end,
    selected_markets,
    selected_products,
):
    total_data = fetch_forecast_scenario(
        cur,
        ta,
        "ALL",
        "ALL",
        "ALL",
        "market_volume",
        scenario,
    )

    if not total_data:
        return {
            "total_market_volume": {
                "market_volume": {},
                "market_share": {},
            },
            "market_distribution": {},
            "product_distribution": {},
            "market_product": {},
            "product_market": {},
        }

    total = build_series(
        total_data,
        start,
        end,
    )

    total_vals = total["values"]
    months = total["months"]
    split_idx = total["split_idx"]

    markets = get_markets(
        cur,
        ta,
    )

    products = get_products(
        cur,
        ta,
    )

    selected_market = (
        selected_markets[0]
        if len(selected_markets) == 1
        else "ALL"
    )

    selected_product = (
        selected_products[0]
        if len(selected_products) == 1
        else "ALL"
    )

    return {
        "total_market_volume": (
            build_total_market_volume(
                total_vals,
                months,
                split_idx,
                scenario,
            )
        ),

        "market_distribution": (
            build_market_distribution(
                cur,
                ta,
                scenario,
                total_vals,
                months,
                split_idx,
                start,
                end,
            )
        ),

        "product_distribution": (
            build_product_distribution(
                cur,
                ta,
                scenario,
                markets,
                total_vals,
                months,
                split_idx,
                start,
                end,
            )
        ),

        "market_product": (
            build_market_product(
                cur,
                ta,
                scenario,
                markets,
                products,
                total_vals,
                months,
                split_idx,
                start,
                end,
                selected_market,
            )
        ),

        "product_market": (
            build_product_market(
                cur,
                ta,
                scenario,
                markets,
                products,
                total_vals,
                months,
                split_idx,
                start,
                end,
                selected_product,
            )
        ),
    }

def add_scenario_name_to_rows(
    rows,
    scenario_name,
    *,
    total_market_volume=False,
):
    if not isinstance(rows, list):
        return []

    renamed_rows = []

    total_labels = {
        "overall",
        "total",
        "grand total",
    }

    for row in rows:
        if not isinstance(row, dict):
            continue

        copied_row = deepcopy(row)

        label = str(
            copied_row.get("label", "")
        ).strip()

        normalized_label = label.lower()

        if label:
            if (
                total_market_volume
                and normalized_label in total_labels
            ):
                copied_row["label"] = scenario_name
            else:
                copied_row["label"] = (
                    f"{label} ({scenario_name})"
                )

        children = copied_row.get("children")

        if isinstance(children, list):
            copied_row["children"] = (
                add_scenario_name_to_rows(
                    children,
                    scenario_name,
                    total_market_volume=False,
                )
            )

        renamed_rows.append(copied_row)

    return renamed_rows

def add_scenario_name_to_chart_series(
    series,
    scenario_name,
    *,
    total_market_volume=False,
):
    if not isinstance(series, list):
        return []

    renamed_series = []

    total_labels = {
        "overall",
        "total",
        "grand total",
    }

    for item in series:
        if not isinstance(item, dict):
            continue

        copied_item = deepcopy(item)

        label_key = None

        for candidate in (
            "name",
            "label",
            "series_name",
        ):
            if candidate in copied_item:
                label_key = candidate
                break

        if label_key is not None:
            label = str(
                copied_item.get(label_key, "")
            ).strip()

            normalized_label = label.lower()

            if label:
                if (
                    total_market_volume
                    and normalized_label in total_labels
                ):
                    copied_item[label_key] = (
                        scenario_name
                    )
                else:
                    copied_item[label_key] = (
                        f"{label} ({scenario_name})"
                    )

        renamed_series.append(copied_item)

    return renamed_series

def prepare_scenario_for_merge(
    market_analysis,
    scenario_name,
):
    prepared = deepcopy(market_analysis)

    for tab_name, tab_data in prepared.items():
        if not isinstance(tab_data, dict):
            continue

        is_total_market_volume = (
            tab_name == "total_market_volume"
        )

        for metric_data in tab_data.values():
            if not isinstance(metric_data, dict):
                continue

            for view_data in metric_data.values():
                if not isinstance(view_data, dict):
                    continue

                table = view_data.get("table")

                if isinstance(table, dict):
                    table["rows"] = (
                        add_scenario_name_to_rows(
                            table.get("rows", []),
                            scenario_name,
                            total_market_volume=(
                                is_total_market_volume
                            ),
                        )
                    )

                chart = view_data.get("chart")

                if isinstance(chart, dict):
                    chart["series"] = (
                        add_scenario_name_to_chart_series(
                            chart.get("series", []),
                            scenario_name,
                            total_market_volume=(
                                is_total_market_volume
                            ),
                        )
                    )

    return prepared

def merge_view_data(
    destination_view,
    source_view,
):
    if not isinstance(destination_view, dict):
        return

    if not isinstance(source_view, dict):
        return

    # =====================================================
    # Merge table rows
    # =====================================================

    source_table = source_view.get("table")

    if isinstance(source_table, dict):
        destination_table = destination_view.get(
            "table"
        )

        if not isinstance(destination_table, dict):
            destination_view["table"] = deepcopy(
                source_table
            )
        else:
            destination_table.setdefault(
                "rows",
                [],
            )

            destination_table["rows"].extend(
                deepcopy(
                    source_table.get("rows", [])
                )
            )

    # =====================================================
    # Merge chart series
    # =====================================================

    source_chart = source_view.get("chart")

    if isinstance(source_chart, dict):
        destination_chart = destination_view.get(
            "chart"
        )

        if not isinstance(destination_chart, dict):
            destination_view["chart"] = deepcopy(
                source_chart
            )
        else:
            destination_chart.setdefault(
                "series",
                [],
            )

            destination_chart["series"].extend(
                deepcopy(
                    source_chart.get("series", [])
                )
            )

    # =====================================================
    # Copy missing metadata
    # =====================================================

    for key, value in source_view.items():
        if key in {"table", "chart"}:
            continue

        if key not in destination_view:
            destination_view[key] = deepcopy(value)

def merge_output_tabs(
    destination,
    source,
):
    if not destination:
        return deepcopy(source)

    for tab_name, source_tab in source.items():
        if tab_name not in destination:
            destination[tab_name] = deepcopy(
                source_tab
            )
            continue

        destination_tab = destination[tab_name]

        if not isinstance(source_tab, dict):
            continue

        for metric_name, source_metric in (
            source_tab.items()
        ):
            if metric_name not in destination_tab:
                destination_tab[metric_name] = (
                    deepcopy(source_metric)
                )
                continue

            destination_metric = (
                destination_tab[metric_name]
            )

            if not isinstance(source_metric, dict):
                continue

            for view_name, source_view in (
                source_metric.items()
            ):
                if view_name not in destination_metric:
                    destination_metric[view_name] = (
                        deepcopy(source_view)
                    )
                    continue

                destination_view = (
                    destination_metric[view_name]
                )

                merge_view_data(
                    destination_view,
                    source_view,
                )

    return destination


def merge_total_market_volume(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "total_market_volume",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "total_market_volume",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(source_period, dict):
                continue

            prepare_total_market_period(
                source_period=source_period,
                metric_name=metric_name,
                scenario_name=scenario_name,
                period_name=period_name,
            )

            # First scenario for this metric/period.
            if period_name not in destination_metric:
                destination_metric[period_name] = (
                    source_period
                )
                continue

            destination_period = destination_metric[
                period_name
            ]

            merge_total_market_table(
                destination_period=destination_period,
                source_period=source_period,
            )

            merge_chart_series(
                destination_period=destination_period,
                source_period=source_period,
            )

def prepare_total_market_period(
    source_period,
    metric_name,
    scenario_name,
    period_name,
):
    source_table = source_period.setdefault(
        "table",
        {},
    )

    source_rows = source_table.get(
        "rows",
        [],
    )

    values = extract_total_market_values(
        source_rows
    )

    source_table["type"] = "flat"

    source_table["headers"] = build_table_headers(
        source_period=source_period,
        period_name=period_name,
    )

    source_table["rows"] = [
        {
            "label": build_grand_total_label(
                scenario_name
            ),
            "target_metric": metric_display_name(
                metric_name
            ),
            "values": values,
        }
    ]

    prepare_total_market_chart(
        source_period=source_period,
        scenario_name=scenario_name,
    )

def extract_total_market_values(rows):
    if not isinstance(rows, list):
        return []

    preferred_labels = {
        "overall",
        "total",
        "grand total",
    }

    for row in rows:
        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip().lower()

        values = row.get("values")

        if (
            label in preferred_labels
            and isinstance(values, list)
        ):
            return deepcopy(values)

    # Fallback to the first valid row.
    for row in rows:
        if not isinstance(row, dict):
            continue

        values = row.get("values")

        if isinstance(values, list):
            return deepcopy(values)

    return []

def build_grand_total_label(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    if scenario_name.lower().endswith(
        "scenario"
    ):
        return f"Grand Total ({scenario_name})"

    return (
        f"Grand Total "
        f"({scenario_name})"
    )

def metric_display_name(
    metric_name,
):
    mapping = {
        "market_volume": "Market Volume",
        "market_share": "Market Share (%)",
    }

    return mapping.get(
        metric_name,
        metric_name.replace(
            "_",
            " ",
        ).title(),
    )

def build_table_headers(
    source_period,
    period_name,
):
    chart = source_period.get(
        "chart",
        {},
    )

    if period_name == "monthly":
        periods = chart.get(
            "months",
            [],
        )

        periods = [
            convert_month_header(period)
            for period in periods
        ]

    else:
        periods = (
            chart.get("years")
            or chart.get("months")
            or []
        )

    return [
        "Metric",
        *periods,
    ]

from datetime import datetime


def convert_month_header(
    month_label,
):
    try:
        return datetime.strptime(
            str(month_label),
            "%b-%y",
        ).strftime("%Y-%m")

    except (TypeError, ValueError):
        return month_label

def prepare_total_market_chart(
    source_period,
    scenario_name,
):
    chart = source_period.setdefault(
        "chart",
        {},
    )

    source_series = chart.get(
        "series",
        [],
    )

    if not source_series:
        return

    # Total Market normally contains one series.
    first_series = deepcopy(
        source_series[0]
    )

    first_series["label"] = clean_scenario_label(
        scenario_name
    )

    chart["series"] = [
        first_series
    ]

def clean_scenario_label(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    suffix = " scenario"

    if scenario_name.lower().endswith(
        suffix
    ):
        return scenario_name[
            :-len(suffix)
        ].strip()

    return scenario_name

def merge_total_market_table(
    destination_period,
    source_period,
):
    source_table = source_period.get(
        "table",
        {},
    )

    destination_table = (
        destination_period.setdefault(
            "table",
            {
                "type": "flat",
                "headers": deepcopy(
                    source_table.get(
                        "headers",
                        [],
                    )
                ),
                "rows": [],
            },
        )
    )

    destination_table["type"] = "flat"

    destination_table.setdefault(
        "headers",
        deepcopy(
            source_table.get(
                "headers",
                [],
            )
        ),
    )

    destination_table.setdefault(
        "rows",
        [],
    ).extend(
        deepcopy(
            source_table.get(
                "rows",
                [],
            )
        )
    )


def merge_market_distribution(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "market_distribution",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "market_distribution",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(source_period, dict):
                continue

            prepare_market_distribution_period(
                source_period=source_period,
                metric_name=metric_name,
                scenario_name=scenario_name,
                period_name=period_name,
            )

            # First scenario
            if period_name not in destination_metric:
                destination_metric[period_name] = (
                    source_period
                )
                continue

            destination_period = destination_metric[
                period_name
            ]

            merge_hierarchy_table_rows(
                destination_period=destination_period,
                source_period=source_period,
            )

            merge_chart_series(
                destination_period=destination_period,
                source_period=source_period,
            )

def prepare_market_distribution_period(
    source_period,
    metric_name,
    scenario_name,
    period_name,
):
    source_table = source_period.setdefault(
        "table",
        {},
    )

    original_rows = deepcopy(
        source_table.get(
            "rows",
            [],
        )
    )

    market_rows = remove_total_rows(
        original_rows
    )

    value_length = get_value_length(
        market_rows
    )

    if metric_name == "market_share":
        grand_total_values = [100.0] * value_length
    else:
        grand_total_values = calculate_grand_total_values(
            rows=market_rows,
        )

    target_metric = metric_display_name(
        metric_name
    )

    formatted_market_rows = []

    for row in market_rows:
        formatted_row = deepcopy(row)

        market_label = str(
            formatted_row.get("label", "")
        ).strip()

        formatted_row["label"] = build_scenario_row_label(
            label=market_label,
            scenario_name=scenario_name,
        )

        add_target_metric_to_row_tree(
            row=formatted_row,
            target_metric=target_metric,
        )

        formatted_market_rows.append(
            formatted_row
        )

    source_table["type"] = "hierarchy"

    source_table["headers"] = build_table_headers(
        source_period=source_period,
        period_name=period_name,
    )

    source_table["rows"] = [
        {
            "label": build_grand_total_label(
                scenario_name
            ),
            "target_metric": target_metric,
            "values": grand_total_values,
            "children": formatted_market_rows,
        }
    ]

    prepare_market_distribution_chart(
        source_period=source_period,
        scenario_name=scenario_name,
    )

def add_target_metric_to_row_tree(
    row,
    target_metric,
):
    if not isinstance(row, dict):
        return

    row["target_metric"] = target_metric

    children = row.get("children")

    if not isinstance(children, list):
        return

    for child in children:
        add_target_metric_to_row_tree(
            row=child,
            target_metric=target_metric,
        )

def remove_total_rows(rows):
    excluded_labels = {
        "overall",
        "total",
        "grand total",
        "all",
    }

    cleaned_rows = []

    if not isinstance(rows, list):
        return cleaned_rows

    for row in rows:

        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip().lower()

        if label in excluded_labels:
            continue

        cleaned_rows.append(
            deepcopy(row)
        )

    return cleaned_rows

def merge_hierarchy_table_rows(
    destination_period,
    source_period,
):
    source_table = source_period.get(
        "table",
        {},
    )

    destination_table = destination_period.setdefault(
        "table",
        {
            "type": "hierarchy",
            "headers": deepcopy(
                source_table.get(
                    "headers",
                    [],
                )
            ),
            "rows": [],
        },
    )

    destination_table["type"] = "hierarchy"

    if not destination_table.get("headers"):
        destination_table["headers"] = deepcopy(
            source_table.get(
                "headers",
                [],
            )
        )

    destination_table.setdefault(
        "rows",
        [],
    ).extend(
        deepcopy(
            source_table.get(
                "rows",
                [],
            )
        )
    )

def calculate_grand_total_values(rows):
    value_length = get_value_length(rows)

    totals = [0.0] * value_length

    for row in rows:

        values = row.get("values", [])

        if not isinstance(values, list):
            continue

        for index in range(
            min(value_length, len(values))
        ):
            value = values[index]

            if isinstance(value, (int, float)):
                totals[index] += value

    return [
        round(value)
        for value in totals
    ]

def get_value_length(rows):
    for row in rows:

        if not isinstance(row, dict):
            continue

        values = row.get("values")

        if isinstance(values, list):
            return len(values)

    return 0

def build_scenario_row_label(
    label,
    scenario_name,
):
    scenario_label = ensure_scenario_suffix(
        scenario_name
    )

    return f"{label} ({scenario_label})"

def build_grand_total_label(
    scenario_name,
):
    scenario_label = ensure_scenario_suffix(
        scenario_name
    )

    return f"Grand Total ({scenario_label})"

def ensure_scenario_suffix(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    if scenario_name.lower().endswith(
        "scenario"
    ):
        return scenario_name

    return f"{scenario_name}"

def prepare_market_distribution_chart(
    source_period,
    scenario_name,
):
    chart = source_period.setdefault(
        "chart",
        {},
    )

    scenario_label = clean_scenario_label(
        scenario_name
    )

    chart_series = []

    for series_item in chart.get(
        "series",
        [],
    ):

        if not isinstance(series_item, dict):
            continue

        item = deepcopy(series_item)

        label = str(
            item.get("label", "")
        ).strip()

        if not label:
            continue

        normalized_label = label.lower()

        if normalized_label in {
            "overall",
            "total",
            "grand total",
            "all",
        }:
            continue

        item["label"] = (
            f"{label} ({scenario_label})"
        )

        chart_series.append(item)

    chart["series"] = chart_series

def clean_scenario_label(
    scenario_name,
):
    scenario_name = str(
        scenario_name
    ).strip()

    suffix = " scenario"

    if scenario_name.lower().endswith(
        suffix
    ):
        return scenario_name[
            :-len(suffix)
        ].strip()

    return scenario_name

def metric_display_name(
    metric_name,
):
    mapping = {
        "market_volume": "Market Volume",
        "market_share": "Market Share (%)",
    }

    return mapping.get(
        metric_name,
        metric_name.replace(
            "_",
            " ",
        ).title(),
    )

from datetime import datetime


def build_table_headers(
    source_period,
    period_name,
):
    chart = source_period.get(
        "chart",
        {},
    )

    if period_name == "monthly":
        periods = [
            convert_month_header(month)
            for month in chart.get(
                "months",
                [],
            )
        ]

    else:
        periods = (
            chart.get("years")
            or chart.get("months")
            or []
        )

    return [
        "Metric",
        *periods,
    ]

def convert_month_header(
    month_label,
):
    try:
        return datetime.strptime(
            str(month_label),
            "%b-%y",
        ).strftime("%Y-%m")

    except (TypeError, ValueError):
        return month_label
    
def merge_flat_table_rows(
    destination_period,
    source_period,
):
    source_table = source_period.get(
        "table",
        {},
    )

    destination_table = (
        destination_period.setdefault(
            "table",
            {
                "type": "flat",
                "headers": deepcopy(
                    source_table.get(
                        "headers",
                        [],
                    )
                ),
                "rows": [],
            },
        )
    )

    destination_table["type"] = "flat"

    if not destination_table.get("headers"):
        destination_table["headers"] = deepcopy(
            source_table.get(
                "headers",
                [],
            )
        )

    destination_table.setdefault(
        "rows",
        [],
    ).extend(
        deepcopy(
            source_table.get(
                "rows",
                [],
            )
        )
    )

def merge_chart_series(
    destination_period,
    source_period,
):
    source_chart = source_period.get(
        "chart"
    )

    if not isinstance(source_chart, dict):
        return

    destination_chart = (
        destination_period.setdefault(
            "chart",
            {},
        )
    )

    for key, value in source_chart.items():

        if key == "series":
            continue

        destination_chart.setdefault(
            key,
            deepcopy(value),
        )

    destination_chart.setdefault(
        "series",
        [],
    ).extend(
        deepcopy(
            source_chart.get(
                "series",
                [],
            )
        )
    )


def merge_product_distribution(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "product_distribution",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "product_distribution",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in (
            "monthly",
            "yearly",
        ):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(
                source_period,
                dict,
            ):
                continue

            prepare_product_distribution_period(
                source_period=source_period,
                metric_name=metric_name,
                scenario_name=scenario_name,
                period_name=period_name,
            )

            if period_name not in destination_metric:

                destination_metric[
                    period_name
                ] = source_period

                continue

            destination_period = destination_metric[
                period_name
            ]

            merge_flat_table_rows(
                destination_period,
                source_period,
            )

            merge_chart_series(
                destination_period,
                source_period,
            )

def prepare_product_distribution_period(
    source_period,
    metric_name,
    scenario_name,
    period_name,
):
    source_table = source_period.setdefault(
        "table",
        {},
    )

    original_rows = deepcopy(
        source_table.get(
            "rows",
            [],
        )
    )

    product_rows = remove_total_rows(
        original_rows
    )

    value_length = get_value_length(
        product_rows
    )

    if metric_name == "market_share":
        grand_total_values = [100.0] * value_length
    else:
        grand_total_values = calculate_grand_total_values(
            rows=product_rows,
        )

    target_metric = metric_display_name(
        metric_name
    )

    formatted_rows = [
        {
            "label": build_grand_total_label(
                scenario_name
            ),
            "target_metric": target_metric,
            "values": grand_total_values,
        }
    ]

    for row in product_rows:

        product_label = str(
            row.get("label", "")
        ).strip()

        formatted_row = deepcopy(row)

        formatted_row["label"] = build_scenario_row_label(
            label=product_label,
            scenario_name=scenario_name,
        )

        formatted_row["target_metric"] = target_metric

        # Product distribution is always flat
        formatted_row.pop(
            "children",
            None,
        )

        formatted_rows.append(
            formatted_row
        )

    source_table["type"] = "flat"

    source_table["headers"] = build_table_headers(
        source_period=source_period,
        period_name=period_name,
    )

    source_table["rows"] = formatted_rows

    prepare_product_distribution_chart(
        source_period=source_period,
        scenario_name=scenario_name,
    )

def prepare_product_distribution_chart(
    source_period,
    scenario_name,
):
    chart = source_period.setdefault(
        "chart",
        {},
    )

    scenario_label = clean_scenario_label(
        scenario_name
    )

    chart_series = []

    for series in chart.get(
        "series",
        [],
    ):

        if not isinstance(series, dict):
            continue

        item = deepcopy(series)

        label = str(
            item.get(
                "label",
                ""
            )
        ).strip()

        if not label:
            continue

        if label.lower() in {
            "overall",
            "total",
            "grand total",
            "all",
        }:
            continue

        item["label"] = (
            f"{label} ({scenario_label})"
        )

        chart_series.append(item)

    chart["series"] = chart_series



def merge_market_product(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get("market_product", {})
    )

    destination = output_tabs.setdefault(
        "market_product",
        {}
    )

    for metric_name, metric_data in source.items():

        # Example:
        # metric_name = "market_volume"
        # metric_name = "market_share"

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {}
        )

        # Preserve unit at metric level
        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(period_name)

            if not isinstance(source_period, dict):
                continue

            source_table = source_period.get("table", {})
            source_rows = source_table.get("rows", [])

            # Remove synthetic rows such as Overall
            market_rows = remove_overall_rows(
                source_rows
            )

            scenario_root = build_market_product_root(
                rows=market_rows,
                scenario_name=scenario_name,
                metric_name=metric_name,
            )

            source_table["rows"] = [scenario_root]

            # Add required table metadata
            source_table["type"] = "hierarchy"

            add_target_metric_to_hierarchy(
                source_table["rows"],
                metric_name,
            )

            ensure_table_headers(
                table=source_table,
                period=period_name,
                period_data=source_period,
            )

            rename_market_product_chart_series(
                source_period=source_period,
                scenario_name=scenario_name,
            )

            # First scenario
            if period_name not in destination_metric:
                destination_metric[period_name] = source_period
                continue

            destination_period = destination_metric[
                period_name
            ]

            destination_table = destination_period.setdefault(
                "table",
                {
                    "type": "hierarchy",
                    "headers": source_table.get(
                        "headers",
                        [],
                    ),
                    "rows": [],
                },
            )

            destination_table.setdefault(
                "rows",
                []
            ).append(scenario_root)

            merge_chart_series(
                destination_period=destination_period,
                source_period=source_period,
            )
def build_market_product_root(
    rows,
    scenario_name,
    metric_name,
):
    rows = deepcopy(rows)

    value_length = get_hierarchy_value_length(rows)

    if metric_name == "market_volume":
        root_values = sum_top_level_values(
            rows,
            value_length,
        )

    elif metric_name == "market_share":
        root_values = [100.0] * value_length

    else:
        root_values = sum_top_level_values(
            rows,
            value_length,
        )

    return {
        "label": f"Grand Total ({scenario_name})",
        "target_metric": metric_display_name(
            metric_name
        ),
        "values": root_values,
        "children": rows,
    }

def remove_overall_rows(rows):
    excluded_labels = {
        "overall",
        "total",
        "grand total",
        "all",
    }

    cleaned_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        label = str(
            row.get("label", "")
        ).strip().lower()

        if label in excluded_labels:
            continue

        cleaned_rows.append(
            deepcopy(row)
        )

    return cleaned_rows

def sum_top_level_values(
    rows,
    value_length,
):
    totals = [0.0] * value_length

    for row in rows:
        values = row.get("values", [])

        if not isinstance(values, list):
            continue

        for index, value in enumerate(
            values[:value_length]
        ):
            if isinstance(value, (int, float)):
                totals[index] += value

    return [
        round(value)
        for value in totals
    ]

def add_target_metric_to_hierarchy(
    rows,
    metric_name,
):
    target_metric = metric_display_name(
        metric_name
    )

    for row in rows:
        if not isinstance(row, dict):
            continue

        row["target_metric"] = target_metric

        children = row.get("children", [])

        if isinstance(children, list):
            add_target_metric_to_hierarchy(
                children,
                metric_name,
            )
def metric_display_name(metric_name):
    mapping = {
        "market_volume": "Market Volume",
        "market_share": "Market Share",
    }

    return mapping.get(
        metric_name,
        metric_name.replace("_", " ").title(),
    )

def get_hierarchy_value_length(rows):
    for row in rows:
        if not isinstance(row, dict):
            continue

        values = row.get("values")

        if isinstance(values, list):
            return len(values)

    return 0

def ensure_table_headers(
    table,
    period,
    period_data,
):
    if table.get("headers"):
        return

    chart = period_data.get("chart", {})

    if period == "monthly":
        periods = chart.get("months", [])

    else:
        periods = chart.get("years", [])

    table["headers"] = [
        "Metric",
        *periods,
    ]
from datetime import datetime


def convert_month_header(month_label):
    try:
        return datetime.strptime(
            month_label,
            "%b-%y",
        ).strftime("%Y-%m")
    except (TypeError, ValueError):
        return month_label

def ensure_table_headers(
    table,
    period,
    period_data,
):
    if table.get("headers"):
        return

    chart = period_data.get("chart", {})

    if period == "monthly":
        periods = [
            convert_month_header(month)
            for month in chart.get("months", [])
        ]
    else:
        periods = chart.get("years", [])

    table["headers"] = [
        "Metric",
        *periods,
    ]

def rename_market_product_chart_series(
    source_period,
    scenario_name,
):
    chart = source_period.get("chart")

    if not isinstance(chart, dict):
        return

    for series_item in chart.get("series", []):
        if not isinstance(series_item, dict):
            continue

        label = str(
            series_item.get("label", "")
        ).strip()

        if label:
            series_item["label"] = (
                f"{label} ({scenario_name})"
            )
def merge_chart_series(
    destination_period,
    source_period,
):
    source_chart = source_period.get("chart")

    if not isinstance(source_chart, dict):
        return

    destination_chart = destination_period.setdefault(
        "chart",
        {}
    )

    # Preserve months, years and forecast_start_index
    for key, value in source_chart.items():
        if key == "series":
            continue

        destination_chart.setdefault(
            key,
            deepcopy(value),
        )

    destination_chart.setdefault(
        "series",
        []
    ).extend(
        deepcopy(
            source_chart.get("series", [])
        )
    )



def merge_product_market(
    output_tabs,
    market_analysis,
    scenario_name,
):
    source = deepcopy(
        market_analysis.get(
            "product_market",
            {},
        )
    )

    destination = output_tabs.setdefault(
        "product_market",
        {},
    )

    for metric_name, metric_data in source.items():

        if not isinstance(metric_data, dict):
            continue

        destination_metric = destination.setdefault(
            metric_name,
            {},
        )

        if "unit" in metric_data:
            destination_metric.setdefault(
                "unit",
                metric_data["unit"],
            )

        for period_name in ("monthly", "yearly"):

            source_period = metric_data.get(
                period_name
            )

            if not isinstance(source_period, dict):
                continue

            source_table = source_period.get(
                "table",
                {}
            )

            product_rows = remove_overall_rows(
                source_table.get(
                    "rows",
                    [],
                )
            )

            scenario_root = build_product_market_root(
                rows=product_rows,
                scenario_name=scenario_name,
                metric_name=metric_name,
            )

            source_table["type"] = "hierarchy"
            source_table["rows"] = [scenario_root]

            add_target_metric_to_hierarchy(
                source_table["rows"],
                metric_name,
            )

            ensure_table_headers(
                source_table,
                period_name,
                source_period,
            )

            rename_product_market_chart_series(
                source_period,
                scenario_name,
            )

            if period_name not in destination_metric:

                destination_metric[
                    period_name
                ] = source_period

                continue

            destination_period = destination_metric[
                period_name
            ]

            destination_table = (
                destination_period.setdefault(
                    "table",
                    {
                        "type": "hierarchy",
                        "headers": source_table.get(
                            "headers",
                            [],
                        ),
                        "rows": [],
                    },
                )
            )

            destination_table.setdefault(
                "rows",
                [],
            ).append(
                scenario_root
            )

            merge_chart_series(
                destination_period,
                source_period,
            )
def build_product_market_root(
    rows,
    scenario_name,
    metric_name,
):
    rows = deepcopy(rows)

    value_length = get_hierarchy_value_length(
        rows
    )

    if metric_name == "market_volume":

        values = sum_top_level_values(
            rows,
            value_length,
        )

    elif metric_name == "market_share":

        values = [100.0] * value_length

    else:

        values = sum_top_level_values(
            rows,
            value_length,
        )

    return {
        "label": f"Grand Total ({scenario_name})",
        "target_metric": metric_display_name(
            metric_name
        ),
        "values": values,
        "children": rows,
    }

def rename_product_market_chart_series(
    source_period,
    scenario_name,
):
    chart = source_period.get(
        "chart"
    )

    if not isinstance(chart, dict):
        return

    for series in chart.get(
        "series",
        [],
    ):

        label = str(
            series.get(
                "label",
                "",
            )
        ).strip()

        if label:

            series["label"] = (
                f"{label} ({scenario_name})"
            )

