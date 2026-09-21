"""The rest of the Informes model — step R4.

Nightly metrics, scores, conversion rates, ranked children, the week-by-week
strip, and the strength/growth an area's page reads rather than recomputes.

The fixture is the same five areas as `test_report_model_ki.py`, reporting
unevenly on purpose. The two bases matter more here than anywhere else: a
nightly goal is one mission-wide number per area per week, so attainment
divides by every ACTIVE area-week, while the change divides by the area-DAYS
that actually filed. Nightly reporting on CCSM rose from 35 of 45 areas to 45
of 45 over six weeks, which on the wrong basis is a twenty per cent improvement
nobody worked for.
"""

from datetime import date

import pandas as pd
import pytest

from app.reports import model as M
from app.reports import periods as P
from app.reports import scope as S

TODAY = date(2026, 9, 21)
W1, W2 = date(2026, 9, 13), date(2026, 9, 20)

CYCLES = [
    {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A3", "Zone": "Norte", "District": "D2"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D3"},
    {"Area_Name": "B2", "Zone": "Sur", "District": "D3"},
])

NEW = "ki_new_people_real"
ATTEMPTS = "contacts_attempted"
MADE = "contacts_made"
LESSONS = "friend_lessons"

WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 10},
    {"_week": "2026-09-13", "_area": "A2", NEW: 20},
    {"_week": "2026-09-13", "_area": "B1", NEW: 30},
    {"_week": "2026-09-20", "_area": "A1", NEW: 12},
    {"_week": "2026-09-20", "_area": "A3", NEW: 8},
])


def _nights(days, areas, attempts, made=0, lessons=0, exchanges=0):
    return [{"_day": d, "_area": a, ATTEMPTS: attempts, MADE: made,
             LESSONS: lessons, M.EXCHANGES: exchanges}
            for d in days for a in areas]


# The period's own fortnight: A1 and A2 filed ten nights each, 100 attempts a
# night. The comparison fortnight: A1 alone, at the same 100 a night — so the
# mission did TWICE the work on the same per-night effort. A change measured
# per active area doubles; per reporting area-day it does not move at all, and
# that is the whole point of the split.
PERIOD_DAYS = [f"2026-09-{d:02d}" for d in range(7, 17)]
BEFORE_DAYS = [f"2026-08-{d:02d}" for d in range(25, 31)]
DAILY = pd.DataFrame(
    _nights(PERIOD_DAYS, ("A1", "A2"), 100, made=50, lessons=20, exchanges=1)
    + _nights(BEFORE_DAYS, ("A1",), 100, made=40, lessons=10)
)

BREAKDOWNS = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", M.EFFORT_SCORE: 2.0,
     "strength1_metric": ATTEMPTS, "strength2_metric": "", "growth_metric": LESSONS},
    {"_week": "2026-09-20", "_area": "A1", M.EFFORT_SCORE: 3.0,
     "strength1_metric": MADE, "strength2_metric": ATTEMPTS,
     "growth_metric": LESSONS},
    {"_week": "2026-09-20", "_area": "A2", M.EFFORT_SCORE: 1.0,
     "strength1_metric": "", "strength2_metric": "", "growth_metric": ""},
])

SCORES = pd.DataFrame([
    {"_week": w, "_area": a, "Effort_Score": e, "Skill_Score": e + 10,
     "KI_Score": e - 10, "Effectiveness_Score": e + 5}
    for w in ("2026-09-13", "2026-09-20")
    for a, e in (("A1", 80), ("A2", 60), ("A3", 40), ("B1", 20))
])

LABELS = {NEW: "Nuevas Personas", ATTEMPTS: "Intentos de Contacto",
          MADE: "Contactos", LESSONS: "Lecciones con Amigos",
          M.EXCHANGES: "Intercambios", M.EFFORT_SCORE: "Nivel de Esfuerzo"}

GOALS = pd.DataFrame([{"area": a, "transfer_start": "2026-09-07", NEW: 30}
                      for a in ("A1", "A2", "A3", "B1", "B2")])


def _ki_goals(week, areas=None):
    return {NEW: 80.0}, {NEW: 4}, date(2026, 9, 6), 4


