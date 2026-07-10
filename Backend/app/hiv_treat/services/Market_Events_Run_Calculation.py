

import copy
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.connection import get_connection
from app.hiv_treat.routes.Events_Calculation import (
    CoverageInput, EventForecastResult, EventInput, EventScope,
    ImpactedEntity, compute_event_forecast,
)

METRICS = ("market_share", "market_volume")
YEARLY_AGG = {"market_share": "average", "market_volume": "sum"}
CURVE_TYPES = ["Linear", "Exponential", "Logarithmic", "SCurve"]
TABLE = "raw_hiv_treat.forecast_outputs"
OVERALL_LABEL = "Overall"
TABS = ("market_event", "product_event", "overall_event")
BASELINE_SCENARIO = "Base"  # never written back to -- stays the canonical baseline

# product_event tab: parent = market,  child = product
# market_event  tab: parent = product, child = market
# overall_event has no breakdown at all -- it isn't in this map, and every
# place that consults it treats absence as "flat Overall series only".
TAB_HIERARCHY = {
    "product_event": ("market", "product"),
    "market_event": ("product", "market"),
}

# Static filter options returned alongside every response so the FE can
# populate the metric dropdown without a separate call.
METRIC_FILTERS = [
    {"label": "Market Share", "value": "market_share"},
    {"label": "Overall Market Volume", "value": "market_volume"},
]


# ======================================================
# 1. DB ACCESS
# ======================================================

def _parse_forecast_data(raw) -> dict:
    if isinstance(raw, str):
        return json.loads(raw) if raw.strip() else {}
    return raw or {}


def fetch_series(
    scenario_name: str,
    ta_name: str,
    metric: str,
    label_field: str,
    market: Optional[Union[str, List[str]]] = None,
    source_of_market: Optional[str] = "ALL",
    products: Optional[List[str]] = None,
) -> List[Dict]:
    """One series entry per matching row: {label, months, history, forecast,
    forecast_start_index}. `label_field` is "product" or "market" --
    whichever column each series should be labeled by.

    Each series also carries `market`/`product` (the exact row identity it
    came from) and `synthesized=False`, so downstream write-back and grid
    building can trace a computed series back to the DB row it belongs to."""
    where = ["scenario_name = %s", "ta_name = %s", "metric = %s"]
    params: List = [scenario_name, ta_name, metric]

    if market is not None:
        where.append("market = ANY(%s)" if isinstance(market, list) else "market = %s")
        params.append(market)

    if source_of_market is not None:
        where.append("source_of_market = %s")
        params.append(source_of_market)

    if products is not None:
        where.append("product = ANY(%s)")
        params.append(products)

    query = f"SELECT market, product, forecast_data FROM {TABLE} WHERE {' AND '.join(where)}"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    series = []
    for market_name, product_name, forecast_data in rows:
        data = _parse_forecast_data(forecast_data)
        history = data.get("train_values", [])
        series.append({
            "label": product_name if label_field == "product" else market_name,
            "market": market_name,
            "product": product_name,
            "synthesized": False,
            "months": data.get("months", []),
            "history": history,
            "forecast": data.get("forecast_values", []),
            "forecast_start_index": data.get("forecast_start_index", len(history)),
        })
    return series


def _fetch_overall_series(scenario_name: str, ta_name: str, metric: str) -> List[dict]:
    """Single portfolio-level row (market=ALL, product=ALL), labeled 'Overall'.
    market_share has no stored row for the whole portfolio -- it's 100% by
    definition -- so synthesize a flat baseline over market_volume's month
    horizon when that's the metric being asked for. Synthesized rows have no
    backing DB row and are flagged so write-back skips them."""
    rows = fetch_series(scenario_name, ta_name, metric,
                         label_field="market", market="ALL", products=["ALL"])
    for row in rows:
        row["label"] = OVERALL_LABEL

    if not rows and metric == "market_share":
        volume_rows = fetch_series(scenario_name, ta_name, "market_volume",
                                    label_field="market", market="ALL", products=["ALL"])
        if volume_rows:
            months = volume_rows[0]["months"]
            fsi = volume_rows[0]["forecast_start_index"]
            rows = [{
                "label": OVERALL_LABEL,
                "market": "ALL",
                "product": "ALL",
                "synthesized": True,
                "months": months,
                "history": [100.0] * fsi,
                "forecast": [100.0] * (len(months) - fsi),
                "forecast_start_index": fsi,
            }]
    return rows


