from pathlib import Path

from tools.extract_ui_strings import extract, extract_unwrapped

WRAPPED_FIXTURE = '''
import streamlit as st
from app.i18n import t
st.info(t("Already wrapped"))
st.button("Not yet wrapped")
_MSG = t("Wrapped away from any widget")
'''


def test_wrapped_strings_stay_in_the_denominator(tmp_path: Path):
    """Wrapping a literal in t() makes it an argument of `t`, not of st.info.
    If the scan only looked at UI-call arguments the string would vanish, and
    a fully wrapped file with an empty ES dict would report 100% translated
    while rendering English."""
    f = tmp_path / "w.py"
    f.write_text(WRAPPED_FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert "Already wrapped" in found
    assert "Not yet wrapped" in found
    assert "Wrapped away from any widget" in found


def test_unwrapped_is_tracked_separately(tmp_path: Path):
    """A literal still handed straight to a widget renders English however
    complete ES is, so it is a distinct failure from a missing translation."""
    f = tmp_path / "w.py"
    f.write_text(WRAPPED_FIXTURE, encoding="utf-8")
    todo = extract_unwrapped([str(f)])
    assert todo == ["Not yet wrapped"], todo

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


CHOICE_FIXTURE = '''
import streamlit as st
mode = st.radio("Show", ["All", "Behind only"], horizontal=True)
tab_a, tab_b = st.tabs(["Scores", "Analyze"])
zone = st.selectbox("Zone", zone_opts_from_sheet)
'''


def test_option_lists_are_extracted(tmp_path: Path):
    """Choices are user-visible. They arrive as a list literal, so the plain
    positional-arg scan never reached them and they sat outside the coverage
    denominator entirely."""
    f = tmp_path / "choices.py"
    f.write_text(CHOICE_FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    for s in ("Show", "All", "Behind only", "Scores", "Analyze", "Zone"):
        assert s in found, f"{s!r} missing from {found}"


def test_dynamic_option_lists_are_left_alone(tmp_path: Path):
    """A list built from sheet data is mission content - already Spanish, and
    translating it again would corrupt area/zone names."""
    f = tmp_path / "choices.py"
    f.write_text(CHOICE_FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    assert all("zone_opts_from_sheet" not in s for s in found)


FSTRING_FIXTURE = '''
import streamlit as st
from app.i18n import t
st.success(f"Goals saved for {area}.")
st.error(f"Could not write {tab}: {e}")
st.caption(f"{pct:.1f}% of {row["name"]} complete")
st.markdown(f"<div style=\\'color:red\\'>{x}</div>", unsafe_allow_html=True)
st.write(f"{x}")
st.info(t("Already converted {n}", n=3))
'''


def test_fstrings_are_reported_unwrapped(tmp_path: Path):
    """An f-string is a JoinedStr, not a Constant, so it was invisible to BOTH
    scans - the gate could not report it missing because it never knew it
    existed. That is how 107 English strings survived a '100%' report."""
    f = tmp_path / "fs.py"
    f.write_text(FSTRING_FIXTURE, encoding="utf-8")
    todo = extract_unwrapped([str(f)])
    assert "Goals saved for {area}." in todo
    assert "Could not write {tab}: {e}" in todo


def test_fstring_placeholders_are_named_from_the_expression(tmp_path: Path):
    """The name is part of the translator-facing key, so {name} must beat
    {v0}. Format specs and subscript keys have to survive too."""
    f = tmp_path / "fs.py"
    f.write_text(FSTRING_FIXTURE, encoding="utf-8")
    todo = extract_unwrapped([str(f)])
    assert "{pct:.1f}% of {name} complete" in todo


CALL_FIXTURE = '''
import streamlit as st
st.caption(f"{get_config_value("MISSION_NAME", d)} — PMG Compass")
st.caption(f"week of {_monday.strftime("%b")}")
st.caption(f"{len(rows)} areas shown")
'''


def test_placeholder_names_describe_the_value_not_the_call(tmp_path: Path):
    """These names end up in the key a native proofreader reads. "{strftime}"
    and "{get_config_value}" tell a translator nothing about what will appear
    there; the call's subject does."""
    f = tmp_path / "c.py"
    f.write_text(CALL_FIXTURE, encoding="utf-8")
    todo = extract_unwrapped([str(f)])
    assert "{mission_name} — PMG Compass" in todo, todo
    assert "week of {monday}" in todo, todo
    assert "{count} areas shown" in todo, todo


def test_html_and_pure_interpolation_fstrings_are_skipped(tmp_path: Path):
    """This app builds layout with f-string <div> blocks - structure, not
    copy - and f"{x}" carries no prose at all."""
    f = tmp_path / "fs.py"
    f.write_text(FSTRING_FIXTURE, encoding="utf-8")
    todo = extract_unwrapped([str(f)])
    assert not any("div" in s or "color:red" in s for s in todo), todo
    assert "{x}" not in todo


def test_converted_fstring_is_not_reported_again(tmp_path: Path):
    """Once converted the template is a Constant inside t(), so it leaves the
    to-do list and joins the denominator instead."""
    f = tmp_path / "fs.py"
    f.write_text(FSTRING_FIXTURE, encoding="utf-8")
    assert "Already converted {n}" not in extract_unwrapped([str(f)])
    assert "Already converted {n}" in extract([str(f)])


FORMAT_FUNC_FIXTURE = '''
import streamlit as st
from app.i18n import t
form = st.selectbox(t("Form"), ["NIGHTLY", "WEEKLY"], format_func=t)
cad = st.selectbox(t("Cadence"), ["weekly", "monthly"],
                   format_func=lambda c: t(c).capitalize())
bare = st.selectbox(t("Bare"), ["Alpha", "Beta"])
'''


def test_format_func_options_are_not_reported_unwrapped(tmp_path: Path):
    """Options whose VALUE is written to the sheet must stay English, so they
    cannot be wrapped in t() directly - format_func=t translates the label
    instead. Reporting those as unwrapped would push a future editor into
    exactly the change that corrupts the stored value."""
    f = tmp_path / "ff.py"
    f.write_text(FORMAT_FUNC_FIXTURE, encoding="utf-8")
    todo = extract_unwrapped([str(f)])
    for handled in ("NIGHTLY", "WEEKLY", "weekly", "monthly"):
        assert handled not in todo, f"{handled} wrongly reported unwrapped"
    assert "Alpha" in todo and "Beta" in todo, todo


def test_format_func_options_still_need_translations(tmp_path: Path):
    """They are translated at render time, so they still need ES entries."""
    f = tmp_path / "ff.py"
    f.write_text(FORMAT_FUNC_FIXTURE, encoding="utf-8")
    found = extract([str(f)])
    for s in ("NIGHTLY", "WEEKLY", "weekly", "monthly"):
        assert s in found, f"{s} dropped from the denominator"


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
