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

**Two exceptions, both narrow.** Tableau's own sign-in page
(``sso.online.tableau.com``) may have its text read and logged, redacted: that
page is Salesforce's, it exists before any authentication, and it holds nothing
about the mission, while its message is the only thing that distinguishes a
rejected username from a hang. See ``signin_page_message``.

On the Church IdP, **the error banner alone** may be read — the elements
matching ``_ERROR_REGIONS``, never the page body, and redacted the same way.
Added 2026-09-21 after four runs failed at Okta's password step without anyone
being able to say what Okta objected to; the operator was certain of the
password and the logs could not confirm or refute him. Those banners are system
messages ("Unable to sign in"), the surrounding page is what names the person,
and the two are different elements. Everything else on that host, and all
mission data past it, stays unread.
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

#: The host the signed-in app lives on. Reaching it means sign-in is OVER, and
#: nothing on it is a login step — run #12 signed in successfully and then typed
#: the Tableau email into a field belonging to the app itself, because the login
#: loop was still looking for boxes to fill.
_VIZ_HOST = VIEW_BASE.split("//")[1].split("/")[0]

#: Tableau Cloud's post-login announcement, which lands on top of the view the
#: first time an account signs in on a new browser — and a container is a new
#: browser every single time. It is a floating dialog with a glass backdrop
#: (``tabcld-postlogin-id-Dialog-Glass``), so the viz never renders behind it
#: and the toolbar never appears: exactly the symptom run #12 died of, five
#: minutes after a sign-in that had worked perfectly.
_POST_LOGIN_DIALOG = "[data-tb-test-id*='postlogin' i], [data-tb-test-id*='Dialog-Glass' i]"

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
    # Whether the page is SHOWING AN ERROR, without reading what it says. On the
    # Church IdP the text is off limits (it names the person signing in), but
    # this answers the question that matters after a password is submitted: was
    # it refused, or is the page simply still thinking?
    #
    # **Counting the regions was not enough.** Okta ships empty ``aria-live``
    # containers as part of its widget, so run #9's "error regions: 2" was
    # consistent with a refusal AND with nothing having happened at all — and it
    # was read as the former, against an operator who was sure of the password.
    # What separates them is whether any of those regions has TEXT IN IT, which
    # is a count, not a quotation.
    total, speaking = 0, 0
    try:
        regions = page.locator(_ERROR_REGIONS)
        total = regions.count()
        speaking = len(error_banner_texts(page))
    except Exception:
        pass
    _logger.error(f"error regions: {total} present, {speaking} with any text")
    # The form's SHAPE, across every frame. On a Tableau page the test-ids above
    # are the whole story; on the Church IdP there are none at all, and without
    # this a stuck sign-in reports an empty list and teaches nothing (run #7).
    # Attributes only — type, name, autocomplete, id — never values or labels.
    for i, fr in enumerate(page.frames):
        try:
            fields = fr.eval_on_selector_all(
                "input, button[type=submit], button[id]",
                """els => els.slice(0, 12).map(e => e.tagName.toLowerCase() + '['
                     + (e.type || '') + '|' + (e.name || '') + '|'
                     + (e.getAttribute('autocomplete') || '') + '|'
                     + (e.id || '') + ']')""",
            )
        except Exception:
            fields = []
        try:
            tb = fr.eval_on_selector_all(
                "[data-tb-test-id]",
                "els => [...new Set(els.map(e => e.getAttribute('data-tb-test-id')))]")
        except Exception:
            tb = []
        # Every frame is logged, empty or not. The viz lives in one of them and a
        # frame skipped for having no form fields is exactly the frame that
        # matters here.
        _logger.error(f"  frame[{i}] {fr.url.split('?')[0][:80]}: "
                      f"fields={fields} test-ids={len(tb)}{sorted(tb)[:12]}")
    _logger.error("---- END DIAGNOSTIC ----")


