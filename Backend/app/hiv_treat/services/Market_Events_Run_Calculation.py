import copy
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union

from dateutil.relativedelta import relativedelta
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
CONFIG_TABLE = "raw_hiv_treat.forecast_configurations"
OVERALL_LABEL = "Overall"
TABS = ("market_event", "product_event", "overall_event")
BASELINE_SCENARIO = "Base"  # never written back to

# product_event tab: parent = market,  child = product
# market_event  tab: parent = product, child = market
# overall_event isn't in this map -- absence means flat Overall series only
TAB_HIERARCHY = {
    "product_event": ("market", "product"),
    "market_event": ("product", "market"),
}

# market_share on product_event/market_event is offered at two switchable
# levels: a flat, non-editable parent-only rollup, and the editable
# parent>child hierarchy (see build_hierarchical_dual_view). Keys/labels
# match the FE's view_options contract. flat_key is named after the tab's
# own entity (market_event -> market_level, product_event -> product_level);
# hierarchy_key is named after the parent>child pairing shown in that tab.
TAB_VIEW_LEVELS = {
    "market_event": {
        "flat_key": "market_level",
        "flat_label": "Market Level",
        "hierarchy_key": "product_market_level",
        "hierarchy_label": "Product-Market Level",
    },
    "product_event": {
        "flat_key": "product_level",
        "flat_label": "Product Level",
        "hierarchy_key": "market_product_level",
        "hierarchy_label": "Market-Product Level",
    },
}

METRIC_FILTERS = [
    {"label": "Market Share", "value": "market_share"},
    {"label": "Overall Market Volume", "value": "market_volume"},
]

# Cache cells are addressed by (market, product) -- this is the entity's
# real identity. A plain product name or market name is NOT unique on its
# own (e.g. "Truvada" exists under every market, "Retail" exists under
# every product), so keying the cache by label alone lets two events that
# happen to touch a same-named entity under different contexts silently
# overwrite each other. See _cell_key / apply_events_to_baseline.
CacheType = Dict[str, Dict[Tuple[str, str], dict]]


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
    """One series entry per matching row. source_of_market=None returns every
    channel row instead of just the pre-aggregated 'ALL' row -- needed for
    scenarios stored split by payer/channel (see _aggregate_by_cell)."""
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

    query = (
        f"SELECT market, product, source_of_market, forecast_data "
        f"FROM {TABLE} WHERE {' AND '.join(where)}"
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    series = []
    for market_name, product_name, channel, forecast_data in rows:
        data = _parse_forecast_data(forecast_data)
        history = data.get("train_values", [])
        series.append({
            "label": product_name if label_field == "product" else market_name,
            "market": market_name,
            "product": product_name,
            "source_of_market": channel or "",
            "synthesized": False,
            "months": data.get("months", []),
            "history": history,
            "forecast": data.get("forecast_values", []),
            "forecast_start_index": data.get("forecast_start_index", len(history)),
        })
    return series


def _fetch_overall_series(scenario_name: str, ta_name: str, metric: str) -> List[dict]:
    """Portfolio row (market=ALL, product=ALL). market_share has no stored
    row for it (100% by definition), so synthesize a flat series when needed."""
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
                "source_of_market": "",
                "synthesized": True,
                "months": months,
                "history": [100.0] * fsi,
                "forecast": [100.0] * (len(months) - fsi),
                "forecast_start_index": fsi,
            }]
    return rows


def _sum_series(rows: List[dict]) -> dict:
    """Elementwise sum -- valid for genuinely additive quantities (volume)."""
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


def _average_series(rows: List[dict]) -> dict:
    """Equal-weighted average -- fallback only, when no channel weights exist."""
    months = rows[0]["months"]
    fsi = rows[0]["forecast_start_index"]
    n_hist, n_fore = fsi, len(months) - fsi
    history = [0.0] * n_hist
    forecast = [0.0] * n_fore
    for r in rows:
        for i, v in enumerate(r["history"][:n_hist]):
            history[i] += v
        for i, v in enumerate(r["forecast"][:n_fore]):
            forecast[i] += v
    k = len(rows)
    history = [round(v / k, 4) for v in history]
    forecast = [round(v / k, 4) for v in forecast]
    return {"months": months, "forecast_start_index": fsi, "history": history, "forecast": forecast}


def _fetch_channel_weights(scenario_name: str, ta_name: str, market: str,
                            channels: Set[str]) -> Dict[str, dict]:
    """Each channel's own share of the market's total, used to blend
    per-channel market_share rows into one market-wide value."""
    if not channels:
        return {}
    rows = fetch_series(scenario_name, ta_name, "market_share",
                         label_field="market", market=market, products=["ALL"],
                         source_of_market=None)
    return {r["source_of_market"]: r for r in rows if r["source_of_market"] in channels}


def _weighted_blend_series(product_rows: List[dict], weight_rows_by_channel: Dict[str, dict]) -> dict:
    """Combine per-channel market_share rows for one (market, product) cell,
    weighted by each channel's own share of the overall market. Matched by
    month label since weight/product rows aren't guaranteed aligned."""
    months = product_rows[0]["months"]
    fsi = product_rows[0]["forecast_start_index"]
    n = len(months)
    numerator = [0.0] * n
    denominator = [0.0] * n

    for row in product_rows:
        channel = row.get("source_of_market")
        weight_row = weight_rows_by_channel.get(channel)
        if weight_row is None:
            continue

        weight_by_month = {
            m: v for m, v in zip(weight_row["months"], weight_row["history"] + weight_row["forecast"])
        }
        combined_values = row["history"] + row["forecast"]

        for i, month in enumerate(months):
            if i >= len(combined_values):
                continue
            weight = weight_by_month.get(month)
            if weight is None:
                continue
            numerator[i] += weight * combined_values[i]
            denominator[i] += weight

    combined = [
        round(numerator[i] / denominator[i], 4) if denominator[i] else 0.0
        for i in range(n)
    ]
    return {
        "months": months,
        "forecast_start_index": fsi,
        "history": combined[:fsi],
        "forecast": combined[fsi:],
    }


def _aggregate_by_cell(rows: List[dict], metric: str, scenario_name: str, ta_name: str) -> List[dict]:
    """Collapse per-channel rows into one series per (market, product) cell.
    market_volume sums; market_share blends by channel weight (or averages
    as a last resort). Synthesized cells have no single backing DB row, so
    persist_events_to_db() skips writing them back."""
    grouped: Dict[Tuple[str, str], List[dict]] = {}
    for r in rows:
        grouped.setdefault((r["market"], r["product"]), []).append(r)

    aggregated = []
    for (market, product), group_rows in grouped.items():
        if len(group_rows) == 1:
            aggregated.append(group_rows[0])
            continue

        if metric == "market_volume":
            combined = _sum_series(group_rows)
        else:
            channels = {r.get("source_of_market") for r in group_rows if r.get("source_of_market")}
            weight_rows = _fetch_channel_weights(scenario_name, ta_name, market, channels)
            if weight_rows:
                combined = _weighted_blend_series(group_rows, weight_rows)
            else:
                combined = _average_series(group_rows)

        aggregated.append({
            "label": group_rows[0]["label"],
            "market": market,
            "product": product,
            "synthesized": True,
            # Needed so persist_events_to_db can write a rebalanced
            # synthesized cell back onto its real underlying rows instead
            # of silently dropping it (see _distribute_synthesized_write).
            "source_rows": group_rows,
            "_baseline_forecast": list(combined["forecast"]),
            **combined,
        })
    return aggregated


def fetch_baseline(event: EventInput, metric: str):

    if event.event_scope == EventScope.PRODUCT_EVENT:
        products = [event.selected_entity] + [
            e.name for e in (event.impacted_entities or [])
        ]

        raw = fetch_series(
            event.scenario_name,
            event.ta_name,
            metric,
            label_field="product",
            market=event.context,
            products=products,
            source_of_market=None,
        )

        return _aggregate_by_cell(
            raw,
            metric,
            event.scenario_name,
            event.ta_name,
        )

    if event.event_scope == EventScope.MARKET_EVENT:
        markets = [event.selected_entity] + [
            e.name for e in (event.impacted_entities or [])
        ]

        #
        # IMPORTANT:
        # Fetch BOTH the selected product and the ALL row.
        #
        raw = fetch_series(
            event.scenario_name,
            event.ta_name,
            metric,
            label_field="market",
            market=markets,
            products=[event.context, "ALL"],
            source_of_market=None,
        )

        return _aggregate_by_cell(
            raw,
            metric,
            event.scenario_name,
            event.ta_name,
        )

    # OVERALL_EVENT -- portfolio row is always genuinely 'ALL'
    return _fetch_overall_series(
        event.scenario_name,
        event.ta_name,
        metric,
    )


