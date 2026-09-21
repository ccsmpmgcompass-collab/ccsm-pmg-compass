"""
tableau_finding_portal.py — drives the live Mission Finding Summary view on
Tableau Cloud and takes its exports.

**The acquisition layer, and nothing else.** Everything downstream of the file
this module hands back — parsing, merging, the provisional-window rules, the
Sheets write — already exists and is tested without a browser. Keeping the
browser confined here is what lets the plan survive its own preferred outcome:
if Tableau's site admin enables Personal Access Tokens, this file is replaced
by about thirty lines of REST and NOTHING ELSE CHANGES. See
``PLAN-2026-09-19-tableau-autosync.md`` §0.2.

What the live inspection of 2026-09-19 established, all of it load-bearing:

1. **The date window is a URL parameter.** Loading the view with
   ``?Start%20Date=2026-09-01&End%20Date=2026-09-19`` applies the filter —
   verified against the real page, which then rendered ``Start Date 9/1/2026``
   and ``Total People Baptized 19``. ISO dates are accepted even though the
   control displays M/D/YYYY.

2. **The viz is canvas and the filter cards are not in the DOM at all.** Only
   the toolbar is. A runner driving the date filter by selector could never
   have worked, and driving it by pixel coordinate would have been worse than
   the selector drift this whole design avoids. (1) is what makes (2) survivable.

3. **The toolbar buttons carry Tableau's own ``data-tb-test-id`` hooks** —
   ``viz-viewer-toolbar-button-download`` and its siblings. Those are the only
   selectors here that were seen live; everything inside the download flyout
   and its dialogs is matched defensively, by test-id pattern first and then by
   visible label in English and Spanish both, because this mission's account
   renders the site in Spanish.

**Nothing here may be published.** The repo is public, so Actions logs and
artifacts are world-readable. This module takes no screenshots and its
diagnostic prints element ids and counts only — never page text, which on the
Detail view is investigator names. That is a deliberate divergence from
``imos_portal.py``, whose failure screenshots of a logged-in session are a
standing flag in the plan (§2.3).

**One exception, drawn at a host boundary:** Tableau's own sign-in page
(``sso.online.tableau.com``) may have its text read and logged, redacted. That
page is Salesforce's, it exists before any authentication, and it holds nothing
about the mission — while its message is the only thing that distinguishes a
rejected username from a hang. See ``signin_page_message``. Everything past it
is the Church IdP and then mission data, where the text-free rule stands.
"""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlencode

from app.utils.logger import get_logger

_logger = get_logger("ingestion.tableau_finding_portal")

#: Site ``churchofjesuschrist``, workbook ``MissionFindingSummaryStephen``
#: (id 2388991). A view's URL name is its sheet title with the spaces stripped.
VIEW_BASE = ("https://prod-useast-b.online.tableau.com/t/churchofjesuschrist"
             "/views/MissionFindingSummaryStephen")
SHEET_SUMMARY = "MissionFindingSummary"
SHEET_DETAIL = "MissionFindingDetail"
SHEET_RANKING = "MissionFindingRankingList"

#: Set EXPLICITLY on every load rather than trusted as a saved default. The
#: view's Mission filter is already scoped to this mission — but a default that
#: silently changes is how a mission-wide export quietly becomes an area-wide
#: one, and neither the file nor the page would look any different afterwards.
MISSION = "Chile Concepción South"

_TOOLBAR_DOWNLOAD = "[data-tb-test-id='viz-viewer-toolbar-button-download']"
_CANVAS = "canvas.tabCanvas"

# Inside the flyout and its dialogs nothing was verified live, so each step
# lists a test-id pattern first and visible labels after it. A miss raises with
# the step named and the ids actually present logged — see _click_first.
_MENU_PDF = [
    "[data-tb-test-id='download-flyout-download-pdf-MenuItem']",
    "[data-tb-test-id*='pdf' i]",
    "[role='menuitem']:has-text('PDF')",
]
_MENU_CROSSTAB = [
    "[data-tb-test-id='download-flyout-download-crosstab-MenuItem']",
    "[data-tb-test-id*='crosstab' i]",
    "[role='menuitem']:has-text('Crosstab')",
    "[role='menuitem']:has-text('referencias cruzadas')",
]
_DIALOG_CONFIRM = [
    "[data-tb-test-id*='export' i][data-tb-test-id*='button' i]",
    "[role='dialog'] button:has-text('Download')",
    "[role='dialog'] button:has-text('Descargar')",
    "button:has-text('Download')",
    "button:has-text('Descargar')",
]
_CROSSTAB_CSV = [
    "[data-tb-test-id*='csv' i]",
    "[role='dialog'] label:has-text('CSV')",
]

