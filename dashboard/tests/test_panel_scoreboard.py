"""The Panel's Key Indicator scoreboard — data-pages plan §4, step C1.

Three things changed that a rendered page is the only honest place to check:

* the seven Key Indicators LEAD the page, as ONE row with the period as a
  toggle. They were sections ③ and ④ of thirteen, and they were two rows of the
  same seven metrics — fourteen cards for seven numbers (audit P1, P2);
* **decision 6**: the goal bar is the companionships' own ``ki_*_meta`` and the
  leadership transfer goal is a labelled MARK on the same bar. It was the other
  way round, which meant the card and the drill-down directly beneath it drew
  two different goals for one metric;
* a Key Indicator the weekly form has not delivered yet says when it arrives
  instead of showing a zero.

The shared fixtures in test_renders_ccsm_with_data.py carry no WEEKLY_FORM_RAW,
so the weekly form — metas, per-week actuals, the cambio series — is empty
there and none of the above can be seen. This file patches
``get_weekly_form_data`` with a tidy frame instead of building the wide
one-section-per-zone raw sheet, and dates it relative to today so the week in
progress and the cambio both have real weeks in them.
"""

import re
from datetime import date, timedelta

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.config import metric_catalog as mc
from app.utils.area_helpers import mission_today
from tests.test_renders_ccsm_with_data import (
    MISSION_ORG, SCORE_CONFIG, _KI_BASES, _dashboard_summary, _questions_config,
)

AREAS = ["Arauco 1", "Lota 2"]

#: Per area per week, for whichever Key Indicator the assertions follow.
REAL_PER_AREA = 10
META_PER_AREA = 8
#: Leadership's transfer goal per area, over a six-week cycle: 42 / 6 = 7 a
#: week, 14 across the two areas. Deliberately BELOW the summed meta (16) so
#: the mark and the bar cannot be confused for one another by a passing test.
LEAD_PER_AREA = 42
CYCLE_WEEKS = 6

METRIC = "ki_new_people_real"
META_COL = "ki_new_people_meta"


def _mondays() -> tuple:
    """(this Monday, the cycle's start Monday) in the mission's own timezone."""
    today = mission_today()
    monday = today - timedelta(days=today.weekday())
    return monday, monday - timedelta(days=7)


def _weekly_form_frame() -> pd.DataFrame:
    """Five complete weeks before the current one, both areas, every week.

    A week's meta is written on the PREVIOUS week's row, so the five rows give
    the newest complete week a meta as well as a result.
    """
    monday, _ = _mondays()
    this_sunday = monday + timedelta(days=6)
    rows = []
    for back in range(5, 0, -1):
        week_end = this_sunday - timedelta(days=7 * back)
        for area in AREAS:
            row = {"week_end_date": week_end.isoformat(), "area": area,
                   "zone": "Arauco"}
            for base, _label in _KI_BASES:
                row[base + "_real"] = REAL_PER_AREA
                row[base + "_meta"] = META_PER_AREA
            rows.append(row)
    return pd.DataFrame(rows)


def _transfer_schedule() -> pd.DataFrame:
    _, cycle_start = _mondays()
    return pd.DataFrame([{"Transfer_Number": "2026-6",
                          "Start_Date": cycle_start.isoformat(),
                          "Weeks": str(CYCLE_WEEKS), "Status": "Activo"}])


def _area_transfer_goals() -> pd.DataFrame:
    _, cycle_start = _mondays()
    rows = []
    for area in AREAS:
        row = {"area": area, "transfer_start": cycle_start.isoformat(),
               "transfer_number": "2026-6", "set_by": "test", "notes": ""}
        for base, _label in _KI_BASES:
            row[base + "_real"] = LEAD_PER_AREA
        rows.append(row)
    return pd.DataFrame(rows)


def _baptisms() -> pd.DataFrame:
    """TABLEAU_BAPTISMS through July of the current year, mission rows only."""
    year = mission_today().year
    return pd.DataFrame(
        [{"month": f"{year}-{m:02d}", "zone": "MISSION", "baptisms": "30"}
         for m in range(1, 8)]
        + [{"month": f"{year - 1}-{m:02d}", "zone": "MISSION", "baptisms": "25"}
           for m in range(1, 13)]
    )


AGENT_CONFIG = pd.DataFrame([
    {"Key": "MISSION_NAME", "Value": "Chile Concepción South Mission"},
    {"Key": "MISSION_LANGUAGE", "Value": "ES"},
    {"Key": "MISSION_LOCALE", "Value": "es_CL"},
    {"Key": "MISSION_TIMEZONE", "Value": "America/Santiago"},
    {"Key": "GOAL_ANNUAL_baptisms", "Value": "527"},
])