def fetch_available_entities(scenario_name: str, ta_name: str) -> Dict[str, List[str]]:
    """Every distinct product/market for this scenario/ta, excluding the
    synthetic 'ALL' row. Used for FE dropdowns and to scope chart/table views."""
    query = f"SELECT DISTINCT market, product FROM {TABLE} WHERE scenario_name = %s AND ta_name = %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, [scenario_name, ta_name])
            rows = cur.fetchall()
    finally:
        conn.close()

    markets = sorted({m for m, p in rows if m not in (None, "ALL")})
    products = sorted({p for m, p in rows if p not in (None, "ALL")})
    return {"markets": markets, "products": products}


def fetch_available_scenarios(ta_name: str) -> List[str]:
    query = f"SELECT DISTINCT scenario_name FROM {TABLE} WHERE ta_name = %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, [ta_name])
            rows = cur.fetchall()
    finally:
        conn.close()
    return sorted({r[0] for r in rows if r[0]})


def fetch_forecast_config(ta_name: str) -> Optional[dict]:
    """Training/forecast window config, keyed inside the config JSONB blob
    itself (not a real column) -- most recently updated row wins."""
    query = f"SELECT config FROM {CONFIG_TABLE} WHERE config->>'ta_name' = %s ORDER BY updated_at DESC LIMIT 1"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, [ta_name])
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    config = row[0]
    if isinstance(config, str):
        config = json.loads(config)
    return config


def fetch_available_months(ta_name: str) -> List[str]:
    """Full date range (history + forecast) for the FE's date-range picker."""
    config = fetch_forecast_config(ta_name)
    if not config:
        return []

    train_start = datetime.strptime(config["train_start_date"], "%Y-%m-%d").date()
    train_end = datetime.strptime(config["train_end_date"], "%Y-%m-%d").date()
    forecast_periods = config.get("forecast_periods", 0) or 0
    forecast_end = train_end + relativedelta(months=forecast_periods)

    months = []
    cursor = train_start
    while cursor <= forecast_end:
        months.append(cursor.strftime("%Y-%m-%d"))
        cursor += relativedelta(months=1)
    return months


def fetch_tab_baseline(tab: str, metric: str, scenario_name: str, ta_name: str, entities: dict) -> List[dict]:
    """Flat series for overall_event only -- product_event/market_event use fetch_grid()."""
    return _fetch_overall_series(scenario_name, ta_name, metric)


# ======================================================
# 2. CURVE APPLY
# ======================================================

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
                            bounds: Optional[Tuple[float, float]] = None) -> Tuple[dict, bool]:
    """Adds curve values onto the forecast portion by month label. `applied`
    is False if the curve never lands on a forecast-side month (e.g. dates
    entirely in history) -- callers use this to detect a silent no-op."""
    series = copy.deepcopy(series)
    applied = False
    month_index = {m: i for i, m in enumerate(series["months"])}
    for month, value in zip(curve_months, curve_values):
        idx = month_index.get(month)
        if idx is None or idx < series["forecast_start_index"]:
            continue
        fi = idx - series["forecast_start_index"]
        if fi < len(series["forecast"]):
            new_value = round(series["forecast"][fi] + value, 2)
            if bounds is not None:
                new_value = max(bounds[0], min(bounds[1], new_value))
            series["forecast"][fi] = new_value
            applied = True
    return series, applied


def _cell_key(event: EventInput, label: str) -> Tuple[str, str]:
    """Maps a touched entity's label to its real (market, product) identity
    under this event's context. A label alone (a product name for
    product_event, a market name for market_event) is not a unique cache
    identity -- e.g. "Truvada" exists under every market, and "Retail"
    exists under every product. Two events that touch a same-named entity
    under different contexts must land in different cache cells, or one
    silently overwrites the other."""
    if event.event_scope == EventScope.PRODUCT_EVENT:
        return (event.context, label)
    if event.event_scope == EventScope.MARKET_EVENT:
        return (label, event.context)
    return ("ALL", "ALL")


GridFetchCache = Dict[Tuple[str, str, Tuple[str, ...], Tuple[str, ...]], List[dict]]


def _grid_with_cache_overlay(
    scenario_name: str,
    ta_name: str,
    share_cache: Dict[Tuple[str, str], dict],
    markets: List[str],
    products: List[str],
    grid_fetch_cache: GridFetchCache,
) -> List[dict]:
    """Cells needed for a reconciliation pass (siblings / other products or
    markets). Prefers the in-memory value a prior event already rebalanced
    this same run over a stale DB read -- otherwise stacked events would
    each reconcile against the original baseline instead of each other's
    results.

    The raw (pre-overlay) DB grid is memoized per (markets, products) for
    the lifetime of one apply_events_to_baseline() call: several reconcile
    passes in the same run (e.g. two market_events sharing a market) would
    otherwise re-fetch the exact same rows from the DB every time."""
    fetch_key = (scenario_name, ta_name, tuple(sorted(markets)), tuple(sorted(products)))
    grid = grid_fetch_cache.get(fetch_key)
    if grid is None:
        grid = fetch_grid(scenario_name, ta_name, "market_share", markets, products)
        grid_fetch_cache[fetch_key] = grid
    return [share_cache.get((row["market"], row["product"]), row) for row in grid]


def _reconcile_product_event_market(
    cache: CacheType,
    scenario_name: str,
    ta_name: str,
    market: str,
    touched_products: List[str],
    has_explicit_redistribution: bool,
    all_products: List[str],
    grid_fetch_cache: GridFetchCache,
) -> None:
    """product_event only: the market's products must still sum to 100%.
    If impacted_entities were given, compute_event_forecast's weighting
    already conserves the total across the touched products -- so any
    leftover residual here is just rounding drift, and gets nudged back
    onto the touched cells only. If no impacted_entities were given,
    there's nothing offsetting the selected product's change, so the
    residual is spread across the untouched sibling products instead
    (the true fallback case).

    `all_products` is passed in (fetched once per run by the caller)
    instead of re-querying the DB on every reconciliation call."""
    share_cache = cache["market_share"]
    bounds = CLAMP_BOUNDS["market_share"]

    touched_rows = [
        share_cache[(market, product)]
        for product in touched_products
        if (market, product) in share_cache
    ]
    if not touched_rows:
        return

    touched_set = {r["product"] for r in touched_rows}
    sibling_rows = [
        row for row in _grid_with_cache_overlay(
            scenario_name, ta_name, share_cache, [market], all_products, grid_fetch_cache)
        if row["product"] not in touched_set
    ]

    n_forecast = len(touched_rows[0]["forecast"])
    for i in range(n_forecast):
        touched_total = sum(r["forecast"][i] for r in touched_rows if i < len(r["forecast"]))
        sibling_total = sum(r["forecast"][i] for r in sibling_rows if i < len(r["forecast"]))
        residual = 100.0 - touched_total - sibling_total
        if abs(residual) <= 1e-6:
            continue

        targets = touched_rows if has_explicit_redistribution else sibling_rows
        weight_total = sum(r["forecast"][i] for r in targets if i < len(r["forecast"]))
        if weight_total <= 0:
            continue

        for row in targets:
            if i >= len(row["forecast"]):
                continue
            weight_pct = row["forecast"][i] / weight_total
            new_value = round(row["forecast"][i] + residual * weight_pct, 4)
            if bounds is not None:
                new_value = max(bounds[0], min(bounds[1], new_value))
            row["forecast"][i] = new_value

    if not has_explicit_redistribution:
        for row in sibling_rows:
            share_cache[(row["market"], row["product"])] = row


