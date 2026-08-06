"""
ccsm_ingestion_settings.py — minimal .env-backed settings for the IMOS roster
runner. Deliberately NOT a port of Provo's app/config/settings.py — that
module carries many Provo-only fields (Church SSO, Tableau, Supabase) this
runner has no use for. Streamlit's own st.secrets is untouched by this;
Streamlit reads its own secrets.toml, this only serves the standalone CLI
runner (imos_transfer_runner.py), which runs outside any Streamlit context.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _resolve(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


IMOS_USERNAME = _resolve("CCSM_IMOS_USERNAME")
IMOS_PASSWORD = _resolve("CCSM_IMOS_PASSWORD")
IMOS_HEADLESS = _resolve("IMOS_HEADLESS", "true").lower() == "true"
COMPASS_SHEET_NAME = _resolve("COMPASS_SHEET_NAME", "COMPASS_CCSM")
GOOGLE_SHEETS_CREDENTIALS_JSON = _resolve("GOOGLE_SHEETS_CREDENTIALS_JSON")
