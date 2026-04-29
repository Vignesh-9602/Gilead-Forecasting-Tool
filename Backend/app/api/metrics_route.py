from datetime import datetime
import json
from fastapi import APIRouter, HTTPException
from dateutil.relativedelta import relativedelta
from app.db.connection import get_connection
from app.repository.metrics_repo import get_oncology_metrics
from app.schemas.metrics_selection_schema import (
    MetricSelectionRequest,
    MetricRecalculateRequest,
    SaveChangesRequest,
    SaveScenarioRequest,
)
from app.services.Secenario_Selection import get_base_scenario,save_base_scenario
from app.services.forecast_service import generate_full_base_forecast, process_forecast

router = APIRouter(prefix="/api")


# =====================================================
# DATE HELPER
# =====================================================
def parse_month_date(date_str: str) -> datetime:
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        dt = datetime.strptime(date_str, "%d-%m-%Y")
    return dt.replace(day=1)


# =====================================================
# FACTORS BUILDER
# =====================================================
def build_factors(chart, trajectory_input=None):

    forecast_start_index = chart["forecast_start_index"]
    forecast_months = chart["months"][forecast_start_index:]
    trajectory_start = forecast_months[0] if forecast_months else None

    if hasattr(trajectory_input, "dict"):
        trajectory_input = trajectory_input.dict()

    return {
        "multiplier": chart["factors"].get("multiplier", 1.0),
        "ets": {
            "alpha": chart["factors"]["alpha"],
            "beta": chart["factors"]["beta"],
            "gamma": chart["factors"]["gamma"],
            "trend_type": chart["factors"].get("trend_type", "additive"),
            "seasonality": chart["factors"].get("seasonality", "none"),
        },
        "trajectory": {
            "growth_type": trajectory_input.get("growth_type") if trajectory_input else "linear",
            "total_growth": trajectory_input.get("total_growth") if trajectory_input else 0,
            "duration": trajectory_input.get("duration") if trajectory_input else 12,
            "trajectory_start": trajectory_start,
        }
    }


# =====================================================
# APPLY
# =====================================================
@router.post("/metrics/apply")
def apply_metrics(payload: MetricSelectionRequest):

    ta = payload.ta_name
    scenario = payload.scenario_name
    indication_code = payload.indications[0].strip().lower()
    selected_product_code = payload.product.strip().lower() if payload.product else None
    selected_lot_code = payload.lots[0].strip().lower()

    conn = get_connection()
    cur = conn.cursor()

    try:
        # =====================================================
        # 1️⃣ FETCH INDICATION + BASE FACTORS (NPS default)
        # =====================================================
        cur.execute("""
            SELECT
                fs.factors,
                im.indications
            FROM raw.forecast_scenarios fs
            JOIN raw.indication_master im
              ON im.ta = fs.ta_name
             AND LOWER(im.indications) = LOWER(fs.indication)
            WHERE
                fs.ta_name = %s
                AND fs.scenario_name = %s
                AND LOWER(fs.indication) = %s
            ORDER BY fs.lot
            LIMIT 1
        """, (ta, scenario, indication_code))

        row = cur.fetchone()
        factors = row[0] if row else {}
        indication = row[1] if row else payload.indications[0]

        # =====================================================
        # 2️⃣ NPS DATA (ALL LOTS)
        # =====================================================
        cur.execute("""
            SELECT fs.lot, fs.chart
            FROM raw.forecast_scenarios fs
            WHERE
                fs.ta_name = %s
                AND fs.scenario_name = %s
                AND LOWER(fs.indication) = %s
                AND fs.metric = 'nps'
            ORDER BY fs.lot
        """, (ta, scenario, indication_code))

        nps_rows = cur.fetchall()

        nps_series = []
        nps_table = {}
        months = None
        forecast_start_index = None

        for lot, chart in nps_rows:
            months = chart["months"]
            forecast_start_index = chart["forecast_start_index"]

            nps_series.append({
                "lot": lot,
                "label": "NPS",
                "train_values": chart["train_values"],
                "forecast_values": chart["forecast_values"],
            })

            nps_table.setdefault(lot, {
                "lot": lot,
                "total": [],
                "children": []
            })["children"].append({
                "label": "NPS",
                "values": chart["train_values"] + chart["forecast_values"]
            })

        # =====================================================
        # 3️⃣ MARKET SHARE DATA
        # =====================================================
        cur.execute("""
            SELECT
                fs.lot,
                fs.chart,
                im.brand_name
            FROM raw.forecast_scenarios fs
            JOIN raw.indication_master im
              ON im.ta = fs.ta_name
             AND LOWER(im.indications) = LOWER(fs.indication)
             AND LOWER(im.brand_name) = LOWER(fs.product)
            WHERE
                fs.ta_name = %s
                AND fs.scenario_name = %s
                AND LOWER(fs.indication) = %s
                AND fs.metric = 'market_share'
            ORDER BY fs.lot, im.brand_name
        """, (ta, scenario, indication_code))

        ms_rows = cur.fetchall()

        ms_series = []
        ms_table = {}

        for lot, chart, product in ms_rows:

            # ✅ CHART → selected LOT only
            if lot.lower() == selected_lot_code:
                ms_series.append({
                    "lot": lot,
                    "label": product,
                    "train_values": chart["train_values"],
                    "forecast_values": chart["forecast_values"],
                })

            # ✅ TABLE → all LOTs + all products
            ms_table.setdefault(lot, {
                "lot": lot,
                "total": [100.0] * len(months),
                "children": []
            })["children"].append({
                "label": product,
                "values": chart["train_values"] + chart["forecast_values"]
            })

        # =====================================================
        # 4️⃣ MARKET SHARE FACTORS (SELECTED PRODUCT)
        # =====================================================
        if selected_product_code:
            cur.execute("""
                SELECT fs.factors
                FROM raw.forecast_scenarios fs
                WHERE
                    fs.ta_name = %s
                    AND fs.scenario_name = %s
                    AND LOWER(fs.indication) = %s
                    AND fs.metric = 'market_share'
                    AND LOWER(fs.product) = %s
                ORDER BY fs.lot
                LIMIT 1
            """, (ta, scenario, indication_code, selected_product_code))

            row = cur.fetchone()
            if row:
                factors = row[0]

    finally:
        cur.close()
        conn.close()

    # =====================================================
    # ✅ FINAL RESPONSE
    # =====================================================
    return {
        "therapy_area": ta,
        "indication": indication,
        "factors": factors,  # includes multiplier_horizon
        "metrics_data": {
            "nps": {
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": nps_series,
                },
                "table": list(nps_table.values()),
            },
            "market_share": {
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": ms_series,
                },
                "table": list(ms_table.values()),
            },
        }
    }