def fetch_baseline(event: EventInput, metric: str) -> List[dict]:
    """The DB rows a given event actually needs for `metric`: the selected
    entity plus every impacted entity, scoped by the event's own context."""
    if event.event_scope == EventScope.PRODUCT_EVENT:
        products = [event.selected_entity] + [e.name for e in (event.impacted_entities or [])]
        return fetch_series(event.scenario_name, event.ta_name, metric,
                             label_field="product", market=event.context, products=products)

    if event.event_scope == EventScope.MARKET_EVENT:
        markets = [event.selected_entity] + [e.name for e in (event.impacted_entities or [])]
        return fetch_series(event.scenario_name, event.ta_name, metric,
                             label_field="market", market=markets, products=[event.context])

    # OVERALL_EVENT
    return _fetch_overall_series(event.scenario_name, event.ta_name, metric)


def fetch_tab_baseline(tab: str, metric: str, scenario_name: str, ta_name: str, selected_filter: dict) -> List[dict]:
    """Flat (non-hierarchical) series for the overall_event tab only -- see
    fetch_grid() for product_event/market_event, which need the full
    (market, product) cross-tab rather than a single-dimension list.

    Despite the name, this is NOT necessarily the untouched baseline: it's a
    fresh DB read, so if it runs after persist_events_to_db() has committed
    an update to the rows it queries, it naturally reflects the latest
    values."""
    if metric == "market_volume":
        return _fetch_overall_series(scenario_name, ta_name, metric)

    # overall_event
    return _fetch_overall_series(scenario_name, ta_name, metric)


# ======================================================
# 2. CURVE APPLY
# ======================================================

# market_share is a percentage and must stay within [0, 100] after events
# stack on top of each other; market_volume has no such bound.
CLAMP_BOUNDS: Dict[str, Optional[Tuple[float, float]]] = {
    "market_share": (0.0, 100.0),
    "market_volume": None,
}


def _entity_curves(result: EventForecastResult) -> Dict[str, List[float]]:
    curves = {result.selected_entity or OVERALL_LABEL: result.selected_curve}
    if result.impacted_curves:
        curves.update(result.impacted_curves)
    return curves


def _apply_curve_to_series(series: dict, curve_months: List[str], curve_values: List[float],
                            bounds: Optional[Tuple[float, float]] = None) -> dict:
    series = copy.deepcopy(series)
    month_index = {m: i for i, m in enumerate(series["months"])}
    for month, value in zip(curve_months, curve_values):
        idx = month_index.get(month)
        if idx is None or idx < series["forecast_start_index"]:
            continue  # not in this baseline, or falls in history -- never edited
        fi = idx - series["forecast_start_index"]
        if fi < len(series["forecast"]):
            new_value = round(series["forecast"][fi] + value, 4)
            if bounds is not None:
                new_value = max(bounds[0], min(bounds[1], new_value))
            series["forecast"][fi] = new_value
    return series


def apply_events_to_baseline(events: List[EventInput]) -> Dict[str, Dict[str, dict]]:
    """For each event: compute its curve, fetch every entity it touches from
    the DB ONCE (cached across events so repeated rows on the same entity
    stack instead of re-fetching/overwriting), and add the curve onto the
    forecast portion. Returns {metric: {label: series}}."""
    cache: Dict[str, Dict[str, dict]] = {metric: {} for metric in METRICS}

    for event in events:
        result = compute_event_forecast(event)
        curves = _entity_curves(result)

        for metric in METRICS:
            for label in curves:
                if label not in cache[metric]:
                    for row in fetch_baseline(event, metric):
                        cache[metric].setdefault(row["label"], row)

            bounds = CLAMP_BOUNDS.get(metric)
            for label, curve in curves.items():
                if label in cache[metric]:
                    cache[metric][label] = _apply_curve_to_series(cache[metric][label], result.months, curve, bounds)

    return cache