_TABS: dict = {}


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    _TABS.clear()
    _TABS.update({
        "QUESTIONS_CONFIG": _questions_config(),
        "SCORE_CONFIG": SCORE_CONFIG,
        "MISSION_ORG": MISSION_ORG,
        "DASHBOARD_SUMMARY": _dashboard_summary(),
        "TRANSFER_SCHEDULE": _transfer_schedule(),
        "AREA_TRANSFER_GOALS": _area_transfer_goals(),
        "TABLEAU_BAPTISMS": _baptisms(),
        "AGENT_CONFIG": AGENT_CONFIG,
    })

    def fake(tab_name, header_marker=None):
        return _TABS.get(tab_name, pd.DataFrame()).copy()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    # The weekly form is a wide sheet with one section per zone; the app's own
    # parser turns it into exactly this frame, and every reader of the weekly
    # metrics goes through that one function.
    frame = _weekly_form_frame()
    monkeypatch.setattr("app.db.queries.get_weekly_form_data", lambda: frame.copy())

    import streamlit as st
    st.cache_data.clear()
    mc.clear_cache()
    yield
    st.cache_data.clear()
    mc.clear_cache()


def _run(**state) -> AppTest:
    at = AppTest.from_file("views/01_Panel.py", default_timeout=120)
    at.session_state["pmg_lang"] = "es"
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


#: The emphasis tier's indigo accent bar, which the plain tier does not draw.
ACCENT = "linear-gradient(180deg,#6366f1,#8b5cf6)"


def _html(at) -> str:
    """Everything the page wrote, markdown and captions alike. The cards, the
    section labels and the ranked lists are raw-HTML markdown blocks; the
    honesty lines that explain a missing arrow are st.caption."""
    parts = [m.value for m in at.markdown if isinstance(m.value, str)]
    parts += [c.value for c in at.caption if isinstance(c.value, str)]
    return "\n".join(parts)


def _cards(html: str) -> list[str]:
    """Each KPI card's HTML, in render order."""
    return re.split(r'(?=class="pmg-kpi pmg-kpi-link"|class="pmg-kpi" style)', html)[1:]


def _card_for(html: str, label: str) -> str:
    for card in _cards(html):
        if f">{label}</div>" in card:
            return card
    raise AssertionError(f"no card labelled {label!r} on the page")


# ── The scoreboard leads, and it is one row ──────────────────────────────────

def test_the_key_indicators_are_the_pages_first_section():
    """Audit P1: the page opened on three nightly outcomes and four conversion
    rates, and the seven indicators the mission is judged on came third."""
    html = _html(_run()).upper()
    ki = html.index("INDICADORES CLAVE")
    for later in ("ACTIVIDAD DIARIA", "TASAS DE CONVERSIÓN", "ZONAS"):
        assert later in html, f"{later} vanished from the page"
        assert ki < html.index(later), \
            f"{later} still renders above the Key Indicators"


def test_there_is_exactly_one_key_indicator_heading():
    """Audit P2: "Semana en curso" and "Semana del 7 al 13" were two headings
    over two rows of the same seven metrics. One heading, one row, and the
    period is a toggle under it."""
    html = _html(_run())
    # Counted on the EMPHASIS tier: the 8-week trend's right-hand chart also
    # carries a plain "Indicadores Clave" sub-label until step C4 replaces it
    # with small multiples, and that is a chart's name, not a page section.
    assert ACCENT in html, "no emphasis-tier heading rendered at all"
    headings = re.findall(r'font-size:1\.05rem;font-weight:800;[^"]*">([^<]*)</span>',
                          html)
    assert headings.count("Indicadores Clave") == 1, (
        f"expected one Key Indicator section heading, found {headings}")


def test_the_seven_indicators_are_one_wrapping_grid_of_links():
    html = _html(_run())
    grid = html[html.index('class="pmg-kpi-grid"'):]
    grid = grid[:grid.index("</div>\n") if "</div>\n" in grid else len(grid)]
    cards = _cards(html)[:7]
    assert len(cards) == 7
    for card in cards:
        assert 'href="?ki=ki_' in card, "a Key Indicator card is not a link"


@pytest.mark.parametrize("period,expected", [
    # Each reading answers a different question, so each must put a different
    # number on the same card. AppTest cannot introspect st.pills, so the
    # toggle is checked through what it selects rather than through its labels.
    ("week", "llega el domingo"),                      # the week in progress
    ("last", f"de {META_PER_AREA * len(AREAS)}"),      # one week's meta
    ("cycle", f"de {META_PER_AREA * len(AREAS) * 2}"),  # two weeks' metas
])
def test_each_period_is_its_own_reading_of_the_same_seven(period, expected):
    card = _card_for(_html(_run(panel_ki_period_val=period)), "Nuevas personas")
    assert expected in card, card


# ── Decision 6: the bar is the meta, leadership is the mark ──────────────────

def test_the_goal_bar_is_the_companionships_meta():
    """Reversed here. The bar used to be leadership's transfer goal, which put
    a different number on the card than the drill-down beneath it drew for the
    same metric and the same week."""
    card = _card_for(_html(_run(panel_ki_period_val="last")),
                     "Nuevas personas")
    meta_total = META_PER_AREA * len(AREAS)          # 16
    actual = REAL_PER_AREA * len(AREAS)              # 20
    assert f">{actual}<" in card, card
    assert f"de {meta_total}" in card, (
        f"the bar is not the companionships' meta of {meta_total}: {card}")


