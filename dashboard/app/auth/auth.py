"""
auth.py
────────────────────────────────────────────────────────────
Two-layer authentication:
  Layer 1 — Streamlit Cloud SSO forces Google login (set app to Private).
  Layer 2 — Code-level allowlist: only approved emails get in regardless of SSO.

Approved emails:
  - ALWAYS_ALLOWED hardcoded list (CCSM system account; Mission President once added — see TODO below)
  - Every Companion1_Email / Companion2_Email in MISSION_ORG — i.e. all 97 area
    mailboxes, NOT just APs. (An earlier version of this docstring said
    "Is_AP = TRUE"; get_allowed_emails() has never filtered on that flag.
    Verified against the live sheet: 97 addresses, all @missionary.org.)
  - STREAMLIT_DEV_EMAIL in secrets (LOCAL DEV ONLY — must be blank in production)

Consequence worth knowing before go-live: MISSION_ORG holds no
churchofjesuschrist.org addresses at all, so mission leadership cannot sign in
on the strength of the sheet alone — the Mission President must be added to
_ALWAYS_ALLOWED below or he is locked out of his own dashboard.
"""

import time
import streamlit as st
from app.db.queries import get_allowed_emails, get_user_role
from app.i18n import t

_SESSION_TIMEOUT_SECONDS = 4 * 3600  # 4 hours

# ── Hardcoded always-allowed list ──────────────────────────────────────────────
# These are approved regardless of MISSION_ORG contents.
# Add or remove emails here to control access tightly.
_ALWAYS_ALLOWED = {
    "ccsm.pmg.compass@gmail.com",   # CCSM system account (from AGENT_CONFIG)

    # TEMPORARY — deploy verification only, remove before go-live.
    "grayden16gmc@gmail.com",

    # Individual missionaries who sign in with a personal address rather than
    # their area's shared mailbox. MISSION_ORG only stores the shared mailbox
    # (a missionary-ID address like 500488642@missionary.org), so anyone using
    # a different address is invisible to get_allowed_emails() and must be
    # listed here by hand.
    "zackary.butterfield@missionary.org",   # Los Huertos, San Pedro zone
    "hyrum.turner@missionary.org",          # AP1 — TODO: remove ~mid-Sept 2026, goes home in 6 weeks (as of 2026-07-31)
    "anderson.phillips@missionary.org",     # AP2

    # Mission President — MISSION_ORG has no churchofjesuschrist.org
    # addresses at all, so the sheet grants him nothing on its own (see
    # module docstring); he can only sign in via this hardcoded entry.
    "gutierrezsaucedom@churchofjesuschrist.org",   # Presidente Gutierrez
}

# Mission-leadership roles, plus the always-allowed owner/admin accounts above.
_LEADERSHIP_ROLES = {"president", "assistant", "leader"}


def is_leadership(email: str) -> bool:
    """
    True for mission leadership (president/assistant/leader per MISSION_ORG) or
    for the always-allowed owner/admin accounts. Use this to gate leadership-only
    pages so the developer/owner account is never locked out.
    """
    email = (email or "").lower().strip()
    if email in _ALWAYS_ALLOWED:
        return True
    return get_user_role(email) in _LEADERSHIP_ROLES


def _resolve_viewer():
    """
    Return the object carrying the signed-in viewer's identity, or None.

    Reads `st.experimental_user`, NOT `st.user`:
      - `st.user` does not exist at all before Streamlit 1.42, and
        requirements.txt pins 1.40.0 on purpose (see RUNNING.md) — so reading
        `st.user` raises AttributeError and every production visitor gets an
        error page. The dev bypass in require_auth() returns before this point,
        so running the app locally can never surface that.
      - From 1.42 on, `st.user` deliberately stops returning a Community Cloud
        account email unless you run your own OIDC provider. On Community
        Cloud, `st.experimental_user` is the one carrying the Google account.

    The `st.user` fallback covers only a future Streamlit that removes
    `experimental_user`. Both are probed with `is None`, never truthiness: an
    empty UserInfoProxy is falsy, so `a or b` would discard a real (empty)
    proxy and mask "signed in but no email" as "attribute missing".

    Covered by tests/test_sso_viewer.py — it asserts against the installed
    Streamlit, because this is exactly the class of bug a source-only check
    reports as fine.
    """
    viewer = getattr(st, "experimental_user", None)
    if viewer is None:
        viewer = getattr(st, "user", None)
    return viewer


def require_auth() -> dict:
    """
    Enforce authentication. Blocks access and calls st.stop() if not approved.
    Returns the session dict for authenticated users.

    SECURITY: dev bypass only works when STREAMLIT_DEV_EMAIL is explicitly set
    in secrets. In production, this key must be absent or empty string.
    """
    # ── Session timeout check ─────────────────────────────────────────────────
    login_at = st.session_state.get("pmg_login_at")
    if login_at and (time.time() - login_at) > _SESSION_TIMEOUT_SECONDS:
        st.session_state.pop("pmg_user", None)
        st.session_state.pop("pmg_login_at", None)
        st.warning(t("Your session has expired. Please sign in again."))
        st.stop()

    cached = st.session_state.get("pmg_user")

    # ── Local dev bypass (MUST be blank in production secrets) ────────────────
    dev_email = (st.secrets.get("STREAMLIT_DEV_EMAIL", "") or "").strip()
    if dev_email:
        if cached and login_at and cached.get("email") == dev_email.lower():
            return cached
        return _build_session(dev_email.lower())

    # ── Streamlit Cloud SSO check ─────────────────────────────────────────────
    viewer = _resolve_viewer()
    is_logged_in = getattr(viewer, "is_logged_in", None)

    if is_logged_in is False:
        st.error(
            t("Access denied. You must be signed in with an approved Google account. "
            "Contact the mission office if you need access.")
        )
        st.stop()

    email = (getattr(viewer, "email", "") or "").lower().strip()
    if not email:
        st.error(t("Could not verify your identity. Please sign out and sign back in."))
        st.stop()

    # ── Reuse the cached session only if it belongs to the CURRENT signed-in
    #    account. Binding to the live SSO email means a different account in the
    #    same browser session re-resolves instead of showing the prior user.
    if cached and login_at and cached.get("email") == email:
        return cached

    # ── Allowlist check — both layers must pass ───────────────────────────────
    allowed = _ALWAYS_ALLOWED | {e.lower() for e in get_allowed_emails()}

    if email not in allowed:
        import datetime
        print(f"[AUTH BLOCKED] {email} attempted access at {datetime.datetime.utcnow().isoformat()}")
        st.error(
            t("Access denied. Your account is not approved for PMG Compass. "
            "Contact the mission office to request access.")
        )
        st.stop()

    # Prefer the real display name from the identity provider; fall back to a
    # name derived from the email local-part.
    display_name = (getattr(viewer, "name", "") or "").strip()
    return _build_session(email, display_name)


def _display_name_from_email(email: str) -> str:
    return email.split("@")[0].replace(".", " ").replace("_", " ").title()


def _build_session(email: str, display_name: str = "") -> dict:
    """Build and cache the session dict for `email` (overwrites any prior user)."""
    role = get_user_role(email)
    name = (display_name or "").strip() or _display_name_from_email(email)
    st.session_state["pmg_user"] = {
        "email": email,
        "name":  name,
        "role":  role,
    }
    st.session_state["pmg_login_at"] = time.time()
    return st.session_state["pmg_user"]


def get_session() -> dict:
    """Return current session or empty dict."""
    return st.session_state.get("pmg_user", {})


def clear_session() -> None:
    st.session_state.pop("pmg_user", None)
    st.session_state.pop("pmg_login_at", None)
