"""
Run Calculation service for HCV Market Events.

Applies user-configured event curves (ramp-up / S-curve / etc.) to the BASE
transaction data and returns updated metrics_views for all three tabs.

Curve math is reused from the HIV team's Events_Calculation module.
Data access uses the existing liver_market_events repository and helpers.
"""

import copy
from datetime import date as date_type

from app.db.connection import get_connection
from app.hiv_treat.routes.Events_Calculation import (
    CoverageInput, CurveType, EventInput, EventScope, ImpactedEntity,
    compute_event_forecast,
)
from app.liver_market_events.helpers.data_helpers import (
    flat_forecast,
    get_volume,
    organize_raw_data,
)
from app.liver_market_events.helpers.date_helpers import (
    add_months,
    generate_month_range,
    parse_year_month,
    to_month_label,
)
from app.liver_market_events.repository.market_events_repo import (
    get_all_configs_for_ta,
    get_payers,
    get_products,
    get_volume_by_product_payer,
    save_impact_rows,
    load_impact_rows,
)
from app.liver_market_events.services.market_events_service import (
    CURVE_TYPES,
    DEFAULT_FORECAST_MONTHS,
    METRIC_FILTERS,
    _available_months_fallback,
    _build_overall_event_metrics,
    _build_payer_event_metrics,
    _build_product_event_metrics,
    _clamp_min_start_to_transaction_floor,
    _get_date_range_from_configs,
    _get_scenarios_with_base,
    _load_scenario_raw_series,
    _merge_config_with_saved_data,
    _persist_market_events_result,
)


# ---------------------------------------------------------------------------
# Data pre-population
# ---------------------------------------------------------------------------

def _fill_forecast_data(data: dict, month_tuples: list, forecast_start_index: int) -> None:
    """
    Pre-populate forecast months in `data` with flat_forecast values for every
    (product, payer) pair that appears in the history window.

    Without this, applying event curves to months not yet in transaction_data
    would silently have no effect (the key simply wouldn't exist in the dict).
    Modifies `data` in-place.
    """
    history_months = month_tuples[:forecast_start_index]
    forecast_months = month_tuples[forecast_start_index:]
    if not forecast_months:
        return

    pairs: set = set()
    for (y, m) in history_months:
        for prod, payer_dict in data.get((y, m), {}).items():
            for payer in payer_dict:
                pairs.add((prod, payer))

    for (prod, payer) in pairs:
        hist_vals = [
            data.get((y, m), {}).get(prod, {}).get(payer, 0.0)
            for (y, m) in history_months
        ]
        fcast_val = flat_forecast(hist_vals)
        if fcast_val <= 0:
            continue
        for (y, m) in forecast_months:
            data.setdefault((y, m), {}).setdefault(prod, {})
            if data[(y, m)][prod].get(payer, 0.0) <= 0:
                data[(y, m)][prod][payer] = fcast_val


def _recompute_total_all(data: dict, month_tuples: list) -> list:
    return [
        sum(
            v
            for prod_dict in data.get((y, m), {}).values()
            for v in prod_dict.values()
            if v > 0
        )
        for (y, m) in month_tuples
    ]


def _context_total(data: dict, y: int, m: int, ctx_products: list, ctx_payers: list) -> float:
    """
    Sum of volume across the given product x payer context for one month.

    A payer_event/product_event row's context (ctx_products/ctx_payers)
    narrows the event to apply WITHIN that slice only -- both the selected
    entity's target share AND the impacted entities' compensating loss are
    interpreted relative to THIS context's own total (e.g. ASGA's own
    volume), not the grand total across every product. This keeps the whole
    redistribution zero-sum strictly within the context: the impacted
    entities lose share from their OWN volume in that same context only,
    never touching their volume in products/payers the event didn't select.
    """
    return sum(
        v
        for prod in ctx_products
        for payer, v in data.get((y, m), {}).get(prod, {}).items()
        if payer in ctx_payers
    )


def _renormalize_context(data: dict, y: int, m: int, ctx_products: list,
                          ctx_payers: list, orig_total: float) -> None:
    """
    Rescale cells within ctx_products x ctx_payers for one month so they sum
    back to orig_total (the context's own pre-delta total) -- a safety net
    for rows with no impacted entities configured, which would otherwise
    inflate the CONTEXT's total instead of redistributing it.

    Scoped to the event's own context only, so it can never touch products/
    payers outside it (e.g. an untouched product like GILD keeps its own
    natural trend, and the grand total is preserved as a consequence since
    this context reverts to exactly its pre-event total).
    """
    ym = data.get((y, m), {})
    current_total = sum(
        ym.get(prod, {}).get(payer, 0.0)
        for prod in ctx_products
        for payer in ctx_payers
        if ym.get(prod, {}).get(payer, 0.0) > 0
    )
    if current_total > 0 and abs(current_total - orig_total) > 1e-6:
        scale = orig_total / current_total
        for prod in ctx_products:
            prod_cell = ym.get(prod)
            if not prod_cell:
                continue
            for payer in ctx_payers:
                if payer in prod_cell and prod_cell[payer] > 0:
                    prod_cell[payer] = max(0.0, prod_cell[payer] * scale)