def _data(**over) -> M.ReportData:
    kw = dict(
        roster=ROSTER, today=TODAY, anchor=W2,
        weekly_ki=WEEKLY_KI, daily_log=DAILY, breakdowns=BREAKDOWNS,
        scores=SCORES, transfer_goals=GOALS, cycles=CYCLES,
        ki_keys=(NEW,),
        nightly_keys=(ATTEMPTS, MADE, LESSONS, M.EXCHANGES, M.EFFORT_SCORE),
        nightly_goals={ATTEMPTS: 150, MADE: 75, LESSONS: 100},
        agent_config={"CONTACT_RATE_TARGET": "0.5", "LESSON_RATE_TARGET": "0.2"},
        labels=LABELS, mission_name="Misión de Prueba", ki_goals_fn=_ki_goals,
    )
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture
def data():
    return _data()


@pytest.fixture
def period(data):
    return P.resolve(P.THIS_TRANSFER, TODAY, data.cycles)


def _report(data, period, level=None, against=P.COMPARE_PRECEDING, **where):
    sc = S.resolve(data.roster, level, mission_name=data.mission_name, **where)
    comp = P.comparison_for(period, TODAY, data.cycles, against=against)
    return M.build_report(sc, period, comp, data)


def _row(model, key):
    return next(r for r in model.nightly_metrics if r.key == key)


# ── Decision 17: every tracked nightly metric ────────────────────────────────

def test_every_tracked_metric_gets_a_row(data, period):
    """Decision 17 — all of them, not an eight-metric shortlist. Including the
    two the nightly form asks that are not numbers."""
    m = _report(data, period)
    assert [r.key for r in m.nightly_metrics] == list(data.nightly_keys)


def test_the_raw_total_is_the_headline(data, period):
    """Two areas, ten nights, a hundred attempts a night."""
    assert _row(_report(data, period), ATTEMPTS).actual == 2000


def test_attainment_divides_by_every_active_area_week(data, period):
    """The goal is one mission-wide number per area per week, so the divisor is
    every roster area — an unreported night is work nobody recorded, and
    counting it as work would flatter the mission. 2000 over five areas and two
    weeks is 200 a week against a goal of 150."""
    row = _row(_report(data, period), ATTEMPTS)
    assert row.per_active_area_week == pytest.approx(200)
    assert row.grade.pct == pytest.approx(200 / 150 * 100)


def test_the_change_divides_by_the_area_days_that_filed(data, period):
    """Twenty area-days this fortnight against six before it, at the same 100
    attempts a night. The work per night did not move, and the row says so —
    on the active basis it would have read as a 233% improvement nobody made."""
    row = _row(_report(data, period), ATTEMPTS)
    assert row.per_reporting_area_week == pytest.approx(700)
    assert row.before_per_reporting_area_week == pytest.approx(700)
    assert row.grade.change_pct == pytest.approx(0)
    assert row.grade.status == "warn"


def test_a_real_movement_still_reads_as_one(data, period):
    """Contacts made went from 40 a night to 50 — up a quarter, past the
    fifteen-point flat band."""
    row = _row(_report(data, period), MADE)
    assert row.grade.change_pct == pytest.approx(25)
    assert row.grade.status == "good"


def test_a_nightly_row_is_never_graded_on_its_goal(data, period):
    """Decision 31. Lessons sit at 40% of goal — "bad" on the Key Indicator
    bands — and the row reads "good", because the work doubled."""
    row = _row(_report(data, period), LESSONS)
    assert row.grade.pct == pytest.approx(40)
    assert row.grade.change_pct == pytest.approx(100)
    assert row.grade.status == "good"


def test_the_yesno_question_counts_nights_rather_than_summing_a_word(data, period):
    """`exchanges` is a YESNO. `get_daily_log` coerces it to a wall of zeros,
    so the model restores it from the raw tab as a 1 or a 0 — twenty nights
    with an exchange, here."""
    assert _row(_report(data, period), M.EXCHANGES).actual == 20


def test_the_effort_choice_is_averaged_not_summed(data, period):
    """Todo / La mayor parte / Algo, as the agents already score it 1 to 3 in
    WEEKLY_BREAKDOWNS. Three area-weeks at 2, 3 and 1."""
    row = _row(_report(data, period), M.EFFORT_SCORE)
    assert row.actual == pytest.approx(2.0)
    assert row.actual_area_weeks == 3


def test_the_nightly_flag_is_the_missions_verdict(data, period):
    """Judged on attainment per active area-week — the basis decision 22's 25%
    floor was calibrated against. Nothing here is below it."""
    assert data.nightly_goal_flags(period) == {
        ATTEMPTS: None, MADE: None, LESSONS: None,
        M.EXCHANGES: None, M.EFFORT_SCORE: None,
    }


