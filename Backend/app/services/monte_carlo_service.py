import numpy as np
from scipy.stats import truncnorm

from app.db.connection import get_connection
from app.schemas.monte_carlo_schema import MonteCarloRunRequest


def _ensure_prefs_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS raw.monte_carlo_preferences (
            user_id             TEXT NOT NULL,
            ta_name             TEXT NOT NULL,
            brand               TEXT,
            confidence_interval FLOAT,
            n_iterations        INT,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, ta_name)
        )
    """)


def get_saved_monte_carlo_filter(cur, user_id: str, ta_name: str):
    _ensure_prefs_table(cur)

    cur.execute("""
        SELECT brand, confidence_interval, n_iterations
        FROM raw.monte_carlo_preferences
        WHERE user_id = %s AND ta_name = %s
    """, (user_id, ta_name))

    row = cur.fetchone()
    if not row:
        return None

    return {
        "brand":               row[0] or "All Brands",
        "confidence_interval": float(row[1]) if row[1] is not None else 0.90,
        "n_iterations":        int(row[2])   if row[2] is not None else 1000,
    }


def save_monte_carlo_filter(cur, user_id: str, ta_name: str, payload: MonteCarloRunRequest):
    _ensure_prefs_table(cur)

    cur.execute("""
        INSERT INTO raw.monte_carlo_preferences (
            user_id, ta_name, brand, confidence_interval, n_iterations, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, ta_name)
        DO UPDATE SET
            brand               = EXCLUDED.brand,
            confidence_interval = EXCLUDED.confidence_interval,
            n_iterations        = EXCLUDED.n_iterations,
            updated_at          = CURRENT_TIMESTAMP
    """, (user_id, ta_name, payload.brand, payload.confidence_interval, payload.n_iterations))


def get_monte_carlo_filters(ta_name: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT brand
            FROM raw.persistency_outputs
            WHERE ta_name = %s
            ORDER BY brand
            """,
            (ta_name,)
        )
        brands = [row[0] for row in cur.fetchall()]

        confidence_interval_options = [
            {"label": "Narrow (80%)", "value": 0.80},
            {"label": "Standard (90%)", "value": 0.90},
            {"label": "Wide (95%)",     "value": 0.95},
        ]

        default_brand = brands[0] if brands else "All Brands"

        saved = get_saved_monte_carlo_filter(cur, "system", ta_name)
        conn.commit()

        if saved:
            selected_filter = {
                "brand":               saved["brand"] if (saved["brand"] in brands or saved["brand"] == "All Brands") else default_brand,
                "confidence_interval": saved["confidence_interval"],
                "n_iterations":        saved["n_iterations"],
            }
        else:
            selected_filter = {
                "brand":               default_brand,
                "confidence_interval": 0.90,
                "n_iterations":        1000,
            }

        return {
            "brands":                      brands,
            "confidence_interval_options": confidence_interval_options,
            "selected_filter":             selected_filter,
        }
    finally:
        cur.close()
        conn.close()


def _load_simulation_inputs(cur, ta_name: str, brand: str) -> tuple:
    """
    Returns (months, base_demand, db_price, comp_mean) where:
      base_demand[i] = SUM(final_demand) from raw.revenue_output per month
      db_price       = AVG(net_price)   from raw.revenue_output
      comp_mean      = AVG(compliance)  from raw.vials_assumptions (0-1 scale)
    """
    # ------------------------------------------------------------------
    # 1. Demand + Price from raw.revenue_output
    # ------------------------------------------------------------------
    if brand == "All Brands":
        cur.execute(
            """
            SELECT month_date, SUM(final_demand), AVG(net_price)
            FROM raw.revenue_outputs
            WHERE ta_name = %s
            GROUP BY month_date
            ORDER BY month_date
            """,
            (ta_name,)
        )
    else:
        cur.execute(
            """
            SELECT month_date, SUM(final_demand), AVG(net_price)
            FROM raw.revenue_outputs
            WHERE ta_name = %s AND brand = %s
            GROUP BY month_date
            ORDER BY month_date
            """,
            (ta_name, brand)
        )

    revenue_rows = cur.fetchall()

    if not revenue_rows:
        raise ValueError(
            "No revenue output data found for this TA/brand. "
            "Run the Net Revenue calculation first."
        )

    months       = [r[0].strftime("%Y-%m-%d") for r in revenue_rows]
    base_demand  = [float(r[1]) if r[1] is not None else 0.0 for r in revenue_rows]
    price_values = [float(r[2]) for r in revenue_rows if r[2] is not None]
    db_price     = float(np.mean(price_values)) if price_values else 0.0

    # ------------------------------------------------------------------
    # 2. Compliance from raw.vials_assumptions
    # ------------------------------------------------------------------
    if brand == "All Brands":
        cur.execute(
            """
            SELECT AVG(compliance)
            FROM raw.vials_assumptions
            WHERE ta_name = %s
            """,
            (ta_name,)
        )
    else:
        cur.execute(
            """
            SELECT AVG(compliance)
            FROM raw.vials_assumptions
            WHERE ta_name = %s AND brand = %s
            """,
            (ta_name, brand)
        )

    comp_row = cur.fetchone()
    raw_comp  = comp_row[0] if comp_row and comp_row[0] is not None else None

    # compliance stored as 0–100 in DB → convert to 0–1
    comp_mean = float(raw_comp) / 100.0 if raw_comp is not None else 0.85

    return months, base_demand, db_price, comp_mean