# ======================================================
# 2b. GRID / HIERARCHY (parent x child cross-tab views)
# ======================================================
# product_event and market_event tabs show a two-level hierarchy in their
# monthly table: one dimension as the parent row, the other as its
# children. A parent's values are simply the elementwise SUM of its
# children -- there is no separate DB row for "Truvada total" distinct from
# summing its Retail + Non-retail cells, so this is a pure display fold.
#
# The monthly CHART only plots the parent-level series. The YEARLY
# chart/table flips the grouping entirely and aggregates across parents,
# showing one series per CHILD label instead (e.g. product_event's yearly
# view shows per-product totals, not per-market).

def fetch_grid(scenario_name: str, ta_name: str, metric: str,
               markets: List[str], products: List[str]) -> List[dict]:
    """Every (market, product) cell in the current filter, for a metric that
    actually has per-combo rows (market_share). Each row keeps its own
    `market`/`product` identity so callers can group it either way."""
    if not markets or not products:
        return []
    return fetch_series(scenario_name, ta_name, metric,
                         label_field="product", market=markets, products=products)


def _sum_series(rows: List[dict]) -> dict:
    """Elementwise sum of history/forecast across series sharing the same
    months/forecast_start_index -- how a parent's total is derived from its
    children."""
    months = rows[0]["months"]
    fsi = rows[0]["forecast_start_index"]
    history = [0.0] * fsi
    forecast = [0.0] * (len(months) - fsi)
    for r in rows:
        for i, v in enumerate(r["history"][:fsi]):
            history[i] = round(history[i] + v, 4)
        for i, v in enumerate(r["forecast"][:len(forecast)]):
            forecast[i] = round(forecast[i] + v, 4)
    return {"months": months, "forecast_start_index": fsi, "history": history, "forecast": forecast}


def _overlay_cache_on_grid(grid: List[dict], cache_by_label: Dict[str, dict]) -> List[dict]:
    """Replace a grid cell's values with the post-event version for that
    exact (market, product), if the event cache computed one. Used only for
    the tab currently being edited, so its response reflects the numbers
    about to be persisted rather than the stale baseline just fetched."""
    by_cell = {(c["market"], c["product"]): c for c in cache_by_label.values()}
    overlaid = []
    for cell in grid:
        override = by_cell.get((cell["market"], cell["product"]))
        overlaid.append(copy.deepcopy(override) if override else cell)
    return overlaid


def _derive_volume_grid(share_grid: List[dict], overall_volume: List[dict]) -> List[dict]:
    """market_volume has no per-(market, product) DB row -- only one
    portfolio-level total. Per-cell volume is therefore a display-time
    derivation: that cell's market_share% applied to the current overall
    total. It is NOT persisted anywhere -- there is no row for it to live
    in. (If per-cell volume needs to be a real, independently-stored fact
    instead of this derivation, that's a schema addition to confirm first.)
    """
    if not overall_volume or not share_grid:
        return []
    overall = overall_volume[0]
    overall_month_index = {m: i for i, m in enumerate(overall["months"])}

    def _total_at(month: str) -> Optional[float]:
        oi = overall_month_index.get(month)
        if oi is None:
            return None
        if oi < overall["forecast_start_index"]:
            return overall["history"][oi]
        fi = oi - overall["forecast_start_index"]
        return overall["forecast"][fi] if fi < len(overall["forecast"]) else None

    derived = []
    for cell in share_grid:
        combined_share = cell["history"] + cell["forecast"]
        values = []
        for month, share_pct in zip(cell["months"], combined_share):
            total = _total_at(month)
            values.append(round(share_pct / 100 * total, 2) if total is not None else 0.0)
        fsi = cell["forecast_start_index"]
        derived.append({
            "market": cell["market"], "product": cell["product"],
            "months": cell["months"], "forecast_start_index": fsi,
            "history": values[:fsi], "forecast": values[fsi:],
        })
    return derived


