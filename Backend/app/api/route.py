from fastapi import APIRouter, HTTPException
from uuid import uuid4
from datetime import date
import json

from app.db.connection import get_connection
from app.schemas.config_schema import (
    SaveConfigRequest,
    UpdateAvgVialsRequest
)
from app.repository.metrics_repo import build_metrics_filter_data, build_metrics_hierarchy, get_oncology_metrics

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
@router.get("/ta/list")
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
@router.get("/configurations/{ta_name}/avg-vials")
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
@router.get("/configurations/{ta_name}")
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
@router.post("/configurations")
def save_configuration(payload: SaveConfigRequest):
    cfg = payload.config

    start_date = date.fromisoformat(cfg.train_start_date)
    end_date = date.fromisoformat(cfg.train_end_date)

    if start_date > end_date:
        raise HTTPException(400, "train_start_date cannot be after train_end_date")

    if cfg.model_granularity.lower() != "monthly":
        raise HTTPException(400, "Only 'monthly' granularity is supported")

    conn = get_connection()
    cur = conn.cursor()

    try:
        # ✅ UPSERT config (avg_vials untouched)
        cur.execute(
            """
            INSERT INTO raw.forecast_configurations (config_id, config)
            VALUES (%s, %s)
            ON CONFLICT ((config->>'ta_name'))
            DO UPDATE SET
                config = EXCLUDED.config,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                str(uuid4()),
                json.dumps(cfg.model_dump()),
            )
        )

        conn.commit()
        return {"ta_name": cfg.ta_name, "status": "config_saved"}

    finally:
        cur.close()
        conn.close()


# ----------------------------------------------------
# POST: SAVE / UPDATE AVG VIALS (UPSERT SAFE)
# ----------------------------------------------------
@router.post("/configurations/avg-vials")
def update_avg_vials(payload: UpdateAvgVialsRequest):
    conn = get_connection()
    cur = conn.cursor()

    try:
        # ✅ Valid brands check
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

        # ✅ UPSERT avg_vials (insert row if config not present)
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

@router.get("/metrics/filters/{ta_name}")
def get_metrics_filters(ta_name: str):

    metrics = get_oncology_metrics(ta_name)

    if not metrics:
        return {
            "ta_name": ta_name,
            "data": {},
            "metric_filters": []
        }

    data = build_metrics_filter_data(metrics)

    return {
        "ta_name": ta_name,
        "data": data,
        "metric_filters": [
            { "label": "Market Share", "value": "market_share" },
            { "label": "New Patient Start", "value": "nps" }
        ]
    }