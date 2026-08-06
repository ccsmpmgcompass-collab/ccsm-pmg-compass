"""
transfer_sheets_writer.py — Clears and rewrites the TRANSFER_IMPORT tab with
rows produced by transfer_roster_transform.build_transfer_rows.

Ported from Utah Provo's app/ingestion/transfer_sheets_writer.py, adapted to
call app.db.sheets_client.overwrite_tab() instead of the raw Sheets API —
CCSM's sheets_client already has an equivalent clear+rewrite helper, so no
separate googleapiclient/service-account plumbing is needed here.

Mirrors the manual process's "select all, delete, paste" step exactly: one
all-or-nothing batched write, never partial rows.

This is a Streamlit-context-only function (needs st.secrets via
sheets_client) — the standalone CLI runner (imos_transfer_runner.py) has no
Streamlit context and writes to Sheets directly instead of importing this
module.
"""

from app.db import sheets_client as sc
from app.utils.logger import get_logger

_logger = get_logger("ingestion.transfer_sheets_writer")

_TAB_NAME = "TRANSFER_IMPORT"
_HEADERS = ["Area", "Zone", "District", "Companion1_Name", "Companion2_Name",
            "Companion3_Name", "Companion4_Name", "Calling", "Area_Email"]


def write_transfer_import(rows: list) -> int:
    """Clears TRANSFER_IMPORT and writes header + rows in one batched call.
    Raises ValueError if rows is empty — never clears the tab with nothing
    to replace it."""
    if not rows:
        raise ValueError("Refusing to write TRANSFER_IMPORT: rows is empty.")

    grid = [_HEADERS] + [[r.get(h, "") for h in _HEADERS] for r in rows]
    sc.overwrite_tab(_TAB_NAME, grid)
    _logger.info(f"Wrote {len(rows)} rows to {_TAB_NAME}")
    return len(rows)
