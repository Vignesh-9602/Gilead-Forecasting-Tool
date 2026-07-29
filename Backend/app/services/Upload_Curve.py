"""
Service layer for the Persistency Curve Upload API.

Excel template layout (fixed, 0-indexed row/col references used in code):

    Row 1 (idx 0): A = "Curve Name" label,      B = <curve name value>
    Row 3 (idx 2): instructions text (ignored)
    Row 4 (idx 3): instructions text (ignored)
    Row 6 (idx 5): A, B, C ... = month headers   (M1, M2, M3, ...)
    Row 7 (idx 6): A, B, C ... = curve values    (aligned with month headers)

Month columns are read left-to-right starting at column A (idx 0) and stop
at the first column where the month header is blank/NaN. This makes the
template flexible — adding M15, M16, ... in row 6 (and matching values in
row 7) works with no code changes.
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
CURVE_NAME_LABEL_ROW = 0
CURVE_NAME_LABEL_COL = 0
CURVE_NAME_VALUE_COL = 1

MONTH_HEADER_ROW = 5   # row 6 in Excel
MONTH_VALUE_ROW = 6    # row 7 in Excel

MONTH_PATTERN = re.compile(r"^M\d+$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Excel parsing
# ---------------------------------------------------------------------------
def parse_excel(file_bytes: bytes) -> Tuple[str, List[str], List[float]]:
    """
    Parses the uploaded Excel file and returns (curve_name, months, values).
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

    # ---- Curve Name ----
    curve_name = None
    try:
        raw_curve_name = df.iat[CURVE_NAME_LABEL_ROW, CURVE_NAME_VALUE_COL]
        if pd.notna(raw_curve_name):
            curve_name = str(raw_curve_name).strip()
    except (IndexError, KeyError):
        curve_name = None

    if not curve_name:
        raise HTTPException(status_code=400, detail="Curve name is required.")

    # ---- Month headers (row 6) ----
    months: List[str] = []
    col = 0
    n_cols = df.shape[1]
    while col < n_cols:
        cell = df.iat[MONTH_HEADER_ROW, col] if MONTH_HEADER_ROW < df.shape[0] else None
        if pd.isna(cell) or str(cell).strip() == "":
            break
        months.append(str(cell).strip())
        col += 1

    if not months:
        raise HTTPException(
            status_code=400,
            detail="Invalid month header found. Expected format: M1, M2, M3...",
        )

    for m in months:
        if not MONTH_PATTERN.match(m):
            raise HTTPException(
                status_code=400,
                detail="Invalid month header found. Expected format: M1, M2, M3...",
            )

    # ---- Values (row 7), same column span as months ----
    if MONTH_VALUE_ROW >= df.shape[0]:
        raise HTTPException(status_code=400, detail="All month values must be provided.")

    raw_values = df.iloc[MONTH_VALUE_ROW, 0:len(months)].tolist()

    if any(pd.isna(v) or str(v).strip() == "" for v in raw_values):
        raise HTTPException(status_code=400, detail="All month values must be provided.")

    if len(raw_values) != len(months):
        raise HTTPException(
            status_code=400,
            detail="Number of months must equal number of values.",
        )

    values: List[float] = []
    for v in raw_values:
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Persistency values must be numeric.")

    return curve_name, months, values


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
    curve_name, months, values = parse_excel(file_bytes)

    conn = get_connection()
    try:
        upsert_curve(conn, ta_name, curve_name, months, values)
        curve_list = fetch_curve_list(conn, ta_name)
    finally:
        conn.close()

    return {
        "message": "Curve uploaded successfully",
        "curve_list": curve_list,
        "curve_preview": {
            "curve_name": curve_name,
            "months": months,
            "values": values,
        },
    }