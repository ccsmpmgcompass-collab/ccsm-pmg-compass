"""Movement on the trend — audit item C2.

The trend drew one line per area and could not answer "how is the zone doing"
at all: fifteen area lines are fifteen answers to "which area", which is a
different question. C2 adds two traces: the group's own bold total, and the
twin behind it, dimmed.

The per-area BAR this file also covered — forty-five bars, each with a ghost at
its twin value and a change chip in its label (audit C3) — was deleted at plan
step D4, along with `_bar_delta_chip` that wrote those chips. The drill-down's
"Por área" tab is the per-area view now, its rows carry the change through
`charts.change_text`, and the eight chip tests moved to `tests/test_charts.py`
with it. What stays here is `_bucketed_totals`, which is the trend's own.

The one thing worth stating twice, because it is the design and not an
implementation detail: the twin overlay is aligned by BUCKET INDEX, not by
date. Day 1 against day 1, week 1 against week 1. Plotted on its own dates the
twin would sit in its own stretch of the axis, beside the current line rather
than behind it, and the eye would have to travel to make the comparison the
chart exists to make. _bucketed_totals returns bare numbers for exactly that
reason — there are no dates to get wrong.
"""

from datetime import date

import pandas as pd
import pytest

from app.breakdowns_engine import _bucketed_totals


# ── _bucketed_totals: the twin line behind the group's own ───────────────────

def _daily(rows):
    return pd.DataFrame([{"Date": d, "Area": a, "new_people_found": v}
                         for d, a, v in rows])


def test_daily_buckets_sum_every_area_per_day():
    totals = _bucketed_totals(
        _daily([("2026-08-17", "A", 3), ("2026-08-17", "B", 4),
                ("2026-08-18", "A", 5)]),
        "new_people_found", is_weekly=False, granularity="Days")
    assert totals == [7.0, 5.0]


def test_weekly_granularity_buckets_into_sunday_ending_weeks():
    """Monday the 17th and Sunday the 23rd are one bucket — the same Mon-Sun
    week the trend chart itself uses, because a twin bucketed by a different
    rule than the line it sits behind is not a comparison."""
    totals = _bucketed_totals(
        _daily([("2026-08-17", "A", 3), ("2026-08-23", "A", 4),
                ("2026-08-24", "A", 9)]),
        "new_people_found", is_weekly=False, granularity="Weeks")
    assert totals == [7.0, 9.0]


def test_a_weekly_form_metric_buckets_on_its_own_week_end_date():
    frame = pd.DataFrame([
        {"week_end_date": "2026-08-16", "Area": "A", "ki_new_people_real": 5},
        {"week_end_date": "2026-08-16", "Area": "B", "ki_new_people_real": 6},
        {"week_end_date": "2026-08-23", "Area": "A", "ki_new_people_real": 8},
    ])
    assert _bucketed_totals(frame, "ki_new_people_real",
                            is_weekly=True, granularity="Weeks") == [11.0, 8.0]


def test_the_totals_carry_no_dates():
    """The contract that makes index-alignment possible. A list of numbers
    cannot be plotted on the twin's own dates by accident."""
    totals = _bucketed_totals(_daily([("2026-08-17", "A", 3)]),
                              "new_people_found", False, "Days")
    assert totals == [3.0]
    assert all(isinstance(v, float) for v in totals)


def test_totals_come_back_oldest_first():
    """Index alignment against the current period's buckets only means anything
    if both run in the same direction."""
    totals = _bucketed_totals(
        _daily([("2026-08-19", "A", 3), ("2026-08-17", "A", 1),
                ("2026-08-18", "A", 2)]),
        "new_people_found", False, "Days")
    assert totals == [1.0, 2.0, 3.0]


def test_an_empty_twin_yields_no_overlay():
    """The live case on the default view: This Month So Far's twin is 1-3
    August and DAILY_LOG begins on the 9th. No trace is drawn at all, rather
    than a flat line along zero implying the mission did nothing."""
    assert _bucketed_totals(pd.DataFrame(), "new_people_found", False, "Days") == []


def test_a_metric_absent_from_the_twin_yields_no_overlay():
    assert _bucketed_totals(_daily([("2026-08-17", "A", 3)]),
                            "baptismal_calendars", False, "Days") == []


def test_a_frame_with_no_date_column_degrades_instead_of_raising():
    frame = pd.DataFrame([{"Area": "A", "new_people_found": 3}])
    assert _bucketed_totals(frame, "new_people_found", False, "Days") == []


def test_non_numeric_values_do_not_poison_a_bucket():
    """DAILY_LOG carries "Todo" in effort and "TRUE" in exchanges. They coerce
    to NaN and sum away, the same as the nightly agent does with them."""
    frame = pd.DataFrame([
        {"Date": "2026-08-17", "Area": "A", "effort": "Todo"},
        {"Date": "2026-08-17", "Area": "B", "effort": 3},
    ])
    assert _bucketed_totals(frame, "effort", False, "Days") == [3.0]


# ── The totals' own y-axis ───────────────────────────────────────────────────

def test_the_totals_axis_is_a_spec_plotly_actually_accepts():
    """This exists because the first version of it was not. `titlefont` is the
    legacy spelling; plotly 6 rejects it with "Invalid property ... Did you mean
    tickfont?" and the whole trend chart rendered as a ValueError. Nothing in
    the suite touched the trend layout, so only opening the page found it —
    handing the real spec to the real plotly is the cheapest way to keep that
    from happening twice."""
    import plotly.graph_objects as go
    from app.breakdowns_engine import _totals_axis_spec

    fig = go.Figure(go.Scatter(x=["a", "b"], y=[1, 2]))
    fig.add_trace(go.Scatter(x=["a", "b"], y=[900, 950], yaxis="y2"))
    fig.update_layout(yaxis2=_totals_axis_spec("San Pedro total", 1020.0))
    assert fig.layout.yaxis2.side == "right"
    assert fig.layout.yaxis2.overlaying == "y"
    assert fig.layout.yaxis2.title.text == "San Pedro total"


def test_the_totals_axis_starts_at_zero_and_clears_the_tallest_point():
    """A total axis that did not start at zero would exaggerate every movement
    on the one line the reader is most likely to quote."""
    from app.breakdowns_engine import _totals_axis_spec
    spec = _totals_axis_spec("total", 1020.0)
    assert spec["range"][0] == 0
    assert spec["range"][1] >= 1020.0


def test_a_flat_zero_series_still_gets_a_usable_axis():
    """A group that reported nothing must not produce range [0, 0], which
    plotly draws as a degenerate axis."""
    from app.breakdowns_engine import _totals_axis_spec
    spec = _totals_axis_spec("total", 0.0)
    assert spec["range"][1] > 0
