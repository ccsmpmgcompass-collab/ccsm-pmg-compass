"""Regression for audit finding B6 (AUDIT-IA-2026-08-22.md).

Two separate defects, both in the Action Center:

1. The bell badge counts summary["maintenance_issues"] into its total (see
   get_action_center_summary), but views/17_Centro_de_Acción.py's "Needs Your
   Action" section only checked suggestions/follow-ups/tasks — never
   maintenance_issues. A leadership user could see the bell say "1", click
   through, and land on "Nothing needs your action right now," with the one
   real item sitting unmentioned in the Maintenance section further down.

2. action_center_queries._maintenance_issues() built its three messages as
   bare f-strings, so they were the one place on an otherwise-Spanish page
   that rendered in English — confirmed live: "6 agent run(s) failed in the
   last 14 days" next to Spanish section headers.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


# ── 1. "Needs Your Action" must reflect a maintenance-only summary ────────────

def _stub_summary(maintenance_issues):
    return {
        "suggestions_ap_count": 0, "suggestions_mp_count": 0,
        "followups_count": 0, "my_tasks_count": len(maintenance_issues) * 0,
        "maintenance_issues": maintenance_issues,
        "total": len(maintenance_issues),
        "suggestions_ap_df": pd.DataFrame(),
        "suggestions_mp_df": pd.DataFrame(),
        "my_tasks_df": pd.DataFrame(),
    }


@pytest.fixture(autouse=True)
def _empty_sheets(monkeypatch):
    monkeypatch.setattr("app.db.sheets_client._read_tab_cached",
                         lambda tab_name, header_marker=None: pd.DataFrame())


def _run_action_center(maintenance_issues):
    import app.auth.auth as auth
    import app.db.action_center_queries as acq

    auth.is_leadership = lambda email: True
    acq.get_action_center_summary = lambda email: _stub_summary(maintenance_issues)

    at = AppTest.from_file("views/17_Centro_de_Acción.py", default_timeout=60)
    at.run()
    assert not at.exception, f"Action Center raised: {at.exception}"
    return at


def test_needs_your_action_is_not_empty_when_only_maintenance_is_outstanding(monkeypatch):
    at = _run_action_center(["6 agent run(s) failed in the last 14 days"])
    body = "\n".join(m.value for m in at.markdown) + "\n".join(s.value for s in at.success)
    assert "Nothing needs your action right now." not in body, (
        "Needs Your Action claimed nothing needed action while the bell's "
        "own total (which this page also computes) was non-zero"
    )


def test_needs_your_action_still_says_nothing_when_truly_empty(monkeypatch):
    at = _run_action_center([])
    body = "\n".join(s.value for s in at.success)
    assert "Nothing needs your action right now." in body


# ── 2. Maintenance messages must be translatable, not baked-in English ────────

def _daily_log_stale():
    return pd.DataFrame([{"Date": "2020-01-01", "Area": "Arauco 1",
                           "Zone": "Arauco", "District": "Arauco"}])


def _agent_run_log_with_failures():
    return pd.DataFrame([
        {"Agent": "Agent1A", "Status": "ERROR", "Timestamp": "2026-08-30 12:00"},
        {"Agent": "Agent3", "Status": "ERROR", "Timestamp": "2026-08-31 12:00"},
    ])


def test_maintenance_issue_text_is_translated_to_spanish(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "AGENT_RUN_LOG":
            return _agent_run_log_with_failures()
        if tab_name == "DAILY_LOG":
            return _daily_log_stale()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)

    def _call():
        from app.db.action_center_queries import _maintenance_issues
        import streamlit as st
        for issue in _maintenance_issues():
            st.text(issue)

    at = AppTest.from_function(_call, default_timeout=60)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception, f"_maintenance_issues raised: {at.exception}"

    texts = [w.value for w in at.get("text")]
    joined = "\n".join(texts)
    assert "agent run(s) failed" not in joined, f"English leaked: {texts}"
    assert "hasn't been written" not in joined, f"English leaked: {texts}"
    assert any("ejecución" in s or "día" in s for s in texts), (
        f"expected Spanish maintenance text, got: {texts}"
    )