def _rebalance_market_products(
    cache: CacheType,
    scenario_name: str,
    ta_name: str,
    selected_product: str,
    markets: List[str],
    all_products: List[str],
    grid_fetch_cache: GridFetchCache,
) -> None:

    share_cache = cache["market_share"]
    bounds = CLAMP_BOUNDS["market_share"]

    selected_rows = {
        market: share_cache[(market, selected_product)]
        for market in markets
        if (market, selected_product) in share_cache
    }

    if not selected_rows:
        return

    affected_markets = list(selected_rows.keys())

    other_rows_by_market = {
    market: [
        row
        for row in _grid_with_cache_overlay(
            scenario_name,
            ta_name,
            share_cache,
            [market],
            all_products,
            grid_fetch_cache,
        )
        if row["product"] not in (selected_product, "ALL")
    ]
    for market in affected_markets
    }   

    n_forecast = len(next(iter(selected_rows.values()))["forecast"])

    for i in range(n_forecast):

        for market in affected_markets:

            if i >= len(selected_rows[market]["forecast"]):
                continue

            selected_rows[market] = share_cache[
                (market, selected_product)
            ]

            selected_value = selected_rows[market]["forecast"][i]

            all_row = share_cache.get((market, "ALL"))

            rows = [
                r
                for r in other_rows_by_market[market]
                if i < len(r["forecast"])
            ]

            # Market share must always total 100%
            market_total = 100.0
            # target_remaining = market_total - selected_value
            if i in (0, 1):
                print("\n==============================")
                print(f"Market: {market}")
                print(f"Forecast Month Index: {i}")

                print("Selected Product:", selected_product)
                print("Selected Value:", selected_value)

                print("\nSibling Values BEFORE:")
                for r in rows:
                    print(r["product"], r["forecast"][i])

                print("Market Total BEFORE:", market_total)
            target_remaining = market_total - selected_value

            rows = [
                r
                for r in other_rows_by_market[market]
                if i < len(r["forecast"])
            ]

            current_remaining = sum(
                r["forecast"][i]
                for r in rows
            )

            if current_remaining <= 0:
                continue

            scale = target_remaining / current_remaining
            if i in (0, 1):
                print("Current Remaining:", current_remaining)
                print("Target Remaining :", target_remaining)
                print("Scale:", scale)

            for row in rows:

                new_value = round(
                    row["forecast"][i] * scale,
                    4,
                )

                if bounds is not None:
                    new_value = max(
                        bounds[0],
                        min(bounds[1], new_value),
                    )

                row["forecast"][i] = new_value
            if i in (0, 1):
                print("\nSibling Values AFTER:")
                for r in rows:
                    print(r["product"], r["forecast"][i])

                final_total = (
                    selected_rows[market]["forecast"][i]
                    + sum(r["forecast"][i] for r in rows)
                )

                print("Final Market Total:", final_total)

                print("Final Market Total:", final_total)
            #
            # Refresh ALL row after redistribution.
            #
            if (
                all_row is not None
                and i < len(all_row["forecast"])
            ):
                total = selected_rows[market]["forecast"][i]

                for row in rows:
                    total += row["forecast"][i]

                all_row["forecast"][i] = round(total, 4)

                share_cache[(market, "ALL")] = all_row

    #
    # Push updated sibling rows back into cache.
    #
    for market, rows in other_rows_by_market.items():
        for row in rows:
            share_cache[(row["market"], row["product"])] = row


def apply_events_to_baseline(events: List[EventInput], entities: Dict[str, List[str]]) -> CacheType:
    """For each event: compute its curve, fetch every touched entity once
    (cached so repeats stack instead of overwriting), add curve onto the
    forecast.

    The cache is keyed by (market, product) -- see _cell_key -- so a
    same-named product/market touched under two different contexts can
    never collide.

    Reconciliation is deferred until every event's curve has been applied
    (two-phase: apply, then reconcile), instead of running after each
    individual event. Reconciling immediately after each event means a
    later event's rebalance pass fights the earlier one over the same
    cells, redistributing against a half-updated grid instead of the
    combined effect of all events. Reconciliation work for the same
    market (product_event) or same product (market_event) is also merged
    across events so the balance pass runs once per cell, not once per
    event:
      - product_event: touched products must still sum to 100% within the
        market -- see _reconcile_product_event_market.
      - market_event: only the selected product should move between
        markets; every other product's total across the affected markets
        must be preserved, not just each market's row total -- see
        _rebalance_market_products.
      - overall_event: single "Overall" row, nothing to reconcile.

    `entities` (the full product/market universe) is fetched once by the
    caller and passed in, and a grid_fetch_cache is shared across every
    reconciliation call this run -- both avoid re-hitting the DB for data
    that's already been read once this call.

    Returns {metric: {(market, product): series}}."""
    cache: CacheType = {metric: {} for metric in METRICS}
    all_products = entities["products"]
    grid_fetch_cache: GridFetchCache = {}

    # (scenario_name, ta_name, market) -> accumulated touched products / flag
    product_event_work: Dict[Tuple[str, str, str], Dict] = {}
    # (scenario_name, ta_name, product) -> accumulated touched markets
    market_event_work: Dict[Tuple[str, str, str], Dict] = {}

    for event in events:
        result = compute_event_forecast(event)
        curves = _entity_curves(result)
        event_touched_forecast = False
        keys_by_label = {label: _cell_key(event, label) for label in curves}

        for metric in METRICS:
            needs_fetch = any(key not in cache[metric] for key in keys_by_label.values())
            if needs_fetch:
                baseline_rows = fetch_baseline(event, metric)

                if (
                    metric == "market_share"
                    and event.event_scope == EventScope.MARKET_EVENT
                ):
                    print("\n========== MARKET_SHARE BASELINE ==========")

                    for row in baseline_rows:
                        print(
                            f"Market={row['market']}, "
                            f"Product={row['product']}"
                        )
                        print("History :", row["history"])
                        print("Forecast:", row["forecast"])
                        print()

                for row in baseline_rows:
                    cache[metric].setdefault(
                        (row["market"], row["product"]),
                        row,
                    )

            bounds = CLAMP_BOUNDS.get(metric)
            for label, curve in curves.items():
                key = keys_by_label[label]
                if key not in cache[metric]:
                    continue
                cache[metric][key], applied = _apply_curve_to_series(
                    cache[metric][key], result.months, curve, bounds)
                event_touched_forecast = event_touched_forecast or applied

        if not event_touched_forecast:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Event '{event.event_name}' (start_date={event.start_date}, "
                    f"duration_months={event.duration_months}) does not overlap "
                    f"the forecast window for any entity it targets -- every "
                    f"affected month falls in history and cannot be edited. "
                    f"Check that start_date is on or after this scenario's "
                    f"forecast_start_date."
                ),
            )

        if event.event_scope == EventScope.PRODUCT_EVENT:
            work_key = (event.scenario_name, event.ta_name, event.context)
            entry = product_event_work.setdefault(
                work_key, {"touched_products": set(), "has_explicit_redistribution": False})
            entry["touched_products"].update(curves.keys())
            entry["has_explicit_redistribution"] = (
                entry["has_explicit_redistribution"] or bool(event.impacted_entities))
        elif event.event_scope == EventScope.MARKET_EVENT:
            work_key = (event.scenario_name, event.ta_name, event.context)
            entry = market_event_work.setdefault(work_key, {"markets": set()})
            entry["markets"].update(curves.keys())

    # Reconcile once every event's curve has landed in the cache.
    for (scenario_name, ta_name, market), entry in product_event_work.items():
        _reconcile_product_event_market(
            cache, scenario_name, ta_name, market,
            touched_products=list(entry["touched_products"]),
            has_explicit_redistribution=entry["has_explicit_redistribution"],
            all_products=all_products,
            grid_fetch_cache=grid_fetch_cache,
        )
    for (scenario_name, ta_name, product), entry in market_event_work.items():
        _rebalance_market_products(
            cache, scenario_name, ta_name,
            selected_product=product,
            markets=list(entry["markets"]),
            all_products=all_products,
            grid_fetch_cache=grid_fetch_cache,
        )

    return cache


# ======================================================
# 2b. GRID / HIERARCHY (parent x child cross-tab views)
# ======================================================
# A parent's monthly values are the elementwise SUM of its children (pure
# display fold -- no separate DB row for the parent total). Monthly chart
# plots parent-level series only; yearly flips to per-child totals.

def fetch_grid(scenario_name: str, ta_name: str, metric: str,
               markets: List[str], products: List[str]) -> List[dict]:
    """Every (market, product) cell in the current universe. source_of_market=None
    + _aggregate_by_cell since a cell may be split across channels."""
    if not markets or not products:
        return []
    raw = fetch_series(scenario_name, ta_name, metric,
                        label_field="product", market=markets, products=products,
                        source_of_market=None)
    return _aggregate_by_cell(raw, metric, scenario_name, ta_name)


