"""
auth.py
────────────────────────────────────────────────────────────
Two-layer authentication:
  Layer 1 — Streamlit Cloud SSO forces Google login (set app to Private).
  Layer 2 — Code-level allowlist: only approved emails get in regardless of SSO.

Approved emails:
  - _ALWAYS_ALLOWED: the owner and system accounts, hardcoded.
  - Every active row of MISSION_LEADERSHIP — the Mission President and the
    assistants, under the addresses they sign in with (since 2026-10-05,
    PLAN-2026-10-05-roster-access.md D1). Edited on Traslados, so a new AP
    is a row, not a code change.
  - Every Companion1_Email / Companion2_Email in MISSION_ORG — i.e. every area
    mailbox, NOT just APs. (An earlier version of this docstring said
    "Is_AP = TRUE"; get_allowed_emails() has never filtered on that flag.)
  - STREAMLIT_DEV_EMAIL in secrets (LOCAL DEV ONLY — must be blank in production)

Who may open the LEADERSHIP pages (is_leadership) is narrower than who may sign
in: the President, the assistants and the owner accounts (D2). Zone, district
and sister training leaders sign in with their area's mailbox, which several
missionaries can share, and until 2026-10-05 that alone opened Traslados'
Apply, Editar Envios and Mantenimiento's settings to 19 mailboxes.
"""

import time
import streamlit as st
from app.db.queries import get_allowed_emails, get_leadership_roles, get_user_role
from app.i18n import t

_SESSION_TIMEOUT_SECONDS = 4 * 3600  # 4 hours

# ── Hardcoded accounts ─────────────────────────────────────────────────────────
#: The owner and system accounts: approved to sign in AND treated as leadership
#: regardless of any tab, so the people who maintain the app can never be
#: locked out of it by a sheet edit.
_OWNER_ACCOUNTS = {
    "ccsm.pmg.compass@gmail.com",           # CCSM system account (from AGENT_CONFIG)
    "zackary.butterfield@missionary.org",   # owner — Los Huertos, San Pedro zone
}

#: Approved to sign in regardless of MISSION_ORG / MISSION_LEADERSHIP.
#:
#: The President and the assistants used to be listed here by hand (and
#: removed by hand — Hyrum Turner, 2026-09-08), because MISSION_ORG cannot
#: supply the address an AP signs in with: its one Is_AP row (La Marina 1)
#: carries the mailbox 500407562@missionary.org that four missionaries share.
#: Since 2026-10-05 they are rows of MISSION_LEADERSHIP instead
#: (PLAN-2026-10-05-roster-access.md D1) — a new AP is a row on Traslados, not
#: a code change. Do not add them back here.
_ALWAYS_ALLOWED = _OWNER_ACCOUNTS | {
    # TEMPORARY — deploy verification only, remove before go-live. Signs in;
    # is NOT leadership and does not set goals.
    "grayden16gmc@gmail.com",
}

#: The roles that open the leadership pages. "leader" (ZL / STL / DL) was in
#: this set until 2026-10-05 and is not now — D2.
_LEADERSHIP_ROLES = {"president", "assistant"}

#: Accounts that may SET the mission's goals beyond the president/assistant
#: roles: the owner accounts. (Before MISSION_LEADERSHIP, the role check alone
#: admitted nobody — probed live 2026-09-05, not one leader's sign-in address
#: was in MISSION_ORG — so this list carried every leader by hand.)
_GOAL_SETTERS = _OWNER_ACCOUNTS


def can_set_goals(user: dict) -> bool:
    """True for the mission president, the assistants, and the owner account.

    Takes the session dict `require_auth()` returns, and checks BOTH the role
    MISSION_ORG derives and the address itself — see _GOAL_SETTERS for why the
    role alone is not enough on this mission's data.
    """
    email = str((user or {}).get("email", "")).strip().lower()
    return (user or {}).get("role") in ("president", "assistant") or email in _GOAL_SETTERS


def allowed_emails() -> set:
    """Every address that may sign in: the hardcoded accounts, MISSION_LEADERSHIP
    and every MISSION_ORG area mailbox."""
    return (_ALWAYS_ALLOWED
            | {e.lower() for e in get_allowed_emails()}
            | set(get_leadership_roles()))


def is_leadership(email: str) -> bool:
    """
    True for the Mission President and the assistants (MISSION_LEADERSHIP, or
    MISSION_ORG's Is_MP / Is_AP flags) and for the owner accounts. Gates the
    leadership-only pages: Traslados' Apply, Editar Envios, Mantenimiento's
    settings, Centro de Accion, Sugerencias and the action bell.

    Zone, district and sister training leaders are NOT leadership here
    (PLAN-2026-10-05-roster-access.md D2): they sign in with their area's
    shared mailbox, and anyone who reads that mailbox could otherwise apply a
    transfer.
    """
    email = (email or "").lower().strip()
    if email in _OWNER_ACCOUNTS:
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
    if email not in allowed_emails():
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