def build_hierarchical_metric_view(grid: List[dict], parent_field: str, child_field: str,
                                    agg: str, overall_series: Optional[dict] = None) -> dict:
    """Builds the {monthly: {chart, table}, yearly: {chart, table}} shape
    for a single metric, grouped as parent (with children) in the monthly
    table, and flipped to per-child totals in the yearly view."""
    if not grid:
        return build_metric_view([], agg)

    months = grid[0]["months"]
    fsi = grid[0]["forecast_start_index"]

    by_parent: Dict[str, List[dict]] = {}
    for row in grid:
        by_parent.setdefault(row[parent_field], []).append(row)

    parent_series, monthly_rows = [], []
    for label, children_rows in by_parent.items():
        summed = _sum_series(children_rows)
        parent_series.append({"label": label, **summed})
        monthly_rows.append({
            "label": label,
            "values": summed["history"] + summed["forecast"],
            "children": [
                {"label": c[child_field], "values": c["history"] + c["forecast"]}
                for c in children_rows
            ],
        })

    overall_row = None
    if overall_series is not None:
        overall_row = {"label": OVERALL_LABEL,
                        "values": overall_series["history"] + overall_series["forecast"]}

    monthly_chart = {
        "months": [_short_month(m) for m in months],
        "forecast_start_index": fsi,
        "series": [{"label": s["label"], "history": s["history"], "forecast": s["forecast"]} for s in parent_series],
    }
    monthly_table = {
        "type": "hierarchy",
        "headers": monthly_chart["months"],
        "forecast_start_index": fsi,
        "editable": True,
        "rows": ([overall_row] if overall_row else []) + monthly_rows,
    }

    # Yearly flips the grouping: aggregate across parents, one series per
    # child label (e.g. per-product totals for product_event's yearly view).
    by_child: Dict[str, List[dict]] = {}
    for row in grid:
        by_child.setdefault(row[child_field], []).append(row)
    child_series = [{"label": label, **_sum_series(rows)} for label, rows in by_child.items()]

    yearly_chart = _to_yearly_chart(child_series, agg)
    yearly_table = _to_table(yearly_chart)

    return {
        "monthly": {"chart": monthly_chart, "table": monthly_table},
        "yearly": {"chart": yearly_chart, "table": yearly_table},
    }


def _build_hierarchy_views(tab: str, scenario_name: str, ta_name: str, selected_filter: dict,
                            cache: Optional[Dict[str, Dict[str, dict]]] = None) -> Tuple[Dict, Optional[str]]:
    """Shared by build_metrics_views() (active tab, overlays the just-
    computed cache onto the grid) and build_latest_metrics_views() (the
    other two tabs, cache=None -- a plain fresh DB read, which already
    reflects this run's changes once persist_events_to_db() has committed).
    """
    parent_field, child_field = TAB_HIERARCHY[tab]
    markets = selected_filter.get("markets", [])
    products = selected_filter.get("products", [])

    share_grid = fetch_grid(scenario_name, ta_name, "market_share", markets, products)
    if cache is not None:
        share_grid = _overlay_cache_on_grid(share_grid, cache["market_share"])

    overall_share = None
    if share_grid:
        g_months, g_fsi = share_grid[0]["months"], share_grid[0]["forecast_start_index"]
        overall_share = {"history": [100.0] * g_fsi, "forecast": [100.0] * (len(g_months) - g_fsi)}

    overall_volume_rows = _fetch_overall_series(scenario_name, ta_name, "market_volume")
    volume_grid = _derive_volume_grid(share_grid, overall_volume_rows)

    metrics_views = {
        "market_share": build_hierarchical_metric_view(
            share_grid, parent_field, child_field, YEARLY_AGG["market_share"], overall_share),
        "market_volume": build_hierarchical_metric_view(
            volume_grid, parent_field, child_field, YEARLY_AGG["market_volume"],
            overall_volume_rows[0] if overall_volume_rows else None),
    }
    forecast_start_date = _forecast_start_date_from(
        {"market_share": share_grid, "market_volume": overall_volume_rows})
    return metrics_views, forecast_start_date


# ======================================================
# 3. CHART / TABLE
# ======================================================

def _short_month(iso_date: str) -> str:
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%b-%y")


def _to_monthly_chart(series_list: List[dict]) -> dict:
    if not series_list:
        return {"months": [], "forecast_start_index": 0, "series": []}
    months = series_list[0]["months"]
    return {
        "months": [_short_month(m) for m in months],
        "forecast_start_index": series_list[0]["forecast_start_index"],
        "series": [{"label": s["label"], "history": s["history"], "forecast": s["forecast"]} for s in series_list],
    }


