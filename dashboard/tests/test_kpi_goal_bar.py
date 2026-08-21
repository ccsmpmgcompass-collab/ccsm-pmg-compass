"""What a KPI tile's goal bar is allowed to claim.

Audit item 2 (2026-08-21) turned goal bars on for the first time — before it,
_mission_goal() returned 0 for every metric, so this rendering path had never
actually been exercised on the Panel. Two of its behaviours were wrong the
moment real numbers reached it:

  * the caption was capped at 100%, so member_contacts at 196% of its goal
    (1,267 against 15/area x 43) displayed "100%" — indistinguishable from a
    goal met exactly, and no signal that the configured number needed
    recalibrating;
  * a tile with no reading yet was rendered through the same numeric path as
    one sitting at zero, so an indicator the mission had not yet had the chance
    to report would have shown "0% of 104".
"""

import re

import pandas as pd
import pytest

from app.components import design_system
from app.components.design_system import render_kpi_row

# The goal caption's own style signature. Asserting against the whole card is
# what made the first cut of these tests wrong: the card's CSS carries
# saturate(150%) and a zero-length bar is literally width:0%, so a bare
# `"%" not in html` catches the stylesheet rather than the claim.
_CAPTION = re.compile(r'font-size:0\.65rem;color:#4b5563;margin-top:3px;">([^<]*)<')


@pytest.fixture
def rendered(monkeypatch):
    """Capture the HTML render_kpi_row writes, without a Streamlit runtime."""
    captured: list[str] = []
    monkeypatch.setattr(
        design_system.st, "markdown",
        lambda html, **kw: captured.append(html),
    )

    def _render(metrics) -> str:
        captured.clear()
        render_kpi_row(metrics)
        return captured[0] if captured else ""

    return _render


def _captions(html: str) -> list[str]:
    """Just the goal-caption text of each card."""
    return _CAPTION.findall(html)


# ── Over-goal ─────────────────────────────────────────────────────────────────

def test_a_metric_past_its_goal_reports_the_true_percentage(rendered):
    html = rendered([{"label": "Contactos", "value": 1267, "goal": 645}])
    assert "196" in html, "capped an over-goal metric back to 100%"


def test_the_bar_width_still_stops_at_100_percent(rendered):
    """The number is uncapped; the drawing is not, or it overflows its track."""
    html = rendered([{"label": "Contactos", "value": 1267, "goal": 645}])
    assert "width:196%" not in html
    assert "width:100%;background:#22c55e" in html


def test_an_exactly_met_goal_and_a_doubled_one_do_not_look_identical(rendered):
    met = rendered([{"label": "A", "value": 645, "goal": 645}])
    over = rendered([{"label": "A", "value": 1290, "goal": 645}])
    assert met != over


# ── No reading yet ────────────────────────────────────────────────────────────

def test_a_metric_with_no_reading_yet_shows_its_goal_without_a_percentage(rendered):
    """The four Key Indicators the nightly form cannot measure. An em dash is an
    absence; 0% would be a failure the mission has not had the chance to have."""
    caption = _captions(rendered([{"label": "Amigos", "value": "—", "goal": 104}]))[0]
    assert "104" in caption
    assert "%" not in caption


def test_a_genuine_zero_still_reports_zero_percent(rendered):
    """The counterpart: a measured zero is a real result and keeps its bar."""
    caption = _captions(rendered([{"label": "Amigos", "value": 0, "goal": 104}]))[0]
    assert "0%" in caption


# ── The derived-goal explanation ──────────────────────────────────────────────

def test_goal_note_is_rendered_under_the_bar(rendered):
    """A mission bar reading "48% of 8.600" is unreadable without its
    arithmetic: 8.600 is GOAL_contacts_attempted (200) x 43 active areas."""
    html = rendered([{
        "label": "Contactos", "value": 4123, "goal": 8600,
        "goal_note": "200 por área × 43",
    }])
    assert "200 por área × 43" in html


def test_a_tile_without_a_note_gains_no_empty_element(rendered):
    html = rendered([{"label": "Contactos", "value": 4123, "goal": 8600}])
    assert "margin-top:1px" not in html


def test_a_note_is_escaped_not_injected(rendered):
    html = rendered([{
        "label": "X", "value": 1, "goal": 2, "goal_note": "<script>x</script>",
    }])
    assert "<script>" not in html


# ── Unchanged behaviour ───────────────────────────────────────────────────────

# ── Per-area comparison ───────────────────────────────────────────────────────

def test_mismatched_area_counts_are_compared_per_area(rendered):
    """The 2.040% case. Week ending 2026-08-16: 33 areas reported 204 new
    people, but its goals were written on the 08-09 form, which one area
    submitted, so the goal totalled 10. 204/10 is 2.040% and means nothing;
    6.2 per area against 10 per area is 62% and means something."""
    caption = _captions(rendered([{
        "label": "Nuevas Personas", "value": 204, "goal": 10,
        "value_basis": 33, "goal_basis": 1,
    }]))[0]
    assert "62%" in caption
    assert "2.040" not in caption and "2040" not in caption


def test_the_per_area_pair_is_printed_not_just_the_percentage(rendered):
    """The tile's own big number is a mission TOTAL, so the percentage has no
    visible arithmetic unless both per-area figures are shown."""
    caption = _captions(rendered([{
        "label": "Nuevas Personas", "value": 204, "goal": 10,
        "value_basis": 33, "goal_basis": 1,
    }]))[0]
    assert "6,2" in caption or "6.2" in caption
    assert "10" in caption


def test_equal_bases_give_the_same_answer_as_a_plain_ratio(rendered):
    """In the steady state per-area costs nothing: it only ever rescues the
    mismatched case."""
    per_area = _captions(rendered([{
        "label": "A", "value": 200, "goal": 400,
        "value_basis": 33, "goal_basis": 33,
    }]))[0]
    plain = _captions(rendered([{"label": "A", "value": 200, "goal": 400}]))[0]
    assert "50%" in per_area and "50%" in plain


def test_a_missing_basis_falls_back_to_the_plain_ratio(rendered):
    """A metric whose goal nobody set has goal_basis 0 — that must not divide
    by zero, and must not silently report a per-area figure it cannot compute."""
    caption = _captions(rendered([{
        "label": "A", "value": 204, "goal": 10,
        "value_basis": 33, "goal_basis": 0,
    }]))[0]
    assert "2.040%" in caption or "2040%" in caption


def test_per_area_never_applies_to_an_unmeasured_tile(rendered):
    caption = _captions(rendered([{
        "label": "A", "value": "—", "goal": 104,
        "value_basis": 33, "goal_basis": 33,
    }]))[0]
    assert "%" not in caption


def test_no_goal_means_no_bar(rendered):
    assert _captions(rendered([{"label": "Contactos", "value": 4123}])) == []


def test_a_zero_goal_draws_nothing(rendered):
    """The relabelled in-progress baptismal tile passes goal=0 deliberately: it
    measures calendars handed out, not friends holding a date, and must not
    inherit the other quantity's target."""
    assert _captions(rendered([{"label": "Calendarios", "value": 14, "goal": 0}])) == []
