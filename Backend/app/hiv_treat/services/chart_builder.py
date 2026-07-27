def build_chart_from_table(table, existing_chart=None):

    print(
        "CHART INPUT LABELS:",
        [
            row.get("label")
            for row in table.get("rows", [])
        ],
    )

    chart = {}

    forecast_start_index = None

    if existing_chart:

        if "months" in existing_chart:
            chart["months"] = existing_chart["months"]

        if "forecast_start_index" in existing_chart:
            forecast_start_index = existing_chart["forecast_start_index"]
            chart["forecast_start_index"] = forecast_start_index

    chart["series"] = []

    for row in table["rows"]:

        values = row["values"]

        if forecast_start_index is not None:

            series = {
                "label": row["label"],
                "history": values[:forecast_start_index],
                "forecast": values[forecast_start_index:]
            }

        else:

            series = {
                "label": row["label"],
                "history": values.copy()
            }

        if "children" in row:

            series["children"] = []

            for child in row["children"]:

                child_values = child["values"]

                if forecast_start_index is not None:

                    child_series = {
                        "label": child["label"],
                        "history": child_values[:forecast_start_index],
                        "forecast": child_values[forecast_start_index:]
                    }

                else:

                    child_series = {
                        "label": child["label"],
                        "history": child_values.copy()
                    }

                series["children"].append(child_series)

        chart["series"].append(series)

    return chart

from datetime import datetime
from dateutil.relativedelta import relativedelta


def get_month_labels(start_date, months):

    start = datetime.strptime(start_date, "%Y-%m-%d")

    labels = []

    for i in range(months):
        labels.append(start + relativedelta(months=i))

    return labels

from collections import OrderedDict

def get_year_slices(month_labels):

    years = OrderedDict()

    for i, month in enumerate(month_labels):

        year = str(month.year)

        years.setdefault(year, []).append(i)

    return years

def build_yearly_table(monthly_table, month_labels):

    year_map = get_year_slices(month_labels)

    rows = []

    for row in monthly_table["rows"]:

        yearly = []

        for indexes in year_map.values():

            yearly.append(
                sum(row["values"][i] for i in indexes)
            )

        new_row = {
            "label": row["label"],
            "values": yearly,
        }

        if "children" in row:

            new_row["children"] = []

            for child in row["children"]:

                child_yearly = []

                for indexes in year_map.values():

                    child_yearly.append(
                        sum(child["values"][i] for i in indexes)
                    )

                new_row["children"].append({
                    "label": child["label"],
                    "values": child_yearly,
                })

        rows.append(new_row)

    return {
        "type": monthly_table["type"],
        "rows": rows,
    }
def build_yearly_chart_from_table(yearly_table):

    rows = yearly_table["rows"]

    years = [
        str(year)
        for year in yearly_table.get("years", [])
    ]

    forecast_start_index = yearly_table.get(
        "forecast_start_index",
        max(len(years) - 2, 0),
    )

    series = []

    for row in rows:

        values = row["values"]

        history = values[:forecast_start_index]
        forecast = values[forecast_start_index:]

        item = {
            "label": row["label"],
            "history": history,
            "forecast": forecast,
        }

        if "children" in row:

            children = []

            for child in row["children"]:

                child_values = child["values"]

                children.append(
                    {
                        "label": child["label"],
                        "history": child_values[:forecast_start_index],
                        "forecast": child_values[forecast_start_index:],
                    }
                )

            item["children"] = children

        series.append(item)

    return {
        "years": years,
        "forecast_start_index": forecast_start_index,
        "series": series,
    }