from datetime import date
from fastapi import APIRouter, HTTPException
from uuid import uuid4
import json
from app.db.connection import get_connection
from typing import Dict, Any
from app.hiv_treat.routes.schema import Configuration,ConfigurationResponse,SaveConfigRequest
from app.hiv_treat.utils.config import add_months

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
    
#save config
@router.post("/save-configurations", tags=["Configuration"])
def save_configuration(payload: SaveConfigRequest):

    cfg = payload.config

    #validation
    try:
        start_date = date.fromisoformat(cfg.train_start_date)
        end_date = date.fromisoformat(cfg.train_end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format")

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

    #convert forecast to periods
    try:
        forecast_end_date = date.fromisoformat(cfg.forecast_periods)
    except ValueError:
        raise HTTPException(400, "Invalid forecast_periods date format")

    forecast_periods = (
        (forecast_end_date.year - end_date.year) * 12
        + (forecast_end_date.month - end_date.month)
    )

    if forecast_periods <= 0:
        raise HTTPException(
            400,
            "Forecast end date must be after Train End Date"
        )

    #prepare config
    config_to_save = cfg.model_dump()
    config_to_save["forecast_periods"] = forecast_periods

    # Normalize TA (important)
    ta = cfg.ta_name.replace("_", " ").strip()

    #validate against hiv date range
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
                raise HTTPException(
                    400,
                    f"No data available for TA '{ta}'"
                )

            min_date, max_date = row

    except Exception as e:
        raise HTTPException(500, f"DB error: {str(e)}")

    #validation check
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

    #insert
    try:
        with get_connection() as conn, conn.cursor() as cur:

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
        raise HTTPException(500, f"Save failed: {str(e)}")

    return {
        "ta_name": ta,
        "status": "configuration_saved",
        "forecast_periods": forecast_periods
    }
