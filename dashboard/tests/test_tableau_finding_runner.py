"""Tests for the nightly Tableau pull — the parts of it that are not a browser.

Acquisition itself cannot be tested without the live site, which is exactly why
everything that decides anything lives outside it: which windows a run asks
for, the URL that carries them, whether the file that came back is the one that
was asked for, and whether the process can even start in the container it runs
in. The Playwright module is a thin shell over those decisions.
"""

import ast
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.ingestion import tableau_finding_portal as portal
from app.ingestion.tableau_finding_runner import (
    DETAIL_FLOOR, capture_windows, detail_window, guard_detail_replacement,
    verify_window,
)
from app.ingestion.tableau_summary_parser import MonthlySummary
from app.ingestion.tableau_upload import is_provisional

ROOT = Path(__file__).resolve().parent.parent  # dashboard/


def _summary(month: str, start: str, end: str, baptized: int = 19) -> MonthlySummary:
    return MonthlySummary(month=month, start_date=start, end_date=end,
                          people_found=0, people_referred=0,
                          people_being_taught=0, multiple_lessons=0,
                          church_attendance=0, baptism_goal_date_set=0,
                          baptized=baptized)


# ── the URL, which IS the date filter ─────────────────────────────────────────

def test_view_url_matches_the_form_verified_live():
    """%20 for the space, ISO dates, both parameters. This exact string shape
    was loaded against the real view on 2026-09-19 and applied the filter."""
    url = portal.view_url(portal.SHEET_SUMMARY, date(2026, 9, 1), date(2026, 9, 19))
    assert "Start%20Date=2026-09-01" in url
    assert "End%20Date=2026-09-19" in url
    assert url.startswith(portal.VIEW_BASE + "/" + portal.SHEET_SUMMARY + "?")


def test_view_url_always_names_the_mission():
    """Never trust the saved default: a filter that silently changes turns a
    mission export into an area export and nothing about the file looks different."""
    assert "Mission=" in portal.view_url(portal.SHEET_DETAIL)
    assert "Chile" in portal.view_url(portal.SHEET_DETAIL)


def test_view_url_omits_dates_it_was_not_given():
    url = portal.view_url(portal.SHEET_DETAIL)
    assert "Start%20Date" not in url and "End%20Date" not in url


# ── what a stuck sign-in is allowed to tell us ────────────────────────────────

def test_the_signin_pages_own_message_is_readable():
    """Tableau's sign-in page is Salesforce's, pre-authentication, and holds
    nothing about the mission — and its message is the only thing that separates
    a rejected username from a hang. Run #5 spent 180 seconds not reading it."""
    msg = portal.signin_page_message(
        "https://sso.online.tableau.com/public/idp/SSO",
        "Sign in to Tableau Cloud\nEnter a valid email.\nUsername")
    assert "Enter a valid email." in msg


def test_no_text_is_read_once_we_leave_that_host():
    """Past the sign-in page it is the Church IdP and then investigator data, on
    a public repo. The boundary is the host, not a judgement call at the call
    site."""
    assert portal.signin_page_message(
        "https://prod-useast-b.online.tableau.com/t/churchofjesuschrist/views/x",
        "Ana Gómez  Baptized 2026-09-04") == ""
    assert portal.signin_page_message("https://okta.churchofjesuschrist.org/",
                                      "Welcome back") == ""


def test_identifiers_are_masked_out_of_whatever_is_read():
    """A sign-in page's error usually quotes the value typed into it."""
    out = portal.redact_identifiers(
        "'someone@missionary.org' is not valid, id 425060123 unknown")
    assert "missionary.org" not in out and "425060123" not in out
    assert "is not valid" in out


def test_a_read_message_cannot_run_away_with_the_log():
    assert len(portal.redact_identifiers("x" * 5000)) <= 240


# ── the sign-in is a loop, because the flow is three steps ────────────────────

def _step(**kw):
    base = dict(toolbar=False, password=False, username=False,
                answered=set(), step="https://idp/", settled=False)
    base.update(kw)
    return portal.next_login_step(**base)


def test_the_toolbar_ends_the_sign_in_whatever_else_is_on_screen():
    """It is the only proof of being signed in; everything else is a guess."""
    assert _step(toolbar=True, password=True, username=True, settled=True) == "done"


def test_tableaus_email_page_is_a_username_step():
    assert _step(username=True) == "username"


