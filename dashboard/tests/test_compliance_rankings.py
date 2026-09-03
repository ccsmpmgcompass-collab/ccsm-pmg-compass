"""Compliance rankings -- app/analytics/compliance_rankings.py.

The reference for this feature was a set of screenshots from a sibling mission's
dashboard. The expected values in TestMatchesTheReference are read straight off
those screenshots, which is what pins the two arithmetic decisions that are easy
to get wrong and impossible to spot by eye: an area averages its two rounded
percentages rather than pooling the counts, and a zone averages its areas rather
than pooling theirs.
"""

from datetime import date

import pandas as pd
import pytest

from app.analytics.compliance_rankings import (
    AMBER_MIN, GREEN_MIN, NIGHTLY, OVERALL, PERIODS, WEEKLY,
    AreaWindow, area_floor, build_area_windows, build_zone_windows,
    clip_window, days_in, period_bounds, rank, status_of, sundays_in,
)

# 2026-08-21 is a Friday; the mission week runs Mon-Sun.
FRIDAY = date(2026, 8, 21)


def _area(days_sub, days_pos, weeks_sub, weeks_pos, name="A", zone="Z"):
    return AreaWindow(name, zone, "D", days_sub, days_pos, weeks_sub, weeks_pos)


class TestMatchesTheReference:
    """Rows read off the reference screenshots, recomputed here.

    Every one of these fails if someone "simplifies" the Overall figure to a
    pooled ratio: Ashley Valley would read 87% instead of 78%.
    """

    @pytest.mark.parametrize("days_sub,days_pos,weeks_sub,weeks_pos,expected", [
        (16, 20, 3, 3, 90),   # Duchesne Stake East
        (10, 13, 2, 2, 88),   # Roosevelt West Stake South Bilingual
        (14, 20, 3, 3, 85),   # Polynesian North
        (20, 20, 2, 3, 84),   # Fort Heber South (OM) Spanish
        (13, 20, 3, 3, 82),   # Polynesian South (P1st)
        (19, 20, 2, 3, 81),   # Kamas Stake South
        (18, 20, 2, 3, 78),   # Ashley Valley (VG) Spanish
    ])
    def test_area_overall_is_the_mean_of_two_rounded_percentages(
            self, days_sub, days_pos, weeks_sub, weeks_pos, expected):
        assert _area(days_sub, days_pos, weeks_sub, weeks_pos).overall_pct == expected

    @pytest.mark.parametrize("pct,expected", [
        (100, "green"), (90, "green"), (85, "green"),
        (84, "amber"), (78, "amber"), (70, "amber"),
        (69, "red"), (58, "red"), (0, "red"),
        (None, "none"),
    ])
    def test_colour_bands_match_the_calendars_above_them(self, pct, expected):
        assert status_of(pct) == expected

    def test_the_bands_are_the_ones_section_seven_already_prints(self):
        """The nightly and weekly calendars legend >=85 / 70-84 / <70. One number
        must not be green on a calendar and amber in the ranking below it."""
        assert (GREEN_MIN, AMBER_MIN) == (85, 70)


class TestOverallWhenOnlyHalfIsMeasurable:
    def test_no_closed_sunday_yet_means_overall_is_the_nightly_figure(self):
        """Mon-Wed contains no Sunday, so no weekly report has come due. Averaging
        in a 0% would report a failure that was never possible -- exactly the
        state CCSM is in for "This Week" every Monday morning."""
        a = _area(3, 3, 0, 0)
        assert a.weekly_pct is None
        assert a.overall_pct == 100

    def test_an_area_with_no_gradable_days_reads_nothing_not_zero(self):
        a = _area(0, 0, 0, 0)
        assert (a.nightly_pct, a.weekly_pct, a.overall_pct) == (None, None, None)

    def test_a_missed_weekly_form_still_counts_against_overall(self):
        """The other side of the rule above: a Sunday that HAS passed and was
        missed is a real 0, not an absence."""
        assert _area(11, 11, 0, 1).overall_pct == 50


