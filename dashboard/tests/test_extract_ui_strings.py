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