def test_oktas_username_screen_is_answered_before_its_password_screen():
    """Run #7 died here. Tableau takes an email, hands off to Church SSO, and
    Okta then asks for a username and a password on SEPARATE screens — so a
    login written as "username box, then password box" arrives at Okta's
    username screen, finds no password, and waits out the viz timeout."""
    okta_user = _step(username=True, step="https://id.churchofjesuschrist.org/a")
    assert okta_user == "username"
    answered = {("username", "https://id.churchofjesuschrist.org/a")}
    assert _step(password=True, username=True, answered=answered,
                 step="https://id.churchofjesuschrist.org/a") == "password"


def test_a_page_showing_both_treats_the_password_as_the_live_step():
    assert _step(password=True, username=True) == "password"


def test_an_unanswered_step_that_is_still_loading_is_waited_for():
    assert _step() == "wait"


def test_a_box_we_already_answered_is_a_rejection_not_a_second_try():
    """Re-submitting the same value into the same box is how a login loop turns
    into a lockout."""
    answered = {("password", "https://idp/")}
    assert _step(password=True, answered=answered, settled=True) == "stuck"


def test_a_just_answered_box_gets_a_moment_before_being_called_stuck():
    """Okta leaves the password field up while it verifies."""
    answered = {("password", "https://idp/")}
    assert _step(password=True, answered=answered, settled=False) == "wait"


# ── which windows a run captures ──────────────────────────────────────────────

def test_default_run_takes_the_previous_month_whole_and_this_one_to_date():
    assert capture_windows(date(2026, 9, 19)) == [
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 19)),
    ]


def test_windows_cross_the_year_boundary():
    assert capture_windows(date(2026, 1, 15), 2) == [
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 15)),
    ]


def test_february_gets_its_real_last_day():
    assert capture_windows(date(2024, 3, 5), 2)[0] == (date(2024, 2, 1), date(2024, 2, 29))


def test_the_current_window_is_provisional_and_the_previous_one_is_not():
    """The point of re-pulling two months. The finished month lands certified;
    the month in progress lands visibly partial, so the annual chart keeps
    drawing it as an open point instead of a collapse."""
    prev, curr = capture_windows(date(2026, 9, 19))
    assert not is_provisional(prev[0].strftime("%Y-%m"), prev[1].isoformat())
    assert is_provisional(curr[0].strftime("%Y-%m"), curr[1].isoformat())


def test_a_run_on_the_first_still_asks_for_a_one_day_window():
    prev, curr = capture_windows(date(2026, 9, 1))
    assert curr == (date(2026, 9, 1), date(2026, 9, 1))
    assert prev == (date(2026, 8, 1), date(2026, 8, 31))


def test_months_back_never_drops_below_one():
    assert len(capture_windows(date(2026, 9, 19), 0)) == 1


# ── the Detail window is never allowed to narrow ──────────────────────────────

def test_detail_window_reaches_back_to_the_floor_when_nothing_is_stored():
    assert detail_window(date(2026, 9, 19), None) == (DETAIL_FLOOR, date(2026, 9, 19))


def test_detail_window_never_starts_later_than_what_is_already_stored():
    """A Detail write REPLACES. Asking for less than the store holds is how 2.6
    years of history disappears in one unattended run."""
    start, _ = detail_window(date(2026, 9, 19), date(2023, 6, 1))
    assert start == date(2023, 6, 1)


# ── what may replace the Detail store ─────────────────────────────────────────

def _detail(dates: list) -> pd.DataFrame:
    return pd.DataFrame({"event_date_selected": dates,
                         "latest_zone_name": ["Concepción"] * len(dates)})


def test_a_full_export_replaces_the_store():
    stored = _detail(["2024-01-05", "2026-09-18"])
    guard_detail_replacement(stored, _detail(["2024-01-05", "2026-09-19"]), {})


def test_a_narrower_export_is_refused_outright():
    """No "Replace anyway" here — the page offers that because a human is
    standing in front of it. A nightly run has nobody to ask."""
    stored = _detail(["2024-01-05", "2026-09-18"])
    with pytest.raises(RuntimeError) as exc:
        guard_detail_replacement(stored, _detail(["2026-08-01", "2026-09-18"]), {})
    assert "Nothing written" in str(exc.value)


def test_an_export_of_the_wrong_sheet_is_refused_before_the_span_is_compared():
    """The dangerous case: a file with none of the milestone columns has no date
    span, so the narrower check sees nothing to lose and would let it through —
    over 2.6 years of real history."""
    stored = _detail(["2024-01-05", "2026-09-18"])
    wrong = pd.DataFrame({"latest_zone_name": ["Concepción", "Chillán"]})
    with pytest.raises(RuntimeError) as exc:
        guard_detail_replacement(stored, wrong, {"missing_expected": ["event_date_selected"]})
    assert "not the Detail view" in str(exc.value)


