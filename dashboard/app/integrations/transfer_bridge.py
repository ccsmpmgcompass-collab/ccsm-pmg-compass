"""
transfer_bridge.py — HTTP client for CCSM_TransferWebApp.gs (see Task 5). The
gspread service account behind this dashboard has no Forms API access, so
nightly/weekly form dropdown sync has to run in Apps Script; this module is
the bridge that calls it from Streamlit.

TRANSFER_WEBAPP_URL / TRANSFER_WEBAPP_SECRET come from Streamlit secrets —
set after CCSM_TransferWebApp.gs is deployed (Task 5, Step 3).
"""
from __future__ import annotations

import requests
import streamlit as st


class FormSyncError(Exception):
    pass


def form_sync(which: str = "both") -> dict:
    """which: 'nightly' | 'weekly' | 'both'. Returns the parsed JSON response
    from CCSM_TransferWebApp.gs's doPost({action:'formSync', which})."""
    url = st.secrets.get("TRANSFER_WEBAPP_URL", "")
    secret = st.secrets.get("TRANSFER_WEBAPP_SECRET", "")
    if not url or not secret:
        raise FormSyncError(
            "TRANSFER_WEBAPP_URL / TRANSFER_WEBAPP_SECRET not set in secrets — "
            "deploy CCSM_TransferWebApp.gs first (see Task 5)."
        )
    resp = requests.post(
        url, json={"secret": secret, "action": "formSync", "which": which},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise FormSyncError(data.get("error", "Unknown form sync failure."))
    return data