def _overlay_cache_on_grid(grid: List[dict], cache_by_cell: Dict[Tuple[str, str], dict]) -> List[dict]:
    """Replace a grid cell with its post-event version, for the tab being
    edited. The cache is already keyed by (market, product) -- the same
    identity used for grid cells -- so no re-derivation between two
    different identities is needed here."""
    overlaid = []
    for cell in grid:
        override = cache_by_cell.get((cell["market"], cell["product"]))
        overlaid.append(copy.deepcopy(override) if override else cell)
    return overlaid

# def _recalculate_all_rows(grid: List[dict]) -> List[dict]:

#     grouped = {}

#     for row in grid:
#         grouped.setdefault(row["market"], []).append(row)

#     output = []

#     for market, rows in grouped.items():

#         all_row = next(
#             (r for r in rows if r["product"] == "ALL"),
#             None,
#         )

#         normal_rows = [
#             r
#             for r in rows
#             if r["product"] != "ALL"
#         ]

#         if (
#             all_row is not None
#             and normal_rows
#         ):

#             for i in range(len(all_row["forecast"])):

#                 all_row["forecast"][i] = round(
#                     sum(
#                         r["forecast"][i]
#                         for r in normal_rows
#                     ),
#                     4,
#                 )

#         output.extend(normal_rows)

#         if all_row:
#             output.append(all_row)

#     return output

def _derive_volume_grid(
    share_grid: List[dict],
    market_share_all: List[dict],
    overall_volume: List[dict],
) -> List[dict]:
    """market_volume has no per-cell DB row -- derived at display time as
    cell's market_share% applied to the current overall total. Not persisted."""
    if not overall_volume or not share_grid:
        return []
    overall = overall_volume[0]
    print("\n========== _derive_volume_grid ==========")
    print("Overall Volume History:", overall["history"])
    print("Overall Volume Forecast:", overall["forecast"])
    overall_month_index = {m: i for i, m in enumerate(overall["months"])}
    market_share_lookup = {}

    for row in market_share_all:
        market_share_lookup[row["market"]] = {
            "months": row["months"],
            "forecast_start_index": row["forecast_start_index"],
            "values": row["history"] + row["forecast"],
        }

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
        print(f"\nMarket={cell['market']} Product={cell['product']}")
        print("Share:", cell["history"] + cell["forecast"])
        combined_share = cell["history"] + cell["forecast"]
        values = []
        for month, share_pct in zip(cell["months"], combined_share):
            total = _total_at(month)
            if total is not None:
                market_share_info = market_share_lookup[cell["market"]]

                market_idx = market_share_info["months"].index(month)

                market_share = market_share_info["values"][market_idx]

                market_volume = total * market_share / 100

                volume = round(
                    market_volume * share_pct / 100,
                    2,
                )

                print(
                    f"Month={month} "
                    f"MarketShare={market_share:.2f}% "
                    f"ProductShare={share_pct:.2f}% "
                    f"Overall={total:.2f} "
                    f"MarketVolume={market_volume:.2f} "
                    f"ProductVolume={volume:.2f}"
                )

                values.append(volume)
            else:
                values.append(0.0)
        fsi = cell["forecast_start_index"]
        derived.append({
            "market": cell["market"], "product": cell["product"],
            "months": cell["months"], "forecast_start_index": fsi,
            "history": values[:fsi], "forecast": values[fsi:],
        })
    print("\n========== Derived Market Totals ==========")

    market_totals = _group_series_by_field(derived, "market")

    for m in market_totals:
        print(
            m["label"],
            m["history"] + m["forecast"]
        )

    print("\n========== Derived Product Totals ==========")

    product_totals = _group_series_by_field(derived, "product")

    for p in product_totals:
        print(
            p["label"],
            p["history"] + p["forecast"]
        )
    return derived


def _clip_series_to_range(series: dict, start_date: Optional[str], end_date: Optional[str]) -> dict:
    """Trims months/history/forecast to selected_filter's window, display only.
    Must run AFTER events are applied against the full baseline, so event
    matching and the "did this touch a forecast month" check aren't broken
    by an out-of-window filter. forecast_start_index recomputed relative to
    the clipped window."""
    months = series["months"]
    if not months:
        return series

    lo = 0
    hi = len(months)
    if start_date:
        lo = next((i for i, m in enumerate(months) if m >= start_date), len(months))
    if end_date:
        hi = next((i for i, m in enumerate(months) if m > end_date), len(months))

    combined = series["history"] + series["forecast"]
    clipped_months = months[lo:hi]
    clipped_values = combined[lo:hi]
    new_fsi = max(0, min(len(clipped_months), series["forecast_start_index"] - lo))

    return {
        **series,
        "months": clipped_months,
        "history": clipped_values[:new_fsi],
        "forecast": clipped_values[new_fsi:],
        "forecast_start_index": new_fsi,
    }


def _clip_series_list(series_list: List[dict], start_date: Optional[str], end_date: Optional[str]) -> List[dict]:
    return [_clip_series_to_range(s, start_date, end_date) for s in series_list]


def _to_yearly_share_from_volume(volume_grid: List[dict], child_field: str,
                                  overall_volume: Optional[dict]) -> dict:
    """Yearly share = sum(child volume in year) / sum(portfolio volume in year).
    Not an average of monthly percentages -- that silently assumes equal
    monthly totals, which understates/overstates events touching only some months."""
    if not volume_grid or not overall_volume:
        return {"years": [], "forecast_start_index": 0, "series": []}

    months = volume_grid[0]["months"]
    fsi = volume_grid[0]["forecast_start_index"]
    years = sorted({m[:4] for m in months})
    first_forecast_year = months[fsi][:4] if fsi < len(months) else years[-1]
    yearly_fsi = years.index(first_forecast_year)

    overall_combined = overall_volume["history"] + overall_volume["forecast"]
    overall_by_year: Dict[str, float] = {}
    for m, v in zip(overall_volume["months"], overall_combined):
        overall_by_year[m[:4]] = overall_by_year.get(m[:4], 0.0) + v

    by_child: Dict[str, List[dict]] = {}
    for row in volume_grid:
        by_child.setdefault(row[child_field], []).append(row)

    yearly_series = []
    for label, rows in by_child.items():
        combined_by_month: Dict[str, float] = {}
        for r in rows:
            r_combined = r["history"] + r["forecast"]
            for m, v in zip(r["months"], r_combined):
                combined_by_month[m] = combined_by_month.get(m, 0.0) + v
        by_year: Dict[str, float] = {}
        for m, v in combined_by_month.items():
            by_year[m[:4]] = by_year.get(m[:4], 0.0) + v

        values = []
        for y in years:
            child_total = by_year.get(y, 0.0)
            overall_total = overall_by_year.get(y, 0.0)
            values.append(round(child_total / overall_total * 100, 2) if overall_total else 0.0)
        yearly_series.append({"label": label, "history": values[:yearly_fsi], "forecast": values[yearly_fsi:]})

    return {"years": years, "forecast_start_index": yearly_fsi, "series": yearly_series}


