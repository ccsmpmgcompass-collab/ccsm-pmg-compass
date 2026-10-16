"""PLAN-2026-10-06 Phase 4 — the road to 95.

Other years from Tableau (4B.1), the index by transfer and "chronic" (4B.3),
the forecasts' backtests (4C.1), what each leak is worth (4C.2), and the
president's one page (4E.1).
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.reports import focus as FC
from app.reports import forecast as F
from app.reports import model as M
from app.reports import packet as PK


# ── 4B.1 · the same weeks in other years ─────────────────────────────────────

def test_other_years_count_the_same_calendar_days():
    dates = pd.Series(pd.to_datetime(
        ["2024-09-10", "2024-09-20", "2025-09-08", "2025-10-30",
         "2026-09-07", "2026-09-30", "2026-10-06"]))
    y = F.other_years([("Encontradas", dates)], None,
                      date(2026, 9, 7), date(2026, 10, 5))
    assert y.years == (2024, 2025, 2026)
    # 2026-10-06 is past the window's end; 2025-10-30 past last year's.
    assert y.rows == (("Encontradas", (2, 1, 2)),)
    assert y.last_two("Encontradas") == (2, 1)


def test_other_years_follow_the_unit_s_rows():
    dates = pd.Series(pd.to_datetime(["2025-09-10", "2025-09-11"]))
    mask = pd.Series([True, False])
    y = F.other_years([("x", dates)], mask, date(2026, 9, 7), date(2026, 9, 30))
    assert y.rows[0][1][-2] == 1


def test_a_small_year_change_is_said_in_units():
    assert PK._year_change(5, 3) == "+2"
    assert PK._year_change(225, 226) == "igual"
    assert PK._year_change(118, 56).startswith("+")


# ── 4B.3 · the index by transfer, and chronic ────────────────────────────────

def _p(value, events=100.0):
    return M.Productivity(value=value, events=events)


def test_chronic_needs_every_transfer_under_the_line_on_enough_figures():
    assert M.IndexHistory.chronic((_p(48), _p(50)))
    assert not M.IndexHistory.chronic((_p(48), _p(95)))
    assert not M.IndexHistory.chronic((_p(50),))                 # one transfer
    assert not M.IndexHistory.chronic((_p(48, events=5), _p(50)))  # thin


# ── 4C.1 · how good the forecasts have been ──────────────────────────────────

def test_the_landing_backtest_replays_earlier_years_at_the_same_month():
    by_month = {f"{y}-{m:02d}": 30 for y in (2024, 2025) for m in range(1, 13)}
    by_month.update({f"2026-{m:02d}": 30 for m in range(1, 10)})
    bt = F.landing_backtest(by_month, 2026, 9)
    assert [c[0] for c in bt.cases] == ["sep 2025", "sep 2024"]
    # A flat year lands exactly where it ends: every anchor says 360.
    assert all(lo == pytest.approx(360) == hi for _, lo, hi, _ in bt.cases)
    assert bt.hits == 2 and bt.miss == pytest.approx(0)


def test_the_finish_backtest_runs_the_method_on_weekly_counts():
    """Ten a week, every week: the worst and best of the last six are both
    ten, so every range is exact and every one hits."""
    start = date(2024, 1, 1)
    days = [start + timedelta(days=d) for d in range(0, 700) for _ in range(10)
            if (start + timedelta(days=d)).weekday() == 2]
    bt = F.finish_backtest(pd.Series(pd.to_datetime(days)), date(2025, 11, 1),
                           weeks_done=4, windows=5)
    assert len(bt.cases) == 5
    assert all(lo == hi == actual == 60 for _, lo, hi, actual in bt.cases)
    assert bt.hits == 5


def test_a_backtest_sentence_says_one_time_in_the_singular():
    bt = F.Backtest(cases=(("x", 1, 2, 1.5), ("y", 1, 2, 9)))
    assert "acertó 1 vez" in bt.sentence


# ── 4C.2 · what a leak is worth ──────────────────────────────────────────────

def _funnel(zone_reached, mission_reached, found=1000, leak_index=4):
    labels = ("Intento de Contacto", "Contactadas con Éxito",
              "Recibiendo Lecciones", "Asistió a la Iglesia",
              "Fecha de Bautismo Fijada", "Bautizados")
    zone = FC.FunnelRow(name="Z", found=found, reached=zone_reached,
                        leak="iglesia a fecha", leak_index=leak_index)
    mission = FC.FunnelRow(name="la misión", found=found * 10,
                           reached=tuple(10 * r for r in mission_reached))
    return FC.MatureFunnel(start=date(2026, 4, 1), end=date(2026, 7, 1),
                           stages=labels, rows=(zone,), mission=mission)


def test_a_lever_carries_the_missing_step_to_dates_and_baptisms():
    """Z sends 100 people to church; 20 get a date where the mission's rate
    would give 40. Twenty more dates per 90 days of finding, about nine per
    six weeks, and half of them baptised at both Z's and the mission's rate."""
    fn = _funnel((900, 500, 300, 100, 20, 10), (900, 500, 300, 100, 40, 20))
    lever = FC.levers(fn)[0]
    lo, hi = lever.dates
    assert lo < 20 * 42 / 90 < hi
    assert lever.baptisms[0] < lever.dates[0]
    assert lever.leak == "iglesia a fecha"


def test_no_named_leak_no_lever():
    fn = _funnel((900, 500, 300, 100, 40, 20), (900, 500, 300, 100, 40, 20),
                 leak_index=None)
    assert FC.levers(fn) == ()


# ── 4E.1 · the president's one page ──────────────────────────────────────────

def test_the_resumen_is_page_two_and_listed_first():
    """Page 1 is the story (PLAN-2026-10-13 3.3); the resumen is the first
    section after it, and "Cómo leer" is an appendix before the guide."""
    sections = PK.sections_for([])
    assert sections[0].key == PK.RESUMEN
    assert sections[1].key == PK.MISSION
    assert [s.key for s in sections[-2:]] == [PK.HOW_TO_READ, PK.PRINT_GUIDE]


def test_the_resumen_asks_each_zone_one_question():
    from app.reports import summary as SM
    d = M.Driver(name="Angol", low_key="ki_rc_at_church_real",
                 low_label="Conversos Recientes en la Iglesia", low_ratio=44,
                 leak="fecha a bautismo", leak_step=(6.2, 16.0))
    m = type("M", (), {"drivers": (d,)})()
    q = SM.questions(m)
    assert q == ["Angol: ¿Qué pasa entre fecha y bautismo? Pasa el 6,2%; "
                 "la misión, el 16,0%."]
