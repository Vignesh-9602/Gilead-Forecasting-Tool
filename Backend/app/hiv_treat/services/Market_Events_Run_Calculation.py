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
            **combined,
        })
    return aggregated


def fetch_baseline(event: EventInput, metric: str) -> List[dict]:
    """DB rows an event needs: selected entity + impacted entities, scoped
    by event context. source_of_market=None + _aggregate_by_cell since a
    cell isn't guaranteed a single pre-aggregated row."""
    if event.event_scope == EventScope.PRODUCT_EVENT:
        products = [event.selected_entity] + [e.name for e in (event.impacted_entities or [])]
        raw = fetch_series(event.scenario_name, event.ta_name, metric,
                            label_field="product", market=event.context, products=products,
                            source_of_market=None)
        return _aggregate_by_cell(raw, metric, event.scenario_name, event.ta_name)

    if event.event_scope == EventScope.MARKET_EVENT:
        markets = [event.selected_entity] + [e.name for e in (event.impacted_entities or [])]
        raw = fetch_series(event.scenario_name, event.ta_name, metric,
                            label_field="market", market=markets, products=[event.context],
                            source_of_market=None)
        return _aggregate_by_cell(raw, metric, event.scenario_name, event.ta_name)

    # OVERALL_EVENT -- portfolio row is always genuinely 'ALL'
    return _fetch_overall_series(event.scenario_name, event.ta_name, metric)


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


def _offset_sibling_market_shares(
    cache: Dict[str, Dict[str, dict]],
    scenario_name: str,
    ta_name: str,
    share_deltas_by_cell: Dict[Tuple[str, str], List[float]],
) -> None:
    """A market's products must sum to 100% market_share, but an event curve
    only touches the cells it names -- this offsets the net delta those
    cells received against every OTHER product in the same market, so the
    market keeps summing to 100.

    Weighting: the FE payload currently has no product-level "source of
    business" field for this axis (that's the separate {product: pct} split
    shown in the Market Events "Edit Source of Business" dialog -- distinct
    from source_percentages, which only covers impacted_markets/impacted_
    products redistribution and is left untouched by this function). Absent
    an explicit split, siblings are offset PROPORTIONALLY TO THEIR OWN
    CURRENT SHARE in that market at each month -- a product holding 40% of
    Retail gives up more than one holding 10% when Retail needs to
    rebalance back to 100. This is a placeholder default: if/when the
    payload adds an explicit product-level split, prefer that map here
    instead of the proportional weights, the same way _resolve_weights
    already prefers an explicit source_percentages over its equal-split
    fallback for impacted_entities.

    Additive offset (not a hard renormalization to a fixed ratio), so an
    untouched sibling keeps its own trend shape over the event window --
    only the amount needed to hold the market at 100 moves.
    """
    if not share_deltas_by_cell:
        return

    all_products = fetch_available_entities(scenario_name, ta_name)["products"]
    markets_touched = {market for market, _ in share_deltas_by_cell}
    share_cache = cache["market_share"]
    bounds = CLAMP_BOUNDS["market_share"]

    # cache["market_share"] is keyed by "label", which means DIFFERENT things
    # depending on who wrote it -- market name for a MARKET_EVENT's touched
    # cells (fetch_baseline uses label_field="market"), product name for
    # fetch_grid's rows here (always label_field="product"). A MARKET_EVENT
    # touches 2+ markets in this loop, and product names repeat across
    # markets (Biktarvy-Retail and Biktarvy-Non-retail both key to
    # "Biktarvy"), so writing sibling rows into share_cache by "label"
    # collides across markets and silently drops the second market's
    # siblings. Use a private (market, product)-keyed index instead, so
    # nothing collides with share_cache's touched-cell entries or across
    # markets within this function.
    sibling_index: Dict[Tuple[str, str], dict] = {}

    for market in markets_touched:
        for row in fetch_grid(scenario_name, ta_name, "market_share", [market], all_products):
            sibling_index.setdefault((row["market"], row["product"]), row)

        touched_products = {p for m, p in share_deltas_by_cell if m == market}
        sibling_rows = [
            row for (m, p), row in sibling_index.items()
            if m == market and p not in touched_products
        ]
        if not sibling_rows:
            continue  # nothing to offset against in this market

        n_forecast = len(sibling_rows[0]["forecast"])
        for i in range(n_forecast):
            net_delta = sum(
                deltas[i] for (m, _p), deltas in share_deltas_by_cell.items()
                if m == market and i < len(deltas)
            )
            if net_delta == 0:
                continue

            # Proportional-to-current-share weights, recomputed per month
            # since siblings' own shares can drift month to month.
            weight_total = sum(
                row["forecast"][i] for row in sibling_rows if i < len(row["forecast"])
            )
            if weight_total <= 0:
                continue  # nothing to distribute against -- leave as-is

            for row in sibling_rows:
                if i >= len(row["forecast"]):
                    continue
                weight_pct = row["forecast"][i] / weight_total
                offset = -net_delta * weight_pct
                new_value = round(row["forecast"][i] + offset, 4)
                if bounds is not None:
                    new_value = max(bounds[0], min(bounds[1], new_value))
                row["forecast"][i] = new_value


