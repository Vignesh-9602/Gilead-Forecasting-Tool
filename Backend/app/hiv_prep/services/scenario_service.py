def get_available_scenarios(cur, ta_name):

    cur.execute("""
        SELECT DISTINCT
            COALESCE(scenario_name,'Base')
        FROM raw_hiv_prep.forecast_outputs
        WHERE ta_name=%s
        
    """, (ta_name,))

    scenarios = [row[0] for row in cur.fetchall()]

    if "Base" not in scenarios:
        scenarios.insert(0, "Base")

    return scenarios