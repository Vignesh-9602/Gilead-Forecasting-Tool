from datetime import date
from dateutil.relativedelta import relativedelta


def parse_year_month(date_str: str) -> tuple:
    """
    Convert a date string into a (year, month) tuple.

    Accepts '2020-04' or '2020-04-01'.
    Example: '2020-04-01' → (2020, 4)
    """
    parts = date_str.split("-")
    return int(parts[0]), int(parts[1])


def to_month_label(year: int, month: int) -> str:
    """
    Format (year, month) as an ISO date string with day = 01.
    Example: (2020, 4) → '2020-04-01'
    """
    return date(year, month, 1).isoformat()


def generate_month_range(start_year: int, start_month: int,
                          end_year: int, end_month: int) -> list:
    """
    Generate a list of month label strings from start to end (inclusive).

    Example: generate_month_range(2024, 6, 2024, 9)
             → ['2024-06-01', '2024-07-01', '2024-08-01', '2024-09-01']
    """
    result = []
    current = date(start_year, start_month, 1)
    end = date(end_year, end_month, 1)

    while current <= end:
        result.append(current.isoformat())
        current += relativedelta(months=1)

    return result


def add_months(year: int, month: int, months_to_add: int) -> tuple:
    """
    Add a number of months to a (year, month) and return the new (year, month).

    Example: add_months(2025, 12, 12) → (2026, 12)
    """
    new_date = date(year, month, 1) + relativedelta(months=months_to_add)
    return new_date.year, new_date.month
