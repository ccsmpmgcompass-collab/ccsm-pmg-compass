"""Regression for audit finding B5 (AUDIT-IA-2026-08-22.md).

The notification bell (app/components/design_system.py's _render_action_bell)
linked to "/Action_Center", a page that does not exist — the real file is
views/17_Centro_de_Acción.py. Streamlit has no 404: an unknown path silently
serves Home, so every leadership user who clicked the bell landed back where
they started with no indication anything was wrong.

The expected href is derived from the real page file via Streamlit's own
page_icon_and_name (the function that computes a page's URL from its
filename), not hardcoded here a second time — if the page ever gets renamed,
this test recomputes the new expected path instead of just re-asserting
whatever string a fix happened to use.
"""

from pathlib import Path

from streamlit.source_util import page_icon_and_name
from streamlit.testing.v1 import AppTest

VIEWS_DIR = Path(__file__).resolve().parent.parent / "views"


def _action_center_expected_href() -> str:
    matches = sorted(VIEWS_DIR.glob("*Centro_de_Acci*.py"))
    assert matches, "views/17_Centro_de_Acción.py (or similar) not found"
    _icon, name = page_icon_and_name(matches[0])
    return f"/{name}"


def _render():
    from app.components.design_system import _render_action_bell
    _render_action_bell({"email": "leader@missionary.org", "name": "Leader"})


def test_bell_links_to_the_real_action_center_page(monkeypatch):
    import app.auth.auth as auth
    import app.db.action_center_queries as acq

    monkeypatch.setattr(auth, "is_leadership", lambda email: True)
    monkeypatch.setattr(acq, "get_action_center_summary", lambda email: {"total": 3})

    # AppTest.from_function defaults to a 3-second script timeout, which this
    # test spent most of on the first import of app.components.design_system.
    # It passed alone and failed inside the full suite for no reason connected
    # to the bell — a timing flake, not a signal. Every other AppTest in this
    # suite already sets an explicit timeout for the same reason.
    at = AppTest.from_function(_render, default_timeout=30)
    at.run()
    assert not at.exception, f"_render_action_bell raised: {at.exception}"

    expected = _action_center_expected_href()
    html = "\n".join(m.value for m in at.markdown)
    assert f'href="{expected}"' in html, (
        f"bell does not link to the real Action Center page ({expected!r}); "
        f"markdown was: {html!r}"
    )
    assert 'href="/Action_Center"' not in html
