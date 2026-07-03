from copy import deepcopy
from typing import Any, Dict, List, Optional

from fastapi import HTTPException


TAB_TOTAL_MARKET_VOLUME = "total_market_volume"
TAB_MARKET_DISTRIBUTION = "market_distribution"
TAB_PRODUCT_DISTRIBUTION = "product_distribution"
TAB_MARKET_PRODUCT = "market_product"
TAB_PRODUCT_MARKET = "product_market"

FREQUENCIES = ["monthly", "yearly"]


# =====================================================
# BASIC HELPERS
# =====================================================

def model_to_dict(obj):
    if obj is None:
        return {}

    if hasattr(obj, "model_dump"):
        return obj.model_dump()

    if hasattr(obj, "dict"):
        return obj.dict()

    return dict(obj)


def normalize_key(value: Optional[str]) -> str:
    if not value:
        return ""

    return (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("%", "")
        .replace("__", "_")
        .strip("_")
    )


TAB_ALIASES = {
    "total_market_volume": TAB_TOTAL_MARKET_VOLUME,
    "market_distribution": TAB_MARKET_DISTRIBUTION,
    "product_distribution": TAB_PRODUCT_DISTRIBUTION,
    "market_product": TAB_MARKET_PRODUCT,
    "product_market": TAB_PRODUCT_MARKET,
}


METRIC_ALIASES = {
    "market_volume": "market_volume",
    "volume": "market_volume",
    "market_share": "market_share",
    "share": "market_share",
}


def normalize_tab_name(value: str) -> str:
    key = normalize_key(value)
    return TAB_ALIASES.get(key, key)


def normalize_metric_name(value: str) -> str:
    key = normalize_key(value)
    return METRIC_ALIASES.get(key, key)


def normalize_frequency(value: str) -> str:
    key = normalize_key(value or "monthly")

    if key not in FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frequency '{value}'. Use monthly or yearly."
        )

    return key


def safe_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def is_overall(value: Optional[str]) -> bool:
    if not value:
        return False

    return value.strip().lower() in ("overall", "all")


def clean_category(value: Optional[str]) -> Optional[str]:
    if not value:
        return value

    if value.strip().upper() == "ALL":
        return "Overall"

    return value


# =====================================================
# EMPTY RESPONSE SHAPE HELPERS
# =====================================================

def empty_frequency_block() -> Dict[str, Any]:
    return {
        "monthly": {},
        "yearly": {}
    }


def empty_metric_block() -> Dict[str, Any]:
    return {
        "market_volume": empty_frequency_block(),
        "market_share": empty_frequency_block()
    }


def empty_market_analysis() -> Dict[str, Any]:
    return {
        "total_market_volume": empty_metric_block(),
        "market_distribution": empty_metric_block(),
        "product_distribution": empty_metric_block(),
        "market_product": empty_metric_block(),
        "product_market": empty_metric_block()
    }


def inactive_scenario_stub() -> Dict[str, Any]:
    return {
        "market_analysis": {
            "total_market_volume": empty_metric_block()
        }
    }


# =====================================================
# MARKET_ANALYSIS ACCESSORS
# =====================================================

def get_frequency_obj(
    market_analysis: Dict[str, Any],
    tab: str,
    metric: str,
    frequency: str
) -> Dict[str, Any]:
    tab_key = normalize_tab_name(tab)
    metric_key = normalize_metric_name(metric)
    frequency_key = normalize_frequency(frequency)

    return (
        market_analysis
        .get(tab_key, {})
        .get(metric_key, {})
        .get(frequency_key, {})
    )


def set_frequency_obj(
    market_analysis: Dict[str, Any],
    tab: str,
    metric: str,
    frequency: str,
    value: Dict[str, Any]
) -> None:
    tab_key = normalize_tab_name(tab)
    metric_key = normalize_metric_name(metric)
    frequency_key = normalize_frequency(frequency)

    market_analysis.setdefault(tab_key, {})
    market_analysis[tab_key].setdefault(metric_key, {})
    market_analysis[tab_key][metric_key][frequency_key] = value


