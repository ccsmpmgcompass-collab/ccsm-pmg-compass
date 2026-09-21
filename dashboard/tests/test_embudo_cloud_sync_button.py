"""The Embudo page's "Sync from Tableau now" button, clicked.

Rendering the page was never the risk. The risk was what happens on the CLICK,
and it bit on the first live press (workflow run #3, 2026-09-21): the button
dispatched the job correctly and then the page died on

    StreamlitAPIException: Expanders may not be nested inside other expanders.

because `run_cloud_job` reports progress in an `st.status` box, a status box IS
an expander, and the control had been placed beside the uploaders inside the
"Datos y carga" expander. The job ran; the person who pressed the button saw a
crash and no result.

So this test presses it. Everything past the dispatch is faked — no GitHub, no
Sheets, no polling — because none of that is what broke. What is real is the
Streamlit render tree the click produces.
"""

import glob

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

PAGE = glob.glob("views/07_Embudo*.py")[0]

_JOB = {"job_id": "test-job", "job_type": "tableau_finding", "status": "SUCCESS",
        "progress_text": "done", "started_at": "", "updated_at": "",
        "result_summary": "TABLEAU_BAPTISMS: 32 months"}


@pytest.fixture
def fake_cloud(monkeypatch):
    """Dispatch and status become no-ops that succeed immediately."""
    from app.integrations import cloud_job_status, github_actions

    sent = {}

    def dispatch(workflow_file, inputs, ref=None):
        sent["workflow_file"] = workflow_file
        sent["inputs"] = inputs

    monkeypatch.setattr(github_actions, "dispatch_workflow", dispatch)
    monkeypatch.setattr(cloud_job_status, "create_job", lambda *a, **k: None)
    monkeypatch.setattr(cloud_job_status, "get_job", lambda job_id: dict(_JOB))
    return sent


@pytest.fixture
def empty_tabs(monkeypatch):
    monkeypatch.setattr("app.db.sheets_client._read_tab_cached",
                        lambda tab_name, header_marker=None: pd.DataFrame())


def _run() -> AppTest:
    at = AppTest.from_file(PAGE, default_timeout=120)
    at.session_state["pmg_lang"] = "es"
    at.run()
    assert not at.exception, at.exception
    return at


def _sync_button(at):
    for b in at.button:
        if "Tableau" in b.label:
            return b
    raise AssertionError(f"no sync button among {[b.label for b in at.button]}")


def test_pressing_sync_does_not_crash_the_page(empty_tabs, fake_cloud):
    """The regression. A status box inside an expander raises, and it raises
    AFTER the workflow has already been dispatched — the worst order."""
    at = _run()
    _sync_button(at).click().run()
    assert not at.exception, at.exception


def test_pressing_sync_dispatches_the_nightly_workflow(empty_tabs, fake_cloud):
    """Same workflow as the cron, and no inputs of its own — the window rules
    live in the runner so the button and the schedule cannot drift apart."""
    at = _run()
    _sync_button(at).click().run()
    assert fake_cloud["workflow_file"] == "tableau-reports.yml"
    assert set(fake_cloud["inputs"]) == {"job_id"}


def test_the_result_is_reported_after_the_rerun(empty_tabs, fake_cloud):
    """The job's own summary is carried through session_state and shown at the
    top of the page, because the rerun that refreshes the data also collapses
    whatever was on screen when the button was pressed."""
    at = _run()
    _sync_button(at).click().run()
    assert any("TABLEAU_BAPTISMS" in s.value for s in at.success), \
        [s.value for s in at.success]