def _monthly_parent_child_view(
    grid,
    parent_field,
    child_field,
    overall_series,
    metric,
    volume_grid=None,
):
    """
    Groups grid cells into parent-with-children rows for the monthly view.

    For market_volume:
        Parent = sum(children)

    For market_share:
        Parent = 100%
        Children are the values supplied in the grid.
        (If needed later, these child values can be recomputed from
        volume_grid exactly like the old build_product_market().)
    """
    months = grid[0]["months"]
    fsi = grid[0]["forecast_start_index"]

    by_parent: Dict[str, List[dict]] = {}
    for row in grid:
        by_parent.setdefault(row[parent_field], []).append(row)

    parent_series = []
    hierarchy_rows = []

    for label, children_rows in by_parent.items():

        if metric == "market_share":

            parent_history = [100.0] * fsi
            parent_forecast = [100.0] * (len(months) - fsi)
            parent_values = parent_history + parent_forecast

            volume_children = [
                r for r in volume_grid
                if r[parent_field] == label
            ]

            parent_volume = _sum_series(volume_children)
            parent_totals = parent_volume["history"] + parent_volume["forecast"]

            print("\n==============================")
            print("Metric :", metric)
            print("Parent :", label)
            print("Parent Field :", parent_field)
            print("Child Field  :", child_field)

            print("\nVolume Children:")

            for r in volume_children:
                print(
                    f"{r[parent_field]} | {r[child_field]}",
                    r["history"] + r["forecast"]
                )

            print("\nParent Totals:")
            print(parent_totals)

            children = []

            for child in volume_children:

                child_volumes = child["history"] + child["forecast"]

                shares = []

                for cv, pv in zip(child_volumes, parent_totals):
                    shares.append(round(cv / pv * 100, 2) if pv else 0.0)

                print(
                    f"\nChild: {child[child_field]}",
                    "\nVolumes:", child_volumes,
                    "\nShares :", shares
                )

                children.append({
                    "label": child[child_field],
                    "values": shares,
                })

        else:

            summed = _sum_series(children_rows)

            parent_history = summed["history"]
            parent_forecast = summed["forecast"]
            parent_values = parent_history + parent_forecast

            children = [
                {
                    "label": child[child_field],
                    "values": child["history"] + child["forecast"],
                }
                for child in children_rows
            ]

        parent_series.append({
            "label": label,
            "history": parent_history,
            "forecast": parent_forecast,
        })

        hierarchy_rows.append({
            "label": label,
            "values": parent_values,
            "children": children,
        })

    overall_row = None
    if overall_series is not None:
        overall_row = {
            "label": OVERALL_LABEL,
            "values": overall_series["history"] + overall_series["forecast"],
        }

    monthly_chart = {
        "months": months,
        "forecast_start_index": fsi,
        "series": [
            {
                "label": s["label"],
                "history": s["history"],
                "forecast": s["forecast"],
            }
            for s in parent_series
        ],
    }

    return monthly_chart, hierarchy_rows, overall_row


def _group_series_by_field(grid: List[dict], field: str) -> List[dict]:

    print("\n========== _group_series_by_field ==========")
    print("Grouping by:", field)

    grouped: Dict[str, List[dict]] = {}

    for row in grid:
        print(
            f"Input -> Market={row['market']}, "
            f"Product={row['product']}"
        )
        print(row["history"] + row["forecast"])

        grouped.setdefault(row[field], []).append(row)

    print("\nGrouped Values:")

    result = []

    for label, rows in grouped.items():

        print(f"\nGroup: {label}")

        for r in rows:
            print(
                f"  {r['market']} | {r['product']}"
            )
            print("   ", r["history"] + r["forecast"])

        summed = _sum_series(rows)

        print("Summed:")
        print(summed["history"] + summed["forecast"])

        result.append(
            {
                "label": label,
                **summed,
            }
        )

    return result


def _monthly_flat_view(
    grid: List[dict],
    child_field: str,
    overall_volume_series: Optional[dict] = None,
) -> Tuple[dict, List[dict]]:
    """Monthly flat roll-up: groups grid cells by the tab's own entity
    (child_field), summed across the other dimension -- e.g. market_event's
    Market Level view sums each market's value across all products. This is
    a genuinely different grouping from _monthly_parent_child_view's
    hierarchy chart (grouped by parent_field), not just the same rows
    re-labeled without children, so it needs its own chart.
    Returns (monthly_chart, flat_rows)."""
    print("\n========== _monthly_flat_view ==========")
    print("Child field:", child_field)

    months = grid[0]["months"]
    fsi = grid[0]["forecast_start_index"]
    if overall_volume_series is None:
        print("\nUsing _group_series_by_field()")
        child_series = _group_series_by_field(grid, child_field)
    else:
        print("\nUsing volume-based market share calculation")

        grouped = _group_series_by_field(grid, child_field)

        overall = overall_volume_series["history"] + overall_volume_series["forecast"]

        child_series = []

        for g in grouped:

            values = g["history"] + g["forecast"]

            shares = []

            print(f"\nProcessing {g['label']}")

            for v, total in zip(values, overall):
                share = round((v / total) * 100, 2) if total else 0.0
                shares.append(share)

            print("Volume :", values)
            print("Overall:", overall)
            print("Share  :", shares)

            child_series.append({
                "label": g["label"],
                "months": g["months"],
                "forecast_start_index": g["forecast_start_index"],
                "history": shares[:g["forecast_start_index"]],
                "forecast": shares[g["forecast_start_index"]:],
            })
    print("\nResult from _group_series_by_field:")
    for s in child_series:
        print(
            f"{s['label']}:",
            s["history"] + s["forecast"]
        )

    monthly_chart = {
        "months": months,
        "forecast_start_index": fsi,
        "series": [{"label": s["label"], "history": s["history"], "forecast": s["forecast"]} for s in child_series],
    }
    flat_rows = [{"label": s["label"], "values": s["history"] + s["forecast"]} for s in child_series]
    print("\nFinal Flat Rows:")
    for r in flat_rows:
        print(r)
    return monthly_chart, flat_rows


def _yearly_cell_shares(volume_grid: List[dict], parent_field: str, child_field: str,
                         overall_volume: Optional[dict]) -> List[dict]:
    """Yearly volume share for each individual (parent, child) grid cell,
    with NO grouping by child label. volume_grid already has exactly one
    row per (market, product) cell, so each row is already the correct
    atomic unit -- grouping by child label alone (as
    _to_yearly_share_from_volume does, by design, for genuinely unique
    labels) would silently merge same-named children across different
    parents here (e.g. "Retail" exists under every product), the same
    identity pitfall documented on CacheType / _cell_key."""
    if not volume_grid or not overall_volume:
        return []

    months = volume_grid[0]["months"]
    fsi = volume_grid[0]["forecast_start_index"]
    years = sorted({m[:4] for m in months})
    first_forecast_year = months[fsi][:4] if fsi < len(months) else years[-1]
    yearly_fsi = years.index(first_forecast_year)

    overall_combined = overall_volume["history"] + overall_volume["forecast"]
    overall_by_year: Dict[str, float] = {}
    for m, v in zip(overall_volume["months"], overall_combined):
        overall_by_year[m[:4]] = overall_by_year.get(m[:4], 0.0) + v

    cell_rows = []
    for row in volume_grid:
        combined = row["history"] + row["forecast"]
        by_year: Dict[str, float] = {}
        for m, v in zip(row["months"], combined):
            by_year[m[:4]] = by_year.get(m[:4], 0.0) + v

        values = []
        for y in years:
            cell_total = by_year.get(y, 0.0)
            overall_total = overall_by_year.get(y, 0.0)
            values.append(round(cell_total / overall_total * 100, 2) if overall_total else 0.0)

        cell_rows.append({
            "parent": row[parent_field], "child": row[child_field],
            "history": values[:yearly_fsi], "forecast": values[yearly_fsi:],
        })
    return cell_rows


def _yearly_cell_totals(grid: List[dict], parent_field: str, child_field: str, agg: str) -> List[dict]:
    """Yearly aggregate (sum or average, per `agg`) for each individual
    (parent, child) grid cell, with NO grouping by child label -- the
    market_volume companion to _yearly_cell_shares, for metrics that
    aggregate directly instead of as a percentage of an overall total."""
    if not grid:
        return []

    months = grid[0]["months"]
    fsi = grid[0]["forecast_start_index"]
    years = sorted({m[:4] for m in months})
    first_forecast_year = months[fsi][:4] if fsi < len(months) else years[-1]
    yearly_fsi = years.index(first_forecast_year)

    cell_rows = []
    for row in grid:
        combined = row["history"] + row["forecast"]
        by_year: Dict[str, List[float]] = {}
        for m, v in zip(row["months"], combined):
            by_year.setdefault(m[:4], []).append(v)

        values = []
        for y in years:
            vs = by_year.get(y, [])
            if not vs:
                values.append(0.0)
            elif agg == "sum":
                values.append(round(sum(vs), 2))
            else:
                values.append(round(sum(vs) / len(vs), 2))

        cell_rows.append({
            "parent": row[parent_field], "child": row[child_field],
            "history": values[:yearly_fsi], "forecast": values[yearly_fsi:],
        })
    return cell_rows