def _to_yearly_chart(series_list: List[dict], agg: str) -> dict:
    if not series_list:
        return {"years": [], "forecast_start_index": 0, "series": []}

    months = series_list[0]["months"]
    fsi = series_list[0]["forecast_start_index"]
    years = sorted({m[:4] for m in months})
    first_forecast_year = months[fsi][:4] if fsi < len(months) else years[-1]
    yearly_fsi = years.index(first_forecast_year)

    yearly_series = []
    for s in series_list:
        combined = s["history"] + s["forecast"]
        by_year: Dict[str, List[float]] = {}
        for m, v in zip(months, combined):
            by_year.setdefault(m[:4], []).append(v)
        values = []
        for y in years:
            vs = by_year.get(y, [])
            if not vs:
                values.append(0.0)
            elif agg == "sum":
                values.append(round(sum(vs), 4))
            else:
                values.append(round(sum(vs) / len(vs), 4))
        yearly_series.append({"label": s["label"], "history": values[:yearly_fsi], "forecast": values[yearly_fsi:]})

    return {"years": years, "forecast_start_index": yearly_fsi, "series": yearly_series}


def _to_table(chart: dict) -> dict:
    return {
        "headers": chart.get("months") or chart.get("years"),
        "forecast_start_index": chart["forecast_start_index"],
        "editable": True,
        "rows": [{"label": s["label"], "values": s["history"] + s["forecast"]} for s in chart["series"]],
    }


def build_metric_view(series_list: List[dict], agg: str) -> dict:
    monthly_chart = _to_monthly_chart(series_list)
    yearly_chart = _to_yearly_chart(series_list, agg)
    return {
        "monthly": {"chart": monthly_chart, "table": _to_table(monthly_chart)},
        "yearly": {"chart": yearly_chart, "table": _to_table(yearly_chart)},
    }


def _forecast_start_date_from(series_by_metric: Dict[str, List[dict]]) -> Optional[str]:
    for rows in series_by_metric.values():
        for row in rows:
            fsi = row["forecast_start_index"]
            if fsi < len(row["months"]):
                return row["months"][fsi]
    return None


def build_metrics_views(tab: str, scenario_name: str, ta_name: str, selected_filter: dict,
                         events: List[EventInput]) -> Tuple[Dict, Optional[str], Dict[str, Dict[str, dict]]]:
    """Builds metrics_views for the tab the FE is actively editing.

    overall_event has no market/product breakdown -- flat Overall series,
    unchanged from before. product_event and market_event render the
    parent/child hierarchy: the post-event cache is overlaid onto a
    freshly-fetched market_share grid cell-by-cell, and market_volume is
    derived from that same grid (share% x current overall total).

    Also returns the raw {metric: {label: series}} cache, so the caller can
    persist the post-event forecast values back to the DB without
    recomputing anything."""
    cache = apply_events_to_baseline(events)

    if tab not in TAB_HIERARCHY:
        # overall_event: flat, unchanged
        series_by_metric = {metric: list(cache[metric].values()) for metric in METRICS}
        metrics_views = {
            metric: build_metric_view(series_by_metric[metric], YEARLY_AGG[metric])
            for metric in METRICS
        }
        return metrics_views, _forecast_start_date_from(series_by_metric), cache

    metrics_views, forecast_start_date = _build_hierarchy_views(
        tab, scenario_name, ta_name, selected_filter, cache=cache
    )
    return metrics_views, forecast_start_date, cache


def build_latest_metrics_views(tab: str, scenario_name: str, ta_name: str,
                                selected_filter: dict) -> Tuple[Dict, Optional[str]]:
    """Same shape as build_metrics_views(), but for a tab the FE isn't
    currently editing -- no rows of its own to apply on this request.

    Deliberately a fresh DB read rather than a cached/derived value. Call it
    AFTER persist_events_to_db() has committed the active tab's updates:
    since every tab's series ultimately come from the same forecast_outputs
    rows, a fresh read here is how the just-persisted changes propagate
    into the other two tabs without recomputing any event math for them.
    Their `rows` (event configuration) stay exactly as they were -- only
    the metrics reflect the latest data."""
    if tab not in TAB_HIERARCHY:
        series_by_metric = {
            metric: fetch_tab_baseline(tab, metric, scenario_name, ta_name, selected_filter)
            for metric in METRICS
        }
        metrics_views = {
            metric: build_metric_view(series_by_metric[metric], YEARLY_AGG[metric])
            for metric in METRICS
        }
        return metrics_views, _forecast_start_date_from(series_by_metric)

    return _build_hierarchy_views(tab, scenario_name, ta_name, selected_filter, cache=None)


