"""gcp_creds.py — shared Google service-account credential loading.

Works in two contexts:
  - Inside a GitHub Actions runner (no Streamlit): reads the
    GOOGLE_SHEETS_CREDENTIALS_JSON env var, which is a real repo secret there.
  - Inside Streamlit (Cloud or local `streamlit run`): falls back to
    st.secrets["gcp_service_account"].

Root .env's copy of GOOGLE_SHEETS_CREDENTIALS_JSON is a stale, unfilled
placeholder — this loader treats any value that fails to JSON-parse as
"not available" and falls through to the Streamlit path instead of raising.
"""
import json
import os


def _normalize(data: dict) -> dict:
    data = dict(data)
    pk = data.get("private_key", "")
    data["private_key"] = pk.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    return data


def get_service_account_dict() -> dict:
    env_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
    if env_json:
        try:
            data = json.loads(env_json)
            if isinstance(data, dict) and data.get("private_key"):
                return _normalize(data)
        except json.JSONDecodeError:
            pass

    try:
        import streamlit as st
        data = dict(st.secrets["gcp_service_account"])
        return _normalize(data)
    except Exception as e:
        raise RuntimeError(
            "No usable Google service account credentials found — set "
            "GOOGLE_SHEETS_CREDENTIALS_JSON (real JSON, not the placeholder) "
            "or configure st.secrets['gcp_service_account']."
        ) from e