def _yearly_parent_child_view(
    volume_grid: Optional[List[dict]],
    parent_field: str,
    child_field: str,
    overall_volume_series: Optional[dict],
) -> Tuple[dict, List[dict]]:

    if not volume_grid:
        return {
            "years": [],
            "forecast_start_index": 0,
            "series": [],
        }, []

    years = sorted({m[:4] for m in volume_grid[0]["months"]})

    fsi = volume_grid[0]["forecast_start_index"]
    first_forecast_year = (
        volume_grid[0]["months"][fsi][:4]
        if fsi < len(volume_grid[0]["months"])
        else years[-1]
    )
    yearly_fsi = years.index(first_forecast_year)

    #
    # Group rows by parent
    #
    by_parent: Dict[str, List[dict]] = {}

    for row in volume_grid:
        by_parent.setdefault(row[parent_field], []).append(row)

    parent_series = []
    hierarchy_rows = []

    for label, children_rows in by_parent.items():

        #
        # Parent is always 100%
        #
        parent_history = [100.0] * yearly_fsi
        parent_forecast = [100.0] * (len(years) - yearly_fsi)

        parent_series.append({
            "label": label,
            "history": parent_history,
            "forecast": parent_forecast,
        })

        #
        # Parent yearly volumes
        #
        parent_volume = _to_yearly_chart(
            [{
                "label": label,
                **_sum_series(children_rows),
            }],
            "sum",
        )["series"][0]

        parent_totals = (
            parent_volume["history"]
            + parent_volume["forecast"]
        )

        children = []

        for child in children_rows:

            child_yearly = _to_yearly_chart(
                [{
                    "label": child[child_field],
                    **child,
                }],
                "sum",
            )["series"][0]

            child_totals = (
                child_yearly["history"]
                + child_yearly["forecast"]
            )

            shares = []

            for cv, pv in zip(child_totals, parent_totals):
                shares.append(
                    round(cv / pv * 100, 2)
                    if pv
                    else 0.0
                )

            children.append({
                "label": child[child_field],
                "values": shares,
            })

        hierarchy_rows.append({
            "label": label,
            "values": parent_history + parent_forecast,
            "children": children,
        })

    parent_yearly = {
        "years": years,
        "forecast_start_index": yearly_fsi,
        "series": parent_series,
    }

    return parent_yearly, hierarchy_rows

def _yearly_overall_row(years: List[str], metric: str,
                         overall_volume_series: Optional[dict] = None) -> Optional[dict]:
    """Overall row for a yearly table -- the yearly counterpart of the
    Overall row _monthly_parent_child_view derives from `overall_series`.
    market_share's overall is always 100% by definition (there's no
    per-year computation needed, same as the synthesized monthly
    overall_share); market_volume's overall is the actual yearly total,
    aggregated from the portfolio (ALL/ALL) series the same way
    _to_yearly_chart aggregates every other series."""
    if not years:
        return None
    if metric == "market_share":
        return {"label": OVERALL_LABEL, "values": [100.0] * len(years)}

    if overall_volume_series is None:
        return None
    yearly = _to_yearly_chart([{"label": OVERALL_LABEL, **overall_volume_series}], YEARLY_AGG["market_volume"])
    if not yearly["series"]:
        return None
    s = yearly["series"][0]
    return {"label": OVERALL_LABEL, "values": s["history"] + s["forecast"]}


def build_hierarchical_dual_view(tab: str, metric: str, grid: List[dict], parent_field: str, child_field: str,
                                  agg: str, overall_series: Optional[dict] = None,
                                  volume_grid: Optional[List[dict]] = None,
                                  overall_volume_series: Optional[dict] = None) -> dict:
    """Flat/hierarchy dual view (view_options + selected_view envelope) for
    one metric within a hierarchy tab (product_event / market_event). Both
    market_share and market_volume go through this, matching the FE's
    Market/Product level switcher contract:
      - hierarchy_key groups by the tab's parent entity, nesting the child
        entity underneath (e.g. market_event nests markets under each
        product) -- table only, the chart never carries child granularity.
      - flat_key groups by the tab's OWN entity (child_field), summed
        across the other dimension (e.g. market_event's flat "Market
        Level" view sums each market's value across every product). This
        is a genuinely different grouping from the hierarchy view's
        top-level rows, not a re-labeling of them -- see _monthly_flat_view.
    market_share derives its values as a share of volume (volume_grid /
    overall_volume_series are required for it); market_volume aggregates
    directly off `grid`."""
    levels = TAB_VIEW_LEVELS[tab]
    view_options = [
        {"label": levels["flat_label"], "value": levels["flat_key"]},
        {"label": levels["hierarchy_label"], "value": levels["hierarchy_key"]},
    ]

    if not grid:
        empty_chart = {"months": [], "forecast_start_index": 0, "series": []}
        empty_side = {
            "view_options": view_options,
            "selected_view": levels["hierarchy_key"],
            levels["flat_key"]: {
                "chart": empty_chart,
                "table": {"type": "flat", "headers": [], "forecast_start_index": 0,
                          "editable": False, "rows": []},
            },
            levels["hierarchy_key"]: {
                "chart": empty_chart,
                "table": {"type": "hierarchy", "headers": [], "forecast_start_index": 0,
                          "editable": True, "rows": []},
            },
        }
        return {"monthly": copy.deepcopy(empty_side), "yearly": copy.deepcopy(empty_side)}

    fsi = grid[0]["forecast_start_index"]

    # ---- monthly: hierarchy chart groups by parent; flat chart groups by
    # child, summed across parents -- two different series sets, not one
    # chart shared between the levels ----
    print("\n================ build_hierarchical_dual_view ================")
    print("Tab    :", tab)
    print("Metric :", metric)
    print("Parent :", parent_field)
    print("Child  :", child_field)

    if metric == "market_share":
        print("\nGrid (share):")
        for r in grid:
            print(
                r[parent_field],
                r[child_field],
                r["history"] + r["forecast"]
            )

        print("\nVolume Grid:")
        for r in volume_grid:
            print(
                r[parent_field],
                r[child_field],
                r["history"] + r["forecast"]
            )
    monthly_parent_chart, hierarchy_rows, overall_row = _monthly_parent_child_view(
            grid,
            parent_field,
            child_field,
            overall_series,
            metric,
            volume_grid,
        )
    if metric == "market_share":
        monthly_child_chart, flat_rows = _monthly_flat_view(
            volume_grid,
            child_field,
            overall_volume_series,
        )
    else:
        monthly_child_chart, flat_rows = _monthly_flat_view(
            grid,
            child_field,
        )
    overall_rows = [overall_row] if overall_row else []

    monthly_flat_table = {
        "type": "flat",
        "headers": monthly_child_chart["months"],
        "forecast_start_index": fsi,
        "editable": False,
        "rows": overall_rows + flat_rows,
    }
    monthly_hierarchy_table = {
        "type": "hierarchy",
        "headers": monthly_parent_chart["months"],
        "forecast_start_index": fsi,
        "editable": True,
        "rows": overall_rows + hierarchy_rows,
    }

    # ---- yearly: same parent/child split as monthly. Yearly has no
    # synthesized 100%/summed series to pull an Overall row from the way
    # _monthly_parent_child_view does, so it's built separately here (see
    # _yearly_overall_row) to keep the yearly tables consistent with monthly. ----
    if metric == "market_share":
        parent_yearly, yearly_hierarchy_rows = _yearly_parent_child_view(
            volume_grid, parent_field, child_field, overall_volume_series)
        child_yearly = (_to_yearly_share_from_volume(volume_grid, child_field, overall_volume_series)
                        if volume_grid else {"years": [], "forecast_start_index": 0, "series": []})
    else:
        parent_series = _group_series_by_field(grid, parent_field)
        parent_yearly = _to_yearly_chart(parent_series, agg)

        cell_totals = _yearly_cell_totals(grid, parent_field, child_field, agg)
        children_by_parent: Dict[str, List[dict]] = {}
        for cell in cell_totals:
            children_by_parent.setdefault(cell["parent"], []).append(cell)
        yearly_hierarchy_rows = [
            {
                "label": s["label"],
                "values": s["history"] + s["forecast"],
                "children": [
                    {"label": c["child"], "values": c["history"] + c["forecast"]}
                    for c in children_by_parent.get(s["label"], [])
                ],
            }
            for s in parent_yearly["series"]
        ]

        child_series = _group_series_by_field(grid, child_field)
        child_yearly = _to_yearly_chart(child_series, agg)

    yearly_overall = _yearly_overall_row(child_yearly["years"], metric, overall_volume_series)
    yearly_overall_rows = [yearly_overall] if yearly_overall else []

    yearly_flat_table = _to_table(child_yearly)
    yearly_flat_table["type"] = "flat"
    yearly_flat_table["editable"] = False
    yearly_flat_table["rows"] = yearly_overall_rows + yearly_flat_table["rows"]

    yearly_hierarchy_table = {
        "type": "hierarchy",
        "headers": parent_yearly["years"],
        "forecast_start_index": parent_yearly["forecast_start_index"],
        "editable": True,
        "rows": yearly_overall_rows + yearly_hierarchy_rows,
    }

    return {
        "monthly": {
            "view_options": view_options,
            "selected_view": levels["hierarchy_key"],
            levels["flat_key"]: {"chart": monthly_child_chart, "table": monthly_flat_table},
            levels["hierarchy_key"]: {"chart": monthly_parent_chart, "table": monthly_hierarchy_table},
        },
        "yearly": {
            "view_options": view_options,
            "selected_view": levels["hierarchy_key"],
            levels["flat_key"]: {"chart": child_yearly, "table": yearly_flat_table},
            levels["hierarchy_key"]: {"chart": parent_yearly, "table": yearly_hierarchy_table},
        },
    }


