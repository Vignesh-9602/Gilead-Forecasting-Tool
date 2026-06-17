import numpy as np
from scipy.stats import truncnorm

from app.db.connection import get_connection
from app.schemas.monte_carlo_schema import MonteCarloRunRequest


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

        return {
            "brands": brands,
            "confidence_interval_options": [
                {"label": "Narrow (80%)", "value": 0.80},
                {"label": "Standard (90%)", "value": 0.90},
                {"label": "Wide (95%)",    "value": 0.95},
            ],
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

    # month_date is a Python date object from psycopg2 — convert to "YYYY-MM-DD" string
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
    raw_comp = comp_row[0] if comp_row and comp_row[0] is not None else None

    # compliance stored as 0–100 in DB → convert to 0–1
    comp_mean = float(raw_comp) / 100.0 if raw_comp is not None else 0.85

    return months, base_demand, db_price, comp_mean


def run_monte_carlo_simulation(payload: MonteCarloRunRequest) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        months, base_demand, db_price, db_comp_mean = _load_simulation_inputs(cur, payload.ta_name, payload.brand)
    finally:
        cur.close()
        conn.close()

    n        = payload.n_iterations
    base_arr = np.array(base_demand, dtype=float)

    # ------------------------------------------------------------------
    # 1. Demand Base Mean
    #    Override: user provides a single value used for all months
    #    Auto:     dynamic per month from DB (base_arr as-is)
    # ------------------------------------------------------------------
    if payload.demand_params and payload.demand_params.base_mean is not None:
        base_arr               = np.full_like(base_arr, payload.demand_params.base_mean)
        demand_base_mean_used  = float(payload.demand_params.base_mean)
    else:
        # Return the average monthly demand so the modal can show a real number
        demand_base_mean_used  = float(np.mean(base_arr)) if len(base_arr) > 0 else 0.0

    # ------------------------------------------------------------------
    # 2. Demand STD DEV
    #    Override: user provides std_pct (as % of mean)
    #    Auto:     Poisson — std = sqrt(mean) per month
    # ------------------------------------------------------------------
    if payload.demand_params and payload.demand_params.std_pct is not None:
        demand_std            = base_arr * (payload.demand_params.std_pct / 100.0)
        demand_volatility_used = float(payload.demand_params.std_pct)
    else:
        demand_std = np.sqrt(np.where(base_arr > 0, base_arr, 1e-9))
        nonzero_mask = base_arr > 0
        demand_volatility_used = float(
            np.mean(demand_std[nonzero_mask] / base_arr[nonzero_mask]) * 100
        ) if nonzero_mask.any() else 0.0

    # ------------------------------------------------------------------
    # 3. Compliance Base Mean
    #    Override: user provides mean value
    #    Auto:     calculated from DB (fact_vials_compliance)
    # ------------------------------------------------------------------
    if payload.compliance_params and payload.compliance_params.mean is not None:
        comp_mean = payload.compliance_params.mean
    else:
        comp_mean = db_comp_mean

    # ------------------------------------------------------------------
    # 4. Compliance STD DEV
    #    Override: user provides std
    #    Auto:     default 0.05
    # ------------------------------------------------------------------
    if payload.compliance_params and payload.compliance_params.std is not None:
        comp_std = payload.compliance_params.std
    else:
        comp_std = 0.05

    # ------------------------------------------------------------------
    # 5. Price per vial
    #    Override: user provides price
    #    Auto:     0.0 (no price set — revenue will be 0)
    # ------------------------------------------------------------------
    if payload.pricing_params and payload.pricing_params.price_per_vial is not None:
        price = payload.pricing_params.price_per_vial
    else:
        price = db_price

    # 6. Pricing STD DEV — always 0 (Fixed distribution, never sampled)
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

    # Statistics
    mean_r   = float(np.mean(revenues))
    median_r = float(np.median(revenues))
    std_r    = float(np.std(revenues))
    min_r    = float(revenues.min())
    max_r    = float(revenues.max())
    p5       = float(np.percentile(revenues, 5))
    p25      = float(np.percentile(revenues, 25))
    p75      = float(np.percentile(revenues, 75))
    p95      = float(np.percentile(revenues, 95))

    # Histogram (15 equal-width bins)
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

    return {
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