def get_table_rows(freq_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    table = freq_obj.get("table") or {}

    rows = (
        table.get("rows")
        or table.get("data")
        or freq_obj.get("rows")
    )

    if rows is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Table rows missing in market_analysis payload",
                "expected_shape": {
                    "table": {
                        "rows": [
                            {
                                "category": "Overall",
                                "values": [100, 200]
                            }
                        ]
                    }
                },
                "received_keys": list(freq_obj.keys())
            }
        )

    return rows


def get_months(freq_obj: Dict[str, Any]) -> List[str]:
    chart = freq_obj.get("chart") or {}
    table = freq_obj.get("table") or {}

    months = (
        chart.get("months")
        or table.get("months")
        or table.get("columns")
        or []
    )

    return months


def get_forecast_start_index(freq_obj: Dict[str, Any]) -> int:
    chart = freq_obj.get("chart") or {}
    return int(chart.get("forecast_start_index", 0) or 0)


def get_month_index(months: List[str], month: str) -> int:
    if month not in months:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Month '{month}' not found",
                "available_months": months
            }
        )

    return months.index(month)


def find_overall_row(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for row in rows:
        category = row.get("category") or row.get("label")

        if is_overall(category):
            return row

    return None


# =====================================================
# EXTRACT ACTIVE MARKET_ANALYSIS
# =====================================================

def extract_market_analysis(payload) -> Dict[str, Any]:
    scenario_name = payload.scenario_name or "Base"
    incoming = payload.market_analysis

    if not incoming:
        raise HTTPException(
            status_code=400,
            detail="market_analysis payload is empty"
        )

    # Direct market_analysis
    if "total_market_volume" in incoming:
        return cleanup_overall_labels(deepcopy(incoming))

    # Full response object passed accidentally
    if "scenarios" in incoming:
        scenarios = incoming.get("scenarios") or {}

        scenario_obj = (
            scenarios.get(scenario_name)
            or scenarios.get("Base")
            or scenarios.get("BASE")
        )

        if scenario_obj and "market_analysis" in scenario_obj:
            return cleanup_overall_labels(
                deepcopy(scenario_obj["market_analysis"])
            )

    # Scenario object directly
    if "market_analysis" in incoming:
        return cleanup_overall_labels(
            deepcopy(incoming["market_analysis"])
        )

    raise HTTPException(
        status_code=400,
        detail={
            "message": "market_analysis not found",
            "available_keys": list(incoming.keys())
        }
    )


# =====================================================
# APPLY TABLE EDITS
# =====================================================

def update_table_cell(
    market_analysis: Dict[str, Any],
    selected_tab: str,
    selected_metric: str,
    edit
) -> None:
    tab_key = normalize_tab_name(selected_tab)
    metric_key = normalize_metric_name(selected_metric)
    frequency_key = normalize_frequency(edit.frequency)

    if tab_key not in market_analysis:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Tab '{selected_tab}' not found",
                "normalized_tab": tab_key,
                "available_tabs": list(market_analysis.keys())
            }
        )

    tab_obj = market_analysis[tab_key]

    if metric_key not in tab_obj:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Metric '{selected_metric}' not found",
                "normalized_metric": metric_key,
                "available_metrics": list(tab_obj.keys())
            }
        )

    metric_obj = tab_obj[metric_key]

    if frequency_key not in metric_obj:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Frequency '{edit.frequency}' not found",
                "normalized_frequency": frequency_key,
                "available_frequencies": list(metric_obj.keys())
            }
        )

    freq_obj = metric_obj[frequency_key]

    rows = get_table_rows(freq_obj)
    months = get_months(freq_obj)
    month_index = get_month_index(months, edit.month)

    edit_category = clean_category(edit.category)

    for row in rows:
        row_category = clean_category(row.get("category") or row.get("label"))

        if row_category == edit_category:
            values = row.get("values", [])

            if month_index >= len(values):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": f"Month index out of range for category '{edit.category}'",
                        "month_index": month_index,
                        "values_length": len(values)
                    }
                )

            values[month_index] = edit.value
            row["values"] = values

            if row.get("category") and row["category"].upper() == "ALL":
                row["category"] = "Overall"

            if row.get("label") and row["label"].upper() == "ALL":
                row["label"] = "Overall"

            return

    raise HTTPException(
        status_code=400,
        detail={
            "message": f"Category '{edit.category}' not found",
            "available_categories": [
                clean_category(r.get("category") or r.get("label"))
                for r in rows
            ]
        }
    )