def _build_hierarchy_views(tab: str, scenario_name: str, ta_name: str, entities: Dict[str, List[str]],
                            cache: Optional[CacheType] = None,
                            date_range: Tuple[Optional[str], Optional[str]] = (None, None)
                            ) -> Tuple[Dict, Optional[str]]:
    """Shared by build_metrics_views (active tab, overlays cache onto grid)
    and build_latest_metrics_views (other tabs, plain fresh DB read).
    `entities` is the full product/market universe, not selected_filter --
    filter only clips the display range, applied last."""
    parent_field, child_field = TAB_HIERARCHY[tab]
    markets = entities.get("markets", [])
    products = entities.get("products", [])
    start_date, end_date = date_range

    share_grid = fetch_grid(
    scenario_name,
    ta_name,
    "market_share",
    markets,
    products,
    )

    if cache is not None:
        share_grid = _overlay_cache_on_grid(
            share_grid,
            cache["market_share"],
        )

    #
    # NEW
    # Refresh ALL rows after overlay
    #
    # share_grid = _recalculate_all_rows(share_grid)

    overall_share = None
    if share_grid:
        g_months, g_fsi = share_grid[0]["months"], share_grid[0]["forecast_start_index"]
        overall_share = {
            "months": g_months,
            "forecast_start_index": g_fsi,
            "history": [100.0] * g_fsi,
            "forecast": [100.0] * (len(g_months) - g_fsi),
        }

    overall_volume_rows = _fetch_overall_series(scenario_name, ta_name, "market_volume")
    market_share_all = fetch_grid(
        scenario_name,
        ta_name,
        "market_share",
        markets,
        ["ALL"],
    )

    print("\n========== Market Share ALL ==========")
    for row in market_share_all:
        print(
            row["market"],
            row["product"],
            row["history"] + row["forecast"]
        )
    print("\n========== Overall_volume_rows ==========")
    print(overall_volume_rows)
    volume_grid = _derive_volume_grid(
            share_grid,
            market_share_all,
            overall_volume_rows,
        )

    share_grid = _clip_series_list(share_grid, start_date, end_date)
    volume_grid = _clip_series_list(volume_grid, start_date, end_date)
    if overall_share is not None:
        overall_share = _clip_series_to_range(overall_share, start_date, end_date)
    overall_volume_rows = _clip_series_list(overall_volume_rows, start_date, end_date)

    overall_volume_series = overall_volume_rows[0] if overall_volume_rows else None
    metrics_views = {
        "market_share": build_hierarchical_dual_view(
            tab, "market_share", share_grid, parent_field, child_field, YEARLY_AGG["market_share"],
            overall_series=overall_share, volume_grid=volume_grid, overall_volume_series=overall_volume_series),
        "market_volume": build_hierarchical_dual_view(
            tab, "market_volume", volume_grid, parent_field, child_field, YEARLY_AGG["market_volume"],
            overall_series=overall_volume_series, volume_grid=volume_grid,
            overall_volume_series=overall_volume_series),
    }
    forecast_start_date = _forecast_start_date_from(
        {"market_share": share_grid, "market_volume": overall_volume_rows})
    return metrics_views, forecast_start_date


# ======================================================
# 3. CHART / TABLE
# ======================================================

