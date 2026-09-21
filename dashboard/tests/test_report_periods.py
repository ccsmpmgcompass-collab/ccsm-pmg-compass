"""Every Informes period's window, its twin, and how much of it was reported.

`app/reports/periods.py`. Fixed `today` throughout and a fixed copy of CCSM's
real TRANSFER_SCHEDULE: a period computed from `date.today()` passes in
September and fails in October, and a cycle read from the live sheet would make
these tests depend on a mission nobody is testing.

The interesting cases are all about a period that is not finished and a
comparison that is not fully reported — those are the two ways this report can
quietly lie, and PLAN-2026-09-21-informes.md §1.3 makes degrading visibly a
requirement rather than a caveat.
"""

from datetime import date

import pytest

from app.reports import periods as P

# CCSM's real cycles, as `transfer_helpers.transfer_cycles()` returns them:
# `end` is the day before the next cycle starts, so a short or long cycle is
# described as it really was (the last row falls back to its own `weeks`).
CYCLES = [
    {"number": "2026-4", "start": date(2026, 6, 15), "end": date(2026, 7, 26),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-7", "start": date(2026, 10, 19), "end": date(2026, 11, 29),
     "weeks": 6, "status": "Scheduled"},
]

# Monday, two complete weeks into 2026-6. The day the plan was written, and the
# day every measured figure in §1.2 was taken.
MONDAY = date(2026, 9, 21)


def _resolve(key, today=MONDAY):
    return P.resolve(key, today, CYCLES)


# ── Week arithmetic ───────────────────────────────────────────────────────────

def test_week_end_closes_on_sunday():
    assert P.week_end(date(2026, 9, 7)) == date(2026, 9, 13)     # Monday
    assert P.week_end(date(2026, 9, 13)) == date(2026, 9, 13)    # Sunday itself


def test_the_week_in_progress_is_not_complete():
    """A week only counts once it has finished. Without this, a period's totals
    include however few areas have filed since Monday morning — the 2-of-43
    reading that put `select_reporting_week` in queries.py."""
    assert P.last_complete_week(MONDAY) == date(2026, 9, 20)


def test_today_being_sunday_does_not_close_that_sunday():
    """Sunday's own week is not due until Monday, so a period ending on a
    Sunday must not count the week it closes."""
    assert P.last_complete_week(date(2026, 9, 20)) == date(2026, 9, 13)


def test_a_window_shorter_than_a_week_holds_no_week():
    """Four days from a Monday close before their Sunday. Empty is the honest
    answer; a half week counted whole would be the alternative."""
    assert P.weeks_ending_in(date(2026, 9, 7), date(2026, 9, 10)) == ()


def test_a_week_belongs_to_the_window_its_sunday_falls_in():
    """September's first week ends Sunday 6 September and is September's, even
    though it began on 31 August. Counting it by its Monday would file five
    days that happened in September under August."""
    weeks = P.weeks_ending_in(date(2026, 9, 1), date(2026, 9, 30))
    assert weeks[0] == date(2026, 9, 6)
    assert len(weeks) == 4


# ── Every period's bounds ─────────────────────────────────────────────────────

def test_every_period_resolves_on_a_mission_with_a_full_schedule():
    assert P.available(MONDAY, CYCLES) == P.PERIOD_KEYS


def test_transfer_periods_disappear_without_a_schedule():
    """A label is simply absent when TRANSFER_SCHEDULE cannot supply it — the
    picker hides the option rather than offering an empty page."""
    assert P.available(MONDAY, []) == (
        P.LAST_WEEK, P.LAST_6_WEEKS, P.CALENDAR_MONTH, P.YEAR)


def test_last_week_is_the_last_complete_week():
    p = _resolve(P.LAST_WEEK)
    assert (p.start, p.end) == (date(2026, 9, 14), date(2026, 9, 20))
    assert p.weeks == (date(2026, 9, 20),)
    assert not p.in_progress


def test_this_transfer_runs_to_today_not_to_its_own_end():
    """An in-progress period stops today; `full_end` remembers where it will
    stop, so a goal bar reads as progress toward the transfer's goal rather
    than silently dropping to a fortnight's worth of it."""
    p = _resolve(P.THIS_TRANSFER)
    assert (p.start, p.end) == (date(2026, 9, 7), MONDAY)
    assert p.full_end == date(2026, 10, 18)
    assert p.in_progress
    assert p.weeks == (date(2026, 9, 13), date(2026, 9, 20))
    assert (p.weeks_elapsed, p.full_weeks) == (2, 6)
    assert p.progress_label == "semana 2 de 6"