def _first_visible(page, selectors: list, timeout_ms: int = 5000):
    """The first selector in priority order that is actually visible, IN ANY FRAME.

    Deliberately not a comma-unioned locator with ``.first``: that picks
    whichever match comes first in DOM order regardless of which selector was
    wanted, which is the bug that put a username into an unrelated search box
    during IMOS's live testing.

    **And deliberately not ``page.locator``, which only ever searches the main
    frame.** The viz — canvas, toolbar and all — renders inside a same-origin
    iframe, a fact the plan recorded on day one (§2.2) and this module then spent
    runs #12 through #15 ignoring: every one of them signed in, reached the view
    and waited three minutes for a toolbar that was on screen the whole time, one
    frame away. Selector first, frames within it, so priority still means what it
    says.
    """
    for sel in selectors:
        for frame in page.frames:
            try:
                loc = frame.locator(sel).first
                if loc.count() and loc.is_visible(timeout=timeout_ms):
                    return loc
            except Exception:
                continue
    return None


def _present(page, selector: str) -> bool:
    """Whether a selector matches anything at all, in any frame."""
    for frame in page.frames:
        try:
            if frame.locator(selector).count():
                return True
        except Exception:
            continue
    return False


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


#: The error banner, and only the error banner. Okta's own callout classes plus
#: the ARIA role. Used both to COUNT regions and to read them — see the module
#: docstring for why this one element on the IdP is readable when the page
#: around it is not.
_ERROR_REGIONS = ("[role=alert], [data-se=callout], .infobox-error, "
                  ".okta-form-infobox-error")


def error_banner_texts(page, limit: int = 8) -> list:
    """The non-empty error banners on the page, redacted.

    A system message ("Unable to sign in", "We can't verify that") is what tells
    a refused credential apart from an unknown user or a second factor, and four
    runs failed without anyone being able to say which. The surrounding page is
    what names the person; this reads the banner elements only, and still masks
    anything email- or id-shaped inside them.
    """
    out = []
    try:
        regions = page.locator(_ERROR_REGIONS)
        for i in range(min(regions.count(), limit)):
            try:
                text = (regions.nth(i).inner_text() or "").strip()
            except Exception:
                continue
            if text:
                out.append(redact_identifiers(text, limit=160))
    except Exception:
        pass
    return out


def signin_page_message(url: str, text: str) -> str:
    """The sign-in page's own message, or '' when we are no longer on it.

    Pure, so the host rule that decides whether text may be read at all is
    testable without a browser.
    """
    if _SIGNIN_HOST not in str(url or ""):
        return ""
    return redact_identifiers(text)


#: What a sign-in step can look like. Order matters in ``next_login_step``.
_USER_FIELDS = (
    "input#email[name='email']",            # Tableau's own page, seen live
    "input[name='identifier']",             # Okta, id.churchofjesuschrist.org
    "input[name='username']:visible",
    "input[autocomplete='username']:visible",
    "input[type='email']:visible",
)
_PASS_FIELDS = (
    "input[name='credentials.passcode']",   # Okta (also its OTP field — see below)
    "input[type='password']:visible",
)
_SUBMIT_BUTTONS = (
    "button#login-submit",                  # Tableau's page, seen live
    "input[type='submit']:visible",
    "button[type='submit']:visible",
)

#: How long a box we already answered may stay on screen before we call it a
#: rejection rather than a page still thinking about it. Okta leaves the
#: password field up while it verifies, so this cannot be instant — and calling
#: a slow verification "stuck" costs a whole run, while waiting a few seconds
#: too long costs nothing.
_STEP_SETTLE_S = 25

#: The whole sign-in, end to end. Three steps and two redirects fit easily;
#: anything longer is a prompt we do not understand and should be reported.
_LOGIN_BUDGET_S = 150


def credentials_for(url: str, tableau: tuple, church: tuple) -> tuple:
    """Which pair of credentials the page in front of us wants.

    **Tableau's page and the Church IdP do not want the same thing**, which
    cost runs 8-11. Tableau's box takes an EMAIL ADDRESS (it validates as one).
    Okta at ``id.churchofjesuschrist.org`` takes a CHURCH ACCOUNT USERNAME,
    which is a different string for most people — and because Okta shows the
    password screen even for usernames it does not recognise (so that nobody can
    test which ones exist), sending the email to both produces a failure at the
    PASSWORD step reading "Invalid username and password combination". Which is
    exactly what it said, about a password that was never the problem.

    Returns ``(username, password, label)``; the label is for the log, so a run
    says which pair it used without saying what they are.
    """
    if _SIGNIN_HOST in str(url or ""):
        return tableau[0], tableau[1], "Tableau"
    return church[0], church[1], "Church"


