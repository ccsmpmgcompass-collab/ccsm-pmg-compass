"""Section labels: contrast, and the ①②③ numbering (audit step 1.3).

The Panel is twelve sections over ten screens and these labels are the only
wayfinding on it (AUDIT-IA-2026-08-22.md). Two things are worth pinning:

* the base tier must clear the WCAG AA 4.5:1 floor on the app background. It
  used to be #6b7280 at 0.65rem, which is 4.13:1 — legible enough to pass a
  glance, not enough to pass a standard, on the one element a reader navigates
  a long page by. The ratio is COMPUTED here rather than the hex asserted, so
  a future palette change is checked rather than merely noticed;

* numbers are handed out automatically in render order, which means they are
  correct by construction but also invisible to code review — nothing in a
  page file says "this is section ⑦". These tests are where that behaviour is
  written down.
"""

import re

import pytest
import streamlit as st

from app.components import design_system as ds

#: The app background, from _CSS's .stApp rule.
BACKGROUND = "#08080e"


def _luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance."""
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = channel(r), channel(g), channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _rendered(text: str, **kwargs) -> str:
    """The HTML one render_section_label call emits."""
    captured = []
    original = st.markdown
    st.markdown = lambda body, **kw: captured.append(body)
    try:
        ds.render_section_label(text, **kwargs)
    finally:
        st.markdown = original
    return captured[0]


@pytest.fixture(autouse=True)
def _fresh_numbering():
    ds.reset_section_numbering()
    yield


def test_the_contrast_helper_agrees_with_the_known_bad_value():
    """Guards the measurement itself: #6b7280 is the colour the audit measured
    at 4.13:1, so if this helper says otherwise the other assertions here are
    measuring nothing."""
    assert _contrast("#6b7280", BACKGROUND) == pytest.approx(4.13, abs=0.05)


def test_base_tier_label_clears_wcag_aa():
    html = _rendered("Cumplimiento")
    colors = re.findall(r"color:(#[0-9a-fA-F]{6})", html)
    label_color = colors[-1]  # the label span is the last coloured element
    ratio = _contrast(label_color, BACKGROUND)
    assert ratio >= 4.5, f"{label_color} is {ratio:.2f}:1 on {BACKGROUND}, AA needs 4.5"


def test_emphasis_tier_stays_stronger_than_the_base_tier():
    """The page relies on two visibly different levels. Raising the base tier
    is only safe while the emphasis tier still reads as louder — brighter and
    larger, not merely different."""
    base = _rendered("Base")
    emph = _rendered("Emphasised", emphasis=True)

    def size_of(html: str) -> float:
        return max(float(s) for s in re.findall(r"font-size:([0-9.]+)rem", html))

    def label_color(html: str) -> str:
        return re.findall(r"color:(#[0-9a-fA-F]{6})", html)[-1]

    assert size_of(emph) > size_of(base)
    assert _luminance(label_color(emph)) > _luminance(label_color(base))


def test_sections_are_numbered_in_render_order():
    assert "①" in _rendered("First")
    assert "②" in _rendered("Second")
    assert "③" in _rendered("Third")


def test_numbering_restarts_for_the_next_page():
    _rendered("First")
    _rendered("Second")
    ds.reset_section_numbering()
    assert "①" in _rendered("A section on the next page")


def test_a_label_keeps_its_number_when_drawn_again():
    """Desgloses draws sections inside an @st.fragment. A fragment rerun
    re-executes that body without the router, so nothing resets the counter —
    the number has to come from what the label was given the first time, or it
    would climb on every scope change."""
    _rendered("Notas")
    _rendered("Compañerismo")
    assert "①" in _rendered("Notas")
    assert "②" in _rendered("Compañerismo")


def test_unnumbered_labels_do_not_consume_a_number():
    """Goals' area-type categories are sub-headings inside one section; they
    must not push the next real section's number along."""
    assert "①" in _rendered("A real section")
    sub = _rendered("Piso", emphasis=True, numbered=False)
    assert not any(g in sub for g in "①②③④⑤")
    assert "②" in _rendered("The next real section")


def test_numbering_falls_back_to_digits_past_twenty():
    """The ㉑-㊿ block is missing from several fonts in the app's stack and
    would render as a box. No page has twenty-one sections today; this pins
    what happens the day one does."""
    for i in range(20):
        _rendered(f"Section {i}")
    html = _rendered("Section twenty-one")
    assert ">21<" in html
