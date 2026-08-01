"""The Effort score must be CCSM's, and must agree with the agent that wrote it.

The dashboard recomputes an Effort score alongside the one CCSM_AgentScores.gs
writes into SCORES. That recomputation used a hardcoded weight map of Utah
Provo's metrics — nm_lessons 30, new_found 25, mmm_sent 20, pew 15, gate 10 —
and pulled its actuals from WEEKLY_KI (for the first three) and the weekly form
(for the last two).

CCSM collects none of those five, and its WEEKLY_KI holds only the weekly form's
ki_* pairs, so the merge contributed nothing, the `if pd.isna(r["nm_lessons"])`
guard fired on every row, and the function returned NaN for all 98 areas. On
screen that is an empty Effort column and an empty breakdown chart — which reads
as "no data yet", not as a calculation that cannot work.

Weights now come from SCORE_CONFIG's `effort` component, the same tab and the
same precedence CCSM_AgentScores.gs uses, so the dashboard EXPLAINS the agent's
score instead of computing a rival one.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

import app.db.queries as q

# CCSM's real SCORE_CONFIG shape: two sections split by a blank row.
SCORE_CONFIG = pd.DataFrame(
    [
        ["ALL", "contacts_attempted", "effort", "0.3", "TRUE"],
        ["ALL", "roleplays", "effort", "0.2", "TRUE"],
        ["ALL", "member_contacts", "effort", "0.2", "TRUE"],
        ["ALL", "effort", "effort", "0.3", "TRUE"],
        ["ALL", "contact_rate", "skill", "0.3", "TRUE"],
        ["ALL", "retired_metric", "effort", "0.9", "FALSE"],
        ["A014", "roleplays", "effort", "0.5", "TRUE"],
        ["", "", "", "", ""],
        ["Area_Code", "Effort_Weight", "Skill_Weight", "KI_Weight", ""],
        ["ALL", "0.33", "0.33", "0.34", ""],
    ],
    columns=["Area_Code", "Metric_Key", "Score_Component", "Weight", "Active"],
)


# QUESTIONS_CONFIG is what declares a metric non-numeric. get_daily_log() runs
# every metric column through _num(), which coerces "Todo" to NaN and then fills
# it with 0 — so by the time a value reaches the scorer, a CHOICE metric is
# indistinguishable from a real zero. The Data_Type column is the only source of
# truth, which is why this fixture has to carry it.
QUESTIONS = pd.DataFrame([
    {"Metric_Key": "contacts_attempted", "Metric_Display_Name": "Intentos de Contacto",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "roleplays", "Metric_Display_Name": "Prácticas de Enseñanza",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "member_contacts", "Metric_Display_Name": "Contactos con Miembros",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "effort", "Metric_Display_Name": "Nivel de Esfuerzo",
     "Form_Type": "NIGHTLY", "Data_Type": "CHOICE", "Active": "TRUE"},
])


def _daily_log():
    """One full Mon–Sun week for one area. 2026-08-03 Mon … 2026-08-09 Sun."""
    rows = []
    start = date(2026, 8, 3)
    for i in range(7):
        rows.append({
            "Date": (start + timedelta(days=i)).isoformat(),
            "Area": "Arauco 1", "Zone": "Arauco", "District": "Arauco",
            "contacts_attempted": 20,
            "roleplays": 1,
            "member_contacts": 2,
            # CHOICE metric: real DAILY_LOG stores the Spanish word, not a number.
            "effort": "Todo",
        })
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    daily = _daily_log()

    def fake(tab_name, header_marker=None):
        if tab_name == "SCORE_CONFIG":
            return SCORE_CONFIG.copy()
        if tab_name == "DAILY_LOG":
            return daily.copy()
        if tab_name == "QUESTIONS_CONFIG":
            return QUESTIONS.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    from app.config import metric_catalog as mc
    caches = (q.get_daily_log, q.get_score_component_weights, q.get_weekly_ki)
    for fn in caches:
        if hasattr(fn, "clear"):
            fn.clear()
    mc.clear_cache()
    yield
    for fn in caches:
        if hasattr(fn, "clear"):
            fn.clear()
    mc.clear_cache()


# ── SCORE_CONFIG reader ───────────────────────────────────────────────────────

def test_effort_weights_come_from_score_config():
    w = q._effort_metric_weights()
    assert w == {"contacts_attempted": 0.3, "roleplays": 0.2,
                 "member_contacts": 0.2, "effort": 0.3}


def test_no_provo_metric_is_weighted():
    w = q._effort_metric_weights()
    assert not ({"nm_lessons", "new_found", "mmm_sent", "pew", "gate"} & set(w))


def test_inactive_rows_are_ignored():
    assert "retired_metric" not in q._effort_metric_weights()


def test_other_components_are_not_mixed_in():
    """A skill metric scored as effort would silently change every area's
    Effort score without changing anything visible in the config."""
    assert "contact_rate" not in q._effort_metric_weights()
    assert "contact_rate" in q.get_score_component_weights("skill")


def test_per_area_row_overrides_the_all_row():
    """Matches applySection1()'s precedence in CCSM_AgentScores.gs."""
    assert q._effort_metric_weights("A014")["roleplays"] == 0.5
    assert q._effort_metric_weights("A014")["contacts_attempted"] == 0.3