_VIZ_LOAD_MS = 180_000
_DOWNLOAD_MS = 300_000


# ══════════════════════════════════════════════════════════════════════════════
# PURE
# ══════════════════════════════════════════════════════════════════════════════

def view_url(sheet: str, start: date | None = None, end: date | None = None,
             mission: str = MISSION) -> str:
    """The view's URL with the window and the mission applied as parameters.

    ``Start Date``/``End Date`` are the workbook's own typed parameters and
    ``Mission`` is a filter field; Tableau takes both the same way, as
    percent-encoded ``name=value`` pairs. Spaces encode as ``%20`` rather than
    ``+`` because ``%20`` is the form verified live.

    Pure, and separately testable — this string IS the entire date-filter
    mechanism, so it is the one part of acquisition worth a unit test.
    """
    params = {}
    if start is not None:
        params["Start Date"] = start.isoformat()
    if end is not None:
        params["End Date"] = end.isoformat()
    if mission:
        params["Mission"] = mission
    if not params:
        return f"{VIEW_BASE}/{sheet}"
    return f"{VIEW_BASE}/{sheet}?" + urlencode(params, quote_via=quote)


# ══════════════════════════════════════════════════════════════════════════════
# BROWSER
# ══════════════════════════════════════════════════════════════════════════════

def _inventory(page, label: str) -> None:
    """Log the test-ids and element counts present, and NOT the text.

    ``imos_portal`` answers "why did this step fail" with a screenshot; this
    runner cannot, because its screenshots would be published (§2.3). Ids and
    counts are enough to re-aim a selector and carry no data about anybody.
    """
    try:
        ids = page.eval_on_selector_all(
            "[data-tb-test-id]",
            "els => [...new Set(els.map(e => e.getAttribute('data-tb-test-id')))]",
        )
    except Exception:
        ids = []
    _logger.error(f"---- TABLEAU DIAGNOSTIC ({label}) ----")
    _logger.error(f"page: {page.url.split('?')[0]}")
    _logger.error(f"data-tb-test-id present ({len(ids)}): {sorted(ids)[:60]}")
    try:
        _logger.error(f"canvases={page.locator(_CANVAS).count()} "
                      f"dialogs={page.locator('[role=dialog]').count()} "
                      f"menuitems={page.locator('[role=menuitem]').count()}")
    except Exception:
        pass
    _logger.error("---- END DIAGNOSTIC ----")


def _first_visible(page, selectors: list, timeout_ms: int = 5000):
    """The first selector in priority order that is actually visible.

    Deliberately not a comma-unioned locator with ``.first``: that picks
    whichever match comes first in DOM order regardless of which selector was
    wanted, which is the bug that put a username into an unrelated search box
    during IMOS's live testing.
    """
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def _click_first(page, selectors: list, what: str, timeout_ms: int = 5000):
    loc = _first_visible(page, selectors, timeout_ms)
    if loc is None:
        _inventory(page, what)
        raise RuntimeError(
            f"Tableau: could not find {what}. The selector list for this step "
            f"is in tableau_finding_portal.py; the diagnostic above lists the "
            f"data-tb-test-id values actually present."
        )
    loc.click(timeout=timeout_ms * 3)
    return loc


#: Tableau's own sign-in host. The one page in this flow whose text is safe to
#: log: it is Salesforce's, it exists before any authentication, and it holds
#: nothing about the mission. Everything after it is the Church IdP and then the
#: mission's own data, where the text-free rule stands.
_SIGNIN_HOST = "sso.online.tableau.com"

_EMAILISH = re.compile(r"[\w.+-]+@[\w.-]+|\b\d{5,}\b")


def redact_identifiers(text: str, limit: int = 240) -> str:
    """Anything that could identify a person, masked, and the rest truncated.

    Email addresses and long digit runs are the two shapes a sign-in page can
    echo back — usually the value that was just typed into it. The message
    around them ("Enter a valid email", "We couldn't find an account") is what
    is actually diagnostic, and it is generic.
    """
    return _EMAILISH.sub("<redacted>", " ".join(str(text or "").split()))[:limit]


def signin_page_message(url: str, text: str) -> str:
    """The sign-in page's own message, or '' when we are no longer on it.

    Pure, so the host rule that decides whether text may be read at all is
    testable without a browser.
    """
    if _SIGNIN_HOST not in str(url or ""):
        return ""
    return redact_identifiers(text)


