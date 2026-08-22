"""Tests for app/analytics/finding_funnel.py.

The module had none, and it is the one the Finding Funnel page leans on
entirely. Fixtures mirror the SHAPE of the real Tableau Detail export (column
names, blank-vs-present milestone dates) and never its rows -- the real file
carries investigators' names and is stamped "Confidential."
"""

from datetime import date

import pandas as pd
import pytest

from app.analytics.finding_funnel import (
    DEFAULT_PRESET,
    FUNNEL_STAGES,
    PRESETS,
    REFERRED_STAGE,
    _STAGE_COLS,
    build_area_rankings,
    compute_funnel_stage_counts,
    data_date_bounds,
    filter_by_range,
    preset_range,
    resolve_col,
    trend_series,
)


def _detail(rows):
    """Build a Detail-shaped frame. Each row is a dict of the columns it has;
    missing milestone columns come through as blank, like the real export."""
    cols = [
        "event_date_selected",
        "latest_zone_name",
        "latest_teaching_area_name",
        "first_referral_event_date",
        "first_contact_attempt_event_date",
        "first_successful_contact_attempt_event_date",
        "first_new_person_being_taught_date",
        "first_sacrament_date",
        "first_baptism_goal_date_set",
        "confirmation_date",
    ]
    return pd.DataFrame([{c: r.get(c, "") for c in cols} for r in rows], columns=cols)


# ── 3.2a: the floor is derived, never hardcoded ───────────────────────────────

def test_bounds_come_from_the_data_not_a_hardcoded_floor():
    """The old DATA_FLOOR = 2026-05-19 hid 86% of the real export. Anything
    before that date must now be selectable."""
    df = _detail([
        {"event_date_selected": "2024-01-03"},
        {"event_date_selected": "2025-06-30"},
        {"event_date_selected": "2026-08-03"},
    ])
    lo, hi = data_date_bounds(df)
    assert lo == date(2024, 1, 3)
    assert hi == date(2026, 8, 3)


def test_module_no_longer_exports_a_hardcoded_data_floor():
    """Guards against the constant creeping back in."""
    import app.analytics.finding_funnel as ff

    assert not hasattr(ff, "DATA_FLOOR")


def test_an_explicit_floor_still_clamps_when_a_caller_asks_for_one():
    df = _detail([
        {"event_date_selected": "2024-01-03"},
        {"event_date_selected": "2026-08-03"},
    ])
    lo, hi = data_date_bounds(df, floor=date(2026, 1, 1))
    assert lo == date(2026, 1, 1)
    assert hi == date(2026, 8, 3)


def test_bounds_fall_back_to_today_when_there_is_nothing_to_measure():
    lo, hi = data_date_bounds(pd.DataFrame())
    assert lo == hi == date.today()
    lo, hi = data_date_bounds(_detail([{"event_date_selected": ""}]))
    assert lo == hi == date.today()


def test_default_preset_is_a_real_preset_and_is_not_all():
    """The page opens on this. 'All' now spans 2.6 years, which is not an
    opening view."""
    assert DEFAULT_PRESET in PRESETS
    assert PRESETS[DEFAULT_PRESET] is not None


def test_preset_range_anchors_on_the_latest_found_date_and_clamps_to_lo():
    lo, hi = date(2024, 1, 3), date(2026, 8, 3)
    assert preset_range("All", lo, hi) == (lo, hi)
    assert preset_range("Last 7 days", lo, hi) == (date(2026, 7, 28), hi)
    # A window longer than the data cannot start before the data does.
    assert preset_range("Last 30 days", date(2026, 8, 1), hi) == (date(2026, 8, 1), hi)


def test_filter_by_range_is_inclusive_at_both_ends():
    df = _detail([
        {"event_date_selected": "2026-07-31"},
        {"event_date_selected": "2026-08-01"},
        {"event_date_selected": "2026-08-03"},
        {"event_date_selected": "2026-08-04"},
    ])
    out = filter_by_range(df, date(2026, 8, 1), date(2026, 8, 3))
    assert len(out) == 2


def test_filter_by_range_with_no_bounds_keeps_blank_dated_rows():
    df = _detail([{"event_date_selected": "2026-08-01"}, {"event_date_selected": ""}])
    assert len(filter_by_range(df, None, None)) == 2


# ── 3.2b: one stage list, and it ends in the outcome ──────────────────────────

def test_the_funnel_includes_baptized():
    """The chart used to stop at 'Baptism Date Set' while the table below it
    counted confirmations -- one page showing two different funnels."""
    labels = [l for l, _ in FUNNEL_STAGES]
    assert labels[0] == "Found"
    assert labels[-1] == "Baptized"
    assert dict(FUNNEL_STAGES)["Baptized"] == "confirmation_date"


def test_referred_is_not_a_funnel_stage_but_is_still_on_the_table():
    """Referred (19,256 real) is smaller than Contact Attempted (85,821), so
    charting it would make the funnel widen halfway down."""
    assert REFERRED_STAGE[0] not in [l for l, _ in FUNNEL_STAGES]
    assert REFERRED_STAGE in _STAGE_COLS