def test_this_transfer_is_labelled_with_its_cycle_number():
    """Transfer_Number is a label with no enforced format — CCSM's read
    "2026-6" — and it is what a council reads on the page."""
    assert _resolve(P.THIS_TRANSFER).label == "2026-6"
    assert _resolve(P.THIS_TRANSFER).transfer == "2026-6"


def test_a_cycle_with_no_number_still_gets_a_name():
    cycles = [{"number": "", "start": date(2026, 9, 7),
               "end": date(2026, 10, 18), "weeks": 6, "status": "Actual"}]
    assert P.resolve(P.THIS_TRANSFER, MONDAY, cycles).label == "Este traslado"


def test_last_transfer_is_the_whole_completed_cycle():
    p = _resolve(P.LAST_TRANSFER)
    assert (p.start, p.end) == (date(2026, 7, 27), date(2026, 9, 6))
    assert not p.in_progress
    assert len(p.weeks) == 6


def test_the_current_transfer_is_the_latest_one_that_has_started():
    """Not the latest marked "Actual" — so 2026-7 becomes current on
    2026-10-19 by itself, without anyone flipping a Status."""
    p = P.resolve(P.THIS_TRANSFER, date(2026, 10, 20), CYCLES)
    assert p.transfer == "2026-7"
    assert P.resolve(P.LAST_TRANSFER, date(2026, 10, 20), CYCLES).transfer == "2026-6"


def test_last_six_weeks_holds_exactly_six_complete_weeks():
    p = _resolve(P.LAST_6_WEEKS)
    assert (p.start, p.end) == (date(2026, 8, 10), date(2026, 9, 20))
    assert len(p.weeks) == 6
    assert p.weeks[-1] == date(2026, 9, 20)


def test_calendar_month_runs_to_today_and_knows_its_own_end():
    p = _resolve(P.CALENDAR_MONTH)
    assert (p.start, p.end, p.full_end) == (
        date(2026, 9, 1), MONDAY, date(2026, 9, 30))
    assert p.weeks == (date(2026, 9, 6), date(2026, 9, 13), date(2026, 9, 20))
    assert p.full_weeks == 4


def test_year_runs_from_january_to_today():
    p = _resolve(P.YEAR)
    assert (p.start, p.end, p.full_end) == (
        date(2026, 1, 1), MONDAY, date(2026, 12, 31))
    assert p.label == "2026"


# ── Comparisons: the same SHAPE, never the same NAME ─────────────────────────

def test_this_transfer_compares_against_the_same_weeks_elapsed():
    """Decision 7. Two weeks into 2026-6, the twin is the FIRST TWO WEEKS of
    2026-5 — not all six. Holding a fortnight against a completed six-week
    cycle is arithmetic guaranteed to report a collapse."""
    comp = P.comparison_for(_resolve(P.THIS_TRANSFER), MONDAY, CYCLES)
    assert comp.kind == P.SAME_WEEKS_ELAPSED
    assert (comp.period.start, comp.period.end) == (
        date(2026, 7, 27), date(2026, 8, 9))
    assert comp.period.weeks == (date(2026, 8, 2), date(2026, 8, 9))
    assert comp.period.label == "2026-5 (primeras 2 semanas)"


def test_the_elapsed_pairing_tracks_the_week_count_as_the_cycle_fills():
    """Five weeks into 2026-6, the twin is 2026-5's first FIVE weeks — the
    pairing follows the elapsed count, it is not fixed when the period opens."""
    p = P.resolve(P.THIS_TRANSFER, date(2026, 10, 12), CYCLES)
    assert p.weeks_elapsed == 5
    comp = P.comparison_for(p, date(2026, 10, 12), CYCLES)
    assert comp.kind == P.SAME_WEEKS_ELAPSED
    assert (comp.period.start, comp.period.end) == (
        date(2026, 7, 27), date(2026, 8, 30))
    assert comp.period.label == "2026-5 (primeras 5 semanas)"


def test_a_cycles_final_sunday_is_not_complete_on_the_day_it_falls():
    """2026-6 ends Sunday 18 October. That week is not due until the Monday,
    so the cycle still reads five weeks on its own last day — the same guard
    that keeps a half-reported week out of every other period here."""
    p = P.resolve(P.THIS_TRANSFER, date(2026, 10, 18), CYCLES)
    assert (p.weeks_elapsed, p.full_weeks) == (5, 6)


def test_a_completed_cycle_pairs_whole_against_whole():
    """Once 2026-6 has closed and 2026-7 has opened, the comparison stops
    calling itself partial and drops the "(primeras N semanas)" suffix."""
    monday_after = date(2026, 10, 19)
    p = P.resolve(P.LAST_TRANSFER, monday_after, CYCLES)
    assert (p.transfer, p.weeks_elapsed) == ("2026-6", 6)
    comp = P.comparison_for(p, monday_after, CYCLES)
    assert comp.kind == P.PREVIOUS
    assert comp.period.label == "2026-5"
    assert (comp.period.start, comp.period.end) == (
        date(2026, 7, 27), date(2026, 9, 6))