def _await_handoff(page, seconds: int = 20) -> None:
    """Wait for the email step to hand off, and say so plainly when it doesn't.

    Submitting the email should do one of two things: bring up a password box,
    or leave Tableau's sign-in host for the IdP. When neither happens the email
    was rejected and **the page is still sitting there saying why** — so read it
    rather than waiting three minutes for a viz toolbar that was never coming.

    This is what run #5 (2026-09-21) spent 180 seconds not learning. The field
    is labelled *Username* but validates as an email: a Church username in
    CCSM_TABLEAU_USERNAME produces "Enter a valid email." and a page that never
    moves, which is indistinguishable from a hang unless somebody reads it.
    """
    for _ in range(seconds):
        if page.locator("input[type='password']:visible").count():
            return
        if _SIGNIN_HOST not in page.url:
            return
        page.wait_for_timeout(1000)

    try:
        message = signin_page_message(page.url, page.inner_text("body"))
    except Exception:
        message = ""
    _inventory(page, "email_step_stuck")
    raise RuntimeError(
        f"Tableau did not accept CCSM_TABLEAU_USERNAME — the sign-in page never "
        f"handed off to Church SSO. It says: \"{message or 'nothing readable'}\". "
        f"That box is labelled Username but is validated as an EMAIL ADDRESS, so "
        f"a Church username or member id will always stop here."
    )


def _login(page, username: str, password: str) -> None:
    """Two hops: Tableau's email-first page, then Church SSO.

    The sign-in page was read on 2026-09-19 through a browser with no session
    of its own (no credentials entered, nothing submitted): an unauthenticated
    view URL lands on ``sso.online.tableau.com/public/idp/SSO``, titled "Login |
    Tableau Cloud", carrying exactly ``input#email[name=email]``, a "remember"
    checkbox and ``button#login-submit``. **There is no password field there** —
    the email identifies the org and Tableau hands off to its IdP, which for
    this site is Church SSO, the same Okta shape ``imos_portal`` meets. So the
    password selectors below belong to the SECOND page, not this one, and the
    "remember" checkbox is deliberately left alone.

    The viz toolbar is the success test. Nothing else leaves it missing for
    three minutes, so a timeout here means the credentials were refused or a
    second factor appeared.
    """
    user_box = _first_visible(page, [
        "input#email[name='email']",          # Tableau's own page, seen live
        "input[name='identifier']",           # Okta
        "input[autocomplete='username']:visible",
        "input[type='email']:visible",
    ], timeout_ms=8000)
    if user_box:
        user_box.fill(username)
        submit = _first_visible(page, ["button#login-submit"], timeout_ms=3000)
        if submit:
            submit.click(timeout=15_000)
        else:
            user_box.press("Enter")
        _logger.info("Username submitted")
        _await_handoff(page)

    pw_box = _first_visible(page, [
        "input[name='credentials.passcode']",
        "input[type='password']:visible",
    ], timeout_ms=15_000)
    if pw_box:
        pw_box.fill(password)
        pw_box.press("Enter")
        _logger.info("Password submitted")
        page.wait_for_timeout(4000)

    try:
        page.wait_for_selector(_TOOLBAR_DOWNLOAD, state="visible",
                               timeout=_VIZ_LOAD_MS)
    except Exception:
        _inventory(page, "login_stuck")
        raise RuntimeError(
            "Tableau sign-in could not be confirmed — the viz toolbar never "
            "appeared. Check CCSM_TABLEAU_USERNAME / CCSM_TABLEAU_PASSWORD, "
            "and whether the account has started asking for a second factor."
        )
    _logger.info("Tableau sign-in confirmed (viz toolbar present).")


