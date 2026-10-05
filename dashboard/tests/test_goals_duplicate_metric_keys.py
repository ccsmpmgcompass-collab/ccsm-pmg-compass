"""Regression test for the Metas duplicate-widget-key crash.

`report_date` is defined on BOTH forms in CcsmData.gs, so QUESTIONS_CONFIG
holds it twice. The old Mission Goals section called get_question_metrics()
with no form_type filter, so both rows came back, both reached st.number_input
with the key `mission_extra_report_date`, and the whole page died with
StreamlitDuplicateElementKey before rendering anything.

Mission Goals was deleted in Step 7 (PLAN-2026-09-05-backlog.md §7.4a), and
until 2026-10-05 this file still drove it: the section no longer rendered, so
two of these tests failed ("rendered no boxes at all") and the other two passed
on a page that drew nothing. What survives of the risk is the one grid that
still builds a number_input per QUESTIONS_CONFIG row — Area Goal
Customization's nightly goals, keyed `goal_n_<area>_<metric>` — and that is
what these drive now.

The fixture below feeds the SHAPE of the live tab (a key repeated across form
types), not a copy of it — the fix has to hold for any future CcsmData.gs edit
that repeats the mistake, not just for `report_date`.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

_AREA = "Arauco 1"

# Two genuinely duplicated keys: report_date (a DATE, never a goal) and
# roleplays (a countable metric, which must survive as exactly ONE box).
_QUESTIONS = pd.DataFrame([
    {"Form_Type": "NIGHTLY", "Metric_Key": "report_date",
     "Metric_Display_Name": "Fecha del Reporte", "Data_Type": "DATE", "Active": "TRUE"},
    {"Form_Type": "NIGHTLY", "Metric_Key": "roleplays",
     "Metric_Display_Name": "Dramatizaciones", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Form_Type": "NIGHTLY", "Metric_Key": "contacts_made",
     "Metric_Display_Name": "Contactos", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Form_Type": "WEEKLY", "Metric_Key": "report_date",
     "Metric_Display_Name": "Fecha del Reporte", "Data_Type": "DATE", "Active": "TRUE"},
    {"Form_Type": "WEEKLY", "Metric_Key": "roleplays",
     "Metric_Display_Name": "Dramatizaciones", "Data_Type": "NUMBER", "Active": "TRUE"},
])

_ORG = pd.DataFrame([{
    "Area_Code": "A014", "Area_Name": _AREA, "Zone": "Arauco", "District": "Arauco",
    "Companion1_Name": "Elder Uno", "Companion1_Email": "arauco1@missionary.org",
    "Companion2_Name": "Elder Dos", "Companion2_Email": "arauco1@missionary.org",
    "Is_DL": "FALSE", "Is_ZL": "FALSE", "Is_STL": "FALSE", "Is_AP": "FALSE",
    "Is_MP": "FALSE", "Active": "TRUE",
}])


@pytest.fixture(autouse=True)
def _questions_config_with_duplicates(monkeypatch):
    from app.config import metric_catalog as mc

    def fake(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return _QUESTIONS.copy()
        if tab_name == "MISSION_ORG":
            return _ORG.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    import streamlit as st
    st.cache_data.clear()
    mc.clear_cache()
    yield
    st.cache_data.clear()
    mc.clear_cache()


def _run_area_goals(lang="en"):
    at = AppTest.from_file("views/02_Metas.py", default_timeout=90)
    at.session_state["pmg_lang"] = lang
    at.session_state["goals_section_val"] = "Area Goal Customization"
    at.run()
    return at


def _nightly_keys(at) -> list:
    prefix = f"goal_n_{_AREA}_"
    return [w.key for w in at.number_input if w.key and w.key.startswith(prefix)]


def test_area_goals_survive_a_metric_key_defined_on_both_forms():
    at = _run_area_goals()
    assert not at.exception, f"Area Goal Customization raised: {at.exception}"


def test_no_widget_key_is_used_twice():
    """The crash's actual signature. Asserted on the rendered widget keys
    rather than on the absence of an exception, so a future refactor that
    dedupes by accident (or stops rendering the grid at all) can't pass this by
    rendering nothing."""
    at = _run_area_goals()
    keys = [w.key for w in at.number_input if w.key]
    assert len(keys) == len(set(keys)), \
        f"duplicate widget keys: {sorted(k for k in keys if keys.count(k) > 1)}"
    assert _nightly_keys(at), \
        "the nightly goal grid rendered no boxes at all — the test proves nothing"


def test_report_date_is_not_offered_as_a_goal():
    """It's the date the report covers, not a countable production number."""
    at = _run_area_goals()
    assert f"goal_n_{_AREA}_report_date" not in _nightly_keys(at)


def test_a_duplicated_countable_metric_still_gets_exactly_one_box():
    """Dropping the repeat must not drop the metric."""
    at = _run_area_goals()
    keys = _nightly_keys(at)
    assert keys.count(f"goal_n_{_AREA}_roleplays") == 1, keys
    assert keys.count(f"goal_n_{_AREA}_contacts_made") == 1, keys
