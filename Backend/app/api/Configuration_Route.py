from fastapi import APIRouter, HTTPException
from uuid import uuid4
from datetime import date
import json

from app.api.Model_Inputs_Route import parse_month_date
from app.db.connection import get_connection
from app.schemas.config_schema import (
    SaveConfigRequest,
    UpdateAvgVialsRequest
)
from app.repository.metrics_repo import build_metrics_filter_data, build_metrics_hierarchy, get_oncology_metrics
from app.services.Secenario_Selection import save_base_scenario
from app.services.forecast_service import generate_full_base_forecast

router = APIRouter(prefix="/api")


# ----------------------------------------------------
# HEALTH
# ----------------------------------------------------
@router.get("/health")
def health():
    return {"status": "ok"}


# ----------------------------------------------------
# GET: TA LIST
# ----------------------------------------------------
@router.get("/ta/list",tags=["Configuration"])
def get_ta_list():
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT DISTINCT TA
            FROM raw.Indication_Master
            ORDER BY TA
        """)
        return {"ta_list": [row[0] for row in cur.fetchall()]}

    finally:
        cur.close()
        conn.close()


# ----------------------------------------------------
# GET: AVG VIAL MASTER (DEFAULTS)
# ----------------------------------------------------
@router.get("/configurations/{ta_name}/avg-vials",tags=["Configuration"])
def get_avg_vials_by_ta(ta_name: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        # --------------------------------------
        # Get TA-specific avg_vials (if exists)
        # --------------------------------------
        cur.execute(
            """
            SELECT avg_vials
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
            """,
            (ta_name,)
        )
        row = cur.fetchone()
        avg_vials = row[0] if row and row[0] else {}

        # --------------------------------------
        # Get DEFAULT Dose_Master values
        # --------------------------------------
        cur.execute(
            """
            SELECT Brand, Dose_Per_Month, Vials_Per_Dose
            FROM raw.Dose_Master
            ORDER BY Brand
            """
        )

        defaults = {
            brand: {
                "dose_per_month": dose,
                "vials_per_month": vials
            }
            for brand, dose, vials in cur.fetchall()
        }

        # --------------------------------------
        # Merge logic
        # TA values override defaults
        # --------------------------------------
        merged = defaults | avg_vials

        # --------------------------------------
        # Return list for UI table
        # --------------------------------------
        return [
            {
                "brand": brand,
                "dose_per_month": data["dose_per_month"],
                "vials_per_month": data["vials_per_month"],
            }
            for brand, data in merged.items()
        ]

    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# GET: LOAD FULL CONFIG BY TA
# ----------------------------------------------------
@router.get("/configurations/{ta_name}",tags=["Configuration"])
def get_configuration_by_ta(ta_name: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
        """, (ta_name,))

        row = cur.fetchone()
        if not row:
            return {"ta_name": ta_name, "exists": False, "config": None}

        return {"ta_name": ta_name, "exists": True, "config": row[0]}

    finally:
        cur.close()
        conn.close()


