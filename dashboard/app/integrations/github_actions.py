"""github_actions.py — fires workflow_dispatch events against CCSM's own
GitHub Actions workflows.

Ported from Utah Provo's app/integrations/github_actions.py, with _API_BASE
repointed from pmgcompass-upm/PMG-Compass to CCSM's own repo.
"""
import os
import subprocess

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


def _current_ref() -> str:
    """The git branch this deployment is actually running from.

    GitHub only lets workflow_dispatch discover/dispatch a workflow whose
    YAML file exists on the default branch, but the CODE that ref checks
    out for the run can be any branch — so a hardcoded "main" default
    silently dispatches whatever code is on main, even while this very
    module is being developed and tested on a feature branch that main
    doesn't have yet (that gap is what stalled the first live dispatch
    tests of this feature). Streamlit Cloud checks out the deployed
    branch's own commit, so this naturally resolves to "main" once this
    code is merged — falling back to "main" here only matters pre-merge,
    and even then only if git itself is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        branch = out.stdout.strip()
        if branch and branch != "HEAD":
            return branch
    except Exception:
        pass
    return "main"


def dispatch_workflow(workflow_file: str, inputs: dict, ref: str | None = None) -> None:
    """Fire a workflow_dispatch event on workflow_file. All input values are
    stringified — GitHub's API requires workflow_dispatch inputs to be
    strings. ref defaults to _current_ref() rather than a hardcoded "main",
    so the code a dispatch runs is always the code that dispatched it."""
    token = _get_token()
    resp = requests.post(
        f"{_API_BASE}/actions/workflows/{workflow_file}/dispatches",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"ref": ref or _current_ref(),
              "inputs": {k: str(v) for k, v in inputs.items()}},
        timeout=15,
    )
    if resp.status_code != 204:
        raise DispatchError(f"Dispatch failed ({resp.status_code}): {resp.text}")