@contextmanager
def tableau_session(username: str, password: str, headless: bool = True):
    """One browser, one sign-in, yielding the page every download reuses.

    A context manager because a nightly run takes three exports — two summary
    windows and the full Detail — and signing in three times is three times the
    chance of tripping whatever rate limit or step-up prompt the IdP keeps in
    reserve.

    **Sign-in happens on the bare view URL, never on a parameterised one.** An
    unauthenticated load bounces through two redirects before coming back, and
    nothing guarantees a query string survives that round trip. Every windowed
    navigation therefore happens afterwards, on a session that is already
    authenticated, where the parameters were verified to apply.

    ``playwright`` is imported inside the function so that importing this module
    (and unit-testing ``view_url``) never requires the browser stack.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        try:
            page.goto(view_url(SHEET_SUMMARY), wait_until="domcontentloaded",
                      timeout=90_000)
            page.wait_for_timeout(4000)
            _login(page, username, password)
            yield page
        finally:
            browser.close()


def _load_window(page, sheet: str, start: date | None, end: date | None) -> None:
    """Navigate to one sheet with one window applied, and wait for it to draw."""
    _logger.info(f"Loading {sheet} for {start} to {end}")
    page.goto(view_url(sheet, start, end), wait_until="domcontentloaded",
              timeout=90_000)
    page.wait_for_selector(_TOOLBAR_DOWNLOAD, state="visible", timeout=_VIZ_LOAD_MS)
    try:
        page.wait_for_selector(_CANVAS, state="attached", timeout=_VIZ_LOAD_MS)
    except Exception:
        # A sheet that draws no marks for its window still exports, and the
        # export itself is what gets verified downstream, so this is a warning
        # rather than a failure.
        _logger.warning(f"{sheet}: no viz canvas after load — continuing to export")
    # Tableau paints progressively and the toolbar goes live before the marks
    # settle. The export reflects what the server holds rather than what is
    # painted, so this wait is politeness, and short for that reason.
    page.wait_for_timeout(5000)


def _take_download(page, output_dir: Path, stem: str, confirm) -> Path:
    with page.expect_download(timeout=_DOWNLOAD_MS) as dl_info:
        confirm()
    download = dl_info.value
    suffix = Path(download.suggested_filename).suffix or ".bin"
    out_path = Path(output_dir) / f"{stem}_{int(time.time())}{suffix}"
    download.save_as(str(out_path))
    _logger.info(f"Downloaded {out_path.name} ({out_path.stat().st_size} bytes)")
    return out_path


def download_summary_pdf(page, start: date, end: date, output_dir: Path) -> Path:
    """The Mission Finding Summary as a PDF, for one window.

    A PDF and not a data export on purpose: it is the format the mission's 31
    stored months came from, ``tableau_summary_parser`` cross-checks two
    independently-laid-out regions of it against each other before returning a
    number, and — the part that matters here — **it prints its own window**.
    That is what lets the runner verify the URL parameter actually took effect
    without ever reading the canvas.
    """
    _load_window(page, SHEET_SUMMARY, start, end)
    _click_first(page, [_TOOLBAR_DOWNLOAD], "the toolbar's Download button")
    page.wait_for_timeout(1000)
    _click_first(page, _MENU_PDF, "the 'PDF' item in the Download menu")
    page.wait_for_timeout(1500)
    confirm = _first_visible(page, _DIALOG_CONFIRM, timeout_ms=8000)
    if confirm is None:
        _inventory(page, "pdf_dialog")
        raise RuntimeError("Tableau: the PDF dialog's Download button was not found.")
    return _take_download(page, output_dir, f"summary_{start}_{end}",
                          lambda: confirm.click(timeout=15_000))


def download_crosstab(page, sheet: str, start: date | None, end: date | None,
                      output_dir: Path) -> Path:
    """One sheet's data as a crosstab file, CSV when the dialog offers it.

    CSV is preferred over Excel only because ``read_tabular`` reads both and a
    90,000-row CSV needs no openpyxl; when the option cannot be found the
    dialog's own default is accepted rather than failing a run over a file
    format that works either way.
    """
    _load_window(page, sheet, start, end)
    _click_first(page, [_TOOLBAR_DOWNLOAD], "the toolbar's Download button")
    page.wait_for_timeout(1000)
    _click_first(page, _MENU_CROSSTAB, "the 'Crosstab' item in the Download menu")
    page.wait_for_timeout(2000)

    csv_choice = _first_visible(page, _CROSSTAB_CSV, timeout_ms=4000)
    if csv_choice is None:
        _logger.info("Crosstab: no CSV option found — taking the dialog's default")
    else:
        try:
            csv_choice.click(timeout=5000)
        except Exception:
            _logger.warning("Crosstab: CSV option found but not clickable — "
                            "taking the dialog's default format")

    confirm = _first_visible(page, _DIALOG_CONFIRM, timeout_ms=8000)
    if confirm is None:
        _inventory(page, "crosstab_dialog")
        raise RuntimeError("Tableau: the Crosstab dialog's Download button was not found.")
    return _take_download(page, output_dir, sheet.lower(),
                          lambda: confirm.click(timeout=15_000))
