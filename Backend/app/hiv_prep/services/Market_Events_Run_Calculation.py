import copy
import json
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Union

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.connection import get_connection
from app.hiv_prep.routes.Events_Calculation import (
    CoverageInput, EventForecastResult, EventInput, EventScope,
    ImpactedEntity, compute_event_forecast,
)

METRICS = ("market_share", "market_volume")

# A product's split ACROSS markets -- for each (market, product), that
# market's share of the product's OWN total. Stored per cell at
# source_of_market='ALL' and read by the Product-Channel / Channel-Product
# views. It is NOT part of METRICS: no event targets it directly, it's a
# roll-up recomputed from market_share after events land (see
# recompute_product_market_split). Left out of the write path, a new
# product ends up with real shares but a pm of zero, and the views that
# read it hand its volume to the other products.
PM_METRIC = "market_share_pm"
YEARLY_AGG = {"market_share": "average", "market_volume": "sum"}
CURVE_TYPES = ["Linear", "Exponential", "Logarithmic", "SCurve"]
TABLE = "raw_hiv_prep.forecast_outputs"
CONFIG_TABLE = "raw_hiv_prep.forecast_configurations"
PRODUCT_MASTER_TABLE = "raw_hiv_prep.product_master_hiv_prep"
OVERALL_LABEL = "Overall"
TABS = ("market_event", "product_event", "overall_event")
BASELINE_SCENARIO = "Base"  # never written back to

# Seeding materializes a registered product into ONE scenario -- whichever
# one the calculation is running against. Loading a screen is not the same
# as working in a scenario, so the load path does not seed by default:
# merely opening every scenario in the dropdown would otherwise create the
# product in all of them. Flip to True if you want a product to appear
# (at zero) as soon as any scenario is opened.
SEED_ON_LOAD = False

# The baseline scenario is never written to -- persist_events_to_db already
# returns early for it, and seeding is a write too. Left ungated, running a
# calculation while Base is selected inserts new product rows into the
# untouched baseline. Flip to True only if you want registered products to
# exist (at zero) in Base as well.
SEED_BASELINE_SCENARIO = False

# A (market, product) cell may have both a canonical source_of_market='ALL'
# row AND per-channel rows (ADAP / Federal / IQVIA / Kaiser / Unknown).
# The canonical row IS the market-wide total; the channel rows are that
# product's share WITHIN each channel. Blending them together treats the
# total as a fifth channel and produces a value that is neither -- and
# because the blended result is then written back onto all five rows, the
# read->blend->write->read cycle is not idempotent and the total drifts
# further from its channels on every run.
#
# True: read the canonical row as the cell's value, and propagate the
# event's delta out to the channel rows on write so they stay in step
# without ever feeding back into a read. Blending is kept only for cells
# that genuinely have no canonical row.
PREFER_CANONICAL_CELL_ROW = True

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
        "flat_label": "Channel Level",
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
    scenarios stored split by payer/channel (see _aggregate_by_cell).
    source_of_market="ALL" matches both the literal 'ALL' and legacy empty-
    string rows -- some rows were written before source normalization was
    added, so an exact-string match on 'ALL' silently misses them.

    Every batch is re-indexed onto one canonical month grid before it is
    returned (see _align_rows) -- a newly created product's row has no
    history and may store a shorter months array / forecast_start_index=0,
    which would otherwise shift every series it is later summed or
    charted with."""
    where = ["scenario_name = %s", "ta_name = %s", "metric = %s"]
    params: List = [scenario_name, ta_name, metric]

    if market is not None:
        where.append("market = ANY(%s)" if isinstance(market, list) else "market = %s")
        params.append(market)

    if source_of_market is not None:
        where.append("COALESCE(NULLIF(source_of_market, ''), 'ALL') = %s")
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
        history = data.get("train_values", []) or []
        series.append({
            "label": product_name if label_field == "product" else market_name,
            "market": market_name,
            "product": product_name,
            "source_of_market": channel or "",
            "synthesized": False,
            "months": data.get("months", []) or [],
            "history": history,
            "forecast": data.get("forecast_values", []) or [],
            "forecast_start_index": data.get("forecast_start_index", len(history)),
        })

    # New entities (zero-history products) come back short/ragged -- align
    # every batch onto one grid so all downstream positional zips hold.
    return _align_rows(series, ta_name)


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


def _empty_series(months: Optional[List[str]] = None, fsi: int = 0) -> dict:
    """All-zero series on a given window -- used wherever a group legitimately
    has no rows (e.g. a parent whose only child is a product with no volume
    yet), so callers never index into an empty list."""
    months = list(months or [])
    fsi = min(fsi, len(months))
    return {
        "months": months,
        "forecast_start_index": fsi,
        "history": [0.0] * fsi,
        "forecast": [0.0] * (len(months) - fsi),
    }


def _sum_series(rows: List[dict]) -> dict:
    """Elementwise sum -- valid for genuinely additive quantities (volume).
    Keyed by month LABEL and referenced off the widest row, so a new product
    contributing only forecast months adds into the right months instead of
    being off by the length of everyone else's history."""
    if not rows:
        return _empty_series()
    reference = max(rows, key=lambda r: len(r["months"]))
    months, fsi = reference["months"], reference["forecast_start_index"]
    totals = {m: 0.0 for m in months}
    for r in rows:
        for m, v in zip(r["months"], r["history"] + r["forecast"]):
            if m in totals:
                totals[m] = round(totals[m] + v, 4)
    values = [totals[m] for m in months]
    return {"months": months, "forecast_start_index": fsi,
            "history": values[:fsi], "forecast": values[fsi:]}


