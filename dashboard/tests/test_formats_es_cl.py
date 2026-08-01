"""es_CL display conventions: decimal comma, dot thousands, day-first dates.

Every assertion here is about a value a Chilean reader would MISREAD rather than
see as broken. `1,234.5` reads as one-point-two-three-four; `08-01-2026` reads as
the 8th of January. That is the same failure shape as the Provo metric
vocabulary — a plausible screen, never an error — which is why these are pinned
rather than left to review.
"""

from datetime import date, datetime

import pytest
import streamlit as st

from app.i18n import formats as f
from app.i18n import get_lang, mission_default_lang, set_lang


@pytest.fixture(autouse=True)
def _clean_session():
    st.session_state.clear()
    yield
    st.session_state.clear()


@pytest.fixture
def es():
    set_lang("es")


@pytest.fixture
def en():
    set_lang("en")


# ── Numbers ───────────────────────────────────────────────────────────────────

def test_spanish_uses_comma_decimal_and_dot_thousands(es):
    assert f.fmt_number(1234.5, 1) == "1.234,5"
    assert f.fmt_number(1234567, 0) == "1.234.567"
    assert f.fmt_number(0.5, 1) == "0,5"
    assert f.fmt_number(-1234.56, 2) == "-1.234,56"


def test_english_keeps_anglo_separators(en):
    assert f.fmt_number(1234.5, 1) == "1,234.5"
    assert f.fmt_number(1234567, 0) == "1,234,567"


def test_grouping_boundaries(es):
    assert f.fmt_number(999) == "999"
    assert f.fmt_number(1000) == "1.000"
    assert f.fmt_number(100) == "100"


def test_percent_is_documented_as_already_scaled(es):
    """fmt_percent takes 0-100, not a 0-1 fraction. Pinned because both
    conventions appear in this codebase and silently accepting either would
    render 87% as 8700%."""
    assert f.fmt_percent(87.5, 1) == "87,5%"
    assert f.fmt_percent(100) == "100%"


def test_none_is_not_zero(es):
    """None means 'we cannot tell'; 0 means 'they did nothing'. A dash for the
    first, a real zero for the second — collapsing them tells a mission it
    scored nothing when nobody had reported yet."""
    assert f.fmt_number(None) == f.NA
    assert f.fmt_int(None) == f.NA
    assert f.fmt_percent(None) == f.NA
    assert f.fmt_number(0) == "0"
    assert f.fmt_percent(0) == "0%"
    assert f.NA != "0"


def test_nan_reads_as_missing_not_as_a_number(es):
    assert f.fmt_number(float("nan")) == f.NA
    assert f.fmt_number(float("inf")) == f.NA


def test_non_numeric_is_returned_untouched_not_coerced(es):
    """A CHOICE answer must not become 0 on its way to the screen."""
    assert f.fmt_number("Todo") == "Todo"


# ── Dates ─────────────────────────────────────────────────────────────────────

def test_spanish_dates_are_day_first(es):
    assert f.fmt_date(date(2026, 8, 1)) == "01-08-2026"
    assert f.fmt_date("2026-08-05") == "05-08-2026"


def test_english_dates_stay_iso(en):
    assert f.fmt_date(date(2026, 8, 1)) == "2026-08-01"


def test_month_year_uses_spanish_month_names_lowercase(es):
    """strftime('%B %Y') emits English regardless of the interface language,
    and RAE writes month names lowercase."""
    assert f.fmt_month_year(date(2026, 8, 1)) == "agosto de 2026"
    assert f.fmt_month_year("2026-12-31") == "diciembre de 2026"


def test_month_year_english(en):
    assert f.fmt_month_year(date(2026, 8, 1)) == "August 2026"


def test_date_range_carries_the_year_once(es):
    assert f.fmt_date_range("2026-08-05", "2026-08-11") == "5 de ago – 11 de ago de 2026"


def test_date_range_english(en):
    assert f.fmt_date_range("2026-08-05", "2026-08-11") == "Aug 5 – Aug 11, 2026"


def test_unparseable_date_reads_as_missing_not_as_today(es):
    assert f.fmt_date("not a date") == f.NA
    assert f.fmt_date(None) == f.NA
    assert f.fmt_date("") == f.NA


def test_datetime_is_accepted(es):
    assert f.fmt_date(datetime(2026, 8, 1, 23, 30)) == "01-08-2026"


def test_formatting_never_produces_an_iso_key():
    """Guard on this module's core rule: a formatted date is for reading only.
    If anything ever round-trips fmt_date() back into a sheet key or a sort, the
    day-first string silently orders and re-parses wrong."""
    set_lang("es")
    shown = f.fmt_date("2026-08-05")
    assert shown != "2026-08-05"
    assert shown == "05-08-2026"


# ── Default language comes from the mission, not from a literal ───────────────

def test_default_language_follows_mission_language(monkeypatch):
    monkeypatch.setattr("app.db.queries.get_config_value",
                        lambda key, default="": "ES" if key == "MISSION_LANGUAGE" else default)
    assert mission_default_lang() == "es"
    assert get_lang() == "es"


def test_user_choice_beats_the_mission_default(monkeypatch):
    monkeypatch.setattr("app.db.queries.get_config_value",
                        lambda key, default="": "ES" if key == "MISSION_LANGUAGE" else default)
    set_lang("en")
    assert get_lang() == "en"


def test_falls_back_to_english_when_the_sheet_is_silent(monkeypatch):
    monkeypatch.setattr("app.db.queries.get_config_value",
                        lambda key, default="": default)
    assert mission_default_lang() == "en"


def test_unreadable_config_does_not_raise(monkeypatch):
    """A quota blip must not take down every page's chrome."""
    def boom(key, default=""):
        raise RuntimeError("quota")
    monkeypatch.setattr("app.db.queries.get_config_value", boom)
    assert mission_default_lang() == "en"
    assert get_lang() == "en"