# =====================================================
# NORMALIZE SHARE ROWS
# =====================================================

def normalize_percent_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows

    max_len = max(len(row.get("values", [])) for row in rows)

    for idx in range(max_len):
        child_rows = []

        for row in rows:
            category = row.get("category") or row.get("label") or ""

            if is_overall(category):
                continue

            child_rows.append(row)

        total = 0.0

        for row in child_rows:
            values = row.get("values", [])

            if idx < len(values):
                total += safe_float(values[idx])

        if total == 0:
            continue

        for row in child_rows:
            values = row.get("values", [])

            if idx < len(values):
                values[idx] = round(
                    (safe_float(values[idx]) / total) * 100,
                    2
                )

            row["values"] = values

        for row in rows:
            category = row.get("category") or row.get("label") or ""

            if is_overall(category):
                values = row.get("values", [])

                if idx < len(values):
                    values[idx] = 100.0

                row["values"] = values

                if row.get("category") and row["category"].upper() == "ALL":
                    row["category"] = "Overall"

                if row.get("label") and row["label"].upper() == "ALL":
                    row["label"] = "Overall"

    return rows


# =====================================================
# CHART / FREQUENCY BUILDERS
# =====================================================

def build_chart(
    months: List[str],
    values: List[float],
    forecast_start_index: int,
    label: str = "Overall"
) -> Dict[str, Any]:
    return {
        "months": months,
        "forecast_start_index": forecast_start_index,
        "series": [
            {
                "label": label,
                "history": values[:forecast_start_index],
                "forecast": values[forecast_start_index:]
            }
        ]
    }


def build_freq_obj(
    months: List[str],
    forecast_start_index: int,
    rows: List[Dict[str, Any]],
    chart_values: Optional[List[float]] = None,
    label: str = "Overall"
) -> Dict[str, Any]:
    if chart_values is None:
        overall_row = find_overall_row(rows)
        chart_values = overall_row.get("values", []) if overall_row else []

    return {
        "chart": build_chart(
            months=months,
            values=chart_values,
            forecast_start_index=forecast_start_index,
            label=label
        ),
        "table": {
            "rows": rows
        }
    }


