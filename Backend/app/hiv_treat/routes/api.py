from datetime import date , datetime
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException , Depends , Body
from uuid import uuid4
import json
from app.db.connection import get_connection
from typing import Dict, Any
from app.hiv_treat.routes.schema import *
from app.hiv_treat.routes.models import *
from app.hiv_treat.utils.config import add_months
from app.hiv_treat.services.HIV_helper_functions import (
    get_total_market_volume,
    get_market_distribution,
    get_product_distribution,
    get_market_wise_product,
    parse_month
)
from app.hiv_treat.services.Model_Input_Service import build_apply_scenario_response,get_scenarios
from app.hiv_treat.services.Model_Input_Save_Scenario import _save_market_analysis,build_save_scenario_response
from app.hiv_treat.services.Market_Events_Run_Calculation import run_calculation
# -----------------------------------
# FORECAST MODELS
# -----------------------------------
from app.services.forecast_service import process_forecast

from app.hiv_treat.services.HIV_helper_functions import (
    process_growth_forecast_auto,
    normalize_shares,
    process_moving_average_forecast
)
from app.services.growth_forecast_service import process_growth_forecast
from app.hiv_treat.services import Model_Input_Service as MIS
from app.hiv_treat.services.HIV_Treat_Retaining_Filters import get_user_configuration, save_user_configuration
from app.hiv_treat.services.scenario_service import get_available_scenarios
from app.hiv_treat.routes.schema import  SaveScenarioRequest
import json as Json
from app.hiv_treat.services.Model_Input_Service import (
    build_apply_scenario_response,
    build_factors,
)

# from app.hiv_treat.services.helpers import (
#     load_market_analysis_from_db
# )

from app.hiv_treat.services.scenario_service import get_available_scenarios

router = APIRouter(prefix="/api/hiv_treat", tags=["hiv_treat"])

@router.get(
    "/configurations/{ta_name}",
    response_model=ConfigurationResponse,
    tags=["Configuration"]
)
def get_configuration_by_ta(ta_name: str) -> Dict[str, Any]:
    """
    Fetch configuration and available training months for a given TA.
    """

    try:
        with get_connection() as conn, conn.cursor() as cur:
            #fetch available months          
            cur.execute("""
                SELECT DISTINCT year, month
                FROM raw_hiv_treat.volume
                WHERE REPLACE(LOWER(TRIM(ta)), '_', ' ') =
                    REPLACE(LOWER(TRIM(%s)), '_', ' ')
                ORDER BY year, month
            """, (ta_name,))


            available_train_months = [
                date(int(year), int(month), 1).isoformat()
                for year, month in cur.fetchall()
            ]

            #config list
            cur.execute("""
                SELECT config
                FROM raw_hiv_treat.forecast_configurations
                WHERE config->>'ta_name' = %s
                LIMIT 1
            """, (ta_name,))

            row = cur.fetchone()

            if not row:
                return {
                    "ta_name": ta_name,
                    "exists": False,
                    "config": None,
                    "available_train_months": available_train_months
                }

            config = row[0] or {}

            try:
                train_end_date = date.fromisoformat(config["train_end_date"])
                forecast_periods = int(config["forecast_periods"])
            except (KeyError, ValueError, TypeError):
                raise HTTPException(
                    status_code=500,
                    detail="Invalid configuration data format"
                )

            #forecast dates
            forecast_end_date = add_months(train_end_date, forecast_periods)

            # Avoid mutating original config unintentionally
            
            enriched_config = {
                **config,
                "forecast_periods": forecast_end_date.isoformat()  # convert to string date
            }


            return {
                "ta_name": ta_name,
                "exists": True,
                "config": enriched_config,
                "available_train_months": available_train_months
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch configuration: {str(e)}"
        )
    