def next_login_step(*, toolbar: bool, password: bool, username: bool,
                    answered: set, step: str, settled: bool) -> str:
    """What to do about the page in front of us: the sign-in flow's whole logic,
    lifted out of the browser so it can be tested.

    Returns ``"done"``, ``"password"``, ``"username"``, ``"stuck"`` or
    ``"wait"``. ``answered`` holds ``(kind, step)`` pairs already submitted,
    ``step`` is the current URL without its query, and ``settled`` says whether
    the field has been sitting there long enough to have been a rejection.

    Three rules, each learned the hard way:

    * **The toolbar wins.** It is the only proof of being signed in.
    * **Password before username.** A page showing both is showing a form we
      have already half-answered; the password is the live step.
    * **A box we already answered, still there and settled, is a rejection** —
      not a page to answer again. Re-submitting the same value into the same
      box is how a login loop turns into a lockout.
    """
    if toolbar:
        return "done"
    if password and ("password", step) not in answered:
        return "password"
    if username and ("username", step) not in answered:
        return "username"
    if settled and (password or username):
        return "stuck"
    return "wait"


def _submit(page, box, value: str, kind: str) -> None:
    """Put a value in and send the form, and record enough to prove it happened.

    Two things get logged, both booleans, never the value or its length: whether
    the field actually holds anything after ``fill`` (a React widget can outrun
    a fill and leave its own state empty, so a click then submits nothing), and
    whether the submit button was enabled when it was clicked.

    Without those, a form that quietly did nothing is indistinguishable from a
    credential that was refused — the ambiguity that had run #9 blaming a
    password its owner was sure of.

    Enter is pressed as well as the button being clicked. Belt and braces: some
    widgets bind one and not the other, and submitting twice is harmless because
    the first submission navigates away.
    """
    box.fill(value)
    page.wait_for_timeout(300)
    try:
        landed = bool((box.input_value() or "").strip())
    except Exception:
        landed = None
    button = _first_visible(page, list(_SUBMIT_BUTTONS), timeout_ms=2000)
    enabled = None
    if button is not None:
        try:
            enabled = button.is_enabled()
        except Exception:
            enabled = None
        button.click(timeout=15_000)
    else:
        box.press("Enter")
    _logger.info(f"{kind.capitalize()} submitted at {_host(page.url)} "
                 f"(field filled: {landed}, submit button: "
                 f"{'none found, pressed Enter' if button is None else f'enabled={enabled}'})")
    page.wait_for_timeout(3000)


def _host(url: str) -> str:
    return str(url or "").split("//")[-1].split("/")[0]


