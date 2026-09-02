"""One sub-navigation idiom, app-wide (audit step 1.7).

Five existed: st.tabs, st.segmented_control, st.radio repainted as tabs by a
CSS block copy-pasted between two pages, a hand-rolled button pair, and plain
horizontal radios. They behaved differently in ways that mattered — st.tabs
runs every tab's body and forgets which tab you were on; segmented_control
will not fill the row — so "pick one" was a correctness decision, not a
cosmetic one. render_section_tabs is the one that survived.

The single exception is asserted here too, so it stays a decision rather than
becoming an oversight.
"""

import ast
import io
from pathlib import Path

import pytest
import streamlit as st

from app.components import design_system as ds

DASHBOARD = Path(__file__).resolve().parent.parent
VIEWS = DASHBOARD / "views"

#: Puntajes' metric-weight editor. Its three tabs are not navigation — they are
#: three parts of one form, and all three bodies MUST render so the single save
#: below them sees all three weight sets. st.tabs' "every body renders", the
#: behaviour that disqualified it everywhere else, is what makes that work.
ALLOWED_ST_TABS = {"06_Puntajes.py": 1}


def _calls(path: Path, dotted: str) -> int:
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    return sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == dotted
    )


@pytest.mark.parametrize("widget", ["segmented_control"])
def test_retired_widgets_are_gone(widget):
    offenders = {p.name for p in VIEWS.glob("*.py") if _calls(p, widget)}
    assert offenders == set(), f"{widget} still used in {sorted(offenders)}"


def test_st_tabs_survives_only_where_every_body_must_render():
    found = {p.name: _calls(p, "tabs") for p in VIEWS.glob("*.py")
             if _calls(p, "tabs")}
    assert found == ALLOWED_ST_TABS, (
        f"st.tabs usage is {found}, expected {ALLOWED_ST_TABS}. st.tabs runs "
        "every tab's body on every rerun and cannot remember which tab is "
        "open; use render_section_tabs unless all bodies must render."
    )


def test_the_copy_pasted_tab_css_is_gone():
    """The Metas/Traslados block repainted radio labels as tabs by targeting
    Streamlit's internal st-key- class names, and existed verbatim in two
    files."""
    offenders = [p.name for p in VIEWS.glob("*.py")
                 if "stRadio" in io.open(p, encoding="utf-8").read()]
    assert offenders == [], f"radio-as-tabs CSS remains in {offenders}"


# ── The component itself ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_state():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    yield


def _render(options, **kwargs):
    captured = []
    original_markdown, original_button = st.markdown, st.button
    st.markdown = lambda body, **kw: captured.append(body)
    st.button = lambda *a, **kw: False
    try:
        active = ds.render_section_tabs(options, **kwargs)
    finally:
        st.markdown, st.button = original_markdown, original_button
    return active, "\n".join(str(c) for c in captured)


def test_the_first_option_is_active_by_default():
    active, _ = _render({"a": "A", "b": "B"}, key="k")
    assert active == "a"


def test_a_stored_id_survives_a_language_switch():
    """Ids are stored, labels are not — so a mid-session language change
    cannot strand a Spanish string in an English option list."""
    st.session_state["k"] = "b"
    active, _ = _render({"a": "Scores", "b": "Analyze"}, key="k")
    assert active == "b"
    active, _ = _render({"a": "Puntajes", "b": "Analizar"}, key="k")
    assert active == "b"


def test_a_stale_stored_id_falls_back_instead_of_raising():
    """A section renamed between releases leaves a value in session_state that
    no longer names an option."""
    st.session_state["k"] = "removed_section"
    active, _ = _render({"a": "A", "b": "B"}, key="k")
    assert active == "a"


def test_the_selected_state_is_drawn_for_the_active_option():
    st.session_state["k"] = "b"
    _, html = _render({"a": "A", "b": "B"}, key="k")
    assert "st-key-k__1" in html
    assert "st-key-k__0" not in html


def test_the_selected_state_survives_an_id_css_cannot_spell():
    """Streamlit turns a widget key into a CSS class by replacing every
    non-alphanumeric character with "-", so keying the selector on the id
    itself silently matched nothing for Mantenimiento's "✅ To-Do & Health" and
    Goals' "Area Goal Customization" — five buttons, none highlighted, no
    error. The suffix is the option's index for exactly this reason."""
    st.session_state["k"] = "✅ To-Do & Health"
    _, html = _render(
        {"✅ To-Do & Health": "Tareas", "🔧 System": "Sistema"}, key="k")
    assert "st-key-k__0" in html
    assert "To-Do" not in html.split("</style>")[0]


def test_an_empty_option_set_returns_empty_rather_than_raising():
    active, _ = _render({}, key="k")
    assert active == ""