def test_the_leadership_goal_is_a_mark_on_that_bar():
    """A transfer total divided by the cycle's weeks — the same conversion the
    drill-down's violet line makes, so one goal cannot mean two things."""
    card = _card_for(_html(_run(panel_ki_period_val="last")),
                     "Nuevas personas")
    weekly_share = LEAD_PER_AREA * len(AREAS) // CYCLE_WEEKS     # 14
    assert "pmg-kpi-mark" in card, f"no leadership mark on the bar: {card}"
    assert f"Meta del liderazgo, por semana: {weekly_share}" in card, card


# ── A metric the weekly form has not delivered yet ───────────────────────────

def test_an_indicator_still_to_arrive_says_so_instead_of_showing_a_zero():
    """The week in progress has no ki_*_real for four of the seven. A zero
    would report a failure the mission has not had the chance to have."""
    card = _card_for(_html(_run(panel_ki_period_val="week")), "Bautizados")
    assert "llega el domingo" in card, card
    assert ">0<" not in card, card


def test_the_baptismal_calendar_count_is_a_note_not_the_indicator():
    """baptismal_calendars counts calendars handed out — a flow; the indicator
    counts friends who hold a date — a standing count. The tile used to be
    relabelled to the nightly question, which put a name that is not a Key
    Indicator among six that are (decision 11)."""
    html = _html(_run(panel_ki_period_val="week"))
    assert "Con fecha bautismal" in html
    assert "Calendarios Bautismales Entregados" not in html


# ── The cambio reading ───────────────────────────────────────────────────────

def test_the_cambio_reading_compares_what_is_done_against_metas_set_so_far():
    """PLAN §1.1, the cambio grain: the bar is actual so far against the metas
    written for the weeks that have elapsed, and the mark is the full cycle."""
    html = _html(_run(panel_ki_period_val="cycle"))
    card = _card_for(html, "Nuevas personas")
    elapsed_metas = META_PER_AREA * len(AREAS) * 2   # two elapsed weeks = 32
    assert f"de {elapsed_metas}" in card, card
    assert f"Meta del cambio: {LEAD_PER_AREA * len(AREAS)}" in card, card


def test_the_heading_names_the_cambio_and_where_the_week_falls_in_it():
    html = _html(_run())
    assert "cambio 2026-6" in html
    assert re.search(r"semana \d+ de 6", html), html[:400]


def test_a_cambio_with_no_predecessor_says_why_there_is_no_arrow():
    """The schedule holds one cycle, so there is no twin to compare against.
    A silently missing arrow is audit finding M7."""
    html = _html(_run(panel_ki_period_val="cycle"))
    assert "no tiene un cambio anterior" in html


# ── The year, moved up and led by its three figures ──────────────────────────

def test_the_baptism_figures_are_cards_above_the_chart():
    """They were one caption below it (step C1.2). A reader who stops at the
    first line should already have the answer."""
    html = _html(_run())
    for label in ("Bautismos hasta jul", "vs. ritmo de la meta", "Proyección"):
        assert label in html, f"{label!r} is not on the page"
    assert html.upper().index("BAUTISMOS HASTA JUL") < html.upper().index("ZONAS")


def test_the_year_sits_directly_under_the_key_indicators():
    html = _html(_run()).upper()
    assert html.index("INDICADORES CLAVE") < html.index("BAUTISMOS 20")
    assert html.index("BAUTISMOS 20") < html.index("ZONAS")


# ── Step C2: the captions became ⓘ text and chips ────────────────────────────

def test_the_page_no_longer_opens_with_a_paragraph():
    """Three sentences of explanation sat between the title and the first
    number. One of them ("drill into a zone on the Breakdowns page") stopped
    being true when every card became a link."""
    html = _html(_run())
    assert "Los datos de resumen se actualizan a diario" not in html


def test_a_refused_comparison_is_a_chip_on_the_card_not_a_paragraph():
    """The schedule holds no cambio before this one, so there is nothing to
    compare the cambio reading against."""
    html = _html(_run(panel_ki_period_val="cycle"))
    card = _card_for(html, "Nuevas personas")
    assert "pmg-kpi-nochange" in card, card
    assert "sin comparación" in card, card


def test_the_reason_for_a_refused_comparison_is_in_the_sections_info():
    """The chip alone would leave a phone with no way to learn why — there is
    no hover on a touch screen, so the ⓘ carries the sentence too."""
    html = _html(_run(panel_ki_period_val="cycle"))
    info = html[html.index('class="pmg-sec-info"'):]
    info = info[:info.index("</p>")]
    assert "no tiene un cambio anterior" in info, info[:300]


def test_every_section_that_carried_captions_now_carries_an_info_glyph():
    html = _html(_run())
    # One ⓘ per section, and the sections that had captions are the ones that
    # have it: Key Indicators, Bautismos, Zonas, Actividad diaria, Tasas.
    assert html.count('class="pmg-info"') >= 5, (
        f"only {html.count('class=\"pmg-info\"')} sections carry an ⓘ")
