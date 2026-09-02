"""Regression for audit finding B7 (AUDIT-IA-2026-08-22.md).

14_Referencias.py's headline and per-area table used to divide received by
asked and present it as a conversion rate/percentage. references_asked and
member_referrals_received are independent nightly counts, not a funnel — a
companionship can receive a referral from a member it never asked that night
— so that "rate" could exceed 100%, and did live (Almirante Latorre 400%,
Los Huertos 250%).

Fixture below reproduces that exact shape: an area that received more
referrals than it asked for. Before the fix this rendered as a percent over
100; after, it's a plain count difference — no percent sign, no division.
"""

from datetime import date, timedelta

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.config import metric_catalog as mc

QUESTIONS_CONFIG = pd.DataFrame([
    {"Question_ID": "Q-1", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "Referencias Solicitadas",
     "Metric_Key": "references_asked",
     "Metric_Display_Name": "Referencias Solicitadas",
     "Data_Type": "NUMBER", "Display_Order": 1, "Active": "TRUE"},
    {"Question_ID": "Q-2", "Form_Type": "NIGHTLY",
     "Form_Column_Header": "Referencias de Miembros Recibidas",
     "Metric_Key": "member_referrals_received",
     "Metric_Display_Name": "Referencias de Miembros Recibidas",
     "Data_Type": "NUMBER", "Display_Order": 2, "Active": "TRUE"},
])


def _daily_log():
    rows = []
    # Almirante Latorre's live shape: 1 asked, 4 received over the window —
    # 400% under the old Received÷Asked math. Dates relative to "today" since
    # get_daily_log's cutoff is real wall-clock time, not fixture-relative.
    today = date.today()
    for offset, asked in ((2, "1"), (1, "0")):
        rows.append({"Date": (today - timedelta(days=offset)).isoformat(),
                     "Area": "Almirante Latorre", "Zone": "Arauco",
                     "District": "Arauco",
                     "references_asked": asked,
                     "member_referrals_received": "2"})
    return pd.DataFrame(rows)


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return QUESTIONS_CONFIG.copy()
        if tab_name == "DAILY_LOG":
            return _daily_log()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    mc.clear_cache()
    yield
    mc.clear_cache()


def _run():
    at = AppTest.from_file("views/14_Referencias.py", default_timeout=60)
    at.run()
    assert not at.exception, f"Referencias raised: {at.exception}"
    return at


def _content_markdown(at) -> list[str]:
    """at.markdown minus the injected global <style> block, which is full of
    CSS percentages (opacity, saturate(), etc.) unrelated to any page content."""
    return [m.value for m in at.markdown if "<style" not in m.value]


def test_no_percent_conversion_rate_anywhere_on_the_page():
    """Scoped to captions and the By Area table's own text — not every
    markdown block, which is full of unrelated CSS percentages
    (backdrop-filter, opacity) baked into the design system's inline styles."""
    at = _run()
    by_area = [m for m in _content_markdown(at) if "pmg-tbl" in m]
    body = "\n".join(by_area) + "\n".join(c.value for c in at.caption)
    assert "%" not in body, f"a percent sign survived the B7 fix: {body!r}"


def test_by_area_table_shows_a_gap_not_a_rate():
    at = _run()
    by_area = [m for m in _content_markdown(at) if "pmg-tbl" in m]
    assert by_area, "By Area table (render_table's themed HTML) did not render"
    table_html = by_area[-1]
    assert not any(h in table_html for h in ("Tasa", ">Rate<")), (
        f"per-area table still carries a rate column: {table_html!r}"
    )
    assert "Diferencia" in table_html or "Gap" in table_html, (
        f"per-area table has no gap column: {table_html!r}"
    )


def test_headline_caption_states_counts_not_a_ratio():
    at = _run()
    captions = [c.value for c in at.caption]
    joined = "\n".join(captions)
    assert "%" not in joined
    # 1 asked, 4 received mission-wide -> a gap of 3, stated in words.
    assert any("más recibidas" in c or "more received" in c for c in captions), (
        f"expected a stated gap in the headline caption, got: {captions}"
    )
