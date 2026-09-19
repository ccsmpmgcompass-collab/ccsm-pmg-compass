"""The Desgloses Key Indicator scoreboard — which weeks it reads, and the line
that says so.

Was test_progression_header.py. The progression header it covered — three lines
at the top of Desgloses, baptisms first, with the reporting coverage under them
— is retired at plan step D1: it sat directly above a row of seven Key
Indicator cards that already carried all three of its metrics, and the
scoreboard now carries its window and its coverage as the heading's right-hand
line (PLAN-2026-09-18-data-pages.md §5).

Two things survived the move and are what this file holds:

  _header_window   which weeks a period actually describes. The seven are
                   collected once a week, on Sunday, so a period can be
                   perfectly valid and contain no weekly report at all — "This
                   Week" before Sunday and "This Month So Far" on the 3rd are
                   two of this page's most common views. The fallback is what
                   keeps the top of the page from being blank on most days of
                   most months, and the tests below hold it to saying so out
                   loud rather than substituting quietly.

  _scoreboard_window_line  the sentence that states it: which weeks, how much
                   of the scope filed, and whether it fell back.
"""

from datetime import date

import pandas as pd
import pytest

from app import i18n
from app.breakdowns_engine import (
    _header_window, _metas_for_weeks, _scoreboard_window_line, _weeks_in,
)


@pytest.fixture
def english(monkeypatch):
    monkeypatch.setattr(i18n, "get_lang", lambda: "en")


def _weekly(rows):
    """rows = [(week_end_date, area, baptized, baptismal_date, sacrament)]"""
    return pd.DataFrame([
        {"week_end_date": w, "area": a, "zone": "San Pedro",
         "ki_baptized_confirmed_real": b,
         "ki_baptismal_date_real": d,
         "ki_friends_sacrament_real": s}
        for w, a, b, d, s in rows
    ])


def _week(week_end, n_areas, baptized=0, dated=2, sacrament=1):
    return [(week_end, f"Area {i}", baptized, dated, sacrament)
            for i in range(n_areas)]


# ── Which weeks the scoreboard reads ─────────────────────────────────────────

def test_it_reads_the_weeks_inside_the_selected_period():
    """"Last Week" is 24-30 August, and the report for it lands on the 30th."""
    weekly = _weekly(_week("2026-08-23", 3) + _week("2026-08-30", 3))
    rows, ends, fell_back = _header_window(weekly, date(2026, 8, 24), date(2026, 8, 30))
    assert ends == ["2026-08-30"]
    assert fell_back is False
    assert len(rows) == 3


def test_a_multi_week_period_reads_all_of_its_weeks():
    weekly = _weekly(_week("2026-08-16", 2) + _week("2026-08-23", 2)
                     + _week("2026-08-30", 2))
    rows, ends, _ = _header_window(weekly, date(2026, 8, 1), date(2026, 8, 31))
    assert ends == ["2026-08-16", "2026-08-23", "2026-08-30"]
    assert len(rows) == 6


def test_a_period_with_no_weekly_report_falls_back_to_the_latest_one():
    """The page's DEFAULT view. On 3 September "This Month So Far" is 1-3
    September and the month's first Sunday has not come, so there is no weekly
    report inside the period at all. Rendering nothing would blank the most
    prominent block on the page for the first week of every month."""
    weekly = _weekly(_week("2026-08-23", 3) + _week("2026-08-30", 3))
    rows, ends, fell_back = _header_window(weekly, date(2026, 9, 1), date(2026, 9, 3))
    assert fell_back is True
    assert ends == ["2026-08-30"]


def test_the_fallback_never_reaches_forward_past_the_period():
    """A report filed for a week ending AFTER the period would describe days the
    reader did not ask about — and, for a past period, days that had not
    happened when the question was asked."""
    weekly = _weekly(_week("2026-08-16", 3) + _week("2026-09-06", 3))
    rows, ends, fell_back = _header_window(weekly, date(2026, 8, 20), date(2026, 8, 25))
    assert ends == ["2026-08-16"] and fell_back is True


def test_no_weekly_history_at_all_yields_no_window():
    rows, ends, fell_back = _header_window(_weekly([]), date(2026, 9, 1),
                                           date(2026, 9, 3))
    assert rows.empty and ends == [] and fell_back is False


def test_an_unbounded_period_reads_everything():
    """All Time passes None bounds — every week the group has ever filed."""
    weekly = _weekly(_week("2026-08-23", 2) + _week("2026-08-30", 2))
    assert len(_weeks_in(weekly, None, None)) == 4


# ── The line that states the window ──────────────────────────────────────────

def test_one_week_names_the_week_and_the_coverage(english):
    """The two facts the retired header carried as a title and a footer: which
    week these numbers are, and how much of the scope is behind them."""
    line = _scoreboard_window_line(["2026-08-30"], 3, 8, False, "Last Week")
    assert "week ending" in line
    assert "3 of 8 areas filed a weekly report" in line
    assert "38%" in line


def test_several_weeks_are_counted_not_listed(english):
    """A month is four Sundays; naming all of them would be a paragraph."""
    line = _scoreboard_window_line(
        ["2026-08-09", "2026-08-16", "2026-08-23", "2026-08-30"], 40, 45,
        False, "Last Month")
    assert "4 weeks to" in line
    assert "40 of 45" in line