def _average_series(rows: List[dict]) -> dict:
    """Equal-weighted average -- fallback only, when no channel weights exist."""
    if not rows:
        return _empty_series()
    summed = _sum_series(rows)
    k = len(rows)
    values = [round(v / k, 4) for v in summed["history"] + summed["forecast"]]
    fsi = summed["forecast_start_index"]
    return {"months": summed["months"], "forecast_start_index": fsi,
            "history": values[:fsi], "forecast": values[fsi:]}


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
    as a last resort). product == "ALL" cells are never blended -- same
    rule as fetch_forecast_scenario: the canonical source_of_market="ALL"
    row IS the total, any other rows sharing this key are per-channel
    internal figures. Synthesized cells have no single backing DB row, so
    persist_events_to_db() skips writing them back."""
    grouped: Dict[Tuple[str, str], List[dict]] = {}
    for r in rows:
        grouped.setdefault((r["market"], r["product"]), []).append(r)

    aggregated = []
    for (market, product), group_rows in grouped.items():
        if len(group_rows) == 1:
            aggregated.append(group_rows[0])
            continue

        # The canonical source_of_market='ALL' row IS this cell's total --
        # for every product, not only for product='ALL'. Per-channel rows
        # sharing the key are the product's share within that channel and
        # must never be averaged into the total (see PREFER_CANONICAL_CELL_ROW
        # and the note in fetch_baseline). They ride along as sibling_rows so
        # the write path can keep them in step.
        canonical = next(
            (r for r in group_rows
             if not r.get("source_of_market") or r["source_of_market"] == "ALL"),
            None,
        )
        if canonical is not None and (product == "ALL" or PREFER_CANONICAL_CELL_ROW):
            cell = dict(canonical)
            siblings = [r for r in group_rows if r is not canonical]
            if siblings:
                cell["sibling_rows"] = siblings
                cell["_baseline_forecast"] = list(canonical["forecast"])
            aggregated.append(cell)
            continue

        if product == "ALL":
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
            market=event.contexts,
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

        # Product-context cells may genuinely be split across channels --
        # still need source_of_market=None + per-cell aggregation.
        raw = fetch_series(
            event.scenario_name,
            event.ta_name,
            metric,
            label_field="market",
            market=markets,
            products=list(event.contexts),
            source_of_market=None,
        )
        aggregated = _aggregate_by_cell(
            raw, metric, event.scenario_name, event.ta_name,
        )

        # (market, "ALL") canonical total row -- fetched at
        # source_of_market="ALL" ONLY, same rule as
        # fetch_forecast_scenario's "prefer the true market-level ALL
        # row" logic. Per-channel "ALL" rows (ADAP, Federal, IQVIA,
        # Kaiser...) are each channel's own internal share-of-channel
        # figure -- they are weights, not pieces of this cell, and must
        # never be blended/averaged into it.
        all_rows = fetch_series(
            event.scenario_name,
            event.ta_name,
            metric,
            label_field="market",
            market=markets,
            products=["ALL"],
            source_of_market="ALL",
        )

        return aggregated + all_rows

    # OVERALL_EVENT -- portfolio row is always genuinely 'ALL'
    return _fetch_overall_series(
        event.scenario_name,
        event.ta_name,
        metric,
    )


def fetch_available_entities(scenario_name: str, ta_name: str,
                             include_registered: bool = False) -> Dict[str, List[str]]:
    """Every distinct product/market for THIS scenario, excluding the
    synthetic 'ALL' row. Used for FE dropdowns and to scope chart/table views.

    Scenario-scoped on purpose: a product materialized into one scenario
    must not appear in another where it has no rows. The master-table union
    is therefore opt-in (include_registered=True) rather than automatic --
    run_calculation seeds the scenario first, so by the time this runs the
    product already has its rows and the union would add nothing except
    products belonging to other scenarios."""
    query = f"SELECT DISTINCT market, product FROM {TABLE} WHERE scenario_name = %s AND ta_name = %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, [scenario_name, ta_name])
            rows = cur.fetchall()
    finally:
        conn.close()

    markets = sorted({m for m, p in rows if m not in (None, "ALL")})
    products = {p for m, p in rows if p not in (None, "ALL")}
    if include_registered:
        products |= set(fetch_registered_products(ta_name))
    return {"markets": markets, "products": sorted(products)}


def fetch_registered_products(ta_name: str) -> List[str]:
    """Products registered in the master table. A product created via the
    add-product API but not yet seeded into forecast_outputs exists only
    here -- without this it can never be picked in an event, because the
    dropdowns are built from forecast_outputs. Safety net only: seeding at
    creation time (see _seed_forecast_rows_for_new_product in the products
    route) is what makes a new product behave like every other one."""
    query = f"SELECT DISTINCT product_id FROM {PRODUCT_MASTER_TABLE} WHERE ta_name = %s"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query, [ta_name])
            rows = cur.fetchall()
    finally:
        conn.close()
    return sorted({r[0] for r in rows if r[0] and r[0] != "ALL"})


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


# ======================================================
# 1c. LAZY PRODUCT SEEDING
# ======================================================
# Products are registered in the master table alone (see the add-product
# route) -- nothing is written to forecast_outputs at creation time. They
# are materialized here instead, the first time a calculation runs for a
# given scenario: zero history, zero forecast, on the same rows every other
# product occupies.
#
# Doing it lazily rather than at creation means a product added today
# automatically appears in scenarios created tomorrow, with no backfill.

def _zeroed_forecast_data(data: dict) -> dict:
    """Copy a template row's forecast_data with every numeric series zeroed,
    keeping months, forecast_start_index and any other structural keys
    exactly as they are.

    Zeroing by structure rather than rebuilding from months/fsi means rows
    whose JSON carries extra arrays, or which omit train_values entirely,
    still come out shaped like their neighbours -- everything downstream
    reads these positionally, so shape is what matters."""
    zeroed = {}
    for key, value in data.items():
        if isinstance(value, list) and value and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in value
        ):
            zeroed[key] = [0.0] * len(value)
        else:
            zeroed[key] = value

    months = zeroed.get("months") or []
    if months:
        fsi = zeroed.get("forecast_start_index")
        if fsi is None:
            fsi = len(zeroed.get("train_values") or [])
        fsi = max(0, min(int(fsi), len(months)))
        zeroed["forecast_start_index"] = fsi
        zeroed.setdefault("train_values", [0.0] * fsi)
        zeroed.setdefault("forecast_values", [0.0] * (len(months) - fsi))

    return zeroed


def _fetch_seed_templates(cur, scenario_name: str, ta_name: str) -> List[tuple]:
    """The full set of row keys a product needs in this scenario, taken as
    the UNION across every product that already has rows.

    Previously this mirrored a single reference product -- whichever had
    the most rows. That inherits any gap the reference itself has: a
    product seeded from a reference with no Retail rows ends up Non-retail
    only, which then shows up as a product missing from one market in
    every view built from it. The union can only be as complete as the
    scenario's best-covered combination of products, which is the right
    bar.

    One representative forecast_data per key supplies the month grid; the
    values are zeroed before insert, so which product it came from doesn't
    matter.
    """
    cur.execute(
        f"""
        SELECT DISTINCT ON (metric, market, COALESCE(NULLIF(source_of_market, ''), 'ALL'))
               metric,
               market,
               source_of_market,
               forecast_data
        FROM {TABLE}
        WHERE ta_name = %s
          AND scenario_name = %s
          AND product IS NOT NULL
          AND UPPER(TRIM(product)) <> 'ALL'
        ORDER BY metric,
                 market,
                 COALESCE(NULLIF(source_of_market, ''), 'ALL'),
                 product
        """,
        [ta_name, scenario_name],
    )
    return cur.fetchall()


def seed_missing_products(scenario_name: str, ta_name: str) -> List[str]:
    """Materialize every registered product that has no rows in this
    scenario yet. Idempotent -- existing rows are never touched, so this is
    safe to call on every calculation.

    Returns the names of the products actually seeded."""
    if scenario_name == BASELINE_SCENARIO and not SEED_BASELINE_SCENARIO:
        # Same rule as persist_events_to_db: Base stays the untouched
        # baseline. Inserting rows into it is still a modification, even
        # when every value is zero.
        print(f"INFO: skipping seeding for baseline scenario "
              f"{BASELINE_SCENARIO!r} -- it is never written to")
        return []

    registered = set(fetch_registered_products(ta_name))
    if not registered:
        return []

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT product FROM {TABLE} "
                f"WHERE ta_name = %s AND scenario_name = %s",
                [ta_name, scenario_name],
            )
            existing = {r[0] for r in cur.fetchall() if r[0]}

            missing = sorted(p for p in registered if p not in existing)
            if not missing:
                return []

            templates = _fetch_seed_templates(cur, scenario_name, ta_name)
            if not templates:
                # Nothing to model on -- a scenario with no per-product rows
                # at all. Better to say so than to invent a month grid.
                print(f"WARNING: cannot seed {missing} into scenario "
                      f"{scenario_name!r} -- no existing product rows to "
                      f"use as a template")
                return []

            seeded = []
            for product in missing:
                inserted = 0
                for metric, market, source_of_market, forecast_data in templates:
                    payload = json.dumps(
                        _zeroed_forecast_data(_parse_forecast_data(forecast_data))
                    )
                    cur.execute(
                        f"""
                        INSERT INTO {TABLE}
                            (scenario_name, ta_name, metric, market, product,
                             source_of_market, forecast_data, updated_at)
                        SELECT %s, %s, %s, %s, %s, %s, %s::jsonb, now()
                        WHERE NOT EXISTS (
                            SELECT 1 FROM {TABLE}
                            WHERE scenario_name = %s AND ta_name = %s AND metric = %s
                              AND market = %s AND product = %s
                              AND COALESCE(NULLIF(source_of_market, ''), 'ALL')
                                = COALESCE(NULLIF(%s, ''), 'ALL')
                        )
                        """,
                        [
                            scenario_name, ta_name, metric, market, product,
                            source_of_market, payload,
                            scenario_name, ta_name, metric, market, product,
                            source_of_market,
                        ],
                    )
                    inserted += cur.rowcount

                if inserted:
                    seeded.append(product)
                    print(f"INFO: seeded {inserted} zero rows for product "
                          f"{product!r} in scenario {scenario_name!r}")

        conn.commit()
        return seeded
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================================================
# 1b. CANONICAL MONTH GRID  (new-entity support)
# ======================================================
# A brand-new product has no history: its stored train_values are empty
# (or all zeros) and its forecast_start_index may be 0, while every
# established series in the same batch has fsi = N. Every aggregation
# helper in this module zips series BY POSITION and reads
# months/forecast_start_index off rows[0], so one ragged series silently
# shifts everything it is summed, blended or charted with.
#
# Rather than special-casing each helper, every series is re-indexed onto
# one grid, matched BY MONTH LABEL, as soon as it leaves the DB (see
# fetch_series -> _align_rows). Months a series has no value for become
# 0.0, which for a new product is exactly its pre-launch history.

_FORECAST_GRID_CACHE: Dict[str, Optional[Tuple[List[str], int]]] = {}


def reset_forecast_grid_cache() -> None:
    """Cleared at the top of run_calculation so a config edit mid-session is
    never served from a stale grid."""
    _FORECAST_GRID_CACHE.clear()


def get_forecast_grid(ta_name: str) -> Optional[Tuple[List[str], int]]:
    """(months, forecast_start_index) for the whole TA, derived from the
    training/forecast window config. Used as the FALLBACK grid only --
    when a batch contains an established series, that series' own window
    wins (see _canonical_grid), since the config may have been edited
    after these forecasts were generated."""
    if ta_name in _FORECAST_GRID_CACHE:
        return _FORECAST_GRID_CACHE[ta_name]

    grid = None
    config = fetch_forecast_config(ta_name)
    if config:
        train_start = datetime.strptime(config["train_start_date"], "%Y-%m-%d").date()
        train_end = datetime.strptime(config["train_end_date"], "%Y-%m-%d").date()
        forecast_end = train_end + relativedelta(months=config.get("forecast_periods", 0) or 0)

        months: List[str] = []
        fsi = 0
        cursor = train_start
        while cursor <= forecast_end:
            months.append(cursor.strftime("%Y-%m-%d"))
            if cursor <= train_end:
                fsi += 1
            cursor += relativedelta(months=1)
        if months:
            grid = (months, fsi)

    _FORECAST_GRID_CACHE[ta_name] = grid
    return grid


def _canonical_grid(rows: List[dict], ta_name: str) -> Tuple[List[str], int]:
    """Widest month window in the batch. forecast_start_index is taken from
    an ESTABLISHED row (one that actually has history) rather than from
    rows[0] -- a new product's own fsi of 0 would otherwise declare the
    entire window to be forecast for every series in the batch. Falls back
    to the TA config only when every row in the batch is a new entity."""
    all_months = sorted({m for r in rows for m in r["months"]})
    established = [r for r in rows if r["months"] and r["forecast_start_index"] > 0]

    if established:
        reference = max(established, key=lambda r: len(r["months"]))
        ref_fsi = reference["forecast_start_index"]
        if ref_fsi >= len(reference["months"]):
            return all_months, len(all_months)  # nothing is forecast
        first_forecast = reference["months"][ref_fsi]
        return all_months, sum(1 for m in all_months if m < first_forecast)

    grid = get_forecast_grid(ta_name)
    if grid:
        config_months, config_fsi = grid
        all_months = sorted(set(all_months) | set(config_months))
        if config_fsi < len(config_months):
            first_forecast = config_months[config_fsi]
            return all_months, sum(1 for m in all_months if m < first_forecast)
    return all_months, 0


def align_series_to_grid(series: dict, months: List[str], fsi: int) -> dict:
    """Re-index one series onto `months`, matched by month label. Months the
    series has no value for become 0.0 -- for a new product that is its
    entire pre-launch history, which is the correct value, not a gap."""
    existing = dict(zip(series["months"], series["history"] + series["forecast"]))
    values = []
    for m in months:
        v = existing.get(m)
        values.append(0.0 if v is None else v)
    return {
        **series,
        "months": list(months),
        "forecast_start_index": fsi,
        "history": values[:fsi],
        "forecast": values[fsi:],
    }


def _align_rows(rows: List[dict], ta_name: str) -> List[dict]:
    if not rows:
        return rows
    months, fsi = _canonical_grid(rows, ta_name)
    if not months:
        return rows
    return [align_series_to_grid(r, months, fsi) for r in rows]


def fetch_available_months(ta_name: str) -> List[str]:
    """Full date range (history + forecast) for the FE's date-range picker --
    same grid every series is aligned to, so the picker and the data can
    never disagree."""
    grid = get_forecast_grid(ta_name)
    return list(grid[0]) if grid else []


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
                            bounds: Optional[Tuple[float, float]] = None,
                            mode: str = "add") -> Tuple[dict, bool]:
    """mode="set": forecast value becomes curve_values[pos] directly (used
    for the selected entity -- pins it exactly to the curve's own target,
    including holding flat at the peak once the curve ends, regardless of
    what the underlying baseline forecast does).
    mode="add": curve_values[pos] is added onto the existing forecast
    (used for impacted/sibling entities -- they move relative to their
    own trend, not toward an absolute target).

    A new product's baseline forecast is whatever was forecasted for it and
    its history is all zeros, so both modes behave normally here -- the
    zero history is never touched (only indices at/after
    forecast_start_index are written)."""
    series = copy.deepcopy(series)
    applied = False
    if not curve_months or not curve_values:
        return series, applied

    month_index = {m: i for i, m in enumerate(series["months"])}
    start_idx = month_index.get(curve_months[0])
    if start_idx is None:
        return series, applied

    hold_value = curve_values[-1]

    for idx in range(start_idx, len(series["months"])):
        if idx < series["forecast_start_index"]:
            continue
        pos = idx - start_idx
        value = curve_values[pos] if pos < len(curve_values) else hold_value

        fi = idx - series["forecast_start_index"]
        if fi >= len(series["forecast"]):
            break

        if mode == "set":
            new_value = round(value, 2)
        else:
            new_value = round(series["forecast"][fi] + value, 2)

        if bounds is not None:
            new_value = max(bounds[0], min(bounds[1], new_value))
        series["forecast"][fi] = new_value
        applied = True

    return series, applied


def _apply_growth_pct_to_series(series: dict, curve_months: List[str], curve_values: List[float]
                                 ) -> Tuple[dict, bool]:
    """Used for overall_event's market_volume: curve_values are a percentage
    growth curve (0 -> peak_pct, coverage-gated), applied MULTIPLICATIVELY
    onto the existing baseline forecast WHILE THE CURVE IS ACTIVE -- peak_pct
    is a %, not raw volume units, so adding it directly (like
    _apply_curve_to_series's "add" mode) is a unit mismatch and has almost no
    visible effect at real volume scale.

    Once the curve itself runs out (pos >= len(curve_values), i.e. past the
    peak/coverage tail), the ABSOLUTE volume from the last curve-active month
    is held flat going forward -- NOT re-derived by continuing to apply
    peak_pct to whatever the baseline forecast is doing in later months.
    Baseline months typically keep moving (trend/seasonality), so
    re-multiplying a moving baseline by a constant % does not stay flat;
    freezing the last computed absolute value is what "stays the same after
    peak" actually requires."""
    series = copy.deepcopy(series)
    applied = False
    if not curve_months or not curve_values:
        return series, applied

    month_index = {m: i for i, m in enumerate(series["months"])}
    start_idx = month_index.get(curve_months[0])
    if start_idx is None:
        return series, applied

    frozen_value = None
    for idx in range(start_idx, len(series["months"])):
        if idx < series["forecast_start_index"]:
            continue
        pos = idx - start_idx

        fi = idx - series["forecast_start_index"]
        if fi >= len(series["forecast"]):
            break

        if pos < len(curve_values):
            pct = curve_values[pos]
            new_value = round(series["forecast"][fi] * (1 + pct / 100.0), 2)
            frozen_value = new_value
        else:
            # curve has ended -- hold the absolute volume from the last
            # curve-active month, regardless of what baseline does now.
            new_value = frozen_value if frozen_value is not None else series["forecast"][fi]

        series["forecast"][fi] = new_value
        applied = True

    return series, applied


def _cell_key(event: EventInput, label: str, context: str) -> Tuple[str, str]:
    if event.event_scope == EventScope.PRODUCT_EVENT:
        return (context, label)
    if event.event_scope == EventScope.MARKET_EVENT:
        return (label, context)
    return ("ALL", "ALL")


def _zero_cell_series(template: Optional[dict], ta_name: str, market: str,
                      product: str, label_field: str) -> Optional[dict]:
    """Zero baseline for a (market, product) cell that has no stored row --
    shaped like a fetch_series row so every downstream helper treats it
    identically. Window is copied from a sibling cell when one is already
    loaded, else from the TA config grid."""
    if template is not None:
        months, fsi = list(template["months"]), template["forecast_start_index"]
    else:
        grid = get_forecast_grid(ta_name)
        if not grid:
            return None
        months, fsi = grid
        months = list(months)
    return {
        "label": product if label_field == "product" else market,
        "market": market,
        "product": product,
        "source_of_market": "ALL",
        "synthesized": False,
        "new_entity": True,
        "months": months,
        "forecast_start_index": fsi,
        "history": [0.0] * fsi,
        "forecast": [0.0] * (len(months) - fsi),
    }


def _ensure_event_cells(cache_by_cell: Dict[Tuple[str, str], dict], event: EventInput,
                        keys_by_label: Dict[str, Tuple[str, str]]) -> None:
    """A product created after this scenario's forecasts were written has no
    stored row for some (market, product) pairs. Without this, its keys are
    simply absent from the cache, no curve is ever applied, and the event
    fails the overlap check with a misleading 422. Seed a zero baseline
    instead -- zero history, zero baseline forecast -- so the curve has
    something to land on.

    Left non-synthesized on purpose: persist_events_to_db still attempts the
    UPDATE, and if there really is no row behind the cell, its existing
    rowcount-0 warning surfaces that instead of dropping the write in
    silence."""
    if event.event_scope == EventScope.OVERALL_EVENT:
        return
    label_field = "product" if event.event_scope == EventScope.PRODUCT_EVENT else "market"
    template = next(iter(cache_by_cell.values()), None)
    for key in keys_by_label.values():
        if key in cache_by_cell:
            continue
        row = _zero_cell_series(template, event.ta_name, key[0], key[1], label_field)
        if row is not None:
            cache_by_cell[key] = row
            print(f"INFO: no stored market_share row for market={key[0]!r} "
                  f"product={key[1]!r} -- treating as a new entity (zero baseline)")


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
    selected_products: Set[str],
    all_products: List[str],
    grid_fetch_cache: GridFetchCache,
) -> None:
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

        if has_explicit_redistribution:
            targets = [r for r in touched_rows if r["product"] not in selected_products]
            if not targets:
                targets = sibling_rows
        else:
            targets = sibling_rows

        if not targets:
            continue

        weight_total = sum(r["forecast"][i] for r in targets if i < len(r["forecast"]))
        # Proportional redistribution is undefined when every target sits at
        # zero this month (all-new products, or a market whose siblings
        # haven't launched yet) -- split the residual evenly instead of
        # skipping, or the column stops summing to 100.
        even_split = residual / len(targets) if weight_total <= 0 else None

        for row in targets:
            if i >= len(row["forecast"]):
                continue
            if even_split is not None:
                delta = even_split
            else:
                delta = residual * (row["forecast"][i] / weight_total)
            new_value = round(row["forecast"][i] + delta, 4)
            if bounds is not None:
                new_value = max(bounds[0], min(bounds[1], new_value))
            row["forecast"][i] = new_value

    if not has_explicit_redistribution:
        for row in sibling_rows:
            share_cache[(row["market"], row["product"])] = row


