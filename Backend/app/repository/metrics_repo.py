from app.db.connection import get_connection

def get_oncology_metrics(ta,start_date, end_date):
    """
    Fetch oncology metrics from new RAW tables:
    - raw.fact_market_share
    - raw.fact_market_patients

    Key format:
      Brand-Indication-LOT
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ms.brand,
            ms.indication,
            ms.lot,
            make_date(ms.year, ms.month, 1) AS month,
            ms.market_share,
            mp.overall_market_patients
        FROM raw.fact_market_share ms
        LEFT JOIN raw.fact_market_patients mp
          ON ms.ta = mp.ta
         AND ms.indication = mp.indication
         AND ms.lot = mp.lot
         AND ms.year = mp.year
         AND ms.month = mp.month
        WHERE ms.ta = %s
          AND make_date(ms.year, ms.month, 1)
              BETWEEN %s AND %s
        ORDER BY ms.year, ms.month
    """, (ta, start_date, end_date))

    rows = cursor.fetchall()
    metrics = {}

    for brand, indication, lot, month, share, patients in rows:
        key = f"{brand}-{indication}-{lot}"

        if key not in metrics:
            metrics[key] = {
                "month": [],
                "market_share": [],
                "nps": []
            }

        metrics[key]["month"].append(month.strftime("%Y-%m-%d"))
        metrics[key]["market_share"].append(float(share))
        metrics[key]["nps"].append(int(patients) if patients else 0)

    cursor.close()
    conn.close()

    return metrics


