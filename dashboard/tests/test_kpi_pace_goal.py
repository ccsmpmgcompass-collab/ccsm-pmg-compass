"""The pace goal — a running period judged against where it should be today.

Audit finding F2: on the Desgloses page's DEFAULT view ("This Month So Far",
whole mission) every goal bar was graded on value/full-month-goal. Two days into
a thirty-day month a zone exactly on pace has produced 7% of the month's target,
so the bar painted it red and told the mission it was failing at the precise
moment it was on track. Every zone was red for the first fortnight of every
month, which is the same as no colour at all.

The fix separates two questions the bar was answering with one number:

  * how far through the goal are we      -> the bar's FILL, still value/goal
  * are we where we should be by now     -> the bar's COLOUR, now value/pace

with a tick on the track at pace/goal so the reader can see the difference
rather than take the colour on trust.

goal_bar_state() is pure, so these are arithmetic tests, not HTML ones. The two
rendering tests at the bottom check that the tick and the caption actually reach
the page.
"""

import re

import pytest

from app.components import design_system
from app.components.design_system import (
    goal_bar_color, goal_bar_state, render_kpi_row,
)

_CAPTION = re.compile(r'font-size:0\.65rem;color:#4b5563;margin-top:3px;">([^<]*)<')


@pytest.fixture
def rendered(monkeypatch):
    """Capture the HTML render_kpi_row writes, without a Streamlit runtime."""
    captured: list[str] = []
    monkeypatch.setattr(design_system.st, "markdown",
                        lambda html, **kw: captured.append(html))

    def _render(cards):
        captured.clear()
        render_kpi_row(cards)
        return captured[0] if captured else ""
    return _render


# ── The F2 case, stated as arithmetic ────────────────────────────────────────

def test_a_zone_exactly_on_pace_two_days_into_a_month_is_green():
    """The audit's own example. A 300-a-month goal, two days in, 20 produced —
    exactly the pace of 20. Graded on the full goal that is 7% and red; graded
    on the pace it is 100% and green."""
    state = goal_bar_state(20, 300, pace=20)
    assert state["grade_pct"] == 100
    assert goal_bar_color(state["grade_pct"]) == "#22c55e"


def test_the_same_zone_without_a_pace_reads_red():
    """The behaviour being replaced, pinned so the difference is visible and a
    later refactor cannot quietly restore it."""
    state = goal_bar_state(20, 300)
    assert state["grade_pct"] == 7
    assert goal_bar_color(state["grade_pct"]) == "#ef4444"


def test_a_zone_genuinely_behind_pace_is_still_red():
    """The point is not to make everything green. Half of pace is half of pace,
    and must still say so."""
    state = goal_bar_state(8, 300, pace=20)
    assert state["grade_pct"] == 40
    assert goal_bar_color(state["grade_pct"]) == "#ef4444"


# ── Fill and tick are about the full goal; only the colour moves ─────────────

def test_the_bar_still_fills_toward_the_full_goal():
    """The fill is not regraded. A zone two days into the month HAS produced
    7% of what the month is for, and a bar drawn at 100% would tell it the
    month was finished."""
    assert goal_bar_state(20, 300, pace=20)["width"] == 7


def test_the_tick_sits_at_the_pace_share_of_the_goal():
    """20 of 300 is 7% along the track, so that is where "where you should be
    today" is drawn — beside a fill of the same 7%, which is what makes "on
    pace" legible at a glance."""
    assert goal_bar_state(20, 300, pace=20)["tick"] == 7


def test_the_tick_is_clamped_to_the_track():
    """A pace above the goal (a period that has over-run its own length) marks
    the end of the track rather than overflowing the card."""
    assert goal_bar_state(400, 300, pace=350)["tick"] == 100


def test_no_pace_means_no_tick():
    assert goal_bar_state(20, 300)["tick"] is None
    assert goal_bar_state(20, 300, pace=0)["tick"] is None
    assert goal_bar_state(20, 300, pace=None)["tick"] is None


# ── What the caption is never allowed to hide ────────────────────────────────

def test_the_percentage_caption_is_never_capped_at_100():
    """Pinned from the 2026-08-21 audit: member_contacts sat at 196% of its
    configured goal and the caption read "100%", so nothing on screen suggested
    the number needed recalibrating."""
    assert goal_bar_state(196, 100)["pct"] == 196


def test_a_value_that_is_not_a_number_is_unmeasured_not_zero():
    """A metric whose weekly form has not landed is not a metric sitting at
    zero. "0% of 104" reports a failure the mission has not had the chance to
    have."""
    state = goal_bar_state("—", 104, pace=20)
    assert state["measured"] is False
    assert state["width"] == 0
    assert state["tick"] is None