def _apply_market_scale_to_siblings(
    cache: CacheType,
    scenario_name: str,
    ta_name: str,
    product: str,
    market_scale: Dict[str, List[float]],
    all_products: List[str],
    grid_fetch_cache: GridFetchCache,
) -> None:
    share_cache = cache["market_share"]
    bounds = CLAMP_BOUNDS["market_share"]

    for market, scale in market_scale.items():
        sibling_rows = [
            row for row in _grid_with_cache_overlay(
                scenario_name, ta_name, share_cache, [market], all_products, grid_fetch_cache)
            if row["product"] not in (product, "ALL")
        ]
        if not sibling_rows:
            continue

        for row in sibling_rows:
            combined = row["history"] + row["forecast"]
            fsi = row["forecast_start_index"]
            n = min(len(combined), len(scale))

            new_combined = list(combined)
            for i in range(n):
                new_v = combined[i] * scale[i]
                new_combined[i] = max(bounds[0], min(bounds[1], round(new_v, 4)))

            row["forecast"] = new_combined[fsi:n] if n < len(combined) else new_combined[fsi:]
            share_cache[(row["market"], row["product"])] = row


def normalize_shares_with_pins(children_values_list, labels, pinned_shares, n):
    """
    Like normalize_shares_to_100, but any product with a directly-saved
    override share (pinned_shares[label] is not None at index t) keeps
    that exact value. The remaining ("free") products are normalized
    proportionally by volume to fill whatever share is left over
    (100 - sum of pinned shares at that index), so all siblings still
    sum to 100 at every time index.

    pinned_shares: dict label -> list[float] | None
    """
    num = len(labels)
    normalized = [[0.0] * n for _ in range(num)]

    for t in range(n):
        pinned_total = 0.0
        free_indices = []
        for c in range(num):
            pin = pinned_shares.get(labels[c])
            if pin is not None and t < len(pin):
                normalized[c][t] = pin[t]
                pinned_total += pin[t]
            else:
                free_indices.append(c)

        remaining = max(0.0, 100.0 - pinned_total)
        free_total_vol = sum(
            children_values_list[c][t] if t < len(children_values_list[c]) else 0
            for c in free_indices
        )
        for c in free_indices:
            val = children_values_list[c][t] if t < len(children_values_list[c]) else 0
            if free_total_vol > 0:
                normalized[c][t] = round((val / free_total_vol) * remaining, 2)
            else:
                normalized[c][t] = 0.0

    return normalized


def _market_event_volume_conserving_shares(
    cache: CacheType,
    scenario_name: str,
    ta_name: str,
    product: str,
    selected_market: str,
    impacted_markets: List[Tuple[str, float]],
    event,
) -> Tuple[Dict[str, List[float]], Dict[str, List[float]]]:
    """Re-splits `product`'s FIXED total volume across the touched markets.
    Returns ({}, {}) when that pool doesn't exist -- e.g. a product created
    after this scenario was forecast, or one still at zero everywhere.
    The caller falls back to plain curve application in that case (see
    apply_events_to_baseline): with no pool to conserve, the curve defines
    the product's share in each market directly instead."""

    share_cache = cache["market_share"]
    volume_cache = cache["market_volume"]
    bounds = CLAMP_BOUNDS["market_share"]
    touched_markets = [selected_market] + [m for m, _ in impacted_markets]

    needed = [(m, product) for m in touched_markets] + [(m, "ALL") for m in touched_markets]
    missing = [k for k in needed if k not in share_cache]
    if missing:
        prod_rows = _aggregate_by_cell(
            fetch_series(scenario_name, ta_name, "market_share", label_field="market",
                         market=touched_markets, products=[product], source_of_market=None),
            "market_share", scenario_name, ta_name)
        all_rows = fetch_series(scenario_name, ta_name, "market_share", label_field="market",
                                 market=touched_markets, products=["ALL"], source_of_market="ALL")
        for row in prod_rows + all_rows:
            share_cache.setdefault((row["market"], row["product"]), row)

    if any((m, product) not in share_cache or (m, "ALL") not in share_cache for m in touched_markets):
        print("BAILOUT: missing market_share cells for volume-conserving reconcile")
        return {}, {}

    # Overall portfolio volume (market="ALL", product="ALL") -- needed to
    # convert between (market,"ALL")'s percentage-of-portfolio and each
    # market's own raw volume total. Reuse if a prior event this run
    # already fetched it into the shared volume_cache.
    overall_key = ("ALL", "ALL")
    if overall_key not in volume_cache:
        overall_rows = fetch_series(scenario_name, ta_name, "market_volume",
                                     label_field="market", market="ALL", products=["ALL"])
        if overall_rows:
            volume_cache[overall_key] = overall_rows[0]
    overall_row = volume_cache.get(overall_key)
    if overall_row is None:
        print("BAILOUT: no overall portfolio market_volume row found")
        return {}, {}

    n = len(share_cache[(selected_market, product)]["months"])
    overall_combined = overall_row["history"] + overall_row["forecast"]
    overall_vol = [overall_combined[i] if i < len(overall_combined) else 0.0 for i in range(n)]

    # ---- Each touched market's own raw total volume (all products), and
    # `product`'s own raw volume within it -- both derived the same way
    # _derive_volume_grid does (overall_vol * market_share_all/100, then
    # * product's own within-market share/100).
    market_vols: Dict[str, List[float]] = {}
    product_vols: Dict[str, List[float]] = {}
    for market in touched_markets:
        all_row = share_cache[(market, "ALL")]
        all_combined = all_row["history"] + all_row["forecast"]
        market_share_all_pct = [all_combined[i] if i < len(all_combined) else 0.0 for i in range(n)]
        market_vols[market] = [overall_vol[i] * market_share_all_pct[i] / 100.0 for i in range(n)]

        prod_row = share_cache[(market, product)]
        prod_combined = prod_row["history"] + prod_row["forecast"]
        prod_share = [prod_combined[i] if i < len(prod_combined) else 0.0 for i in range(n)]
        product_vols[market] = [market_vols[market][i] * prod_share[i] / 100.0 for i in range(n)]

    # `product`'s fixed total across just the touched markets -- the pool
    # being re-split; never changes because of this event.
    product_total_vol = [sum(product_vols[m][i] for m in touched_markets) for i in range(n)]

    # No pool at all: a brand-new product has zero volume in every touched
    # market, so every target below would come out as a hard zero. Bail so
    # the caller can apply the curve directly instead of silently writing
    # zeros over the product's own forecast.
    if not any(product_total_vol):
        print(f"BAILOUT: product={product!r} has no baseline volume across "
              f"{touched_markets} -- nothing to redistribute")
        return {}, {}

    baseline_cross_pct = [
        round(product_vols[selected_market][i] / product_total_vol[i] * 100, 4) if product_total_vol[i] else 0.0
        for i in range(n)
    ]

    fsi = share_cache[(selected_market, product)]["forecast_start_index"]
    months = share_cache[(selected_market, product)]["months"]
    month_index = {m: i for i, m in enumerate(months)}
    start_month = event.start_date.strftime("%Y-%m-%d")
    start_idx = month_index.get(start_month)
    baseline_pct_at_start = baseline_cross_pct[start_idx] if start_idx is not None and start_idx < n else 0.0
    _i = start_idx if start_idx is not None else 0
    print(
        f"DEBUG scenario={scenario_name!r} market={selected_market!r} product={product!r} "
        f"month_idx={_i} "
        f"market_vols[{selected_market}]={market_vols[selected_market][_i]:.2f} "
        f"overall_vol={overall_vol[_i]:.2f} "
        f"product_vols[{selected_market}]={product_vols[selected_market][_i]:.2f} "
        f"product_total_vol={product_total_vol[_i]:.2f} "
        f"baseline_cross_pct={baseline_cross_pct[_i]:.4f} "
        f"market_vols_pct_of_overall={(market_vols[selected_market][_i] / overall_vol[_i] * 100 if overall_vol[_i] else 0):.4f}"
    )

    result = compute_event_forecast(event, baseline_pct=baseline_pct_at_start)
    event_start_idx = month_index.get(result.months[0]) if result.months else None
    if event_start_idx is None:
        return {}, {}

    # ---- Target cross-share curve per touched market
    target_cross_share: Dict[str, List[float]] = {}

    hold_selected = result.selected_curve[-1] if result.selected_curve else baseline_pct_at_start
    selected_target = list(baseline_cross_pct)
    for i in range(event_start_idx, n):
        pos = i - event_start_idx
        selected_target[i] = result.selected_curve[pos] if pos < len(result.selected_curve) else hold_selected
    target_cross_share[selected_market] = [max(0.0, min(100.0, v)) for v in selected_target]

    for market, _weight in impacted_markets:
        delta_curve = (result.impacted_curves or {}).get(market)
        if delta_curve is None:
            continue
        market_baseline_cross = [
            round(product_vols[market][i] / product_total_vol[i] * 100, 4) if product_total_vol[i] else 0.0
            for i in range(n)
        ]
        hold_delta = delta_curve[-1] if delta_curve else 0.0
        own_target = list(market_baseline_cross)
        for i in range(event_start_idx, n):
            pos = i - event_start_idx
            own_target[i] = market_baseline_cross[i] + (delta_curve[pos] if pos < len(delta_curve) else hold_delta)
        target_cross_share[market] = [max(0.0, min(100.0, v)) for v in own_target]

    new_forecasts: Dict[str, List[float]] = {}
    market_scale: Dict[str, List[float]] = {}
    impacted_labels = [m for m in target_cross_share if m != selected_market]
    if impacted_labels:
        for i in range(n):
            remaining = 100.0 - target_cross_share[selected_market][i]
            impacted_sum = sum(target_cross_share[m][i] for m in impacted_labels)
            if impacted_sum > 0:
                scale = remaining / impacted_sum
                for m in impacted_labels:
                    target_cross_share[m][i] = max(0.0, min(100.0, target_cross_share[m][i] * scale))
            elif impacted_labels:
                # no baseline volume to scale from -- split remainder evenly
                even_share = remaining / len(impacted_labels)
                for m in impacted_labels:
                    target_cross_share[m][i] = max(0.0, min(100.0, even_share))
    for market, shares in target_cross_share.items():
        new_vol = [product_total_vol[i] * shares[i] / 100.0 for i in range(n)]

        # Everything else in this market is frozen -- market's real new
        # total is exactly (frozen siblings) + (product's new volume).
        other_products_vol = [market_vols[market][i] - product_vols[market][i] for i in range(n)]
        updated_market_total = [other_products_vol[i] + new_vol[i] for i in range(n)]

        new_raw = [
            round(new_vol[i] / updated_market_total[i] * 100, 4) if updated_market_total[i] else 0.0
            for i in range(n)
        ]
        new_forecasts[market] = [max(bounds[0], min(bounds[1], v)) for v in new_raw][fsi:]

        print(f"DEBUG new_forecasts[{market}]:", new_forecasts[market])
        print(f"DEBUG target_cross_share[{market}]:", shares)
        print(f"DEBUG new_vol[{market}]:", new_vol)

        # Siblings' volumes never change -- this ratio, applied to their
        # OWN share, keeps new_share * new_total == old_share * old_total
        # (i.e. their displayed volume stays bit-for-bit frozen even
        # though the market's total under them just moved).
        market_scale[market] = [
            round(market_vols[market][i] / updated_market_total[i], 6) if updated_market_total[i] else 1.0
            for i in range(n)
        ]

        # Persist the market's real new total back as its %-of-portfolio,
        # matching (market,"ALL")'s existing units (see _derive_volume_grid).
        all_key = (market, "ALL")
        all_row = share_cache[all_key]
        all_fsi = all_row["forecast_start_index"]
        new_all_share = [
            round(updated_market_total[i] / overall_vol[i] * 100, 4) if overall_vol[i] else 0.0
            for i in range(n)
        ]
        all_row["forecast"] = [max(bounds[0], min(bounds[1], v)) for v in new_all_share][all_fsi:]

    return new_forecasts, market_scale


