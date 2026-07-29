from pathlib import Path

from tools.extract_ui_strings import extract

FIXTURE = '''
import streamlit as st
st.markdown("Hello world")
st.button("Save changes")
st.caption(f"Week {x}")
value = "not a ui string"
st.write(some_variable)
'''


def test_extracts_only_ui_call_literals(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text(FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert "Hello world" in found
    assert "Save changes" in found
    assert "not a ui string" not in found


def test_ignores_dynamic_arguments(tmp_path: Path):
    f = tmp_path / "sample.py"
    f.write_text(FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert all("some_variable" not in s for s in found)


CSS_FIXTURE = '''
import streamlit as st
st.markdown("<style>div[data-testid='x']{color:#fff !important}</style>",
            unsafe_allow_html=True)
st.markdown("<b>Warning</b> - check this")
st.info("Real message")
'''


def test_stylesheets_are_not_translatable_strings(tmp_path: Path):
    """A <style> block is CSS, not UI copy - it must stay out of the
    translator's queue and out of the coverage denominator."""
    f = tmp_path / "css.py"
    f.write_text(CSS_FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert not any(s.startswith("<style>") for s in found), found
    assert "Real message" in found


def test_markup_wrapped_prose_is_still_extracted(tmp_path: Path):
    """The stylesheet filter must not become a general 'starts with <' rule -
    prose inside tags is still user-facing text that needs translating."""
    f = tmp_path / "css.py"
    f.write_text(CSS_FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert "<b>Warning</b> - check this" in found
