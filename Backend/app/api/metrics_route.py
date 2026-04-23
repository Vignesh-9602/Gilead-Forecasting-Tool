from datetime import datetime
import json

from fastapi import APIRouter, Body, HTTPException

from app.db.connection import get_connection
from app.repository.metrics_repo import get_oncology_metrics
from app.schemas.metrics_selection_schema import (
    MetricSelectionRequest,
    MetricRecalculateRequest,
    SaveChangesRequest,
    SaveScenarioRequest,
)
from app.services.forecast_service import process_forecast
from dateutil.relativedelta import relativedelta

router = APIRouter(prefix="/api")


# =====================================================
# Helper: Build Factors (Single Source of Truth)
# =====================================================
def build_factors(chart, trajectory_input=None):
    """
    Builds response factors in a consistent format.
    Handles both dict and Pydantic inputs safely.
    """

    # -------- Forecast start → trajectory start --------
    forecast_start_index = chart["forecast_start_index"]
    forecast_months = chart["months"][forecast_start_index:]
    trajectory_start = forecast_months[0] if forecast_months else None

    # -------- Normalize trajectory input (dict safe) --------
    if trajectory_input is not None:
        if hasattr(trajectory_input, "dict"):
            trajectory_input = trajectory_input.dict()

    # -------- ETS --------
    ets_block = {
        "alpha": chart["factors"]["alpha"],
        "beta": chart["factors"]["beta"],
        "gamma": chart["factors"]["gamma"],
        "trend_type": chart["factors"].get("trend_type", "additive"),
        "seasonality": chart["factors"].get("seasonality", "none"),
    }

    # -------- Trajectory --------
    trajectory_block = {
        "growth_type": (
            trajectory_input.get("growth_type")
            if trajectory_input else "linear"
        ),
        "total_growth": (
            trajectory_input.get("total_growth")
            if trajectory_input else 0
        ),
        "duration": (
            trajectory_input.get("duration")
            if trajectory_input else 12
        ),
        "trajectory_start": trajectory_start,
    }

    # -------- Final --------
    return {
        "multiplier": chart["factors"].get("multiplier", 1.0),
        "ets": ets_block,
        "trajectory": trajectory_block
    }


