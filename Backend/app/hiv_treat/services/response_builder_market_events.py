def build_monthly_table(
    headers,
    forecast_start_index,
    rows,
    hierarchy=False,
):
    """
    Generic Monthly Table Builder.

    Parameters
    ----------
    headers : list
        Month headers.

    forecast_start_index : int

    rows : list
        Table rows.

    hierarchy : bool
        Whether the table contains children.

    Returns
    -------
    {
        "headers": [...],
        "forecast_start_index": int,
        "editable": True,
        "rows": [...]
    }
    """

    table = {
        "headers": headers,
        "forecast_start_index": forecast_start_index,
        "editable": True,
        "rows": rows,
    }

    if hierarchy:
        table["type"] = "hierarchy"

    return table

def build_yearly_table(monthly_table, aggregation="sum"):
    months = monthly_table["headers"]
    forecast_start_index = monthly_table["forecast_start_index"]

    years = sorted({month[:4] for month in months})

    if forecast_start_index >= len(months):
        yearly_forecast_start_index = len(years)
    elif forecast_start_index <= 0:
        yearly_forecast_start_index = 0
    else:
        forecast_year = months[forecast_start_index][:4]
        yearly_forecast_start_index = years.index(forecast_year)

    yearly = {
        "headers": years,
        "forecast_start_index": yearly_forecast_start_index,
        "editable": monthly_table.get("editable", True),
        "rows": [],
    }

    if monthly_table.get("type") == "hierarchy":
        yearly["type"] = "hierarchy"

    yearly["rows"] = [
        build_yearly_row(row, months, years, aggregation)
        for row in monthly_table["rows"]
    ]

    return yearly

def build_yearly_row(row, months, years, aggregation):
    yearly_values = []

    for year in years:
        matching_values = [
            value
            for month, value in zip(months, row["values"])
            if month.startswith(year)
        ]

        if aggregation == "average":
            result = (
                sum(matching_values) / len(matching_values)
                if matching_values
                else 0
            )
        else:
            result = sum(matching_values)

        yearly_values.append(round(result, 2))

    yearly_row = {
        "label": row["label"],
        "values": yearly_values,
    }

    if "children" in row:
        yearly_row["children"] = [
            build_yearly_row(child, months, years, aggregation)
            for child in row["children"]
        ]

    return yearly_row

def build_monthly_chart(monthly_table):
    headers = monthly_table["headers"]
    forecast_start_index = monthly_table["forecast_start_index"]

    series = []

    for row in monthly_table["rows"]:

        if (
            monthly_table.get("type") == "hierarchy"
            and row["label"] == "Overall"
        ):
            continue

        series.append(
            {
                "label": row["label"],
                "history": row["values"][:forecast_start_index],
                "forecast": row["values"][forecast_start_index:],
            }
        )

    return {
        "months": headers,
        "forecast_start_index": forecast_start_index,
        "series": series,
    }

def build_yearly_chart(yearly_table):
    headers = yearly_table["headers"]
    forecast_start_index = yearly_table["forecast_start_index"]

    series = []

    for row in yearly_table["rows"]:

        if (
            yearly_table.get("type") == "hierarchy"
            and row["label"] == "Overall"
        ):
            continue

        series.append(
            {
                "label": row["label"],
                "history": row["values"][:forecast_start_index],
                "forecast": row["values"][forecast_start_index:],
            }
        )

    return {
        "years": headers,
        "forecast_start_index": forecast_start_index,
        "series": series,
    }