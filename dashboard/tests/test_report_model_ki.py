"""The Informes model's identity, coverage and Key Indicators — step R3.

`app/reports/model.py`. A hand-built `ReportData` throughout, never the live
sheet: `build_report` is pure over it by construction, and the numbers below are
small enough to check on paper.

The fixture is five areas over two zones, reporting badly on purpose — three
areas one week and two the next. That is the shape every hazard in this file
takes. A mission total summed over five area-weeks, held against a goal summed
over nine, is the 2.040% bug; a compliance line reading "4 of 5 areas" when only
two filed last week is the flattering one.
"""

from datetime import date

import pandas as pd
import pytest

from app.reports import model as M
from app.reports import periods as P
from app.reports import scope as S

TODAY = date(2026, 9, 21)          # Monday, two complete weeks into 2026-6
W1, W2 = date(2026, 9, 13), date(2026, 9, 20)

CYCLES = [
    {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1",
     "Companion1_Name": "Elder Uno", "Companion2_Name": "Elder Dos"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A3", "Zone": "Norte", "District": "D2"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D3"},
    {"Area_Name": "B2", "Zone": "Sur", "District": "D3"},
])

NEW = "ki_new_people_real"
LESSONS = "ki_member_lessons_real"
ABSENT = "ki_rc_at_church_real"      # declared, never a column — see the test

# Week 1: A1, A2, B1 filed. Week 2: A1, A3. Five area-weeks of a possible ten.
# `new` totals 80 across the mission; `lessons` is A1's alone, 20 of it.
WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 10, LESSONS: 10},
    {"_week": "2026-09-13", "_area": "A2", NEW: 20, LESSONS: 0},
    {"_week": "2026-09-13", "_area": "B1", NEW: 30, LESSONS: 0},
    {"_week": "2026-09-20", "_area": "A1", NEW: 12, LESSONS: 10},
    {"_week": "2026-09-20", "_area": "A3", NEW: 8, LESSONS: 0},
])

DAILY = pd.DataFrame(
    [{"_day": d, "_area": a}
     for d in ("2026-09-14", "2026-09-15", "2026-09-16")
     for a in ("A1", "A2", "B1")]
)

# Every area has a 2026-6 goal; only A1 has one for 2026-5 — the shape CCSM is
# really in, where 44 of 45 areas have no goal for the previous cycle.
GOALS = pd.DataFrame(
    [{"area": a, "transfer_start": "2026-09-07", NEW: 30, LESSONS: 12,
      ABSENT: 0} for a in ("A1", "A2", "A3", "B1", "B2")]
    + [{"area": "A1", "transfer_start": "2026-07-27", NEW: 30, LESSONS: 12,
        ABSENT: 0}]
)


def _ki_goals(week, areas=None):
    """The companionships' own goals for `week`, as `get_ki_goals_for_week`
    returns them: (goals, set_by, source_week, areas that filed the source).

    The counts differ from the result counts ON PURPOSE. Four areas filed the
    form week 1's goals were written on and five filed week 2's, against three
    and two areas reporting results — which is exactly the mismatch that makes
    a raw sum-over-sum meaningless.
    """
    if week == W1:
        return {NEW: 80.0, LESSONS: 80.0}, {NEW: 4, LESSONS: 2}, date(2026, 9, 6), 4
    return {NEW: 100.0, LESSONS: 100.0}, {NEW: 5, LESSONS: 2}, date(2026, 9, 13), 5


def _data(**over) -> M.ReportData:
    kw = dict(
        roster=ROSTER, weekly_ki=WEEKLY_KI, daily_log=DAILY,
        transfer_goals=GOALS, cycles=CYCLES,
        ki_keys=(NEW, LESSONS, ABSENT),
        labels={NEW: "Nuevas Personas", LESSONS: "Lecciones con Miembros",
                ABSENT: "Conversos Recientes"},
        mission_name="Misión de Prueba", today=TODAY, anchor=W2,
        ki_goals_fn=_ki_goals,
    )
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture
def data():
    return _data()


