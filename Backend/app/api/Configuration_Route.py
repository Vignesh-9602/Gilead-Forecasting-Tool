from fastapi import APIRouter, HTTPException
from uuid import uuid4
from datetime import date
import json

from app.api.Model_Inputs_Route import parse_month_date
from app.db.connection import get_connection
from app.schemas.config_schema import (
    ConfigurationResponse,
    SaveConfigRequest,
    UpdateAvgVialsRequest
)
from app.repository.metrics_repo import build_metrics_filter_data, build_metrics_hierarchy, get_oncology_metrics
from app.services.Retaining_Filters import get_saved_user_filter
from app.services.Secenario_Selection import save_base_scenario
from app.services.forecast_service import generate_full_base_forecast
from app.services.scenario_service import get_scenario_filters

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
def add_months(source_date: date, months: int) -> date:
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1

    return date(year, month, 1)

def get_available_months(start_date: date, end_date: date):
    months = []

    current = date(
        start_date.year,
        start_date.month,
        1
    )

    end = date(
        end_date.year,
        end_date.month,
        1
    )

    while current <= end:
        months.append(current.isoformat())

        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return months
# ----------------------------------------------------
# GET: LOAD FULL CONFIG BY TA
# ----------------------------------------------------
@router.get(
    "/configurations/{ta_name}",
    response_model=ConfigurationResponse,
    tags=["Configuration"]
)
def get_configuration_by_ta(ta_name: str):

    conn = get_connection()
    cur = conn.cursor()

    try:

        # ==========================================
        # Always fetch available months
        # ==========================================
        cur.execute("""
            SELECT DISTINCT
                year,
                month
            FROM raw.fact_market_patients
            WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
            ORDER BY year, month
        """, (ta_name,))

        available_train_months = [
            date(int(year), int(month), 1).isoformat()
            for year, month in cur.fetchall()
        ]

        # ==========================================
        # Fetch configuration
        # ==========================================
        cur.execute("""
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
        """, (ta_name,))

        row = cur.fetchone()

        # ==========================================
        # First time load
        # ==========================================
        if not row:
            return {
                "ta_name": ta_name,
                "exists": False,
                "config": None,
                "available_train_months": available_train_months
            }

        config = row[0]

        train_end_date = date.fromisoformat(
            config["train_end_date"]
        )

        forecast_periods = int(
            config["forecast_periods"]
        )

        forecast_end_date = add_months(
            train_end_date,
            forecast_periods
        )

        config["forecast_periods"] = (
            forecast_end_date.isoformat()
        )

        return {
            "ta_name": ta_name,
            "exists": True,
            "config": config,
            "available_train_months": available_train_months
        }

    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# POST: SAVE / UPDATE FORECAST CONFIG
# ----------------------------------------------------
@router.post("/configurations", tags=["Configuration"])
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

    # =====================================================
    # 0.1 CONVERT FORECAST END DATE TO FORECAST PERIODS
    # FE sends forecast_periods as date, DB saves as number
    # =====================================================
    forecast_end_date = date.fromisoformat(cfg.forecast_periods)

    forecast_periods = (
        (forecast_end_date.year - end_date.year) * 12
        + (forecast_end_date.month - end_date.month)
    )

    if forecast_periods <= 0:
        raise HTTPException(
            400,
            "Forecast end date must be after Train End Date"
        )

    # Save only number in DB
    config_to_save = cfg.model_dump()
    config_to_save["forecast_periods"] = forecast_periods

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

    if start_date < min_date or start_date > max_date:
        raise HTTPException(
            400,
            f"Invalid Train Start Date. Available data is from {min_date} to {max_date}"
        )

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
            json.dumps(config_to_save)
        ))

        conn.commit()

    finally:
        cur.close()
        conn.close()

    # =====================================================
    # 2. INVALIDATE EXISTING BASE
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
        config=config_to_save,
        metric="nps",
        train_start=train_start,
        train_end=train_end
    )

    for s in nps_base["series"]:
        indication = s["display"]["indication"]
        lot = s["display"]["lot"]

        factors = nps_base["factors_map"][(indication, lot)]

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
        config=config_to_save,
        metric="market_share",
        train_start=train_start,
        train_end=train_end
    )

    for s in ms_base["series"]:
        indication = s["display"]["indication"]
        lot = s["display"]["lot"]
        product = s["display"]["product"]

        factors = ms_base["factors_map"][(indication, lot, product)]

        nps_series = next(
            (
                x for x in nps_base["series"]
                if (
                    x["display"]["indication"] == indication
                    and x["display"]["lot"] == lot
                )
            ),
            None
        )

        patient_metrics = None

        if nps_series:
            nps_values = (
                nps_series["train_values"]
                + nps_series["forecast_values"]
            )

            market_share_values = (
                s["train_values"]
                + s["forecast_values"]
            )

            final_patient_share = []

            for nps, share in zip(nps_values, market_share_values):
                patient_count = round(
                    float(nps or 0) * (float(share or 0) / 100),
                    2
                )

                final_patient_share.append(patient_count)

            patient_metrics = {
                "final_nps": [
                    round(float(x or 0), 2)
                    for x in nps_values
                ],
                "final_market_share": [
                    round(float(x or 0), 2)
                    for x in market_share_values
                ],
                "final_patient_share": final_patient_share
            }

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
            factors=factors,
            patient_metrics=patient_metrics
        )

    # =====================================================
    # FINAL RESPONSE
    # =====================================================
    return {
        "ta_name": ta,
        "status": "config_saved_and_base_rebuilt",
        # "forecast_periods": forecast_periods
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

    user_id = "system"

    conn = get_connection()
    cur = conn.cursor()

    try:
        filter_data = get_scenario_filters(cur, ta_name)

        saved_filter = get_saved_user_filter(cur, user_id, ta_name)

        default_filter = {
            **filter_data["default_filter"],
            "metric": "nps",
            "product": ""
        }

        selected_filter = (
            saved_filter.copy()
            if saved_filter
            else default_filter.copy()
        )

        selected_filter["scenario_name"] = "BASE"

        return {
            "ta_name": ta_name,

            "scenario_names": filter_data["scenario_names"],

            "data": filter_data["data"],

            "metric_filters": [
                {
                    "label": "Market Share",
                    "value": "market_share"
                },
                {
                    "label": "Overall Market Volume",
                    "value": "nps"
                }
            ],

            "selected_filter": selected_filter
        }

    finally:
        cur.close()
        conn.close()