def build_share_rows_from_volume_rows(
    volume_rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    overall_row = find_overall_row(volume_rows)

    if not overall_row:
        return []

    overall_values = overall_row.get("values", [])
    share_rows = []

    for row in volume_rows:
        category = clean_category(row.get("category") or row.get("label"))
        values = row.get("values", [])

        if is_overall(category):
            share_values = [100.0 for _ in overall_values]
        else:
            share_values = []

            for idx, value in enumerate(values):
                denominator = (
                    safe_float(overall_values[idx])
                    if idx < len(overall_values)
                    else 0
                )

                if denominator == 0:
                    share_values.append(0)
                else:
                    share_values.append(
                        round((safe_float(value) / denominator) * 100, 2)
                    )

        share_rows.append({
            "category": category,
            "values": share_values
        })

    return share_rows


# =====================================================
# REBUILD VOLUME FROM SHARE
# =====================================================

def rebuild_distribution_volume(
    market_analysis: Dict[str, Any],
    distribution_tab: str
) -> Dict[str, Any]:
    for frequency in FREQUENCIES:
        tmv_freq = get_frequency_obj(
            market_analysis,
            TAB_TOTAL_MARKET_VOLUME,
            "market_volume",
            frequency
        )

        share_freq = get_frequency_obj(
            market_analysis,
            distribution_tab,
            "market_share",
            frequency
        )

        if not tmv_freq or not share_freq:
            continue

        tmv_rows = get_table_rows(tmv_freq)
        share_rows = get_table_rows(share_freq)

        months = get_months(tmv_freq)
        forecast_start_index = get_forecast_start_index(tmv_freq)

        overall_row = find_overall_row(tmv_rows)

        if not overall_row:
            continue

        overall_values = overall_row.get("values", [])
        volume_rows = []

        for share_row in share_rows:
            category = clean_category(
                share_row.get("category") or share_row.get("label")
            )
            share_values = share_row.get("values", [])

            if is_overall(category):
                values = [round(safe_float(v), 2) for v in overall_values]
            else:
                values = []

                for idx in range(len(months)):
                    total_volume = (
                        safe_float(overall_values[idx])
                        if idx < len(overall_values)
                        else 0
                    )
                    pct = (
                        safe_float(share_values[idx])
                        if idx < len(share_values)
                        else 0
                    )

                    values.append(round(total_volume * (pct / 100), 2))

            volume_rows.append({
                "category": category,
                "values": values
            })

        set_frequency_obj(
            market_analysis,
            distribution_tab,
            "market_volume",
            frequency,
            build_freq_obj(
                months=months,
                forecast_start_index=forecast_start_index,
                rows=volume_rows
            )
        )

    return market_analysis


# =====================================================
# REBUILD SHARE FROM VOLUME
# =====================================================

def rebuild_share_from_volume(
    market_analysis: Dict[str, Any],
    tab: str
) -> Dict[str, Any]:
    for frequency in FREQUENCIES:
        volume_freq = get_frequency_obj(
            market_analysis,
            tab,
            "market_volume",
            frequency
        )

        if not volume_freq:
            continue

        rows = get_table_rows(volume_freq)
        months = get_months(volume_freq)
        forecast_start_index = get_forecast_start_index(volume_freq)

        share_rows = build_share_rows_from_volume_rows(rows)

        set_frequency_obj(
            market_analysis,
            tab,
            "market_share",
            frequency,
            build_freq_obj(
                months=months,
                forecast_start_index=forecast_start_index,
                rows=share_rows,
                chart_values=[100.0 for _ in months]
            )
        )

    return market_analysis


# =====================================================
# REBUILD MARKET-PRODUCT
# =====================================================

def rebuild_market_product(market_analysis: Dict[str, Any]) -> Dict[str, Any]:
    for frequency in FREQUENCIES:
        tmv_freq = get_frequency_obj(
            market_analysis,
            TAB_TOTAL_MARKET_VOLUME,
            "market_volume",
            frequency
        )

        md_share_freq = get_frequency_obj(
            market_analysis,
            TAB_MARKET_DISTRIBUTION,
            "market_share",
            frequency
        )

        pd_share_freq = get_frequency_obj(
            market_analysis,
            TAB_PRODUCT_DISTRIBUTION,
            "market_share",
            frequency
        )

        if not tmv_freq or not md_share_freq or not pd_share_freq:
            continue

        tmv_rows = get_table_rows(tmv_freq)
        md_rows = get_table_rows(md_share_freq)
        pd_rows = get_table_rows(pd_share_freq)

        months = get_months(tmv_freq)
        forecast_start_index = get_forecast_start_index(tmv_freq)

        overall_row = find_overall_row(tmv_rows)

        if not overall_row:
            continue

        overall_values = overall_row.get("values", [])

        mp_rows = []

        for market_row in md_rows:
            market_name = clean_category(
                market_row.get("category") or market_row.get("label")
            )

            if not market_name or is_overall(market_name):
                continue

            market_values = market_row.get("values", [])

            for product_row in pd_rows:
                product_name = clean_category(
                    product_row.get("category") or product_row.get("label")
                )

                if not product_name or is_overall(product_name):
                    continue

                product_values = product_row.get("values", [])
                values = []

                for idx in range(len(months)):
                    total_volume = (
                        safe_float(overall_values[idx])
                        if idx < len(overall_values)
                        else 0
                    )
                    market_pct = (
                        safe_float(market_values[idx])
                        if idx < len(market_values)
                        else 0
                    )
                    product_pct = (
                        safe_float(product_values[idx])
                        if idx < len(product_values)
                        else 0
                    )

                    value = total_volume * (market_pct / 100) * (product_pct / 100)
                    values.append(round(value, 2))

                mp_rows.append({
                    "category": f"{market_name} - {product_name}",
                    "values": values
                })

        overall_mp_values = []

        for idx in range(len(months)):
            overall_mp_values.append(
                round(sum(row["values"][idx] for row in mp_rows), 2)
            )

        mp_rows.insert(0, {
            "category": "Overall",
            "values": overall_mp_values
        })

        set_frequency_obj(
            market_analysis,
            TAB_MARKET_PRODUCT,
            "market_volume",
            frequency,
            build_freq_obj(
                months=months,
                forecast_start_index=forecast_start_index,
                rows=mp_rows,
                chart_values=overall_mp_values
            )
        )

        share_rows = build_share_rows_from_volume_rows(mp_rows)

        set_frequency_obj(
            market_analysis,
            TAB_MARKET_PRODUCT,
            "market_share",
            frequency,
            build_freq_obj(
                months=months,
                forecast_start_index=forecast_start_index,
                rows=share_rows,
                chart_values=[100.0 for _ in months]
            )
        )

    return market_analysis


# =====================================================
# REBUILD PRODUCT-MARKET
# =====================================================

def rebuild_product_market(market_analysis: Dict[str, Any]) -> Dict[str, Any]:
    for frequency in FREQUENCIES:
        mp_freq = get_frequency_obj(
            market_analysis,
            TAB_MARKET_PRODUCT,
            "market_volume",
            frequency
        )

        if not mp_freq:
            continue

        mp_rows = get_table_rows(mp_freq)
        months = get_months(mp_freq)
        forecast_start_index = get_forecast_start_index(mp_freq)

        product_map = {}

        for row in mp_rows:
            category = clean_category(
                row.get("category") or row.get("label")
            )

            if not category or is_overall(category):
                continue

            if " - " not in category:
                continue

            _, product_name = category.split(" - ", 1)
            product_name = clean_category(product_name)

            product_map.setdefault(product_name, [0.0] * len(months))

            values = row.get("values", [])

            for idx in range(len(months)):
                product_map[product_name][idx] += (
                    safe_float(values[idx])
                    if idx < len(values)
                    else 0
                )

        pm_rows = []
        overall_values = [0.0 for _ in months]

        for product_name, values in product_map.items():
            rounded_values = [round(v, 2) for v in values]

            for idx, value in enumerate(rounded_values):
                overall_values[idx] += value

            pm_rows.append({
                "category": product_name,
                "values": rounded_values
            })

        overall_values = [round(v, 2) for v in overall_values]

        pm_rows.insert(0, {
            "category": "Overall",
            "values": overall_values
        })

        set_frequency_obj(
            market_analysis,
            TAB_PRODUCT_MARKET,
            "market_volume",
            frequency,
            build_freq_obj(
                months=months,
                forecast_start_index=forecast_start_index,
                rows=pm_rows,
                chart_values=overall_values
            )
        )

        share_rows = build_share_rows_from_volume_rows(pm_rows)

        set_frequency_obj(
            market_analysis,
            TAB_PRODUCT_MARKET,
            "market_share",
            frequency,
            build_freq_obj(
                months=months,
                forecast_start_index=forecast_start_index,
                rows=share_rows,
                chart_values=[100.0 for _ in months]
            )
        )

    return market_analysis


# =====================================================
# CLEANUP ALL -> Overall
# =====================================================

def cleanup_overall_labels(market_analysis: Dict[str, Any]) -> Dict[str, Any]:
    for tab_obj in market_analysis.values():
        if not isinstance(tab_obj, dict):
            continue

        for metric_obj in tab_obj.values():
            if not isinstance(metric_obj, dict):
                continue

            for freq_obj in metric_obj.values():
                if not isinstance(freq_obj, dict):
                    continue

                table = freq_obj.get("table") or {}
                rows = table.get("rows") or []

                for row in rows:
                    if row.get("category") and row["category"].upper() == "ALL":
                        row["category"] = "Overall"

                    if row.get("label") and row["label"].upper() == "ALL":
                        row["label"] = "Overall"

                chart = freq_obj.get("chart") or {}
                series_list = chart.get("series") or []

                for series in series_list:
                    if series.get("label") and series["label"].upper() == "ALL":
                        series["label"] = "Overall"

    return market_analysis


# =====================================================
# RECOMPUTE DEPENDENCIES
# =====================================================

def recompute_related_tabs(
    market_analysis: Dict[str, Any],
    selected_tab: str,
    selected_metric: str
) -> Dict[str, Any]:
    market_analysis = deepcopy(market_analysis)

    tab = normalize_tab_name(selected_tab)
    metric = normalize_metric_name(selected_metric)

    # ------------------------------
    # If editing Total Market Volume
    # ------------------------------
    if tab == TAB_TOTAL_MARKET_VOLUME:
        if metric == "market_volume":
            rebuild_share_from_volume(market_analysis, TAB_TOTAL_MARKET_VOLUME)

        rebuild_distribution_volume(market_analysis, TAB_MARKET_DISTRIBUTION)
        rebuild_distribution_volume(market_analysis, TAB_PRODUCT_DISTRIBUTION)
        rebuild_market_product(market_analysis)
        rebuild_product_market(market_analysis)

    # ------------------------------
    # If editing Market Distribution
    # ------------------------------
    elif tab == TAB_MARKET_DISTRIBUTION:
        if metric == "market_share":
            for frequency in FREQUENCIES:
                share_freq = get_frequency_obj(
                    market_analysis,
                    TAB_MARKET_DISTRIBUTION,
                    "market_share",
                    frequency
                )

                if share_freq:
                    rows = get_table_rows(share_freq)
                    normalize_percent_rows(rows)

            rebuild_distribution_volume(market_analysis, TAB_MARKET_DISTRIBUTION)

        elif metric == "market_volume":
            rebuild_share_from_volume(market_analysis, TAB_MARKET_DISTRIBUTION)

        rebuild_market_product(market_analysis)
        rebuild_product_market(market_analysis)

    # ------------------------------
    # If editing Product Distribution
    # ------------------------------
    elif tab == TAB_PRODUCT_DISTRIBUTION:
        if metric == "market_share":
            for frequency in FREQUENCIES:
                share_freq = get_frequency_obj(
                    market_analysis,
                    TAB_PRODUCT_DISTRIBUTION,
                    "market_share",
                    frequency
                )

                if share_freq:
                    rows = get_table_rows(share_freq)
                    normalize_percent_rows(rows)

            rebuild_distribution_volume(market_analysis, TAB_PRODUCT_DISTRIBUTION)

        elif metric == "market_volume":
            rebuild_share_from_volume(market_analysis, TAB_PRODUCT_DISTRIBUTION)

        rebuild_market_product(market_analysis)
        rebuild_product_market(market_analysis)

    # ------------------------------
    # If editing Market-Product
    # ------------------------------
    elif tab == TAB_MARKET_PRODUCT:
        if metric == "market_volume":
            rebuild_share_from_volume(market_analysis, TAB_MARKET_PRODUCT)

        rebuild_product_market(market_analysis)

    # ------------------------------
    # If editing Product-Market
    # ------------------------------
    elif tab == TAB_PRODUCT_MARKET:
        if metric == "market_volume":
            rebuild_share_from_volume(market_analysis, TAB_PRODUCT_MARKET)

    return cleanup_overall_labels(market_analysis)


# =====================================================
# RESPONSE BUILDER
# =====================================================

def build_hiv_edit_response(
    payload,
    active_market_analysis: Dict[str, Any],
    available_scenarios: Optional[List[str]] = None
) -> Dict[str, Any]:

    active_scenario = payload.scenario_name or "Base"

    if available_scenarios is None:
        available_scenarios = ["Base", active_scenario]

    available_scenarios = list(dict.fromkeys(available_scenarios))

    scenarios = {}

    for scenario in available_scenarios:
        if scenario == active_scenario:
            scenarios[scenario] = {
                "factors": {
                    **model_to_dict(payload.factors),
                    "active_model": payload.model_type
                },
                "market_analysis": active_market_analysis
            }
        else:
            scenarios[scenario] = inactive_scenario_stub()

    return {
        "ta_name": payload.ta_name,
        "selected_filter": {
            "start_date": payload.selected_filter.start_date,
            "end_date": payload.selected_filter.end_date,
            "market": payload.selected_filter.market,
            "product": payload.selected_filter.product,
        },
        "available_scenarios": available_scenarios,
        "active_scenario": active_scenario,
        "scenarios": scenarios
    }