@pytest.fixture
def period(data):
    return P.resolve(P.THIS_TRANSFER, TODAY, data.cycles)


def _report(data, period, level=None, **where):
    sc = S.resolve(data.roster, level, mission_name=data.mission_name, **where)
    comp = P.comparison_for(period, TODAY, data.cycles)
    return M.build_report(sc, period, comp, data)


# ── The four levels ───────────────────────────────────────────────────────────

def test_the_mission_sums_every_area_that_reported(data, period):
    row = _report(data, period).ki(NEW)
    assert row.actual == 80
    assert row.actual_area_weeks == 5


def test_a_zone_sums_only_its_own(data, period):
    """Membership comes from MISSION_ORG, never from a row's own Zone column —
    the WEEKLY_KI fixture does not even have one."""
    assert _report(data, period, S.ZONE, zone="Norte").ki(NEW).actual == 50
    assert _report(data, period, S.ZONE, zone="Sur").ki(NEW).actual == 30


def test_a_district_and_an_area_narrow_the_same_way(data, period):
    assert _report(data, period, S.DISTRICT, zone="Norte",
                   district="D1").ki(NEW).actual == 42
    assert _report(data, period, S.AREA, area="A1").ki(NEW).actual == 22


def test_the_seven_are_always_rows_even_with_no_column_behind_them(data, period):
    """Decision 10 is a standing rule, not a filter. A Key Indicator that
    disappears from the table when nobody reports it is one nobody asks about."""
    m = _report(data, period)
    assert [r.key for r in m.key_indicators] == [NEW, LESSONS, ABSENT]
    assert m.ki(ABSENT).actual is None
    assert m.ki(ABSENT).grade.status is None


# ── Decision 12: the sum is the headline, the rate is the comparison ─────────

def test_the_two_bases_are_different_numbers_and_both_are_carried(data, period):
    """80 new people over five area-weeks that filed is 16; over the ten
    area-weeks the mission actually had is 8. The first is what attainment and
    change are computed on, the second is what ranks one unit against another.
    Using either for the other's job is a different report."""
    row = _report(data, period).ki(NEW)
    assert row.actual == 80
    assert row.per_reporting_area_week == pytest.approx(16)
    assert row.per_active_area_week == pytest.approx(8)


def test_a_silent_area_drags_the_per_active_rate_and_not_the_reporting_one(data, period):
    """Sur reported 30 from one of its two areas in one of two weeks. Per
    reporting area-week that is 30; per active area-week it is 7.5, and a zone
    whose areas go silent ranking lower is `zone_comparison`'s standing rule,
    on purpose."""
    row = _report(data, period, S.ZONE, zone="Sur").ki(NEW)
    assert row.per_reporting_area_week == pytest.approx(30)
    assert row.per_active_area_week == pytest.approx(7.5)


def test_the_two_bases_agree_when_every_area_reported_every_week(data, period):
    """A1 filed both weeks, so there is nothing for the bases to disagree
    about. This is what the rest of the mission would look like at 100%."""
    row = _report(data, period, S.AREA, area="A1").ki(NEW)
    assert row.per_reporting_area_week == row.per_active_area_week == 11


# ── The goal, and the population it rests on ─────────────────────────────────

def test_attainment_reduces_both_sides_before_dividing(data, period):
    """180 of goal over nine area-weeks is 20 per area-week; 80 of result over
    five is 16. 80%, not the 44% the two raw sums would have given."""
    row = _report(data, period).ki(NEW)
    assert row.meta == 180
    assert row.meta_area_weeks == 9
    assert row.meta_per_area_week == pytest.approx(20)
    assert row.grade.pct == pytest.approx(80)
    assert row.grade.status == "warn"


