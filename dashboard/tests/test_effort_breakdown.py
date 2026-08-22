"""Effort over every active area -- app/analytics/effort_breakdown.py.

The bug this module exists to prevent has a shape: a numerator counted from the
areas that filed, sitting over a denominator that also came from the areas that
filed, presented as the mission. Most of these tests are that shape -- an area
that reports nothing must move the shares and must NOT move the score.

Live figures from 2026-08-22 (window 08-15..08-21, 43 active areas) are pinned
in TestLiveShape so a refactor that quietly changes the denominator fails here
rather than on the president's screen.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.analytics.effort_breakdown import (
    ALL, DEFAULT_SCORE_TARGET, LEVELS, LEVEL_WEIGHTS, MOST, SOME,
    area_floors, build_window, normalize_level, rank_areas, score_of, score_target,
    window_bounds,
)

SYSTEM_START = date(2026, 8, 10)
TRANSFER_START = date(2026, 8, 10)
ANCHOR = date(2026, 8, 21)          # a Friday; the last night whose deadline passed
START, END = date(2026, 8, 15), date(2026, 8, 21)


def _areas(names, zone="Zona 1", district="Distrito 1", area_id="A1"):
    return pd.DataFrame([
        {"Area_Name": n, "Zone": zone, "District": district, "Area_ID": area_id}
        for n in names
    ])


def _log(rows):
    """rows: (area, 'YYYY-MM-DD', answer)."""
    return pd.DataFrame(
        [{"Date": d, "Area": a, "Zone": "Zona 1", "District": "Distrito 1",
          "effort": e} for a, d, e in rows]
    )


def _window(areas, rows, start=START, end=END,
            system_start=SYSTEM_START, transfer_start=TRANSFER_START):
    return build_window(_log(rows), areas, start=start, end=end,
                        system_start=system_start, transfer_start=transfer_start)


class TestNormalizeLevel:

    @pytest.mark.parametrize("raw,expected", [
        ("Todo", ALL),
        ("todo", ALL),
        ("  Todo  ", ALL),
        ("La mayor parte", MOST),
        ("LA MAYOR PARTE", MOST),
        ("Algo", SOME),
    ])
    def test_the_forms_own_words(self, raw, expected):
        assert normalize_level(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", None, "nan", "Nada", "3", "Sí"])
    def test_anything_else_is_not_an_answer(self, raw):
        """Unrecognised text is "did not answer", never folded into Algo."""
        assert normalize_level(raw) is None


class TestScoreOf:

    def test_weights_match_ccsm_helpers(self):
        assert LEVEL_WEIGHTS == {ALL: 3, MOST: 2, SOME: 1}

    def test_all_threes(self):
        assert score_of({ALL: 5, MOST: 0, SOME: 0}) == 3.0

    def test_mixed(self):
        # (2*3 + 2*2 + 1*1) / 5
        assert score_of({ALL: 2, MOST: 2, SOME: 1}) == pytest.approx(2.2)

    def test_nothing_answered_has_no_score(self):
        """Not zero. Zero is a score; this is the absence of one."""
        assert score_of({ALL: 0, MOST: 0, SOME: 0}) is None
        assert score_of({}) is None


class TestScoreTarget:

    def test_reads_agent_config(self):
        assert score_target({"EFFORT_SCORE_TARGET": "2.5"}) == 2.5

    @pytest.mark.parametrize("cfg", [
        {}, None, {"EFFORT_SCORE_TARGET": ""}, {"EFFORT_SCORE_TARGET": "abc"},
        {"EFFORT_SCORE_TARGET": "0"}, {"EFFORT_SCORE_TARGET": "-1"},
    ])
    def test_falls_back_to_the_agents_default(self, cfg):
        """Never to zero -- a zero target grades every score as met."""
        assert score_target(cfg) == DEFAULT_SCORE_TARGET

    def test_is_not_a_fraction(self):
        """rate_metrics.target_pct multiplies by 100; this deliberately does not."""
        assert score_target({"EFFORT_SCORE_TARGET": "2.75"}) == 2.75


class TestWindowBounds:

    def test_seven_days_ending_on_the_anchor(self):
        assert window_bounds(ANCHOR) == (date(2026, 8, 15), date(2026, 8, 21))

    def test_never_eight(self):
        """CCSM_Agent5A.gs cuts at `today - 7`, which spans eight dates."""
        start, end = window_bounds(ANCHOR)
        assert (end - start).days + 1 == 7


class TestTheDenominator:
    """The whole point: possible comes from the areas, not from the answers."""

    def test_missing_areas_are_counted(self):
        areas = _areas(["A", "B", "C"])
        # Only A answers, every night.
        rows = [("A", f"2026-08-{d}", "Todo") for d in range(15, 22)]
        w = _window(areas, rows)
        assert w.possible == 21          # 3 areas x 7 days
        assert w.answered == 7
        assert w.missing == 14
        assert w.reporting_pct == pytest.approx(7 / 21 * 100)

    def test_shares_are_of_all_area_days(self):
        areas = _areas(["A", "B"])
        rows = [("A", "2026-08-15", "Todo"), ("B", "2026-08-15", "Algo")]
        w = _window(areas, rows)
        assert w.possible == 14
        assert w.share(ALL) == pytest.approx(1 / 14 * 100)
        assert w.share(SOME) == pytest.approx(1 / 14 * 100)
        assert w.missing_share == pytest.approx(12 / 14 * 100)

    def test_shares_and_missing_share_sum_to_a_hundred(self):
        areas = _areas(["A", "B", "C"])
        rows = [("A", "2026-08-16", "Todo"), ("B", "2026-08-16", "La mayor parte"),
                ("C", "2026-08-17", "Algo")]
        w = _window(areas, rows)
        total = sum(w.share(k) for k in LEVELS) + w.missing_share
        assert total == pytest.approx(100.0)

    def test_a_silent_area_does_not_move_the_score(self):
        """A missing form is a compliance fact, not an effort of zero."""
        areas_one = _areas(["A"])
        areas_four = _areas(["A", "B", "C", "D"])
        rows = [("A", "2026-08-15", "Todo"), ("A", "2026-08-16", "La mayor parte")]
        assert _window(areas_one, rows).score == _window(areas_four, rows).score
        assert _window(areas_four, rows).score == pytest.approx(2.5)

    def test_an_area_outside_mission_org_is_ignored_entirely(self):
        """Otherwise a closed area's old rows inflate a numerator whose
        denominator no longer counts it, and a day reads over 100%."""
        areas = _areas(["A"])
        rows = [("A", "2026-08-15", "Todo"), ("Cerrada", "2026-08-15", "Todo")]
        w = _window(areas, rows)
        assert w.possible == 7
        assert w.counts[ALL] == 1
        assert w.days[0].share(ALL) == pytest.approx(100.0)

    def test_nothing_at_all(self):
        w = _window(_areas(["A", "B"]), [])
        assert w.possible == 14
        assert w.answered == 0
        assert w.missing == 14
        assert w.score is None
        assert w.reporting_pct == 0.0

    def test_no_active_areas_is_an_empty_window_not_a_crash(self):
        w = _window(pd.DataFrame(columns=["Area_Name", "Zone", "District", "Area_ID"]), [])
        assert w.possible == 0
        assert w.score is None
        assert w.share(ALL) is None
        assert w.days == []


class TestPerDay:

    def test_one_row_per_date_in_the_window_even_when_silent(self):
        """A night nobody filed is a bar of grey, not a missing bar."""
        w = _window(_areas(["A"]), [("A", "2026-08-15", "Todo")])
        assert [d.day for d in w.days] == [START + timedelta(days=i) for i in range(7)]
        assert w.days[0].answered == 1
        assert w.days[1].answered == 0
        assert w.days[1].missing == 1
        assert w.days[1].score is None

    def test_day_possible_is_the_active_area_count(self):
        w = _window(_areas(["A", "B", "C"]), [])
        assert [d.possible for d in w.days] == [3] * 7

    def test_day_shares(self):
        areas = _areas(["A", "B", "C", "D"])
        rows = [("A", "2026-08-15", "Todo"), ("B", "2026-08-15", "Todo"),
                ("C", "2026-08-15", "Algo")]
        day = _window(areas, rows).days[0]
        assert day.share(ALL) == pytest.approx(50.0)
        assert day.share(SOME) == pytest.approx(25.0)
        assert day.missing_share == pytest.approx(25.0)
        assert day.score == pytest.approx((3 + 3 + 1) / 3)


class TestPerArea:

    def test_one_row_per_active_area_including_the_silent_ones(self):
        w = _window(_areas(["A", "B"]), [("A", "2026-08-15", "Todo")])
        by_name = {a.area: a for a in w.areas}
        assert set(by_name) == {"A", "B"}
        assert by_name["B"].answered == 0
        assert by_name["B"].missing == 7
        assert by_name["B"].score is None

    def test_area_counts_and_score(self):
        rows = [("A", "2026-08-15", "Todo"), ("A", "2026-08-16", "Todo"),
                ("A", "2026-08-17", "Algo")]
        area = _window(_areas(["A"]), rows).areas[0]
        assert area.counts == {ALL: 2, MOST: 0, SOME: 1}
        assert area.answered == 3
        assert area.possible == 7
        assert area.missing == 4
        assert area.score == pytest.approx(7 / 3)

    def test_carries_zone_and_district(self):
        area = _window(_areas(["A"]), []).areas[0]
        assert (area.zone, area.district) == ("Zona 1", "Distrito 1")

    def test_a_resubmission_counts_once(self):
        """DAILY_LOG holds no duplicates today; this makes that a property of
        the function rather than a hope."""
        rows = [("A", "2026-08-15", "Todo"), ("A", "2026-08-15", "Algo")]
        w = _window(_areas(["A"]), rows)
        assert w.answered == 1


class TestFloors:
    """An area created at the last transfer is not charged for the days before
    it existed -- reusing compliance_rankings.area_floor, so the denominator
    here and the one in the compliance rankings cannot drift apart."""

    def test_a_new_area_floors_at_the_transfer(self):
        areas = pd.DataFrame([
            {"Area_Name": "Vieja", "Zone": "Z", "District": "D", "Area_ID": "A1"},
            {"Area_Name": "Nueva", "Zone": "Z", "District": "D", "Area_ID": ""},
        ])
        rows = [("Nueva", "2026-08-19", "Todo")]
        w = build_window(_log(rows), areas, start=START, end=END,
                         system_start=SYSTEM_START,
                         transfer_start=date(2026, 8, 18))
        by_name = {a.area: a for a in w.areas}
        assert by_name["Vieja"].possible == 7
        assert by_name["Nueva"].possible == 4      # 18th through 21st
        assert w.possible == 11
        assert w.days[0].possible == 1             # only Vieja existed on the 15th

    def test_the_log_overrules_a_blank_area_id(self):
        """Live data has areas with a blank ID that were submitting well before
        the transfer. Without this they report over 100%."""
        areas = pd.DataFrame([
            {"Area_Name": "Nueva", "Zone": "Z", "District": "D", "Area_ID": ""},
        ])
        rows = [("Nueva", "2026-08-11", "Todo"), ("Nueva", "2026-08-15", "Todo")]
        w = build_window(_log(rows), areas, start=START, end=END,
                         system_start=SYSTEM_START,
                         transfer_start=date(2026, 8, 18))
        assert w.areas[0].possible == 7

    def test_area_floors_is_one_entry_per_active_area(self):
        areas = pd.DataFrame([
            {"Area_Name": "Vieja", "Zone": "Z", "District": "D", "Area_ID": "A1"},
            {"Area_Name": "Nueva", "Zone": "Z", "District": "D", "Area_ID": ""},
            {"Area_Name": "", "Zone": "Z", "District": "D", "Area_ID": "A3"},
        ])
        floors = area_floors(areas, _log([("Nueva", "2026-08-19", "Todo")]),
                             system_start=SYSTEM_START,
                             transfer_start=date(2026, 8, 18))
        assert floors == {"Vieja": SYSTEM_START, "Nueva": date(2026, 8, 18)}


class TestLiveShape:
    """The mission as it stood on 2026-08-22, rebuilt from its real totals.

    Section 6 reported 146 / 83 / 13 before this module existed -- 242 answers
    over a denominator of 242. The denominator is 301.
    """

    def _mission(self):
        areas = _areas([f"Area {i}" for i in range(43)])
        # Per-day answers as DAILY_LOG holds them for 08-15..08-21.
        per_day = [
            ("2026-08-15", 18, 17, 1),
            ("2026-08-16", 17, 14, 4),
            ("2026-08-17", 13, 17, 2),
            ("2026-08-18", 25, 10, 2),
            ("2026-08-19", 27, 7, 1),
            ("2026-08-20", 24, 9, 2),
            ("2026-08-21", 19, 5, 2),
        ]
        rows = []
        for day, n_all, n_most, n_some in per_day:
            i = 0
            for n, answer in ((n_all, "Todo"), (n_most, "La mayor parte"),
                              (n_some, "Algo")):
                for _ in range(n):
                    rows.append((f"Area {i}", day, answer))
                    i += 1
        return _window(areas, rows)

    def test_the_denominator_is_every_area_every_night(self):
        assert self._mission().possible == 301

    def test_a_fifth_of_the_week_was_never_filed(self):
        w = self._mission()
        assert w.answered == 236
        assert w.missing == 65
        assert round(w.missing_share) == 22

    def test_full_effort_is_not_a_majority(self):
        """47,5% of the mission's nights, not the 60,6% of submitters that the
        old section implied."""
        w = self._mission()
        assert round(w.share(ALL), 1) == 47.5
        assert round(w.counts[ALL] / w.answered * 100, 1) == 60.6

    def test_the_score_is_over_the_answers(self):
        w = self._mission()
        assert round(w.score, 2) == 2.55
        # Scoring the silent nights as zero would say something else entirely.
        assert round(
            sum(w.counts[k] * LEVEL_WEIGHTS[k] for k in LEVELS) / w.possible, 2
        ) == 2.00


class TestRankAreas:
    """Display order. The rule exists because Yumbel answered twice, said Todo
    both times, and outranked every area that answered all seven nights."""

    def _area(self, name, n_all=0, n_most=0, n_some=0, possible=7):
        from app.analytics.effort_breakdown import AreaEffort
        return AreaEffort(area=name, zone="Z", district="D",
                          counts={ALL: n_all, MOST: n_most, SOME: n_some},
                          possible=possible)

    def test_thin_evidence_sinks_below_a_full_week(self):
        thin = self._area("Yumbel", n_all=2)            # 2 answers, score 3,00
        full = self._area("Ñielol", n_all=6, n_most=1)  # 7 answers, score 2,86
        assert [a.area for a in rank_areas([thin, full])] == ["Ñielol", "Yumbel"]

    def test_above_the_threshold_score_decides(self):
        strong = self._area("A", n_all=4)                # 4 answers, 3,00
        weaker = self._area("B", n_all=6, n_most=1)      # 7 answers, 2,86
        assert [a.area for a in rank_areas([strong, weaker])] == ["A", "B"]

    def test_equal_scores_break_on_answers(self):
        many = self._area("A", n_all=7)
        few = self._area("B", n_all=5)
        assert [a.area for a in rank_areas([many, few])] == ["A", "B"]

    def test_an_area_that_answered_nothing_sorts_last(self):
        silent = self._area("Silenciosa")
        thin = self._area("Poca", n_some=1)
        full = self._area("Completa", n_all=7)
        order = [a.area for a in rank_areas([silent, thin, full])]
        assert order == ["Completa", "Poca", "Silenciosa"]

    def test_threshold_is_injectable(self):
        thin = self._area("A", n_all=2)
        full = self._area("B", n_all=6, n_most=1)
        assert [a.area for a in rank_areas([thin, full], min_answers=2)] == ["A", "B"]