def test_a_goal_the_work_barely_touches_is_flagged(period):
    """A goal of 4000 attempts per area per week against 200 achieved: 5%, not
    a yardstick. Flagged at mission scope and handed down."""
    data = _data(nightly_goals={ATTEMPTS: 4000})
    assert data.nightly_goal_flags(period)[ATTEMPTS] == "goal_too_high"
    row = _row(_report(data, period, S.AREA, area="A1"), ATTEMPTS)
    assert row.grade.flag == "goal_too_high"


# ── Decision 18: the scores ──────────────────────────────────────────────────

def test_the_mission_gets_one_summary_row(data, period):
    """Four areas scored at 80, 60, 40 and 20 across two weeks."""
    sc = _report(data, period).scores
    assert sc.effort == pytest.approx(50)
    assert sc.skill == pytest.approx(60)
    assert sc.ki == pytest.approx(40)
    assert sc.effectiveness == pytest.approx(55)
    assert (sc.areas_scored, sc.weeks) == (4, 2)


def test_an_area_gets_its_rank_within_its_district(data, period):
    """D1 holds A1 and A2. A1 scores higher, so it is first of two."""
    sc = _report(data, period, S.AREA, area="A1").scores
    assert (sc.rank, sc.of) == (1, 2)
    assert _report(data, period, S.AREA, area="A2").scores.rank == 2


def test_a_zone_is_not_ranked_within_anything(data, period):
    sc = _report(data, period, S.ZONE, zone="Norte").scores
    assert sc.rank is None and sc.of is None
    assert sc.areas_scored == 3


def test_an_unscored_area_says_so_rather_than_scoring_zero(data, period):
    """B2 has no SCORES row. "Not scored yet" and "scored zero" are different
    claims — the agent writes a genuine 0.0 for a week an area had no goals to
    be scored against."""
    sc = _report(data, period, S.AREA, area="B2").scores
    assert not sc.measured
    assert sc.effectiveness is None


# ── Decision 13: the conversion rates ────────────────────────────────────────

def test_the_rates_are_the_ratio_of_totals(data, period):
    """1000 contacts made of 2000 attempted is 50%, on target. Not the mean of
    the areas' own rates, which `rate_metrics` documents as the wrong answer."""
    rates = {r["key"]: r for r in _report(data, period).rates}
    assert rates["contact_rate"]["value"] == pytest.approx(50)
    assert rates["contact_rate"]["pct_of_target"] == pytest.approx(100)
    assert rates["lesson_rate"]["value"] == pytest.approx(20)


def test_the_rates_stop_at_zone_level(data, period):
    """Decision 13. A close rate over one companionship's fortnight of three
    lessons is a ratio of two small integers."""
    assert len(_report(data, period, S.ZONE, zone="Norte").rates) == 4
    assert _report(data, period, S.DISTRICT, zone="Norte", district="D1").rates == ()
    assert _report(data, period, S.AREA, area="A1").rates == ()


# ── Decisions 14, 15, 16: the children ───────────────────────────────────────

def test_children_are_ranked_weakest_first_and_none_is_cut(data, period):
    """Decision 15 — every child, no top-N, weakest first.

    Sur is last on the basis that matters. One of its two areas filed, in one
    of two weeks, and did 30 — which per REPORTING area-week is 150% of goal
    and would put Sur top. Per ACTIVE area-week it is 37.5%, against Norte's
    41.7%, and that is the zone."""
    kids = _report(data, period).children
    assert [c.name for c in kids] == ["Sur", "Norte"]
    assert [c.rank for c in kids] == [1, 2]
    assert kids[0].mean_attainment == pytest.approx(37.5)


def test_a_child_with_nothing_measured_sorts_last_not_first(data, period):
    """D2 and D3 hold areas that reported; D1's A1 and A2 did too. An unmeasured
    unit is not the weakest — printing it first would put "no data" where a
    council looks for its biggest problem."""
    kids = _report(data, period, S.ZONE, zone="Sur").children
    assert [c.name for c in kids] == ["D3"]
    empty = _report(data, period, S.DISTRICT, zone="Sur", district="D3").children
    assert [c.name for c in empty] == ["B1", "B2"]
    assert empty[-1].mean_attainment is None      # B2 filed nothing


def test_each_child_names_its_own_silent_areas(data, period):
    """Decision 16, one level down: the table says who did not file."""
    sur = _report(data, period).children[0]
    assert sur.areas_silent == ("B2",)
    assert sur.coverage.area_weeks_reported == 1