# ----------------------------------------------------
# POST: SAVE / UPDATE FORECAST CONFIG
# ----------------------------------------------------
@router.post("/configurations",tags=["Configuration"])
def save_configuration(payload: SaveConfigRequest):

    cfg = payload.config

    # =====================================================
    # 0. VALIDATION
    # =====================================================
    start_date = date.fromisoformat(cfg.train_start_date)
    end_date = date.fromisoformat(cfg.train_end_date)

    if start_date > end_date:
        raise HTTPException(
            400,
            "train_start_date cannot be after train_end_date"
        )

    if cfg.model_granularity.lower() != "monthly":
        raise HTTPException(
            400,
            "Only 'monthly' granularity is supported"
        )
    # =============================
    # VALIDATE AGAINST DB DATES
    # =============================
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                MIN(make_date(year, month, 1)) AS min_date,
                MAX(make_date(year, month, 1)) AS max_date
            FROM raw.fact_market_share
            WHERE ta = %s
        """, (cfg.ta_name,))

        row = cur.fetchone()

        if not row or not row[0] or not row[1]:
            raise HTTPException(
                400,
                "No data available for selected TA"
            )

        min_date, max_date = row

    finally:
        cur.close()
        conn.close()

    # =============================
    # VALIDATION LOGIC
    # =============================

    # Start date check
    if start_date < min_date or start_date > max_date:
        raise HTTPException(
            400,
            f"Invalid Train Start Date. Available data is from {min_date} to {max_date}"
        )

    # End date check
    if end_date < min_date or end_date > max_date:
        raise HTTPException(
            400,
            f"Invalid Train End Date. Available data is from {min_date} to {max_date}"
    )
    ta = cfg.ta_name

    # =====================================================
    # 1. UPSERT CONFIGURATION
    # =====================================================
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO raw.forecast_configurations (config_id, config)
            VALUES (%s, %s)
            ON CONFLICT ((config->>'ta_name'))
            DO UPDATE SET
                config = EXCLUDED.config,
                updated_at = CURRENT_TIMESTAMP
        """, (
            str(uuid4()),
            json.dumps(cfg.model_dump())
        ))
        conn.commit()

    finally:
        cur.close()
        conn.close()

    # =====================================================
    # 2. INVALIDATE EXISTING BASE (CRITICAL FIX)
    # =====================================================
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            DELETE FROM raw.forecast_scenarios
            WHERE scenario_name = 'BASE'
              AND ta_name = %s
        """, (ta,))
        conn.commit()

    finally:
        cur.close()
        conn.close()

    # =====================================================
    # 3. GENERATE BASE DATA
    # =====================================================
    train_start = parse_month_date(cfg.train_start_date)
    train_end = parse_month_date(cfg.train_end_date)

    metrics_data = get_oncology_metrics(ta)

  # ---------- NPS BASE ----------
    nps_base = generate_full_base_forecast(
        metrics=metrics_data,
        config=cfg.model_dump(),
        metric="nps",
        train_start=train_start,
        train_end=train_end
    )

    for s in nps_base["series"]:
        indication = s["display"]["indication"]   #    DISPLAY VALUE
        lot = s["display"]["lot"]                 #    DISPLAY VALUE

        factors = nps_base["factors_map"][(indication, lot)]
        # ↑ NO .get(), crash loudly if mismatched

        save_base_scenario(
            ta=ta,
            indication=indication,
            lot=lot,
            metric="nps",
            product=None,
            chart={
                "months": nps_base["months"],
                "forecast_start_index": nps_base["forecast_start_index"],
                "train_values": s["train_values"],
                "forecast_values": s["forecast_values"],
            },
            factors=factors
        )

    # ---------- MARKET SHARE BASE ----------
    ms_base = generate_full_base_forecast(
        metrics=metrics_data,
        config=cfg.model_dump(),
        metric="market_share",
        train_start=train_start,
        train_end=train_end
    )

    for s in ms_base["series"]:
        indication = s["display"]["indication"]   
        lot = s["display"]["lot"]                 
        product = s["display"]["product"]         

        factors = ms_base["factors_map"][(indication, lot, product)]
        # ↑ NO .get()

        save_base_scenario(
            ta=ta,
            indication=indication,
            lot=lot,
            metric="market_share",
            product=product,
            chart={
                "months": ms_base["months"],
                "forecast_start_index": ms_base["forecast_start_index"],
                "train_values": s["train_values"],
                "forecast_values": s["forecast_values"],
            },
            factors=factors
        )


    # =====================================================
    #    FINAL RESPONSE
    # =====================================================
    return {
        "ta_name": ta,
        "status": "config_saved_and_base_rebuilt"
    }



# ----------------------------------------------------
# POST: SAVE / UPDATE AVG VIALS (UPSERT SAFE)
# ----------------------------------------------------
@router.post("/configurations/avg-vials",tags=["Configuration"])
def update_avg_vials(payload: UpdateAvgVialsRequest):
    conn = get_connection()
    cur = conn.cursor()

    try:
        #    Valid brands check
        cur.execute("SELECT DISTINCT Brand FROM raw.Dose_Master")
        valid_brands = {row[0] for row in cur.fetchall()}

        avg_vials_map = {}

        for v in payload.avg_vials:
            if (
                not v.brand
                or v.brand.lower() == "string"
                or v.brand.lower().startswith("additionalprop")
                or v.brand not in valid_brands
            ):
                continue

            avg_vials_map[v.brand] = {
                "dose_per_month": v.dose_per_month,
                "vials_per_month": v.vials_per_month
            }

        if not avg_vials_map:
            raise HTTPException(400, "No valid avg_vials data provided")

        #    UPSERT avg_vials (insert row if config not present)
        cur.execute(
            """
            INSERT INTO raw.forecast_configurations
                (config_id, config, avg_vials)
            VALUES
                (%s, %s, %s)
            ON CONFLICT ((config->>'ta_name'))
            DO UPDATE SET
                avg_vials = COALESCE(raw.forecast_configurations.avg_vials, '{}'::jsonb)
                            || EXCLUDED.avg_vials,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(uuid4()),
                json.dumps({"ta_name": payload.ta_name}),
                json.dumps(avg_vials_map),
            )
        )

        conn.commit()

        return {
            "ta_name": payload.ta_name,
            "updated_brands": list(avg_vials_map.keys()),
            "status": "avg_vials_saved"
        }

    finally:
        cur.close()
        conn.close()

