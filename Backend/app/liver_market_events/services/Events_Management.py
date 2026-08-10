from typing import Optional, Literal

from psycopg2.extras import Json
from pydantic import BaseModel

from app.db.connection import get_connection

EventType = Literal["product_event", "payer_event", "payment_type_payer_product_event"]


# ============================================================
# Request schema
# ============================================================
class SelectedFilter(BaseModel):
    payment_types: list[str] = []
    payers: list[str] = []
    products: list[str] = []
    start_date: str
    end_date: str

# ============================================================
# Get all events (all event types) for a ta_name
# ============================================================
ALL_EVENT_TYPES: tuple[EventType, ...] = (
    "product_event",
    "payer_event",
    "payment_type_payer_product_event",
)


def get_all_market_events(ta_name: str) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        events_management: dict[str, dict] = {}
        for event_type in ALL_EVENT_TYPES:
            cur.execute(SELECT_ROWS_SQL, (ta_name, event_type))
            db_rows = cur.fetchall()
            events_management[event_type] = {
                "impact_curve_configuration": {
                    "rows": _rows_to_response(db_rows, event_type)
                }
            }

        return {"events_management": events_management}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


class EventRow(BaseModel):
    """event_id present = existing row to update, absent/None = new row to insert.

    'payers' is only meaningful for payment_type_payer_product_event rows —
    product_event and payer_event never use it (ignored/stored empty if sent).
    payer_event now distributes across payment types (Commercial, Medicaid, ...),
    not payers (CVS, Non-CVS) — hence impacted_payment_types, not impacted_payers.
    """
    event_id: Optional[int] = None
    event_name: str
    start_date: str
    peak_percent: Optional[float] = None
    months: Optional[int] = None
    curve_type: Optional[str] = None
    factor: Optional[float] = None
    payment_type: Optional[str] = None                 # only for payment_type_payer_product_event
    payment_types: list[str] = []
    payers: list[str] = []                              # only used for payment_type_payer_product_event
    products: list[str] = []
    source_percentages: dict[str, float] = {}
    impacted_products: Optional[list[str]] = None       # product_event, payment_type_payer_product_event
    impacted_payment_types: Optional[list[str]] = None  # payer_event


class ImpactCurveConfiguration(BaseModel):
    rows: list[EventRow]


class SaveEventRequest(BaseModel):
    ta_name: str
    selected_filter: SelectedFilter
    selected_tab: EventType
    impact_curve_configuration: ImpactCurveConfiguration


# ============================================================
# SQL (psycopg2 style, %s placeholders)
# ============================================================
SELECT_EXISTING_IDS_SQL = """
    SELECT id FROM raw_liver.market_event_configuration
    WHERE ta_name = %s AND event_type = %s;
"""

UPDATE_ROW_SQL = """
    UPDATE raw_liver.market_event_configuration
       SET event_name = %s, start_date = %s, peak_percent = %s, months = %s,
           curve_type = %s, factor = %s, payment_type = %s, payment_types = %s,
           payers = %s, products = %s, source_percentages = %s, impacted_entities = %s
     WHERE id = %s;
"""

INSERT_ROW_SQL = """
    INSERT INTO raw_liver.market_event_configuration (
        ta_name, event_type, event_name, start_date, peak_percent, months,
        curve_type, factor, payment_type, payment_types, payers, products,
        source_percentages, impacted_entities, created_by
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'admin')
    RETURNING id;
"""

DELETE_REMOVED_SQL = """
    DELETE FROM raw_liver.market_event_configuration WHERE id = ANY(%s);
"""

DELETE_SINGLE_SQL = """
    DELETE FROM raw_liver.market_event_configuration WHERE event_name = %s AND ta_name = %s AND event_type = %s;
"""

SELECT_ROWS_SQL = """
    SELECT id, event_name, start_date, peak_percent, months, curve_type, factor,
           payment_type, payment_types, payers, products, source_percentages, impacted_entities
    FROM raw_liver.market_event_configuration
    WHERE ta_name = %s AND event_type = %s
    ORDER BY id;
"""


