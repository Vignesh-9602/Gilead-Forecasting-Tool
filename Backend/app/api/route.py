from fastapi import APIRouter, Query
from app.schemas.config_schema import Config
from app.services.forecast_service import process_forecast
from app.db.connection import get_connection
from app.repository.metrics_repo import get_oncology_metrics

from uuid import uuid4
import json

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------
@router.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------
# GET: Basic Configuration (Configuration Page)
# ------------------------------------------------------------------
@router.get("/oncology/config-basic")
def get_oncology_basic_config(
    ta: str = Query(..., description="Therapeutic Area (e.g. Oncology)")
):
    """
    Returns configuration inputs needed by the frontend:
    - Forecast start date
    - Granularity
    - Avg vials per brand (derived from Dose_Master)
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # 1. Earliest forecast start date
        cur.execute("""
            SELECT MIN(make_date(year, month, 1))
            FROM raw.Fact_Market_Share
            WHERE LOWER(TA) = LOWER(%s)
        """, (ta,))
        min_date = cur.fetchone()[0]

        # 2. Avg vials per brand
        cur.execute("""
            SELECT
                Brand,
                Dose_Per_Month,
                Vials_Per_Dose,
                Compliance
            FROM raw.Dose_Master
            ORDER BY Brand
        """)

        avg_vials = []
        for brand, dose_pm, vials_pd, compliance in cur.fetchall():
            value = dose_pm * vials_pd * compliance
            avg_vials.append({
                "brand": brand,
                "avg_vials": round(float(value), 2)
            })

        return {
            "ta": ta,
            "forecast_start_date": (
                min_date.strftime("%Y-%m-%d") if min_date else None
            ),
            "granularity": ["monthly"],
            "avg_vials": avg_vials
        }

    finally:
        cur.close()
        conn.close()


# ------------------------------------------------------------------
# POST: Save Configuration (Persistence)
# ------------------------------------------------------------------
@router.post("/configurations")
def save_configuration(payload: dict):
    """
    Saves the configuration sent by frontend.
    Each save creates a new row (append-only).
    """
    config_id = str(uuid4())
    ta = payload.get("ta")
    config = payload.get("config")

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO app.forecast_configurations
            (config_id, ta, config)
            VALUES (%s, %s, %s)
        """, (config_id, ta, json.dumps(config)))

        conn.commit()

        return {
            "config_id": config_id,
            "status": "saved"
        }

    finally:
        cur.close()
        conn.close()


# ------------------------------------------------------------------
# (Kept for future use) Forecast Selector helper
# ------------------------------------------------------------------
def resolve_entity_key(ui_key: str, metrics: dict) -> str | None:
    parts = ui_key.split("-")

    indication = parts[0]
    lot = parts[2]
    brand = "-".join(parts[3:])

    for repo_key in metrics.keys():
        repo_brand, repo_indication, repo_lot = repo_key.split("-")

        if (
            repo_brand == brand
            and repo_indication == indication
            and repo_lot == lot
        ):
            return repo_key

    return None


# ------------------------------------------------------------------
# (Kept for future use) Forecast API
# ------------------------------------------------------------------
@router.post("/forecast")
def forecast_endpoint(config: Config):
    """
    Runs forecast computation.
    Kept intact for future pages.
    """
    print("===== PAYLOAD RECEIVED FROM FRONTEND =====")
    print(config.model_dump())
    print("=========================================")

    ta = config.ta_name
    metrics = get_oncology_metrics(
        ta,
        config.train_start_date,
        config.train_end_date
    )

    results = []

    for ui_key in config.entity_keys:
        resolved_key = resolve_entity_key(ui_key, metrics)

        if not resolved_key:
            results.append({
                "ui_entity": ui_key,
                "error": "Entity not found"
            })
            continue

        forecast_result = process_forecast(
            metrics,
            resolved_key,
            config
        )

        results.append({
            "ui_entity": ui_key,
            "resolved_entity": resolved_key,
            "result": forecast_result
        })

    return {
        "ta": ta,
        "forecast_results": results
    }