from app.db.connection import get_connection

def get_oncology_metrics(ta_name: str):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
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
            ORDER BY ms.year, ms.month
            """,
            (ta_name,)
        )

        rows = cur.fetchall()
        metrics = {}
        seen_nps_months = set()

        for brand, indication, lot, month, market_share, nps in rows:
            # ✅ DISPLAY — EXACT DB VALUES
            brand_disp = brand.strip() if brand else None
            indication_disp = indication.strip()
            lot_disp = lot.strip()

            # ✅ INTERNAL KEYS — ALWAYS LOWERCASE
            brand_n = brand_disp.lower() if brand_disp else None
            indication_n = indication_disp.lower()
            lot_n = lot_disp.lower()

            month_str = month.strftime("%Y-%m-%d")

            # ---------------------------
            # MARKET SHARE
            # ---------------------------
            if brand_disp:
                key = f"{brand_n}-{indication_n}-{lot_n}"

                if key not in metrics:
                    metrics[key] = {
                        "month": [],
                        "market_share": [],
                        "nps": [],
                        "display": {
                            "brand": brand_disp,
                            "indication": indication_disp,
                            "lot": lot_disp
                        }
                    }

                metrics[key]["month"].append(month_str)
                metrics[key]["market_share"].append(float(market_share or 0))
                metrics[key]["nps"].append(0)

            # ---------------------------
            # NPS (once per month)
            # ---------------------------
            nps_key = f"{indication_n}-{lot_n}"

            if nps_key not in metrics:
                metrics[nps_key] = {
                    "month": [],
                    "market_share": [],
                    "nps": [],
                    "display": {
                        "brand": None,
                        "indication": indication_disp,
                        "lot": lot_disp
                    }
                }

            dedup_key = (nps_key, month_str)
            if dedup_key not in seen_nps_months:
                seen_nps_months.add(dedup_key)
                metrics[nps_key]["month"].append(month_str)
                metrics[nps_key]["market_share"].append(0.0)
                metrics[nps_key]["nps"].append(int(nps or 0))

        return metrics

    finally:
        cur.close()
        conn.close()

def build_metrics_hierarchy(metrics: dict):
    """
    Build Indication -> LOT -> Brands hierarchy
    using DB display values.
    """

    hierarchy = {}

    for value in metrics.values():
        ind = value["display"]["indication"]
        lot = value["display"]["lot"]
        brand = value["display"]["brand"]

        hierarchy.setdefault(ind, {})
        hierarchy[ind].setdefault("lots", {})
        hierarchy[ind]["lots"].setdefault(lot, {})
        hierarchy[ind]["lots"][lot].setdefault("brands", [])

        if brand and brand not in hierarchy[ind]["lots"][lot]["brands"]:
            hierarchy[ind]["lots"][lot]["brands"].append(brand)

    return hierarchy


def build_metrics_filter_data(metrics: dict):
    """
    indication -> lot -> [brands]
    USING EXACT DB VALUES (no casing changes)
    """

    data = {}

    for value in metrics.values():
        indication = value["display"]["indication"]
        lot = value["display"]["lot"]
        brand = value["display"]["brand"]

        data.setdefault(indication, {})
        data[indication].setdefault(lot, [])

        if brand:
            if brand not in data[indication][lot]:
                data[indication][lot].append(brand)

    return data