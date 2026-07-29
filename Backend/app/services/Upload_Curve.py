"""
Service layer for the Persistency Curve Upload API.

Excel template layout (multi-curve table format, 0-indexed row/col refs):

    Row 1 (idx 0): A = "Curve Name" label (ignored), B, C, D ... = month
                   headers (M1, M2, M3, ...)
    Row 2+ (idx 1+): A = curve name, B, C, D ... = values aligned with the
                   month headers in row 1.

Each row is one curve. Curves can have different lengths — a row only
needs to fill values up to whichever month it actually has data for;
trailing blank cells (after the last filled value) simply mean that curve
stops early. A blank cell BEFORE the last filled value in a row is treated
as a real gap and rejected.

Month headers are read left-to-right starting at column B (idx 1) and stop
at the first blank/NaN header cell — so adding M19, M20, ... to row 1 (and
filling in whichever curve rows need them) works with no code changes.
"""

import io
import re
import pandas as pd
import psycopg2.extras
from typing import List, Tuple

from fastapi import HTTPException, UploadFile

from app.db.connection import get_connection


# ---------------------------------------------------------------------------
# Row/col positions in the template (0-indexed)
# ---------------------------------------------------------------------------
HEADER_ROW = 4          # row 5 in Excel - "Curve name" + month headers
FIRST_DATA_ROW = 5      # row 6 in Excel - first curve data row
CURVE_NAME_COL = 0      # column A - curve name
FIRST_MONTH_COL = 1     # column B - first month header/value

MONTH_PATTERN = re.compile(r"^M\d+$", re.IGNORECASE)


def _is_blank(cell) -> bool:
    return pd.isna(cell) or str(cell).strip() == ""


# ---------------------------------------------------------------------------
# Excel parsing
# ---------------------------------------------------------------------------
def parse_excel(file_bytes: bytes) -> List[Tuple[str, List[str], List[float]]]:
    """
    Parses the uploaded multi-curve Excel file.
    Returns a list of (curve_name, months, values) tuples, one per curve row.
    Raises HTTPException(400) on any structural/validation problem.
    """
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded Excel file is empty.")

    try:
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, header=None, engine="openpyxl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to read Excel file: {exc}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded Excel file is empty.")

    # ---- Month headers (row 1, starting col B) ----
    months_all: List[str] = []
    col = FIRST_MONTH_COL
    n_cols = df.shape[1]
    while col < n_cols:
        cell = df.iat[HEADER_ROW, col]
        if _is_blank(cell):
            break
        months_all.append(str(cell).strip())
        col += 1

    if not months_all:
        raise HTTPException(
            status_code=400,
            detail="Invalid month header found. Expected format: M1, M2, M3...",
        )

    for m in months_all:
        if not MONTH_PATTERN.match(m):
            raise HTTPException(
                status_code=400,
                detail="Invalid month header found. Expected format: M1, M2, M3...",
            )

    # ---- Curve rows (row 2 onward) ----
    curves: List[Tuple[str, List[str], List[float]]] = []
    n_rows = df.shape[0]
    row_idx = FIRST_DATA_ROW

    while row_idx < n_rows:
        curve_name_cell = df.iat[row_idx, CURVE_NAME_COL]
        if _is_blank(curve_name_cell):
            row_idx += 1
            continue  # skip stray blank rows

        curve_name = str(curve_name_cell).strip()

        raw_row_values = df.iloc[
            row_idx, FIRST_MONTH_COL: FIRST_MONTH_COL + len(months_all)
        ].tolist()

        # Find the last filled cell in this row - everything after it is
        # "this curve doesn't go that far", not missing data.
        last_filled = -1
        for i, v in enumerate(raw_row_values):
            if not _is_blank(v):
                last_filled = i

        if last_filled == -1:
            raise HTTPException(
                status_code=400,
                detail=f"All month values must be provided for curve '{curve_name}'.",
            )

        used_months = months_all[: last_filled + 1]
        used_values_raw = raw_row_values[: last_filled + 1]

        # Any blank WITHIN the used range is a real gap - reject.
        if any(_is_blank(v) for v in used_values_raw):
            raise HTTPException(
                status_code=400,
                detail=f"All month values must be provided for curve '{curve_name}'.",
            )

        values: List[float] = []
        for v in used_values_raw:
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"Persistency values must be numeric for curve '{curve_name}'.",
                )

        curves.append((curve_name, used_months, values))
        row_idx += 1

    if not curves:
        raise HTTPException(status_code=400, detail="Curve name is required.")

    return curves


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------
# Placeholder until real authenticated-user context is wired into this endpoint.
DEFAULT_USER_ID = "system_default_user"


def upsert_curve(
    conn,
    ta_name: str,
    curve_name: str,
    months: List[str],
    values: List[float],
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """
    Inserts a new curve, or updates curve_values/updated_at if a row with
    the same (ta_name, curve_name) already exists.
    Relies on the uq_persistency_curve UNIQUE (ta_name, curve_name) constraint.
    """
    curve_values = {"months": months, "values": values}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.persistency_curve_master
                (user_id, ta_name, curve_name, curve_values)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ta_name, curve_name)
            DO UPDATE SET
                curve_values = EXCLUDED.curve_values,
                user_id = EXCLUDED.user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, ta_name, curve_name, psycopg2.extras.Json(curve_values)),
        )
    conn.commit()


def fetch_curve_list(conn, ta_name: str) -> List[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT curve_name
            FROM raw.persistency_curve_master
            WHERE ta_name = %s
            ORDER BY curve_name
            """,
            (ta_name,),
        )
        rows = cur.fetchall()
    return [{"curve_name": r[0]} for r in rows]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def process_curve_upload(file: UploadFile, ta_name: str) -> dict:
    if not ta_name or not ta_name.strip():
        raise HTTPException(status_code=400, detail="TA name is required.")

    if not file:
        raise HTTPException(status_code=400, detail="Uploaded Excel file is empty.")

    file_bytes = await file.read()
    curves = parse_excel(file_bytes)  # list of (curve_name, months, values)

    conn = get_connection()
    try:
        curve_previews = []
        for curve_name, months, values in curves:
            upsert_curve(conn, ta_name, curve_name, months, values)
            curve_previews.append({
                "curve_name": curve_name,
                "months": months,
                "values": values,
            })
        curve_list = fetch_curve_list(conn, ta_name)
    finally:
        conn.close()

    return {
        "message": "Curve uploaded successfully",
        "curve_list": curve_list,
        "curve_previews": curve_previews,
    }