def test_section_two_is_not_parsed_as_weights():
    """Section 2 rows have a different meaning. Reading past the blank
    separator would turn effectiveness sub-weights into metric weights."""
    w = q.get_score_component_weights("effort")
    assert "Effort_Weight" not in w and "0.33" not in w


# ── Actuals ───────────────────────────────────────────────────────────────────

def test_actuals_sum_the_week_from_daily_log():
    a = q.get_area_effort_actuals_weekly("Arauco 1", "2026-08-09")
    assert a is not None, "a full week of submissions produced no actuals"
    assert a["contacts_attempted"] == 140.0   # 7 days x 20
    assert a["roleplays"] == 7.0
    assert a["member_contacts"] == 14.0


def test_a_choice_metric_is_excluded_not_counted_as_zero():
    """`effort` is Todo / La mayor parte / Algo. Coercing it to 0 would drag
    every area's Effort score down by its full 0.3 weight, permanently."""
    a = q.get_area_effort_actuals_weekly("Arauco 1", "2026-08-09")
    assert a["effort"] is None


def test_no_submissions_that_week_returns_none_not_zero():
    """None means "we cannot tell"; zero means "they did nothing". Rendering
    the first as the second accuses an area of inactivity."""
    assert q.get_area_effort_actuals_weekly("Arauco 1", "2026-07-05") is None
    assert q.get_area_effort_actuals_weekly("No Such Area", "2026-08-09") is None


# ── Scoring ───────────────────────────────────────────────────────────────────

def test_score_is_computed_and_in_range():
    a = q.get_area_effort_actuals_weekly("Arauco 1", "2026-08-09")
    exp = {"contacts_attempted": 140.0, "roleplays": 7.0, "member_contacts": 14.0}
    score = q.compute_effort_score(a, exp)
    assert score is not None, "meeting every expectation must produce a score"
    assert 0.0 <= score <= 100.0
    # Exactly meeting expectation scores 75 on this scale, per
    # _scale_effort_metric's docstring.
    assert round(score, 4) == 75.0


def test_excluded_metrics_renormalize_rather_than_deflate():
    """`effort` is None here, so the remaining 0.7 of weight must be scaled up
    to 1.0. If it were treated as a zero-scoring metric, an area that met every
    countable expectation would score 52.5 instead of 75."""
    actuals = {"contacts_attempted": 140.0, "roleplays": 7.0,
               "member_contacts": 14.0, "effort": None}
    exp = {"contacts_attempted": 140.0, "roleplays": 7.0, "member_contacts": 14.0}
    assert round(q.compute_effort_score(actuals, exp), 4) == 75.0


def test_score_is_none_when_nothing_can_be_scored():
    assert q.compute_effort_score({"effort": None}, {}) is None
    assert q.compute_effort_score({}, {}) is None


def test_unweighted_metric_is_skipped_not_crashed():
    """SCORE_CONFIG is editable from the Scores page, so a metric can vanish
    from scoring between one read and the next."""
    actuals = {"contacts_attempted": 140.0, "some_removed_metric": 5.0}
    score = q.compute_effort_score(actuals, {"contacts_attempted": 140.0})
    assert score is not None


def test_breakdown_matches_the_score_it_explains():
    a = q.get_area_effort_actuals_weekly("Arauco 1", "2026-08-09")
    exp = {"contacts_attempted": 140.0, "roleplays": 7.0, "member_contacts": 14.0}
    rows = q.compute_effort_score_breakdown(a, exp)
    assert {r["metric"] for r in rows} == {
        "contacts_attempted", "roleplays", "member_contacts"}
    total_w = sum(r["weight"] for r in rows)
    recomputed = sum(r["contribution"] for r in rows) / total_w
    assert round(recomputed, 6) == round(q.compute_effort_score(a, exp), 6), \
        "the pie chart must add up to the score printed beside it"


def test_batch_scores_every_area_that_submitted():
    scores_df = pd.DataFrame([
        {"Area_Name": "Arauco 1", "Week_Ending_Date": "2026-08-09"},
        {"Area_Name": "Arauco 1", "Week_Ending_Date": "2026-07-05"},
    ])
    out = q.compute_mission_president_effort_scores(scores_df)
    assert pd.notna(out.iloc[0]), "a week with real submissions must score"
    assert pd.isna(out.iloc[1]), "a week with no submissions must stay NaN"