def test_a_transfer_with_no_complete_week_has_no_comparison():
    """Transfer day plus three. There is nothing to hold against anything, and
    saying so is the `sin comparación` chip."""
    p = P.resolve(P.THIS_TRANSFER, date(2026, 9, 10), CYCLES)
    comp = P.comparison_for(p, date(2026, 9, 10), CYCLES)
    assert not comp
    assert comp.kind == P.NO_COMPARISON
    assert "semana completa" in comp.reason


def test_a_schedule_that_does_not_reach_back_says_so():
    comp = P.comparison_for(
        P.resolve(P.LAST_TRANSFER, MONDAY, CYCLES[1:]), MONDAY, CYCLES[1:])
    assert not comp
    assert "no llega tan atrás" in comp.reason


def test_last_transfer_compares_against_the_cycle_before_it():
    comp = P.comparison_for(_resolve(P.LAST_TRANSFER), MONDAY, CYCLES)
    assert comp.period.transfer == "2026-4"
    assert comp.kind == P.PREVIOUS


def test_calendar_month_compares_against_the_same_elapsed_days():
    comp = P.comparison_for(_resolve(P.CALENDAR_MONTH), MONDAY, CYCLES)
    assert comp.kind == P.SAME_DAYS_ELAPSED
    assert (comp.period.start, comp.period.end) == (
        date(2026, 8, 1), date(2026, 8, 21))


def test_a_short_previous_month_clamps_rather_than_spilling_forward():
    """31 days into March against February: the twin ends on the 28th, not on
    2 March, which would double-count days already inside the period."""
    p = P.resolve(P.CALENDAR_MONTH, date(2026, 3, 31), CYCLES)
    comp = P.comparison_for(p, date(2026, 3, 31), CYCLES)
    assert (comp.period.start, comp.period.end) == (
        date(2026, 2, 1), date(2026, 2, 28))


def test_a_comparison_reaching_before_the_records_is_still_returned():
    """2026-4 has no WEEKLY_KI at all. The window is returned anyway and the
    caller reports zero coverage — clamping it here would quietly compare two
    different spans instead."""
    comp = P.comparison_for(_resolve(P.LAST_TRANSFER), MONDAY, CYCLES)
    assert comp.period.start == date(2026, 6, 15)


def test_a_leap_day_clamps_when_the_year_shifts_back():
    p = P.resolve(P.YEAR, date(2028, 2, 29), CYCLES)
    comp = P.comparison_for(p, date(2028, 2, 29), CYCLES)
    assert comp.period.end == date(2027, 2, 28)


# ── The second pill: the weeks immediately before ────────────────────────────

def test_preceding_weeks_is_the_transfer_day_discontinuity():
    """§1.3's "comparable today": the two weeks since transfer day against the
    two before it. The other pill's window is nearly empty; this one is not."""
    comp = P.comparison_for(_resolve(P.THIS_TRANSFER), MONDAY, CYCLES,
                            against=P.COMPARE_PRECEDING)
    assert comp.kind == P.PRECEDING_WEEKS
    assert comp.period.weeks == (date(2026, 8, 30), date(2026, 9, 6))
    assert comp.period.label == "2 semanas anteriores"


def test_both_pills_are_offered_when_they_differ():
    p = _resolve(P.THIS_TRANSFER)
    assert P.available_comparisons(p, MONDAY, CYCLES) == P.COMPARE_KEYS


def test_one_pill_when_the_two_resolve_to_the_same_window():
    """"Semana pasada" against the week before it is the same window either
    way, and two pills doing the same thing are worse than one."""
    p = _resolve(P.LAST_WEEK)
    assert P.available_comparisons(p, MONDAY, CYCLES) == (P.COMPARE_PRIOR,)


def test_the_year_is_too_long_for_the_preceding_pill():
    """38 weeks ending last December is a window with no name, overlapping the
    previous year the other pill already offers."""
    p = _resolve(P.YEAR)
    assert P.available_comparisons(p, MONDAY, CYCLES) == (P.COMPARE_PRIOR,)


# ── Coverage ─────────────────────────────────────────────────────────────────

# WEEKLY_KI as it stood on 2026-09-21: areas reporting per week, including the
# single-area stray dated 2026-08-09 and the one dated 2026-09-27, a week that
# has not happened yet.
REPORTED = {
    "2026-08-09": 1, "2026-08-16": 31, "2026-08-23": 32, "2026-08-30": 30,
    "2026-09-06": 26, "2026-09-13": 36, "2026-09-20": 27, "2026-09-27": 1,
}
AREAS = 45


