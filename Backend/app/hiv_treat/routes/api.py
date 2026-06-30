from datetime import date
from fastapi import APIRouter, HTTPException
from uuid import uuid4
import json
from app.db.connection import get_connection
from typing import Dict, Any
from app.hiv_treat.routes.schema import Configuration,ConfigurationResponse,SaveConfigRequest,ModelInputFilterResponse,ApplyScenarioRequest
from app.hiv_treat.utils.config import add_months
from app.hiv_treat.services.HIV_helper_functions import (
    get_total_market_volume,
    get_market_distribution,
    get_product_distribution,
    get_market_wise_product
)
from app.hiv_treat.services.Model_Input_Service import build_apply_scenario_response
# -----------------------------------
# FORECAST MODELS
# -----------------------------------
from app.services.forecast_service import process_forecast

from app.hiv_treat.services.HIV_helper_functions import (
    process_growth_forecast_auto,
    normalize_shares
)

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
                months, values,
                cfg.train_start_date,
                cfg.train_end_date,
                forecast_periods,
                model_type="ETS",
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

            # --- MARKET LEVEL (FIXED) ---
            market_data = {}
            market_data_map = {}

            # --- SOURCE LEVEL (UNCHANGED) ---
            source_data = {}

            for y, m, market, source, share in rows:

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

                    source_data[src]["months"].append(month)
                    source_data[src]["values"].append(float(share))


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
                market_fc[market] = process_growth_forecast_auto(
                    d["months"], d["values"],
                    cfg.train_start_date,
                    cfg.train_end_date,
                    forecast_periods,
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
                source_fc[src] = process_growth_forecast_auto(
                    d["months"], d["values"],
                    cfg.train_start_date,
                    cfg.train_end_date,
                    forecast_periods,
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
                product_fc[key] = process_growth_forecast_auto(
                    d["months"], d["values"],
                    cfg.train_start_date,
                    cfg.train_end_date,
                    forecast_periods,
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
            selected_filter = {
                "market": markets[0] if markets else None,
                "product": products[0] if products else None,
                "start_date": start_date,
                "end_date": end_date
            }

            return {
                "ta_name": ta,
                "markets": markets,
                "products": products,
                "available_months": months_sorted,
                "selected_filter": selected_filter
            }

    except Exception as e:
        raise HTTPException(500, str(e))
    

@router.post("/apply-scenario")
def apply_scenario(payload: ApplyScenarioRequest):

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

            return build_apply_scenario_response(cur, payload, config)

    except Exception as e:
        raise HTTPException(500, str(e))