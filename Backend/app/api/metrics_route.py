from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException

from app.db.connection import get_connection
from app.repository.metrics_repo import get_oncology_metrics
from app.schemas.metrics_selection_schema import (
    MetricSelectionRequest,
    MetricRecalculateRequest,
    SaveChangesRequest,
)
from app.services.forecast_service import process_forecast

router = APIRouter(prefix="/api")


# =====================================================
# POST: APPLY (initial computation)
# =====================================================
@router.post("/metrics/apply")
def apply_metrics(payload: MetricSelectionRequest):

    ta = payload.ta_name
    indication = payload.indications[0].lower()
    metric = payload.metric_filter.lower()
    product = payload.product.strip().lower() if payload.product else ""

    if metric == "market_share" and not product:
        raise HTTPException(
            status_code=400,
            detail="Product is required when metric_filter is market_share"
        )

    # ---------------------------
    # Load forecast config
    # ---------------------------
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

    # ✅ IMPORTANT: DO NOT normalize dates here
    train_start_str = config["train_start_date"]
    train_end_str = config["train_end_date"]

    metrics = get_oncology_metrics(ta)

    # ---------------------------
    # Chart (focus series only)
    # ---------------------------
    lot = payload.lots[0].lower()
    chart_key = (
        f"{product}-{indication}-{lot}"
        if metric == "market_share"
        else f"{indication}-{lot}"
    )

    if chart_key not in metrics:
        raise HTTPException(400, "Selected series not found")

    chart_data = metrics[chart_key]

    chart = process_forecast(
        chart_data["month"],
        chart_data[metric],
        train_start_str,
        train_end_str,
        config["forecast_periods"],
        multiplier=1.0,
        override_params=None,
        trend_type_override="additive",
        seasonality="none",
        metric=metric
    )

    # ==================================================
    # TABLE (NESTED STRUCTURE)
    # ==================================================
    table = []
    grouped = {}

    if metric == "market_share":
        num_months = len(chart["months"])

        for key, data in metrics.items():
            parts = key.split("-")
            if len(parts) != 3:
                continue

            _, ind_n, _ = parts
            if ind_n != indication:
                continue

            lot_label = data["display"]["lot"]

            if lot_label not in grouped:
                grouped[lot_label] = {
                    "lot": lot_label,
                    "total": [100.0] * num_months,
                    "children": []
                }

            row = process_forecast(
                data["month"],
                data["market_share"],
                config["train_start_date"],
                config["train_end_date"],
                config["forecast_periods"],
                multiplier=1.0,
                override_params=None,
                trend_type_override="additive",
                seasonality="none",
                metric="market_share"
            )

            grouped[lot_label]["children"].append({
                "label": data["display"]["brand"],
                "values": row["train_values"] + row["forecast_values"]
            })

    else:  # NPS
        for key, data in metrics.items():
            parts = key.split("-")
            if len(parts) != 2:
                continue

            ind_n, _ = parts
            if ind_n != indication:
                continue

            lot_label = data["display"]["lot"]

            if lot_label not in grouped:
                grouped[lot_label] = {
                    "lot": lot_label,
                    "total": [],
                    "children": []
                }

            row = process_forecast(
                data["month"],
                data["nps"],
                config["train_start_date"],
                config["train_end_date"],
                config["forecast_periods"],
                multiplier=1.0,
                override_params=None,
                trend_type_override="additive",
                seasonality="none",
                metric="nps"
            )

            grouped[lot_label]["children"].append({
                "label": "NPS",
                "values": row["train_values"] + row["forecast_values"]
            })

    table = list(grouped.values())

    return {
        "therapy_area": ta,
        "indication": payload.indications[0],
        "metric": metric.replace("_", " ").title(),
        "product": payload.product if payload.product else None,
        "factors": chart["factors"],
        "chart": chart,
        "table": table
    }

# =====================================================
# POST: RECALCULATE (user‑adjusted factors)
# =====================================================
@router.post("/metrics/recalculate")
def recalculate_metrics(payload: MetricRecalculateRequest):

    ta = payload.ta_name
    indication = payload.indications[0].lower()
    metric = payload.metric_filter.lower()
    product = payload.product.strip().lower() if payload.product else ""
    factors = payload.factors

    if metric == "market_share" and not product:
        raise HTTPException(
            status_code=400,
            detail="Product is required when metric_filter is market_share"
        )

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

    # ✅ SAME RULE: pass config dates AS-IS
    train_start_str = config["train_start_date"]
    train_end_str = config["train_end_date"]

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

    chart = process_forecast(
        chart_data["month"],
        chart_data[metric],
        train_start_str,
        train_end_str,
        config["forecast_periods"],
        multiplier=factors.multiplier,
        override_params={
            "alpha": factors.alpha,
            "beta": factors.beta,
            "gamma": factors.gamma
        },
        trend_type_override=factors.trend_type.lower(),
        seasonality=factors.seasonality.lower(),
        metric=metric
    )

    grouped = {}
    num_months = len(chart["months"])

    for key, data in metrics.items():
        parts = key.split("-")
        if (metric == "market_share" and len(parts) != 3) or \
           (metric == "nps" and len(parts) != 2):
            continue

        if parts[1] != indication:
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
            train_start_str,
            train_end_str,
            config["forecast_periods"],
            multiplier=factors.multiplier,
            override_params={
                "alpha": factors.alpha,
                "beta": factors.beta,
                "gamma": factors.gamma
            },
            trend_type_override=factors.trend_type.lower(),
            seasonality=factors.seasonality.lower(),
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
        "product": payload.product if payload.product else None,
        "factors": chart["factors"],
        "chart": chart,
        "table": list(grouped.values())
    }


# =====================================================
# POST: RECALCULATE (user‑adjusted factors)
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