def test_a_fallback_says_which_period_came_up_empty(english):
    """The substitution is only honest if the reader can see it happened. The
    cards describe the week named at the left of the line; this clause says the
    period they asked for holds no weekly report at all."""
    line = _scoreboard_window_line(["2026-08-30"], 3, 8, True, "This Week")
    assert "this week holds no weekly report yet" in line.lower()


def test_no_fallback_means_no_such_clause(english):
    line = _scoreboard_window_line(["2026-08-30"], 3, 8, False, "This Week")
    assert "holds no weekly report yet" not in line


def test_no_weeks_means_no_line(english):
    """Nothing to read, so nothing to say about what was read — the section
    itself does not render in this state."""
    assert _scoreboard_window_line([], 0, 8, False, "This Week") == ""


def test_an_empty_roster_drops_the_coverage_rather_than_dividing_by_zero(english):
    """MISSION_ORG can come back empty — the page guards that separately, and
    this line must not be the thing that raises."""
    line = _scoreboard_window_line(["2026-08-30"], 0, 0, False, "This Week")
    assert "week ending" in line
    assert "areas filed" not in line


# ── The bar: what the companionships set themselves (decision 6) ─────────────
# The goal bar on these seven cards stopped being leadership's transfer goal at
# step D1 and became the companionships' own ki_*_meta, because that is the
# number the Church's own app shows them and the two must agree. Which rows
# carry it is the whole arithmetic.

NEW, NEW_META = "ki_new_people_real", "ki_new_people_meta"
BAP_META = "ki_baptized_confirmed_meta"


def _forms(rows):
    """rows = [(week_end_date, area, meta_new_people, meta_baptized)]"""
    return pd.DataFrame([
        {"week_end_date": w, "area": a, NEW: 0, NEW_META: m, BAP_META: b}
        for w, a, m, b in rows
    ])


def test_a_weeks_meta_is_read_off_the_previous_weeks_form():
    """The form asks for "las metas ... para la SEMANA SIGUIENTE", so the goals
    FOR the week ending the 13th were written on the form of the 6th. Reading
    them off the same row grades a week against the target set for the week
    after it."""
    weekly = _forms([("2026-09-06", "Huequen", 5, 1),
                     ("2026-09-13", "Huequen", 9, 2)])
    totals, _ = _metas_for_weeks(weekly, ["2026-09-13"], [NEW])
    assert totals[NEW] == 5


def test_the_weeks_come_from_the_caller_so_a_fallback_week_keeps_its_goals():
    """The scoreboard falls back to the latest complete week when the selected
    period holds no weekly report. Derived from the period's own dates instead,
    that week would have been graded against nothing."""
    weekly = _forms([("2026-09-06", "Huequen", 5, 1)])
    # "This Week" is 14-19 September and holds no form at all; the week shown
    # is the 13th, and its goals are on the 6th.
    totals, _ = _metas_for_weeks(weekly, ["2026-09-13"], [NEW])
    assert totals[NEW] == 5


def test_the_basis_counts_areas_not_rows():
    """A multi-week window holds one row per area per week. Counting rows
    reported "78 areas set a goal" on a mission of 43 and handed that 78 to the
    card as the goal's basis, which then divided the two sides of the
    percentage by different numbers (audit F8, in reverse)."""
    weekly = _forms([("2026-08-30", "Huequen", 4, 0), ("2026-08-30", "Angol 1", 6, 0),
                     ("2026-09-06", "Huequen", 5, 0), ("2026-09-06", "Angol 1", 5, 0)])
    totals, basis = _metas_for_weeks(weekly, ["2026-09-06", "2026-09-13"], [NEW])
    assert totals[NEW] == 20        # all four rows' metas
    assert basis[NEW] == 2          # two areas, not four rows


def test_an_area_that_left_the_goal_blank_is_not_counted_as_having_set_one():
    """A blank meta is a commitment to nothing, not a commitment to zero — and
    counting it would make a goal one area signed up to look like a goal three
    areas did."""
    weekly = _forms([("2026-09-06", "Huequen", 7, 0),
                     ("2026-09-06", "Angol 1", 0, 0),
                     ("2026-09-06", "Lautaro 1", None, 0)])
    totals, basis = _metas_for_weeks(weekly, ["2026-09-13"], [NEW])
    assert totals[NEW] == 7 and basis[NEW] == 1


def test_a_metric_nobody_set_a_meta_for_is_absent_rather_than_zero():
    """§1.1: no meta written means no bar and "sin meta" — never a zero goal,
    which would draw a full bar for any result at all."""
    weekly = _forms([("2026-09-06", "Huequen", 5, 0)])
    totals, basis = _metas_for_weeks(weekly, ["2026-09-13"],
                                     [NEW, "ki_baptized_confirmed_real"])
    assert "ki_baptized_confirmed_real" not in totals
    assert "ki_baptized_confirmed_real" not in basis


def test_no_weeks_and_no_frame_are_both_empty_not_an_error():
    assert _metas_for_weeks(_forms([]), ["2026-09-13"], [NEW]) == ({}, {})
    assert _metas_for_weeks(_forms([("2026-09-06", "Huequen", 5, 0)]),
                            [], [NEW]) == ({}, {})
