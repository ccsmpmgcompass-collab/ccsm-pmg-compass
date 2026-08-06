"""
imos_portal.py — Logs into imos.churchofjesuschrist.org and downloads the
"Organization Roster" Excel report (Reports and Surveys > Mission Office
Reports > "Organization Roster" > Excel).

Selectors below follow the same defensive, multi-fallback pattern as
tableau_reports_playwright.py's login flow (Church systems commonly share
Okta SSO) but have not yet been verified against the live portal — expect to
adjust them the first time this runs against a real login.
"""

import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.utils.logger import get_logger

_logger = get_logger("ingestion.imos_portal")

IMOS_BASE_URL = "https://imos.churchofjesuschrist.org/reports/#/all-reports"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEBUG_DIR = _REPO_ROOT / "debug"


def _screenshot(page, label: str) -> None:
    try:
        _DEBUG_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        path = _DEBUG_DIR / f"{ts}_imos_{label}.png"
        page.screenshot(path=str(path))
        _logger.info(f"Screenshot saved: {path}")
    except Exception:
        pass


def _diagnose_login_state(page) -> None:
    _logger.error("---- IMOS LOGIN-STUCK DIAGNOSTIC ----")
    try:
        _logger.error(f"URL: {page.url}")
    except Exception:
        pass
    for i, fr in enumerate(page.frames):
        try:
            inputs = fr.locator("input:visible")
            descs = []
            for j in range(min(inputs.count(), 6)):
                el = inputs.nth(j)
                descs.append(
                    (el.get_attribute("type") or "text") + ":" +
                    (el.get_attribute("name") or el.get_attribute("autocomplete") or "?")
                )
            if descs:
                _logger.error(f"  frame[{i}]: inputs={descs}")
        except Exception:
            continue
    _logger.error("---- END DIAGNOSTIC ----")