def test_table_stages_are_derived_from_the_funnel_so_they_cannot_drift():
    funnel_cols = {c for _, c in FUNNEL_STAGES if c is not None}
    table_cols = {c for _, c in _STAGE_COLS} - {REFERRED_STAGE[1]}
    assert funnel_cols == table_cols


def test_a_skipped_milestone_still_counts_toward_the_stages_below_it():
    """The real export is not strictly nested. Over the live last-30-days,
    2,515 people carry a being-taught date and only 1,842 a successful-contact
    date, so per-column counts made the funnel bulge outward. A person taught
    without a logged contact did get contacted."""
    df = _detail([
        # taught, but the contact attempt was never logged
        {"event_date_selected": "2026-08-01",
         "first_new_person_being_taught_date": "2026-08-04"},
        # the ordinary path
        {"event_date_selected": "2026-08-01",
         "first_contact_attempt_event_date": "2026-08-02",
         "first_successful_contact_attempt_event_date": "2026-08-03",
         "first_new_person_being_taught_date": "2026-08-04"},
    ])
    counts = compute_funnel_stage_counts(df)
    assert counts["Being Taught"] == 2
    assert counts["Successfully Contacted"] == 2, "inherits the skipped step"
    assert counts["Contact Attempted"] == 2
    values = list(counts.values())
    assert values == sorted(values, reverse=True)


def test_a_baptism_pulls_the_person_through_every_stage_above_it():
    df = _detail([{"event_date_selected": "2026-08-01",
                   "confirmation_date": "2026-08-30"}])
    counts = compute_funnel_stage_counts(df)
    assert all(counts[l] == 1 for l, _ in FUNNEL_STAGES)


def test_stage_counts_are_keyed_in_english_and_narrow_monotonically():
    """Keys must be English: the page reads them back with English literals,
    and keying by the translated label made every Spanish lookup return 0."""
    df = _detail([
        # reached every stage
        {"event_date_selected": "2026-08-01",
         "first_contact_attempt_event_date": "2026-08-02",
         "first_successful_contact_attempt_event_date": "2026-08-03",
         "first_new_person_being_taught_date": "2026-08-04",
         "first_sacrament_date": "2026-08-09",
         "first_baptism_goal_date_set": "2026-08-10",
         "confirmation_date": "2026-08-30"},
        # attempted and contacted only
        {"event_date_selected": "2026-08-01",
         "first_contact_attempt_event_date": "2026-08-02",
         "first_successful_contact_attempt_event_date": "2026-08-03"},
        # found, never attempted
        {"event_date_selected": "2026-08-01"},
    ])
    counts = compute_funnel_stage_counts(df)

    assert list(counts) == [l for l, _ in FUNNEL_STAGES]
    assert counts["Found"] == 3
    assert counts["Contact Attempted"] == 2
    assert counts["Baptized"] == 1

    values = list(counts.values())
    assert values == sorted(values, reverse=True), "funnel must never widen"


def test_stage_counts_on_an_empty_frame_is_empty_not_a_row_of_zeros():
    assert compute_funnel_stage_counts(pd.DataFrame()) == {}


# ── the trend chart cannot draw 950 daily bars ────────────────────────────────

def test_trend_buckets_by_day_for_a_short_window():
    df = _detail([
        {"event_date_selected": "2026-08-01"},
        {"event_date_selected": "2026-08-01"},
        {"event_date_selected": "2026-08-03"},
    ])
    labels, values, gran = trend_series(df)
    assert gran == "day"
    assert labels == ["2026-08-01", "2026-08-03"]
    assert values == [2, 1]


def test_trend_buckets_by_month_once_the_window_is_long():
    """'All' now spans 2024-01 -> 2026-08. Per-day that is ~950 bars."""
    df = _detail([
        {"event_date_selected": "2024-01-15"},
        {"event_date_selected": "2024-01-20"},
        {"event_date_selected": "2026-08-03"},
    ])
    labels, values, gran = trend_series(df)
    assert gran == "month"
    assert labels[0] == "2024-01"
    assert values[0] == 2


def test_trend_on_an_empty_frame_returns_nothing_to_draw():
    assert trend_series(pd.DataFrame()) == ([], [], "day")


# ── rankings still line up with the reconciled stage list ─────────────────────

def test_area_rankings_carry_every_stage_column():
    df = _detail([
        {"event_date_selected": "2026-08-01", "latest_teaching_area_name": "Alemania 1",
         "first_referral_event_date": "2026-08-01",
         "first_contact_attempt_event_date": "2026-08-02",
         "first_successful_contact_attempt_event_date": "2026-08-03",
         "confirmation_date": "2026-08-30"},
        {"event_date_selected": "2026-08-01", "latest_teaching_area_name": "Alemania 1"},
    ])
    ranks = build_area_rankings(df)
    row = ranks.iloc[0]
    assert row["Area"] == "Alemania 1"
    assert row["Found"] == 2
    assert row["Referred"] == 1
    assert row["Baptized"] == 1
    assert row["Contact %"] == pytest.approx(50.0)


def test_resolve_col_prefers_the_short_column_over_tableaus_combined_mashup():
    df = pd.DataFrame(columns=[
        "latest_zone_name",
        "latest_zone_name_and_5_more_(combined)",
    ])
    assert resolve_col(df, "latest_zone") == "latest_zone_name"