def test_the_divisor_is_who_filed_the_form_not_who_filled_that_box(data, period):
    """Four area-weeks wrote a lessons goal; nine filed the form it was written
    on. Dividing 180 by the four would read the mission as aiming at 45 lessons
    per area per week, when five of the nine areas committed to none.
    `meta_set_by` is the caption, and only the caption."""
    row = _report(data, period).ki(LESSONS)
    assert (row.meta, row.meta_area_weeks, row.meta_set_by) == (180, 9, 4)
    assert row.meta_per_area_week == pytest.approx(20)
    assert row.meta / row.meta_set_by == pytest.approx(45)   # the wrong answer


def test_a_goal_nobody_set_reads_zero_rather_than_missing(data, period):
    """Areas DID file the form; none of them wrote a number in this box. That
    is a commitment to nothing, which cannot be graded against — so the row
    shows zero and carries no status, rather than pretending to a percentage."""
    row = _report(data, period).ki(ABSENT)
    assert row.meta == 0
    assert row.meta_per_area_week == 0        # nine area-weeks aiming at none
    assert row.grade.pct is None and row.grade.status is None


# ── Decision 22: the flag is the mission's verdict, handed down ──────────────

def test_an_unusable_goal_is_judged_at_mission_scope_and_applied_everywhere():
    """A1 reaches half of the lessons goal and would grade "bad" on its own.
    The mission reaches a fifth of it, which is not a yardstick — so the row is
    flagged rather than scored, at every level, including A1's."""
    data = _data()
    period = P.resolve(P.THIS_TRANSFER, TODAY, data.cycles)
    assert data.ki_goal_flags(period)[LESSONS] == "goal_too_high"

    area = _report(data, period, S.AREA, area="A1").ki(LESSONS)
    assert area.grade.pct == pytest.approx(50)     # it would have been graded
    assert area.grade.status is None               # but it is flagged instead
    assert area.grade.flag_label.startswith("meta no utilizable")


def test_a_usable_goal_is_not_flagged_anywhere(data, period):
    assert data.ki_goal_flags(period)[NEW] is None
    assert _report(data, period, S.AREA, area="A1").ki(NEW).grade.flag is None


# ── Decision 11 and 23: the leadership mark ─────────────────────────────────

def test_the_transfer_goal_is_pro_rated_to_the_part_of_the_cycle_covered(data, period):
    """Five areas at 30 each is 150 for the whole of 2026-6; two of its six
    weeks have happened, so a third of it is the mark."""
    row = _report(data, period).ki(NEW)
    assert row.leadership_goal == pytest.approx(50)
    assert row.has_leadership_goal


def test_a_cycle_only_one_area_planned_reads_sin_meta(data):
    """Decision 23. 2026-5's goal exists for A1 alone; a mission bar marked
    with one companionship's target would be a fabricated mission figure."""
    past = P.resolve(P.LAST_TRANSFER, TODAY, CYCLES)
    row = _report(data, past).ki(NEW)
    assert row.leadership_goal_areas == 1
    assert not row.has_leadership_goal
    assert not row.leadership_goal_complete


def test_an_areas_own_mark_is_its_own_goal(data, period):
    assert _report(data, period, S.AREA,
                   area="A1").ki(NEW).leadership_goal == pytest.approx(10)


# ── Coverage, and the compliance headline (decision 19) ─────────────────────

def test_coverage_counts_area_weeks_not_areas(data, period):
    m = _report(data, period)
    assert m.coverage.label == "2 de 2 semanas"
    assert m.coverage.area_weeks_reported == 5
    assert m.coverage.reporting_rate == pytest.approx(0.5)


def test_the_compliance_headline_does_not_flatter(data, period):
    """Four of five areas filed something across the two weeks, but only two
    filed the second of them. A subtitle reading "4 de 5 áreas" would hide
    that, so a multi-week period reports the area-WEEK rate instead."""
    m = _report(data, period)
    assert len(m.areas_reporting) == 4
    assert m.compliance_label == "5 de 10 informes semanales (50%)"
    assert m.subtitle == ("2026-6 · 2 de 6 semanas completas · "
                          "5 de 10 informes semanales (50%)")


