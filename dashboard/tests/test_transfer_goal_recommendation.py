"""A cycle's REC must be the area's own average stretched — not a weekly floor
multiplied by six.

Zackary, 2026-09-05, looking at the first real REC values on the Metas page:
"the baptism goal for the transfer can't default to 6 because it's extremely
unlikely it will happen."

He was right, and the cause was arithmetic rather than anything about baptisms.
`_stretch_recommendation` floors every weekly figure at 1 — a DISPLAY rule, so
a badge never reads 0 — and `get_recommended_transfer_goals` used to multiply
that floored badge by the cycle's weeks. Los Huertos has reported 0 baptisms in
every week it has submitted, so the floor fired and six weeks of "the badge
cannot show 0" became "baptize six people this cambio".

The same double rounding inflated every metric with a fractional average:
`ki_rc_at_church_real` sits at a flat 2 a week there, and ceil(2 x 1.1) x 6
recommended 18 where the honest stretch is ceil(2 x 1.1 x 6) = 14.

The fix scales the MEAN and rounds once, at the cadence the number is shown at.
The weekly badge is untouched — its floor is correct for a week, and two other
callers depend on it.
"""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

import app.db.queries as q
from app.config import metric_catalog as mc

QUESTIONS = pd.DataFrame([
    {"Metric_Key": "ki_baptized_confirmed_real",
     "Metric_Display_Name": "Bautizados y Confirmados (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_rc_at_church_real",
     "Metric_Display_Name": "Conversos Recientes en la Iglesia (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_member_lessons_real",
     "Metric_Display_Name": "Lecciones con Miembros (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    # Flat 2 a week like ki_rc_at_church_real, but bounded by effort rather
    # than by a roster — so it carries the double-rounding guard now that the
    # RC metric is clamped.
    {"Metric_Key": "ki_friends_sacrament_real",
     "Metric_Display_Name": "Amigos en la Reunión Sacramental (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_new_people_meta",
     "Metric_Display_Name": "Nuevas Personas (Meta)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "contacts_attempted", "Metric_Display_Name": "Intentos de Contacto",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    # The three nightly questions that carry no countable quantity. CCSM asks
    # all three, and every one of them drew a goal box and a REC badge until
    # 2026-09-06.
    {"Metric_Key": "report_date", "Metric_Display_Name": "Fecha del Informe",
     "Form_Type": "NIGHTLY", "Data_Type": "DATE", "Active": "TRUE"},
    {"Metric_Key": "exchanges", "Metric_Display_Name": "Intercambios",
     "Form_Type": "NIGHTLY", "Data_Type": "YESNO", "Active": "TRUE"},
    {"Metric_Key": "effort", "Metric_Display_Name": "Nivel de Esfuerzo",
     "Form_Type": "NIGHTLY", "Data_Type": "CHOICE", "Active": "TRUE"},
])

#: Los Huertos' real WEEKLY_KI rows, probed live 2026-09-05. Three completed
#: weeks, all well in the past so `exclude_current_week` keeps every one.
WEEKLY = pd.DataFrame([
    {"area": "Los Huertos", "week_end_date": "2026-08-09",
     "ki_baptized_confirmed_real": 0, "ki_rc_at_church_real": 2,
     "ki_friends_sacrament_real": 2,
     "ki_member_lessons_real": 1},
    {"area": "Los Huertos", "week_end_date": "2026-08-16",
     "ki_baptized_confirmed_real": 0, "ki_rc_at_church_real": 2,
     "ki_friends_sacrament_real": 2,
     "ki_member_lessons_real": 0},
    {"area": "Los Huertos", "week_end_date": "2026-08-23",
     "ki_baptized_confirmed_real": 0, "ki_rc_at_church_real": 2,
     "ki_friends_sacrament_real": 2,
     "ki_member_lessons_real": 0},
])

NIGHTLY = pd.DataFrame([
    {"area": "Los Huertos", "week_end_date": "2026-08-09", "contacts_attempted": 40},
    {"area": "Los Huertos", "week_end_date": "2026-08-16", "contacts_attempted": 40},
])

WEEKS = 6.0   # every CCSM cycle in TRANSFER_SCHEDULE


@pytest.fixture
def live(monkeypatch):
    """The catalogue and the two history frames, without touching the sheet."""
    monkeypatch.setattr(
        "app.db.sheets_client._read_tab_cached",
        lambda tab, header_marker=None: (
            QUESTIONS.copy() if tab == "QUESTIONS_CONFIG" else pd.DataFrame()))
    monkeypatch.setattr(q, "get_weekly_ki", lambda: NIGHTLY.copy())
    monkeypatch.setattr(q, "get_weekly_form_data", lambda: WEEKLY.copy())
    monkeypatch.setattr(q, "get_question_metrics", lambda: [
        (r["Metric_Key"], r["Metric_Display_Name"], r["Form_Type"])
        for _, r in QUESTIONS.iterrows()])
    monkeypatch.setattr(q, "get_rec_stretch_pct", lambda: 10)
    mc.clear_cache()
    q.get_recommended_transfer_goals.clear()
    yield
    q.get_recommended_transfer_goals.clear()
    mc.clear_cache()


def _rec(area="Los Huertos", weeks=WEEKS):
    return q.get_recommended_transfer_goals(area, weeks)


# ── the report that started this ─────────────────────────────────────────────

def test_an_area_with_no_baptisms_is_recommended_one_not_one_per_week(live):
    """0, 0, 0 across every reported week. The cycle floor is 1, not 1 x 6."""
    assert _rec()["ki_baptized_confirmed_real"] == 1


def test_the_floor_is_applied_once_whatever_the_cycle_length(live):
    """A longer cycle must not raise a floor. The floor says "we cannot show
    zero", and that is equally true of a five-week cycle and a seven-week one."""
    for weeks in (1.0, 5.0, 6.0, 7.0, 6.2857):
        assert _rec(weeks=weeks)["ki_baptized_confirmed_real"] == 1


# ── the same rule, applied to what an area actually did ──────────────────────

def test_a_real_average_is_stretched_then_scaled_once(live):
    """2 a week, stretched 10%, over six weeks: ceil(2 x 1.1 x 6) = 14.

    The old path rounded first — ceil(2 x 1.1) = 3 — and scaled the rounded
    figure to 18. That is a 29% overstatement produced entirely by rounding.

    Asked of friends at sacrament meeting rather than of recent converts at
    church: the two have identical history here, but the RC metric is now
    clamped to its roster (below), which would mask this.
    """
    assert _rec()["ki_friends_sacrament_real"] == 14
    assert _rec()["ki_friends_sacrament_real"] != 18


def test_a_fractional_average_survives_to_the_cycle_total(live):
    """1 lesson in three weeks is 0.33 a week — a real signal that the old path
    threw away by flooring it to 1 and then recommending 6."""
    assert _rec()["ki_member_lessons_real"] == math.ceil(1 / 3 * 1.1 * 6)   # 3


def test_a_metric_the_area_has_never_recorded_still_recommends_one(live):
    """`_stretch_means` returns nothing for a key absent from the frame, so the
    dict comprehension's own floor is what answers. Every box keeps a REC pill."""
    assert _rec()["contacts_attempted"] >= 1
    assert _rec(area="Nueva Área")["ki_baptized_confirmed_real"] == 1


# ── the weekly badge is deliberately unchanged ───────────────────────────────

def test_the_weekly_badge_still_floors_at_one(live):
    """`_stretch_recommendation` keeps its floor: `get_recommended_goals` and
    `get_mission_recommended_goals` both show a weekly number, where a badge
    reading 0 tells a companionship nothing. Only the scaling caller changed."""
    weekly = q._stretch_recommendation(WEEKLY.copy(),
                                       ["ki_baptized_confirmed_real"], "Los Huertos")
    assert weekly["ki_baptized_confirmed_real"] == 1


def test_the_weekly_badge_still_rounds_up(live):
    """2 a week + 10% is 2.2, and the badge shows 3 — unchanged."""
    weekly = q._stretch_recommendation(WEEKLY.copy(),
                                       ["ki_rc_at_church_real"], "Los Huertos")
    assert weekly["ki_rc_at_church_real"] == 3


def test_the_means_underneath_are_not_rounded(live):
    """The whole point of the split: `_stretch_means` hands back 2.2, so the
    caller can decide where the rounding belongs."""
    means = q._stretch_means(WEEKLY.copy(), ["ki_rc_at_church_real"], "Los Huertos")
    assert means["ki_rc_at_church_real"] == pytest.approx(2.2)


# ── the roster ceiling ───────────────────────────────────────────────────────
#
# Zackary, 2026-09-06, on being recommended 14 recent converts at church:
# "We only have 2 converts, and if each of them come every week that would lead
# us to 12 at the end of the transfer, not 14. We can't jump up that number
# until we have another baptism."
#
# `ki_rc_at_church_real` is bounded by a roster the companionship cannot grow
# inside a cycle — only a baptism grows it. A percentage stretch is the wrong
# operator for it, and over six Sundays two converts can produce twelve
# attendances and no more. Probed the same day: the stretch exceeded the
# ceiling for 9 of the mission's 41 reporting areas, and every one of those
# nine was already at PERFECT attendance (mean == peak).

RC = "ki_rc_at_church_real"


def _weeks(values, first="2026-05-31", area="Los Huertos"):
    """One row per week, `values` in order, ending well before the current one."""
    start = date.fromisoformat(first)
    return pd.DataFrame([
        {"area": area,
         "week_end_date": (start + timedelta(days=7 * i)).isoformat(),
         RC: v}
        for i, v in enumerate(values)
    ])


def test_a_capped_metric_is_never_recommended_past_its_roster(live):
    """2, 2, 2 — everyone already comes every week. Six Sundays, ceiling 12."""
    assert _rec()[RC] == 12


def test_the_uncapped_stretch_would_have_asked_for_more(live):
    """Guards the point of the test above: without the clamp this is 14."""
    assert math.ceil(2.0 * 1.1 * WEEKS) == 14
    assert _rec()[RC] < 14


def test_an_area_with_slack_keeps_its_stretch(live, monkeypatch):
    """Peak 3 means at least three converts, so the ceiling is 18 and the
    stretch of 14 is achievable. The clamp fires only where it must."""
    monkeypatch.setattr(q, "get_weekly_form_data", lambda: _weeks([2, 1, 3]))
    q.get_recommended_transfer_goals.clear()
    assert _rec()[RC] == 14


def test_the_ceiling_follows_the_cycle_length(live):
    """A five-week cycle offers five Sundays, so two converts cap at 10."""
    assert _rec(weeks=5.0)[RC] == 10
    assert _rec(weeks=1.0)[RC] == 2


def test_the_peak_sets_the_ceiling_not_the_average(live, monkeypatch):
    """0, 2, 0 is a mean of 0.67 but still proves two converts exist."""
    monkeypatch.setattr(q, "get_weekly_form_data", lambda: _weeks([0, 2, 0]))
    q.get_recommended_transfer_goals.clear()
    assert q.roster_ceiling(_weeks([0, 2, 0]), RC, "Los Huertos", 6.0) == 12


def test_an_old_peak_stops_holding_the_ceiling_up(live):
    """A convert who has since aged out of "recent", or moved away, must not
    raise today's ceiling forever — the peak looks back twelve weeks."""
    fourteen = _weeks([9] + [2] * 13)          # the 9 is fourteen weeks back
    assert q.roster_ceiling(fourteen, RC, "Los Huertos", 6.0) == 12


def test_a_metric_that_is_not_roster_capped_has_no_ceiling(live):
    """Only declared metrics are capped. Finding new people is bounded by
    effort, not by a roster, so nothing clamps it."""
    assert q.roster_ceiling(WEEKLY.copy(), "ki_new_people_real",
                            "Los Huertos", 6.0) is None


def test_an_area_with_no_history_has_no_ceiling(live):
    """No evidence of a roster is not evidence of an empty one — a new area
    falls back to the ordinary floor rather than being capped at nothing."""
    assert q.roster_ceiling(WEEKLY.copy(), RC, "Nueva Área", 6.0) is None
    assert _rec(area="Nueva Área")[RC] == 1


# ── metrics a goal cannot apply to ───────────────────────────────────────────
#
# Zackary, 2026-09-06: "take out goals for the date, intercambios, and effort
# level." A weekly goal of 3 for a DATE, a YESNO or a three-way CHOICE is not a
# smaller or larger target — it is a category error. All three still drew a
# number box on the Goals page, a REC badge of 1, and a column in the bulk
# preview table every leader reads before saving goals for the whole mission.
#
# The weekly half of this rule has excluded CHOICE since it was written
# (_goalable_weekly_keys); the nightly half never got it.

def test_non_numeric_metrics_get_no_recommendation(live):
    rec = _rec()
    for key in ("report_date", "exchanges", "effort"):
        assert key not in rec, key


def test_countable_nightly_metrics_still_do(live):
    """The filter must not take the whole nightly form with it."""
    assert _rec()["contacts_attempted"] >= 1


def test_the_rule_reads_the_sheet_not_a_list_of_keys(live):
    """Data_Type decides, so a mission whose form asks a different CHOICE
    question is covered without a code change — the same reason the KI set is
    taken from the catalogue rather than written down."""
    defs = [("whatever_we_call_it", "Cualquiera", "NIGHTLY")]
    assert q._goalable_nightly_keys(defs) == ["whatever_we_call_it"]
    from app.config.metric_catalog import non_numeric_metrics
    assert non_numeric_metrics() == {"report_date", "exchanges", "effort"}
