from collections import defaultdict

import re


def sort_lots(lot_name):

    if not lot_name:
        return 999

    lot_upper = lot_name.upper()

    match = re.search(r"(\d+)", lot_upper)

    if match:
        return int(match.group(1))

    return 999




def get_scenario_filters(cursor, ta_name: str):

    # -----------------------------------------------------
    # Scenario names
    # -----------------------------------------------------

    cursor.execute("""
        SELECT DISTINCT scenario_name
        FROM raw.forecast_scenarios
        WHERE ta_name = %s
        ORDER BY scenario_name
    """, (ta_name,))

    scenario_names = [r[0] for r in cursor.fetchall()]

    if not scenario_names:
        return {
            "scenario_names": [],
            "data": {},
            "default_filter": {}
        }

    # -----------------------------------------------------
    # Scenario + indication + lot + product
    # -----------------------------------------------------

    cursor.execute("""
        WITH scenario_lots AS (

            SELECT DISTINCT
                scenario_name,
                ta_name,
                indication,
                lot
            FROM raw.forecast_scenarios
            WHERE ta_name = %s
        )

        SELECT
            sl.scenario_name,
            im.indications AS indication,
            sl.lot,
            im.brand_name AS product

        FROM scenario_lots sl

        JOIN raw.indication_master im
          ON im.ta = sl.ta_name
         AND LOWER(im.indications) = LOWER(sl.indication)

        WHERE im.brand_name IS NOT NULL

        ORDER BY
            sl.scenario_name,
            im.indications,
            sl.lot,
            im.brand_name
    """, (ta_name,))

    rows = cursor.fetchall()

    data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(list)
        )
    )

    for scenario, indication, lot, product in rows:

        if product not in data[scenario][indication][lot]:
            data[scenario][indication][lot].append(product)

    # -----------------------------------------------------
    # Default filter
    # -----------------------------------------------------

    default_scenario = (
        "BASE"
        if "BASE" in scenario_names
        else scenario_names[0]
    )

    default_indication = ""
    default_lot = ""

    if (
        default_scenario in data
        and data[default_scenario]
    ):

        default_indication = sorted(
            data[default_scenario].keys(),
            
        )[0]

        lots = list(
            data[default_scenario][default_indication].keys()
        )

        if lots:

            default_lot = sorted(
                    lots,
                    key=sort_lots
                )[0]

    return {
        "scenario_names": scenario_names,
        "data": data,
        "default_filter": {
            "scenario_name": default_scenario,
            "indication": default_indication,
            "lot": default_lot
        }
    }

def build_patient_metrics(
    nps_values,
    market_share_values
):

    patient_values = []

    for nps, share in zip(
        nps_values,
        market_share_values
    ):

        patient_count = round(
            float(nps or 0)
            * (float(share or 0) / 100),
            2
        )

        patient_values.append(patient_count)

    return {
        "final_nps": [
            round(float(x or 0), 2)
            for x in nps_values
        ],

        "final_market_share": [
            round(float(x or 0), 2)
            for x in market_share_values
        ],

        "final_patient_share": patient_values
    }