# =====================================================
# RECALCULATE
# =====================================================
@router.post("/metrics/recalculate")
def recalculate_metrics(payload: MetricRecalculateRequest):

    # -----------------------------------------------------
    # INPUT NORMALIZATION
    # -----------------------------------------------------
    ta = payload.ta_name

    indication_input = payload.indications[0].strip()
    indication_l = indication_input.lower()

    selected_lot_input = payload.lots[0].strip()
    selected_lot_l = selected_lot_input.lower()

    metric_to_recalc = payload.metric_filter.strip().lower()

    selected_product_input = payload.product.strip() if payload.product else None
    selected_product_l = selected_product_input.lower() if selected_product_input else None

    model_type = payload.model_type.lower()
    factors_input = payload.factors.dict()

    multiplier = factors_input.get("multiplier", 1.0)
    multiplier_horizon = factors_input.get("multiplier_horizon", "Forecast")

    ets = factors_input.get("ets", {})
    trajectory = factors_input.get("trajectory", {})

    # -----------------------------------------------------
    # 1️⃣ LOAD CONFIG
    # -----------------------------------------------------
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
        """, (ta,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(400, "Forecast config not found")
        config = row[0]
    finally:
        cur.close()
        conn.close()

    train_start = parse_month_date(config["train_start_date"])
    train_end = parse_month_date(config["train_end_date"])
    forecast_periods = config["forecast_periods"]

    # -----------------------------------------------------
    # 2️⃣ LOAD BASE SERIES FROM DB (ONLY SOURCE)
    # -----------------------------------------------------
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT metric, lot, product, chart
            FROM raw.forecast_scenarios
            WHERE
                scenario_name = 'BASE'
                AND ta_name = %s
                AND LOWER(indication) = %s
        """, (ta, indication_l))
        base_rows = cur.fetchall()
        if not base_rows:
            raise HTTPException(400, "Base scenario not found")
    finally:
        cur.close()
        conn.close()

    # -----------------------------------------------------
    # SERIES CONTAINERS
    # -----------------------------------------------------
    nps_series = []
    ms_chart_series = []   # ✅ Chart → selected LOT only
    ms_table_series = []   # ✅ Table → all LOTs

    months = None
    forecast_start_index = None

    # -----------------------------------------------------
    # 3️⃣ LOOP THROUGH BASE SERIES
    # -----------------------------------------------------
    for metric, lot, product, base_chart in base_rows:

        lot_l = lot.lower()
        product_l = product.lower() if product else None

        is_selected = (
            metric == metric_to_recalc
            and lot_l == selected_lot_l
            and (metric != "market_share" or product_l == selected_product_l)
        )

        base_months = base_chart["months"]
        base_train_values = base_chart["train_values"]
        base_forecast_values = base_chart["forecast_values"]
        base_start_idx = base_chart["forecast_start_index"]

        # ---------------------------
        # RECALCULATE SELECTED SERIES
        # ---------------------------
        if is_selected:
            full_series_months = base_months
            full_series_values = base_train_values + base_forecast_values

            row = process_forecast(
                full_series_months,
                full_series_values,
                train_start,
                train_end,
                forecast_periods,
                multiplier=multiplier,
                multiplier_horizon=multiplier_horizon,
                override_params={
                    "alpha": ets.get("alpha"),
                    "beta": ets.get("beta"),
                    "gamma": ets.get("gamma"),
                },
                seasonality=ets.get("seasonality", "none"),
                metric=metric,
                growth_type=trajectory.get("growth_type")
                    if model_type == "trajectory"
                    else None,
                total_growth_pct=trajectory.get("total_growth", 0)
                    if model_type == "trajectory"
                    else 0,
                growth_duration=trajectory.get("duration"),
                trajectory_start=trajectory.get("trajectory_start"),
            )

        # ---------------------------
        # KEEP BASE
        # ---------------------------
        else:
            row = {
                "months": base_months,
                "train_values": base_train_values,
                "forecast_values": base_forecast_values,
                "forecast_start_index": base_start_idx,
            }

        months = row["months"]
        forecast_start_index = row["forecast_start_index"]

        series_entry = {
            "lot": lot,
            "label": product if metric == "market_share" else "NPS",
            "train_values": row["train_values"],
            "forecast_values": row["forecast_values"],
        }

        # ---------------------------
        # ROUTING TO CHART / TABLE
        # ---------------------------
        if metric == "nps":
            nps_series.append(series_entry)

        else:
            # ✅ Market share table → all LOTs
            ms_table_series.append(series_entry)

            # ✅ Market share chart → selected LOT only
            if lot_l == selected_lot_l:
                ms_chart_series.append(series_entry)

    # -----------------------------------------------------
    # 4️⃣ BUILD TABLES (DERIVED)
    # -----------------------------------------------------
    nps_table, ms_table = {}, {}
    num_months = len(months)

    for s in nps_series:
        nps_table.setdefault(s["lot"], {
            "lot": s["lot"],
            "total": [],
            "children": []
        })["children"].append({
            "label": "NPS",
            "values": s["train_values"] + s["forecast_values"]
        })

    for s in ms_table_series:
        ms_table.setdefault(s["lot"], {
            "lot": s["lot"],
            "total": [100.0] * num_months,
            "children": []
        })["children"].append({
            "label": s["label"],
            "values": s["train_values"] + s["forecast_values"]
        })

    # -----------------------------------------------------
    # ✅ FINAL RESPONSE
    # -----------------------------------------------------
    return {
        "therapy_area": ta,
        "indication": indication_input,
        "factors": factors_input,
        "metrics_data": {
            "nps": {
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": nps_series,
                },
                "table": list(nps_table.values()),
            },
            "market_share": {
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": ms_chart_series,
                },
                "table": list(ms_table.values()),
            }
        }
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
    # Find values row correctly (Pydantic-safe)
    # --------------------------------------------------
    product_values = None

    for lot_group in payload.table:
        if lot_group.lot != payload.lot:
            continue

        if metric == "market_share":
            # product is required
            for child in lot_group.children:
                if child.label == payload.product:
                    product_values = child.values
                    break

        else:  # NPS — single row, no product
            if lot_group.children:
                product_values = lot_group.children[0].values

    if product_values is None:
        raise HTTPException(
            status_code=400,
            detail="Selected row not found in table"
        )

    # --------------------------------------------------
    # Train / forecast split
    # --------------------------------------------------
    train_len = len(product_values) - forecast_periods
    if train_len < 0:
        raise HTTPException(
            status_code=400,
            detail="Forecast periods exceed total values length"
        )

    # --------------------------------------------------
    # Build MONTHS (same logic as your earlier version)
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
# Build MULTI SERIES from table (LIKE APPLY)
# --------------------------------------------------
    series_list = []

    months = train_months + forecast_months
    forecast_start_index = train_len

    for lot_group in payload.table:
        lot_label = lot_group.lot

        for child in lot_group.children:
            values = child.values

            series_list.append({
                "lot": lot_label,
                "label": child.label,
                "train_values": values[:train_len],
                "forecast_values": values[train_len:]
            })

    # --------------------------------------------------
    # Final chart (MULTI SERIES)
    # --------------------------------------------------
    chart = {
        "months": months,
        "forecast_start_index": forecast_start_index,
        "series": series_list
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
            INSERT INTO raw.forecast_scenarios (
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