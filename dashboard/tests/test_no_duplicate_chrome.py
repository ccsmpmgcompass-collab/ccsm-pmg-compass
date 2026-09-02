"""No page draws the app's chrome twice (audit step 1.6).

The double TEST MODE banner on Desgloses survived two previous fixes because
the duplication was not where anyone looked for it. It was not two calls to a
banner function; it was one function, inject_global_css(), doing two jobs with
different lifetimes — style the page (which a fragment rerun destroys and must
redo) and announce TEST MODE (which a fragment rerun must NOT redo). Splitting
inject_stylesheet() out of it is the fix; these tests are what keep it split.
"""

import ast
import io
from pathlib import Path

import pytest
import streamlit as st

from app.components import design_system as ds

DASHBOARD = Path(__file__).resolve().parent.parent
VIEWS = DASHBOARD / "views"


def _calls_in(path: Path, name: str) -> int:
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    return sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and (getattr(n.func, "id", None) == name
             or getattr(n.func, "attr", None) == name)
    )


def test_only_the_router_injects_page_chrome():
    """inject_global_css draws the banner, so exactly one caller may exist and
    it must be the router. A page calling it would draw a second banner on top
    of the router's."""
    callers = [p.name for p in VIEWS.glob("*.py")
               if _calls_in(p, "inject_global_css")]
    assert callers == [], (
        f"these pages call inject_global_css: {callers}. The router owns page "
        "chrome; a page that lost its stylesheet to a fragment rerun wants "
        "inject_stylesheet() instead."
    )
    assert _calls_in(DASHBOARD / "Home.py", "inject_global_css") == 1


def test_fragments_reinject_the_stylesheet_without_the_banner():
    """Desgloses is the one page with an @st.fragment, and it must get its
    stylesheet back after a fragment rerun — see _scope_body's comment for the
    live incident that put it there."""
    desgloses = next(VIEWS.glob("04_*.py"))
    assert _calls_in(desgloses, "inject_stylesheet") >= 1


def test_inject_stylesheet_draws_no_banner(monkeypatch):
    """The split is only worth anything if the CSS-only path really is banner
    free — with TEST_MODE on, which is when a duplicate would show."""
    import app.db.queries as q
    monkeypatch.setattr(q, "get_config_value",
                        lambda key, default="": "TRUE" if key == "TEST_MODE" else default)

    captured = []
    original = st.markdown
    st.markdown = lambda body, **kw: captured.append(body)
    try:
        ds.inject_stylesheet()
    finally:
        st.markdown = original

    assert not any("TEST MODE" in str(c) for c in captured), \
        "inject_stylesheet emitted the TEST MODE banner"


def test_the_language_switch_is_rendered_in_exactly_one_place():
    """Home used to render its own copy above the sidebar's mirror. The two
    stayed in sync only by an accident of Streamlit's widget-identity rules."""
    sources = [DASHBOARD / "Home.py"] + list(VIEWS.glob("*.py"))
    callers = [p.name for p in sources if _calls_in(p, "render_language_switch")]
    assert callers == [], (
        f"{callers} render their own language switch; the sidebar's copy is "
        "visible from every page."
    )
    assert _calls_in(DASHBOARD / "app" / "components" / "design_system.py",
                     "render_language_switch") == 1
