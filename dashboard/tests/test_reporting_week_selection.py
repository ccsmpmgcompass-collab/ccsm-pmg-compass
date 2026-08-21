"""The Panel's Key Indicator tiles must describe a COMPLETE reporting week.

The bug this pins (audit C1, 2026-08-20): the tiles took df.iloc[-1], the newest
week in the frame. Weekly totals are a sum over whoever has submitted, so from
Monday morning until the last area reports, the newest week is a partial one. On
2026-08-20 that put "14 new people" (2 of 43 areas) at tile size directly above a
chart reading 190 (31 of 43) — one page, two different "latest weeks", the
mission understated roughly 13x. Nothing on screen looked broken, which is why
it survived: a plausible number is worse than a visibly wrong one.

Synthetic weeks throughout, with `today` injected. The live sheet cannot test
this — whether the current week has any submissions yet depends on the day the
suite happens to run, so against real data these assertions would pass or fail
by calendar accident.
"""

from datetime import date

import pandas as pd
import pytest

from app.db.queries import select_reporting_week

# Sundays. 2026-08-16 and 2026-08-23 are consecutive week ends.
LAST_COMPLETE = "2026-08-16"
IN_PROGRESS = "2026-08-23"

# Thursday of the week ending 2026-08-23 — the week is running, not finished.
MIDWEEK = date(2026, 8, 20)
# Monday after it closed.
AFTER = date(2026, 8, 24)


def _frame(*weeks_and_values) -> pd.DataFrame:
    return pd.DataFrame(
        [{"week_end_date": w, "ki_new_people_real": v} for w, v in weeks_and_values]
    )


def test_the_in_progress_week_is_not_what_the_tiles_show():
    """The regression itself: 2 of 43 areas must not displace 31 of 43."""
    df = _frame((LAST_COMPLETE, 190), (IN_PROGRESS, 14))
    row, week_end, partial = select_reporting_week(df, today=MIDWEEK)
    assert week_end == date(2026, 8, 16)
    assert row["ki_new_people_real"] == 190
    assert partial is False


def test_a_week_becomes_selectable_once_it_has_actually_ended():
    """Same frame, read the following Monday: 08-23 is now a finished week."""
    df = _frame((LAST_COMPLETE, 190), (IN_PROGRESS, 14))
    _, week_end, partial = select_reporting_week(df, today=AFTER)
    assert week_end == date(2026, 8, 23)
    assert partial is False


def test_newest_complete_week_wins_not_merely_the_second_to_last_row():
    """Guard against 'drop the last row' as a shortcut fix: with two complete
    weeks plus a partial one, the answer is the newest COMPLETE week."""
    df = _frame(("2026-08-09", 100), (LAST_COMPLETE, 190), (IN_PROGRESS, 14))
    _, week_end, _ = select_reporting_week(df, today=MIDWEEK)
    assert week_end == date(2026, 8, 16)


def test_unsorted_input_is_ordered_before_choosing():
    """WEEKLY_KI arrives grouped, and a caller must not have to sort first."""
    df = _frame((IN_PROGRESS, 14), ("2026-08-09", 100), (LAST_COMPLETE, 190))
    _, week_end, _ = select_reporting_week(df, today=MIDWEEK)
    assert week_end == date(2026, 8, 16)


def test_a_mission_in_its_first_week_still_sees_its_numbers_but_flagged():
    """No complete week exists yet. Showing nothing would be a blank page on a
    mission's first Thursday; showing it unlabelled is the original bug. So it
    is shown AND reported as partial."""
    df = _frame((IN_PROGRESS, 14))
    row, week_end, partial = select_reporting_week(df, today=MIDWEEK)
    assert week_end == date(2026, 8, 23)
    assert row["ki_new_people_real"] == 14
    assert partial is True


@pytest.mark.parametrize("df", [
    pd.DataFrame(),
    pd.DataFrame({"something_else": [1]}),
    pd.DataFrame({"week_end_date": ["not a date"]}),
])
def test_nothing_to_choose_from_is_reported_as_such(df):
    assert select_reporting_week(df) == (None, None, True)


def test_unparseable_weeks_are_skipped_rather_than_selected():
    """A junk week_end_date must not become the week the page names."""
    df = _frame((LAST_COMPLETE, 190), ("", 0))
    _, week_end, _ = select_reporting_week(df, today=MIDWEEK)
    assert week_end == date(2026, 8, 16)