class TestPeriodBounds:
    def test_this_week_runs_monday_to_today(self):
        start, end = period_bounds("This Week", FRIDAY)
        assert (start, end) == (date(2026, 8, 17), FRIDAY)
        assert start.weekday() == 0

    def test_last_week_is_the_seven_days_before_this_monday(self):
        start, end = period_bounds("Last Week", FRIDAY)
        assert (start, end) == (date(2026, 8, 10), date(2026, 8, 16))
        assert end.weekday() == 6

    def test_this_month_so_far_ends_today_not_at_month_end(self):
        assert period_bounds("This Month So Far", FRIDAY) == (date(2026, 8, 1), FRIDAY)

    def test_last_month_is_the_whole_previous_month(self):
        assert period_bounds("Last Month", FRIDAY) == (date(2026, 7, 1), date(2026, 7, 31))

    def test_all_time_is_unbounded_and_left_to_the_caller_to_floor(self):
        assert period_bounds("All Time", FRIDAY) == (None, None)

    def test_the_period_list_matches_the_breakdowns_page(self):
        """Both pages of one dashboard must mean the same seven days by "This
        Week". breakdowns_engine owns the other copy of this list.

        A SUBSET, not an equality, since 2026-09-03: Breakdowns also offers
        "Custom", which resolves from two date widgets rather than from `today`
        and so has no bounds this section could share. The part that protects
        the reader is unchanged and is the loop below — every label the two
        pages both offer must cut the same days, in the same order, from the
        same Monday. A label appearing here and NOT in Breakdowns is still a
        failure: this list is the subset, and drift in that direction means one
        of the two grew a period the other does not know about."""
        from app.breakdowns_engine import _KPI_PERIODS, _kpi_period_bounds
        assert set(PERIODS) <= set(_KPI_PERIODS)
        assert [p for p in _KPI_PERIODS if p in PERIODS] == list(PERIODS),             "shared periods must stay in the same order on both pages"
        for label in PERIODS:
            mine = period_bounds(label, FRIDAY)
            theirs = _kpi_period_bounds(label, FRIDAY)[:2]
            assert mine == theirs, label


class TestClipWindow:
    FLOOR = date(2026, 8, 10)
    ANCHOR = date(2026, 8, 20)

    def test_a_period_before_tracking_began_is_empty_not_zero(self):
        """July, for a mission that started logging on 10 August. The page shows
        "no data yet" rather than 43 areas at 0%."""
        start, end = period_bounds("Last Month", FRIDAY)
        assert clip_window(start, end, self.FLOOR, self.ANCHOR) == (None, None)

    def test_a_period_straddling_the_floor_starts_at_the_floor(self):
        """This Month So Far spans 1-21 August but only 10 August onward can be
        graded -- otherwise every area is charged for nine days that were never
        possible."""
        start, end = period_bounds("This Month So Far", FRIDAY)
        assert clip_window(start, end, self.FLOOR, self.ANCHOR) == (self.FLOOR, self.ANCHOR)

    def test_the_window_never_runs_past_the_anchor(self):
        """Today's nightly form is not late until tonight's deadline passes."""
        _, end = clip_window(date(2026, 8, 17), FRIDAY, self.FLOOR, self.ANCHOR)
        assert end == self.ANCHOR

    def test_all_time_floors_at_the_system_start(self):
        assert clip_window(None, None, self.FLOOR, self.ANCHOR) == (self.FLOOR, self.ANCHOR)


class TestSundays:
    def test_counts_one_sunday_per_weekly_report_due(self):
        assert sundays_in(date(2026, 8, 1), date(2026, 8, 21)) == [
            date(2026, 8, 2), date(2026, 8, 9), date(2026, 8, 16)]

    def test_a_part_week_with_no_sunday_has_no_weekly_grade(self):
        # Monday 17th to Wednesday 19th.
        assert sundays_in(date(2026, 8, 17), date(2026, 8, 19)) == []

    def test_a_sunday_at_either_edge_is_included(self):
        assert sundays_in(date(2026, 8, 16), date(2026, 8, 16)) == [date(2026, 8, 16)]

    def test_an_empty_window_has_none(self):
        assert sundays_in(None, None) == []
        assert days_in(None, None) == 0


class TestAreaFloor:
    SYS = date(2026, 8, 10)
    TRANSFER = date(2026, 8, 17)

    def test_an_established_area_floors_at_the_system_start(self):
        assert area_floor({"Area_ID": "A-01"}, self.SYS, self.TRANSFER, None) == self.SYS

    def test_a_blank_id_marks_a_new_area_and_floors_at_the_transfer(self):
        assert area_floor({"Area_ID": ""}, self.SYS, self.TRANSFER, None) == self.TRANSFER

    def test_the_log_overrides_the_blank_id_hint(self):
        """Live data has shown blank-Area_ID areas already submitting under the
        same name before the transfer. Trusting the flag there makes
        days_possible smaller than days_submitted and the area reports >100%."""
        earlier = date(2026, 8, 11)
        assert area_floor({"Area_ID": ""}, self.SYS, self.TRANSFER, earlier) == self.SYS


