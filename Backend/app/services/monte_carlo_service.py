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


def _load_base_demand(cur, ta_name: str, brand: str) -> tuple:
    """
    Returns (months, base_demand, comp_mean) where:
      base_demand[i] = sum over all (brand, indication, lot) of
                       total_patients[i] * avg_vials_per_dose[i]
      comp_mean      = average compliance from raw.fact_vials_compliance (0-1 scale)

    Compliance mean is read from DB so the simulation is grounded in real data.
    Compliance std and demand std_pct remain user-controlled since the DB
    has no historical variation to derive them from.
    """
    if brand == "All Brands":
        cur.execute(
            """
            SELECT brand, indication, lot, months, total_patients
            FROM raw.persistency_outputs
            WHERE ta_name = %s
            ORDER BY brand, indication, lot
            """,
            (ta_name,)
        )
    else:
        cur.execute(
            """
            SELECT brand, indication, lot, months, total_patients
            FROM raw.persistency_outputs
            WHERE ta_name = %s AND brand = %s
            ORDER BY indication, lot
            """,
            (ta_name, brand)
        )

    rows = cur.fetchall()

    if not rows:
        raise ValueError(
            "No persistency data found for this TA/brand. "
            "Complete the persistency calculation step first."
        )

    # Build a unified sorted month list from ALL rows so every row
    # contributes regardless of its own date range.
    all_months_set = set()
    for _, _, _, row_months, _ in rows:
        all_months_set.update(row_months)
    months = sorted(all_months_set)

    # month → position index for O(1) lookup
    month_to_idx = {m: i for i, m in enumerate(months)}
    base_demand = [0.0] * len(months)

    all_compliance_values = []

    for row_brand, indication, lot, row_months, total_patients in rows:
        cur.execute(
            """
            SELECT year, month, avg_vials_per_dose, compliance
            FROM raw.fact_vials_compliance
            WHERE ta = %s AND indication = %s AND lot = %s AND brand = %s
            ORDER BY year, month
            """,
            (ta_name, indication, lot, row_brand)
        )

        vials_rows = cur.fetchall()
        avg_vials_map: dict = {}
        latest_avg: float = 0.0

        for yr, mo, avg_v, comp in vials_rows:
            key = f"{int(yr)}-{int(mo):02d}-01"
            avg_vials_map[key] = float(avg_v)
            latest_avg = float(avg_v)
            # compliance stored as 0-100 in DB, convert to 0-1
            all_compliance_values.append(float(comp) / 100.0)

        # Align by month string — not by position — so mismatched
        # date ranges across rows don't cause index errors.
        for j, row_month in enumerate(row_months):
            if j >= len(total_patients):
                break
            if row_month not in month_to_idx:
                continue
            idx = month_to_idx[row_month]
            avg_v = avg_vials_map.get(row_month, latest_avg)
            base_demand[idx] += float(total_patients[j]) * avg_v

    # Calculate compliance mean from DB history.
    # Fallback to 0.85 if no compliance data found.
    comp_mean = float(np.mean(all_compliance_values)) if all_compliance_values else 0.85

    return months, base_demand, comp_mean


def run_monte_carlo_simulation(payload: MonteCarloRunRequest) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        months, base_demand, comp_mean = _load_base_demand(cur, payload.ta_name, payload.brand)
    finally:
        cur.close()
        conn.close()

    n     = payload.n_iterations
    price = payload.pricing_params.price_per_vial

    base_arr = np.array(base_demand, dtype=float)

    # ------------------------------------------------------------------
    # Demand std — auto-calculate using Poisson (std = sqrt(mean))
    # or use user override if demand_params.std_pct was sent.
    # Poisson is the standard assumption for count data (vials).
    # ------------------------------------------------------------------
    if payload.demand_params and payload.demand_params.std_pct is not None:
        demand_std = base_arr * (payload.demand_params.std_pct / 100.0)
        demand_volatility_used = float(payload.demand_params.std_pct)
    else:
        demand_std = np.sqrt(np.where(base_arr > 0, base_arr, 1e-9))
        # Report back effective std_pct for the modal (std/mean × 100)
        nonzero_mask = base_arr > 0
        if nonzero_mask.any():
            demand_volatility_used = float(
                np.mean(demand_std[nonzero_mask] / base_arr[nonzero_mask]) * 100
            )
        else:
            demand_volatility_used = 0.0

    # ------------------------------------------------------------------
    # Compliance std — use user override or default to 0.05
    # ------------------------------------------------------------------
    if payload.compliance_params and payload.compliance_params.std is not None:
        comp_std = payload.compliance_params.std
    else:
        comp_std = 0.05

    # ------------------------------------------------------------------
    # Sample demand: shape (n_iterations, n_months)
    # Each month is drawn from Normal(base_demand[m], std[m]) independently.
    # ------------------------------------------------------------------
    sampled_demand = np.random.normal(loc=base_arr, scale=demand_std, size=(n, len(base_arr)))
    sampled_demand = np.maximum(sampled_demand, 0.0)

    # Total demand across all months, per iteration: shape (n_iterations,)
    total_demand_per_iter = sampled_demand.sum(axis=1)

    # ------------------------------------------------------------------
    # Sample compliance: one draw per iteration from Truncated Normal [0, 1]
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
            "demand_volatility":     demand_volatility_used,
            "compliance_mean":       comp_mean,
            "compliance_volatility": comp_std,
        },
    }