def _cov(key, reported=REPORTED, today=MONDAY):
    return P.week_coverage(P.resolve(key, today, CYCLES), reported, AREAS)


def test_coverage_counts_only_the_weeks_inside_the_window():
    """The 2026-09-27 row is for a week that has not finished. It cannot
    inflate this transfer's coverage, and it does not."""
    cov = _cov(P.THIS_TRANSFER)
    assert (cov.weeks_expected, cov.weeks_reported) == (2, 2)
    assert cov.area_weeks_reported == 36 + 27


def test_coverage_reads_string_week_keys_and_dates_alike():
    """WEEKLY_KI stores its week_end_date as a string; the periods here are
    real dates. Both sides work, so no caller has to remember which it holds."""
    as_dates = {date(2026, 9, 13): 36, date(2026, 9, 20): 27}
    assert (P.week_coverage(_resolve(P.THIS_TRANSFER), as_dates, AREAS)
            == _cov(P.THIS_TRANSFER))


def test_the_2026_5_partial_case_reports_five_of_six():
    """2026-5 ran six weeks; WEEKLY_KI begins part-way through it. Five of its
    six weeks carry a row — the fifth being the single-area 2026-08-09 — so the
    caption is "5 de 6 semanas" and the 44% reporting rate beside it is what
    says how thin two of those weeks really are."""
    cov = _cov(P.LAST_TRANSFER)
    assert cov.label == "5 de 6 semanas"
    assert not cov.complete
    assert cov.reporting_rate == pytest.approx(120 / 270)


def test_a_fully_reported_window_is_complete():
    assert _cov(P.LAST_6_WEEKS).complete


def test_a_window_with_nothing_in_it_is_not_usable():
    """2026-4 predates WEEKLY_KI entirely. This is the only case decision 6
    lets become the `sin comparación` chip."""
    comp = P.comparison_for(_resolve(P.LAST_TRANSFER), MONDAY, CYCLES)
    cov = P.week_coverage(comp.period, REPORTED, AREAS)
    assert not cov.usable
    assert cov.reporting_rate == 0.0


def test_a_window_resting_on_one_area_is_usable_but_thin():
    """Decision 6 shows partial comparisons rather than hiding them, so the
    first two weeks of 2026-5 are still reported — but one area of a possible
    ninety area-weeks is not a mission, and `thin` is what says so."""
    comp = P.comparison_for(_resolve(P.THIS_TRANSFER), MONDAY, CYCLES)
    cov = P.week_coverage(comp.period, REPORTED, AREAS)
    assert cov.usable and cov.thin
    assert cov.label == "1 de 2 semanas"


def test_the_weeks_since_transfer_day_are_not_thin():
    """The pill §1.3 says is honest today: 62% of possible reports against the
    other pill's 1%."""
    comp = P.comparison_for(_resolve(P.THIS_TRANSFER), MONDAY, CYCLES,
                            against=P.COMPARE_PRECEDING)
    cov = P.week_coverage(comp.period, REPORTED, AREAS)
    assert cov.complete and not cov.thin
    assert cov.reporting_rate == pytest.approx(56 / 90)


def test_coverage_is_not_the_same_question_as_elapsed_time():
    """Two weeks into a six-week transfer, both fully reported: coverage says
    "2 de 2 semanas" and progress says "semana 2 de 6". Conflating them is how
    a third of a transfer gets reported as the whole of it."""
    p = _resolve(P.THIS_TRANSFER)
    assert P.week_coverage(p, REPORTED, AREAS).label == "2 de 2 semanas"
    assert p.progress_label == "semana 2 de 6"


def test_a_one_week_period_says_semana_not_semanas():
    assert _cov(P.LAST_WEEK).label == "1 de 1 semana"


# ── Transfer boundaries on a time axis (decision 9) ──────────────────────────

def test_a_boundary_is_marked_where_a_cycle_starts_inside_the_window():
    assert P.transfer_boundaries(CYCLES, date(2026, 8, 16), date(2026, 9, 20)) \
        == ((date(2026, 9, 7), "2026-6"),)


def test_no_rule_is_drawn_on_the_axis_edge():
    """"Este traslado" begins on a transfer boundary. A dashed rule on the
    first pixel of every chart is noise, not information."""
    assert P.transfer_boundaries(CYCLES, date(2026, 9, 7), date(2026, 9, 20)) == ()


def test_a_long_axis_carries_every_boundary_it_crosses():
    marks = P.transfer_boundaries(CYCLES, date(2026, 6, 1), date(2026, 11, 30))
    assert [n for _, n in marks] == ["2026-4", "2026-5", "2026-6", "2026-7"]
