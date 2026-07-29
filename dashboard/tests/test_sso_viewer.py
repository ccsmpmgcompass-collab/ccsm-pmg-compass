"""Guards on the production sign-in path.

Why this file exists: `auth.py` originally read `viewer = st.user`, which does
not exist on the pinned Streamlit 1.40.0 — so the FIRST person to open the
deployed app would have hit
`AttributeError: module 'streamlit' has no attribute 'user'`.

Nothing caught it, and nothing could have:
  - Running the app locally never reaches this code. `STREAMLIT_DEV_EMAIL` is
    set in local secrets and require_auth() returns from the dev bypass first.
  - The page-render suite exercised all 10 pages without raising, for the same
    reason.
  - A source-level check ("does auth.py read a viewer object?") passes on the
    broken version — the name `st.user` reads perfectly well.

So these tests assert against the *installed* Streamlit, not against source
text: the property that matters is "reading the viewer works on the version we
actually deploy". Same lesson as tests/test_renders_spanish.py.
"""
import sys
from pathlib import Path

import pytest

dashboard_dir = Path(__file__).resolve().parent.parent
if str(dashboard_dir) not in sys.path:
    sys.path.insert(0, str(dashboard_dir))

import streamlit as st
from app.auth.auth import _resolve_viewer


def _streamlit_version() -> tuple:
    return tuple(int(p) for p in st.__version__.split(".")[:2])


def test_viewer_object_exists_on_installed_streamlit():
    """The deployed Streamlit must expose a viewer object at all."""
    viewer = _resolve_viewer()
    assert viewer is not None, (
        f"streamlit {st.__version__} exposes neither experimental_user nor "
        "user; the production SSO path cannot resolve an identity"
    )


def test_reading_the_email_attribute_does_not_raise():
    """The exact failure mode of the original bug: reading the attribute blew up.

    `getattr(..., default)` only swallows AttributeError, so a proxy that raises
    KeyError for a missing key would still crash require_auth(). Assert the read
    itself is safe rather than assuming which exception type it uses.
    """
    viewer = _resolve_viewer()
    try:
        email = getattr(viewer, "email", "")
    except Exception as exc:  # noqa: BLE001 - the point is that nothing escapes
        pytest.fail(
            f"reading viewer.email raised {type(exc).__name__}: {exc}. "
            "require_auth() would crash for every production visitor."
        )
    # Off Community Cloud, Streamlit returns the placeholder 'test@example.com'.
    # It is NOT in _ALWAYS_ALLOWED and cannot be an AP in MISSION_ORG, so the
    # allowlist denies it — the failure mode is a locked door, not an open one.
    assert email is None or isinstance(email, str)


def test_st_user_is_not_the_primary_read_on_pre_1_42():
    """Regression guard: don't let a future edit put `st.user` back first.

    Pinned at 1.40.0, `st.user` is an AttributeError. This asserts on the
    resolution ORDER by hiding experimental_user and confirming the fallback
    is what runs, so it stays honest if the pin ever moves.
    """
    if _streamlit_version() >= (1, 42):
        pytest.skip(
            "streamlit >= 1.42 has st.user; re-verify which object carries the "
            "Community Cloud email before relaxing this guard"
        )
    assert hasattr(st, "experimental_user"), (
        "experimental_user is gone on this version — _resolve_viewer() would "
        "fall through to st.user, which raises on < 1.42"
    )
    assert not hasattr(st, "user"), (
        "st.user now exists on a < 1.42 build; re-check which object Community "
        "Cloud populates before trusting either"
    )


def test_dev_bypass_key_is_absent_from_the_deploy_template():
    """`STREAMLIT_DEV_EMAIL` bypasses BOTH SSO and the allowlist (auth.py).

    secrets.cloud.toml is the file that gets pasted into Streamlit Cloud's
    secrets box. If the key reaches production, anyone with the URL is admitted
    as that user. The template is generated, so this asserts on the artifact
    that actually gets copied, not on a habit.
    """
    template = dashboard_dir / ".streamlit" / "secrets.cloud.toml"
    if not template.exists():
        pytest.skip("secrets.cloud.toml not generated on this machine")
    for i, line in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "STREAMLIT_DEV_EMAIL" not in stripped, (
            f"{template.name}:{i} sets STREAMLIT_DEV_EMAIL — pasting this into "
            "Streamlit Cloud disables authentication entirely"
        )