def _login(page, tableau: tuple, church: tuple) -> None:
    """Sign in, however many steps it takes, with the right pair at each host.

    **It is three steps, not two** — the thing run #7 (2026-09-21) cost us. Tableau's
    page takes an email and hands off to Church SSO at
    ``id.churchofjesuschrist.org/app/tableauonline/…/sso/saml``, and Okta then
    asks for a username and a password on SEPARATE screens. A login written as
    "fill the username box, then fill the password box" fills Tableau's email,
    arrives at Okta's username screen, finds no password on it, and waits three
    minutes for a viz that was never coming.

    So this is a loop over whatever step is on screen rather than a fixed
    script, which also covers the two-step case and any reordering. Every value
    is submitted at most once per page: ``next_login_step`` holds the rules and
    the reasons.

    **And the two hosts want different credentials** — runs 8-11. Tableau takes
    an email, the Church IdP takes a Church Account username; ``credentials_for``
    picks, and says which pair it used without saying what they are.

    The viz toolbar is the success test — the only proof that gets past every
    redirect. When the loop ends without it, the page's own field inventory is
    logged (attributes, never values or text) and the failure names the step.
    """
    answered: set = set()
    nudged: set = set()
    first_seen: dict = {}
    deadline = time.monotonic() + _LOGIN_BUDGET_S

    while time.monotonic() < deadline:
        step = page.url.split("?")[0]
        if _VIZ_HOST in page.url:
            # Signed in: this host is the application, not the IdP. Nothing here
            # is a login step, and run #12 proved the cost of pretending
            # otherwise — it typed the Tableau email into a field belonging to
            # the app. What IS here is Tableau's post-login dialog, sitting over
            # the view with a glass backdrop so the viz never draws behind it.
            dismiss_post_login_dialog(page)
            break
        pw_box = _first_visible(page, list(_PASS_FIELDS), timeout_ms=1200)
        user_box = _first_visible(page, list(_USER_FIELDS), timeout_ms=1200)
        toolbar = _present(page, _TOOLBAR_DOWNLOAD)

        marker = (step, bool(pw_box), bool(user_box))
        first_seen.setdefault(marker, time.monotonic())
        settled = time.monotonic() - first_seen[marker] >= _STEP_SETTLE_S

        action = next_login_step(toolbar=toolbar, password=bool(pw_box),
                                 username=bool(user_box), answered=answered,
                                 step=step, settled=settled)

        if action == "done":
            _logger.info("Tableau sign-in confirmed (viz toolbar present).")
            return
        user, pw, whose = credentials_for(page.url, tableau, church)
        if action == "password":
            _submit(page, pw_box, pw, f"{whose} password")
            answered.add(("password", step))
            continue
        if action == "username":
            _submit(page, user_box, user, f"{whose} username")
            answered.add(("username", step))
            continue
        if action == "stuck":
            # One nudge before giving up: press Enter in the box we already
            # answered. If the click went to a button the widget does not listen
            # to, this submits; if the credential was really refused, nothing
            # changes and the next pass reports it with a run's worth of
            # evidence rather than a guess.
            box = pw_box or user_box
            if step not in nudged and box is not None:
                nudged.add(step)
                _logger.info(f"Step did not move at {_host(page.url)} — "
                             f"pressing Enter once before reporting it stuck")
                try:
                    box.press("Enter")
                except Exception:
                    pass
                first_seen.pop(marker, None)
                page.wait_for_timeout(4000)
                continue
            _stuck(page, pw_box is not None)
        page.wait_for_timeout(2000)

    if not wait_for_toolbar(page, _VIZ_LOAD_MS):
        _stuck(page, False)
    _logger.info("Tableau sign-in confirmed (viz toolbar present).")