# ======================================================
# 4. FE ROW ADAPTER
# ======================================================
# The frontend's row shape (id, event_name, products, markets,
# impacted_markets/impacted_products, start_date, peak_percent, months,
# curve_type, factor, coverage_curve_type, coverage_factor,
# coverage_peak_percent, coverage_peak_months, source_percentages) is
# adapted into our internal EventInput here.
#
# `source_percentages` is an optional {entity_name: percent} map -- how much
# of the selected entity's gain comes out of each impacted entity. If the FE
# omits it (or sends 0s for everything), impacted entities split evenly.

def _equal_weights(names: List[str]) -> List[float]:
    if not names:
        return []
    share = round(100.0 / len(names), 4)
    weights = [share] * len(names)
    weights[-1] = round(100.0 - share * (len(names) - 1), 4)  # absorb rounding error
    return weights


def _resolve_weights(row: dict, impacted_names: List[str]) -> List[float]:
    if not impacted_names:
        return []

    source_percentages = row.get("source_percentages") or {}
    raw = [source_percentages.get(name, 0.0) for name in impacted_names]
    total = sum(raw)

    if total > 0:
        return [round(w * 100.0 / total, 4) for w in raw]  # normalize to 100
    return _equal_weights(impacted_names)  # nothing usable sent -- split evenly


def row_to_event(row: dict, tab: str, scenario_name: str, ta_name: str) -> EventInput:
    coverage = None
    if row.get("coverage_peak_percent") is not None and row.get("coverage_peak_months") is not None:
        coverage = CoverageInput(
            curve_type=row.get("coverage_curve_type", row["curve_type"]),
            factor=row.get("coverage_factor", row.get("factor", 1.0)),
            peak_pct=row["coverage_peak_percent"],
            peak_months=row["coverage_peak_months"],
        )

    common = dict(
        event_name=row["event_name"],
        event_scope=EventScope(tab),
        scenario_name=scenario_name,
        ta_name=ta_name,
        start_date=row["start_date"],
        peak_pct=row["peak_percent"],
        duration_months=row["months"],
        curve_type=row["curve_type"],
        factor=row.get("factor", 1.0),
        coverage=coverage,
    )

    if tab == "overall_event":
        return EventInput(**common)

    if tab == "market_event":
        selected_entity = row["markets"][0]
        context = row["products"][0]
        impacted_field = "impacted_markets"
    else:  # product_event
        selected_entity = row["products"][0]
        context = row["markets"][0]
        impacted_field = "impacted_products"

    impacted_names = [n for n in row.get(impacted_field, []) if n != selected_entity]
    weights = _resolve_weights(row, impacted_names)
    impacted_entities = [ImpactedEntity(name=n, weight=w) for n, w in zip(impacted_names, weights)] or None

    return EventInput(
        **common,
        context=context,
        selected_entity=selected_entity,
        impacted_entities=impacted_entities,
    )


def tab_config(tab: str, selected_filter: dict) -> dict:
    products = selected_filter.get("products", [])
    markets = selected_filter.get("markets", [])
    config = {"curve_types": CURVE_TYPES}
    if tab == "market_event":
        config.update(products=products, markets=markets, impact_markets=markets)
    elif tab == "product_event":
        config.update(products=products, markets=markets, impact_products=products)
    return config


# ======================================================
# 5. DB WRITE-BACK
# ======================================================
# After a Run Calculation, the post-event forecast values (and the exact FE
# row configuration that produced them) are written back onto their source
# rows in raw_hiv_treat.forecast_outputs -- for every scenario except
# "Base", which stays the untouched canonical baseline.
#
# Requires:
#   ALTER TABLE raw_hiv_treat.forecast_outputs
#       ADD COLUMN IF NOT EXISTS events_payload JSONB;
#
# Only market_share cells are ever written here (they're the real
# (market, product) rows this schema has). market_volume is never touched
# by product_event/market_event, since it has no per-cell row to write to --
# its grid is purely a display-time derivation (see _derive_volume_grid).