def test_every_area_is_ranked_under_the_mission_and_under_a_zone(data, period):
    """§3.2's Z3 and the drawer the mission page keeps 45 areas behind. Same
    ranking rule as the children — weakest first, unmeasured last.

    Per active area-week against a goal of 20: A3 8/2 = 20%, A2 20/2 = 50%,
    A1 22/2 = 55%, B1 30/2 = 75%. B1 filed once and did the most that week, and
    it still ranks above A1, which filed twice — one area IS its own active
    count, so the two bases coincide and nothing is being flattered here.
    """
    mission = _report(data, period)
    assert [c.name for c in mission.areas_ranked] == ["A3", "A2", "A1", "B1", "B2"]
    assert mission.areas_ranked[-1].mean_attainment is None    # B2 filed nothing

    norte = _report(data, period, S.ZONE, zone="Norte")
    assert [c.name for c in norte.areas_ranked] == ["A3", "A2", "A1"]


def test_a_district_does_not_list_its_areas_twice(data, period):
    """At district level the areas ARE the children, and the same list under
    two headings is noise."""
    d = _report(data, period, S.DISTRICT, zone="Norte", district="D1")
    assert [c.name for c in d.children] == ["A2", "A1"]      # 50% then 55%
    assert d.areas_ranked == ()


def test_an_area_has_nothing_below_it(data, period):
    assert _report(data, period, S.AREA, area="A1").areas_ranked == ()


# ── Decisions 9, 26: the week-by-week strip ──────────────────────────────────

def test_every_key_indicator_carries_its_own_weeks(data, period):
    s = _report(data, period).series[NEW]
    assert [p.week for p in s.points] == [W1, W2]
    assert [p.actual for p in s.points] == [60, 20]
    assert [p.reporting for p in s.points] == [3, 2]


def test_a_week_nobody_filed_is_none_and_not_a_zero(data, period):
    s = _report(data, period, S.AREA, area="B2").series[NEW]
    assert [p.actual for p in s.points] == [None, None]


def test_the_strip_is_built_from_the_same_frame_as_the_cards(data, period):
    """The one failure this layer exists to prevent: a card reading 80 above a
    strip totalling something else."""
    m = _report(data, period)
    assert sum(p.actual for p in m.series[NEW].reported_points) == m.ki(NEW).actual


def test_a_transfer_boundary_inside_the_window_is_marked(data):
    """Decision 9. "Últimas 6 semanas" spans transfer day; "Este traslado"
    starts on it, and a dashed rule on the axis edge is noise."""
    six = P.resolve(P.LAST_6_WEEKS, TODAY, CYCLES)
    assert _report(data, six).series[NEW].boundaries == ((date(2026, 9, 7), "2026-6"),)
    assert _report(data, P.resolve(P.THIS_TRANSFER, TODAY, CYCLES)
                   ).series[NEW].boundaries == ()


# ── Strength and growth: read, never recomputed ──────────────────────────────

def test_an_area_reads_the_agents_own_choice_of_strength_and_growth(data, period):
    """§1.2 — WEEKLY_BREAKDOWNS already holds these, chosen by the Apps Script
    agents. The most recent week in the period wins, and the keys come back as
    the mission's own Spanish names."""
    m = _report(data, period, S.AREA, area="A1")
    assert m.strengths == ("Contactos", "Intentos de Contacto")
    assert m.growth == "Lecciones con Amigos"


def test_a_week_with_no_pick_reads_as_no_pick(data, period):
    m = _report(data, period, S.AREA, area="A2")
    assert m.strengths == () and m.growth is None


def test_only_an_area_has_a_strength(data, period):
    """The columns hold ONE companionship's judgement; a zone made of nine of
    them has no such row."""
    assert _report(data, period, S.ZONE, zone="Norte").strengths == ()
    assert _report(data, period).growth is None


# ── Nothing to report ────────────────────────────────────────────────────────

def test_a_mission_with_no_nightly_data_still_builds(period):
    m = _report(_data(daily_log=pd.DataFrame()), period)
    assert len(m.nightly_metrics) == 5
    assert all(r.actual is None for r in m.nightly_metrics
               if r.key != M.EFFORT_SCORE)
    assert m.rates and all(r["value"] is None for r in m.rates)


def test_a_mission_that_has_never_run_the_scoring_agent_still_builds(period):
    m = _report(_data(scores=pd.DataFrame()), period)
    assert not m.scores.measured