@router.get("/metrics/filters/{ta_name}", tags=["Model_Input"])
def get_metrics_filters(ta_name: str):

    conn = get_connection()
    cur = conn.cursor()

    try:
        # Scenario names
        cur.execute("""
            SELECT DISTINCT scenario_name
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
            ORDER BY scenario_name
        """, (ta_name,))

        scenario_names = [r[0] for r in cur.fetchall()]

        if not scenario_names:
            return {
                "ta_name": ta_name,
                "scenario_names": [],
                "data": {},
                "metric_filters": [],
                "default_filter": {
                    "scenario_name": "",
                    "indication": "",
                    "lot": "",
                    "metric": "nps",
                    "product": ""
                }
            }

        cur.execute("""
            WITH scenario_lots AS (
                SELECT DISTINCT
                    scenario_name,
                    ta_name,
                    indication,
                    lot
                FROM raw.forecast_scenarios
                WHERE ta_name = %s
            )
            SELECT
                sl.scenario_name,
                im.indications AS indication,
                sl.lot,
                im.brand_name AS product
            FROM scenario_lots sl
            JOIN raw.indication_master im
              ON im.ta = sl.ta_name
             AND LOWER(im.indications) = LOWER(sl.indication)
            WHERE im.brand_name IS NOT NULL
            ORDER BY
                sl.scenario_name,
                im.indications,
                sl.lot,
                im.brand_name
        """, (ta_name,))

        rows = cur.fetchall()

    finally:
        cur.close()
        conn.close()

    data = {}

    for scenario, indication, lot, product in rows:
        scenario_map = data.setdefault(scenario, {})
        indication_map = scenario_map.setdefault(indication, {})
        lot_products = indication_map.setdefault(lot, [])

        if product and product not in lot_products:
            lot_products.append(product)

    # -----------------------------------------------------
    # Default filter for FE initial page load
    # -----------------------------------------------------

    default_scenario = "BASE" if "BASE" in scenario_names else scenario_names[0]

    default_indication = ""
    default_lot = ""
    default_product = ""

    if default_scenario in data and data[default_scenario]:

        default_indication = sorted(
            data[default_scenario].keys()
        )[0]

        if default_indication and data[default_scenario][default_indication]:

            default_lot = sorted(
                data[default_scenario][default_indication].keys()
            )[0]

            # For nps, product should be blank
            default_product = ""

    return {
        "ta_name": ta_name,
        "scenario_names": scenario_names,
        "data": data,
        "metric_filters": [
            {"label": "Market Share", "value": "market_share"},
            {"label": "Overall Market Volume", "value": "nps"}
        ],
        "default_filter": {
            "scenario_name": default_scenario,
            "indication": default_indication,
            "lot": default_lot,
            "metric": "nps",
            "product": default_product
        }
    }