def test_a_single_week_period_reports_a_plain_count(data):
    """Over one week the area count and the area-week rate are the same thing,
    and the count is the sentence a person would say."""
    week = P.resolve(P.LAST_WEEK, TODAY, CYCLES)
    assert _report(data, week).compliance_label == "2 de 5 áreas informaron"


def test_one_area_gets_a_singular_verb(data):
    week = P.resolve(P.LAST_WEEK, TODAY, CYCLES)
    assert _report(data, week, S.AREA,
                   area="A1").compliance_label == "1 de 1 área informó"


def test_the_silent_areas_are_named(data, period):
    """Decision 16 — at every level, the mission included."""
    assert _report(data, period).areas_silent == ("B2",)
    assert _report(data, period, S.ZONE, zone="Sur").areas_silent == ("B2",)


def test_nightly_coverage_stops_at_the_compliance_anchor(data, period):
    """The period runs to Monday 21 September, but the last day does not count
    as a miss until the evening refresh has run. Nine area-days filed of a
    possible 14 days x 5 areas."""
    cov = _report(data, period).nightly_coverage
    assert cov.days_possible == 14 * 5
    assert cov.days_reported == 9
    assert cov.label == "9 de 70 días-área"


# ── A scope with nothing in it ───────────────────────────────────────────────

def test_a_scope_that_reported_nothing_says_so_rather_than_showing_zeros(data, period):
    """B2 filed neither week. "No reading" and "a reading of nothing" are
    different claims and must not render alike."""
    m = _report(data, period, S.AREA, area="B2")
    assert m.areas_reporting == ()
    assert m.ki(NEW).actual is None
    assert m.ki(NEW).per_reporting_area_week is None
    assert m.ki(NEW).grade.status is None
    assert not m.coverage.usable
    assert m.compliance_label == "0 de 2 informes semanales (0%)"


def test_a_period_before_any_data_still_builds(data):
    """Every Key Indicator present, every number absent. A page that renders
    empty is better than a page that raises."""
    old = P.resolve(P.LAST_WEEK, date(2026, 8, 1), CYCLES)
    m = _report(data, old)
    assert len(m.key_indicators) == 3
    assert all(r.actual is None for r in m.key_indicators)


def test_an_empty_weekly_ki_tab_does_not_take_the_page_down(period):
    m = _report(_data(weekly_ki=pd.DataFrame()), period)
    assert len(m.key_indicators) == 3
    assert m.coverage.weeks_reported == 0


# ── The comparison ───────────────────────────────────────────────────────────

def test_the_comparison_window_is_measured_on_the_same_basis(data, period):
    """The default pill holds 2026-6's two weeks against 2026-5's first two.
    Nothing was reported then, so there is no `before` — and the change is
    None rather than a fall from nothing."""
    row = _report(data, period).ki(NEW)
    assert row.before_per_reporting_area_week is None
    assert row.grade.change_pct is None


def test_the_preceding_weeks_pill_produces_a_real_change():
    """The same mission, with the fortnight before transfer day reported: 40
    new people over four area-weeks is 10, against 16 now."""
    before = pd.DataFrame([
        {"_week": "2026-08-30", "_area": "A1", NEW: 10, LESSONS: 0},
        {"_week": "2026-08-30", "_area": "A2", NEW: 10, LESSONS: 0},
        {"_week": "2026-09-06", "_area": "A1", NEW: 10, LESSONS: 0},
        {"_week": "2026-09-06", "_area": "B1", NEW: 10, LESSONS: 0},
    ])
    data = _data(weekly_ki=pd.concat([WEEKLY_KI, before], ignore_index=True))
    period = P.resolve(P.THIS_TRANSFER, TODAY, CYCLES)
    comp = P.comparison_for(period, TODAY, CYCLES, against=P.COMPARE_PRECEDING)
    m = M.build_report(S.mission_scope(data.roster, data.mission_name),
                       period, comp, data)
    assert m.ki(NEW).before_per_reporting_area_week == pytest.approx(10)
    assert m.ki(NEW).grade.change_pct == pytest.approx(60)
    assert m.comparison_coverage.label == "2 de 2 semanas"