# ---------------------------------------------------------------------------
# Delta application helpers
# ---------------------------------------------------------------------------

def _apply_payer_delta(data: dict, y: int, m: int,
                       payer: str, show_products: list, delta_vol: float) -> None:
    """
    Scale all (product, payer) cells for `payer` so the payer's total volume
    changes by `delta_vol`. Proportional scaling preserves the product mix.

    If `payer` currently has zero volume across `show_products` (e.g. a
    payer that's never bought this narrowed product context) but the event
    wants to give it a positive target, there is nothing to scale
    proportionally from -- 0 * any scale is still 0. In that case, set each
    cell to an even split of the target instead of scaling. This is what
    lets a brand-new entity actually receive volume from an event, rather
    than the event's computed target being silently discarded.
    """
    ym = data.get((y, m), {})
    current = sum(ym.get(prod, {}).get(payer, 0.0) for prod in show_products)
    target = max(0.0, current + delta_vol)
    if current <= 0:
        if target <= 0 or not show_products:
            return
        even_share = target / len(show_products)
        for prod in show_products:
            ym.setdefault(prod, {})[payer] = even_share
        return
    scale = target / current
    for prod in show_products:
        if payer in ym.get(prod, {}):
            ym[prod][payer] *= scale


def _apply_product_delta(data: dict, y: int, m: int,
                         product: str, delta_vol: float, show_payers: list | None = None) -> None:
    """
    Scale (product, payer) cells for `product` so the product's total volume
    (summed over `show_payers`, or every payer under it if not given) changes
    by `delta_vol`. Proportional scaling preserves the payer mix within that set.

    Same zero-current bootstrap as _apply_payer_delta above: a product with
    no existing volume (e.g. a brand-new product added via Manage Products)
    can't be grown by scaling, since there's nothing there to multiply. If
    the target is positive, set an even split across the relevant payers
    instead of returning with no-op.
    """
    ym = data.get((y, m), {})
    prod_data = ym.setdefault(product, {})
    payers = show_payers if show_payers is not None else list(prod_data.keys())
    current = sum(prod_data.get(payer, 0.0) for payer in payers)
    target = max(0.0, current + delta_vol)
    if current <= 0:
        if target <= 0 or not payers:
            return
        even_share = target / len(payers)
        for payer in payers:
            prod_data[payer] = even_share
        return
    scale = target / current
    for payer in payers:
        if payer in prod_data:
            prod_data[payer] *= scale


# ---------------------------------------------------------------------------
# EventInput builder
# ---------------------------------------------------------------------------