def test_a_zero_goal_degrades_instead_of_raising():
    state = goal_bar_state(20, 0, pace=5)
    assert state["measured"] is False and state["width"] == 0


# ── Mismatched bases still cancel, with or without a pace ────────────────────

def test_per_area_rates_still_cancel_a_mismatched_basis():
    """The 2026-08-21 case: 204 new people from 33 areas over one area's goal
    of 10 read 2.040%. Reduced to rates it is 6,2 against 10 — 62%."""
    state = goal_bar_state(204, 10, value_basis=33, goal_basis=1)
    assert state["pct"] == 62
    assert state["per_area"] is True


def test_the_pace_is_graded_on_the_same_per_area_footing():
    """A pace compared against a mission total while the goal is compared per
    area would grade the two sides in different units — the exact bug the
    per-area reduction exists to prevent, reintroduced one line down."""
    state = goal_bar_state(204, 10, pace=5, value_basis=33, goal_basis=1)
    assert state["grade_pct"] == 124   # (204/33) / (5/1) = 1,236…


# ── It reaches the page ──────────────────────────────────────────────────────

def test_a_paced_card_draws_a_tick_on_the_track(rendered):
    html = rendered([{"label": "Nuevas personas", "value": 20, "goal": 300,
                      "pace": 20}])
    assert "left:7%" in html


def test_an_unpaced_card_draws_no_tick(rendered):
    html = rendered([{"label": "Nuevas personas", "value": 20, "goal": 300}])
    assert "left:" not in html


def test_a_paced_caption_states_the_pace_and_keeps_the_full_goal(rendered):
    """Both halves matter. Without the pace the caption grades against a goal
    nobody could have met yet; without the full goal the card stops saying what
    the period is ultimately for."""
    html = rendered([{"label": "Nuevas personas", "value": 20, "goal": 300,
                      "pace": 20, "goal_by": "30 sep"}])
    caption = _CAPTION.search(html).group(1)
    assert "20" in caption and "300" in caption and "30 sep" in caption


def test_a_paced_caption_survives_a_missing_due_date(rendered):
    """goal_by is optional — a period whose end the engine cannot name still
    gets the pace half of the sentence rather than an empty "by"."""
    html = rendered([{"label": "Nuevas personas", "value": 20, "goal": 300,
                      "pace": 20}])
    caption = _CAPTION.search(html).group(1)
    assert "20" in caption and "300" in caption
    assert caption.rstrip().endswith("300")


# ── Two bars must mean two things ────────────────────────────────────────────

def test_a_card_can_carry_a_goal_bar_and_an_expectation_bar(rendered):
    """They are different references and are deliberately styled apart — graded
    green/indigo/amber/red for the goal, fixed violet for the expectation."""
    html = rendered([{"label": "Nuevas personas", "value": 20, "goal": 300,
                      "expectation": 250}])
    assert "#8b5cf6" in html          # the expectation bar's violet
    assert "expectation" in html or "expectativa" in html


# ── Audit F8: a total from 38 areas over a goal set for 43 ───────────────────

def test_a_group_goal_reports_how_many_areas_it_covers():
    """_resolve_group_goal's third value. render_kpi_row needs it beside the
    value's own basis or the two totals get divided directly."""
    from app.breakdowns_engine import _resolve_group_goal
    goal, note, basis = _resolve_group_goal(
        "new_people_found", {}, {"new_people_found": 8}, 43)
    assert goal == 8 * 43
    assert basis == 43
    assert "43" in note          # the arithmetic is shown, not just the product


def test_an_entered_goal_needs_no_explanatory_note():
    from app.breakdowns_engine import _resolve_group_goal
    goal, note, basis = _resolve_group_goal(
        "new_people_found", {"new_people_found": 300}, {"new_people_found": 8}, 43)
    assert goal == 300 and note == ""


def test_a_metric_with_no_goal_anywhere_yields_no_bar():
    from app.breakdowns_engine import _resolve_group_goal
    assert _resolve_group_goal("exchanges", {}, {}, 43) == (0.0, "", 0)


def test_mismatched_bases_are_reduced_before_being_divided(rendered):
    """38 areas reporting 190 against a goal of 8 per area for 43 areas (344).
    Divided directly that is 55%; per area it is 5,0 against 8,0 — 62%. The
    second is the one that describes the mission. (62 and not 63: round()
    breaks a .5 to even, which is a rounding convention, not an error.)"""
    html = rendered([{"label": "Nuevas personas", "value": 190, "goal": 344,
                      "value_basis": 38, "goal_basis": 43}])
    caption = _CAPTION.search(html).group(1)
    assert "62" in caption
    assert "per area" in caption or "por área" in caption
