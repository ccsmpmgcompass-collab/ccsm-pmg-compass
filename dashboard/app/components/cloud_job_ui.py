"""cloud_job_ui.py — shared Streamlit UI for dispatching a GitHub Actions
workflow and polling CLOUD_JOB_STATUS until it finishes. Used by the
Tableau Reports, Transfer, and Referral scraper "Run" buttons so all three
share one polling/timeout/error-display implementation instead of each
page re-inventing it.
"""
import time
import uuid

import streamlit as st

from app.i18n import t
from app.integrations import cloud_job_status, github_actions

_POLL_INTERVAL_S = 3
_TIMEOUT_S = 1200  # 20 minutes


class CloudJobTimeout(Exception):
    pass


class CloudJobFailed(Exception):
    def __init__(self, result_summary: str):
        self.result_summary = result_summary
        super().__init__(result_summary)


def _poll_until_terminal(job_id: str, on_tick=None,
                          poll_interval_s: float = _POLL_INTERVAL_S,
                          timeout_s: float = _TIMEOUT_S,
                          sleep=time.sleep, now=time.monotonic) -> dict:
    """Pure polling loop (no Streamlit calls) — unit-testable with fake
    get_job/sleep/now. Returns the terminal job dict on SUCCESS; raises
    CloudJobFailed on ERROR or CloudJobTimeout if the deadline passes."""
    deadline = now() + timeout_s
    while True:
        job = cloud_job_status.get_job(job_id)
        if job is not None:
            if on_tick:
                on_tick(job)
            if job["status"] == "SUCCESS":
                return job
            if job["status"] == "ERROR":
                raise CloudJobFailed(job.get("result_summary", "Unknown error"))
        if now() >= deadline:
            raise CloudJobTimeout(f"Job {job_id} did not finish within {timeout_s:.0f}s")
        sleep(poll_interval_s)


def _format_elapsed(seconds: float) -> str:
    """mm:ss for the in-place progress line — never re-derive this inline,
    a poll tick every few seconds makes an off-by-one here show up fast."""
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _progress_message(job: dict, elapsed_s: float) -> str:
    """The in-place progress line's text — pulled out of on_tick() so it's
    unit-testable without a running Streamlit script. Worth it: an earlier
    version passed status_text= as a t() kwarg, which collides with t()'s
    own first parameter (also named `text`) and raised TypeError only when
    actually clicked in a browser — no test caught it because none of them
    called t() through this path."""
    status_text = job.get("progress_text", "") or t("Working...")
    return t("{status_text} ({elapsed} elapsed)",
              status_text=status_text, elapsed=_format_elapsed(elapsed_s))


def run_cloud_job(job_type: str, workflow_file: str, dispatch_inputs: dict,
                   running_label: str = "Running in the cloud...",
                   timeout_s: float = _TIMEOUT_S) -> dict:
    """Dispatches workflow_file on GitHub Actions and blocks (showing a
    Streamlit status box) until CLOUD_JOB_STATUS shows SUCCESS/ERROR or the
    poll times out. Returns the terminal job dict on success.

    timeout_s defaults to 20 minutes (fine for Transfer/Referral); pass a
    larger value for jobs with a longer realistic runtime, e.g. the Tableau
    Quarterly Reports full run (workflow's own timeout-minutes is the
    ultimate ceiling — keep this comfortably under that)."""
    job_id = str(uuid.uuid4())
    cloud_job_status.create_job(job_id, job_type)
    github_actions.dispatch_workflow(workflow_file, {**dispatch_inputs, "job_id": job_id})

    with st.status(running_label, expanded=True) as box:
        # A single placeholder, updated in place — box.write() here would
        # append a fresh line on every 3-second tick instead of replacing
        # the last one, so a job that sits at the same step for a while
        # renders a wall of identical "Working..." lines.
        progress = st.empty()
        start = time.monotonic()

        def on_tick(job: dict) -> None:
            progress.write(_progress_message(job, time.monotonic() - start))

        try:
            job = _poll_until_terminal(job_id, on_tick=on_tick, timeout_s=timeout_s)
        except CloudJobFailed as e:
            box.update(label="Failed", state="error")
            st.error(t("Cloud job failed: {summary}", summary=e.result_summary))
            raise
        except CloudJobTimeout as e:
            box.update(label="Still running", state="error")
            st.warning(
                t("{error} — check the GitHub Actions tab; it may still finish.",
                  error=str(e))
            )
            raise

        box.update(label="Done", state="complete")
        return job