def _build_event_input(event_row: dict, tab: str) -> EventInput | None:
    """
    Build a pydantic EventInput from one impact_curve_configuration row.
    Returns None if required fields are missing or invalid.

    The curve math in compute_event_forecast is independent of HCV/HIV context;
    we use EventScope.PRODUCT_EVENT as a valid non-overall scope so validation
    passes. EventInput's real field is `contexts` (plural, list) — passing the
    old singular `context=` kwarg was silently dropped by pydantic, leaving
    `contexts` at its default None, which made the model's own validator
    reject EVERY payer_event/product_event row (caught below, returning None,
    so run-calculation silently no-op'd for both tabs). `contexts` itself is
    never read by compute_event_forecast; the actual context-scoping (which
    products a payer_event row applies within, or which payers a product_event
    row applies within) is handled by the caller directly from `event_row`,
    not through this field.
    """
    try:
        start_dt = date_type.fromisoformat(str(event_row.get("start_date", ""))[:10])
    except (ValueError, TypeError):
        return None

    peak_pct = float(event_row.get("peak_percent", 0.0))
    duration = max(1, int(event_row.get("months", 12)))
    raw_factor = event_row.get("factor")

    try:
        curve_type = CurveType(event_row.get("curve_type", "Linear"))
    except ValueError:
        curve_type = CurveType.LINEAR

    # SCurve with factor=1 is mathematically indistinguishable from Linear.
    # Default to k=5 (visible sigmoid) when no meaningful factor is provided.
    if curve_type == CurveType.SCURVE and (raw_factor is None or float(raw_factor) == 1.0):
        factor = 5.0
    else:
        factor = float(raw_factor if raw_factor is not None else 1.0)

    if tab == "payer_event":
        payers_list = event_row.get("payers") or []
        selected = payers_list[0] if payers_list else None
        impacted_names = [n for n in (event_row.get("impacted_payers") or []) if n != selected]
    elif tab == "product_event":
        products_list = event_row.get("products") or []
        selected = products_list[0] if products_list else None
        impacted_names = [n for n in (event_row.get("impacted_products") or []) if n != selected]
    else:
        selected = None
        impacted_names = []

    if tab != "overall_event" and not selected:
        return None

    # Normalise weights to sum exactly to 100 so the validator passes
    source_pcts = event_row.get("source_percentages") or {}
    raw_w = [float(source_pcts.get(n, 0.0)) for n in impacted_names]
    total_w = sum(raw_w)
    if total_w > 0:
        weights = [w / total_w * 100.0 for w in raw_w]
    elif impacted_names:
        eq = 100.0 / len(impacted_names)
        weights = [eq] * len(impacted_names)
    else:
        weights = []

    if weights:
        weights[-1] = round(100.0 - sum(weights[:-1]), 4)

    impacted_entities = (
        [ImpactedEntity(name=n, weight=w) for n, w in zip(impacted_names, weights)]
        or None
    )

    coverage = None
    if (
        event_row.get("coverage_peak_percent") is not None
        and event_row.get("coverage_peak_months") is not None
    ):
        try:
            cov_ct = CurveType(event_row.get("coverage_curve_type") or event_row.get("curve_type", "Linear"))
        except ValueError:
            cov_ct = CurveType.LINEAR
        coverage = CoverageInput(
            curve_type=cov_ct,
            factor=float(event_row.get("coverage_factor", 1.0)),
            peak_pct=float(event_row["coverage_peak_percent"]),
            peak_months=int(event_row["coverage_peak_months"]),
        )

    scope = EventScope.OVERALL_EVENT if tab == "overall_event" else EventScope.PRODUCT_EVENT

    try:
        return EventInput(
            event_name=event_row.get("event_name", "Event"),
            event_scope=scope,
            scenario_name="BASE",
            ta_name="HCV",
            start_date=start_dt,
            peak_pct=peak_pct,
            duration_months=duration,
            curve_type=curve_type,
            factor=factor,
            coverage=coverage,
            impacted_entities=impacted_entities,
            contexts=["context"] if scope != EventScope.OVERALL_EVENT else None,
            selected_entity=selected,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Event application
# ---------------------------------------------------------------------------

def _apply_events_to_data(
    data: dict,
    month_tuples: list,
    forecast_start_index: int,
    total_all: list,
    event_rows: list,
    tab: str,
    show_products: list,
    show_payers: list,
) -> list:
    """
    Apply each event row's curve to `data` (forecast months only), the same
    way the HIV team's engine is driven: baseline_pct is passed straight into
    compute_event_forecast() so the selected entity's curve is an ABSOLUTE
    share target (baseline -> peak_percent, held flat after), and the
    selected entity is PINNED to that target each month (mode="set") rather
    than having a fixed delta added onto whatever happens to already be in
    `data` for that month. Impacted/sibling entities still move by the
    curve's redistribution delta (mode="add"), same as HIV.

    Pinning (recomputing target_vol - current_vol fresh every month) instead
    of adding a delta computed once against the last-history baseline means
    the result lands exactly on peak_percent regardless of any drift between
    the pre-filled forecast and the true history baseline.

    For overall_event, peak_percent remains a multiplicative growth delta
    (baseline_pct stays 0.0), unchanged from before.

    Modifies `data` in-place. Returns the updated `total_all` list.
    """
    month_iso = [f"{y:04d}-{m:02d}-01" for y, m in month_tuples]

    for event_row in event_rows:
        # Context scoping: a payer_event row's "products" field (and a
        # product_event row's "payers" field) is a genuine sub-selection —
        # which product(s)/payer(s) this event's share change applies within —
        # sent by the frontend on every row (sanitizeRunCalculationRow always
        # populates both `products` and `payers`). Default to the full universe
        # when the row didn't narrow it down, so behavior is unchanged for
        # rows that don't use this.
        ctx_products = show_products
        ctx_payers = show_payers
        if tab == "payer_event":
            row_products = event_row.get("products") or []
            if row_products:
                ctx_products = [p for p in show_products if p in row_products] or show_products
        elif tab == "product_event":
            row_payers = event_row.get("payers") or []
            if row_payers:
                ctx_payers = [p for p in show_payers if p in row_payers] or show_payers

        # Anchor month: the month just before THIS row's own start_date, not
        # always the last history month -- when a later-starting row is
        # stacked on the same entity/market after an earlier row already ran
        # (e.g. row 1 ramps to peak by Jun-2026, row 2 starts Aug-2026), data
        # at that prior month already reflects row 1's effect, so row 2's
        # curve continues from wherever row 1 left things instead of jumping
        # back to the original historical baseline. Rows starting at/before
        # the forecast begins are unaffected -- they still anchor to the last
        # history month, same as always.
        baseline_idx = forecast_start_index - 1
        event_start_iso = str(event_row.get("start_date", ""))[:10]
        if event_start_iso:
            start_idx = next(
                (i for i, ms in enumerate(month_iso) if ms >= event_start_iso), None
            )
            if start_idx is not None and start_idx - 1 > baseline_idx:
                baseline_idx = start_idx - 1

        baseline_share = 0.0
        baseline_total = 0.0
        if tab != "overall_event":
            if baseline_idx >= 0:
                last_y, last_m = month_tuples[baseline_idx]
                if tab == "payer_event":
                    last_ctx_total = _context_total(data, last_y, last_m, ctx_products, show_payers)
                else:
                    last_ctx_total = _context_total(data, last_y, last_m, show_products, ctx_payers)
                if last_ctx_total > 0:
                    if tab == "payer_event":
                        entity = (event_row.get("payers") or [None])[0]
                        if entity:
                            entity_vol = sum(
                                data.get((last_y, last_m), {}).get(prod, {}).get(entity, 0.0)
                                for prod in ctx_products
                            )
                            baseline_share = entity_vol / last_ctx_total * 100.0
                    elif tab == "product_event":
                        entity = (event_row.get("products") or [None])[0]
                        if entity:
                            entity_vol = sum(
                                data.get((last_y, last_m), {}).get(entity, {}).get(py, 0.0)
                                for py in ctx_payers
                            )
                            baseline_share = entity_vol / last_ctx_total * 100.0
        else:
            # overall_event's "baseline" is the anchor month's TOTAL market
            # volume (not a share) -- the fixed reference point peak_percent
            # growth is computed against, e.g. "peak=40%" means "40% above
            # whatever the market was at the anchor month," regardless of how
            # many times this calculation gets re-run afterward.
            if baseline_idx >= 0:
                baseline_total = total_all[baseline_idx]

        event_input = _build_event_input(event_row, tab)
        if event_input is None:
            continue

        result = compute_event_forecast(event_input, baseline_pct=baseline_share)

        # Selected entity: ABSOLUTE target share per month (baseline -> peak_percent
        # for payer/product events; a pure growth delta for overall_event, since
        # baseline_share is 0.0 there).
        selected_curve = dict(zip(result.months, result.selected_curve))
        # Impacted/sibling entities: SHARE deltas to add (unchanged semantics).
        impacted_deltas = {
            entity: dict(zip(result.months, deltas))
            for entity, deltas in (result.impacted_curves or {}).items()
        }

        event_start_month = result.months[0] if result.months else None
        event_end_month = result.months[-1] if result.months else None
        sustained_selected = result.selected_curve[-1] if result.selected_curve else baseline_share
        sustained_impacted = {
            entity: (deltas[-1] if deltas else 0.0)
            for entity, deltas in (result.impacted_curves or {}).items()
        }

        event_touched_forecast = False

        for i in range(forecast_start_index, len(month_tuples)):
            y, m = month_tuples[i]
            month_str = month_iso[i]
            total_vol = total_all[i]
            if total_vol <= 0:
                continue

            before_window = event_start_month is not None and month_str < event_start_month
            after_window = event_end_month is not None and month_str > event_end_month

            if tab == "overall_event":
                # Pin the market's total volume to an ABSOLUTE target each
                # month (baseline_total * (1 + peak%/100)), the same
                # "pinning" principle payer_event/product_event use for their
                # selected entity -- NOT a multiplicative scale applied to
                # whatever total_vol currently is. The old scale-in-place
                # approach compounded on every re-run (each run grew the
                # ALREADY-grown total by another peak% on top), and never
                # truly held flat after the ramp, since a constant multiplier
                # on a naturally-varying baseline still varies. Pinning to a
                # FIXED baseline_total makes re-running idempotent and makes
                # the post-ramp "sustained" months land on a genuinely
                # constant absolute value.
                if before_window:
                    continue
                delta_share = sustained_selected if after_window else selected_curve.get(month_str, sustained_selected)
                target_total = max(0.0, baseline_total * (1.0 + delta_share / 100.0))
                event_touched_forecast = True
                if target_total <= 0:
                    continue
                ym = data.get((y, m), {})
                current_total = sum(v for pd in ym.values() for v in pd.values() if v > 0)
                if current_total <= 0:
                    continue
                scale = target_total / current_total
                for prod in ym:
                    for payer in ym[prod]:
                        ym[prod][payer] = max(0.0, ym[prod][payer] * scale)
                continue

            # payer_event / product_event: pin the selected entity to the curve's
            # absolute target share this month; before the event's own window,
            # leave it untouched (None sentinel = no-op).
            if before_window:
                target_share = None
                eff_impacted = {}
            elif after_window:
                target_share = sustained_selected
                eff_impacted = sustained_impacted
            else:
                target_share = selected_curve.get(month_str, sustained_selected)
                eff_impacted = {
                    entity: imp_map.get(month_str, 0.0)
                    for entity, imp_map in impacted_deltas.items()
                }

            if tab == "payer_event":
                sel_payer = event_input.selected_entity
                # Both the selected payer's target AND the impacted payers'
                # compensating loss are sized against the SAME context total
                # (ASGA's own volume, not the grand total) and applied WITHIN
                # the same ctx_products only -- e.g. peak=50% means "Cash
                # reaches 50% of ASGA," funded entirely by Commercial/Medicaid/
                # Medicare's OWN ASGA volume, never touching their volume in
                # any other product.
                ctx_total_vol = _context_total(data, y, m, ctx_products, show_payers)
                # Renormalization (the "no drift" safety net) must never touch a
                # payer the row didn't actually configure -- e.g. if only
                # Commercial is marked impacted, Medicaid/Medicare must keep
                # their own natural trend untouched. Scope it to exactly the
                # selected payer + the row's own impacted payers; only fall
                # back to the full show_payers set when NO impacted payers were
                # configured at all (nothing else to spread the compensating
                # loss across).
                touched_payers = [sel_payer] + [p for p in eff_impacted if p != sel_payer]
                renorm_payers = touched_payers if eff_impacted else show_payers
                renorm_orig_total = (
                    _context_total(data, y, m, ctx_products, renorm_payers)
                    if eff_impacted else ctx_total_vol
                )
                ctx_changed = False
                delta_vol = 0.0
                if target_share is not None:
                    current_vol = sum(
                        data.get((y, m), {}).get(prod, {}).get(sel_payer, 0.0)
                        for prod in ctx_products
                    )
                    target_vol = max(0.0, target_share / 100.0 * ctx_total_vol)
                    delta_vol = target_vol - current_vol
                    if abs(delta_vol) > 1e-9:
                        _apply_payer_delta(data, y, m, sel_payer, ctx_products, delta_vol)
                        ctx_changed = True
                    event_touched_forecast = True
                # Impacted payers' loss is sized proportional to Cash's ACTUAL
                # delta_vol this month (via eff_impacted's own weight ratios),
                # NOT the curve's theoretical percentage-point delta from
                # baseline_pct * ctx_total_vol. The theoretical curve value
                # assumes the selected payer's real trajectory exactly matches
                # baseline_pct -> peak_pct, but the selected payer is pinned
                # against its own ACTUAL (organically trending) volume every
                # month, so the two can diverge -- especially deep into the
                # sustained (post-ramp, held-at-peak) phase, where the curve
                # keeps demanding the same theoretical cut every month even
                # after the selected payer has stopped needing it. Since
                # renormalization includes the selected payer itself, that
                # mismatch was bleeding into Cash's own share, pushing it past
                # its peak_percent target instead of holding it there. Sizing
                # off delta_vol directly keeps the redistribution exactly
                # zero-sum by construction, regardless of any such drift.
                sum_d = sum(eff_impacted.values())
                if eff_impacted and delta_vol != 0.0 and sum_d != 0.0:
                    for imp, d in eff_impacted.items():
                        if d != 0.0:
                            _apply_payer_delta(data, y, m, imp, ctx_products,
                                               -delta_vol * (d / sum_d))
                            ctx_changed = True
                            event_touched_forecast = True
                if ctx_changed and renorm_orig_total > 0:
                    _renormalize_context(data, y, m, ctx_products, renorm_payers, renorm_orig_total)

            elif tab == "product_event":
                sel_prod = event_input.selected_entity
                # Same reasoning as the payer_event branch above, mirrored:
                # impacted products lose share from their OWN volume within
                # ctx_payers only, not their volume with any other payer.
                ctx_total_vol = _context_total(data, y, m, show_products, ctx_payers)
                # Mirrors the payer_event scoping above: never renormalize a
                # product the row didn't configure (e.g. only GILD marked
                # impacted, some third product must keep its own trend).
                touched_products = [sel_prod] + [p for p in eff_impacted if p != sel_prod]
                renorm_products = touched_products if eff_impacted else show_products
                renorm_orig_total = (
                    _context_total(data, y, m, renorm_products, ctx_payers)
                    if eff_impacted else ctx_total_vol
                )
                ctx_changed = False
                delta_vol = 0.0
                if target_share is not None:
                    current_vol = sum(
                        data.get((y, m), {}).get(sel_prod, {}).get(py, 0.0) for py in ctx_payers
                    )
                    target_vol = max(0.0, target_share / 100.0 * ctx_total_vol)
                    delta_vol = target_vol - current_vol
                    if abs(delta_vol) > 1e-9:
                        _apply_product_delta(data, y, m, sel_prod, delta_vol, show_payers=ctx_payers)
                        ctx_changed = True
                    event_touched_forecast = True
                # See the identical reasoning in the payer_event branch above:
                # size impacted products' loss off the selected product's
                # ACTUAL delta_vol this month, not the curve's theoretical
                # percentage-point delta, so the redistribution is always
                # exactly zero-sum regardless of organic drift.
                sum_d = sum(eff_impacted.values())
                if eff_impacted and delta_vol != 0.0 and sum_d != 0.0:
                    for imp, d in eff_impacted.items():
                        if d != 0.0:
                            _apply_product_delta(data, y, m, imp, -delta_vol * (d / sum_d),
                                                 show_payers=ctx_payers)
                            ctx_changed = True
                            event_touched_forecast = True
                if ctx_changed and renorm_orig_total > 0:
                    _renormalize_context(data, y, m, renorm_products, ctx_payers, renorm_orig_total)

        if not event_touched_forecast:
            event_name = event_row.get("event_name", "Event")
            start_date = event_row.get("start_date", "")
            raise ValueError(
                f"Event '{event_name}' (start_date={start_date}) does not overlap "
                f"the forecast window — every affected month falls in history and "
                f"cannot be modified. Set start_date on or after the forecast start date."
            )

        if tab == "overall_event":
            # Total market volume changes — recompute for next stacked event
            total_all = _recompute_total_all(data, month_tuples)
        # payer_event / product_event: each month's context was already
        # renormalized back to its own pre-delta total inline above (see
        # _renormalize_context calls), which keeps the grand total_all
        # invariant intact as a consequence — untouched products/payers are
        # never part of that context, so they're never rescaled.

    return total_all


# ---------------------------------------------------------------------------
# Touched-entity chart scoping
# ---------------------------------------------------------------------------

def _compute_touched_entities(event_rows: list, tab: str):
    """
    Mirror HIV's _touched_entities_for_tab (Market_Events_Run_Calculation.py):
    after running an event, the active tab's HIERARCHY chart (product_payer_level
    / payer_product_level -- the only views run-calculation actually scopes; the
    flat payer_level/product_level rollups are never calculation targets, see
    _build_product_event_metrics) should show only the (product, payer) combos
    the event actually touched -- the selected entity plus any impacted/
    redistribution entities, crossed with the row's own context selection --
    NOT the raw selected_filter products/payers.

    Returns touched_pairs:
      payer_event:   keyed (product, payer).
      product_event: keyed (payer, product).
      overall_event / unrecognized tab: None -- no hierarchy chart to restrict.
    """
    if tab == "payer_event":
        pairs = set()
        for row in event_rows:
            payers_list = row.get("payers") or []
            if not payers_list:
                continue
            touched_payers = {payers_list[0]} | set(row.get("impacted_payers") or [])
            for product in (row.get("products") or []):
                for payer in touched_payers:
                    pairs.add((product, payer))
        return pairs
    if tab == "product_event":
        pairs = set()
        for row in event_rows:
            products_list = row.get("products") or []
            if not products_list:
                continue
            touched_prod = {products_list[0]} | set(row.get("impacted_products") or [])
            for payer in (row.get("payers") or []):
                for product in touched_prod:
                    pairs.add((payer, product))
        return pairs
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_market_events_calculation(payload) -> dict:
    """
    POST /api/liver-market-events/run-calculation

    1. Fetches BASE transaction data for the selected filter.
    2. Applies event curves (from impact_curve_configuration.rows) to the
       active tab's data only.
    3. Rebuilds metrics_views for all three tabs (active tab uses post-event
       data; the other two tabs reflect BASE data unchanged).
    4. Returns the same shape as /apply-filters so the frontend can re-render
       consistently.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        ta = payload.ta_name
        sf = payload.selected_filter
        tab = payload.selected_tab

        if sf.scenario_name.strip().upper() == "BASE":
            raise ValueError(
                "Run Calculation cannot be run on the Base scenario. "
                "Please select or create a scenario first."
            )

        payers = get_payers(cur)
        products = get_products(cur)
        scenarios = _get_scenarios_with_base(cur)

        if sf.scenario_name not in scenarios:
            raise ValueError(
                f"Scenario '{sf.scenario_name}' does not exist. "
                "Scenarios can only be created in the model input module."
            )

        # Full config set for the TA, not narrowed to the currently-selected
        # payers/products -- see the identical fix in market_events_service.py's
        # apply_market_events_filters/refresh_market_events.
        configs = get_all_configs_for_ta(cur, ta)
        min_start, forecast_start_date, max_end = _get_date_range_from_configs(configs)
        if min_start:
            min_start = _clamp_min_start_to_transaction_floor(cur, ta, min_start)

        if min_start and max_end:
            from_year, from_month = parse_year_month(min_start)
            to_year, to_month = parse_year_month(max_end)
            available_months = generate_month_range(from_year, from_month, to_year, to_month)
        else:
            available_months, forecast_start_date = _available_months_fallback(cur, ta)
            from_year, from_month = parse_year_month(available_months[0])
            to_year, to_month = parse_year_month(available_months[-1])

        fcast_year, fcast_month = parse_year_month(forecast_start_date)

        # The calculation itself (Base data + event application below) always
        # runs across the FULL available_months range, matching what gets
        # persisted (see _persist_market_events_result below, and the
        # identical "always save the wide range" rule save_market_events
        # already follows) -- NOT the user's currently-selected sf.start_date/
        # end_date. A narrower, display-only slice of this same computed data
        # is carved out further below, right before building the HTTP
        # response, so Run Calculation's response still matches what
        # apply-filters shows for the user's selected window without ever
        # persisting anything less than the full computed range.
        month_iso_list = generate_month_range(from_year, from_month, to_year, to_month)
        month_tuples = [(int(s[:4]), int(s[5:7])) for s in month_iso_list]
        chart_headers = month_iso_list

        fcast_iso = to_month_label(fcast_year, fcast_month)
        forecast_start_index = (
            month_iso_list.index(fcast_iso)
            if fcast_iso in month_iso_list
            else len(month_tuples)
        )

        # ── Base data ──────────────────────────────────────────────────────
        # Prefer this scenario's OWN persisted, properly-forecasted volumes --
        # the exact same source apply_market_events_filters/refresh_market_events
        # would show for it -- over rebuilding from raw transaction_data.
        # Rebuilding from scratch here used flat_forecast (a single flat value
        # repeated across every forecast month) for anything the event
        # doesn't touch, which visibly diverged from the trending forecast
        # every other screen shows for the same scenario. Reindexed onto our
        # OWN month_tuples (the full available range, computed above) rather
        # than trusting the snapshot's own month list, since configs/data may
        # have widened since this scenario was last saved; any month our
        # range covers that the snapshot doesn't is left for the existing
        # zero-seed / flat-forecast fallback below to fill, same as it
        # already does for a scenario with no persisted data at all.
        scenario_series = _load_scenario_raw_series(cur, sf.scenario_name)
        if scenario_series:
            snap_data, _snap_months, snap_month_tuples, _snap_fsi, snap_total_all, _sp, _spy = scenario_series
            snap_total_by_month = dict(zip(snap_month_tuples, snap_total_all))
            base_data = {mt: snap_data.get(mt, {}) for mt in month_tuples}
            base_total_raw = [snap_total_by_month.get(mt, 0.0) for mt in month_tuples]
        else:
            raw_rows = get_volume_by_product_payer(
                cur, ta, from_year, from_month, to_year, to_month,
                payers=None, products=None,
            )
            base_data = organize_raw_data(raw_rows)
            base_total_raw = None  # computed below, after the zero-history seeding

        # Seed every (product, payer) combo from the full active master-data
        # universe (products/payers fetched above), not just the ones with
        # real transaction_data rows -- using setdefault so any real,
        # existing value is left completely untouched. Without this, a
        # brand-new product (e.g. added via Manage Products, zero rows in
        # transaction_data) would be entirely absent from base_data: it'd be
        # selectable in every dropdown (those are product_master-driven,
        # independent of this) but produce no row in any table/chart, and
        # _apply_payer_delta/_apply_product_delta would have no cell to
        # write into at all.
        for (y, m) in month_tuples:
            cell = base_data.setdefault((y, m), {})
            for prod in products:
                prod_cell = cell.setdefault(prod, {})
                for payer in payers:
                    prod_cell.setdefault(payer, 0.0)

        show_products = sorted({p for ym in base_data.values() for p in ym})
        show_payers = sorted({
            py
            for ym in base_data.values()
            for pd in ym.values()
            for py in pd
        })

        if base_total_raw is None:
            # Fallback path only -- the scenario-snapshot path above already
            # set this from the snapshot's own stored total, which stays
            # authoritative even after the zero-history seeding (newly-seeded
            # cells are all 0.0, so they can't change the sum).
            base_total_raw = [get_volume(base_data, y, m) for y, m in month_tuples]
        base_hist = base_total_raw[:forecast_start_index]
        base_fcast_flat = flat_forecast(base_hist)
        base_total_all = base_hist + [
            v if v > 0 else base_fcast_flat
            for v in base_total_raw[forecast_start_index:]
        ]

        # ── Apply events to a deep copy of base data (active tab only) ─────
        event_rows = [
            {**row.model_dump(), "event_id": row.event_id or idx + 1}
            for idx, row in enumerate(payload.impact_curve_configuration.rows)
        ]

        if event_rows:
            mod_data = copy.deepcopy(base_data)
            _fill_forecast_data(mod_data, month_tuples, forecast_start_index)
            # Start from recomputed totals (pre-fill may raise per-series totals above base)
            mod_total = _recompute_total_all(mod_data, month_tuples)
            # Keep history months aligned with base
            mod_total[:forecast_start_index] = list(base_total_all[:forecast_start_index])
            mod_total = _apply_events_to_data(
                mod_data, month_tuples, forecast_start_index,
                mod_total, event_rows, tab,
                show_products, show_payers,
            )
        else:
            mod_data = base_data
            mod_total = base_total_all

        # ── Build metrics_views for every tab ─────────────────────────────
        # All tabs use mod_data/mod_total so switching tabs shows the same
        # post-event state (e.g. overall_event volume increase is visible
        # in payer and product tabs without re-running). Takes the month
        # grid as parameters (rather than closing over fixed outer values) so
        # it can be built once for the full computed range (persistence) and
        # again for a narrower, display-only slice (the HTTP response) below.
        def _metrics(t: str, mt: list, ch: list, fsi: int, tot: list) -> dict:
            # Only the tab actually being edited this run gets its hierarchy
            # chart scoped to what the event rows touched; the other two tabs
            # keep the plain selected_filter-based scoping (no rows exist for
            # them this run anyway).
            touched_pairs = (
                _compute_touched_entities(event_rows, t) if (t == tab and event_rows) else None
            )
            if t == "payer_event":
                return _build_payer_event_metrics(
                    mod_data, mt, ch, fsi,
                    tot, show_products, show_payers,
                    filter_products=sf.products, filter_payers=sf.payers,
                    touched_pairs=touched_pairs,
                )
            if t == "product_event":
                return _build_product_event_metrics(
                    mod_data, mt, ch, fsi,
                    tot, show_products, show_payers,
                    filter_products=sf.products, filter_payers=sf.payers,
                    touched_pairs=touched_pairs,
                )
            return _build_overall_event_metrics(
                mt, ch, fsi, tot,
            )

        saved_tabs = {
            t: {"metrics_views": _metrics(t, month_tuples, chart_headers, forecast_start_index, mod_total)}
            for t in ("payer_event", "product_event", "overall_event")
        }

        # A narrower, display-only slice of the SAME computed data, scoped to
        # the user's OWN selected filter window (sf.start_date/end_date) --
        # mirrors _clip_snapshot_to_range's clamp-not-extend clipping of a
        # saved snapshot for display. saved_tabs above (the full computed
        # range) is what gets persisted a few lines down; this narrower
        # disp_saved_tabs is ONLY for the HTTP response, so Run Calculation's
        # response stays consistent with what apply-filters shows for this
        # same scenario+filter, without ever truncating what's actually saved.
        calc_start = max(sf.start_date, available_months[0])
        calc_end = min(sf.end_date, available_months[-1])
        if calc_start > calc_end:
            calc_start, calc_end = available_months[0], available_months[-1]
        disp_lo = next((i for i, mth in enumerate(chart_headers) if mth >= calc_start), len(chart_headers))
        disp_hi = next((i for i, mth in enumerate(chart_headers) if mth > calc_end), len(chart_headers))
        disp_month_tuples = month_tuples[disp_lo:disp_hi]
        disp_chart_headers = chart_headers[disp_lo:disp_hi]
        disp_forecast_start_index = max(0, min(len(disp_month_tuples), forecast_start_index - disp_lo))
        disp_mod_total = mod_total[disp_lo:disp_hi]

        disp_saved_tabs = {
            t: {"metrics_views": _metrics(t, disp_month_tuples, disp_chart_headers,
                                           disp_forecast_start_index, disp_mod_total)}
            for t in ("payer_event", "product_event", "overall_event")
        }

        # Persist this run's event rows for the active tab (whole-array
        # replace -- the frontend always resends the complete current list,
        # never a single row to add/delete, see save_impact_rows), so they
        # survive a tab switch, a page reload, or the next apply-filters/
        # refresh call instead of vanishing the moment this response is sent.
        # Persisted even when empty (0 rows): that correctly captures "the
        # user deleted their last event and reran," not "leave whatever was
        # there before."
        save_impact_rows(cur, ta, sf.scenario_name, tab, event_rows)
        conn.commit()

        # The other two tabs weren't touched by this run -- load their own
        # independently-persisted rows instead of blanking them to [].
        payer_rows   = event_rows if tab == "payer_event"   else load_impact_rows(cur, ta, sf.scenario_name, "payer_event")
        product_rows = event_rows if tab == "product_event" else load_impact_rows(cur, ta, sf.scenario_name, "product_event")
        overall_rows = event_rows if tab == "overall_event" else load_impact_rows(cur, ta, sf.scenario_name, "overall_event")

        # ── Assemble impact_curve_configuration per tab ────────────────────
        payer_event_cfg = {
            "products":            products,
            "payers":              payers,
            "impact_payers":       payers,
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                payer_rows,
        }
        product_event_cfg = {
            "products":            products,
            "payers":              payers,
            "impact_products":     products,
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                product_rows,
        }
        overall_event_cfg = {
            "products":            products,
            "payers":              payers,
            "impact_payers":       ["Overall"],
            "forecast_start_date": forecast_start_date,
            "curve_types":         CURVE_TYPES,
            "rows":                overall_rows,
        }

        event_tabs_wide = _merge_config_with_saved_data(
            payer_event_cfg, product_event_cfg, overall_event_cfg, saved_tabs
        )
        event_tabs = _merge_config_with_saved_data(
            payer_event_cfg, product_event_cfg, overall_event_cfg, disp_saved_tabs
        )

        # Auto-save the computed result directly into this (non-Base, already
        # confirmed to exist above) scenario -- same persistence Save Scenario
        # already does manually (see _persist_market_events_result), so
        # running a calculation no longer requires a separate explicit save
        # step to make its result durable. Always persists the FULL computed
        # range (event_tabs_wide), never the display-filtered event_tabs
        # returned below -- matching save_market_events' identical "always
        # save the wide range" rule, so a narrower FROM/TO filter active at
        # calculation time can never truncate history out of the saved
        # scenario.
        _persist_market_events_result(cur, conn, sf.scenario_name, event_tabs_wide)

        return {
            "ta_name":             ta,
            "available_scenarios": scenarios,
            "available_months":    available_months,
            "selected_filter":     sf.model_dump(),
            "selected_tab":        tab,
            "metric_filters":      METRIC_FILTERS,
            "event_tabs":          event_tabs,
        }
    finally:
        cur.close()
        conn.close()