class TestBuildAreaWindows:
    AREAS = pd.DataFrame([
        {"Area_Name": "Arauco 1", "Zone": "Arauco", "District": "Arauco", "Area_ID": "A-1"},
        {"Area_Name": "Lota 2", "Zone": "Arauco", "District": "Lota", "Area_ID": "A-2"},
    ])

    def _log(self, rows):
        return pd.DataFrame([{"Date": d, "Area": a} for a, d in rows])

    def test_counts_only_days_inside_the_window(self):
        log = self._log([
            ("Arauco 1", "2026-08-10"),
            ("Arauco 1", "2026-08-11"),
            ("Arauco 1", "2026-08-25"),      # after the anchor
        ])
        rows = build_area_windows(
            self.AREAS, log, pd.DataFrame(),
            start=date(2026, 8, 10), end=date(2026, 8, 12),
            system_start=date(2026, 8, 10), transfer_start=date(2026, 8, 10),
            anchor=date(2026, 8, 12))
        arauco = next(r for r in rows if r.area == "Arauco 1")
        assert (arauco.days_submitted, arauco.days_possible) == (2, 3)

    def test_a_duplicate_row_for_one_day_counts_once(self):
        """DAILY_LOG can hold two rows for one area-day; compliance asks whether
        the form arrived, not how many times."""
        log = self._log([("Arauco 1", "2026-08-10"), ("Arauco 1", "2026-08-10")])
        rows = build_area_windows(
            self.AREAS, log, pd.DataFrame(),
            start=date(2026, 8, 10), end=date(2026, 8, 10),
            system_start=date(2026, 8, 10), transfer_start=date(2026, 8, 10),
            anchor=date(2026, 8, 10))
        assert next(r for r in rows if r.area == "Arauco 1").days_submitted == 1

    def test_an_area_that_never_submitted_is_present_with_a_zero(self):
        """A silently missing row would quietly shrink the mission."""
        rows = build_area_windows(
            self.AREAS, self._log([("Arauco 1", "2026-08-10")]), pd.DataFrame(),
            start=date(2026, 8, 10), end=date(2026, 8, 10),
            system_start=date(2026, 8, 10), transfer_start=date(2026, 8, 10),
            anchor=date(2026, 8, 10))
        lota = next(r for r in rows if r.area == "Lota 2")
        assert (lota.days_submitted, lota.days_possible, lota.nightly_pct) == (0, 1, 0)
        assert len(rows) == 2

    def test_weekly_submissions_are_matched_to_sundays_in_the_window(self):
        weekly = pd.DataFrame([{"week_end_date": "2026-08-16", "area": "Arauco 1"}])
        rows = build_area_windows(
            self.AREAS, pd.DataFrame(), weekly,
            start=date(2026, 8, 10), end=date(2026, 8, 20),
            system_start=date(2026, 8, 10), transfer_start=date(2026, 8, 10),
            anchor=date(2026, 8, 20))
        arauco = next(r for r in rows if r.area == "Arauco 1")
        lota = next(r for r in rows if r.area == "Lota 2")
        assert (arauco.weeks_submitted, arauco.weeks_possible) == (1, 1)
        assert (lota.weeks_submitted, lota.weeks_possible) == (0, 1)

    def test_area_names_are_stripped_on_both_sides(self):
        """MISSION_ORG and DAILY_LOG are written by different agents -- the same
        trap zone_comparison.py already guards against for zone names."""
        areas = pd.DataFrame([{"Area_Name": " Arauco 1 ", "Zone": "Arauco",
                               "District": "D", "Area_ID": "A-1"}])
        log = pd.DataFrame([{"Date": "2026-08-10", "Area": "Arauco 1 "}])
        rows = build_area_windows(
            areas, log, pd.DataFrame(),
            start=date(2026, 8, 10), end=date(2026, 8, 10),
            system_start=date(2026, 8, 10), transfer_start=date(2026, 8, 10),
            anchor=date(2026, 8, 10))
        assert rows[0].days_submitted == 1

    def test_no_areas_yields_no_rows(self):
        assert build_area_windows(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
            start=None, end=None, system_start=date(2026, 8, 10),
            transfer_start=date(2026, 8, 10), anchor=date(2026, 8, 20)) == []