def apply_events_to_baseline(events: List[EventInput]) -> Dict[str, Dict[str, dict]]:
    """For each event: compute its curve, fetch every touched entity once
    (cached so repeats stack instead of overwriting), add curve onto the
    forecast. For market_share, also offsets the delta against untouched
    sibling products in the same market so the market keeps summing to
    100% (see _offset_sibling_market_shares). Returns {metric: {label: series}}."""
    cache: Dict[str, Dict[str, dict]] = {metric: {} for metric in METRICS}

    for event in events:
        result = compute_event_forecast(event)
        curves = _entity_curves(result)
        event_touched_forecast = False
        share_deltas_by_cell: Dict[Tuple[str, str], List[float]] = {}

        for metric in METRICS:
            for label in curves:
                if label not in cache[metric]:
                    for row in fetch_baseline(event, metric):
                        cache[metric].setdefault(row["label"], row)

            bounds = CLAMP_BOUNDS.get(metric)
            for label, curve in curves.items():
                if label not in cache[metric]:
                    continue
                before_forecast = cache[metric][label]["forecast"][:]
                cache[metric][label], applied = _apply_curve_to_series(
                    cache[metric][label], result.months, curve, bounds)
                event_touched_forecast = event_touched_forecast or applied

                if metric == "market_share" and applied:
                    row = cache[metric][label]
                    share_deltas_by_cell[(row["market"], row["product"])] = [
                        round(a - b, 4) for a, b in zip(row["forecast"], before_forecast)
                    ]

        if not event_touched_forecast:
            # Curve's target months fall entirely in history -- surface it
            # rather than silently no-op'ing.
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

        _offset_sibling_market_shares(
            cache, event.scenario_name, event.ta_name, share_deltas_by_cell,
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


def _overlay_cache_on_grid(grid: List[dict], cache_by_label: Dict[str, dict]) -> List[dict]:
    """Replace a grid cell with its post-event version, for the tab being edited."""
    by_cell = {(c["market"], c["product"]): c for c in cache_by_label.values()}
    overlaid = []
    for cell in grid:
        override = by_cell.get((cell["market"], cell["product"]))
        overlaid.append(copy.deepcopy(override) if override else cell)
    return overlaid


def _derive_volume_grid(share_grid: List[dict], overall_volume: List[dict]) -> List[dict]:
    """market_volume has no per-cell DB row -- derived at display time as
    cell's market_share% applied to the current overall total. Not persisted."""
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


def build_hierarchical_metric_view(metric: str, grid: List[dict], parent_field: str, child_field: str,
                                    agg: str, overall_series: Optional[dict] = None,
                                    volume_grid: Optional[List[dict]] = None,
                                    overall_volume_series: Optional[dict] = None) -> dict:
    """Monthly view groups parent-with-children; yearly view flips to per-child
    totals. market_share yearly is derived from volumes, not averaged percentages."""
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

    if metric == "market_share" and volume_grid:
        yearly_chart = _to_yearly_share_from_volume(volume_grid, child_field, overall_volume_series)
    else:
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


def _build_hierarchy_views(tab: str, scenario_name: str, ta_name: str, entities: Dict[str, List[str]],
                            cache: Optional[Dict[str, Dict[str, dict]]] = None,
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

    share_grid = fetch_grid(scenario_name, ta_name, "market_share", markets, products)
    if cache is not None:
        share_grid = _overlay_cache_on_grid(share_grid, cache["market_share"])

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
    volume_grid = _derive_volume_grid(share_grid, overall_volume_rows)

    share_grid = _clip_series_list(share_grid, start_date, end_date)
    volume_grid = _clip_series_list(volume_grid, start_date, end_date)
    if overall_share is not None:
        overall_share = _clip_series_to_range(overall_share, start_date, end_date)
    overall_volume_rows = _clip_series_list(overall_volume_rows, start_date, end_date)

    overall_volume_series = overall_volume_rows[0] if overall_volume_rows else None
    metrics_views = {
        "market_share": build_hierarchical_metric_view(
            "market_share", share_grid, parent_field, child_field, YEARLY_AGG["market_share"],
            overall_share, volume_grid=volume_grid, overall_volume_series=overall_volume_series),
        "market_volume": build_hierarchical_metric_view(
            "market_volume", volume_grid, parent_field, child_field, YEARLY_AGG["market_volume"],
            overall_volume_series),
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


def build_metrics_views(tab: str, scenario_name: str, ta_name: str, entities: dict,
                         events: List[EventInput],
                         date_range: Tuple[Optional[str], Optional[str]] = (None, None)
                         ) -> Tuple[Dict, Optional[str], Dict[str, Dict[str, dict]]]:
    """Builds metrics_views for the actively-edited tab, plus returns the raw
    cache so the caller can persist without recomputing."""
    cache = apply_events_to_baseline(events)

    if tab not in TAB_HIERARCHY:
        start_date, end_date = date_range
        series_by_metric = {
            metric: _clip_series_list(list(cache[metric].values()), start_date, end_date)
            for metric in METRICS
        }
        metrics_views = {
            metric: build_metric_view(series_by_metric[metric], YEARLY_AGG[metric])
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
            metric: build_metric_view(series_by_metric[metric], YEARLY_AGG[metric])
            for metric in METRICS
        }
        return metrics_views, _forecast_start_date_from(series_by_metric)

    return _build_hierarchy_views(tab, scenario_name, ta_name, entities, cache=None, date_range=date_range)


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

def persist_events_to_db(
    scenario_name: str,
    ta_name: str,
    rows: List[dict],
    cache: Dict[str, Dict[str, dict]],
) -> None:
    """Writes post-event forecast_values + the FE row config back onto their
    source rows. Skipped for Base (stays untouched baseline) and for
    synthesized series (no single row to write to)."""
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
            "metrics_views": metrics_views,
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