def wait_for_toolbar(page, timeout_ms: int) -> bool:
    """Wait for the viz toolbar, clearing whatever Tableau puts in front of it.

    **Not a single wait_for_selector**, which is what runs #12 and #14 did: they
    dismissed the post-login dialog once, a second before Tableau actually
    rendered it, and then blocked for three minutes behind the dialog they had
    already "handled". The dialog arrives on its own schedule after the SAML
    redirect, so it has to be watched for, not checked for.

    One reload is spent halfway through. A dialog that survives Escape and its
    own close button usually does not survive a fresh page load, and by then the
    session cookie exists so the reload costs nothing but a few seconds.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    reloaded = False
    while time.monotonic() < deadline:
        if _present(page, _TOOLBAR_DOWNLOAD):
            return True
        dismiss_post_login_dialog(page, tries=1)
        remaining = deadline - time.monotonic()
        if not reloaded and remaining < timeout_ms / 2000:
            reloaded = True
            _logger.info("Toolbar still absent — reloading the view once")
            try:
                page.reload(wait_until="domcontentloaded", timeout=90_000)
            except Exception:
                pass
        page.wait_for_timeout(2000)
    return False


def _stuck(page, on_password: bool) -> None:
    """Report a sign-in that stopped moving, and say where.

    ``signin_page_message`` supplies Tableau's own wording when we are still on
    its page (that host, redacted, is the one place text may be read); on the
    Church IdP the field inventory in ``_inventory`` is what there is to go on,
    and an OTP box showing up where a password should be is what a second
    factor looks like from here.
    """
    try:
        message = signin_page_message(page.url, page.inner_text("body"))
    except Exception:
        message = ""
    banners = error_banner_texts(page)
    if banners and not message:
        message = " / ".join(banners)
    _inventory(page, "login_stuck")
    where = _host(page.url)
    raise RuntimeError(
        f"Tableau sign-in stopped at {where}: the "
        f"{'password' if on_password else 'username'} step was answered, Enter "
        f"was pressed, and the page did not move on."
        + (f' It says: "{message}".' if message else
           " Read the diagnostic above before blaming a credential: 'field "
           "filled: False' means the value never reached the widget and this is "
           "our bug; '0 with any text' means no error was shown, so nothing was "
           "refused either. **And a failure at the PASSWORD step is not proof "
           "the password is wrong** — Okta shows the password screen even for a "
           "username it does not recognise, precisely so that nobody can test "
           "which usernames exist. A second factor looks the same from here too: "
           "its OTP box shares a name with the password box.")
    )


@contextmanager
def tableau_session(username: str, password: str, headless: bool = True,
                    church_username: str = "", church_password: str = ""):
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
            _login(page, (username, password),
                   (church_username or username, church_password or password))
            yield page
        finally:
            browser.close()


def dismiss_post_login_dialog(page, tries: int = 3) -> bool:
    """Close Tableau's post-login announcement, if one is covering the view.

    Returns True when something was dismissed. Escape first, because that is the
    one action whose meaning is unambiguous: the dialog's buttons are unlabelled
    ``tab-shared-widget-…`` submits, one of which may well be "Learn more" and
    navigate away from the view entirely. Only if Escape fails do we click, and
    then the LAST button, Tableau's slot for the confirming action.

    The "don't show this again" checkbox is deliberately left alone. It would
    save a few seconds a night by changing a preference on the mission's own
    account, which is not this job's to change.
    """
    dismissed = False
    for _ in range(tries):
        try:
            if not _present(page, _POST_LOGIN_DIALOG):
                return dismissed
        except Exception:
            return dismissed
        _logger.info("Post-login dialog is covering the view — dismissing it")
        page.keyboard.press("Escape")
        page.wait_for_timeout(1500)
        dismissed = True
        try:
            if not _present(page, _POST_LOGIN_DIALOG):
                _logger.info("Dialog closed on Escape")
                return dismissed
        except Exception:
            return dismissed
        # Escape did not take. Try the close control, then the dialog's own last
        # button. ``-Button`` is a real test-id on this page — Tableau's floater
        # gives its close control an empty prefix — and it appears in the
        # inventory of every run that has reached this screen.
        for selector in ("[data-tb-test-id='-Button']",
                         "[data-tb-test-id*='Dialog'] button",
                         "[data-tb-test-id*='Dialog-Body'] button, "
                         "[data-tb-test-id*='Dialog-Content'] button"):
            try:
                candidates = page.locator(selector)
                if not candidates.count():
                    continue
                candidates.last.click(timeout=8000)
                _logger.info(f"Clicked dialog control: {selector}")
                page.wait_for_timeout(1500)
                if not _present(page, _POST_LOGIN_DIALOG):
                    return dismissed
            except Exception:
                continue
    return dismissed


def _load_window(page, sheet: str, start: date | None, end: date | None) -> None:
    """Navigate to one sheet with one window applied, and wait for it to draw."""
    _logger.info(f"Loading {sheet} for {start} to {end}")
    page.goto(view_url(sheet, start, end), wait_until="domcontentloaded",
              timeout=90_000)
    if not wait_for_toolbar(page, _VIZ_LOAD_MS):
        _inventory(page, f"{sheet}_never_drew")
        raise RuntimeError(
            f"{sheet} never showed its toolbar for {start}..{end} — the view did "
            f"not finish loading. The diagnostic above lists what was on screen.")
    if not _present(page, _CANVAS):
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