class TestZoneRollup:
    """A zone averages its areas; it does not pool their counts.

    Pooling would rank a 13-area zone above an 8-area one on volume -- the
    mission's standing rule for every zone comparison on the dashboard.
    """

    def test_zone_percentage_is_the_mean_of_its_areas(self):
        rows = [_area(20, 20, 3, 3, "A1", "Z"),      # 100
                _area(10, 20, 0, 3, "A2", "Z")]      # (50 + 0) / 2 = 25
        zone = build_zone_windows(rows, OVERALL)[0]
        assert [r.overall_pct for r in rows] == [100, 25]
        # 62.5 rounds to 62 under Python's banker's rounding -- the same rule
        # that makes the reference's Polynesian South read 82 from 82.5.
        assert zone.pct() == 62

    def test_pooling_the_counts_would_give_a_different_and_wrong_answer(self):
        rows = [_area(20, 20, 3, 3, "A1", "Z"), _area(10, 20, 0, 3, "A2", "Z")]
        zone = build_zone_windows(rows, OVERALL)[0]
        pooled = round((zone.days_submitted + zone.weeks_submitted)
                       / (zone.days_possible + zone.weeks_possible) * 100)
        assert pooled == 72         # 33/46, against the areas' mean of 62
        assert zone.pct() != pooled

    def test_the_counts_beside_the_percentage_are_sums(self):
        rows = [_area(20, 20, 3, 3, "A1", "Z"), _area(10, 20, 0, 3, "A2", "Z")]
        zone = build_zone_windows(rows, OVERALL)[0]
        assert (zone.days_submitted, zone.days_possible) == (30, 40)
        assert (zone.weeks_submitted, zone.weeks_possible) == (3, 6)
        assert zone.areas == 2

    def test_an_unmeasurable_area_is_dropped_from_the_average_not_zeroed(self):
        rows = [_area(20, 20, 3, 3, "A1", "Z"), _area(0, 0, 0, 0, "A2", "Z")]
        zone = build_zone_windows(rows, OVERALL)[0]
        assert zone.pct() == 100

    def test_a_zone_with_nothing_measurable_reads_nothing(self):
        zone = build_zone_windows([_area(0, 0, 0, 0, "A1", "Z")], OVERALL)[0]
        assert zone.pct() is None

    def test_the_rollup_follows_the_chosen_compliance_type(self):
        rows = [_area(20, 20, 0, 3, "A1", "Z")]      # nightly 100, weekly 0
        assert build_zone_windows(rows, NIGHTLY)[0].pct() == 100
        assert build_zone_windows(rows, WEEKLY)[0].pct() == 0

    def test_areas_group_by_zone(self):
        rows = [_area(1, 1, 0, 0, "A1", "North"), _area(1, 1, 0, 0, "A2", "South")]
        zones = {z.zone for z in build_zone_windows(rows, OVERALL)}
        assert zones == {"North", "South"}


class TestRank:
    ROWS = [_area(20, 20, 3, 3, "Best"),        # 100
            _area(14, 20, 3, 3, "Middle"),      # 85
            _area(10, 20, 0, 3, "Worst"),       # 25
            _area(0, 0, 0, 0, "Unmeasured")]    # None

    def test_best_first_by_default(self):
        assert [r.area for r in rank(self.ROWS, OVERALL)][:3] == [
            "Best", "Middle", "Worst"]

    def test_worst_first_reverses_only_the_readable_rows(self):
        assert [r.area for r in rank(self.ROWS, OVERALL, worst_first=True)][:3] == [
            "Worst", "Middle", "Best"]

    def test_an_unmeasured_row_sorts_last_in_both_directions(self):
        """"Not measurable" is neither an achievement nor a failure, so it
        belongs at neither end of a leaderboard."""
        assert rank(self.ROWS, OVERALL)[-1].area == "Unmeasured"
        assert rank(self.ROWS, OVERALL, worst_first=True)[-1].area == "Unmeasured"

    def test_ties_break_on_name_so_the_order_is_stable(self):
        rows = [_area(1, 1, 0, 0, "Zulu"), _area(1, 1, 0, 0, "Alpha")]
        assert [r.area for r in rank(rows, OVERALL)] == ["Alpha", "Zulu"]

    def test_by_name_ignores_the_percentage_entirely(self):
        assert [r.area for r in rank(self.ROWS, OVERALL, by_name=True)] == [
            "Best", "Middle", "Unmeasured", "Worst"]

    def test_ranking_zones_works_the_same_way(self):
        zones = build_zone_windows(
            [_area(20, 20, 3, 3, "A1", "High"), _area(4, 20, 0, 3, "A2", "Low")],
            OVERALL)
        assert [z.zone for z in rank(zones, OVERALL)] == ["High", "Low"]
