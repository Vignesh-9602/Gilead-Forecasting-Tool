from app.db.connection import get_connection
from app.services.growth_forecast_service import process_growth_forecast
from app.services.forecast_service import process_forecast


# -----------------------------------
# HELPERS
# -----------------------------------

def _payer_filter(val) -> bool:
    if not val:
        return False
    if isinstance(val, list):
        return val and val != ["All"] and "All" not in val
    return val != "All"


def _to_list(val) -> list:
    return val if isinstance(val, list) else [val]


def normalize_shares(values):
    total = sum(values)
    if total == 0:
        return values
    return [(v * 100.0) / total for v in values]


# -----------------------------------
# TOTAL MARKET VOLUME (Monthly)
# -----------------------------------

def get_total_market_volume(
    cur,
    ta,
    from_year,
    from_month,
    to_year,
    to_month,
    market=None
):

    if _payer_filter(market):
        cur.execute("""
            SELECT year, month, SUM(volume)
            FROM raw_hiv_treat.volume
            WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
              AND market = ANY(%s::text[])
              AND (year * 100 + month)
                  BETWEEN (%s * 100 + %s)
                      AND (%s * 100 + %s)
            GROUP BY year, month
            ORDER BY year, month
        """, (ta, _to_list(market), from_year, from_month, to_year, to_month))

    else:
        cur.execute("""
            SELECT year, month, SUM(volume)
            FROM raw_hiv_treat.volume
            WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
              AND (year * 100 + month)
                  BETWEEN (%s * 100 + %s)
                      AND (%s * 100 + %s)
            GROUP BY year, month
            ORDER BY year, month
        """, (ta, from_year, from_month, to_year, to_month))

    return cur.fetchall()


# -----------------------------------
# PRODUCT DISTRIBUTION
# -----------------------------------

def get_product_distribution(
    cur,
    ta,
    from_year,
    from_month,
    to_year,
    to_month,
    product="All",
    metric="market_volume"
):

    base_query = """
        SELECT year, month, product, volume, distribution_pct
        FROM (
            SELECT year, month, product,
                   SUM(volume) AS volume,
                   ROUND(
                       SUM(volume) * 100.0 /
                       NULLIF(SUM(SUM(volume)) OVER (PARTITION BY year, month), 0),
                       2
                   ) AS distribution_pct
            FROM raw_hiv_treat.volume
            WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
              AND (year * 100 + month)
                  BETWEEN (%s * 100 + %s)
                      AND (%s * 100 + %s)
            GROUP BY year, month, product
        ) agg
        {product_filter}
        ORDER BY product, year, month
    """

    if product != "All":
        cur.execute(
            base_query.format(product_filter="WHERE product = %s"),
            (ta, from_year, from_month, to_year, to_month, product)
        )
    else:
        cur.execute(
            base_query.format(product_filter=""),
            (ta, from_year, from_month, to_year, to_month)
        )

    rows = cur.fetchall()
    col_idx = 4 if metric == "market_share" else 3

    return [(r[0], r[1], r[2], float(r[col_idx])) for r in rows]


# -----------------------------------
# MARKET DISTRIBUTION
# -----------------------------------

def get_market_distribution(
    cur,
    ta,
    from_year,
    from_month,
    to_year,
    to_month,
    market=None,
    metric="market_volume"
):
    query = """
        SELECT year,
               month,
               market,
               source_of_market,
               SUM(volume) AS volume
        FROM raw_hiv_treat.volume
        WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
          AND (year * 100 + month)
              BETWEEN (%s * 100 + %s)
                  AND (%s * 100 + %s)
        GROUP BY year, month, market, source_of_market
        ORDER BY market, source_of_market, year, month
    """

    cur.execute(query, (ta, from_year, from_month, to_year, to_month))
    rows = cur.fetchall()

    results = []

    month_totals = {}
    for y, m, market, source, volume in rows:
        month_totals[(y, m)] = month_totals.get((y, m), 0) + float(volume)

    for y, m, market, source, volume in rows:
        if metric == "market_share":
            share = round((float(volume) * 100) / month_totals[(y, m)], 2)
            results.append((y, m, market, source, share))
        else:
            results.append((y, m, market, source, float(volume)))

    return results


# -----------------------------------
# MARKET → PRODUCT (FIXED HIERARCHY)
# -----------------------------------

def get_market_wise_product(
    cur,
    ta,
    from_year,
    from_month,
    to_year,
    to_month,
    market=None,
    metric="market_volume"
):
    query = """
        SELECT year,
               month,
               market,
               source_of_market,
               product,
               SUM(volume) AS volume
        FROM raw_hiv_treat.volume
        WHERE LOWER(TRIM(ta)) = LOWER(TRIM(%s))
          AND (year * 100 + month)
              BETWEEN (%s * 100 + %s)
                  AND (%s * 100 + %s)
        GROUP BY year, month, market, source_of_market, product
        ORDER BY market, source_of_market, product, year, month
    """

    cur.execute(query, (ta, from_year, from_month, to_year, to_month))
    rows = cur.fetchall()

    results = []

    group_totals = {}
    for y, m, market, source, product, volume in rows:
        key = (y, m, market, source)
        group_totals[key] = group_totals.get(key, 0) + float(volume)

    for y, m, market, source, product, volume in rows:
        key = (y, m, market, source)

        if metric == "market_share":
            share = round((float(volume) * 100) / group_totals[key], 2)
            results.append((y, m, market, source, product, share))
        else:
            results.append((y, m, market, source, product, float(volume)))

    return results


# -----------------------------------
# GROWTH ESTIMATION (FIXED)
# -----------------------------------

def estimate_growth_pct(series_values, metric="market_volume"):

    if len(series_values) < 3:
        return 0.0

    growth_rates = []

    for i in range(1, len(series_values)):
        prev = series_values[i - 1]
        curr = series_values[i]

        if metric == "market_share":
            growth_rates.append(curr - prev)
        else:
            if prev == 0:
                continue
            growth_rates.append((curr - prev) / prev)

    if not growth_rates:
        return 0.0

    g6 = sum(growth_rates[-6:]) / min(6, len(growth_rates))
    g12 = sum(growth_rates[-12:]) / min(12, len(growth_rates))

    final_growth = (0.7 * g6) + (0.3 * g12)

    # Clamp volatility
    if metric == "market_volume":
        final_growth = max(min(final_growth, 0.20), -0.20)
    else:
        final_growth = max(min(final_growth, 5), -5)

    return round(final_growth * 100, 2) if metric == "market_volume" else round(final_growth, 2)


# -----------------------------------
# AUTO FORECAST WRAPPER
# -----------------------------------

def process_growth_forecast_auto(
    series_months,
    series_values,
    train_start_date,
    train_end_date,
    forecast_periods,
    metric="market_share",
    growth_type="linear"
):

    if growth_type == "ets":
        return process_forecast(
            series_months=series_months,
            series_values=series_values,
            train_start_date=train_start_date,
            train_end_date=train_end_date,
            forecast_periods=forecast_periods,
            metric=metric
        )

    total_growth = estimate_growth_pct(series_values, metric=metric)

    result = process_growth_forecast(
        series_months=series_months,
        series_values=series_values,
        train_start_date=train_start_date,
        train_end_date=train_end_date,
        forecast_periods=forecast_periods,
        multiplier=1.0,
        total_growth=total_growth,
        duration=forecast_periods,
        growth_type=growth_type,
        metric=metric
    )


    return result