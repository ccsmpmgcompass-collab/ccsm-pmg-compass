"""The KPI card after the data-pages redesign, step A1 (2026-09-18).

Audit finding X1: render_kpi_row was a NON-WRAPPING flex row, so the Panel's
seven Key Indicator cards at 375px rendered as seven columns a few characters
wide. The row is now a CSS grid that wraps; a card may carry a sparkline, a
link and a second labelled mark on its goal bar; and it prints ONE caption
line. These tests pin the contract the pages build on in Phases B–D; the
goal-bar arithmetic is untouched and stays in test_kpi_goal_bar.py /
test_kpi_pace_goal.py.
"""

import re

import pytest

from app.components import design_system
from app.components.design_system import render_kpi_row, sparkline_svg
from test_section_labels import BACKGROUND, _contrast


@pytest.fixture
def rendered(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(design_system.st, "markdown",
                        lambda html, **kw: captured.append(html))

    def _render(cards):
        captured.clear()
        render_kpi_row(cards)
        return captured[0] if captured else ""
    return _render


# ── It wraps ─────────────────────────────────────────────────────────────────

def test_the_row_is_a_grid_not_a_flex_row(rendered):
    html = rendered([{"label": "A", "value": 1}] * 7)
    assert 'class="pmg-kpi-grid"' in html
    assert "display:grid" in html
    assert "display:flex" not in html.split('class="pmg-kpi"')[0]


def test_the_stylesheet_carries_the_phone_breakpoint():
    """The inline grid is the desktop grid; the two-across phone layout is a
    media query, and a media query can only live in the stylesheet."""
    css = design_system._CSS
    assert ".pmg-kpi-grid" in css
    assert re.search(r"@media \(max-width: ?640px\)[^}]*\{[^}]*\.pmg-kpi-grid", css, re.S)
    assert "repeat(2, minmax(0, 1fr))" in css


def test_seven_cards_go_out_in_one_block(rendered):
    """Callers no longer chunk 4-up; the grid breaks the rows."""
    html = rendered([{"label": f"K{i}", "value": i} for i in range(7)])
    assert html.count('class="pmg-kpi"') == 7


# ── The sparkline ────────────────────────────────────────────────────────────

def test_a_spark_draws_an_inline_svg_with_one_polyline(rendered):
    html = rendered([{"label": "A", "value": 5, "spark": [1, 3, 2, 5]}])
    assert "<svg" in html and "<polyline" in html
    assert html.count("<polyline") == 1


def test_an_empty_or_single_point_spark_draws_nothing(rendered):
    assert "<svg" not in rendered([{"label": "A", "value": 5, "spark": []}])
    assert "<svg" not in rendered([{"label": "A", "value": 5, "spark": [4]}])
    assert "<svg" not in rendered([{"label": "A", "value": 5}])


def test_the_last_point_is_emphasised():
    svg = sparkline_svg([1, 2, 3])
    assert "<circle" in svg
    # the dot sits on the final polyline vertex
    last_xy = re.findall(r"points=\"([^\"]*)\"", svg)[0].split()[-1]
    cx, cy = last_xy.split(",")
    assert f'cx="{cx}"' in svg and f'cy="{cy}"' in svg


def test_a_flat_series_still_draws_a_line():
    svg = sparkline_svg([4, 4, 4, 4])
    assert "<polyline" in svg


def test_a_spark_with_junk_in_it_is_skipped_not_raised():
    assert sparkline_svg(["a", None]) == ""
    assert sparkline_svg(None) == ""


# ── The link ─────────────────────────────────────────────────────────────────

def test_an_href_makes_the_whole_card_an_anchor(rendered):
    html = rendered([{"label": "Nuevas personas", "value": 20,
                      "href": "?ki=ki_new_people_real"}])
    assert re.search(r'<a class="pmg-kpi pmg-kpi-link" href="\?ki=ki_new_people_real"', html)
    assert 'target="_self"' in html
    assert "<div class=\"pmg-kpi\"" not in html


def test_a_card_without_an_href_is_a_div(rendered):
    html = rendered([{"label": "A", "value": 1}])
    assert "<a " not in html


def test_an_href_is_escaped(rendered):
    html = rendered([{"label": "A", "value": 1, "href": '?ki=x" onclick="evil()'}])
    assert 'onclick="evil()' not in html


# ── The mark ─────────────────────────────────────────────────────────────────

def test_a_mark_draws_a_second_tick_at_its_share_of_the_goal(rendered):
    html = rendered([{"label": "A", "value": 20, "goal": 400, "mark": 100}])
    tick = re.search(r'class="pmg-kpi-mark" title="([^"]*)" style="[^"]*left:(\d+)%', html)
    assert tick, "no mark rendered"
    assert tick.group(2) == "25"
    assert "100" in tick.group(1)


def test_the_mark_is_clamped_to_the_track(rendered):
    html = rendered([{"label": "A", "value": 20, "goal": 100, "mark": 250}])
    assert re.search(r'class="pmg-kpi-mark"[^>]*left:100%', html)


def test_the_mark_and_the_pace_tick_are_distinct(rendered):
    html = rendered([{"label": "A", "value": 20, "goal": 400, "pace": 40,
                      "mark": 100}])
    assert "left:10%" in html          # pace tick
    assert re.search(r'class="pmg-kpi-mark"[^>]*left:25%', html)
    assert design_system._MARK_COLOR in html
    assert "rgba(244,244,248,0.85)" in html


def test_a_mark_label_names_the_tick(rendered):
    html = rendered([{"label": "A", "value": 20, "goal": 400, "mark": 100,
                      "mark_label": "Meta del cambio"}])
    assert 'title="Meta del cambio: 100"' in html


def test_no_mark_means_no_mark(rendered):
    html = rendered([{"label": "A", "value": 20, "goal": 400}])
    assert "pmg-kpi-mark" not in html


# ── One caption line ─────────────────────────────────────────────────────────

def test_a_goal_card_prints_exactly_one_caption_line(rendered):
    html = rendered([{
        "label": "A", "value": 190, "goal": 344,
        "value_basis": 38, "goal_basis": 43, "pace": 100, "goal_by": "18 oct",
        "goal_note": "8 por área × 43",
        "projection": {"value": 400, "confidence": "high"},
    }])
    assert html.count('class="pmg-kpi-cap"') == 1
    caption = re.search(r'class="pmg-kpi-cap"[^>]*>([^<]*)<', html).group(1)
    assert "8 por área" not in caption
    assert "~400" not in caption
    assert "18 oct" not in caption
    details = re.search(r'class="pmg-kpi-cap" title="([^"]*)"', html).group(1)
    for piece in ("8 por área × 43", "~400", "18 oct", "por área"):
        assert piece in details


def test_the_caption_clears_wcag_aa(rendered):
    """The old #4b5563 was 2.9:1 on the app background — a caption the reader
    was meant to check the bar against, and could not read."""
    html = rendered([{"label": "A", "value": 20, "goal": 100}])
    color = re.search(r'class="pmg-kpi-cap"[^>]*style="[^"]*color:(#[0-9a-fA-F]{6})', html).group(1)
    ratio = _contrast(color, BACKGROUND)
    assert ratio >= 4.5, f"{color} is {ratio:.2f}:1 on {BACKGROUND}"


def test_the_label_clears_wcag_aa(rendered):
    html = rendered([{"label": "A", "value": 20}])
    color = re.search(r'class="pmg-kpi-label"[^>]*style="[^"]*color:(#[0-9a-fA-F]{6})', html).group(1)
    assert _contrast(color, BACKGROUND) >= 4.5


def test_the_label_is_not_shouted(rendered):
    html = rendered([{"label": "Nuevas personas", "value": 20}])
    label = re.search(r'class="pmg-kpi-label"[^>]*>', html).group(0)
    assert "uppercase" not in label
    assert "letter-spacing" not in label
    assert "min-height:2.4em" in label


def test_a_details_string_from_the_caller_rides_with_the_rest(rendered):
    html = rendered([{"label": "A", "value": 20, "goal": 100,
                      "details": "meta del cambio 2.038"}])
    assert "meta del cambio 2.038" in re.search(
        r'class="pmg-kpi-cap" title="([^"]*)"', html).group(1)
