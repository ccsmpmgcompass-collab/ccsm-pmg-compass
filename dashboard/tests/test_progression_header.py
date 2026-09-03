"""The progression header — audit items D1 and D2, built as one block.

D1 asked for four lines at the top of Desgloses that answer "where does this
scope stand" without scrolling. D2 asked for the reporting-coverage caveat to be
visible rather than hidden. They are one thing: an arrow is only as good as the
share of areas behind it, so the coverage sits directly under the arrows it
qualifies.

Baptisms lead, per Zackary 2026-09-03. The design problem that answer creates is
that a zone baptises two or three people a MONTH across 43 areas, so a
baptisms-only header reads "0 · sin cambio" most weeks. The two indicators that
precede a baptism ride underneath for exactly that reason, and several tests
below are about the zero case being useful rather than merely honest.

The other hard part is that all three indicators are collected once a week, on
Sunday — so the page's own default period ("This Month So Far", early in the
month) contains no weekly report at all. _header_window's fallback is what keeps
the block from being blank on most days of most months, and the tests hold it to
saying so out loud.
"""

from datetime import date

import pandas as pd
import pytest

from app import i18n
from app.breakdowns_engine import (
    _HEADER_METRICS, _change_chip, _header_lines, _header_window, _weeks_in,
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


# ── Which weeks the header reads ─────────────────────────────────────────────

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


def test_no_weekly_history_at_all_yields_no_header():
    rows, ends, fell_back = _header_window(_weekly([]), date(2026, 9, 1),
                                           date(2026, 9, 3))
    assert rows.empty and ends == [] and fell_back is False


def test_an_unbounded_period_reads_everything():
    """All Time passes None bounds — every week the group has ever filed."""
    weekly = _weekly(_week("2026-08-23", 2) + _week("2026-08-30", 2))
    assert len(_weeks_in(weekly, None, None)) == 4


# ── The lines themselves ─────────────────────────────────────────────────────

def test_the_three_lines_are_the_outcome_and_the_two_that_precede_it():
    assert _HEADER_METRICS == (
        "ki_baptized_confirmed_real",
        "ki_baptismal_date_real",
        "ki_friends_sacrament_real",
    )


def test_a_zone_at_zero_baptisms_still_sees_its_pipeline_moving():
    """The case that decided the header's shape. No baptisms this week and none
    last week, but friends with a baptismal date went 6 -> 18 — the fact the
    zone can act on, and the one a baptisms-only header would have hidden."""
    lines = _header_lines(
        _weekly(_week("2026-08-30", 3, baptized=0, dated=6)),
        _weekly(_week("2026-08-23", 3, baptized=0, dated=2)))
    # Lines come back in _HEADER_METRICS order — baptisms, then the two that
    # precede them. Indexing that contract rather than matching on a display
    # label, which is Spanish, sheet-sourced and none of this test's business.
    assert [k for k in _HEADER_METRICS][0] == "ki_baptized_confirmed_real"
    assert lines[0][1] == 0                       # honest about the zero
    assert lines[1][1] == 18                      # ...and the pipeline is not
    assert lines[1][2] is not None and lines[1][2]["direction"] > 0


def test_the_prior_side_is_normalized_on_REPORTING_AREAS_not_days():
    """Six areas filing 2 each is not an improvement on three areas filing 2
    each — it is the same mission with twice the paperwork in. Scaled onto the
    current basis the prior side is 12, and the change is flat."""
    cur = _weekly(_week("2026-08-30", 6, dated=2))     # 6 areas -> 12
    prior = _weekly(_week("2026-08-23", 3, dated=2))   # 3 areas -> 6
    dated = _header_lines(cur, prior)[1][2]
    assert dated is not None
    assert dated["prior_adjusted"] == pytest.approx(12.0)
    assert dated["direction"] == 0


def test_no_prior_week_means_a_value_with_no_arrow():
    """A number without a comparison is still worth printing. A number with an
    invented comparison is not."""
    cur = _weekly(_week("2026-08-30", 3, dated=6))
    lines = _header_lines(cur, pd.DataFrame())
    assert lines and all(change is None for _, _, change in lines)


def test_a_metric_missing_from_the_data_is_skipped_not_zeroed():
    """A form that never asked the question has no answer — not an answer of
    nought."""
    cur = _weekly(_week("2026-08-30", 3)).drop(columns=["ki_friends_sacrament_real"])
    assert len(_header_lines(cur, pd.DataFrame())) == 2


# ── The change chip ──────────────────────────────────────────────────────────

def test_a_rise_is_green_and_a_severe_fall_is_red():
    assert "#22c55e" in _change_chip({"direction": 1, "pct": 25.0, "show": "percent"})
    assert "#ef4444" in _change_chip({"direction": -1, "pct": -40.0, "show": "percent"})


def test_a_mild_fall_is_amber_not_red():
    """Same four tiers as the cards below. -8% is a wobble worth flagging and
    not a collapse, and spending red on it would teach the reader to ignore
    red."""
    assert "#f59e0b" in _change_chip({"direction": -1, "pct": -8.0, "show": "percent"})


def test_a_move_inside_the_neutral_band_is_grey_and_flat():
    chip = _change_chip({"direction": 0, "pct": 2.0, "show": "percent"})
    assert "#6b7280" in chip and "→" in chip


def test_a_small_count_prints_an_absolute_change_not_a_percentage():
    """Baptisms going 3 to 5 is "+2", not "+67%" — the same fact, and the only
    one of the two that admits how small the sample is."""
    chip = _change_chip({"direction": 1, "pct": 66.7, "show": "absolute",
                         "change": 2.0})
    assert "+2" in chip and "%" not in chip


def test_no_change_means_no_chip():
    assert _change_chip(None) == ""
    assert _change_chip({}) == ""


def test_a_small_district_still_gets_an_arrow():
    """period_delta's MIN_COMPARABLE_DAYS floor is 5 and counts DAYS. Applied to
    areas it would silence every district in the mission — CCSM's districts hold
    two to four areas, so none could ever clear it. The floor that belongs to
    this unit is relative, not absolute."""
    cur = _weekly(_week("2026-08-30", 3, dated=9))
    prior = _weekly(_week("2026-08-23", 3, dated=3))
    dated = _header_lines(cur, prior)[1][2]
    assert dated is not None and dated["direction"] > 0


def test_a_prior_week_with_too_few_areas_gets_no_arrow():
    """One area of eight is not last week. Scaling it up eightfold to stand for
    the zone would produce a confident arrow resting on a single
    companionship's paperwork."""
    cur = _weekly(_week("2026-08-30", 8, dated=3))
    prior = _weekly(_week("2026-08-23", 1, dated=3))
    assert all(c is None for _, _, c in _header_lines(cur, prior))


def test_exactly_half_the_areas_is_enough():
    """The boundary is inclusive — four of eight is a readable week."""
    cur = _weekly(_week("2026-08-30", 8, dated=3))
    prior = _weekly(_week("2026-08-23", 4, dated=1))
    assert any(c is not None for _, _, c in _header_lines(cur, prior))
