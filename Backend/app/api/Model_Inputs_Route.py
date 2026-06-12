from datetime import datetime
import json
from fastapi import APIRouter, HTTPException
from dateutil.relativedelta import relativedelta
from app.db.connection import get_connection
from app.repository.metrics_repo import get_oncology_metrics
from app.schemas.metrics_selection_schema import (
    MetricSelectionRequest,
    MetricRecalculateRequest,
    Refreshchangerequest,
    SaveScenarioRequest,
    UpdateScenarioRequest
)
from app.services.Retaining_Filters import save_user_filter
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
@router.post("/metrics/apply",tags=["Model_Input"])
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
        # FETCH INDICATION + BASE FACTORS (NPS default)
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
        # NPS DATA (ALL LOTS)
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
                "train_values": [round(v) for v in chart["train_values"]],
                "forecast_values": [round(v) for v in chart["forecast_values"]],
            })

            nps_table.setdefault(lot, {
                "lot": lot,
                "total": [],
                "children": []
            })["children"].append({
                "label": "NPS",
                "values": [
                    round(v)
                    for v in (chart["train_values"] + chart["forecast_values"])
                ]
            })

        # =====================================================
        # MARKET SHARE DATA
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

        # =====================================================
        # STEP 1 → GROUP DATA LOT WISE
        # =====================================================
        lot_product_values = {}

        for lot, chart, product in ms_rows:

            values = chart["train_values"] + chart["forecast_values"]

            lot_product_values.setdefault(lot, []).append({
                "product": product,
                "values": values,
                "train_values": chart["train_values"],
                "forecast_values": chart["forecast_values"]
            })

        # =====================================================
        # STEP 2 → NORMALIZE TO 100
        # =====================================================
        for lot, products_data in lot_product_values.items():

            total_months = max(len(item["values"]) for item in products_data)

            monthly_totals = [0.0] * total_months

            for item in products_data:
                for idx, val in enumerate(item["values"]):
                    if idx < total_months:
                        monthly_totals[idx] += float(val or 0)

            ms_table[lot] = {
                "lot": lot,
                "total": [100.0] * total_months,
                "children": []
            }

            for item in products_data:

                normalized_values = []

                for idx in range(total_months):
                    val = item["values"][idx] if idx < len(item["values"]) else 0
                    total = monthly_totals[idx]

                    normalized_val = (
                        round((float(val or 0) / total) * 100, 2)
                        if total > 0 else 0
                    )

                    normalized_values.append(normalized_val)

                if lot.lower() == selected_lot_code:

                    train_len = len(item["train_values"])

                    ms_series.append({
                        "lot": lot,
                        "label": item["product"],
                        "train_values": normalized_values[:train_len],
                        "forecast_values": normalized_values[train_len:],
                    })

                ms_table[lot]["children"].append({
                    "label": item["product"],
                    "values": normalized_values
                })
        # =====================================================
        # MARKET SHARE FACTORS (SELECTED PRODUCT)
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
                
        # =====================================================
        # SAVE USER FILTER PREFERENCE
        # =====================================================
        selected_indication = payload.indications[0] if payload.indications else None
        selected_lot = payload.lots[0] if payload.lots else None
        selected_product = payload.product.strip() if payload.product and payload.product.strip() else None

        cur.execute("""
            UPDATE raw.user_filter_preferences
            SET
                scenario_name = COALESCE(%s, scenario_name),
                indication   = COALESCE(%s, indication),
                lot          = COALESCE(%s, lot),
                metric       = 'nps',
                product      = COALESCE(%s, product),
                updated_at   = CURRENT_TIMESTAMP
            WHERE user_id = %s
            AND ta_name = %s
        """, (
            scenario,
            selected_indication,
            selected_lot,
            selected_product,
            "system",
            ta
        ))

        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO raw.user_filter_preferences (
                    user_id,
                    ta_name,
                    scenario_name,
                    indication,
                    lot,
                    metric,
                    product
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                "system",
                ta,
                scenario,
                selected_indication,
                selected_lot,
                "nps",
                selected_product
            ))

        conn.commit()
    finally:
        cur.close()
        conn.close()

    # =====================================================
    #   FINAL RESPONSE
    # =====================================================
    return {
        "therapy_area": ta,
        "indication": indication,
        "factors": factors,  # includes multiplier_horizon
        "metrics_data": {
            "nps": {
                "unit": "",
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": nps_series,
                },
                "table": list(nps_table.values()),
            },
            "market_share": {
                "unit": "%",
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
@router.post("/metrics/recalculate", tags=["Model_Input"])
def recalculate_metrics(payload: MetricRecalculateRequest):

    ta = payload.ta_name
    scenario_name = payload.scenario_name.strip()

    indication_input = payload.indications[0].strip()
    indication_l = indication_input.lower()

    selected_lot_input = payload.lots[0].strip()
    selected_lot_l = selected_lot_input.lower()

    metric_to_recalc = payload.metric_filter.strip().lower()

    selected_product_input = payload.product.strip() if payload.product else None
    selected_product_l = selected_product_input.lower() if selected_product_input else None

    model_type = payload.model_type.lower().strip()

    factors_input = payload.factors.model_dump()

    multiplier = factors_input.get("multiplier", 1.0)
    multiplier_horizon = factors_input.get("multiplier_horizon", "Forecast")

    ets = factors_input.get("ets") or {}
    growth = factors_input.get("growth") or {}

    if metric_to_recalc == "market_share" and not selected_product_l:
        raise HTTPException(
            status_code=400,
            detail="product is required for market_share recalculate"
        )

    # -----------------------------------------------------
    # LOAD CONFIG
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
            raise HTTPException(
                status_code=400,
                detail="Forecast config not found"
            )

        config = row[0]

    finally:
        cur.close()
        conn.close()

    train_start = parse_month_date(config["train_start_date"])
    train_end = parse_month_date(config["train_end_date"])
    forecast_periods = int(config["forecast_periods"])

    # -----------------------------------------------------
    # LOAD SELECTED SCENARIO SERIES
    # -----------------------------------------------------
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                metric,
                lot,
                product,
                chart,
                factors
            FROM raw.forecast_scenarios
            WHERE scenario_name = %s
              AND ta_name = %s
              AND LOWER(indication) = %s
            ORDER BY metric, lot, product
        """, (
            scenario_name,
            ta,
            indication_l
        ))

        scenario_rows = cur.fetchall()

        if not scenario_rows:
            raise HTTPException(
                status_code=400,
                detail=f"Scenario '{scenario_name}' not found for selected indication"
            )

    finally:
        cur.close()
        conn.close()

    nps_series = []
    ms_chart_series = []
    ms_table_series = []

    months = None
    forecast_start_index = None

    selected_base_factors = {}
    selected_row_found = False

    for metric, lot, product, scenario_chart, scenario_factors in scenario_rows:

        metric_l = (metric or "").lower()
        lot_l = (lot or "").lower()
        product_l = (product or "").lower() if product else None

        is_selected = (
            metric_l == metric_to_recalc
            and lot_l == selected_lot_l
            and (
                metric_l != "market_share"
                or product_l == selected_product_l
            )
        )

        scenario_train_values = list(scenario_chart.get("train_values", []))
        scenario_forecast_values = list(scenario_chart.get("forecast_values", []))

        scenario_start_idx = scenario_chart.get(
            "forecast_start_index",
            len(scenario_train_values)
        )

        scenario_months = scenario_chart.get("months")

        if not scenario_months:
            total_months = len(scenario_train_values) + len(scenario_forecast_values)

            scenario_months = [
                (train_start + relativedelta(months=i)).strftime("%Y-%m-%d")
                for i in range(total_months)
            ]
        else:
            scenario_months = list(scenario_months)

        if is_selected:
            selected_row_found = True
            selected_base_factors = scenario_factors or {}

            full_series_months = list(scenario_months[:scenario_start_idx])
            full_series_values = list(scenario_train_values)

            if model_type == "ets":
                row = process_forecast(
                    full_series_months,
                    full_series_values,
                    train_start,
                    train_end,
                    forecast_periods,
                    model_type="ets",
                    metric=metric_l,
                    multiplier=multiplier,
                    multiplier_horizon=multiplier_horizon,
                    alpha=ets.get("alpha"),
                    beta=ets.get("beta"),
                    gamma=ets.get("gamma")
                )

            else:
                row = process_forecast(
                    full_series_months,
                    full_series_values,
                    train_start,
                    train_end,
                    forecast_periods,
                    model_type=model_type,
                    metric=metric_l,
                    multiplier=multiplier,
                    multiplier_horizon=multiplier_horizon,
                    total_growth_pct=growth.get("total_growth", 0),
                    duration=growth.get("duration", forecast_periods),
                    k=growth.get("k_value"),
                    trajectory_start=growth.get("trajectory_start")   
                )

        else:
            row = {
                "months": list(scenario_months),
                "train_values": list(scenario_train_values),
                "forecast_values": list(scenario_forecast_values),
                "forecast_start_index": scenario_start_idx
            }

        if months is None:
            months = list(row["months"])
            forecast_start_index = row["forecast_start_index"]

        series_entry = {
            "lot": lot,
            "label": product if metric_l == "market_share" else "NPS",
            "train_values": (
                    [round(v) for v in row["train_values"]]
                    if metric_l == "nps"
                    else list(row["train_values"])
                ),
                "forecast_values": (
                    [round(v) for v in row["forecast_values"]]
                    if metric_l == "nps"
                    else list(row["forecast_values"])
                )
        }

        if metric_l == "nps":
            nps_series.append(series_entry)

        elif metric_l == "market_share":
            ms_table_series.append(series_entry)

            if lot_l == selected_lot_l:
                ms_chart_series.append(series_entry)

    if not selected_row_found:
        raise HTTPException(
            status_code=400,
            detail="Selected LOT/metric/product combination not found in selected scenario"
        )

    # -----------------------------------------------------
    # BUILD TABLES
    # -----------------------------------------------------
    nps_table = {}
    ms_table = {}

    num_months = len(months) if months else 0

    for s in nps_series:
        nps_table.setdefault(s["lot"], {
            "lot": s["lot"],
            "total": [],
            "children": []
        })["children"].append({
            "label": "NPS",
            "values": list(s["train_values"]) + list(s["forecast_values"])
        })

    # Normalize market share values lot-wise, month-wise to total 100
    ms_grouped = {}

    for s in ms_table_series:
        ms_grouped.setdefault(s["lot"], []).append(s)

    for lot, series_list in ms_grouped.items():

        total_months = max(
            len(list(s["train_values"]) + list(s["forecast_values"]))
            for s in series_list
        )

        monthly_totals = [0.0] * total_months

        for s in series_list:
            values = list(s["train_values"]) + list(s["forecast_values"])

            for idx, val in enumerate(values):
                if idx < total_months:
                    monthly_totals[idx] += float(val or 0)

        ms_table[lot] = {
            "lot": lot,
            "total": [100.0] * total_months,
            "children": []
        }

        for s in series_list:
            values = list(s["train_values"]) + list(s["forecast_values"])

            normalized_values = []

            for idx in range(total_months):
                val = values[idx] if idx < len(values) else 0
                total = monthly_totals[idx]

                normalized_values.append(
                    round((float(val or 0) / total) * 100, 2)
                    if total > 0 else 0
                )

            ms_table[lot]["children"].append({
                "label": s["label"],
                "values": normalized_values
            })

    # -----------------------------------------------------
    # BUILD RESPONSE FACTORS
    # -----------------------------------------------------
    s_curve_factors = (
        selected_base_factors.get("scurve")
        or selected_base_factors.get("s_curve")
        or {}
    )

    response_factors = {
        "active_model": model_type,
        "multiplier": float(multiplier),
        "multiplier_horizon": multiplier_horizon,

        "ets": selected_base_factors.get("ets", {
            "alpha": None,
            "beta": None,
            "gamma": None
        }),

        "linear": selected_base_factors.get("linear", {
            "total_growth": None,
            "duration": None,
            "trajectory_start": None
        }),

        "exponential": selected_base_factors.get("exponential", {
            "total_growth": None,
            "duration": None,
            "k_value": None,
            "trajectory_start": None
        }),

        "logarithmic": selected_base_factors.get("logarithmic", {
            "total_growth": None,
            "duration": None,
            "k_value": None,
            "trajectory_start": None
        }),

        "scurve": {
            "total_growth": s_curve_factors.get("total_growth"),
            "duration": s_curve_factors.get("duration"),
            "k_value": s_curve_factors.get("k_value"),
            "trajectory_start": s_curve_factors.get("trajectory_start")
        }
    }

    # -----------------------------------------------------
    # OVERRIDE GROWTH FACTORS FOR ALL CURVE TYPES
    # -----------------------------------------------------
    if model_type == "ets":

        response_factors["ets"] = {
            "alpha": ets.get("alpha"),
            "beta": ets.get("beta"),
            "gamma": ets.get("gamma")
        }

    else:

        shared_growth_factors = {
            "total_growth": growth.get("total_growth"),
            "duration": growth.get("duration"),
            "trajectory_start": growth.get("trajectory_start")
        }

        response_factors["linear"] = {
            **shared_growth_factors
        }

        response_factors["exponential"] = {
            **shared_growth_factors,
            "k_value": growth.get("k_value")
        }

        response_factors["logarithmic"] = {
            **shared_growth_factors,
            "k_value": growth.get("k_value")
        }

        response_factors["scurve"] = {
            **shared_growth_factors,
            "k_value": growth.get("k_value")
        }

    return {
        "therapy_area": ta,
        "indication": indication_input,
        "scenario_name": scenario_name,
        "factors": response_factors,
        "metrics_data": {
            "nps": {
                "unit": "",
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": nps_series
                },
                "table": list(nps_table.values())
            },
            "market_share": {
                "unit": "%",
                "chart": {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "series": ms_chart_series
                },
                "table": list(ms_table.values())
            }
        }
    }

# =====================================================
# POST: SAVE CHANGES (UNCHANGED)
# =====================================================
# =====================================================
def build_patient_metrics(nps_values, market_share_values):
    return {
        "final_nps": [
            round(float(x or 0), 2)
            for x in nps_values
        ],
        "final_market_share": [
            round(float(x or 0), 2)
            for x in market_share_values
        ],
        "final_patient_share": [
            round(float(nps or 0) * (float(ms or 0) / 100), 2)
            for nps, ms in zip(nps_values, market_share_values)
        ]
    }

def normalize_market_share_table(
    market_share_table,
    selected_brand: str
):
    normalized_table = []

    for lot_group in market_share_table:
        lot = lot_group["lot"] if isinstance(lot_group, dict) else lot_group.lot
        children = lot_group["children"] if isinstance(lot_group, dict) else lot_group.children

        total_months = max(
            len(child["values"] if isinstance(child, dict) else child.values)
            for child in children
        )

        normalized_children = []

        for month_idx in range(total_months):

            edited_value = 0.0
            other_total = 0.0

            # -----------------------------
            # Get edited brand value and other brands total
            # -----------------------------
            for child in children:
                label = child["label"] if isinstance(child, dict) else child.label
                values = child["values"] if isinstance(child, dict) else child.values

                value = float(values[month_idx] or 0) if month_idx < len(values) else 0.0

                if label == selected_brand:
                    edited_value = value
                else:
                    other_total += value

            remaining_share = max(100.0 - edited_value, 0.0)

            # -----------------------------
            # Normalize each brand
            # -----------------------------
            month_values = {}

            for child in children:
                label = child["label"] if isinstance(child, dict) else child.label
                values = child["values"] if isinstance(child, dict) else child.values

                value = float(values[month_idx] or 0) if month_idx < len(values) else 0.0

                if label == selected_brand:
                    month_values[label] = round(edited_value, 2)
                else:
                    month_values[label] = (
                        round((value / other_total) * remaining_share, 2)
                        if other_total > 0
                        else 0.0
                    )

            if not normalized_children:
                for child in children:
                    label = child["label"] if isinstance(child, dict) else child.label
                    normalized_children.append({
                        "label": label,
                        "values": []
                    })

            for child in normalized_children:
                child["values"].append(month_values[child["label"]])

        normalized_table.append({
            "lot": lot,
            "total": [100.0] * total_months,
            "children": normalized_children
        })

    return normalized_table

@router.post("/metrics/refresh", tags=["Model_Input"])
def refresh_changes(payload: Refreshchangerequest):

    metric = payload.metric.lower()
    scenario_name = payload.scenario_name.strip()
    is_base_scenario = scenario_name.upper() == "BASE"
    # if payload.scenario_name.strip().upper() == "BASE":
    #     raise HTTPException(
    #         status_code=400,
    #         detail="BASE scenario is read-only. Please save the scenario with a new name before making changes."
    #     )

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
        cur.execute("""
            SELECT config
            FROM raw.forecast_configurations
            WHERE config->>'ta_name' = %s
        """, (payload.therapy_area,))

        row = cur.fetchone()

        if not row:
            raise HTTPException(400, "Forecast config not found")

        config = row[0]

    finally:
        cur.close()
        conn.close()

    forecast_periods = int(config["forecast_periods"])
    train_start_date = config["train_start_date"]

    # --------------------------------------------------
    # Find selected edited row
    # --------------------------------------------------
    product_values = None

    for lot_group in payload.table:
        if lot_group.lot.lower() != payload.lot.lower():
            continue

        if metric == "market_share":
            for child in lot_group.children:
                if child.label.lower() == payload.product.lower():
                    product_values = child.values
                    break
        else:
            if lot_group.children:
                product_values = lot_group.children[0].values

    if product_values is None:
        raise HTTPException(
            status_code=400,
            detail="Selected row not found in table"
        )

    train_len = len(product_values) - forecast_periods

    if train_len < 0:
        raise HTTPException(
            status_code=400,
            detail="Forecast periods exceed total values length"
        )

    # --------------------------------------------------
    # Build months
    # --------------------------------------------------
    train_start = datetime.fromisoformat(train_start_date).replace(day=1)

    train_months = [
        (train_start + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(train_len)
    ]

    if train_len > 0:
        last_train_month = datetime.fromisoformat(train_months[-1])
    else:
        last_train_month = train_start

    forecast_months = [
        (last_train_month + relativedelta(months=i)).strftime("%Y-%m-%d")
        for i in range(1, forecast_periods + 1)
    ]

    months = train_months + forecast_months
    forecast_start_index = train_len

    # --------------------------------------------------
    # Build selected metric chart
    # --------------------------------------------------
    selected_chart_series = []

    for lot_group in payload.table:
        lot_label = lot_group.lot

        if metric == "market_share" and lot_label.lower() != payload.lot.lower():
            continue

        for child in lot_group.children:
            values = child.values

            selected_chart_series.append({
                "lot": lot_label,
                "label": child.label,
                "train_values": values[:train_len],
                "forecast_values": values[train_len:]
            })

    # --------------------------------------------------
    # Normalize market share for response
    # --------------------------------------------------
    if metric == "market_share":
        normalized_market_share_table = normalize_market_share_table(
                    payload.table,
                    selected_brand=payload.product
                )

        selected_chart_series = []

        for lot_group in normalized_market_share_table:
            lot_label = lot_group["lot"]

            if lot_label.lower() != payload.lot.lower():
                continue

            for child in lot_group["children"]:
                values = child["values"]

                selected_chart_series.append({
                    "lot": lot_label,
                    "label": child["label"],
                    "train_values": values[:train_len],
                    "forecast_values": values[train_len:]
                })

        updated_metric_block = {
            "chart": {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "series": selected_chart_series
            },
            "table": normalized_market_share_table
        }

    else:
        updated_metric_block = {
            "chart": {
                "months": months,
                "forecast_start_index": forecast_start_index,
                "series": selected_chart_series
            },
            "table": payload.table
        }

    # --------------------------------------------------
    # Load other metric from DB - always required for response
    # --------------------------------------------------
    other_metric = "market_share" if metric == "nps" else "nps"

    conn = get_connection()
    cur = conn.cursor()

    try:
        if other_metric == "nps":
            cur.execute("""
                SELECT lot, chart
                FROM raw.forecast_scenarios
                WHERE scenario_name = %s
                  AND ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND metric = 'nps'
                ORDER BY lot
            """, (
                scenario_name,
                payload.therapy_area,
                payload.indication
            ))

            rows = cur.fetchall()

            other_series = []
            other_table = {}

            for lot, chart in rows:
                other_series.append({
                    "lot": lot,
                    "label": "NPS",
                    "train_values": chart["train_values"],
                    "forecast_values": chart["forecast_values"]
                })

                other_table.setdefault(lot, {
                    "lot": lot,
                    "total": [],
                    "children": []
                })["children"].append({
                    "label": "NPS",
                    "values": chart["train_values"] + chart["forecast_values"]
                })

        else:
            cur.execute("""
                SELECT lot, product, chart
                FROM raw.forecast_scenarios
                WHERE scenario_name = %s
                  AND ta_name = %s
                  AND LOWER(indication) = LOWER(%s)
                  AND metric = 'market_share'
                ORDER BY lot, product
            """, (
                scenario_name,
                payload.therapy_area,
                payload.indication
            ))

            rows = cur.fetchall()

            other_series = []
            other_table = {}

            for lot, product, chart in rows:

                if lot.lower() == payload.lot.lower():
                    other_series.append({
                        "lot": lot,
                        "label": product,
                        "train_values": chart["train_values"],
                        "forecast_values": chart["forecast_values"]
                    })

                other_table.setdefault(lot, {
                    "lot": lot,
                    "total": [100.0] * len(months),
                    "children": []
                })["children"].append({
                    "label": product,
                    "values": chart["train_values"] + chart["forecast_values"]
                })

    finally:
        cur.close()
        conn.close()

    other_metric_block = {
        "chart": {
            "months": months,
            "forecast_start_index": forecast_start_index,
            "series": other_series
        },
        "table": list(other_table.values())
    }

    # --------------------------------------------------
    # Final response
    # --------------------------------------------------
    if metric == "nps":
        metrics_data = {
            "nps": {
                "unit": "",
                **updated_metric_block
            },
            "market_share": {
                "unit": "%",
                **other_metric_block
            }
        }
    else:
        metrics_data = {
            "market_share": {
                "unit": "%",
                **updated_metric_block
            },
            "nps": {
                "unit": "",
                **other_metric_block
            }
        }

    # --------------------------------------------------
    # Save only for non-BASE scenarios
    # --------------------------------------------------
    if not is_base_scenario:

        # --------------------------------------------------
        # Save normalized market share values
        # --------------------------------------------------
        if metric == "market_share":

            conn = get_connection()
            cur = conn.cursor()

            try:
                market_share_table = metrics_data["market_share"]["table"]

                for lot_group in market_share_table:
                    lot = lot_group["lot"]
                    children = lot_group["children"]

                    for child in children:
                        product = child["label"]
                        values = child["values"]

                        chart_payload = {
                            "train_values": values[:train_len],
                            "forecast_values": values[train_len:]
                        }

                        table_payload = {
                            "lot": lot,
                            "total": [100.0] * len(values),
                            "children": [
                                {
                                    "label": product,
                                    "values": values
                                }
                            ]
                        }

                        cur.execute("""
                            UPDATE raw.forecast_scenarios
                            SET
                                chart = %s::jsonb,
                                table_data = %s::jsonb,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE scenario_name = %s
                              AND ta_name = %s
                              AND LOWER(indication) = LOWER(%s)
                              AND LOWER(lot) = LOWER(%s)
                              AND LOWER(metric) = 'market_share'
                              AND LOWER(product) = LOWER(%s)
                        """, (
                            json.dumps(chart_payload),
                            json.dumps(table_payload),
                            scenario_name,
                            payload.therapy_area,
                            payload.indication,
                            lot,
                            product
                        ))

                conn.commit()

            finally:
                cur.close()
                conn.close()

        # --------------------------------------------------
        # Save patient_metrics based on latest edited values
        # --------------------------------------------------
        nps_table = metrics_data["nps"]["table"]
        market_share_table = metrics_data["market_share"]["table"]

        nps_by_lot = {}

        for lot_group in nps_table:
            lot = lot_group["lot"] if isinstance(lot_group, dict) else lot_group.lot
            children = lot_group["children"] if isinstance(lot_group, dict) else lot_group.children

            if children:
                child = children[0]
                values = child["values"] if isinstance(child, dict) else child.values
                nps_by_lot[lot] = values

        conn = get_connection()
        cur = conn.cursor()

        try:
            for lot_group in market_share_table:

                lot = lot_group["lot"] if isinstance(lot_group, dict) else lot_group.lot
                children = lot_group["children"] if isinstance(lot_group, dict) else lot_group.children

                nps_values = nps_by_lot.get(lot)

                if not nps_values:
                    continue

                for child in children:

                    product = child["label"] if isinstance(child, dict) else child.label
                    ms_values = child["values"] if isinstance(child, dict) else child.values

                    patient_metrics = {
                        "final_nps": [
                            round(float(x or 0), 2)
                            for x in nps_values
                        ],
                        "final_market_share": [
                            round(float(x or 0), 2)
                            for x in ms_values
                        ],
                        "final_patient_share": [
                            round(
                                float(nps or 0) * (float(ms or 0) / 100),
                                2
                            )
                            for nps, ms in zip(nps_values, ms_values)
                        ]
                    }

                    cur.execute("""
                        UPDATE raw.forecast_scenarios
                        SET
                            patient_metrics = %s::jsonb,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE scenario_name = %s
                          AND ta_name = %s
                          AND LOWER(indication) = LOWER(%s)
                          AND LOWER(lot) = LOWER(%s)
                          AND LOWER(metric) = 'market_share'
                          AND LOWER(product) = LOWER(%s)
                    """, (
                        json.dumps(patient_metrics),
                        scenario_name,
                        payload.therapy_area,
                        payload.indication,
                        lot,
                        product
                    ))

            conn.commit()

        finally:
            cur.close()
            conn.close()

    return {
        "therapy_area": payload.therapy_area,
        "indication": payload.indication,
        "scenario_name": scenario_name,
        "metrics_data": metrics_data
    }

@router.post("/metrics/save",tags=["Model_Input"])
def save_scenario(payload: SaveScenarioRequest):

    # --------------------------------------------------
    # DO NOT ALLOW USER TO SAVE AS BASE
    # --------------------------------------------------
    if payload.scenario_name.strip().upper() == "BASE":
        raise HTTPException(
            status_code=400,
            detail="BASE scenario cannot be overwritten. Please save as a different scenario name."
        )

    conn = get_connection()
    cur = conn.cursor()

    saved_ids = []

    try:
        metrics_data = payload.metrics_data or {}

        # --------------------------------------------------
        # DO NOT ALLOW DUPLICATE SCENARIO NAME
        # --------------------------------------------------
        cur.execute("""
            SELECT COUNT(*)
            FROM raw.forecast_scenarios
            WHERE scenario_name = %s
              AND ta_name = %s
              AND LOWER(indication) = LOWER(%s)
        """, (
            payload.scenario_name,
            payload.ta_name,
            payload.indication
        ))

        existing_count = cur.fetchone()[0]

        if existing_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Scenario name already exists. Please use Update to overwrite this scenario or provide a new scenario name."
            )

        # ==================================================
        # SAVE NPS - ONE ROW PER LOT
        # ==================================================
        nps_block = metrics_data.get("nps")

        if nps_block:
            nps_chart = nps_block.get("chart", {}) or {}
            nps_table = nps_block.get("table", []) or []

            months = nps_chart.get("months", []) or []
            forecast_start_index = nps_chart.get("forecast_start_index", 0) or 0
            nps_series = nps_chart.get("series", []) or []

            for series in nps_series:
                lot = series.get("lot")

                if not lot:
                    continue

                row_chart = {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "train_values": series.get("train_values", []) or [],
                    "forecast_values": series.get("forecast_values", []) or []
                }

                row_table = [
                    t for t in nps_table
                    if str(t.get("lot", "")).lower().strip()
                    == str(lot).lower().strip()
                ]

                cur.execute("""
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
                """, (
                    payload.scenario_name,
                    payload.user_id,
                    payload.ta_name,
                    payload.indication,
                    lot,
                    "nps",
                    None,
                    payload.model_type,
                    json.dumps(payload.factors),
                    json.dumps(row_chart),
                    json.dumps(row_table),
                ))

                saved_ids.append(cur.fetchone()[0])
        # --------------------------------------------------
        # Prepare NPS values by LOT for patient_metrics
        # --------------------------------------------------
        nps_by_lot = {}

        if nps_block:
            nps_table = nps_block.get("table", []) or []

            for lot_group in nps_table:
                lot = lot_group.get("lot")
                children = lot_group.get("children", []) or []

                if lot and children:
                    nps_by_lot[
                        str(lot).lower().strip()
                    ] = children[0].get("values", []) or []
        # ==================================================
        # SAVE MARKET SHARE - ONE ROW PER LOT + PRODUCT
        # ==================================================
        ms_block = metrics_data.get("market_share")

        if ms_block:
            ms_chart = ms_block.get("chart", {}) or {}
            ms_table = ms_block.get("table", []) or []

            months = ms_chart.get("months", []) or []
            forecast_start_index = ms_chart.get("forecast_start_index", 0) or 0

            for lot_group in ms_table:
                lot = lot_group.get("lot")

                if not lot:
                    continue

                children = lot_group.get("children", []) or []

                for child in children:
                    product = child.get("label")
                    values = child.get("values", []) or []

                    if not product:
                        continue
                    nps_values = nps_by_lot.get(
                            str(lot).lower().strip(),
                            []
                        )

                    patient_metrics = None

                    if (
                        nps_values
                        and values
                        and len(nps_values) == len(values)
                    ):
                        patient_metrics = {
                            "final_nps": [
                                round(float(x or 0), 2)
                                for x in nps_values
                            ],
                            "final_market_share": [
                                round(float(x or 0), 2)
                                for x in values
                            ],
                            "final_patient_share": [
                                round(
                                    float(nps or 0) * (float(ms or 0) / 100),
                                    2
                                )
                                for nps, ms in zip(nps_values, values)
                            ]
                        }
                    row_chart = {
                        "months": months,
                        "forecast_start_index": forecast_start_index,
                        "train_values": values[:forecast_start_index],
                        "forecast_values": values[forecast_start_index:]
                    }

                    row_table = [{
                        "lot": lot,
                        "total": lot_group.get("total", []) or [],
                        "children": [child]
                    }]

                    cur.execute("""
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
                                table_data,
                                patient_metrics
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (
                            payload.scenario_name,
                            payload.user_id,
                            payload.ta_name,
                            payload.indication,
                            lot,
                            "market_share",
                            product,
                            payload.model_type,
                            json.dumps(payload.factors),
                            json.dumps(row_chart),
                            json.dumps(row_table),
                            json.dumps(patient_metrics) if patient_metrics else None,
                        ))

                    saved_ids.append(cur.fetchone()[0])

        if not saved_ids:
            raise HTTPException(
                status_code=400,
                detail="No scenario data found to save."
            )

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()

    return {
        "scenario_name": payload.scenario_name,
        "saved_rows": len(saved_ids),
        "scenario_ids": [f"SCN_{sid}" for sid in saved_ids],
        "message": "Scenario saved successfully"
    }

@router.put("/update-scenario",tags=["Model_Input"])
def update_scenario(payload: UpdateScenarioRequest):

    # --------------------------------------------------
    # BASE SCENARIO CANNOT BE UPDATED
    # --------------------------------------------------
    # if payload.scenario_name.strip().upper() == "BASE":
    #     raise HTTPException(
    #         status_code=400,
    #         detail="BASE scenario cannot be updated. Please create a new scenario."
    #     )

    conn = get_connection()
    cur = conn.cursor()

    saved_ids = []

    try:
        metrics_data = payload.metrics_data or {}

        # --------------------------------------------------
        # CHECK SCENARIO EXISTS
        # --------------------------------------------------
        cur.execute("""
            SELECT COUNT(*)
            FROM raw.forecast_scenarios
            WHERE scenario_name = %s
              AND ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND scenario_name <> 'BASE'
        """, (
            payload.scenario_name,
            payload.ta_name,
            payload.indication
        ))

        scenario_exists = cur.fetchone()[0]

        if scenario_exists == 0:
            raise HTTPException(
                status_code=400,
                detail="Scenario does not exist. Please use Save Scenario to create a new scenario first."
            )

        # --------------------------------------------------
        # DELETE OLD SCENARIO SNAPSHOT
        # --------------------------------------------------
        cur.execute("""
            DELETE FROM raw.forecast_scenarios
            WHERE scenario_name = %s
              AND ta_name = %s
              AND LOWER(indication) = LOWER(%s)
              AND scenario_name <> 'BASE'
        """, (
            payload.scenario_name,
            payload.ta_name,
            payload.indication
        ))

        # ==================================================
        # INSERT NPS - ONE ROW PER LOT
        # ==================================================
        nps_block = metrics_data.get("nps")

        if nps_block:
            nps_chart = nps_block.get("chart", {}) or {}
            nps_table = nps_block.get("table", []) or []

            months = nps_chart.get("months", []) or []
            forecast_start_index = nps_chart.get("forecast_start_index", 0) or 0
            nps_series = nps_chart.get("series", []) or []

            for series in nps_series:
                lot = series.get("lot")

                if not lot:
                    continue

                row_chart = {
                    "months": months,
                    "forecast_start_index": forecast_start_index,
                    "train_values": series.get("train_values", []) or [],
                    "forecast_values": series.get("forecast_values", []) or []
                }

                row_table = [
                    t for t in nps_table
                    if str(t.get("lot", "")).lower().strip()
                    == str(lot).lower().strip()
                ]

                cur.execute("""
                    INSERT INTO raw.forecast_scenarios (
                        scenario_name,
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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    payload.scenario_name,
                    payload.ta_name,
                    payload.indication,
                    lot,
                    "nps",
                    None,
                    payload.model_type,
                    json.dumps(payload.factors),
                    json.dumps(row_chart),
                    json.dumps(row_table),
                ))

                saved_ids.append(cur.fetchone()[0])
        # --------------------------------------------------
        # Prepare NPS values by LOT for patient_metrics
        # --------------------------------------------------
        nps_by_lot = {}

        if nps_block:
            nps_table = nps_block.get("table", []) or []

            for lot_group in nps_table:
                lot = lot_group.get("lot")
                children = lot_group.get("children", []) or []

                if lot and children:
                    nps_by_lot[
                        str(lot).lower().strip()
                    ] = children[0].get("values", []) or []
        # ==================================================
        # INSERT MARKET SHARE - ONE ROW PER LOT + PRODUCT
        # ==================================================
        ms_block = metrics_data.get("market_share")

        if ms_block:
            ms_chart = ms_block.get("chart", {}) or {}
            ms_table = ms_block.get("table", []) or []

            months = ms_chart.get("months", []) or []
            forecast_start_index = ms_chart.get("forecast_start_index", 0) or 0

            for lot_group in ms_table:
                lot = lot_group.get("lot")

                if not lot:
                    continue

                children = lot_group.get("children", []) or []

                for child in children:
                    product = child.get("label")
                    values = child.get("values", []) or []

                    if not product:
                        continue
                    nps_values = nps_by_lot.get(
                        str(lot).lower().strip(),
                        []
                    )

                    patient_metrics = None

                    if (
                        nps_values
                        and values
                        and len(nps_values) == len(values)
                    ):

                        patient_metrics = {
                            "final_nps": [
                                round(float(x or 0), 2)
                                for x in nps_values
                            ],

                            "final_market_share": [
                                round(float(x or 0), 2)
                                for x in values
                            ],

                            "final_patient_share": [
                                round(
                                    float(nps or 0)
                                    * (float(ms or 0) / 100),
                                    2
                                )
                                for nps, ms in zip(
                                    nps_values,
                                    values
                                )
                            ]
                        }
                    row_chart = {
                        "months": months,
                        "forecast_start_index": forecast_start_index,
                        "train_values": values[:forecast_start_index],
                        "forecast_values": values[forecast_start_index:]
                    }

                    row_table = [{
                        "lot": lot,
                        "total": lot_group.get("total", []) or [],
                        "children": [child]
                    }]

                    cur.execute("""
                        INSERT INTO raw.forecast_scenarios (
                            scenario_name,
                            ta_name,
                            indication,
                            lot,
                            metric,
                            product,
                            model_type,
                            factors,
                            chart,
                            table_data,
                            patient_metrics
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
                        RETURNING id
                    """, (
                        payload.scenario_name,
                        payload.ta_name,
                        payload.indication,
                        lot,
                        "market_share",
                        product,
                        payload.model_type,
                        json.dumps(payload.factors),
                        json.dumps(row_chart),
                        json.dumps(row_table),
                        json.dumps(patient_metrics)
                            if patient_metrics else None,
                    ))

                    saved_ids.append(cur.fetchone()[0])

        if not saved_ids:
            raise HTTPException(
                status_code=400,
                detail="No scenario data found to update."
            )

        conn.commit()

    except HTTPException:
        conn.rollback()
        raise

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()

    return {
    "therapy_area": payload.ta_name,
    "indication": payload.indication,
    "lot": payload.lot,
    "metric": payload.metric,
    "product": payload.product,
    "scenario_name": payload.scenario_name,
    "updated_rows": len(saved_ids),
    "scenario_ids": [f"SCN_{sid}" for sid in saved_ids],
    "factors": payload.factors,
    "metrics_data": {
        "nps": {
            "unit": "",
            **(payload.metrics_data.get("nps", {}) if payload.metrics_data else {})
        },
        "market_share": {
            "unit": "%",
            **(payload.metrics_data.get("market_share", {}) if payload.metrics_data else {})
        }
    },
    "message": "Scenario updated successfully"
}