def _to_monthly_chart(series_list: List[dict]) -> dict:
    if not series_list:
        return {"months": [], "forecast_start_index": 0, "series": []}
    months = series_list[0]["months"]
    return {
        "months": months,
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
                values.append(round(sum(vs), 2))
            else:
                values.append(round(sum(vs) / len(vs), 2))
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
    """Plain {chart, table} shape, unwrapped. Used for the overall_event
    view, wrapped by _wrap_overall_view at the call site -- do not wrap it
    here."""
    monthly_chart = _to_monthly_chart(series_list)
    yearly_chart = _to_yearly_chart(series_list, agg)
    return {
        "monthly": {"chart": monthly_chart, "table": _to_table(monthly_chart)},
        "yearly": {"chart": yearly_chart, "table": _to_table(yearly_chart)},
    }


# overall_event has no flat/hierarchy switch -- it's always one flat
# "Overall" series -- but the FE contract is consistent across all three
# tabs, so it still gets a view_options/selected_view envelope with a
# single option. The FE can hide the dropdown for this tab since
# selected_view never changes.
OVERALL_VIEW_KEY = "overall_level"
OVERALL_VIEW_OPTIONS = [{"label": OVERALL_LABEL, "value": OVERALL_VIEW_KEY}]


def _wrap_overall_view(view: dict) -> dict:
    """Wraps build_metric_view()'s plain {chart, table} shape in the same
    view_options/selected_view envelope product_event/market_event use for
    their flat/hierarchy switcher (see build_hierarchical_dual_view), so
    all three tabs are consistent on the wire."""
    return {
        period: {
            "view_options": OVERALL_VIEW_OPTIONS,
            "selected_view": OVERALL_VIEW_KEY,
            OVERALL_VIEW_KEY: view[period],
        }
        for period in ("monthly", "yearly")
    }


def _forecast_start_date_from(series_by_metric: Dict[str, List[dict]]) -> Optional[str]:
    for rows in series_by_metric.values():
        for row in rows:
            fsi = row["forecast_start_index"]
            if fsi < len(row["months"]):
                return row["months"][fsi]
    return None


def build_metrics_views(tab: str, scenario_name: str, ta_name: str, entities: dict,
                         events: List[EventInput],
                         date_range: Tuple[Optional[str], Optional[str]] = (None, None)
                         ) -> Tuple[Dict, Optional[str], CacheType]:
    """Builds metrics_views for the actively-edited tab, plus returns the raw
    cache so the caller can persist without recomputing."""
    cache = apply_events_to_baseline(events, entities)

    if tab not in TAB_HIERARCHY:
        start_date, end_date = date_range
        series_by_metric = {
            metric: _clip_series_list(list(cache[metric].values()), start_date, end_date)
            for metric in METRICS
        }
        metrics_views = {
            metric: _wrap_overall_view(build_metric_view(series_by_metric[metric], YEARLY_AGG[metric]))
            for metric in METRICS
        }
        return metrics_views, _forecast_start_date_from(series_by_metric), cache

    metrics_views, forecast_start_date = _build_hierarchy_views(
        tab, scenario_name, ta_name, entities, cache=cache, date_range=date_range
    )
    return metrics_views, forecast_start_date, cache


def build_latest_metrics_views(tab: str, scenario_name: str, ta_name: str, entities: dict,
                                date_range: Tuple[Optional[str], Optional[str]] = (None, None)
                                ) -> Tuple[Dict, Optional[str]]:
    """Same shape as build_metrics_views but for a tab not being edited this
    run -- fresh DB read, reflects the latest persisted values."""
    start_date, end_date = date_range
    if tab not in TAB_HIERARCHY:
        series_by_metric = {
            metric: _clip_series_list(
                fetch_tab_baseline(tab, metric, scenario_name, ta_name, entities), start_date, end_date)
            for metric in METRICS
        }
        metrics_views = {
            metric: _wrap_overall_view(build_metric_view(series_by_metric[metric], YEARLY_AGG[metric]))
            for metric in METRICS
        }
        return metrics_views, _forecast_start_date_from(series_by_metric)

    return _build_hierarchy_views(tab, scenario_name, ta_name, entities, cache=None, date_range=date_range)


# ======================================================
# 3b. FINAL ROUNDING (display only)
# ======================================================
# Internal calculations (RAS reconciliation, channel blending, residual
# redistribution, etc.) keep their own working precision -- those roundings
# stay where they are, since the math needs stable intermediate values.
# This pass only rounds what actually goes to the FE, once, at the end:
# market_share to 2 decimals, market_volume to whole numbers.

ROUND_DIGITS: Dict[str, int] = {"market_share": 2, "market_volume": 0}


def _round_tree(obj, ndigits: int):
    """Recursively rounds every list of numbers found anywhere in a nested
    chart/table structure, regardless of its shape -- so this works for both
    the plain {chart, table} views and the flat/hierarchy/overall
    view_options structures without needing to know its exact layout.
    Non-numeric lists (months, years, labels, view_options) and everything
    else pass through untouched."""
    if isinstance(obj, dict):
        return {k: _round_tree(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        if obj and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj):
            return [round(x, ndigits) for x in obj]
        return [_round_tree(x, ndigits) for x in obj]
    return obj


def _round_metrics_views(metrics_views: Dict[str, dict]) -> Dict[str, dict]:
    return {
        metric: _round_tree(view, ROUND_DIGITS.get(metric, 4))
        for metric, view in metrics_views.items()
    }


# ======================================================
# 4. FE ROW ADAPTER
# ======================================================

def _equal_weights(names: List[str]) -> List[float]:
    if not names:
        return []
    share = round(100.0 / len(names), 4)
    weights = [share] * len(names)
    weights[-1] = round(100.0 - share * (len(names) - 1), 4)  # absorb rounding error
    return weights


def _resolve_weights(row: dict, impacted_names: List[str]) -> List[float]:
    """Normalizes source_percentages to 100 across the given names, or
    splits evenly if none were usable."""
    if not impacted_names:
        return []

    source_percentages = row.get("source_percentages") or {}
    raw = [source_percentages.get(name, 0.0) for name in impacted_names]
    total = sum(raw)

    if total > 0:
        return [round(w * 100.0 / total, 4) for w in raw]
    return _equal_weights(impacted_names)


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
        source_percentages=row.get("source_percentages"),
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


def tab_config(tab: str, entities: Dict[str, List[str]]) -> dict:
    """`entities` is the full universe, not selected_filter -- always every
    selectable product/market for redistribution."""
    all_products = entities["products"]
    all_markets = entities["markets"]
    config = {"curve_types": CURVE_TYPES}
    if tab == "market_event":
        config.update(products=all_products, markets=all_markets, impact_markets=all_markets)
    elif tab == "product_event":
        config.update(products=all_products, markets=all_markets, impact_products=all_products)
    return config


# ======================================================
# 5. DB WRITE-BACK
# ======================================================
# Requires (run once): ALTER TABLE raw_hiv_treat.forecast_outputs
#   ADD COLUMN IF NOT EXISTS events_payload JSONB;
# Only market_share cells are written -- market_volume has no per-cell row,
# it's purely a display-time derivation (_derive_volume_grid).
# Synthesized cells (summed/blended/averaged, no single backing row) are
# skipped -- known gap, not resolved here.

def _distribute_synthesized_write(metric: str, series: dict) -> List[Tuple[str, str, str, str, List[float]]]:
    """A synthesized cell (channel-split rows blended into one) has no
    single backing DB row -- but if it was touched by an event this run,
    the rebalanced value still needs to land somewhere, or it silently
    reverts to the old per-channel values on the next refresh. Propagates
    the cell's change back onto its underlying per-channel rows.

    market_volume channels are combined by SUM, so each channel keeps its
    original share of the new total (scale by that channel's pre-event
    share of the pre-event sum).

    market_share channels are combined by weighted BLEND, not a simple
    share of the total, so there's no clean inverse decomposition. Instead
    every channel absorbs the same point-change the blended cell picked up
    (additive delta) -- a defensible default, but a business call worth
    confirming if channel-level share precision matters downstream."""
    source_rows = series.get("source_rows")
    if not source_rows:
        return []  # no per-channel breakdown available (e.g. synthetic Overall row)

    new_forecast = series["forecast"]
    old_forecast = series.get("_baseline_forecast", new_forecast)
    updates = []

    if metric == "market_volume":
        old_total = sum(old_forecast) or 1.0
        for src in source_rows:
            channel_share = sum(src["forecast"]) / old_total
            scaled = [round(v * channel_share, 4) for v in new_forecast]
            updates.append((metric, src["market"], src["product"], src["source_of_market"], scaled))
    else:
        deltas = [round(n - o, 4) for n, o in zip(new_forecast, old_forecast)]
        for src in source_rows:
            adjusted = [
                round(v + (deltas[i] if i < len(deltas) else 0.0), 4)
                for i, v in enumerate(src["forecast"])
            ]
            updates.append((metric, src["market"], src["product"], src["source_of_market"], adjusted))

    return updates


def persist_events_to_db(
    scenario_name: str,
    ta_name: str,
    rows: List[dict],
    cache: CacheType,
) -> None:
    """Writes post-event forecast_values + the FE row config back onto their
    source rows. Skipped for Base (stays untouched baseline).

    Non-synthesized cells write directly onto their single backing row.
    Synthesized cells (channel-split, no single backing row) are
    propagated back onto their underlying channel rows via
    _distribute_synthesized_write instead of being dropped -- previously
    any rebalanced channel-split cell was silently skipped here, so it
    would appear correct in the response but revert on the next refresh."""
    if scenario_name == BASELINE_SCENARIO:
        return

    updates: List[Tuple[str, str, str, str, List[float]]] = []
    for metric, by_cell in cache.items():
        for series in by_cell.values():
            if not series.get("synthesized"):
                updates.append((metric, series["market"], series["product"], "ALL", series["forecast"]))
            else:
                updates.extend(_distribute_synthesized_write(metric, series))
    if not updates:
        return

    events_payload = json.dumps(rows)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for metric, market, product, source_of_market, forecast_values in updates:
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
                        json.dumps(forecast_values),
                        events_payload,
                        scenario_name, ta_name, metric,
                        market, product, source_of_market,
                    ],
                )
                if cur.rowcount == 0:
                    print(
                        f"WARNING: No row updated -> "
                        f"{metric} | {market} | {product} | {source_of_market}"
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
    raw_rows = payload["impact_curve_configuration"]["rows"]

    # Assign a stable event_id to every row missing one, for FE keying.
    rows = [{**row, "event_id": row.get("event_id", idx + 1)} for idx, row in enumerate(raw_rows)]

    # Full universe, reused for every tab's dropdown config + view scoping.
    entities = fetch_available_entities(scenario_name, ta_name)
    available_scenarios = fetch_available_scenarios(ta_name)
    available_months = fetch_available_months(ta_name)

    # Display-only clip, applied after events are computed against the full baseline.
    date_range = (selected_filter.get("start_date"), selected_filter.get("end_date"))

    events = [row_to_event(row, tab, scenario_name, ta_name) for row in rows]
    active_metrics_views, forecast_start_date, cache = build_metrics_views(
        tab, scenario_name, ta_name, entities, events, date_range=date_range
    )

    # Persist before building the other two tabs so their fresh DB reads pick up this run's changes.
    persist_events_to_db(scenario_name, ta_name, rows, cache)

    # Every tab computed and returned so the FE can switch without a round trip.
    event_tabs = {}
    for t in TABS:
        if t == tab:
            metrics_views = active_metrics_views
            tab_forecast_start_date = forecast_start_date
            tab_rows = rows
        else:
            metrics_views, tab_forecast_start_date = build_latest_metrics_views(
                t, scenario_name, ta_name, entities, date_range=date_range
            )
            tab_rows = []  # other tabs' event config untouched this run
        event_tabs[t] = {
            "impact_curve_configuration": {
                **tab_config(t, entities),
                "forecast_start_date": tab_forecast_start_date,
                "rows": tab_rows,
            },
            "metrics_views": _round_metrics_views(metrics_views),
        }

    return {
        "ta_name": ta_name,
        "available_scenarios": available_scenarios,
        "available_months": available_months,
        "selected_filter": selected_filter,
        "selected_tab": tab,
        "impact_curve_configuration": {
            **tab_config(tab, entities),
            "forecast_start_date": forecast_start_date,
            "rows": rows,
        },
        "metric_filters": METRIC_FILTERS,
        "event_tabs": event_tabs,
    }