def apply_events_to_baseline(events: List[EventInput], entities: Dict[str, List[str]]) -> CacheType:

    cache: CacheType = {metric: {} for metric in METRICS}
    all_products = entities["products"]
    all_markets = entities["markets"]
    grid_fetch_cache: GridFetchCache = {}

    # (scenario_name, ta_name, market) -> accumulated touched products / flag
    product_event_work: Dict[Tuple[str, str, str], Dict] = {}
    # (scenario_name, ta_name, product) -> accumulated touched markets
    market_event_work: Dict[Tuple[str, str, str], Dict] = {}

    for event in events:
        contexts = event.contexts if event.event_scope != EventScope.OVERALL_EVENT else [None]
        for context in contexts:
            event_touched_forecast = False

            label_names = [event.selected_entity or OVERALL_LABEL]
            if event.impacted_entities:
                label_names += [e.name for e in event.impacted_entities]
            keys_by_label = {label: _cell_key(event, label, context) for label in label_names}

            needs_share_fetch = any(key not in cache["market_share"] for key in keys_by_label.values())
            if needs_share_fetch:
                baseline_rows = fetch_baseline(event, "market_share")  # pulls ALL contexts at once
                for row in baseline_rows:
                    cache["market_share"].setdefault((row["market"], row["product"]), row)
                # A product created after this scenario was forecast may have
                # no row for some cells -- seed a zero baseline so its curve
                # has something to land on.
                _ensure_event_cells(cache["market_share"], event, keys_by_label)

            baseline_pct = 0.0
            if event.event_scope != EventScope.OVERALL_EVENT:
                selected_key = keys_by_label[event.selected_entity]
                selected_row = cache["market_share"].get(selected_key)
                if selected_row is not None:
                    start_month = event.start_date.strftime("%Y-%m-%d")
                    month_index = {m: i for i, m in enumerate(selected_row["months"])}
                    idx = month_index.get(start_month)
                    if idx is not None:
                        combined = selected_row["history"] + selected_row["forecast"]
                        if idx < len(combined):
                            baseline_pct = combined[idx]

            result = compute_event_forecast(event, baseline_pct=baseline_pct)
            curves = _entity_curves(result)
            print("\n================ CURVES =================")
            print("Selected:", result.selected_entity)
            print("Selected Curve:", result.selected_curve)

            print("Impacted Curves:")
            for name, curve in (result.impacted_curves or {}).items():
                print(name, curve)

            for metric in METRICS:
                needs_fetch = any(key not in cache[metric] for key in keys_by_label.values())
                if needs_fetch:
                    baseline_rows = fetch_baseline(event, metric)
                    for row in baseline_rows:
                        cache[metric].setdefault((row["market"], row["product"]), row)
                    # market_share only -- market_volume has no per-cell DB
                    # row (it's derived in _derive_volume_grid), so seeding
                    # zeros there would fabricate rows that don't exist.
                    if metric == "market_share":
                        _ensure_event_cells(cache[metric], event, keys_by_label)

                if event.event_scope == EventScope.MARKET_EVENT and metric == "market_share":
                    impacted_weights = [(e.name, e.weight) for e in (event.impacted_entities or [])]
                    new_forecasts, market_scale = _market_event_volume_conserving_shares(
                        cache, event.scenario_name, event.ta_name, context,
                        event.selected_entity, impacted_weights, event)

                    if new_forecasts:
                        for market, forecast in new_forecasts.items():
                            key = (market, context)
                            if key not in cache["market_share"]:
                                continue
                            cache["market_share"][key]["forecast"] = forecast
                            event_touched_forecast = True

                        work_key = (event.scenario_name, event.ta_name, context)
                        entry = market_event_work.setdefault(
                            work_key, {"touched_markets": set(), "market_scale": {}})
                        entry["touched_markets"].update(new_forecasts.keys())
                        entry["market_scale"].update(market_scale)   # <-- carry it forward
                        continue

                    # Nothing to re-split: the product has no baseline volume
                    # in any touched market (a product created after this
                    # scenario was forecast, or one still at zero). Fall
                    # through to plain curve application -- the curve then
                    # DEFINES the product's share in each market rather than
                    # redistributing a fixed pool between them.
                    print(f"INFO: volume-conserving reconcile unavailable for "
                          f"product={context!r}, event={event.event_name!r} -- "
                          f"applying curves directly")

                elif event.event_scope == EventScope.MARKET_EVENT and metric == "market_volume":
                    continue

                bounds = CLAMP_BOUNDS.get(metric)
                selected_label = event.selected_entity or OVERALL_LABEL
                for label, curve in curves.items():
                    key = keys_by_label[label]
                    if key not in cache[metric]:
                        continue
                    if event.event_scope == EventScope.OVERALL_EVENT and metric == "market_share":
                        # Portfolio share of itself is always 100% by definition --
                        # there's no larger whole to move against. Overall events
                        # shape volume growth instead; this synthesized flat row
                        # is never curve-applied.
                        continue
                    if event.event_scope == EventScope.OVERALL_EVENT and metric == "market_volume":
                        cache[metric][key], applied = _apply_growth_pct_to_series(
                            cache[metric][key], result.months, curve)
                    else:
                        mode = "set" if (metric == "market_share" and label == selected_label) else "add"

                        print("\n================ APPLY CURVE ================")
                        print("Metric :", metric)
                        print("Label  :", label)
                        print("Mode   :", mode)
                        print("Curve  :", curve)
                        cache[metric][key], applied = _apply_curve_to_series(
                            cache[metric][key], result.months, curve, bounds, mode=mode)
                    event_touched_forecast = event_touched_forecast or applied

            if not event_touched_forecast:
                # Distinguish "this entity has no forecast rows at all" (a
                # newly created product whose rows were never written) from
                # a genuine window mismatch -- the two need different fixes.
                if not any(k in cache["market_share"] for k in keys_by_label.values()):
                    raise HTTPException(422, detail=(
                        f"Event '{event.event_name}' references entities with no stored "
                        f"market_share rows in scenario '{event.scenario_name}' "
                        f"(context={context}). If this is a newly created product, its "
                        f"forecast rows must be written to {TABLE} first."))
                raise HTTPException(422, detail=(
                    f"Event '{event.event_name}' (context={context}, start_date={event.start_date}, "
                    f"duration_months={event.duration_months}) does not overlap the forecast window."))

            if event.event_scope == EventScope.PRODUCT_EVENT:
                work_key = (event.scenario_name, event.ta_name, context)
                entry = product_event_work.setdefault(work_key, {
                    "touched_products": set(), "has_explicit_redistribution": False, "selected_products": set()})
                entry["touched_products"].update(curves.keys())
                entry["has_explicit_redistribution"] |= bool(event.impacted_entities)
                entry["selected_products"].add(event.selected_entity)

    # Reconcile once every event's curve has landed in the cache.
    for (scenario_name, ta_name, market), entry in product_event_work.items():
        _reconcile_product_event_market(
            cache, scenario_name, ta_name, market,
            touched_products=list(entry["touched_products"]),
            has_explicit_redistribution=entry["has_explicit_redistribution"],
            selected_products=entry["selected_products"],
            all_products=all_products,
            grid_fetch_cache=grid_fetch_cache,
        )
    for (scenario_name, ta_name, product), entry in market_event_work.items():
        _apply_market_scale_to_siblings(
            cache, scenario_name, ta_name, product,
            market_scale=entry["market_scale"],
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


def _derive_volume_grid(
    share_grid: List[dict],
    market_share_all: List[dict],
    overall_volume: List[dict],
) -> List[dict]:
    """market_volume has no per-cell DB row -- derived at display time as
    cell's market_share% applied to the current overall total. Not persisted.

    Lookups are by month LABEL and tolerant of misses: a market with no
    canonical ALL row, or a month a series doesn't cover, yields 0.0 for
    that cell rather than raising -- a new product/market must not be able
    to take down the whole view."""
    if not overall_volume or not share_grid:
        return []
    overall = overall_volume[0]
    overall_month_index = {m: i for i, m in enumerate(overall["months"])}

    market_share_lookup: Dict[str, Dict[str, float]] = {}
    for row in market_share_all:
        market_share_lookup[row["market"]] = dict(
            zip(row["months"], row["history"] + row["forecast"])
        )

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
        by_month = market_share_lookup.get(cell["market"])
        if by_month is None:
            # No canonical (market, "ALL") share row -- can't scale this
            # cell to volume. Zero rather than crash; the market_share
            # views are unaffected.
            print(f"WARNING: no market-level ALL share row for market="
                  f"{cell['market']!r} -- derived volume is 0 for its cells")
            by_month = {}

        values = []
        for month, share_pct in zip(cell["months"], combined_share):
            total = _total_at(month)
            market_share = by_month.get(month)
            if total is None or market_share is None:
                values.append(0.0)
                continue
            # Unrounded on purpose -- _round_metrics_views does the single
            # rounding pass at the end. Rounding to 2 here and then to 0
            # there rounds the same number twice, which can shift a cell by
            # an extra half unit for no benefit.
            market_volume = total * market_share / 100
            values.append(market_volume * share_pct / 100)

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


def _monthly_parent_child_view(
    grid,
    parent_field,
    child_field,
    overall_series,
    metric,
    volume_grid=None,
    overall_volume_series=None,
):
    """
    Groups grid cells into parent-with-children rows for the monthly view.

    For market_volume:
        Parent = sum(children)

    For market_share:
        Parent share is 100% -- each parent's own internal breakdown, so
        its children sum to 100 under it.

    A parent whose children are all new products (no volume yet) has no
    volume rows to fold; that yields an all-zero parent total and 0.00%
    children rather than an index error.
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

            volume_children = [
                r for r in (volume_grid or [])
                if r[parent_field] == label
            ]

            parent_volume = (_sum_series(volume_children) if volume_children
                             else _empty_series(months, fsi))
            parent_totals = parent_volume["history"] + parent_volume["forecast"]

            # Parent share is always 100% -- this hierarchy shows each
            # parent's own internal breakdown (children sum to 100 under
            # it), not the parent's share of the overall portfolio.
            parent_shares = [100.0] * len(parent_totals)
            parent_history = parent_shares[:fsi]
            parent_forecast = parent_shares[fsi:]
            parent_values = parent_shares

            children = []
            for child in volume_children:
                child_volumes = child["history"] + child["forecast"]
                shares = [
                    round(cv / pv * 100, 2) if pv else 0.0
                    for cv, pv in zip(child_volumes, parent_totals)
                ]

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
    grouped: Dict[str, List[dict]] = {}
    for row in grid:
        grouped.setdefault(row[field], []).append(row)

    result = []
    for label, rows in grouped.items():
        result.append({"label": label, **_sum_series(rows)})
    return result


def _monthly_flat_view_from_canonical_rows(rows: List[dict]) -> Tuple[dict, List[dict]]:

    if not rows:
        return {"months": [], "forecast_start_index": 0, "series": []}, []
    months = rows[0]["months"]
    fsi = rows[0]["forecast_start_index"]
    chart = {
        "months": months,
        "forecast_start_index": fsi,
        "series": [{"label": r["market"], "history": r["history"], "forecast": r["forecast"]} for r in rows],
    }
    flat_rows = [{"label": r["market"], "values": r["history"] + r["forecast"]} for r in rows]
    return chart, flat_rows


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
    if not grid:
        return {"months": [], "forecast_start_index": 0, "series": []}, []

    months = grid[0]["months"]
    fsi = grid[0]["forecast_start_index"]
    if overall_volume_series is None:
        child_series = _group_series_by_field(grid, child_field)
    else:
        grouped = _group_series_by_field(grid, child_field)
        overall_by_month = dict(
            zip(overall_volume_series["months"],
                overall_volume_series["history"] + overall_volume_series["forecast"])
        )

        child_series = []
        for g in grouped:
            values = g["history"] + g["forecast"]
            shares = []
            for month, v in zip(g["months"], values):
                total = overall_by_month.get(month)
                shares.append(round((v / total) * 100, 2) if total else 0.0)

            g_fsi = g["forecast_start_index"]
            child_series.append({
                "label": g["label"],
                "months": g["months"],
                "forecast_start_index": g_fsi,
                "history": shares[:g_fsi],
                "forecast": shares[g_fsi:],
            })

    monthly_chart = {
        "months": months,
        "forecast_start_index": fsi,
        "series": [{"label": s["label"], "history": s["history"], "forecast": s["forecast"]} for s in child_series],
    }
    flat_rows = [{"label": s["label"], "values": s["history"] + s["forecast"]} for s in child_series]
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
        # Parent yearly volume
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

        #
        # Parent share is always 100% -- this hierarchy is each parent's
        # own internal breakdown, not its share of the overall portfolio.
        #
        parent_shares = [100.0] * len(parent_totals)

        parent_history = parent_shares[:yearly_fsi]
        parent_forecast = parent_shares[yearly_fsi:]

        parent_series.append({
            "label": label,
            "history": parent_history,
            "forecast": parent_forecast,
        })

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

            #
            # Child share = child's own yearly volume as a % of its
            # parent's yearly volume. A product that launches mid-window
            # is simply 0.00 in the years before it has volume.
            #
            shares = [
                round(cv / pv * 100, 2) if pv else 0.0
                for cv, pv in zip(child_totals, parent_totals)
            ]

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


def _resolve_coverage(row: dict) -> Optional[CoverageInput]:
    """Coverage is inferred purely from whether the FE included the coverage
    fields on the row -- there's no separate enable_coverage flag sent by
    the FE. Both peak fields must be present (not None) for coverage to
    apply. Single source of truth -- used both to build the EventInput's
    coverage and to report back enable_coverage in the response row, so
    the two can never disagree."""
    if row.get("coverage_peak_percent") is None or row.get("coverage_peak_months") is None:
        return None
    return CoverageInput(
        curve_type=row.get("coverage_curve_type", row["curve_type"]),
        factor=row.get("coverage_factor", row.get("factor", 1.0)),
        peak_pct=row["coverage_peak_percent"],
        peak_months=row["coverage_peak_months"],
    )


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


def _monthly_cell_shares(volume_grid: List[dict], cell_pairs: Set[Tuple[str, str]],
                          parent_field: str, child_field: str) -> dict:
    """Monthly counterpart to _yearly_cell_shares: per (parent, child) cell
    share = that cell's own volume / its parent's total volume that month,
    matching the pivot _monthly_parent_child_view uses for hierarchy_rows.
    Must NOT reuse raw market_share grid values here -- those are keyed to
    a different pivot (see _scoped_cells_chart, which is fine for
    market_volume but wrong for market_share)."""
    if not volume_grid or not cell_pairs:
        return {"months": [], "forecast_start_index": 0, "series": []}

    months = volume_grid[0]["months"]
    fsi = volume_grid[0]["forecast_start_index"]
    n = len(months)

    parent_totals: Dict[str, List[float]] = {}
    by_parent: Dict[str, List[dict]] = {}
    for row in volume_grid:
        by_parent.setdefault(row[parent_field], []).append(row)
    for label, rows in by_parent.items():
        combined = [0.0] * n
        for r in rows:
            vals = r["history"] + r["forecast"]
            for i in range(min(n, len(vals))):
                combined[i] += vals[i]
        parent_totals[label] = combined

    series = []
    for cell in volume_grid:
        key = (cell[parent_field], cell[child_field])
        if key not in cell_pairs:
            continue
        vals = cell["history"] + cell["forecast"]
        totals = parent_totals.get(cell[parent_field], [0.0] * n)
        shares = [
            round(vals[i] / totals[i] * 100, 2) if i < len(vals) and totals[i] else 0.0
            for i in range(n)
        ]
        series.append({
            "label": f"{cell[parent_field]} - {cell[child_field]}",
            "history": shares[:fsi],
            "forecast": shares[fsi:],
        })
    return {"months": months, "forecast_start_index": fsi, "series": series}


def build_hierarchical_dual_view(tab: str, metric: str, grid: List[dict], parent_field: str, child_field: str,
                                  agg: str, overall_series: Optional[dict] = None,
                                  volume_grid: Optional[List[dict]] = None,
                                  overall_volume_series: Optional[dict] = None,
                                  scope_cells: Optional[Set[Tuple[str, str]]] = None,
                                  market_share_all: Optional[List[dict]] = None) -> dict:

    levels = TAB_VIEW_LEVELS[tab]
    view_options = [
        {"label": levels["flat_label"], "value": levels["flat_key"]},
        {"label": levels["hierarchy_label"], "value": levels["hierarchy_key"]},
    ]

    if not grid:
        empty_chart = {"months": [], "forecast_start_index": 0, "series": []}
        empty_side = {
            "view_options": view_options,
            "selected_view": levels["flat_key"],
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
    monthly_parent_chart, hierarchy_rows, overall_row = _monthly_parent_child_view(
        grid,
        parent_field,
        child_field,
        overall_series,
        metric,
        volume_grid,
        overall_volume_series,
    )

    # Once markets/products are selected in selected_filter, the hierarchy
    # chart shows only the (market, product) cells implied by that
    # selection -- every child under each selected parent -- instead of
    # the full parent-summed rollup. The table (hierarchy_rows, computed
    # above) keeps showing the full nested rollup regardless; only the
    # chart series change here.
    if scope_cells:
        if metric == "market_share":
            monthly_parent_chart = _monthly_cell_shares(volume_grid, scope_cells, parent_field, child_field)
        else:
            monthly_parent_chart = _scoped_cells_chart(grid, scope_cells, parent_field, child_field)

    if metric == "market_share":
        if tab == "market_event" and market_share_all:
            monthly_child_chart, flat_rows = _monthly_flat_view_from_canonical_rows(market_share_all)
        else:
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
        "headers": monthly_parent_chart["months"] if monthly_parent_chart["months"] else grid[0]["months"],
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
        if tab == "market_event" and market_share_all:
            child_yearly = _to_yearly_chart(market_share_all, YEARLY_AGG["market_share"])
        else:
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

    # Same scoped-values swap as monthly, but built off the already-
    # scaffolded per-cell yearly helpers (_yearly_cell_shares /
    # _yearly_cell_totals) instead of _scoped_cells_chart, since
    # yearly needs the year-bucketing logic those helpers already
    # implement. cell_rows carry both "parent" and "child" keys, so we
    # filter on the (parent, child) pair -- same identity used by
    # _scoped_cells_chart for monthly -- to keep each product only
    # paired with the markets it's actually selected against, not
    # every market it happens to share a name with.
    if scope_cells:
        if metric == "market_share":
            cell_rows = _yearly_cell_shares(volume_grid, parent_field, child_field, overall_volume_series)
        else:
            cell_rows = _yearly_cell_totals(grid, parent_field, child_field, agg)

        parent_yearly = {
            "years": parent_yearly["years"],
            "forecast_start_index": parent_yearly["forecast_start_index"],
            "series": [
                {"label": f"{c['parent']} - {c['child']}", "history": c["history"], "forecast": c["forecast"]}
                for c in cell_rows
                if (c["parent"], c["child"]) in scope_cells
            ],
        }

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
            "selected_view": levels["flat_key"],
            levels["flat_key"]: {"chart": monthly_child_chart, "table": monthly_flat_table},
            levels["hierarchy_key"]: {"chart": monthly_parent_chart, "table": monthly_hierarchy_table},
        },
        "yearly": {
            "view_options": view_options,
            "selected_view": levels["flat_key"],
            levels["flat_key"]: {"chart": child_yearly, "table": yearly_flat_table},
            levels["hierarchy_key"]: {"chart": parent_yearly, "table": yearly_hierarchy_table},
        },
    }


def _selected_filter_cells(
    tab: str,
    entities: Dict[str, List[str]],
    selected_filter: dict,
) -> Optional[Set[Tuple[str, str]]]:
    if tab not in TAB_HIERARCHY:
        return None
    parent_field, child_field = TAB_HIERARCHY[tab]
    parent_key = "markets" if parent_field == "market" else "products"
    child_key = "markets" if child_field == "market" else "products"

    raw_parents = selected_filter.get(parent_key) or []
    # FE may send a single selection as a bare string instead of a list --
    # normalize so we never iterate over a string's characters.
    selected_parents = [raw_parents] if isinstance(raw_parents, str) else list(raw_parents)
    if not selected_parents:
        return None

    all_children = entities.get(child_key, [])
    return {(parent, child) for parent in selected_parents for child in all_children}


def _scoped_cells_chart(grid: List[dict], cell_pairs: Set[Tuple[str, str]],
                         parent_field: str, child_field: str) -> dict:
    """Builds a monthly chart with one series per (parent, child) grid cell
    named in cell_pairs -- e.g. the (market, product) pairs implied by
    selected_filter (see _selected_filter_cells)."""

    if not grid or not cell_pairs:
        return {"months": [], "forecast_start_index": 0, "series": []}
    months = grid[0]["months"]
    fsi = grid[0]["forecast_start_index"]
    series = [
        {"label": f"{cell[parent_field]} - {cell[child_field]}",
         "history": cell["history"], "forecast": cell["forecast"]}
        for cell in grid
        if (cell[parent_field], cell[child_field]) in cell_pairs
    ]
    return {"months": months, "forecast_start_index": fsi, "series": series}


def _build_hierarchy_views(tab: str, scenario_name: str, ta_name: str, entities: Dict[str, List[str]],
                            cache: Optional[CacheType] = None,
                            date_range: Tuple[Optional[str], Optional[str]] = (None, None),
                            selected_filter: Optional[dict] = None
                            ) -> Tuple[Dict, Optional[str]]:

    parent_field, child_field = TAB_HIERARCHY[tab]
    markets = entities.get("markets", [])
    products = entities.get("products", [])
    start_date, end_date = date_range
    scope_cells = _selected_filter_cells(tab, entities, selected_filter or {})

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
        # A cell the event created from scratch (new product with no stored
        # row) exists only in the cache -- fetch_grid never returned it, so
        # the overlay above can't place it. Append it so the new product
        # actually shows up in the tables/charts.
        known = {(c["market"], c["product"]) for c in share_grid}
        for (market, product), row in cache["market_share"].items():
            if product == "ALL" or market == "ALL":
                continue
            if (market, product) in known:
                continue
            if market in markets and product in products:
                share_grid.append(copy.deepcopy(row))

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

    market_share_all = fetch_series(
        scenario_name, ta_name, "market_share",
        label_field="market", market=markets, products=["ALL"],
        source_of_market="ALL",
    )
    if cache is not None:
        market_share_all = [
            cache["market_share"].get((row["market"], row["product"]), row)
            for row in market_share_all
        ]

    volume_grid = _derive_volume_grid(
        share_grid,
        market_share_all,
        overall_volume_rows,
    )

    share_grid = _clip_series_list(share_grid, start_date, end_date)
    volume_grid = _clip_series_list(volume_grid, start_date, end_date)
    market_share_all_clipped = _clip_series_list(market_share_all, start_date, end_date)
    if overall_share is not None:
        overall_share = _clip_series_to_range(overall_share, start_date, end_date)
    overall_volume_rows = _clip_series_list(overall_volume_rows, start_date, end_date)

    overall_volume_series = overall_volume_rows[0] if overall_volume_rows else None
    metrics_views = {
        "market_share": build_hierarchical_dual_view(
            tab, "market_share", share_grid, parent_field, child_field, YEARLY_AGG["market_share"],
            overall_series=overall_share, volume_grid=volume_grid,
            overall_volume_series=overall_volume_series, scope_cells=scope_cells,
            market_share_all=market_share_all_clipped),
        "market_volume": build_hierarchical_dual_view(
            tab, "market_volume", volume_grid, parent_field, child_field, YEARLY_AGG["market_volume"],
            overall_series=overall_volume_series, volume_grid=volume_grid,
            overall_volume_series=overall_volume_series, scope_cells=scope_cells),
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
    """Bucketed by each series' OWN months, not series_list[0]'s -- a series
    that covers a shorter window (or none at all) simply contributes 0.0 to
    the years it doesn't reach, instead of reading another series' months."""
    if not series_list:
        return {"years": [], "forecast_start_index": 0, "series": []}

    reference = max(series_list, key=lambda s: len(s["months"]))
    months = reference["months"]
    fsi = reference["forecast_start_index"]
    years = sorted({m[:4] for m in months})
    if not years:
        return {"years": [], "forecast_start_index": 0, "series": []}
    first_forecast_year = months[fsi][:4] if fsi < len(months) else years[-1]
    yearly_fsi = years.index(first_forecast_year)

    yearly_series = []
    for s in series_list:
        combined = s["history"] + s["forecast"]
        by_year: Dict[str, List[float]] = {}
        for m, v in zip(s["months"], combined):
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
    """First forecast month. Rows with fsi == 0 are skipped -- an all-forecast
    row is what a brand-new product looks like, and taking months[0] from it
    would report the start of history as the forecast start for the whole tab."""
    for rows in series_by_metric.values():
        for row in rows:
            fsi = row["forecast_start_index"]
            if 0 < fsi < len(row["months"]):
                return row["months"][fsi]
    return None


def build_metrics_views(tab: str, scenario_name: str, ta_name: str, entities: dict,
                         events: List[EventInput],
                         date_range: Tuple[Optional[str], Optional[str]] = (None, None),
                         selected_filter: Optional[dict] = None
                         ) -> Tuple[Dict, Optional[str], CacheType]:
    """Builds metrics_views for the actively-edited tab, plus returns the raw
    cache so the caller can persist without recomputing.

    `selected_filter` is passed straight through to _build_hierarchy_views,
    which uses it to scope the hierarchy chart -- see _selected_filter_cells.
    Not needed for overall_event (no hierarchy chart to scope)."""
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
        tab, scenario_name, ta_name, entities, cache=cache, date_range=date_range,
        selected_filter=selected_filter,
    )
    return metrics_views, forecast_start_date, cache


def build_latest_metrics_views(tab: str, scenario_name: str, ta_name: str, entities: dict,
                                date_range: Tuple[Optional[str], Optional[str]] = (None, None),
                                selected_filter: Optional[dict] = None
                                ) -> Tuple[Dict, Optional[str]]:
    """Same shape as build_metrics_views but for a tab not being edited this
    run -- fresh DB read, reflects the latest persisted values.
    `selected_filter` is threaded through the same way as in
    build_metrics_views, so non-active tabs scope their hierarchy chart
    identically to the active one."""
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

    return _build_hierarchy_views(
        tab, scenario_name, ta_name, entities, cache=None, date_range=date_range,
        selected_filter=selected_filter,
    )


# ======================================================
# 3b. FINAL ROUNDING (display only)
# ======================================================
# Internal calculations (RAS reconciliation, channel blending, residual
# redistribution, etc.) keep their own working precision -- those roundings
# stay where they are, since the math needs stable intermediate values.
# This pass only rounds what actually goes to the FE, once, at the end:
# market_share to 2 decimals, market_volume to whole numbers.

ROUND_DIGITS: Dict[str, int] = {"market_share": 2, "market_volume": 0}

# Precision written to the DB. Kept identical to what the FE displays, so a
# stored share and a displayed share are the same number -- any other view
# deriving volume from these rows (Model Inputs) then lands on the same
# figure this module's own views do. Storing 4 decimals while showing 2 was
# what put the two screens 1-5 units apart on a ~70,000 market: at that
# scale one unit in the second decimal of a share is ~7 units of volume.
#
# This is the STORAGE boundary only. Internal working precision stays at 4
# decimals (see the note above ROUND_DIGITS) -- reconciliation and channel
# blending need stable intermediates, and rounding those to 2 would make
# the sum-to-100 residual bigger, not smaller.
STORE_DECIMALS: Dict[str, int] = {"market_share": 2, "market_volume": 2, PM_METRIC: 2}


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
    coverage = _resolve_coverage(row)

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
        selected_entity = row["markets"][0]     # still single-select
        contexts = row["products"]              # now multi-select
        impacted_field = "impacted_markets"
    else:  # product_event
        selected_entity = row["products"][0]    # still single-select
        contexts = row["markets"]               # now multi-select
        impacted_field = "impacted_products"

    impacted_names = [n for n in row.get(impacted_field, []) if n != selected_entity]
    if not impacted_names and row.get("source_percentages"):
        # Only entries with a POSITIVE share are actually giving up share.
        # The FE sends the full product list in source_percentages with 0
        # for every product the user left unset, so taking every key made
        # each of them an impacted entity -- they'd get a zero curve, a row
        # in the output, and a place in the reconciliation targets despite
        # never having been selected.
        impacted_names = [
            name for name, weight in row["source_percentages"].items()
            if name != selected_entity and (weight or 0) > 0
        ]
    weights = _resolve_weights(row, impacted_names)
    impacted_entities = [ImpactedEntity(name=n, weight=w) for n, w in zip(impacted_names, weights)] or None

    return EventInput(
        **common,
        contexts=contexts,
        selected_entity=selected_entity,
        impacted_entities=impacted_entities,
    )


def tab_config(tab: str, entities: Dict[str, List[str]]) -> dict:
    """`entities` is the full universe, not selected_filter -- always every
    selectable product/market for redistribution. A product added by the
    add-product API is included automatically, since entities comes from a
    live DISTINCT over the outputs table unioned with the product master.

    products/markets are returned for EVERY tab, including overall_event.
    They previously appeared only on market_event/product_event, so on the
    overall_event tab the FE had no list to populate its filter dropdowns
    from. The impact_* keys stay tab-specific -- those drive the
    redistribution pickers, which genuinely differ per tab."""
    all_products = entities["products"]
    all_markets = entities["markets"]
    config = {
        "curve_types": CURVE_TYPES,
        "products": all_products,
        "markets": all_markets,
    }
    if tab == "market_event":
        config["impact_markets"] = all_markets
    elif tab == "product_event":
        config["impact_products"] = all_products
    return config


# ======================================================
# 5. WRITE-BACK PIPELINE
# ======================================================
# Requires (run once): ALTER TABLE raw_hiv_prep.forecast_outputs
#   ADD COLUMN IF NOT EXISTS events_payload JSONB;
#
# Every row this scenario owns is rebuilt here, in one pass, with exactly
# ONE writer per row. That single-owner rule is the point of this section:
# the previous design had the curve application, a sibling-delta step and
# three separate roll-ups all touching market_share rows, and their
# ordering was load-bearing but invisible. Deltas got applied twice, rows
# drifted out of agreement with each other, and the symptom always
# surfaced somewhere else -- on whichever product happened to be correct,
# because the views normalize children to their parent.
#
# The stored rows and what owns each:
#
#   (market, product, 'ALL')      canonical within-market share
#                                 <- the event cache
#   (market, product, <source>)   same share measured inside one source
#                                 <- rescaled so their WEIGHTED sum equals
#                                    the canonical
#   ('ALL', product, 'ALL')       product's share of the whole portfolio
#                                 <- summed from the cells
#   market_share_pm               each market's share of a product's own
#                                 cross-market total
#                                 <- derived from cell volumes
#   (market, 'ALL', <source>)     each source's share of its market
#                                 <- scaled with the market total, these
#                                    are COMPONENTS and must keep summing
#                                    to it
#
# The invariants that tie them together, all checked before anything is
# written (see validate_write_set):
#
#   1. products in a market sum to 100
#   2. a product's per-source rows, weighted by source share, equal its
#      canonical row
#   3. sources in a market sum to 100
#   4. products' portfolio shares sum to 100
#   5. a product's market_share_pm rows sum to 100
#
# A view that rebuilds a market from its sources and a view that reads the
# canonical row land on the same number if and only if 1-3 hold.

# How far a sum may drift from its target before it's reported. Two
# decimals are stored, so a handful of hundredths across a dozen rows is
# rounding; anything larger is a real inconsistency.
INVARIANT_TOLERANCE = 0.05

# One row to write: its identity, the full value series, and the DB row it
# came from (for months / forecast_start_index).
WriteRow = Dict[str, object]


def _row_values(row: dict) -> List[float]:
    return list(row["history"]) + list(row["forecast"])


def _weighted(values_by_source: Dict[str, List[float]],
              weights_by_source: Dict[str, List[float]],
              index: int) -> Optional[float]:
    """Weighted average across sources at one month, or None when no source
    carries any weight there."""
    numerator = 0.0
    denominator = 0.0
    for source, values in values_by_source.items():
        weights = weights_by_source.get(source)
        if weights is None or index >= len(weights) or index >= len(values):
            continue
        numerator += weights[index] * values[index]
        denominator += weights[index]
    if not denominator:
        return None
    return numerator / denominator


def build_write_set(cache: CacheType, scenario_name: str, ta_name: str,
                    entities: Dict[str, List[str]]) -> Tuple[List[WriteRow], List[str]]:
    """Rebuild every row this scenario owns from the post-event cache.

    Returns (write_set, warnings). The write set is complete and internally
    consistent -- persist_events_to_db does nothing but write it."""
    share_cache = cache["market_share"]
    markets = entities.get("markets", [])
    products = entities.get("products", [])
    write_set: List[WriteRow] = []

    if not markets or not products:
        return write_set, []

    # ---- inputs -------------------------------------------------------
    # Canonical per-cell shares: the DB grid with this run's events over it.
    grid_rows = fetch_grid(scenario_name, ta_name, "market_share", markets, products)
    canonical: Dict[Tuple[str, str], dict] = {}
    for row in grid_rows:
        key = (row["market"], row["product"])
        canonical[key] = share_cache.get(key, row)
    # Cells that exist only in the cache (a product materialized this run).
    for key, row in share_cache.items():
        market, product = key
        if product == "ALL" or market == "ALL":
            continue
        if key not in canonical and market in markets and product in products:
            canonical[key] = row

    # Per-source rows for those same cells, and each source's weight.
    source_rows: Dict[Tuple[str, str], Dict[str, dict]] = {}
    for row in fetch_series(scenario_name, ta_name, "market_share",
                            label_field="product", market=markets, products=products,
                            source_of_market=None):
        source = row.get("source_of_market") or "ALL"
        if source == "ALL":
            continue
        source_rows.setdefault((row["market"], row["product"]), {})[source] = row

    market_total_rows: Dict[str, dict] = {}
    weight_rows: Dict[str, Dict[str, dict]] = {}
    for row in fetch_series(scenario_name, ta_name, "market_share",
                            label_field="market", market=markets, products=["ALL"],
                            source_of_market=None):
        source = row.get("source_of_market") or "ALL"
        key = (row["market"], "ALL")
        if source == "ALL":
            market_total_rows[row["market"]] = share_cache.get(key, row)
        else:
            weight_rows.setdefault(row["market"], {})[source] = row

    overall_volume_rows = _fetch_overall_series(scenario_name, ta_name, "market_volume")
    overall_volume = overall_volume_rows[0] if overall_volume_rows else None

    months = next(iter(canonical.values()))["months"] if canonical else []
    n = len(months)

    # ---- 1. canonical cells, normalized so each market sums to 100 -----
    # The event path reconciles this already; renormalizing is a safety net
    # that also absorbs the hundredths lost to 2-decimal storage.
    for market in markets:
        cells = [(p, canonical[(market, p)]) for p in products if (market, p) in canonical]
        if not cells:
            continue
        values = {p: _row_values(row) for p, row in cells}
        for i in range(n):
            total = sum(v[i] for v in values.values() if i < len(v))
            if not total or abs(total - 100.0) <= 1e-9:
                continue
            for p in values:
                if i < len(values[p]):
                    values[p][i] = values[p][i] * 100.0 / total
        for product, row in cells:
            write_set.append({
                "metric": "market_share", "market": market, "product": product,
                "source": "ALL", "values": values[product], "template": row,
            })

    canonical_values = {
        (w["market"], w["product"]): w["values"]
        for w in write_set if w["metric"] == "market_share" and w["source"] == "ALL"
    }

    # ---- 2. per-source cells, pinned to their canonical ----------------
    # Their weighted sum IS the canonical value, so rescaling by
    # canonical / weighted-sum keeps the real variation between sources
    # while making the two readings agree. This is the ONLY place these
    # rows are written.
    for (market, product), by_source in source_rows.items():
        target = canonical_values.get((market, product))
        if target is None:
            continue
        weights = {s: _row_values(r) for s, r in weight_rows.get(market, {}).items()}
        if not weights:
            continue

        values_by_source = {s: _row_values(r) for s, r in by_source.items()}
        for i in range(n):
            current = _weighted(values_by_source, weights, i)
            wanted = target[i] if i < len(target) else 0.0
            for source, values in values_by_source.items():
                if i >= len(values):
                    continue
                if current is None or current == 0:
                    # No baseline shape to preserve -- every source takes
                    # the canonical value, which is self-consistent.
                    values[i] = wanted
                else:
                    values[i] = values[i] * wanted / current

        for source, row in by_source.items():
            write_set.append({
                "metric": "market_share", "market": market, "product": product,
                "source": source, "values": values_by_source[source], "template": row,
            })

    # ---- 3. market totals and their source components ------------------
    # (market, 'ALL', <source>) rows sum to their market total, so they
    # scale with it rather than shifting by its delta.
    for market, row in market_total_rows.items():
        new_values = _row_values(row)
        write_set.append({
            "metric": "market_share", "market": market, "product": "ALL",
            "source": "ALL", "values": new_values, "template": row,
        })

        components = weight_rows.get(market, {})
        if not components:
            continue
        baseline_total = _row_values(
            fetch_series(scenario_name, ta_name, "market_share", label_field="market",
                         market=market, products=["ALL"], source_of_market="ALL")[0]
        ) if market not in share_cache else None

        for source, comp_row in components.items():
            values = _row_values(comp_row)
            if baseline_total:
                for i in range(min(n, len(values))):
                    old = baseline_total[i] if i < len(baseline_total) else 0.0
                    new = new_values[i] if i < len(new_values) else 0.0
                    if old:
                        values[i] = values[i] * new / old
            write_set.append({
                "metric": "market_share", "market": market, "product": "ALL",
                "source": source, "values": values, "template": comp_row,
            })

    # ---- 4. cell volumes, and the two roll-ups derived from them -------
    cell_volume: Dict[Tuple[str, str], List[float]] = {}
    if overall_volume:
        overall_by_month = dict(zip(overall_volume["months"], _row_values(overall_volume)))
        market_share_by_month = {
            market: dict(zip(row["months"], _row_values(row)))
            for market, row in market_total_rows.items()
        }
        for (market, product), values in canonical_values.items():
            weights = market_share_by_month.get(market, {})
            volumes = []
            for i, month in enumerate(months):
                total = overall_by_month.get(month)
                market_pct = weights.get(month)
                if total is None or market_pct is None or i >= len(values):
                    volumes.append(0.0)
                    continue
                volumes.append(total * market_pct / 100.0 * values[i] / 100.0)
            cell_volume[(market, product)] = volumes

    product_volume: Dict[str, List[float]] = {}
    for (market, product), volumes in cell_volume.items():
        totals = product_volume.setdefault(product, [0.0] * n)
        for i, v in enumerate(volumes[:n]):
            totals[i] += v
    overall_by_index = [0.0] * n
    for totals in product_volume.values():
        for i, v in enumerate(totals[:n]):
            overall_by_index[i] += v

    # ('ALL', product): share of the whole portfolio.
    for row in fetch_series(scenario_name, ta_name, "market_share",
                            label_field="product", market="ALL", products=products,
                            source_of_market="ALL"):
        totals = product_volume.get(row["product"])
        if totals is None:
            continue
        values = [
            round(totals[i] / overall_by_index[i] * 100, 4) if overall_by_index[i] else 0.0
            for i in range(n)
        ]
        write_set.append({
            "metric": "market_share", "market": "ALL", "product": row["product"],
            "source": "ALL", "values": values, "template": row,
        })

    # market_share_pm: each market's share of a product's own total.
    for row in fetch_series(scenario_name, ta_name, PM_METRIC,
                            label_field="product", market=markets, products=products,
                            source_of_market="ALL"):
        volumes = cell_volume.get((row["market"], row["product"]))
        totals = product_volume.get(row["product"])
        if volumes is None or totals is None:
            continue
        values = [
            round(volumes[i] / totals[i] * 100, 4) if i < len(totals) and totals[i] else 0.0
            for i in range(n)
        ]
        write_set.append({
            "metric": PM_METRIC, "market": row["market"], "product": row["product"],
            "source": "ALL", "values": values, "template": row,
        })

    warnings = validate_write_set(write_set, markets, products, n)
    return write_set, warnings


def validate_write_set(write_set: List[WriteRow], markets: List[str],
                       products: List[str], n: int) -> List[str]:
    """Check every invariant the views depend on, before anything is
    written. A violation reported here names the market, product and month
    directly -- the alternative is discovering it as two screens quietly
    disagreeing three tabs away."""
    warnings: List[str] = []
    by_key = {(w["metric"], w["market"], w["product"], w["source"]): w["values"]
              for w in write_set}

    def _report(label: str, market: str, product: str, index: int,
                actual: float, target: float) -> None:
        warnings.append(
            f"INVARIANT {label}: market={market} product={product} "
            f"month_index={index} -- got {actual:.4f}, expected {target:.4f}"
        )

    # 1. products in a market sum to 100
    for market in markets:
        rows = [by_key[k] for k in by_key
                if k[0] == "market_share" and k[1] == market
                and k[2] in products and k[3] == "ALL"]
        if not rows:
            continue
        for i in range(n):
            total = sum(r[i] for r in rows if i < len(r))
            if abs(total - 100.0) > INVARIANT_TOLERANCE:
                _report("products-sum-to-100", market, "*", i, total, 100.0)
                break

    # 2. per-source rows weight to their canonical
    for market in markets:
        weights = {k[3]: by_key[k] for k in by_key
                   if k[0] == "market_share" and k[1] == market
                   and k[2] == "ALL" and k[3] != "ALL"}
        if not weights:
            continue
        for product in products:
            values_by_source = {k[3]: by_key[k] for k in by_key
                                if k[0] == "market_share" and k[1] == market
                                and k[2] == product and k[3] != "ALL"}
            target = by_key.get(("market_share", market, product, "ALL"))
            if not values_by_source or target is None:
                continue
            for i in range(n):
                actual = _weighted(values_by_source, weights, i)
                if actual is None or i >= len(target):
                    continue
                if abs(actual - target[i]) > INVARIANT_TOLERANCE:
                    _report("sources-weight-to-canonical", market, product, i, actual, target[i])
                    break

    # 3. sources in a market sum to 100
    for market in markets:
        rows = [by_key[k] for k in by_key
                if k[0] == "market_share" and k[1] == market
                and k[2] == "ALL" and k[3] != "ALL"]
        if not rows:
            continue
        for i in range(n):
            total = sum(r[i] for r in rows if i < len(r))
            if abs(total - 100.0) > INVARIANT_TOLERANCE:
                _report("sources-sum-to-100", market, "ALL", i, total, 100.0)
                break

    # 4. portfolio shares sum to 100
    portfolio = [by_key[k] for k in by_key
                 if k[0] == "market_share" and k[1] == "ALL" and k[3] == "ALL"]
    if portfolio:
        for i in range(n):
            total = sum(r[i] for r in portfolio if i < len(r))
            if abs(total - 100.0) > INVARIANT_TOLERANCE:
                _report("portfolio-sums-to-100", "ALL", "*", i, total, 100.0)
                break

    # 5. a product's market_share_pm rows sum to 100
    for product in products:
        rows = [by_key[k] for k in by_key if k[0] == PM_METRIC and k[2] == product]
        if not rows:
            continue
        for i in range(n):
            total = sum(r[i] for r in rows if i < len(r))
            # A product with no volume anywhere legitimately sums to 0.
            if total and abs(total - 100.0) > INVARIANT_TOLERANCE:
                _report("pm-sums-to-100", "*", product, i, total, 100.0)
                break

    for msg in warnings:
        print(f"WARNING: {msg}")
    return warnings


def persist_events_to_db(
    scenario_name: str,
    ta_name: str,
    rows: List[dict],
    write_set: List[WriteRow],
) -> List[str]:
    """Write the prepared set. No arithmetic here on purpose -- everything
    was decided in build_write_set, so a value that reaches this function
    is written verbatim (bar the storage rounding).

    Skipped for Base, which stays the untouched baseline.

    Returns warnings for rows that matched nothing in the DB, so a
    silently-dropped write is never mistaken for an applied event."""
    if scenario_name == BASELINE_SCENARIO or not write_set:
        return []

    events_payload = json.dumps(rows)
    warnings: List[str] = []

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for entry in write_set:
                template = entry["template"]
                metric = entry["metric"]
                fsi = template["forecast_start_index"]
                values = entry["values"]

                expected = len(template["months"]) - fsi
                forecast = values[fsi:]
                if expected > 0 and len(forecast) != expected:
                    # jsonb_set replaces forecast_values and leaves months
                    # alone, so a short array would leave the row claiming
                    # more months than it carries -- and every later read
                    # pads the gap with zeros, silently blanking a product.
                    msg = (f"REFUSED {metric} | market={entry['market']} | "
                           f"product={entry['product']} | source={entry['source']} -- "
                           f"{len(forecast)} values for a {expected}-month forecast")
                    print(f"ERROR: {msg}")
                    warnings.append(msg)
                    continue

                digits = STORE_DECIMALS.get(metric)
                if digits is not None:
                    forecast = [round(v, digits) for v in forecast]

                cur.execute(
                    f"""
                    UPDATE {TABLE}
                    SET forecast_data = jsonb_set(
                            forecast_data::jsonb, '{{forecast_values}}', %s::jsonb
                        ),
                        events_payload = %s::jsonb,
                        updated_at = now()
                    WHERE scenario_name = %s AND ta_name = %s AND metric = %s
                    AND market = %s AND product = %s
                    AND COALESCE(NULLIF(source_of_market, ''), 'ALL') = %s
                    """,
                    [
                        json.dumps(forecast),
                        events_payload,
                        scenario_name, ta_name, metric,
                        entry["market"], entry["product"], entry["source"],
                    ],
                )
                if cur.rowcount == 0:
                    msg = (f"No matching row for {metric} | market={entry['market']} | "
                           f"product={entry['product']} | source={entry['source']} -- "
                           f"not persisted")
                    print(f"WARNING: {msg}")
                    warnings.append(msg)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return warnings


# ======================================================
# 6. RUN CALCULATION -- one tab in, all three tabs out
# ======================================================

def run_calculation(payload: dict) -> dict:
    # Config-derived month grid is memoized per TA for the duration of a
    # request only -- a product added (or the window edited) between calls
    # must never be served from a stale grid.
    reset_forecast_grid_cache()

    tab = payload["selected_tab"]
    ta_name = payload["ta_name"]
    selected_filter = payload["selected_filter"]
    scenario_name = selected_filter["scenario_name"]
    raw_rows = payload["impact_curve_configuration"]["rows"]
    print("DEBUG raw_rows:", raw_rows)

    # Assign a stable event_id to every row missing one, for FE keying.
    rows = [
        {
            **row,
            "event_id": row.get("event_id", idx + 1),
            "enable_coverage": _resolve_coverage(row) is not None,
        }
        for idx, row in enumerate(raw_rows)
    ]

    # Materialize any registered product that has no rows in THIS scenario
    # yet -- zero history, zero forecast, scoped to scenario_name alone.
    # Other scenarios are untouched; each one materializes the product the
    # first time a calculation is run against it. Must run BEFORE entities
    # are read, since every dropdown and grid cell derives from that query.
    seeded_products = seed_missing_products(scenario_name, ta_name)

    # Full universe, reused for every tab's dropdown config + view scoping.
    entities = fetch_available_entities(scenario_name, ta_name)
    available_scenarios = fetch_available_scenarios(ta_name)
    available_months = fetch_available_months(ta_name)

    # Display-only clip, applied after events are computed against the full baseline.
    date_range = (selected_filter.get("start_date"), selected_filter.get("end_date"))

    events = [row_to_event(row, tab, scenario_name, ta_name) for row in rows]
    active_metrics_views, forecast_start_date, cache = build_metrics_views(
        tab, scenario_name, ta_name, entities, events, date_range=date_range,
        selected_filter=selected_filter,
    )

    # The (ALL, product) roll-up rows behind the Product Distribution (%)
    # view are never touched by an event directly -- rebuild them from the
    # post-event grid so that view moves with the per-cell ones.
    # Rebuild every row this scenario owns -- canonical cells, their
    # per-source rows, the market totals and both roll-ups -- as one
    # internally consistent set, with the invariants checked before
    # anything is written. See section 5.
    write_set, invariant_warnings = build_write_set(
        cache, scenario_name, ta_name, entities)

    # Persist before building the other two tabs so their fresh DB reads pick up this run's changes.
    persist_warnings = invariant_warnings + persist_events_to_db(
        scenario_name, ta_name, rows, write_set)

    # Every tab computed and returned so the FE can switch without a round trip.
    event_tabs = {}
    for t in TABS:
        if t == tab:
            metrics_views = active_metrics_views
            tab_forecast_start_date = forecast_start_date
            tab_rows = rows
        else:
            metrics_views, tab_forecast_start_date = build_latest_metrics_views(
                t, scenario_name, ta_name, entities, date_range=date_range,
                selected_filter=selected_filter,
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

    return _assemble_response(
        ta_name=ta_name,
        selected_filter=selected_filter,
        tab=tab,
        entities=entities,
        available_scenarios=available_scenarios,
        available_months=available_months,
        forecast_start_date=forecast_start_date,
        rows=rows,
        event_tabs=event_tabs,
        warnings=persist_warnings,
        seeded_products=seeded_products,
    )


# ======================================================
# 7. INITIAL LOAD -- same response, no events
# ======================================================

def _assemble_response(ta_name: str, selected_filter: dict, tab: str,
                       entities: Dict[str, List[str]], available_scenarios: List[str],
                       available_months: List[str], forecast_start_date: Optional[str],
                       rows: List[dict], event_tabs: dict,
                       warnings: Optional[List[str]] = None,
                       seeded_products: Optional[List[str]] = None) -> dict:
    """One response shape for both the initial load and Run Calculation, so
    the FE never has to branch on which call produced the payload.

    available_products / available_channels are lifted to the top level:
    the filter bar needs them regardless of which tab is active, and
    digging them out of the active tab's impact_curve_configuration meant
    the dropdowns came up empty whenever that tab didn't carry them.
    `market` is the channel dimension in this schema (Retail / Non-retail),
    hence the alias -- both keys hold the same list."""
    return {
        "ta_name": ta_name,
        "available_scenarios": available_scenarios,
        "available_months": available_months,
        "available_products": entities.get("products", []),
        "available_markets": entities.get("markets", []),
        "available_channels": entities.get("markets", []),
        "selected_filter": selected_filter,
        "selected_tab": tab,
        "impact_curve_configuration": {
            **tab_config(tab, entities),
            "forecast_start_date": forecast_start_date,
            "rows": rows,
        },
        "metric_filters": METRIC_FILTERS,
        "event_tabs": event_tabs,
        # Surfaced so a cell whose write found no DB row (e.g. a new product
        # missing a market_share row for some market) is visible to the FE
        # instead of failing silently.
        "warnings": warnings or [],
        # Products materialized into this scenario during this call, at zero.
        "seeded_products": seeded_products or [],
    }


def load_calculation(payload: dict) -> dict:
    """Initial page load: identical response to run_calculation, but with no
    events applied and nothing persisted -- every tab reads the latest
    stored values.

    This exists because entities (and therefore every dropdown) were only
    ever computed inside run_calculation, so nothing populated the filters
    until the user pressed Run Calculation. Point the screen's load
    endpoint at this.

    `selected_filter` may arrive empty on a cold load -- scenario falls
    back to the first available, and an absent start/end date simply means
    no display clipping."""
    reset_forecast_grid_cache()

    ta_name = payload["ta_name"]
    selected_filter = dict(payload.get("selected_filter") or {})
    tab = payload.get("selected_tab") or TABS[0]

    available_scenarios = fetch_available_scenarios(ta_name)
    scenario_name = selected_filter.get("scenario_name") or (
        available_scenarios[0] if available_scenarios else BASELINE_SCENARIO)
    selected_filter["scenario_name"] = scenario_name

    # Off by default -- see SEED_ON_LOAD. Loading a scenario shouldn't
    # create rows in it; only running a calculation should.
    seeded_products = (
        seed_missing_products(scenario_name, ta_name) if SEED_ON_LOAD else []
    )

    entities = fetch_available_entities(scenario_name, ta_name)
    available_months = fetch_available_months(ta_name)
    date_range = (selected_filter.get("start_date"), selected_filter.get("end_date"))

    event_tabs = {}
    for t in TABS:
        metrics_views, tab_forecast_start_date = build_latest_metrics_views(
            t, scenario_name, ta_name, entities, date_range=date_range,
            selected_filter=selected_filter,
        )
        event_tabs[t] = {
            "impact_curve_configuration": {
                **tab_config(t, entities),
                "forecast_start_date": tab_forecast_start_date,
                "rows": [],  # no events on load
            },
            "metrics_views": _round_metrics_views(metrics_views),
        }

    forecast_start_date = event_tabs[tab]["impact_curve_configuration"]["forecast_start_date"]

    return _assemble_response(
        ta_name=ta_name,
        selected_filter=selected_filter,
        tab=tab,
        entities=entities,
        available_scenarios=available_scenarios,
        available_months=available_months,
        forecast_start_date=forecast_start_date,
        rows=[],
        event_tabs=event_tabs,
        seeded_products=seeded_products,
    )