def _find_first_match(page, selectors: list, timeout_ms: int = 8000):
    """Try selectors in priority order, returning the first one that's
    actually visible — NOT a comma-unioned locator with .first, which picks
    whichever matching element appears first in DOM order regardless of
    which selector we actually wanted (this caused the username to land in
    an unrelated church.org search box during live testing)."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def _login(page, username: str, password: str) -> None:
    _logger.info("Attempting imos.churchofjesuschrist.org login...")

    try:
        user_box = _find_first_match(
            page,
            ["input[name='identifier']", "input[autocomplete='username']:visible",
             "input[type='email']:visible"],
        )
        if user_box:
            user_box.fill(username)
            user_box.press("Enter")
            _logger.info("Username submitted")
            page.wait_for_timeout(4000)
    except Exception:
        pass

    try:
        pw_box = _find_first_match(
            page,
            ["input[name='credentials.passcode']", "input[type='password']:visible"],
        )
        if pw_box:
            pw_box.fill(password)
            pw_box.press("Enter")
            _logger.info("Password submitted")
            page.wait_for_timeout(4000)
    except Exception:
        pass

    for _ in range(12):
        try:
            # Require the actual missionary portal domain + a portal-specific
            # marker, not just "some churchofjesuschrist.org page with no
            # password box" — that loose check previously treated an
            # unrelated church.org search results page as a successful login.
            if "missionary.churchofjesuschrist.org" in page.url and \
                    page.get_by_text("Missionary Portal", exact=False).count() and \
                    not page.locator("input[type='password']:visible").count():
                _logger.info("IMOS login succeeded.")
                return
        except Exception:
            pass
        page.wait_for_timeout(2000)

    _screenshot(page, "login_stuck")
    _diagnose_login_state(page)
    raise RuntimeError(
        "IMOS login failed or could not be confirmed — see debug/ screenshot "
        "and log for the DOM state. Check IMOS_USERNAME/IMOS_PASSWORD in .env."
    )


def _open_organization_roster_report(page):
    """Reports and Surveys (accordion) > Mission Office Reports > 'Current
    Organization' (Excel). Confirmed via a live DOM dump that the sidebar
    uses native <details>/<summary> for 'Reports and Surveys' and a plain
    <a href> for 'Mission Office Reports' — but a direct page.goto() to that
    href breaks the app's SPA routing (loads the wrong state), so we click
    through the accordion instead. The accordion opens then can collapse
    again almost immediately if we click its child too fast, so we wait for
    it to settle before clicking 'Mission Office Reports'. Returns the
    'Current Organization' locator — NOT yet clicked — so the caller can
    click it inside an expect_download() context, since clicking this entry
    is itself what triggers the Excel download (no separate export step).
    If we already landed on the reports listing (e.g. IMOS_BASE_URL's deep
    link survived the login redirect this time), skip straight to looking
    for 'Current Organization' instead of re-clicking the accordion."""
    already_there = page.get_by_text("Current Organization", exact=False).count() > 0
    if not already_there:
        mission_office = None
        for attempt in range(6):
            reports_summary = page.get_by_text("Reports and Surveys", exact=False).first
            reports_summary.click(timeout=15000)
            page.wait_for_timeout(1500)
            candidate = page.locator("a[href*='reports/#/all-reports']:visible").first
            if candidate.count():
                mission_office = candidate
                break
            page.wait_for_timeout(500)

        if mission_office is None:
            _screenshot(page, "reports_accordion_not_open")
            raise RuntimeError(
                "Could not get the 'Reports and Surveys' accordion to stay open "
                "after 6 attempts — see debug/ screenshot."
            )

        mission_office.click(timeout=15000)
        page.wait_for_timeout(2000)

    current_org = page.get_by_text("Current Organization", exact=False).first
    current_org.wait_for(state="visible", timeout=20000)
    return current_org


def _download_roster_excel(page, output_dir: Path) -> Path:
    """Assumes an already-logged-in page. Opens 'Current Organization',
    generates the Excel report, and downloads it into output_dir.

    Clicking the report row opens a "Current Organization" modal with an
    optional description field — "GENERATE EXCEL REPORT" only QUEUES the
    report; it does not download directly. The portal generates it
    asynchronously, then shows a green checkmark badge (button[aria-
    label='Action'][iconcolor='#318d43']) in the header once ready. Clicking
    that opens a notification panel; clicking "Details" on the newest card
    expands a "Download report." link, which is what actually triggers the
    file download. Confirmed step-by-step via live screenshots — see
    docs/superpowers/plans/2026-07-01-transfer-roster-playwright.md session
    notes."""
    current_org = _open_organization_roster_report(page)

    current_org.click(timeout=15000)
    generate_btn = page.get_by_text("GENERATE EXCEL REPORT", exact=False).first
    generate_btn.wait_for(state="visible", timeout=15000)
    generate_btn.click(timeout=15000)

    checkmark_btn = page.locator(
        "button[aria-label='Action'][iconcolor='#318d43']"
    ).first
    checkmark_btn.wait_for(state="visible", timeout=90000)
    checkmark_btn.click(timeout=5000)
    page.wait_for_timeout(1500)

    details = page.get_by_text("Details", exact=True).first
    details.click(timeout=10000)
    page.wait_for_timeout(1000)

    download_link = page.get_by_text("Download report", exact=False).first
    download_link.wait_for(state="visible", timeout=10000)

    with page.expect_download(timeout=60000) as dl_info:
        download_link.click(timeout=15000)
    download = dl_info.value

    # The portal's "Excel" export is actually legacy .xls (confirmed
    # live — pandas needed the xlrd engine, not openpyxl), so use
    # the download's real suggested extension rather than assuming.
    suggested_ext = Path(download.suggested_filename).suffix or ".xls"
    out_path = output_dir / f"organization_roster_{int(time.time())}{suggested_ext}"
    download.save_as(str(out_path))
    _logger.info(f"Downloaded Organization Roster to {out_path}")
    return out_path


def download_organization_roster(
    username: str,
    password: str,
    output_dir: Path,
    headless: bool = True,
) -> Path:
    """Logs in, opens the Organization Roster report, downloads the Excel
    file into output_dir, and returns its local path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        try:
            page.goto(IMOS_BASE_URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(4000)
            _login(page, username, password)
            return _download_roster_excel(page, output_dir)
        except Exception as e:
            _screenshot(page, "download_fail")
            _diagnose_login_state(page)
            _logger.error(f"IMOS download failed: {e}")
            raise
        finally:
            browser.close()


def scrape_area_emails(page, context) -> dict:
    """Assumes an already-logged-in page. Communications > Missionary.org
    Google Accounts opens mail.missionary.org in a new tab (target="_blank")
    with three sections: Mission Office Account, Closed Teaching Area
    Accounts, and Teaching Area Accounts. Only the last is in scope — each
    entry is a <button>AreaName<br><span>...</span><span>id@missionary.org
    </span></button>. Confirmed live 2026-07-01: no download involved, pure
    DOM scrape. Returns {area_name: email}."""
    # The left sidebar (Communications, Reports and Surveys, etc.) only
    # exists on the Portal Home page — the Mission Reports listing page
    # (where a roster download leaves us) is full-width with no sidebar at
    # all, confirmed live. If Communications isn't already visible, navigate
    # back to Home first (its breadcrumb link only exists when we're NOT
    # already on Home, so guard the click on that too).
    if not page.get_by_text("Communications", exact=False).count():
        home_link = page.get_by_text("Home", exact=True).first
        if home_link.count():
            home_link.click(timeout=15000)
            page.wait_for_timeout(2000)

    link = None
    for attempt in range(6):
        comms = page.get_by_text("Communications", exact=False).first
        comms.click(timeout=15000)
        page.wait_for_timeout(1500)
        candidate = page.locator(
            "a[href='https://mail.missionary.org/']:visible"
        ).first
        if candidate.count():
            link = candidate
            break
        page.wait_for_timeout(500)

    if link is None:
        _screenshot(page, "communications_accordion_not_open")
        raise RuntimeError(
            "Could not get the 'Communications' accordion to stay open "
            "after 6 attempts — see debug/ screenshot."
        )

    with context.expect_page(timeout=15000) as popup_info:
        link.click(timeout=15000)
    popup = popup_info.value
    popup.wait_for_load_state("domcontentloaded", timeout=30000)
    popup.wait_for_timeout(5000)

    try:
        area_emails = popup.evaluate(
            """() => {
                const headings = [...document.querySelectorAll('h2')];
                const target = headings.find(h =>
                    h.textContent.trim().startsWith('Teaching Area Accounts'));
                if (!target) return {};
                const section = target.closest('.mb-5');
                if (!section) return {};
                const buttons = [...section.querySelectorAll('button')];
                const result = {};
                for (const b of buttons) {
                    const area = b.childNodes[0]?.textContent?.trim();
                    const match = b.textContent.match(/(\\d+@missionary\\.org)/);
                    if (area && match) result[area] = match[1];
                }
                return result;
            }"""
        )
    except Exception as e:
        _screenshot(page, "area_emails_scrape_fail")
        _logger.error(f"Area email scrape failed: {e}")
        raise
    finally:
        popup.close()

    _logger.info(f"Scraped {len(area_emails)} area emails")
    return area_emails


def download_organization_roster_and_emails(
    username: str,
    password: str,
    output_dir: Path,
    headless: bool = True,
):
    """One login, both the roster Excel download and the area email scrape.
    Returns (roster_path: Path, area_emails: dict)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        try:
            page.goto(IMOS_BASE_URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(4000)
            _login(page, username, password)

            roster_path = _download_roster_excel(page, output_dir)
            area_emails = scrape_area_emails(page, ctx)

            return roster_path, area_emails
        except Exception as e:
            _screenshot(page, "download_fail")
            _diagnose_login_state(page)
            _logger.error(f"IMOS download failed: {e}")
            raise
        finally:
            browser.close()