# =====================================================
# APPLY
# =====================================================
@router.post("/metrics/apply")
def apply_metrics(payload: MetricSelectionRequest):

    ta = payload.ta_name
    indication = payload.indications[0].lower()
    metric = payload.metric_filter.lower()
    product = payload.product.strip().lower() if payload.product else ""

    if metric == "market_share" and not product:
        raise HTTPException(400, "Product is required")

    # -------- CONFIG --------
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
            """,
            (ta,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(400, "Forecast config not found")
        config = row[0]
    finally:
        cur.close()
        conn.close()

    metrics = get_oncology_metrics(ta)

    lot = payload.lots[0].lower()
    chart_key = (
        f"{product}-{indication}-{lot}"
        if metric == "market_share"
        else f"{indication}-{lot}"
    )

    if chart_key not in metrics:
        raise HTTPException(400, "Selected series not found")

    chart_data = metrics[chart_key]

    # -------- FORECAST --------
    chart = process_forecast(
        chart_data["month"],
        chart_data[metric],
        config["train_start_date"],
        config["train_end_date"],
        config["forecast_periods"],
        multiplier=1.0,
        override_params=None,
        seasonality="none",
        metric=metric
    )

    # ✅ Build factors BEFORE removing from chart
    factors = build_factors(chart)

    # ✅ Remove duplication
    chart.pop("factors", None)

    # -------- TABLE --------
    grouped = {}
    num_months = len(chart["months"])

    for key, data in metrics.items():
        parts = key.split("-")

        if metric == "market_share":
            if len(parts) != 3 or parts[1] != indication:
                continue
        else:
            if len(parts) != 2 or parts[0] != indication:
                continue

        lot_label = data["display"]["lot"]

        grouped.setdefault(lot_label, {
            "lot": lot_label,
            "total": [100.0] * num_months if metric == "market_share" else [],
            "children": []
        })

        series = data["market_share"] if metric == "market_share" else data["nps"]

        row = process_forecast(
            data["month"],
            series,
            config["train_start_date"],
            config["train_end_date"],
            config["forecast_periods"],
            multiplier=1.0,
            override_params=None,
            seasonality="none",
            metric=metric
        )

        grouped[lot_label]["children"].append({
            "label": data["display"]["brand"] if metric == "market_share" else "NPS",
            "values": row["train_values"] + row["forecast_values"]
        })

    return {
        "therapy_area": ta,
        "indication": payload.indications[0],
        "metric": metric.replace("_", " ").title(),
        "product": payload.product or None,
        "factors": factors,
        "chart": chart,
        "table": list(grouped.values())
    }


# =====================================================
# RECALCULATE
# =====================================================
@router.post("/metrics/recalculate")

def recalculate_metrics(
    payload: MetricRecalculateRequest
):


    ta = payload.ta_name
    indication = payload.indications[0].lower()
    metric = payload.metric_filter.lower()
    product = payload.product.strip().lower() if payload.product else ""
    model_type = payload.model_type.lower()

    factors_input = payload.factors
    multiplier = factors_input.get("multiplier", 1.0)
    ets = factors_input.get("ets", {})
    trajectory = factors_input.get("trajectory", {})

    # -------- CONFIG --------
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
            """,
            (ta,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(400, "Forecast config not found")
        config = row[0]
    finally:
        cur.close()
        conn.close()

    metrics = get_oncology_metrics(ta)

    lot = payload.lots[0].lower()
    chart_key = (
        f"{product}-{indication}-{lot}"
        if metric == "market_share"
        else f"{indication}-{lot}"
    )

    if chart_key not in metrics:
        raise HTTPException(400, "Selected series not found")

    chart_data = metrics[chart_key]

    # -------- FORECAST --------
    chart = process_forecast(
        chart_data["month"],
        chart_data[metric],
        config["train_start_date"],
        config["train_end_date"],
        config["forecast_periods"],
        multiplier=multiplier,
        override_params={
            "alpha": ets.get("alpha"),
            "beta": ets.get("beta"),
            "gamma": ets.get("gamma"),
        },
        seasonality=(ets.get("seasonality") or "none").lower(),
        metric=metric,
        growth_type=trajectory.get("growth_type") if model_type == "trajectory" else None,
        total_growth_pct=trajectory.get("total_growth") if model_type == "trajectory" else 0,
        growth_duration=trajectory.get("duration"),
        trajectory_start=trajectory.get("trajectory_start") if model_type == "trajectory" else None
    )

    # ✅ Rebuild factors from backend truth
    rebuilt_factors = build_factors(
        chart,
        trajectory_input=trajectory if model_type == "trajectory" else None
    )

    # ✅ Remove duplication
    chart.pop("factors", None)

    # -------- TABLE --------
    grouped = {}
    num_months = len(chart["months"])

    for key, data in metrics.items():
        parts = key.split("-")

        if metric == "market_share":
            if len(parts) != 3 or parts[1] != indication:
                continue
        else:
            if len(parts) != 2 or parts[0] != indication:
                continue

        lot_label = data["display"]["lot"]

        grouped.setdefault(lot_label, {
            "lot": lot_label,
            "total": [100.0] * num_months if metric == "market_share" else [],
            "children": []
        })

        series = data["market_share"] if metric == "market_share" else data["nps"]

        row = process_forecast(
            data["month"],
            series,
            config["train_start_date"],
            config["train_end_date"],
            config["forecast_periods"],
            multiplier=multiplier,
            override_params={
                "alpha": ets.get("alpha"),
                "beta": ets.get("beta"),
                "gamma": ets.get("gamma"),
            },
            seasonality=(ets.get("seasonality") or "none").lower(),
            metric=metric,
            growth_type=trajectory.get("growth_type") if model_type == "trajectory" else None,
            total_growth_pct=trajectory.get("total_growth") if model_type == "trajectory" else 0,
            growth_duration=trajectory.get("duration"),
            trajectory_start=trajectory.get("trajectory_start") if model_type == "trajectory" else None
        )

        grouped[lot_label]["children"].append({
            "label": data["display"]["brand"] if metric == "market_share" else "NPS",
            "values": row["train_values"] + row["forecast_values"]
        })

    return {
        "therapy_area": ta,
        "indication": payload.indications[0],
        "metric": metric.replace("_", " ").title(),
        "product": payload.product or None,
        "factors": rebuilt_factors,
        "chart": chart,
        "table": list(grouped.values())
    }

# =====================================================
# POST: SAVE CHANGES (UNCHANGED)
# =====================================================
@router.post("/metrics/save-changes")
def save_changes(payload: SaveChangesRequest):
    """
    Save user-edited table values and update chart accordingly.
    - Backend DOES NOT recompute totals
    - Backend DOES NOT smooth history
    - Backend trusts FE table as authoritative
    """

    metric = payload.metric.lower()
    if metric not in ["market_share", "nps"]:
        raise HTTPException(
            status_code=400,
            detail="Save Changes supports only market_share or nps"
        )

    # --------------------------------------------------
    # Load forecast config
    # --------------------------------------------------
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
            """,
            (payload.therapy_area,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(400, "Forecast config not found")
        config = row[0]
    finally:
        cur.close()
        conn.close()

    forecast_periods = config["forecast_periods"]
    train_start_date = config["train_start_date"]

    # --------------------------------------------------
    # ✅ Find values row correctly (Pydantic-safe)
    # --------------------------------------------------
    product_values = None

    for lot_group in payload.table:
        if lot_group.lot != payload.lot:
            continue

        if metric == "market_share":
            # ✅ product is required
            for child in lot_group.children:
                if child.label == payload.product:
                    product_values = child.values
                    break

        else:  # ✅ NPS — single row, no product
            if lot_group.children:
                product_values = lot_group.children[0].values

    if product_values is None:
        raise HTTPException(
            status_code=400,
            detail="Selected row not found in table"
        )

    # --------------------------------------------------
    # ✅ Train / forecast split
    # --------------------------------------------------
    train_len = len(product_values) - forecast_periods
    if train_len < 0:
        raise HTTPException(
            status_code=400,
            detail="Forecast periods exceed total values length"
        )

    # --------------------------------------------------
    # ✅ Build MONTHS (same logic as your earlier version)
    # --------------------------------------------------
    train_start = datetime.fromisoformat(train_start_date).replace(day=1)

    train_months = [
        (train_start + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(train_len)
    ]

    last_train_month = datetime.fromisoformat(train_months[-1])
    forecast_months = [
        (last_train_month + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(1, forecast_periods + 1)
    ]

    # --------------------------------------------------
    # ✅ Final chart
    # --------------------------------------------------
    chart = {
        "months": train_months + forecast_months,
        "train_values": product_values[:train_len],
        "forecast_values": product_values[train_len:],
        "forecast_start_index": train_len
    }

    return {
        "chart": chart,
        "table": payload.table
    }
@router.post("/metrics/save")
def save_scenario(payload: SaveScenarioRequest):

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            INSERT INTO forecast_scenarios (
                scenario_name,
                user_id,
                ta_name,
                indication,
                lot,
                metric,
                product,
                model_type,
                factors,
                chart,
                table_data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                payload.scenario_name,
                payload.user_id,
                payload.ta_name,
                payload.indication,
                payload.lot,
                payload.metric,
                payload.product,
                payload.model_type,
                json.dumps(payload.factors),
                json.dumps(payload.chart),
                json.dumps(payload.table),
            )
        )

        scenario_id = cur.fetchone()[0]
        conn.commit()

    finally:
        cur.close()
        conn.close()

    return {
        "scenario_id": f"SCN_{scenario_id}",
        "scenario_name": payload.scenario_name,
        "message": "Scenario saved successfully"
    }