# ============================================================
# Helper: build response rows from a DB fetch
# ============================================================
def _rows_to_response(db_rows: list, event_type: str) -> list[dict]:
    result = []
    for r in db_rows:
        row = {
            "event_id":            r[0],
            "event_name":          r[1],
            "start_date":          r[2].isoformat() if r[2] else None,
            "peak_percent":        float(r[3]) if r[3] is not None else None,
            "months":              r[4],
            "curve_type":          r[5],
            "factor":              float(r[6]) if r[6] is not None else None,
            "payment_types":       r[8] or [],
            "products":            r[10] or [],
            "source_percentages":  r[11] or {},
        }

        if event_type == "payment_type_payer_product_event":
            row["payment_type"] = r[7]
            row["payers"] = r[9] or []
            row["impacted_products"] = r[12] or []
        elif event_type == "product_event":
            row["impacted_products"] = r[12] or []
        else:  # payer_event — now distributes by payment_type, not payer
            row["impacted_payment_types"] = r[12] or []

        result.append(row)
    return result


# ============================================================
# Save (diff: update existing / insert new / delete removed)
# ============================================================
def save_market_events(payload: SaveEventRequest) -> dict:
    ta_name    = payload.ta_name
    event_type = payload.selected_tab
    rows       = payload.impact_curve_configuration.rows

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(SELECT_EXISTING_IDS_SQL, (ta_name, event_type))
        existing_ids = {r[0] for r in cur.fetchall()}
        incoming_ids = {r.event_id for r in rows if r.event_id is not None}

        removed_ids = existing_ids - incoming_ids
        if removed_ids:
            cur.execute(DELETE_REMOVED_SQL, (list(removed_ids),))

        for row in rows:
            if event_type == "payment_type_payer_product_event":
                payers = row.payers
                impacted = row.impacted_products or []
            elif event_type == "product_event":
                payers = []
                impacted = row.impacted_products or []
            else:  # payer_event — distributes by payment_type
                payers = []
                impacted = row.impacted_payment_types or []

            if row.event_id is not None and row.event_id in existing_ids:
                cur.execute(UPDATE_ROW_SQL, (
                    row.event_name, row.start_date, row.peak_percent, row.months,
                    row.curve_type, row.factor, row.payment_type, Json(row.payment_types),
                    Json(payers), Json(row.products), Json(row.source_percentages),
                    Json(impacted), row.event_id,
                ))
            else:
                cur.execute(INSERT_ROW_SQL, (
                    ta_name, event_type, row.event_name, row.start_date, row.peak_percent,
                    row.months, row.curve_type, row.factor, row.payment_type,
                    Json(row.payment_types), Json(payers), Json(row.products),
                    Json(row.source_percentages), Json(impacted),
                ))

        conn.commit()

        cur.execute(SELECT_ROWS_SQL, (ta_name, event_type))
        db_rows = cur.fetchall()

        return {
            "events_management": {
                event_type: {
                    "impact_curve_configuration": {
                        "rows": _rows_to_response(db_rows, event_type)
                    }
                }
            }
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ============================================================
# Delete a single event
# ============================================================
def delete_market_event(event_name: str, ta_name: str, event_type: EventType) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(DELETE_SINGLE_SQL, (event_name, ta_name, event_type))
        deleted = cur.rowcount
        conn.commit()

        if deleted == 0:
            raise ValueError(f"Event name {event_name} not found for ta_name={ta_name}, event_type={event_type}")

        cur.execute(SELECT_ROWS_SQL, (ta_name, event_type))
        db_rows = cur.fetchall()

        return {
            "events_management": {
                event_type: {
                    "impact_curve_configuration": {
                        "rows": _rows_to_response(db_rows, event_type)
                    }
                }
            }
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()