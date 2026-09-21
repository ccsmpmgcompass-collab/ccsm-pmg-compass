"""The mission's pages, M1–M5 — PLAN step P3.

These tests are about the translation from a `ReportModel` to a printed row,
and three of them are about refusing to print something.

**A goal that is not a yardstick is not a verdict** (decision 22): the row says
so instead of being graded, and it is not eligible to be named the mission's
best or worst work.

**A nightly row's colour is its movement, not its distance from its goal**
(decision 31): the bar draws in the magnitude blue and the change carries the
status, because seventeen of twenty rows are below 90% of a goal set at roughly
twice what the mission does.

**A change measured across a window that holds one area keeps its number and
loses its arrow**: decision 6 says a partial comparison is shown, and §1.3 says
it must degrade visibly. The live default comparison for this transfer prints
every Key Indicator between −36% and −65% off a single area's fortnight.
"""

import re
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from app.reports import grading as G
from app.reports import model as M
from app.reports import packet as PK
from app.reports import packet_parts as PP

TODAY = date(2026, 9, 21)
W2 = date(2026, 9, 20)

CYCLES = [
    {"number": "2026-5", "start": date(2026, 7, 27), "end": date(2026, 9, 6),
     "weeks": 6, "status": "Actual"},
    {"number": "2026-6", "start": date(2026, 9, 7), "end": date(2026, 10, 18),
     "weeks": 6, "status": "Actual"},
]

ROSTER = pd.DataFrame([
    {"Area_Name": "A1", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "A2", "Zone": "Norte", "District": "D1"},
    {"Area_Name": "B1", "Zone": "Sur", "District": "D2"},
])

NEW = "ki_new_people_real"
SACR = "ki_friends_sacrament_real"
BAUT = "ki_baptized_confirmed_real"

WEEKLY_KI = pd.DataFrame([
    {"_week": "2026-09-13", "_area": "A1", NEW: 20, SACR: 4, BAUT: 1},
    {"_week": "2026-09-13", "_area": "B1", NEW: 30, SACR: 6, BAUT: 0},
    {"_week": "2026-09-20", "_area": "A1", NEW: 10, SACR: 2, BAUT: 0},
])

DAILY = pd.DataFrame(
    [{"_day": d, "_area": a, "contacts_attempted": 30, "roleplays": 1}
     for d in ("2026-09-14", "2026-09-15") for a in ("A1", "B1")]
)

#: A2 is deliberately absent: the scoring agent writes no row for an area it
#: has not scored, and "not scored" must not average in as a zero.
SCORES = pd.DataFrame([
    {"_week": "2026-09-13", "_area": a, "Effort_Score": 60.0,
     "Skill_Score": 70.0, "KI_Score": 40.0, "Effectiveness_Score": 55.0}
    for a in ("A1", "B1")
])


def _ki_goals(week, areas=None):
    """Three areas filed the source form; the goals are round numbers."""
    return ({NEW: 90.0, SACR: 30.0, BAUT: 3.0},
            {NEW: 3, SACR: 3, BAUT: 3}, date(2026, 9, 6), 3)


def _data(**over) -> M.ReportData:
    kw = dict(roster=ROSTER, weekly_ki=WEEKLY_KI, daily_log=DAILY,
              scores=SCORES,
              cycles=CYCLES, ki_keys=(NEW, SACR, BAUT),
              nightly_keys=("contacts_attempted", "roleplays"),
              nightly_goals={"contacts_attempted": 150.0, "roleplays": 7.0},
              labels={NEW: "Nuevas Personas", SACR: "Amigos en Sacramental",
                      BAUT: "Bautizados y Confirmados",
                      "contacts_attempted": "Intentos de Contacto",
                      "roleplays": "Prácticas de Enseñanza"},
              mission_name="Misión de Prueba", today=TODAY, anchor=W2,
              ki_goals_fn=_ki_goals)
    kw.update(over)
    return M.ReportData(**kw)


@pytest.fixture(scope="module")
def models():
    return M.build_all(data=_data())


@pytest.fixture(scope="module")
def mission(models):
    return models[0]


def _row(model, key):
    return next(r for r in model.key_indicators if r.key == key)


# ── A Key Indicator becomes a printed row ─────────────────────────────────────

def test_the_bar_fills_against_the_companionships_own_goal(mission):
    """Decision 11, and the same statement the KPI card makes on the screen —
    so the two surfaces cannot disagree about what a bar means."""
    line = next(l for l in PK.ki_lines(mission, comparable=False)
                if l.label == "Nuevas Personas")
    row = _row(mission, NEW)
    assert line.value == "60"                     # the raw sum, decision 12
    assert line.pct == pytest.approx(row.grade.pct)


def test_the_violet_mark_is_the_leadership_goal_on_the_same_scale(mission):
    """A mark drawn against a different denominator from the bar beside it is
    two numbers pretending to be comparable."""
    row = _row(mission, NEW)
    marked = replace(row, leadership_goal=45.0, leadership_goal_complete=True)
    model = replace(mission, key_indicators=(marked,))
    line = PK.ki_lines(model, comparable=False)[0]
    assert line.mark_pct == pytest.approx(45.0 / row.meta * 100)


