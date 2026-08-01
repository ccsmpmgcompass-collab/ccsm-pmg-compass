"""Regression test for the Mission Goals duplicate-widget-key crash.

`report_date` is defined on BOTH forms in CcsmData.gs, so QUESTIONS_CONFIG
holds it twice. The Mission Goals section calls get_question_metrics() with no
form_type filter, so both rows came back, both reached st.number_input with the
key `mission_extra_report_date`, and the whole page died with
StreamlitDuplicateElementKey before rendering anything.

The fixture below feeds the SHAPE of the live tab (a key repeated across form
types), not a copy of it — the fix has to hold for any future CcsmData.gs edit
that repeats the mistake, not just for `report_date`.
"""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

# Two genuinely duplicated keys: report_date (the real one, excluded by name)
# and exchanges (a countable metric, which must survive as exactly ONE box).
_QUESTIONS = pd.DataFrame([
    {"Form_Type": "NIGHTLY", "Metric_Key": "report_date",
     "Metric_Display_Name": "Fecha del Reporte", "Active": "TRUE"},
    {"Form_Type": "NIGHTLY", "Metric_Key": "exchanges",
     "Metric_Display_Name": "Intercambios", "Active": "TRUE"},
    {"Form_Type": "NIGHTLY", "Metric_Key": "roleplays",
     "Metric_Display_Name": "Dramatizaciones", "Active": "TRUE"},
    {"Form_Type": "WEEKLY", "Metric_Key": "report_date",
     "Metric_Display_Name": "Fecha del Reporte", "Active": "TRUE"},
    {"Form_Type": "WEEKLY", "Metric_Key": "exchanges",
     "Metric_Display_Name": "Intercambios", "Active": "TRUE"},
])


@pytest.fixture(autouse=True)
def _questions_config_with_duplicates(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return _QUESTIONS.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)


def _run_mission_goals(lang="en"):
    at = AppTest.from_file("pages/02_Metas.py", default_timeout=90)
    at.session_state["pmg_lang"] = lang
    at.session_state["goals_active_section"] = "Mission Goals"
    at.run()
    return at


def test_mission_goals_survives_a_metric_key_defined_on_both_forms():
    at = _run_mission_goals()
    assert not at.exception, f"Mission Goals raised: {at.exception}"


def test_no_widget_key_is_used_twice():
    """The crash's actual signature. Asserted on the rendered widget keys
    rather than on the absence of an exception, so a future refactor that
    dedupes by accident (or stops rendering the expander at all) can't pass
    this by rendering nothing."""
    at = _run_mission_goals()
    keys = [w.key for w in at.number_input if w.key]
    assert len(keys) == len(set(keys)), \
        f"duplicate widget keys: {sorted(k for k in keys if keys.count(k) > 1)}"
    assert any(k.startswith("mission_extra_") for k in keys), \
        "Other Metrics rendered no boxes at all — the test proves nothing"


def test_report_date_is_not_offered_as_a_goal():
    """It's the date the report covers, not a countable production number."""
    at = _run_mission_goals()
    keys = {w.key for w in at.number_input if w.key}
    assert "mission_extra_report_date" not in keys


def test_a_duplicated_countable_metric_still_gets_exactly_one_box():
    """Dropping the repeat must not drop the metric."""
    at = _run_mission_goals()
    keys = [w.key for w in at.number_input if w.key]
    assert keys.count("mission_extra_exchanges") == 1, keys