def persist_events_to_db(
    scenario_name: str,
    ta_name: str,
    rows: List[dict],
    cache: Dict[str, Dict[str, dict]],
) -> None:
    """Write the post-event forecast_values (and the FE rows that produced
    them) back onto their source DB rows. Skipped entirely for the Base
    scenario -- that stays the untouched baseline -- and skipped per-series
    for synthesized rows (e.g. synthesized Overall market_share) that have
    no backing DB row to update.

    Only `forecast_values` is overwritten in the stored JSON -- `months`,
    `train_values`, and any `factors` sub-object are left exactly as they
    were. `events_payload` stores the raw FE rows array so the event
    configuration behind a given forecast is always traceable.
    """
    if scenario_name == BASELINE_SCENARIO:
        return

    updates = [
        (metric, series)
        for metric, by_label in cache.items()
        for series in by_label.values()
        if not series.get("synthesized")
    ]
    if not updates:
        return

    events_payload = json.dumps(rows)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for metric, series in updates:
                cur.execute(
                    f"""
                    UPDATE {TABLE}
                    SET forecast_data = jsonb_set(
                            forecast_data::jsonb, '{{forecast_values}}', %s::jsonb
                        ),
                        events_payload = %s::jsonb,
                        updated_at = now()
                    WHERE scenario_name = %s AND ta_name = %s AND metric = %s
                      AND market = %s AND product = %s AND source_of_market = %s
                    """,
                    [
                        json.dumps(series["forecast"]),
                        events_payload,
                        scenario_name, ta_name, metric,
                        series["market"], series["product"], "ALL",
                    ],
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================================================
# 6. RUN CALCULATION -- one tab in, all three tabs out
# ======================================================

def run_calculation(payload: dict) -> dict:
    tab = payload["selected_tab"]
    ta_name = payload["ta_name"]
    selected_filter = payload["selected_filter"]
    scenario_name = selected_filter["scenario_name"]
    rows = payload["impact_curve_configuration"]["rows"]

    events = [row_to_event(row, tab, scenario_name, ta_name) for row in rows]
    active_metrics_views, forecast_start_date, cache = build_metrics_views(
        tab, scenario_name, ta_name, selected_filter, events
    )

    # Persist BEFORE building the other two tabs -- their metrics_views come
    # from a fresh DB read (build_latest_metrics_views), so this ordering is
    # what makes this run's changes show up on tabs the user isn't even
    # looking at right now. For the Base scenario nothing is written (see
    # persist_events_to_db), so the other tabs simply read back the
    # untouched baseline, same as before.
    persist_events_to_db(scenario_name, ta_name, rows, cache)

    # Every tab gets computed and returned so the FE can switch tabs without
    # a round trip. The active tab uses the in-memory result just computed
    # above (the exact numbers that were persisted) rather than a rescoped
    # DB refetch, so entities outside the current products/markets filter
    # (e.g. impacted entities from the event's redistribution) never get
    # silently dropped from what the user just submitted. The other two
    # tabs' own rows stay empty -- only their metrics refresh, never their
    # event configuration.
    event_tabs = {}
    for t in TABS:
        if t == tab:
            metrics_views = active_metrics_views
            tab_forecast_start_date = forecast_start_date
        else:
            metrics_views, tab_forecast_start_date = build_latest_metrics_views(
                t, scenario_name, ta_name, selected_filter
            )
        event_tabs[t] = {
            "impact_curve_configuration": {
                **tab_config(t, selected_filter),
                "forecast_start_date": tab_forecast_start_date,
                "rows": [],
            },
            "metrics_views": metrics_views,
        }

    return {
        "selected_tab": tab,
        "impact_curve_configuration": {
            **tab_config(tab, selected_filter),
            "forecast_start_date": forecast_start_date,
            "rows": rows,  # echoed back unchanged
        },
        "metric_filters": METRIC_FILTERS,
        "event_tabs": event_tabs,
    }









