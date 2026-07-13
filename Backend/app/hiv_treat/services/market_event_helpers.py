METRIC_FILTERS = [
    {
        "label": "Market Share",
        "value": "market_share",
    },
    {
        "label": "Overall Market Volume",
        "value": "market_volume",
    },
]


def load_metadata(cursor, ta_name: str, scenario_name: str,start_date: str,end_date: str):
    """
    Loads all metadata required by Apply Filters.

    Returns:
    {
        "available_scenarios": [...],
        "available_months": [...],
        "metric_filters": [...],
        "forecast_start_date": "...",
    }
    """

    # -----------------------------
    # Available scenarios
    # -----------------------------
    cursor.execute(
        """
        SELECT DISTINCT scenario_name
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
        ORDER BY scenario_name
        """,
        (ta_name,),
    )

    scenarios = [row["scenario_name"] for row in cursor.fetchall()]

    if "BASE" not in scenarios:
        scenarios.insert(0, "BASE")

    # -----------------------------
    # Load one row to extract months
    # -----------------------------
    cursor.execute(
        """
        SELECT forecast_data
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name = %s
        LIMIT 1
        """,
        (ta_name, scenario_name),
    )

    row = cursor.fetchone()

    available_months = []
    forecast_start_date = None

    if row:

        forecast_data = row["forecast_data"]

        all_months = forecast_data.get("months", [])

        available_months = [
            month
            for month in all_months
            if start_date <= month <= end_date
        ]

        forecast_index = forecast_data.get("forecast_start_index", 0)

        forecast_start_date = None

        if forecast_index < len(all_months):
            forecast_start_date = all_months[forecast_index]

    metric_filters = [
        {
            "label": "Market Share",
            "value": "market_share",
        },
        {
            "label": "Overall Market Volume",
            "value": "market_volume",
        },
    ]

    return {
        "available_scenarios": scenarios,
        "available_months": available_months,
        "metric_filters": metric_filters,
        "forecast_start_date": forecast_start_date,
    }

def load_forecast_outputs(
    cursor,
    ta_name: str,
    scenario_name: str,
):
    """
    Load all forecast outputs for a TA and scenario.

    Returns
    -------
    {
        "market_share": [...],
        "market_volume": [...]
    }
    """

    cursor.execute(
        """
        SELECT
            metric,
            market,
            source_of_market,
            product,
            forecast_data
        FROM raw_hiv_treat.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name = %s
        ORDER BY
            metric,
            market,
            source_of_market,
            product
        """,
        (
            ta_name,
            scenario_name,
        ),
    )

    rows = cursor.fetchall()

    metrics = {
        "market_share": [],
        "market_volume": [],
    }

    for row in rows:

        metric = row["metric"]

        if metric not in metrics:
            metrics[metric] = []

        metrics[metric].append(
            {
                "market": row["market"],
                "source_of_market": row["source_of_market"],
                "product": row["product"],
                "forecast_data": row["forecast_data"],
            }
        )

    return metrics