def test_a_unit_with_no_transfer_goal_says_so_instead_of_drawing_a_mark(mission):
    """Decision 23 — 44 of 45 areas have no 2026-5 goal, and a bar marked with
    a goal nobody set would be a fabricated figure wearing the unit's name."""
    line = next(l for l in PK.ki_lines(mission, comparable=False)
                if l.label == "Nuevas Personas")
    assert line.mark_pct is None
    assert "sin meta de traslado" in line.note


def test_a_flagged_goal_prints_the_flag_instead_of_a_grade(mission):
    """Decision 22: it is not scored, so there is no word to print."""
    row = replace(_row(mission, NEW),
                  grade=G.Grade(status=None, pct=12.0, flag=G.GOAL_TOO_HIGH))
    line = PK.ki_lines(replace(mission, key_indicators=(row,)),
                       comparable=False)[0]
    assert line.verdict == "meta no utilizable: demasiado alta"
    assert not any(word in line.verdict for word in PP.STATUS_WORD.values())


def test_a_graded_row_prints_the_word_and_the_percentage(mission):
    row = replace(_row(mission, NEW), grade=G.Grade(status="warn", pct=71.0))
    line = PK.ki_lines(replace(mission, key_indicators=(row,)),
                       comparable=False)[0]
    assert line.verdict == "atrasado · 71%"


# ── The change column, and its two kinds of silence ───────────────────────────

def _line_with_change(mission, *, comparable, confident, pct=-64.0):
    row = replace(_row(mission, NEW), grade=G.Grade(status="bad", pct=50.0,
                                                    change_pct=pct))
    return PK.ki_lines(replace(mission, key_indicators=(row,)),
                       comparable=comparable, confident=confident)[0]


def test_no_comparison_window_prints_no_change_at_all(mission):
    assert _line_with_change(mission, comparable=False, confident=False).change is None


def test_a_thin_window_keeps_the_number_and_drops_the_direction(mission):
    """The live case: the default comparison for this transfer is the first two
    weeks of 2026-5, which hold a single area, and all seven Key Indicators
    come out between −36% and −65%. Seven red triangles down a council page
    would report that area's fortnight as the mission collapsing."""
    change = _line_with_change(mission, comparable=True, confident=False).change
    assert change == (0, "-64%")
    assert PP.change_mark(0, 0, change[0]) is None      # no triangle is drawn


def test_a_window_worth_trusting_carries_its_direction(mission):
    assert _line_with_change(mission, comparable=True,
                             confident=True).change == (-1, "-64%")
    assert _line_with_change(mission, comparable=True, confident=True,
                             pct=12.0).change == (1, "+12%")


def test_the_sign_is_written_out_as_well_as_drawn():
    """A photocopy loses the colour; the "+" and "−" survive it."""
    from app.config import es_display
    assert es_display.signed_percent(12) == "+12%"
    assert es_display.signed_percent(-12) == "-12%"


# ── The nightly table ─────────────────────────────────────────────────────────

def test_the_nightly_bar_is_a_magnitude_and_not_a_grade(mission):
    """Decision 31. Seventeen of twenty real rows sit below 60% of their goal;
    painting them is the wall of colour decision 10 exists to prevent."""
    lines = PK.nightly_lines(mission, _data().nightly_goals, comparable=False)
    assert lines and all(line.magnitude for line in lines)
    assert all(line.status is None for line in lines)


def test_the_nightly_rows_run_furthest_behind_first(mission):
    lines = PK.nightly_lines(mission, _data().nightly_goals, comparable=False)
    graded = [l.pct for l in lines if l.pct is not None]
    assert graded == sorted(graded)


def test_a_nightly_row_names_the_goal_it_is_measured_against(mission):
    lines = PK.nightly_lines(mission, _data().nightly_goals, comparable=False)
    line = next(l for l in lines if l.label == "Intentos de Contacto")
    # A flag rides on the same line when the goal has stopped being a
    # yardstick, so the goal is what the note OPENS with rather than all of it.
    assert line.note.startswith("meta 150/área/sem")
    assert line.verdict.endswith("de la meta")


def test_a_nightly_metric_with_no_configured_goal_says_so():
    """Built goal-free, not just printed goal-free: `nightly_lines` takes the
    goals the MODEL was built from, so handing it a different dict would only
    change the note and leave the verdict disagreeing with it."""
    bare = M.build_all(data=_data(nightly_goals={}))[0]
    lines = PK.nightly_lines(bare, {}, comparable=False)
    assert lines
    assert all(l.note.startswith("sin meta configurada") for l in lines)
    assert all(l.verdict == "sin meta" for l in lines)
    assert all(l.goal == "—" and l.pct is None for l in lines)


# ── What M1 names ─────────────────────────────────────────────────────────────