def run_monte_carlo_simulation(payload: MonteCarloRunRequest) -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        _, base_demand, db_price, db_comp_mean = _load_simulation_inputs(
            cur, payload.ta_name, payload.brand
        )

        n        = payload.n_iterations
        base_arr = np.array(base_demand, dtype=float)

        # ------------------------------------------------------------------
        # 1. Demand Base Mean
        # ------------------------------------------------------------------
        if payload.demand_params and payload.demand_params.base_mean is not None:
            base_arr              = np.full_like(base_arr, payload.demand_params.base_mean)
            demand_base_mean_used = float(payload.demand_params.base_mean)
        else:
            demand_base_mean_used = float(np.mean(base_arr)) if len(base_arr) > 0 else 0.0

        # ------------------------------------------------------------------
        # 2. Demand STD DEV
        # ------------------------------------------------------------------
        if payload.demand_params and payload.demand_params.std_pct is not None:
            demand_std             = base_arr * (payload.demand_params.std_pct / 100.0)
            demand_volatility_used = float(payload.demand_params.std_pct)
        else:
            demand_std = np.sqrt(np.where(base_arr > 0, base_arr, 1e-9))
            nonzero_mask = base_arr > 0
            demand_volatility_used = float(
                np.mean(demand_std[nonzero_mask] / base_arr[nonzero_mask]) * 100
            ) if nonzero_mask.any() else 0.0

        # ------------------------------------------------------------------
        # 3. Compliance Base Mean
        # ------------------------------------------------------------------
        if payload.compliance_params and payload.compliance_params.mean is not None:
            comp_mean = payload.compliance_params.mean
        else:
            comp_mean = db_comp_mean

        # ------------------------------------------------------------------
        # 4. Compliance STD DEV
        # ------------------------------------------------------------------
        if payload.compliance_params and payload.compliance_params.std is not None:
            comp_std = payload.compliance_params.std
        else:
            comp_std = 0.05

        # ------------------------------------------------------------------
        # 5. Price per vial
        # ------------------------------------------------------------------
        if payload.pricing_params and payload.pricing_params.price_per_vial is not None:
            price = payload.pricing_params.price_per_vial
        else:
            price = db_price

        pricing_std_used = payload.pricing_params.std if payload.pricing_params else 0.0

        # ------------------------------------------------------------------
        # Sample demand: shape (n_iterations, n_months)
        # ------------------------------------------------------------------
        sampled_demand = np.random.normal(loc=base_arr, scale=demand_std, size=(n, len(base_arr)))
        sampled_demand = np.maximum(sampled_demand, 0.0)
        total_demand_per_iter = sampled_demand.sum(axis=1)

        # ------------------------------------------------------------------
        # Sample compliance: one draw per iteration from Truncated Normal [0,1]
        # ------------------------------------------------------------------
        a_comp = (0.0 - comp_mean) / comp_std
        b_comp = (1.0 - comp_mean) / comp_std
        sampled_compliance = truncnorm.rvs(a_comp, b_comp, loc=comp_mean, scale=comp_std, size=n)

        # ------------------------------------------------------------------
        # Revenue = total_demand × compliance × price_per_vial
        # ------------------------------------------------------------------
        revenues = total_demand_per_iter * sampled_compliance * price

        mean_r   = float(np.mean(revenues))
        median_r = float(np.median(revenues))
        std_r    = float(np.std(revenues))
        min_r    = float(revenues.min())
        max_r    = float(revenues.max())
        p5       = float(np.percentile(revenues, 5))
        p25      = float(np.percentile(revenues, 25))
        p75      = float(np.percentile(revenues, 75))
        p95      = float(np.percentile(revenues, 95))

        counts, bin_edges = np.histogram(revenues, bins=15)

        def fmt_m(v: float) -> str:
            return f"{v / 1_000_000:.1f}M"

        histogram = [
            {
                "range": f"{fmt_m(bin_edges[i])}-{fmt_m(bin_edges[i + 1])}",
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]

        # Peak bar: find the highest bin, then average demand/compliance
        # for only the iterations that landed in that bin's revenue range
        peak_idx = int(np.argmax(counts))
        peak_lo  = bin_edges[peak_idx]
        peak_hi  = bin_edges[peak_idx + 1]

        # Last bin is closed on both sides in np.histogram
        if peak_idx == len(counts) - 1:
            peak_mask = (revenues >= peak_lo) & (revenues <= peak_hi)
        else:
            peak_mask = (revenues >= peak_lo) & (revenues < peak_hi)

        peak_demand     = float(np.mean(total_demand_per_iter[peak_mask])) if peak_mask.any() else 0.0
        peak_compliance = float(np.mean(sampled_compliance[peak_mask]))    if peak_mask.any() else 0.0

        result = {
            "histogram": histogram,
            "summary": {
                "number_of_simulations": n,
                "mean_revenue":          mean_r,
                "median_revenue":        median_r,
                "std_dev_revenue":       std_r,
                "min_revenue":           min_r,
                "max_revenue":           max_r,
                "percentile_5":          p5,
                "percentile_25":         p25,
                "percentile_75":         p75,
                "percentile_95":         p95,
                "peak_bar": {
                    "revenue_range":   f"{fmt_m(peak_lo)}-{fmt_m(peak_hi)}",
                    "mean_demand":     peak_demand,
                    "mean_compliance": peak_compliance,
                    "price_per_vial":  price,
                },
            },
            "input_parameters": {
                "demand_base_mean":      demand_base_mean_used,
                "demand_volatility":     demand_volatility_used,
                "compliance_mean":       comp_mean,
                "compliance_volatility": comp_std,
                "price_per_vial":        price,
                "pricing_std":           pricing_std_used,
            },
        }

        # Save the filter so revisits restore the same selections
        save_monte_carlo_filter(cur, "system", payload.ta_name, payload)
        conn.commit()

        return result

    finally:
        cur.close()
        conn.close()
