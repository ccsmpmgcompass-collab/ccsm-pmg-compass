"""github_actions.py — fires workflow_dispatch events against CCSM's own
GitHub Actions workflows.

Ported from Utah Provo's app/integrations/github_actions.py, with _API_BASE
repointed from pmgcompass-upm/PMG-Compass to CCSM's own repo.
"""
import os

import requests

_API_BASE = "https://api.github.com/repos/ccsmpmgcompass-collab/ccsm-pmg-compass"


class DispatchError(Exception):
    pass


def _get_token() -> str:
    try:
        import streamlit as st
        if "GITHUB_ACTIONS_TOKEN" in st.secrets:
            return st.secrets["GITHUB_ACTIONS_TOKEN"]
    except Exception:
        pass
    token = os.environ.get("GITHUB_ACTIONS_TOKEN", "")
    if not token:
        raise DispatchError(
            "GITHUB_ACTIONS_TOKEN not found in st.secrets or the environment."
        )
    return token


def dispatch_workflow(workflow_file: str, inputs: dict, ref: str = "main") -> None:
    """Fire a workflow_dispatch event on workflow_file. All input values are
    stringified — GitHub's API requires workflow_dispatch inputs to be strings."""
    token = _get_token()
    resp = requests.post(
        f"{_API_BASE}/actions/workflows/{workflow_file}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": ref, "inputs": {k: str(v) for k, v in inputs.items()}},
        timeout=15,
    )
    if resp.status_code != 204:
        raise DispatchError(f"Dispatch failed ({resp.status_code}): {resp.text}")