def test_the_furthest_behind_excludes_a_goal_that_is_not_a_yardstick(mission):
    """Naming it would report the goal as though it were the work."""
    rows = list(mission.key_indicators)
    rows[0] = replace(rows[0], grade=G.Grade(pct=3.0, flag=G.GOAL_TOO_HIGH))
    model = replace(mission, key_indicators=tuple(rows))
    named = PK.furthest_behind(model)
    assert rows[0].label not in {r.label for r in named}


def test_the_best_and_the_worst_are_the_ends_of_the_same_ordering(mission):
    best, worst = PK._best_and_worst(mission)
    graded = sorted((r.grade.pct for r in mission.key_indicators
                     if r.grade.pct is not None and not r.grade.flag))
    assert best.grade.pct == graded[-1] and worst.grade.pct == graded[0]


def test_a_mission_with_nothing_graded_names_neither(mission):
    blank = replace(mission, key_indicators=tuple(
        replace(r, grade=G.Grade()) for r in mission.key_indicators))
    assert PK._best_and_worst(blank) == (None, None)
    assert PK.furthest_behind(blank) == []


def test_the_headline_tiles_fall_back_rather_than_coming_out_empty(mission):
    """The four named Key Indicators are CCSM's; a mission whose catalogue
    differs still gets a band rather than a blank strip."""
    odd = replace(mission, key_indicators=tuple(
        replace(r, key=f"other_{i}") for i, r in
        enumerate(mission.key_indicators)))
    assert len(PK._headline_tiles(odd)) == min(4, len(odd.key_indicators))


# ── The week table ────────────────────────────────────────────────────────────

def test_the_week_table_carries_how_many_areas_filed_each_week(mission):
    """These are raw sums, and CCSM's weekly reporting runs 26 to 36 areas of
    45 between one week and the next. Without this row a week with nine fewer
    forms reads as a mission that halved its work."""
    weeks, rows, _, reporting = PK._week_rows(mission)
    assert len(reporting) == len(weeks)
    assert reporting == [2, 1]          # A1 + B1, then A1 alone


def test_a_transfer_boundary_lands_between_two_week_columns(mission):
    """Decision 9. An index of 0 would draw the rule off the table's edge."""
    _, _, boundaries, _ = PK._week_rows(mission)
    assert all(b > 0 for b in boundaries)


def test_the_week_columns_give_way_to_the_line_when_there_are_too_many():
    """"Año" can run to thirty-eight complete weeks, and thirty-eight columns
    of 13pt is not a table anybody reads."""
    weeks = [date(2026, 1, 4)] * (PP.WEEK_COLUMN_LIMIT + 2)
    wide = PP.week_table(520, weeks, [("x", [1] * len(weeks), "9")])
    narrow = PP.week_table(520, weeks[:2], [("x", [1, 2], "3")])
    assert wide.height <= narrow.height


# ── The pages themselves ──────────────────────────────────────────────────────

def test_the_missions_pages_run_in_order_one_section_to_a_page(models):
    """M1-M5 and the scores, in order, one to a page.

    Scanned forward rather than searched: "Indicadores Clave" also appears in
    M1's own section note ("de los Indicadores Clave con una meta utilizable"),
    and "zonas" appears on the cover's contents. A plain substring search finds
    those first and reports the packet as out of order when it is not.
    """
    import io

    from pypdf import PdfReader
    pdf = PK.build_packet(models, ROSTER, _data().nightly_goals)
    pages = [(p.extract_text() or "").upper()
             for p in PdfReader(io.BytesIO(pdf)).pages]
    heads = ["DÓNDE ESTAMOS", "INDICADORES CLAVE", "SEMANA A SEMANA", "ZONAS",
             "TODO EL TRABAJO NOCTURNO", "PUNTAJES"]
    at, found = 0, []
    for head in heads:
        at = next(i for i in range(at, len(pages)) if head in pages[i])
        found.append(at)
        at += 1
    # Strictly increasing and one to a page. Outcomes, then activity, then
    # process: the scores are last because they judge how the work was done.
    assert found == sorted(set(found))
    assert found[-1] - found[0] == len(heads) - 1


def test_every_string_the_mission_pages_print_survives_the_encoding(mission):
    """If `text()` changes anything here, something is about to print in
    ZapfDingbats — see `packet_parts`."""
    from reportlab.platypus import Paragraph, Table
    seen = 0

    def walk(flow):
        nonlocal seen
        if isinstance(flow, Paragraph):
            seen += 1
            assert PP.is_printable(re.sub(r"<[^>]+>", "", flow.text)), flow.text
        elif isinstance(flow, Table):
            for row in flow._cellvalues:
                for cell in row:
                    walk(cell)
        elif isinstance(flow, (list, tuple)):
            for item in flow:
                walk(item)
        elif isinstance(flow, PP.SectionHead):
            seen += 1
            assert PP.is_printable(flow.label) and PP.is_printable(flow.note)
        elif isinstance(flow, PP.TrackedLabel):
            seen += 1
            assert PP.is_printable(flow.label)

    walk(PK.mission_pages(mission, _data().nightly_goals))
    assert seen > 20
