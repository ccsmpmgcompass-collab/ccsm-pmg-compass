"""
imos_transfer_runner.py — CLI entry point for CCSM's transfer roster
automation. Runs standalone (GitHub Actions or a local shell), no Streamlit
context — so it authenticates to Sheets directly via
GOOGLE_SHEETS_CREDENTIALS_JSON rather than through app.db.sheets_client
(which needs st.secrets).

Usage:
    python -m app.ingestion.imos_transfer_runner

Downloads the Organization Roster from imos.churchofjesuschrist.org,
transforms it into TRANSFER_IMPORT rows, and writes them to COMPASS_CCSM's
TRANSFER_IMPORT tab. Never calls apply()/form_sync() — the mission office
still reviews and applies from the Traslados page.

Ported from Utah Provo's app/ingestion/imos_transfer_runner.py.
"""

import json
import sys
import tempfile
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from app.ingestion import ccsm_ingestion_settings as settings
from app.ingestion.imos_portal import download_organization_roster_and_emails
from app.ingestion.transfer_roster_transform import transform_roster
from app.utils.logger import get_logger

_logger = get_logger("ingestion.imos_transfer_runner")

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
_HEADERS = ["Area", "Zone", "District", "Companion1_Name", "Companion2_Name",
            "Companion3_Name", "Companion4_Name", "Calling", "Area_Email"]


def match_area_emails(rows: list[dict], area_emails: dict) -> tuple[int, int, list[str]]:
    """Fills in row["Area_Email"] in place from the scraped area_emails dict.
    Exact match first, then a prefix match only when exactly one candidate
    qualifies (never misassigns an email between two different areas)."""
    matched = 0
    fuzzy_matched = 0
    email_lookup = {k.strip().lower(): v for k, v in area_emails.items()}
    unmatched_areas = []
    for row in rows:
        area_key = str(row["Area"]).strip().lower()
        email = email_lookup.get(area_key)
        if not email:
            candidates = [k for k in email_lookup
                          if k.startswith(area_key) or area_key.startswith(k)]
            if len(candidates) == 1:
                email = email_lookup[candidates[0]]
                fuzzy_matched += 1
        if email:
            row["Area_Email"] = email
            matched += 1
        else:
            unmatched_areas.append(row["Area"])
    return matched, fuzzy_matched, unmatched_areas


def _write_transfer_import(rows: list[dict]) -> int:
    creds_dict = json.loads(settings.GOOGLE_SHEETS_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    client = gspread.authorize(creds)
    sh = client.open(settings.COMPASS_SHEET_NAME)
    ws = sh.worksheet("TRANSFER_IMPORT")
    ws.clear()
    grid = [_HEADERS] + [[r.get(h, "") for h in _HEADERS] for r in rows]
    ws.update(grid, value_input_option="RAW")
    return len(rows)


def main() -> None:
    if not settings.IMOS_USERNAME or not settings.IMOS_PASSWORD:
        _logger.error("CCSM_IMOS_USERNAME/CCSM_IMOS_PASSWORD not set — aborting.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp:
        _logger.info("Downloading Organization Roster and area emails...")
        roster_path, area_emails = download_organization_roster_and_emails(
            username=settings.IMOS_USERNAME,
            password=settings.IMOS_PASSWORD,
            output_dir=Path(tmp),
            headless=settings.IMOS_HEADLESS,
        )

        _logger.info("Transforming roster...")
        rows = transform_roster(roster_path)
        if not rows:
            _logger.error("Transform produced zero rows — aborting before Sheets write.")
            sys.exit(1)

        matched, fuzzy_matched, unmatched_areas = match_area_emails(rows, area_emails)
        _logger.info(f"Matched {matched}/{len(rows)} areas to an email "
                      f"({fuzzy_matched} via prefix fallback, {len(area_emails)} emails scraped)")
        if unmatched_areas:
            _logger.info(f"Areas with no matching email (check manually): {unmatched_areas}")

        _logger.info(f"Writing {len(rows)} rows to TRANSFER_IMPORT...")
        written = _write_transfer_import(rows)
        _logger.info(f"Done — {written} rows written. Review on the Traslados page "
                      f"before applying.")


if __name__ == "__main__":
    main()
