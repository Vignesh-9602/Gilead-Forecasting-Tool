import json


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
        FROM raw_hiv_prep.forecast_outputs
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
        FROM raw_hiv_prep.forecast_outputs
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
        FROM raw_hiv_prep.forecast_outputs
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



def load_events_payload(
    cursor,
    ta_name,
    scenario_name,
):
    cursor.execute(
        """
        SELECT events_payload
        FROM raw_hiv_prep.forecast_outputs
        WHERE ta_name = %s
          AND scenario_name = %s
          AND events_payload IS NOT NULL
        LIMIT 1
        """,
        (
            ta_name,
            scenario_name,
        ),
    )

    row = cursor.fetchone()

    if not row:
        return []

    if isinstance(row, dict):
        raw_payload = row.get(
            "events_payload"
        )
    else:
        raw_payload = row[0]

    if raw_payload is None:
        return []

    # JSON/JSONB may already be converted
    if isinstance(raw_payload, list):
        return raw_payload

    if isinstance(raw_payload, dict):
        return [raw_payload]

    if isinstance(raw_payload, str):
        raw_payload = raw_payload.strip()

        if not raw_payload:
            return []

        try:
            parsed = json.loads(
                raw_payload
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid events_payload JSON "
                f"for scenario {scenario_name!r}: "
                f"{exc}"
            ) from exc

        if isinstance(parsed, list):
            return parsed

        if isinstance(parsed, dict):
            return [parsed]

    return []


def is_overall_event(event):
    if not isinstance(event, dict):
        return False

    return (
        "impacted_markets" not in event
        and "impacted_products" not in event
    )

def get_overall_events(events):
    return [
        event
        for event in (events or [])
        if is_overall_event(event)
    ]

def normalize_overall_event(event):
    event = event or {}

    return {
        "event_id": event.get(
            "event_id"
        ),

        "event_name": str(
            event.get(
                "event_name",
                "",
            )
            or ""
        ),

        "start_date": event.get(
            "start_date"
        ),

        "peak_percent": float(
            event.get(
                "peak_percent",
                0,
            )
            or 0
        ),

        "months": int(
            event.get(
                "months",
                0,
            )
            or 0
        ),

        "curve_type": str(
            event.get(
                "curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "factor": float(
            event.get(
                "factor",
                0,
            )
            or 0
        ),

        "enable_coverage": bool(
            event.get(
                "enable_coverage",
                False,
            )
        ),

        "coverage_peak_percent": float(
            event.get(
                "coverage_peak_percent",
                0,
            )
            or 0
        ),

        "coverage_peak_months": int(
            event.get(
                "coverage_peak_months",
                0,
            )
            or 0
        ),

        "coverage_curve_type": str(
            event.get(
                "coverage_curve_type",
                "Linear",
            )
            or "Linear"
        ),

        "coverage_factor": float(
            event.get(
                "coverage_factor",
                0,
            )
            or 0
        ),
    }