@router.post("/save-configurations", tags=["Configuration"])
def save_configuration(payload: SaveConfigRequest):

    cfg = payload.config
    
    # =========================================
    #     Normalize TA FIRST (FIXED)
    # =========================================
    ta = cfg.ta_name.replace("_", " ").strip()

    # =========================================
    #     VALIDATION BLOCK (FIXED ORDER)
    # =========================================
    try:
        start_date = date.fromisoformat(cfg.train_start_date)
        end_date = date.fromisoformat(cfg.train_end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format")

    if start_date > end_date:
        raise HTTPException(400, "train_start_date cannot be after train_end_date")

    if cfg.model_granularity.lower() != "monthly":
        raise HTTPException(400, "Only 'monthly' granularity is supported")

    try:
        forecast_end_date = date.fromisoformat(cfg.forecast_periods)
    except ValueError:
        raise HTTPException(400, "Invalid forecast_periods date format")

    forecast_periods = (
        (forecast_end_date.year - end_date.year) * 12 +
        (forecast_end_date.month - end_date.month)
    )

    if forecast_periods <= 0:
        raise HTTPException(400, "Forecast end date must be after Train End Date")

    #     Prepare config JSON
    config_to_save = cfg.model_dump()
    config_to_save["forecast_periods"] = forecast_periods

    # =========================================
    #     DB DATE RANGE VALIDATION (FIXED)
    # =========================================
    try:
        with get_connection() as conn, conn.cursor() as cur:

            cur.execute("""
                SELECT 
                    MIN(make_date(year, month, 1)),
                    MAX(make_date(year, month, 1))
                FROM raw_hiv_treat.volume
                WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
            """, (ta,))

            row = cur.fetchone()

            if not row or not row[0] or not row[1]:
                raise HTTPException(400, f"No data available for TA '{ta}'")

            min_date, max_date = row

    except Exception as e:
        raise HTTPException(500, f"DB error: {str(e)}")

    #     Final date checks
    if start_date < min_date or start_date > max_date:
        raise HTTPException(
            400,
            f"Invalid Train Start Date. Available: {min_date} → {max_date}"
        )

    if end_date < min_date or end_date > max_date:
        raise HTTPException(
            400,
            f"Invalid Train End Date. Available: {min_date} → {max_date}"
        )


    try:
        with get_connection() as conn, conn.cursor() as cur:

            # -----------------------------------
            #    DELETE SCENARIO
            # -----------------------------------
            cur.execute("""
                DELETE FROM raw_hiv_treat.forecast_outputs
                WHERE user_id=%s AND scenario_name=%s AND ta_name=%s
            """, ("default_user", "Base", ta))

            # =====================================================
            #    STEP 1 — TOTAL VOLUME
            # =====================================================
            rows = get_total_market_volume(
                cur, ta,
                start_date.year, start_date.month,
                end_date.year, end_date.month
            )

            if not rows:
                raise HTTPException(400, f"No data found for {ta}")

            months = [f"{y}-{m:02d}-01" for y, m, _ in rows]
            values = [float(v) for _, _, v in rows]

            tv_fc = process_forecast(
            series_months=months,
            series_values=values,
            train_start_date=cfg.train_start_date,
            train_end_date=cfg.train_end_date,
            forecast_periods=forecast_periods,
            metric="market_volume"
        )
        
            fc_len = len(tv_fc["forecast_values"])

            # =====================================================
            #    STEP 2 — MARKET + SOURCE SPLIT
            # =====================================================
            rows = get_market_distribution(
                cur, ta,
                start_date.year, start_date.month,
                end_date.year, end_date.month,
                metric="market_share"
            )
            print("\n===== MARKET DISTRIBUTION ROWS =====")

            for r in rows[:15]:
                print(r)
            
            non_retail_totals = {}

            for y, m, market, source, share in rows:

                if market == "Non-retail":
                    key = (y, m)

                    if key not in non_retail_totals:
                        non_retail_totals[key] = 0.0

                    non_retail_totals[key] += float(share)


            # --- MARKET LEVEL (FIXED) ---
            market_data = {}
            market_data_map = {}

            # --- SOURCE LEVEL (UNCHANGED) ---
            source_data = {}

            for y, m, market, source, share in rows:
                
                if market == "Non-retail" and y == 2026 and m in [1, 2]:
                    print(
                        "DEBUG SOURCE SHARE:",
                        y,
                        m,
                        market,
                        source,share)
         


                month = f"{y}-{m:02d}-01"

                #   FIX: aggregate shares per (market, month)
                key = (market, month)

                if key not in market_data_map:
                    market_data_map[key] = 0.0

                market_data_map[key] += float(share)

                #   keep source logic SAME
                if market == "Non-retail":
                    src = source or "Unknown"

                    if src not in source_data:
                        source_data[src] = {"months": [], "values": []}
                        print("\n===== SOURCE DATA CHECK =====")

                        for src, d in source_data.items():
                            print(src)
                            print("Last months:", d["months"][-3:])
                            print("Last values:", d["values"][-3:])

                    source_share = round(
                        (float(share) * 100) /
                        non_retail_totals[(y, m)],
                        2
                    )

                    source_data[src]["months"].append(month)
                    source_data[src]["values"].append(source_share)
                    
                    if y == 2026 and m in [1, 2]:
                        print(
                            "NORMALIZED SOURCE:",
                            src,
                            source_share
                        )



            #   Build clean market series (sorted by month)
            from collections import defaultdict

            temp_market = defaultdict(list)

            for (market, month), share in market_data_map.items():
                temp_market[market].append((month, round(share, 2)))

            for market, items in temp_market.items():
                items_sorted = sorted(items, key=lambda x: x[0])

                market_data[market] = {
                    "months": [m for m, _ in items_sorted],
                    "values": [v for _, v in items_sorted]
    }


            # -----------------------------------
            #    MARKET FORECAST
            # -----------------------------------
            market_fc = {}

            for market, d in market_data.items():
                market_fc[market] = process_moving_average_forecast(
                series_months=d["months"],
                series_values=d["values"],
                train_start_date=cfg.train_start_date,
                train_end_date=cfg.train_end_date,
                forecast_periods=forecast_periods,
                window=cfg.window,
                metric="market_share"
            )

            #    Normalize markets
            for i in range(fc_len):
                vals = [market_fc[m]["forecast_values"][i] for m in market_fc]
                norm = normalize_shares(vals)

                for idx, mkt in enumerate(market_fc):
                    market_fc[mkt]["forecast_values"][i] = round(norm[idx], 2)
            

            #    Derived market volume
            market_volume_fc = {}
            for mkt, fc in market_fc.items():
                market_volume_fc[mkt] = [
                    round(tv_fc["forecast_values"][i] * fc["forecast_values"][i] / 100, 2)
                    for i in range(fc_len)
                ]

            # -----------------------------------
            #    SOURCE FORECAST (Non-retail split)
            # -----------------------------------
            source_fc = {}

            #   SORT SOURCE DATA (fix ordering)
            for src in source_data:
                pairs = list(zip(source_data[src]["months"], source_data[src]["values"]))
                pairs_sorted = sorted(pairs, key=lambda x: x[0])

                source_data[src]["months"] = [m for m, _ in pairs_sorted]
                source_data[src]["values"] = [v for _, v in pairs_sorted]
                source_fc[src] = process_moving_average_forecast(
                series_months=source_data[src]["months"],
                series_values=source_data[src]["values"],
                train_start_date=cfg.train_start_date,
                train_end_date=cfg.train_end_date,
                forecast_periods=forecast_periods,
                window=cfg.window,
                metric="market_share"
            )

            #    Normalize sources
            #   Build base weights (from historical data)
            base_weights = {}
            for src, d in source_data.items():
                if d["values"]:
                    base_weights[src] = sum(d["values"]) / len(d["values"])
                else:
                    base_weights[src] = 1.0  # fallback


            #   Normalize sources with weights
            for i in range(fc_len):
                vals = [
                    source_fc[s]["forecast_values"][i] * base_weights.get(s, 1.0)
                    for s in source_fc
                ]

                norm = normalize_shares(vals)

                for idx, s in enumerate(source_fc):
                    source_fc[s]["forecast_values"][i] = round(norm[idx], 2)

            # =====================================================
            #    STEP 3 — PRODUCT (WITH SOURCE)
            # =====================================================
            product_rows = get_market_wise_product(
                cur, ta,
                start_date.year, start_date.month,
                end_date.year, end_date.month,
                metric="market_share"
            )

            product_data = {}

            for y, m, market, source, product, share in product_rows:

                key = (market, source, product)

                if key not in product_data:
                    product_data[key] = {"months": [], "values": []}

                product_data[key]["months"].append(f"{y}-{m:02d}-01")
                product_data[key]["values"].append(float(share))

            product_fc = {}

            for key, d in product_data.items():
                product_fc[key] = process_moving_average_forecast(
                series_months=d["months"],
                series_values=d["values"],
                train_start_date=cfg.train_start_date,
                train_end_date=cfg.train_end_date,
                forecast_periods=forecast_periods,
                window=cfg.window,
                metric="market_share"
            )

            #    Normalize per (market + source)
            groups = set((m, s) for m, s, _ in product_fc)

            for mkt, src in groups:
                keys = [k for k in product_fc if k[0] == mkt and k[1] == src]

                for i in range(fc_len):
                    vals = [product_fc[k]["forecast_values"][i] for k in keys]
                    norm = normalize_shares(vals)

                    for idx, k in enumerate(keys):
                        product_fc[k]["forecast_values"][i] = round(norm[idx], 2)

            # =====================================================
            #    STEP 4 — SAVE (CORRECT HIERARCHY)
            # =====================================================
            upsert_query = """
            INSERT INTO raw_hiv_treat.forecast_outputs
            (user_id, scenario_name, ta_name,
             market, source_of_market, product,
             metric, forecast_data)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id, scenario_name, ta_name,
                         market, source_of_market, product, metric)
            DO UPDATE SET forecast_data = EXCLUDED.forecast_data
            """

            #    TOTAL
            cur.execute(upsert_query, (
                "default_user", "Base", ta,
                "ALL", "ALL", "ALL",
                "market_volume",
                json.dumps(tv_fc)
            ))

            #    MARKET LEVEL
            for mkt, fc in market_fc.items():
                cur.execute(upsert_query, (
                    "default_user", "Base", ta,
                    mkt, None, "ALL",
                    "market_share",
                    json.dumps(fc)
                ))

            #    SOURCE LEVEL
            for src, fc in source_fc.items():
                cur.execute(upsert_query, (
                    "default_user", "Base", ta,
                    "Non-retail", src, "ALL",
                    "market_share",
                    json.dumps(fc)
                ))

            #    PRODUCT LEVEL
            for (mkt, src, prod), fc in product_fc.items():
                cur.execute(upsert_query, (
                    "default_user", "Base", ta,
                    mkt, src, prod,
                    "market_share",
                    json.dumps(fc)
                ))
             #     CONFIG SAVE (MATCHES YOUR TABLE)
            cur.execute("""
                INSERT INTO raw_hiv_treat.forecast_configurations (config_id, config)
                VALUES (%s, %s)
                ON CONFLICT ((config->>'ta_name'))
                DO UPDATE SET
                    config = EXCLUDED.config,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                str(uuid4()),
                json.dumps(config_to_save)
            ))
            conn.commit()

    except Exception as e:
        raise HTTPException(500, str(e))

    return {
        "scenario_name": "Base",
        "status": "saved",
        "forecast_periods": forecast_periods
    }




@router.get("/model-input-filters", response_model=ModelInputFilterResponse)
def get_model_input_filters(ta_name: str ):

    ta = ta_name.strip()

    try:
        with get_connection() as conn, conn.cursor() as cur:

            # MARKETS
            cur.execute("""
                SELECT DISTINCT market
                FROM raw_hiv_treat.forecast_outputs
                WHERE ta_name = %s
                AND market != 'ALL'
            """, (ta,))
            markets = sorted([r[0] for r in cur.fetchall()])

            # PRODUCTS
            cur.execute("""
                SELECT DISTINCT product
                FROM raw_hiv_treat.forecast_outputs
                WHERE ta_name = %s
                AND product != 'ALL'
            """, (ta,))
            products = sorted([r[0] for r in cur.fetchall()])

            # MONTHS (from any one stable row)
            cur.execute("""
                SELECT forecast_data
                FROM raw_hiv_treat.forecast_outputs
                WHERE ta_name = %s
                AND market = 'ALL'
                AND product = 'ALL'
                AND source_of_market = 'ALL'
                LIMIT 1
            """, (ta,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "No data found")

            forecast_data = row[0]

            months = forecast_data.get("months", [])

            # Sort just in case
            months_sorted = sorted(months)

            start_date = months_sorted[0]
            end_date = months_sorted[-1]

            # DEFAULT SELECTION
            user_id = "system"

            saved_config = get_user_configuration(
                cur,
                user_id,
                ta
            )

            default_filter = {
                "market": markets[0] if markets else None,
                "product": products[0] if products else None,
                "start_date": start_date,
                "end_date": end_date
            }

            selected_filter = (
                saved_config
                if saved_config
                else default_filter
            )

            return {
                "ta_name": ta,
                "markets": markets,
                "products": products,
                "available_months": months_sorted,
                "selected_filter": selected_filter
            }

    except Exception as e:
        raise HTTPException(500, str(e))
    

def _build_lookup_map(cur, ta):
    cur.execute("""
        SELECT market, source_of_market, product, metric, scenario_name, forecast_data
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
    """, (ta,))
    lookup = {}
    for market, source, product, metric, scenario_name, forecast_data in cur.fetchall():
        norm_src = _norm_source(source)
        key = (market, product, metric, scenario_name)
        lookup.setdefault(key, []).append((norm_src, forecast_data))
    return lookup
 
 
def _scenario_matches(row_scenario_name, requested_scenario):
    if requested_scenario.upper() == "BASE":
        return row_scenario_name is None or row_scenario_name.upper() == "BASE"
    return row_scenario_name == requested_scenario
 
 
def _resolve_from_lookup(lookup, market, source, product, metric, scenario):
    """
    source is not None -> exact match on normalized source, or None if absent.
    source is None      -> prefer the true market-level row (norm source is
                            None, i.e. 'ALL'); only if no such row exists
                            fall back to any other row for that key (e.g.
                            Retail's 'Unknown' placeholder), chosen
                            deterministically rather than by incidental
                            dict/row order.
    """
    norm_wanted = _norm_source(source)
    candidates = []
    for (m, p, met, sc_name), entries in lookup.items():
        if m != market or p != product or met != metric:
            continue
        if not _scenario_matches(sc_name, scenario):
            continue
        candidates.extend(entries)
 
    if not candidates:
        return None
 
    if norm_wanted is not None:
        for src, data in candidates:
            if src == norm_wanted:
                return data
        return None
 
    all_rows = [d for s, d in candidates if s is None]
    if all_rows:
        return all_rows[0]
 
    fallback = sorted(candidates, key=lambda sd: (sd[0] is None, sd[0] or ""))
    return fallback[0][1]
 
 
# =========================================================
# ================= ENDPOINT ================================
# =========================================================

BASELINE_SCENARIO = "Base"

# Breakdowns to post-process. Both are percentage views, so 2 decimals is
# what the stored rows already carry -- anything longer is derivation noise
# leaking into the UI (31.419958% next to Base's 31.42%, which reads as two
# different numbers when it's one).
POST_PROCESSED_BREAKDOWNS = ("market_distribution", "product_distribution")

DISPLAY_DECIMALS = 2

# A row is treated as absent rather than zero only if every value is
# exactly zero. A real product that genuinely rounds to 0.00 in one month
# still has non-zero months and is kept.
ZERO_TOLERANCE = 0.0


def _round_tree(obj, ndigits=DISPLAY_DECIMALS):
    """Round every list of numbers anywhere in a nested chart/table
    structure, whatever its shape. Non-numeric lists (months, years,
    labels) and everything else pass through untouched."""
    if isinstance(obj, dict):
        return {k: _round_tree(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        if obj and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj
        ):
            return [round(x, ndigits) for x in obj]
        return [_round_tree(x, ndigits) for x in obj]
    return obj


def _is_all_zero(values) -> bool:
    if not values:
        return False
    return all(
        isinstance(v, (int, float)) and abs(v) <= ZERO_TOLERANCE
        for v in values
    )


def _drop_empty_rows(obj, keep_labels=("Overall",)):
    """Remove table rows whose every value is zero.

    A product with no rows in this scenario is ASKED for anyway -- the
    product list is built TA-wide, not per scenario -- and the lookup
    returns nothing, which renders as 0%. That reads as a real product
    holding no share rather than as one that isn't in this scenario at all.

    Applied to the baseline only: in a working scenario a genuine zero is
    information ('this scenario didn't launch it'), and dropping it would
    make scenarios disagree on row count. Base is the reference everything
    else is compared against, so a phantom there is pure noise.
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key in ("rows", "children") and isinstance(value, list):
                kept = []
                for row in value:
                    if (
                        isinstance(row, dict)
                        and row.get("label") not in keep_labels
                        and _is_all_zero(row.get("values"))
                    ):
                        continue
                    kept.append(_drop_empty_rows(row, keep_labels))
                result[key] = kept
            else:
                result[key] = _drop_empty_rows(value, keep_labels)
        return result
    if isinstance(obj, list):
        return [_drop_empty_rows(x, keep_labels) for x in obj]
    return obj


def post_process_scenarios(response: dict) -> dict:
    """Round the percentage breakdowns to 2 decimals, and strip phantom
    all-zero rows from the baseline's product distribution.

    Done on the assembled response rather than inside the builders: the
    product list feeding these tables is TA-wide (see get_products), so
    every scenario is asked for every product that exists anywhere. Fixing
    it at the source means threading a scenario through several builders;
    this shapes the one place all of them come together."""
    scenarios = response.get("scenarios") or {}

    for scenario, block in scenarios.items():
        market_analysis = block.get("market_analysis") or {}
        is_baseline = str(scenario).strip().lower() == BASELINE_SCENARIO.lower()

        for breakdown in POST_PROCESSED_BREAKDOWNS:
            view = market_analysis.get(breakdown)
            if not view:
                continue

            view = _round_tree(view)

            if is_baseline and breakdown == "product_distribution":
                view = _drop_empty_rows(view)

            market_analysis[breakdown] = view

    # The comparison charts are built from the same series, so round them
    # to match -- otherwise the same figure appears at two precisions
    # depending on which panel you read it in.
    comparison = response.get("comparison_charts") or {}
    for breakdown in POST_PROCESSED_BREAKDOWNS:
        if breakdown in comparison:
            comparison[breakdown] = _round_tree(comparison[breakdown])

    return response
 
@router.post("/applyfilter")
def apply_filter(payload: ApplyScenarioRequest):
 
    ta = payload.ta_name
 
    try:
        with get_connection() as conn, conn.cursor() as cur:
 
            cur.execute("""
                SELECT config
                FROM raw_hiv_treat.forecast_configurations
                WHERE config->>'ta_name' = %s
            """, (ta,))
 
            row = cur.fetchone()
            config = row[0] if row else {}
 
            save_user_configuration(
                cur=cur,
                user_id="system",
                ta_name=payload.ta_name,
                market=payload.selected_filter.market,
                product=payload.selected_filter.product,
                start_date=payload.selected_filter.start_date,
                end_date=payload.selected_filter.end_date
            )
            conn.commit()
 
            # Bulk-fetch once, then serve every fetch_forecast_scenario()
            # call MIS makes internally from this in-memory, deterministic
            # lookup -- same monkeypatch pattern /recalculate already uses.
            lookup = _build_lookup_map(cur, ta)
            orig_fetch = MIS.fetch_forecast_scenario
 
            def fetch_deterministic(cur_in, ta_in, market_in, source_in, product_in, metric_in, scenario_in):
                data = _resolve_from_lookup(lookup, market_in, source_in, product_in, metric_in, scenario_in)
                if data is not None:
                    return data
                # Fall back to the real query for anything not covered
                # (e.g. edge cases outside this TA's bulk fetch).
                return orig_fetch(cur_in, ta_in, market_in, source_in, product_in, metric_in, scenario_in)
 
            MIS.fetch_forecast_scenario = fetch_deterministic
            try:
                return post_process_scenarios(
                    build_apply_scenario_response(cur, payload, config)
                )
            finally:
                MIS.fetch_forecast_scenario = orig_fetch
 
    except Exception as e:
        raise HTTPException(500, str(e))


_METRIC_ALIASES = {
    "market_share": "market_share",
    "market_volume": "volume",
}
 
 
# =========================================================
# ================= SERIES HELPERS ===========================
# =========================================================
 
def _series_from_data(data):
    months = data.get("months", [])
    tv = data.get("train_values") or []
    fv = data.get("forecast_values") or []
    return months, tv, fv
 
 
def _full_series(base_map, key, n):
    """Return a length-n (train+forecast) series for a base_map row, padded
    with the last known value if shorter than n. Returns None if missing."""
    if key not in base_map:
        return None
    _, tv, fv = _series_from_data(base_map[key])
    full = tv + fv
    if not full:
        return None
    if len(full) < n:
        full = full + [full[-1]] * (n - len(full))
    return full[:n]
 
 
# =========================================================
# ================= PARENT VOLUME (metric="market_volume") ===
# =========================================================
 
def _parent_volume_for_group(base_map, target_key, total_vals, n):
    """
    The base (unchanged) volume of the immediate parent scope that a
    target row's share is a percentage OF.
 
    - market-level row (product == 'ALL'):        parent = overall total
    - product row within Retail (source is None):  parent = total * Retail_share_base
    - product row within a Non-retail source:       parent = total * NonRetail_share_base
                                                              * source_share_within_NR_base
 
    `source` is only treated as a real hierarchy level if it has its own
    (market, source, 'ALL', metric) row (e.g. Kaiser under Non-retail).
    Flat-market placeholders (e.g. Retail's "Unknown") have no such row
    by design -- that's expected, not a data issue, so we skip that
    multiplication rather than warn about it.
 
    All inputs are pulled from base_map, never from `overrides` -- the
    parent must stay fixed regardless of what's being recalculated, or the
    tie-back-to-total guarantee breaks.
    """
    market, source, product, metric = target_key
 
    if product == "ALL":
        return list(total_vals)
 
    market_share_vals = _full_series(base_map, (market, None, "ALL", "market_share"), n)
    if market_share_vals is None:
        print(f"WARNING: missing base market_share for parent volume, market={market}")
        return list(total_vals)
 
    vol = [total_vals[i] * market_share_vals[i] / 100 for i in range(n)]
 
    if source is not None and (market, source, "ALL", "market_share") in base_map:
        source_share_vals = _full_series(base_map, (market, source, "ALL", "market_share"), n)
        if source_share_vals is not None:
            vol = [vol[i] * source_share_vals[i] / 100 for i in range(n)]
 
    return vol
 
 
# =========================================================
# ================= GROUP RESOLUTION ==========================
# =========================================================
 
def _resolve_recalc_groups(selected_tab, selected_filter, base_map):
    """Decides which target row(s) + siblings are in scope for the given
    tab and selected_filter."""
    tab = (selected_tab or "total_market_volume").lower()
    sel_market = selected_filter.market
    sel_product = selected_filter.product
    groups = []
 
    if tab == "total_market_volume":
        return groups
 
    if tab in ("market_distribution", "product_market"):
        target_key = (sel_market, None, "ALL", "market_share")
        if target_key not in base_map:
            return groups
        siblings = [
            k for k in base_map
            if k[3] == "market_share" and k[2] == "ALL"
            and k[1] is None and k[0] != sel_market
        ]
        groups.append((target_key, siblings))
        return groups
 
    if tab in ("product_distribution", "market_product"):
        matching_rows = [
            k for k in base_map
            if k[3] == "market_share" and k[0] == sel_market and k[2] == sel_product
        ]
        if not matching_rows:
            return groups
        sources_present = {k[1] for k in matching_rows}
        for src in sources_present:
            target_key = (sel_market, src, sel_product, "market_share")
            if target_key not in base_map:
                continue
            siblings = [
                k for k in base_map
                if k[3] == "market_share" and k[0] == sel_market and k[1] == src
                and k[2] not in ("ALL", sel_product)
            ]
            groups.append((target_key, siblings))
        return groups
 
    return groups
 
 
def _renormalize_siblings(target_new_fv, base_map, sibling_keys):
    """Rescales siblings so the group always sums to 100% at every
    forecast time index."""
    n = len(target_new_fv)
    target_clipped = [round(max(0.0, min(100.0, v)), 2) for v in target_new_fv]

    base_sibling_fv = {}
    for sk in sibling_keys:
        _, _, fv = _series_from_data(base_map[sk])
        fv = fv + [fv[-1] if fv else 0.0] * (n - len(fv))
        base_sibling_fv[sk] = fv[:n]

    new_sibling_fv = {sk: [0.0] * n for sk in sibling_keys}

    for i in range(n):
        remaining = 100.0 - target_clipped[i]
        base_sum = sum(base_sibling_fv[sk][i] for sk in sibling_keys)
        for sk in sibling_keys:
            if base_sum > 0:
                new_sibling_fv[sk][i] = round(remaining * (base_sibling_fv[sk][i] / base_sum), 2)
            else:
                new_sibling_fv[sk][i] = round(remaining / len(sibling_keys) if sibling_keys else 0.0, 2)

    return target_clipped, new_sibling_fv
 
 
# =========================================================
# ================= TARGET FORECAST COMPUTATION ===============
# =========================================================
 
def _compute_target_new_share(
    target_key, base_map, parent_vol, months, n,
    interp_metric, model_type, alpha, beta, gamma,
    growth, multiplier, multiplier_horizon,
    train_start, train_end, fp
):
    """
    Computes the target's NEW forecast-period share trajectory, honoring
    `interp_metric` (internal sentinel: "market_share" or "volume"):
 
    - "market_share": process_forecast runs directly on the target's own
      stored share values. Growth % applies to the share number itself.
 
    - "volume": process_forecast runs on the target's IMPLIED volume
      (base share * parent's base volume). Growth % applies to actual
      volume. Result is converted back to a share using the same
      (unchanged) parent volume.
    """
    target_data = base_map[target_key]
    _, tv, fv = _series_from_data(target_data)
    base_share_full = tv + fv
    if len(base_share_full) < n:
        base_share_full = base_share_full + [base_share_full[-1]] * (n - len(base_share_full))
    base_share_full = base_share_full[:n]
 
    if interp_metric == "volume":
        target_vol_full = [base_share_full[i] * parent_vol[i] / 100 for i in range(n)]
 
        try:
            new_fc = process_forecast(
                months, target_vol_full, train_start, train_end, fp,
                model_type=model_type, metric="market_volume",
                alpha=alpha, beta=beta, gamma=gamma,
                total_growth_pct=growth.get("total_growth", 0),
                duration=growth.get("duration", fp),
                k=growth.get("k_value"),
                trajectory_start=growth.get("trajectory_start"),
                multiplier=multiplier, multiplier_horizon=multiplier_horizon
            )
        except Exception as e:
            print(f"Forecast failed (volume-mode) target={target_key} error={e}")
            return base_share_full[-len(fv):] if fv else []
 
        new_vol_fv = new_fc.get("forecast_values") or []
        # Prefer process_forecast's own reported split point over a
        # separately recomputed one -- avoids drift if duration/
        # trajectory_start ever cause the split to differ from the
        # target row's original forecast_start_index. Falls back safely
        # if that key isn't present.
        start_idx = new_fc.get("forecast_start_index", n - len(new_vol_fv))
 
        new_share_fv = []
        for j, vol_j in enumerate(new_vol_fv):
            idx = start_idx + j
            if idx < len(parent_vol) and parent_vol[idx]:
                new_share_fv.append(round(vol_j / parent_vol[idx] * 100, 2))
            else:
                new_share_fv.append(0.0)
        return new_share_fv
 
    else:  # "market_share"
        try:
            if model_type == "moving_average":
                new_fc = process_moving_average_forecast(
                    series_months=months,
                    series_values=base_share_full,      # fixed
                    train_start_date=train_start,
                    train_end_date=train_end,
                    forecast_periods=fp,
                    window=growth.get("window", 3),
                    metric="market_volume",
                    multiplier=multiplier,
                    multiplier_horizon=multiplier_horizon
                )
            else:
                new_fc = process_forecast(
                    months, base_share_full, train_start, train_end, fp,   # fixed
                    model_type=model_type,
                    metric="market_volume",
                    alpha=alpha,
                    beta=beta,
                    gamma=gamma,
                    total_growth_pct=growth.get("total_growth", 0),
                    duration=growth.get("duration", fp),
                    k=growth.get("k_value"),
                    trajectory_start=growth.get("trajectory_start"),
                    multiplier=multiplier,
                    multiplier_horizon=multiplier_horizon
                )
        except Exception as e:
            print(f"Forecast failed (share-mode) target={target_key} error={e}")
            return base_share_full[-len(fv):] if fv else []

        return [round(v, 2) for v in (new_fc.get("forecast_values") or [])]
 
 
# =========================================================
# ================= OVERRIDE ALIASING (Retail fix) ============
# =========================================================
 
def _augment_with_source_aliases(overrides, base_map):
    """
    Model_Input_Service.py's builders hardcode `source=None` when querying
    product-level market_share rows for "flat" markets (e.g. `if mkt ==
    "Retail": fetch_forecast_scenario(cur, ta, mkt, None, prod, ...)`),
    even though the DB stores a non-null placeholder in source_of_market
    for those rows (observed: "Unknown" for Retail's product rows). The
    real SQL wildcards when the source param is None, so it finds these
    rows fine -- but our exact-key override dict does not, unless we add
    an explicit alias keyed with source=None.
 
    A source is "real" (hierarchical, e.g. Kaiser under Non-retail,
    drillable from market_distribution) if it has its own
    (market, source, 'ALL', metric) row. If not, it's a flat-market
    placeholder and gets a source=None alias so MIS's None-based lookup
    hits our (possibly recalculated) value instead of silently falling
    back to the unmodified DB row.
    """
    augmented = dict(overrides)
    for key in base_map.keys():
        market, source, product, metric = key
        if source is None or metric != "market_share":
            continue
        if (market, source, "ALL", metric) in base_map:
            continue  # real hierarchical source (e.g. Kaiser) -- no alias needed
        alias_key = (market, None, product, metric)
        if key in overrides:
            augmented[alias_key] = overrides[key]
    return augmented
 
 
# =========================================================
# ================= ENDPOINT ==================================
# =========================================================
def _norm_source(s):
    """Canonical sentinel for 'no source level' is None.
    Some scenarios store this as NULL, others as the literal string 'ALL'
    (or ''). Collapse all of them to None here, once, so every downstream
    lookup (base_map, overrides, sibling resolution, alias logic) only
    ever has to deal with one convention."""
    if s is None:
        return None
    if str(s).strip().upper() in ("", "ALL"):
        return None
    return s
@router.post("/recalculate")
def recalculate(payload: RecalculateRequest):
    """
    Recalculate preview endpoint (does NOT persist).
 
    - selected_tab == "total_market_volume" (or omitted): recalculates the
      TOTAL market_volume row directly using model_type/factors. `metric`
      is irrelevant here -- always volume.
 
    - Any other selected_tab: recalculates market_share row(s) inferred
      from selected_tab + selected_filter (see _resolve_recalc_groups).
      `metric` decides HOW the target's new share is computed:
        "market_share"  -> grow the share % directly
        "market_volume" -> grow the implied volume, convert back to share
                           using the (unchanged) parent volume
      Siblings are always renormalized so the group sums to 100%, and
      every volume at every tab is derived downstream in
      Model_Input_Service.py as total_volume(base) * share -- no changes
      needed there for this endpoint's own logic, since its build_*
      functions all resolve `fetch_forecast_scenario` as a bare name at
      call time, which we monkeypatch below.
    """
    ta = payload.ta_name
    scenario = payload.scenario_name
 
    try:
        with get_connection() as conn, conn.cursor() as cur:
 
            cur.execute("""
                SELECT config
                FROM raw_hiv_treat.forecast_configurations
                WHERE config->>'ta_name' = %s
            """, (ta,))
            row = cur.fetchone()
            config = row[0] if row else {}
 
            cur.execute("""
                SELECT market, source_of_market, product, metric, forecast_data
                FROM raw_hiv_treat.forecast_outputs
                WHERE ta_name = %s
                  AND scenario_name = %s
            """, (ta, scenario))
            rows = cur.fetchall()
            if not rows:
                raise HTTPException(
                    status_code=404,
                    detail=f"No forecasts found for scenario '{scenario}'"
                )
 
            base_map = {}
            for market, source, product, metric_col, forecast_data in rows:
                base_map[(market, _norm_source(source), product, metric_col)] = forecast_data

            overrides = dict(base_map)
 
            model_type = (payload.model_type or "ets").lower()
 
            # Frontend sends "market_share" or "market_volume". Normalize
            # to the internal sentinel used throughout this file
            # ("market_share" / "volume") in exactly this one place, and
            # reject anything else instead of silently falling back --
            # a typo here (e.g. "market_volume" being mistaken for the
            # old internal "volume" sentinel) previously caused a silent
            # wrong-mode recalculation with no error at all.
            raw_metric = (payload.metric or "market_share").lower()
            if raw_metric not in _METRIC_ALIASES:
                raise HTTPException(
                    status_code=400,
                    detail=f"metric must be 'market_share' or 'market_volume', got '{payload.metric}'"
                )
            interp_metric = _METRIC_ALIASES[raw_metric]
 
            factors = payload.factors or {}
            if hasattr(factors, "model_dump"):
                factors = factors.model_dump()
 
            fp = config.get("forecast_periods")
            
            train_start = config.get("train_start_date")
            train_end = config.get("train_end_date")
            ets = (factors.get("ets") if isinstance(factors, dict) else {}) or {}
            growth = (factors.get("growth") if isinstance(factors, dict) else {}) or {}
            multiplier = factors.get("multiplier", 1.0) if isinstance(factors, dict) else 1.0
            multiplier_horizon = factors.get("multiplier_horizon", "Forecast") if isinstance(factors, dict) else "Forecast"
 
            tab = (payload.selected_tab or "total_market_volume").lower()
 
            print("SELECTED TAB =", tab, "METRIC =", interp_metric)
            print("FACTORS =", factors)
 
            # Confirmed against Model_Input_Service.build_scenario_market_analysis:
            # MIS always fetches the top-level total row with source="ALL"
            # (literal), never None. Keep the None-source fallback only as
            # a defensive backstop.
            total_key = ("ALL", "ALL", "ALL", "market_volume")
            if total_key not in base_map:
                total_key = ("ALL", None, "ALL", "market_volume")
 
            if tab == "total_market_volume":
                # ---------- recalc TOTAL market_volume only ----------
                if total_key in base_map:
                    data = base_map[total_key]
                    months, tv, fv = _series_from_data(data)
                    values = tv + fv
                    if months and values:
                        try:
                            forecast_train_start = train_start

                            if model_type == "moving_average":

                                new_fc = process_moving_average_forecast(
                                    series_months=months,
                                    series_values=values,
                                    train_start_date=forecast_train_start,
                                    train_end_date=train_end,
                                    forecast_periods=fp,
                                    window=growth.get("window", 3),
                                    metric="market_volume",
                                    multiplier=multiplier,
                                    multiplier_horizon=multiplier_horizon
                                )

                            else:

                                new_fc = process_forecast(
                                    months, values, forecast_train_start, train_end, fp,
                                    model_type=model_type,
                                    metric="market_volume",
                                    alpha=ets.get("alpha"),
                                    beta=ets.get("beta"),
                                    gamma=ets.get("gamma"),
                                    total_growth_pct=growth.get("total_growth", 0),
                                    duration=growth.get("duration", fp),
                                    k=growth.get("k_value"),
                                    trajectory_start=growth.get("trajectory_start"),
                                    multiplier=multiplier,
                                    multiplier_horizon=multiplier_horizon
                                )
                            overrides[total_key] = new_fc
                        except Exception as e:
                            print(f"Forecast failed key={total_key} error={e}")
 
            else:
                # ---------- SHARE RENORMALIZATION MODE ----------
                groups = _resolve_recalc_groups(tab, payload.selected_filter, base_map)
 
                if not groups:
                    print(f"WARNING: no recalc groups resolved for tab={tab}, "
                          f"filter={payload.selected_filter}. Response will be base values.")
 
                # anchor total volume series, needed for metric="market_volume" mode
                total_vals = None
                if interp_metric == "volume" and total_key in base_map:
                    _, tv, fv = _series_from_data(base_map[total_key])
                    total_vals = tv + fv
 
                for target_key, sibling_keys in groups:
                    months, tv, fv = _series_from_data(base_map[target_key])
                    n = len(tv) + len(fv)
                    if n == 0:
                        continue
 
                    if interp_metric == "volume" and total_vals is None:
                        print(f"WARNING: metric=market_volume requested but total market_volume "
                              f"row missing; falling back to market_share mode for {target_key}")
                        effective_metric = "market_share"
                        parent_vol = None
                    else:
                        effective_metric = interp_metric
                        if effective_metric == "volume":
                            padded_total = total_vals[:n]
                            if len(padded_total) < n:
                                padded_total = padded_total + [padded_total[-1]] * (n - len(padded_total))
                            parent_vol = _parent_volume_for_group(base_map, target_key, padded_total, n)
                        else:
                            parent_vol = None
 
                    forecast_train_start = train_start

                    if model_type == "moving_average":
                        forecast_train_start = payload.selected_filter.start_date

                    target_new_fv = _compute_target_new_share(
                        target_key, base_map, parent_vol, months, n,
                        effective_metric, model_type,
                        ets.get("alpha"), ets.get("beta"), ets.get("gamma"),
                        growth, multiplier, multiplier_horizon,
                        forecast_train_start, train_end, fp
                    )
                                        
 
                    target_clipped, new_sibling_fv = _renormalize_siblings(
                        target_new_fv, base_map, sibling_keys
                    )
 
                    target_override = dict(base_map[target_key])
                    target_override["forecast_values"] = target_clipped
                    overrides[target_key] = target_override
 
                    for sk in sibling_keys:
                        sib_override = dict(base_map[sk])
                        sib_override["forecast_values"] = new_sibling_fv[sk]
                        overrides[sk] = sib_override
 
            # Alias overrides so MIS's hardcoded source=None lookups
            # (e.g. Retail product rows) hit recalculated values instead
            # of silently falling back to the unmodified DB row.
            overrides = _augment_with_source_aliases(overrides, base_map)
 
            # Monkeypatch fetch_forecast_scenario in Model_Input_Service.
            # Every build_* function in MIS resolves this as a bare name
            # from the module's global namespace at call time, so this
            # patch transparently redirects all of MIS's reads through
            # `overrides` -- no edits needed inside Model_Input_Service.py
            # for this override mechanism (the normalize_shares_to_100
            # zero-fix is a separate, unrelated change in that file).
            def _same_scenario(a, b):
                if a is None or b is None:
                    return a == b
                if a.upper() == "BASE" and b.upper() == "BASE":
                    return True
                return a == b

            orig_fetch = MIS.fetch_forecast_scenario

            def fetch_with_override(cur_in, ta_in, market_in, source_in, product_in, metric_in, scenario_in):
                if _same_scenario(scenario_in, scenario):   # `scenario` = payload.scenario_name, closed over
                    k = (market_in, _norm_source(source_in), product_in, metric_in)
                    if k in overrides:
                        return overrides[k]
                return orig_fetch(cur_in, ta_in, market_in, source_in, product_in, metric_in, scenario_in)

            MIS.fetch_forecast_scenario = fetch_with_override
 
            try:
                response = MIS.build_apply_scenario_response(cur, payload, config)
 
                if "scenarios" in response and scenario in response["scenarios"]:
                    scenario_factors = response["scenarios"][scenario]["factors"]
 
                    scenario_factors["active_model"] = model_type
                    scenario_factors["multiplier"] = factors.get(
                        "multiplier", scenario_factors.get("multiplier", 1)
                    )
                    scenario_factors["multiplier_horizon"] = factors.get(
                        "multiplier_horizon",
                        scenario_factors.get("multiplier_horizon", "Forecast")
                    )
 
                    if model_type == "ets":
                        scenario_factors["ets"]["alpha"] = ets.get("alpha", scenario_factors["ets"].get("alpha"))
                        scenario_factors["ets"]["beta"] = ets.get("beta", scenario_factors["ets"].get("beta"))
                        scenario_factors["ets"]["gamma"] = ets.get("gamma", scenario_factors["ets"].get("gamma"))

                    elif model_type == "moving_average":

                        selected_end = payload.selected_filter.end_date

                        fp_to_use = fp

                        if selected_end:
                            train_end_dt = parse_month(train_end)
                            selected_end_dt = parse_month(selected_end)

                            fp_to_use = (
                                (selected_end_dt.year - train_end_dt.year) * 12
                                + (selected_end_dt.month - train_end_dt.month)
                            )

                            fp_to_use = max(1, fp_to_use)

                        growth = growth or {}
                        growth["forecast_periods"] = fp_to_use

                        scenario_factors["moving_average"]["window"] = growth.get(
                            "window",
                            scenario_factors["moving_average"].get("window")
                        )

                        scenario_factors["moving_average"]["forecast_periods"] = fp_to_use
 
                    elif model_type in ("linear", "exponential", "logarithmic", "scurve", "s-curve"):
                        norm_key = "scurve" if model_type == "s-curve" else model_type
                        block = scenario_factors[norm_key]
                        block["duration"] = growth.get("duration", block.get("duration"))
                        block["total_growth"] = growth.get("total_growth", block.get("total_growth"))
                        block["trajectory_start"] = growth.get("trajectory_start", block.get("trajectory_start"))
                        if "k_value" in block:
                            block["k_value"] = growth.get("k_value", block.get("k_value"))
 
            finally:
                MIS.fetch_forecast_scenario = orig_fetch
 
            return response
 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    


from app.hiv_treat.services.refresh_helpers import refresh_engine,build_refresh_response,normalize_overall_labels,filter_market_distribution_chart,filter_product_distribution_chart,filter_market_product_chart,filter_product_market_chart
from app.hiv_treat.routes.refresh_models import RefreshEditsRequest
from types import SimpleNamespace
from copy import deepcopy


@router.post("/refresh-edits")
def refresh_edits(payload: RefreshEditsRequest):

    print("==============================")
    print("TA :", payload.ta_name)
    print("Scenario :", payload.scenario_name)
    print("Tab :", payload.selected_tab)
    print("Metric :", payload.selected_metric)
    print("Edited rows :", payload.edited_rows)
    print("==============================")

    try:
        with get_connection() as conn, conn.cursor() as cur:

            # --------------------------------------------------
            # 1. Load forecasting configuration
            # --------------------------------------------------
            cur.execute(
                """
                SELECT config
                FROM raw_hiv_treat.forecast_configurations
                WHERE config->>'ta_name' = %s
                """,
                (payload.ta_name,),
            )

            row = cur.fetchone()
            config = row[0] if row else {}

            # --------------------------------------------------
            # 2. Normalize selected_filter
            # --------------------------------------------------
            selected_filter = payload.selected_filter

            if isinstance(selected_filter, dict):
                filter_object = SimpleNamespace(
                    start_date=selected_filter.get(
                        "start_date"
                    ),
                    end_date=selected_filter.get(
                        "end_date"
                    ),
                    market=selected_filter.get(
                        "market",
                        selected_filter.get(
                            "markets",
                            [],
                        ),
                    ),
                    product=selected_filter.get(
                        "product",
                        selected_filter.get(
                            "products",
                            [],
                        ),
                    ),
                )
            else:
                filter_object = selected_filter

            apply_payload = SimpleNamespace(
                ta_name=payload.ta_name,
                scenario_name=payload.scenario_name,
                selected_filter=filter_object,
            )

            # --------------------------------------------------
            # 3. Load all saved scenarios
            # --------------------------------------------------
            response = build_apply_scenario_response(
                cur,
                apply_payload,
                config,
            )

            active_scenario = payload.scenario_name

            if active_scenario not in response["scenarios"]:
                raise ValueError(
                    f"Active scenario '{active_scenario}' "
                    "was not found."
                )

            # --------------------------------------------------
            # 4. Capture original active scenario
            # --------------------------------------------------
            original_market_analysis = deepcopy(
                response["scenarios"][active_scenario][
                    "market_analysis"
                ]
            )

            # --------------------------------------------------
            # 5. Recompute only the active scenario
            # --------------------------------------------------
            refreshed_market_analysis = refresh_engine(
                payload=payload,
                original_market_analysis=(
                    original_market_analysis
                ),
            )

            refreshed_market_analysis = (
                normalize_overall_labels(
                    refreshed_market_analysis
                )
            )

            # --------------------------------------------------
            # 6. Replace only the active scenario
            # --------------------------------------------------
            response["scenarios"][active_scenario][
                "market_analysis"
            ] = deepcopy(
                refreshed_market_analysis
            )

            # --------------------------------------------------
            # 7. Normalize and filter every scenario
            # --------------------------------------------------
            for scenario_name, scenario_data in (
                response["scenarios"].items()
            ):
                scenario_market_analysis = scenario_data.get(
                    "market_analysis"
                )

                if scenario_market_analysis is None:
                    continue

                scenario_market_analysis = (
                    normalize_overall_labels(
                        scenario_market_analysis
                    )
                )

                # Market Distribution:
                # filter chart by selected market.
                scenario_market_analysis = (
                    filter_market_distribution_chart(
                        market_analysis=(
                            scenario_market_analysis
                        ),
                        selected_filter=filter_object,
                    )
                )

                # Product Distribution:
                # filter chart by selected product.
                scenario_market_analysis = (
                    filter_product_distribution_chart(
                        market_analysis=(
                            scenario_market_analysis
                        ),
                        selected_filter=filter_object,
                    )
                )

                

                # Channel-Product:
                # filter chart by selected market.
                scenario_market_analysis = (
                    filter_market_product_chart(
                        market_analysis=(
                            scenario_market_analysis
                        ),
                        selected_filter=filter_object,
                    )
                )

                # Product-Channel:
                # filter chart by selected product.
                scenario_market_analysis = (
                    filter_product_market_chart(
                        market_analysis=(
                            scenario_market_analysis
                        ),
                        selected_filter=filter_object,
                    )
                )

                

                scenario_data["market_analysis"] = (
                    scenario_market_analysis
                )

            response["active_scenario"] = (
                active_scenario
            )

            response = post_process_scenarios(response)

            # --------------------------------------------------
            # 8. Debug monthly and yearly chart series
            # --------------------------------------------------
            for scenario_name, scenario_data in (
                response["scenarios"].items()
            ):
                analysis = scenario_data.get(
                    "market_analysis"
                )

                if not analysis:
                    continue

                debug_sections = [
                    (
                        "Market Distribution",
                        "market_distribution",
                    ),
                    (
                        "Product Distribution",
                        "product_distribution",
                    ),
                    (
                        "Channel-Product",
                        "market_product",
                    ),
                    (
                        "Product-Channel",
                        "product_market",
                    ),
                ]

                for display_name, section_name in (
                    debug_sections
                ):
                    for metric_name in (
                        "market_volume",
                        "market_share",
                    ):
                        for period_name in (
                            "monthly",
                            "yearly",
                        ):
                            series = (
                                analysis
                                .get(section_name, {})
                                .get(metric_name, {})
                                .get(period_name, {})
                                .get("chart", {})
                                .get("series", [])
                            )

                            print(
                                f"{scenario_name} "
                                f"{display_name} "
                                f"{metric_name} "
                                f"{period_name}:",
                                [
                                    item.get("label")
                                    for item in series
                                ],
                            )

            return response

    except HTTPException:
        raise

    except Exception as e:
        import traceback

        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


def scenario_exists(cur, ta, scenario_name):
    cur.execute("""
        SELECT 1
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name = %s
        LIMIT 1
    """, (ta, scenario_name))

    return cur.fetchone() is not None

@router.post("/save-scenarios")
def save_scenario(payload: SaveScenarioRequest):

    ta = payload.ta_name
    scenario = payload.scenario_name
    # print("================================")
    # print("FULL PAYLOAD")
    # print(payload.model_dump())
    # print("FACTORS CLASS:", type(payload.factors))
    # print("FACTORS MODULE:", type(payload.factors).__module__)
    # print("FACTORS ATTRS:", payload.factors.model_dump())
    # print("================================")

    try:
        with get_connection() as conn, conn.cursor() as cur:

            if scenario.upper() != "BASE" and scenario_exists(
                cur,
                ta,
                scenario
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Scenario '{scenario}' already exists"
                )

            user_id = getattr(
                payload,
                "user_id",
                None
            ) or "default_user"
            factors = payload.factors.model_dump() if payload.factors else {}

            if payload.model_type == "linear":
                factors["linear"] = factors.pop("growth", None)
                factors["active_model"] = "linear"

            elif payload.model_type == "scurve":
                factors["scurve"] = factors.pop("growth", None)
                factors["active_model"] = "scurve"

            elif payload.model_type == "exponential":
                factors["exponential"] = factors.pop("growth", None)
                factors["active_model"] = "exponential"

            elif payload.model_type == "logarithmic":
                factors["logarithmic"] = factors.pop("growth", None)
                factors["active_model"] = "logarithmic"

            print("================================")
            print("MODEL TYPE:", payload.model_type)
            print("ORIGINAL FACTORS:", payload.factors)
            print("TRANSFORMED FACTORS:", factors)
            print("================================")
            _save_market_analysis(
                cur,
                ta,
                scenario,
                user_id,
                payload.market_analysis,
                factors
            )

            conn.commit()

            response = build_save_scenario_response(
                cur,
                ta,
                scenario,
                payload.selected_filter
            )

            return response

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(500, str(e))
    
@router.post("/apply_selected_scenario")
def apply_scenario(payload: ApplySelectedScenarioRequest):
    """
    User clicks a scenario in the table -> return the same shape as
    save_scenario's response, but read-only: no DB write, just builds
    full detail for the clicked scenario and total_market_volume-only
    for every other scenario. Reuses build_save_scenario_response as-is,
    since that function already implements exactly this split.
    """
    ta = payload.ta_name
    scenario = payload.scenario_name
 
    try:
        with get_connection() as conn, conn.cursor() as cur:
            available_scenarios = MIS.get_scenarios(cur, ta)
            if scenario not in available_scenarios:
                raise HTTPException(
                    status_code=404,
                    detail=f"Scenario '{scenario}' not found for ta_name '{ta}'"
                )
 
            response = build_save_scenario_response(cur, ta, scenario, payload.selected_filter)
            return response
 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

def scenario_exists_save(cur, ta, scenario):
    cur.execute("""
        SELECT 1 FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND UPPER(COALESCE(scenario_name, 'BASE')) = UPPER(%s)
        LIMIT 1
    """, (ta, scenario))
    return cur.fetchone() is not None

@router.put("/scenarios/{scenario_name}")
def update_scenario(payload: UpdateScenarioRequest):
    """
    Updates an EXISTING scenario's saved data and returns the same response
    shape as save-scenarios. Unlike the create endpoint, this rejects if
    the scenario does NOT already exist (a PUT updates a resource that's
    there, it doesn't silently create one) and blocks updating "Base"
    directly through this endpoint -- Base is treated as the source-of-
    truth engine forecast, not something this UI action should overwrite.
    Confirm that restriction is actually what you want; remove the check
    below if Base should be editable this way too.
    """
    ta = payload.ta_name
    scenario_name =payload.scenario_name

    if scenario_name != payload.scenario_name:
        raise HTTPException(
            status_code=400,
            detail=f"URL scenario '{scenario_name}' does not match body scenario_name '{payload.scenario_name}'"
        )

    scenario = payload.scenario_name

    try:
        with get_connection() as conn, conn.cursor() as cur:

            if scenario.upper() == "BASE":
                raise HTTPException(
                    status_code=400,
                    detail="Base cannot be updated through this endpoint"
                )

            if not scenario_exists_save(cur, ta, scenario):
                raise HTTPException(
                    status_code=404,
                    detail=f"Scenario '{scenario}' does not exist for ta_name '{ta}'"
                )

            user_id = payload.user_id or "default_user"
            factors = payload.factors.model_dump() if payload.factors else {}

            if payload.model_type == "linear":
                factors["linear"] = factors.pop("growth", None)
                factors["active_model"] = "linear"

            elif payload.model_type == "scurve":
                factors["scurve"] = factors.pop("growth", None)
                factors["active_model"] = "scurve"

            elif payload.model_type == "exponential":
                factors["exponential"] = factors.pop("growth", None)
                factors["active_model"] = "exponential"

            elif payload.model_type == "logarithmic":
                factors["logarithmic"] = factors.pop("growth", None)
                factors["active_model"] = "logarithmic"

            _save_market_analysis(
                cur, ta, scenario, user_id,
                payload.market_analysis,factors
            )

            conn.commit()

            response = build_save_scenario_response(
                cur, ta, scenario, payload.selected_filter
            )
            return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


def delete_scenario_rows(cur, ta, scenario):
    cur.execute("""
        DELETE FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND UPPER(COALESCE(scenario_name, 'BASE')) = UPPER(%s)
    """, (ta, scenario))
    return cur.rowcount

@router.delete("/scenarios/{scenario_name}")
def delete_scenario(payload: DeleteScenarioRequest):
    ta = payload.ta_name
    scenario = payload.scenario_name

    try:
        with get_connection() as conn, conn.cursor() as cur:

            if scenario.upper() == "BASE":
                raise HTTPException(
                    status_code=400,
                    detail="Base cannot be deleted"
                )

            if not scenario_exists_save(cur, ta, scenario):
                raise HTTPException(
                    status_code=404,
                    detail=f"Scenario '{scenario}' does not exist for ta_name '{ta}'"
                )

            delete_scenario_rows(cur, ta, scenario)
            conn.commit()

            remaining_scenarios = MIS.get_scenarios(cur, ta)
            active_scenario = remaining_scenarios[0]  # canonical Base label, always first

            response = build_save_scenario_response(
                cur, ta, active_scenario, payload.selected_filter
            )
            return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    
class RunCalculationRequest(BaseModel):
    ta_name: str
    selected_filter: dict
    selected_tab: str
    impact_curve_configuration: dict


@router.post("/run-calculation")
def run_calculation_endpoint(payload: RunCalculationRequest) -> dict:
    try:
        return run_calculation(payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))