def test_an_empty_export_is_refused_even_with_nothing_stored():
    with pytest.raises(RuntimeError):
        guard_detail_replacement(pd.DataFrame(), pd.DataFrame(), {})


def test_the_first_ever_run_may_write_into_an_empty_store():
    guard_detail_replacement(pd.DataFrame(), _detail(["2024-01-05", "2026-09-19"]), {})


# ── the file has to be the file we asked for ──────────────────────────────────

def test_verify_window_accepts_the_window_it_asked_for():
    verify_window(_summary("2026-09", "2026-09-01", "2026-09-19"),
                  date(2026, 9, 1), date(2026, 9, 19))


def test_verify_window_refuses_a_file_for_different_days():
    """The URL parameter is the whole filter mechanism, so a parameter that
    silently fails to apply must not be storable. The PDF prints its own
    window; this is where the two are compared."""
    with pytest.raises(RuntimeError) as exc:
        verify_window(_summary("2026-09", "2026-09-01", "2026-09-30"),
                      date(2026, 9, 1), date(2026, 9, 19))
    assert "Nothing stored" in str(exc.value)


def test_verify_window_refuses_a_whole_month_when_month_to_date_was_asked_for():
    with pytest.raises(RuntimeError):
        verify_window(_summary("2026-08", "2026-08-01", "2026-08-31"),
                      date(2026, 9, 1), date(2026, 9, 19))


# ── it has to be able to start where it runs ──────────────────────────────────

def _imports(path: Path) -> tuple[list[str], list[str]]:
    """(every module imported anywhere, modules imported at module scope).

    The distinction is the whole rule. A module-scope import runs the moment
    the runner is loaded, so it must exist in the container. An import inside a
    function may legitimately be a fallback that never executes there —
    ``gcp_creds`` reaches for ``st.secrets`` only after the environment
    variable it actually uses in Actions has already answered.
    """
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))

    def named(node) -> list[str]:
        if isinstance(node, ast.ImportFrom):
            return [node.module] if node.module else []
        return [a.name for a in node.names]

    every, top = [], []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            every += named(node)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            top += named(node)
    return every, top


def _module_path(mod: str):
    p = ROOT / (mod.replace(".", "/") + ".py")
    if p.exists():
        return p
    p2 = ROOT / mod.replace(".", "/") / "__init__.py"
    return p2 if p2.exists() else None


def test_the_runner_reaches_no_streamlit_when_it_starts_up():
    """The nightly job runs in a Playwright container against
    requirements_cloud.txt, which has no Streamlit in it. An innocent
    `from app.db.queries import ...` added later would import sheets_client,
    import streamlit, and fail at 09:00 UTC in a log nobody is reading — so the
    rule is checked here instead of discovered there.

    This is also the reason ``app/db/tabular_io.py`` exists: the pure storage
    helpers had to be reachable from a process with no Streamlit.

    **Module scope only, and deliberately.** What breaks a cold start is what
    runs during import. A function-scope import is a different thing: in this
    graph each one is either a guarded fallback that is *expected* to fail in
    the container and be caught (``gcp_creds`` reaching for ``st.secrets`` after
    the environment variable already answered; ``area_helpers`` reaching for
    AGENT_CONFIG's timezone before falling back to America/Santiago) or a
    deliberate deferral — which is why the portal is a root here in its own
    right rather than something this walk discovers.
    """
    seen = set()
    queue = ["app.ingestion.tableau_finding_runner",
             "app.ingestion.tableau_finding_portal"]
    offenders = []
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        path = _module_path(mod)
        if path is None:
            continue
        _, top = _imports(path)
        offenders += [f"{mod} imports {m} at module scope"
                      for m in top if m.split(".")[0] == "streamlit"]
        queue += [m for m in top if m.startswith("app.")]
    assert offenders == [], offenders
    assert "app.db.tabular_io" in seen, "the runner stopped using the shared helpers"


def test_the_portal_does_not_import_playwright_until_it_is_used():
    """Importing the acquisition module must not require the browser stack —
    that is what lets every test above run, and what keeps the REST replacement
    of this file a drop-in when PATs are enabled."""
    assert not hasattr(portal, "sync_playwright")


def test_the_workflow_uploads_no_artifacts():
    """The repository is public: an Actions artifact from this job would be a
    page of investigator names, downloadable by anyone who finds the run."""
    yml = (ROOT.parent / ".github" / "workflows" / "tableau-reports.yml").read_text(
        encoding="utf-8")
    assert "upload-artifact" not in yml
