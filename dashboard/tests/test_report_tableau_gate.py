# -*- coding: utf-8 -*-
"""Phase T step T1 — the freshness gate.

Decision 32: the finding section is allowed to be absent, and a period the
stored export cannot cover gets a stated reason instead of a number. These
tests pin the four outcomes of `clip`, the fact that the gate keys on COVERAGE
rather than on age, and that a comparison window is never drawn at a different
length from the window it is held against.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.reports import periods as P
from app.reports import tableau as T


def detail(dates) -> pd.DataFrame:
    """A Detail frame with nothing but found-dates — all `read_export` reads."""
    return pd.DataFrame({"event_date_selected": [str(d) for d in dates]})


def span(first: str, last: str) -> pd.DataFrame:
    lo, hi = date.fromisoformat(first), date.fromisoformat(last)
    days = (hi - lo).days
    return detail([lo + timedelta(days=i) for i in range(days + 1)])


def period(start: str, end: str, *, key: str = "p", label: str = "Período"):
    """A Period with the two fields the gate reads, and honest week bookkeeping."""
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    return P.Period(key=key, label=label, start=s, end=e, weeks=(),
                    full_end=e, full_weeks=1)


# ── Describing the export ─────────────────────────────────────────────────────

def test_an_empty_export_is_absent_rather_than_a_zero_length_window():
    export = T.read_export(pd.DataFrame())
    assert not export.present
    assert export.first is None and export.last is None
    assert export.freshness_label(date(2026, 9, 21)) == "sin exportación de Tableau"


def test_the_window_comes_from_the_data_not_from_a_configured_floor():
    export = T.read_export(span("2024-01-01", "2024-01-10"))
    assert export.first == date(2024, 1, 1)
    assert export.last == date(2024, 1, 10)
    assert export.rows == 10


def test_age_is_measured_from_the_last_found_date_not_from_the_upload():
    """The live export was uploaded on 2026-09-21 and ends 2026-09-17. An
    export is as old as the newest day it holds, not as old as its file."""
    export = T.read_export(span("2026-09-01", "2026-09-17"),
                           uploaded_by="auto:tableau",
                           uploaded_at="2026-09-21 19:47 UTC")
    assert export.age_days(date(2026, 9, 21)) == 4
    assert not export.stale(date(2026, 9, 21))
    assert export.stale(date(2026, 9, 30))


def test_the_freshness_strip_names_the_day_the_export_reaches():
    export = T.read_export(span("2026-09-01", "2026-09-17"))
    strip = export.freshness_label(date(2026, 9, 21))
    assert "17 de sep de 2026" in strip
    assert "4 días atrás" in strip


@pytest.mark.parametrize("today,expected", [
    (date(2026, 9, 17), "hasta hoy"),
    (date(2026, 9, 18), "hasta ayer"),
])
def test_today_and_yesterday_are_words_not_a_day_count(today, expected):
    export = T.read_export(span("2026-09-01", "2026-09-17"))
    assert expected in export.freshness_label(today)


def test_the_auto_sync_is_named_in_spanish_not_as_its_marker():
    export = T.read_export(span("2026-09-01", "2026-09-17"),
                           uploaded_by="auto:tableau",
                           uploaded_at="2026-09-21 19:47 UTC")
    assert export.source_label() == "sincronización automática, 2026-09-21 19:47 UTC"


# ── The gate ──────────────────────────────────────────────────────────────────

def test_a_period_the_export_covers_whole_is_not_clipped():
    export = T.read_export(span("2024-01-01", "2026-09-17"))
    window = T.clip(period("2026-07-27", "2026-09-06"), export)
    assert window.usable and not window.clipped
    assert window.days == 42 and window.coverage == 1.0
    assert window.shortfall_label == ""
    assert window.caption == "fuente: Tableau · 27 de jul - 6 de sep de 2026"


def test_an_in_progress_period_is_clipped_and_says_by_how_much():
    """The live case on 2026-09-21: this transfer runs 09-07..09-21 and the
    export reaches 09-17, so eleven of its fifteen days are answerable."""
    export = T.read_export(span("2024-01-01", "2026-09-17"))
    window = T.clip(period("2026-09-07", "2026-09-21"), export)
    assert window.usable and window.clipped
    assert (window.start, window.end) == (date(2026, 9, 7), date(2026, 9, 17))
    assert window.days == 11 and round(window.coverage, 2) == 0.73
    assert window.shortfall_label == "11 de 15 días del período"
    assert "fuente: Tableau" in window.caption
    assert "11 de 15 días del período" in window.caption


def test_a_period_after_the_export_ends_is_refused_with_the_export_s_own_date():
    export = T.read_export(span("2024-01-01", "2026-08-03"))
    window = T.clip(period("2026-09-07", "2026-09-21"), export)
    assert not window.usable
    assert "3 de ago de 2026" in window.reason
    assert "no alcanza este período" in window.reason


def test_a_period_before_the_export_begins_is_refused_the_other_way():
    export = T.read_export(span("2026-01-01", "2026-09-17"))
    window = T.clip(period("2025-03-01", "2025-04-01"), export)
    assert not window.usable
    assert "empieza el" in window.reason and "1 de ene de 2026" in window.reason


def test_a_sliver_of_a_period_is_refused_rather_than_captioned():
    """Decision 32's case: an export six days behind covers one day of last
    week, and one evening printed under "Semana pasada" is the thing that is
    worse than no finding section."""
    export = T.read_export(span("2026-01-01", "2026-09-14"))
    window = T.clip(period("2026-09-14", "2026-09-20"), export)
    assert not window.usable
    assert "sólo cubre 1 de 7 días" in window.reason
    assert "muy poco" in window.reason


def test_the_floor_is_coverage_and_lets_a_thin_but_real_window_through():
    export = T.read_export(span("2026-01-01", "2026-09-16"))
    window = T.clip(period("2026-09-14", "2026-09-20"), export)
    assert window.usable and window.days == 3        # 3/7 = 43%, above 25%
    assert window.clipped


def test_the_gate_ignores_how_old_the_export_is_when_the_period_is_covered():
    """An export 49 days behind today still answers for a period that closed
    before it ended. Gating on age would have refused this one."""
    export = T.read_export(span("2024-01-01", "2026-08-03"))
    window = T.clip(period("2026-06-15", "2026-07-26"), export)
    assert export.stale(date(2026, 9, 21))
    assert window.usable and not window.clipped


def test_no_export_at_all_is_its_own_sentence():
    window = T.clip(period("2026-09-07", "2026-09-21"), T.read_export(pd.DataFrame()))
    assert not window.usable
    assert window.reason == "no hay ninguna exportación de Tableau guardada"
    assert window.label == "—" and window.days == 0


# ── The comparison ────────────────────────────────────────────────────────────

def test_the_comparison_matches_the_clipped_window_s_length_not_the_period_s():
    """Eleven days of this transfer against forty-two of the last one would
    print a collapse that is entirely the two windows being different sizes."""
    export = T.read_export(span("2024-01-01", "2026-09-17"))
    window = T.clip(period("2026-09-07", "2026-09-21"), export)
    before = T.preceding(window)
    assert before.days == window.days == 11
    assert (before.start, before.end) == (date(2026, 8, 27), date(2026, 9, 6))


def test_a_comparison_running_off_the_front_of_the_export_is_refused():
    export = T.read_export(span("2026-09-01", "2026-09-17"))
    window = T.clip(period("2026-09-07", "2026-09-17"), export)
    before = T.clamp(T.preceding(window), export)
    assert not before.usable
    assert "ventana de comparación completa" in before.reason


def test_a_comparison_the_export_holds_whole_is_kept():
    export = T.read_export(span("2024-01-01", "2026-09-17"))
    window = T.clip(period("2026-09-07", "2026-09-21"), export)
    before = T.clamp(T.preceding(window), export)
    assert before.usable and before.days == 11


def test_an_unusable_window_has_no_comparison_at_all():
    window = T.clip(period("2026-09-07", "2026-09-21"),
                    T.read_export(pd.DataFrame()))
    assert not T.preceding(window).usable


# ── Purity ────────────────────────────────────────────────────────────────────

def test_importing_the_gate_does_not_pull_in_streamlit():
    """A cold interpreter, not a `sys.modules` deletion: P2's note records the
    122 tests the in-process version broke."""
    import subprocess
    import sys

    code = ("import app.reports.tableau, sys; "
            "sys.exit(1 if 'streamlit' in sys.modules else 0)")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


# ── T2 · Reconciliation ───────────────────────────────────────────────────────

def roster(rows) -> pd.DataFrame:
    """A MISSION_ORG-shaped frame: (area, zone) pairs."""
    return pd.DataFrame([{"Area_Name": a, "Zone": z, "District": "D"}
                         for a, z in rows])


def detail_rows(rows) -> pd.DataFrame:
    """(found date, zone, area) per person."""
    return pd.DataFrame([{"event_date_selected": d,
                          "latest_zone_name": z,
                          "latest_teaching_area_name": a} for d, z, a in rows])


def test_rows_are_claimed_by_area_name_never_by_the_exports_own_zone():
    """`scope.py`'s standing rule: an area that transferred still carries its
    old zone on every row written before the move."""
    det = detail_rows([("2026-09-10", "Angol", "El Mirador"),
                       ("2026-09-10", "San Pedro", "El Mirador"),
                       ("2026-09-10", "Angol", "Los Huertos")])
    assert len(T.for_areas(det, ["El Mirador"])) == 2


def test_an_export_name_the_roster_does_not_carry_is_dropped_from_a_unit():
    det = detail_rows([("2026-09-10", "Angol", "El Mirador"),
                       ("2026-09-10", "Angol", "Caupolican")])
    assert len(T.for_areas(det, ["El Mirador", "Los Huertos"])) == 1


def test_reconcile_counts_the_dropped_rows_rather_than_letting_them_vanish():
    """The live shape on 2026-09-21: three export names inside the pilot zones
    that MISSION_ORG does not carry, worth 23 people of 42.616."""
    det = detail_rows([("2026-09-10", "Angol", "El Mirador")] * 97
                      + [("2026-09-10", "Angol", "Caupolican")] * 2
                      + [("2026-09-10", "Angol", "Lautaro")])
    rec = T.reconcile(det, roster([("El Mirador", "Angol")]))
    assert rec.unknown == (("Caupolican", 2), ("Lautaro", 1))
    assert rec.unknown_rows == 3 and rec.scoped_rows == 100
    assert rec.unknown_share == 0.03
    assert "Caupolican · Lautaro" in rec.note
    assert "3 personas" in rec.note


def test_zones_outside_the_pilot_are_not_counted_as_unmatched_names():
    """Six of the mission's ten zones run no Compass forms. Counting them as
    misses would report 57% of the mission as a data error."""
    det = detail_rows([("2026-09-10", "Angol", "El Mirador"),
                       ("2026-09-10", "Villarrica", "Pucón")])
    rec = T.reconcile(det, roster([("El Mirador", "Angol")]))
    assert rec.clean and rec.note == ""
    assert rec.scoped_rows == 1 and rec.total_rows == 2


def test_a_roster_area_the_export_never_names_is_reported_as_a_silence():
    det = detail_rows([("2026-09-10", "Angol", "El Mirador")])
    rec = T.reconcile(det, roster([("El Mirador", "Angol"),
                                   ("Los Huertos", "Angol")]))
    assert rec.missing == ("Los Huertos",)
    assert "no aparecen en la exportación" in rec.note


def test_a_refused_window_selects_nothing_rather_than_everything():
    """A gate that fell through to the whole 2.7-year export would be worse
    than no gate: the refusal would print as a very large number."""
    det = detail_rows([("2026-09-10", "Angol", "El Mirador")])
    refused = T.clip(period("2026-09-07", "2026-09-21"),
                     T.read_export(pd.DataFrame()))
    assert T.in_window(det, refused).empty


def test_in_window_keeps_only_the_days_the_gate_allowed():
    det = detail_rows([("2026-09-06", "Angol", "El Mirador"),
                       ("2026-09-10", "Angol", "El Mirador"),
                       ("2026-09-20", "Angol", "El Mirador")])
    window = T.clip(period("2026-09-07", "2026-09-21"),
                    T.read_export(span("2024-01-01", "2026-09-17")))
    assert len(T.in_window(det, window)) == 1
