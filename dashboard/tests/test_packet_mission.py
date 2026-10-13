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


#: Leadership's 2026-6 goals (decision 59): per area-week 20 new people, 8
#: friends at sacrament and one baptism. Three areas over two weeks is six
#: area-weeks of goal, and the three that did not report count as zero, so
#: the grade is 60 of 120 new people (50%), 12 of 48 friends (25%) and one of
#: six baptisms (17%, never coloured — decision 46).
LEAD_GOALS = pd.DataFrame([
    {"area": a, "transfer_start": "2026-09-07", NEW: 120, SACR: 48, BAUT: 6}
    for a in ("A1", "A2", "B1")])


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
              transfer_goals=LEAD_GOALS, ki_goals_fn=_ki_goals)
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


def test_the_grade_is_leadership_s_and_the_compromiso_is_its_own_column(
        mission):
    """Decision 59: META is leadership's full goal for every area-week, a
    silent one counting as zero, and the companionships' own summed goal is
    the uncoloured COMPROMISO beside it — no violet mark on the bar."""
    rows = {l.label: l for l in PK.ki_lines(mission, comparable=False)}
    new, sacr = rows["Nuevas Personas"], rows["Amigos en Sacramental"]
    assert (new.value, new.goal, new.pct) == ("60", "120", pytest.approx(50))
    assert new.status == "bad"
    assert new.note == ""                    # every area-week has a goal
    assert (sacr.goal, sacr.pct, sacr.status) == ("48", pytest.approx(25),
                                                  "bad")
    assert new.own == "180"                  # 90 a week, two weeks
    assert new.mark_pct is None


def test_the_form_s_baptisms_carry_a_percentage_and_no_colour(mission):
    """Decision 46: 527 is the baptism target, so leadership's transfer goal
    is shown and never colours the row."""
    line = next(l for l in PK.ki_lines(mission, comparable=False)
                if l.label == "Bautizados y Confirmados")
    assert line.pct == pytest.approx(100 / 6)
    assert line.status is None
    assert "meta anual" in line.note


def test_a_unit_with_no_transfer_goal_says_so_and_is_not_graded():
    """Decision 23 — 44 of 45 areas had no 2026-5 goal, and a grade against a
    goal nobody set would be a fabricated figure wearing the unit's name."""
    bare = M.build_all(data=_data(transfer_goals=pd.DataFrame()))[0]
    line = next(l for l in PK.ki_lines(bare, comparable=False)
                if l.label == "Nuevas Personas")
    assert line.pct is None and line.status is None
    assert line.goal == "—"
    assert "sin meta del liderazgo" in line.note


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


def test_no_comparison_window_prints_a_dash(mission):
    """Decision 38: no base, no figure — a dash, not a blank cell that reads
    like a rendering fault."""
    assert _line_with_change(mission, comparable=False,
                             confident=False).change == (0, "—")


def test_a_thin_window_prints_a_dash_not_a_figure_it_disowns(mission):
    """A2. The live case: the default comparison for this transfer is the first
    two weeks of 2026-5, which hold a single area, and all seven Key
    Indicators come out between −36% and −65%. The packet printed them in grey
    and disowned them four lines below; decision 38 prints nothing."""
    change = _line_with_change(mission, comparable=True, confident=False).change
    assert change == (0, "—")
    assert PP.change_mark(0, 0, change[0]) is None      # no triangle is drawn


def test_the_column_head_carries_the_reason():
    assert PK._metric_headers(based=True)[-1] == "Cambio"
    assert PK._metric_headers(based=False)[-1] == ("Cambio",
                                                   "sin base este período")


def test_a_head_with_a_second_line_prints_both(mission):
    table = PP.metric_table([], headers=PK._metric_headers(based=False))
    head = table._cellvalues[0][-1]
    assert isinstance(head, list) and len(head) == 2
    assert head[0].label == "Cambio"
    assert "sin base este período" in head[1].text


def test_the_second_line_fits_its_column_on_one_line():
    """70pt, less 7pt of padding, holds 61pt of note."""
    room = PP.METRIC_COLUMNS[-1] - 2 * 3.5
    assert PP.width_of("sin base este período", PP.NOTE) <= room
    assert sum(PP.METRIC_COLUMNS) == PP.CONTENT_WIDTH


def test_the_note_under_the_table_no_longer_disowns_a_figure(mission):
    note = PK._comparison_note(mission)
    assert "sin dirección" not in note
    assert "La cifra se muestra" not in note


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
    # AUDIT-2026-10-06 H4: REAL and META on one basis, per area per week, so
    # the goal is the META cell itself and the period's total is the note.
    assert line.goal == "150"
    assert line.note.startswith("total del período: ")
    assert line.verdict.endswith("de la meta")


def test_a_flagged_nightly_goal_sorts_last_not_first(mission):
    """AUDIT-2026-10-06 H4: "Lecciones con CR" topped every nightly table for a
    goal nobody could meet. A flagged goal is not a yardstick, so it cannot be
    the furthest from one."""
    rows = list(mission.nightly_metrics)
    rows[0] = replace(rows[0], grade=G.Grade(pct=1.0, flag=G.GOAL_TOO_HIGH))
    ordered = replace(mission, nightly_metrics=tuple(rows)).nightly_weakest_first
    assert ordered[-1].grade.flag == G.GOAL_TOO_HIGH


def test_the_nightly_page_says_why_a_count_differs_from_the_key_indicator(
        mission):
    """900 nightly against 806 weekly for "Nuevas Personas Encontradas", with
    nothing connecting them — the sentence is the model's, both renderers'."""
    text = mission.nightly_source_note
    assert "informe de cada noche" in text and "semanas completas" in text
    page = " ".join(getattr(f, "text", "") for f in
                    PK.nightly_page(mission, _data().nightly_goals))
    assert "informe de cada noche" in page
    assert "más lejos de su meta primero" in " ".join(
        f.note for f in
        PK.nightly_page(mission, _data().nightly_goals)
        if isinstance(f, PP.SectionHead))


def test_a_nightly_metric_with_no_configured_goal_says_so():
    """Built goal-free, not just printed goal-free: `nightly_lines` takes the
    goals the MODEL was built from, so handing it a different dict would only
    change the note and leave the verdict disagreeing with it."""
    bare = M.build_all(data=_data(nightly_goals={}))[0]
    lines = PK.nightly_lines(bare, {}, comparable=False)
    assert lines
    assert all("sin meta configurada" in l.note for l in lines)
    assert all(l.verdict == "sin meta" for l in lines)
    assert all(l.goal == "—" and l.pct is None for l in lines)


# ── What M1 names ─────────────────────────────────────────────────────────────

def test_the_furthest_behind_excludes_a_goal_that_is_not_a_yardstick(mission):
    """Naming it would report the goal as though it were the work."""
    rows = list(mission.key_indicators)
    rows[0] = replace(rows[0], grade=G.Grade(pct=3.0, flag=G.GOAL_TOO_HIGH))
    model = replace(mission, key_indicators=tuple(rows))
    best, worst = PK._best_and_worst(model)
    assert rows[0].label not in {r.label for r in (best, worst) if r}


def test_the_best_and_the_worst_are_the_ends_of_the_same_ordering(mission):
    best, worst = PK._best_and_worst(mission)
    graded = sorted((r.grade.pct for r in mission.key_indicators
                     if r.grade.pct is not None and not r.grade.flag
                     and r.key not in PK.NOT_FOR_VERDICTS))
    assert best.grade.pct == graded[-1] and worst.grade.pct == graded[0]


# ── Decision 37: the form's baptisms never open a unit ────────────────────────

BAPTIZED = "ki_baptized_confirmed_real"


def _with_baptisms_at(mission, pct):
    rows = [replace(r, grade=G.Grade(status="warn", pct=pct))
            if r.key == BAPTIZED else r for r in mission.key_indicators]
    assert any(r.key == BAPTIZED for r in rows), "fixture lost the baptism row"
    return replace(mission, key_indicators=tuple(rows))


def test_the_form_s_baptisms_are_never_called_the_strongest(mission):
    """A1: page 3 called baptisms the mission's strongest number off the
    form's 5, beside a certified 319 + 24."""
    best, _ = PK._best_and_worst(_with_baptisms_at(mission, 999.0))
    assert best is not None and best.key != BAPTIZED


def test_nor_the_one_that_has_to_move(mission):
    model = _with_baptisms_at(mission, 0.5)
    _, worst = PK._best_and_worst(model)
    assert worst is not None and worst.key != BAPTIZED


def test_the_baptism_row_itself_stays_on_the_page(mission):
    """Only the opening sentences lose it — the tablero's row keeps it."""
    model = _with_baptisms_at(mission, 999.0)
    assert BAPTIZED in {r.key for r in model.key_indicators}
    labels = {l.label for l in PK.tablero_lines(model, comparable=False,
                                                confident=False)}
    assert model.ki(BAPTIZED).label in labels


def test_a_mission_with_nothing_graded_names_neither(mission):
    blank = replace(mission, key_indicators=tuple(
        replace(r, grade=G.Grade()) for r in mission.key_indicators))
    assert PK._best_and_worst(blank) == (None, None)


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

def test_the_missions_sections_run_in_order_down_the_pages(models):
    """M1-M5 and the scores, in order — outcomes, then activity, then process.

    Scanned forward rather than searched: "Indicadores Clave" also appears in
    M1's own section note ("de los Indicadores Clave con una meta utilizable"),
    and "zonas" appears on the cover's contents. A plain substring search finds
    those first and reports the packet as out of order when it is not.

    Phase V stopped giving each section a page of its own — seven Key
    Indicators took a whole sheet and left two thirds of it blank — so this
    asserts the ORDER and no longer that consecutive heads land on
    consecutive pages.
    """
    import io

    from pypdf import PdfReader
    pdf = PK.build_packet(models, ROSTER, _data().nightly_goals)
    pages = [(p.extract_text() or "").upper()
             for p in PdfReader(io.BytesIO(pdf)).pages]
    # PLAN-2026-10-06 Phase 3: the tablero opens, then the zones and who
    # reported, the twelve weeks and the nights.
    heads = ["DÓNDE ESTAMOS", "EL TABLERO", "ZONAS", "QUIÉN INFORMÓ",
             "LAS ÚLTIMAS 12 SEMANAS", "TODO EL TRABAJO NOCTURNO"]
    at, found = 0, []
    for head in heads:
        at = next((i for i in range(at, len(pages)) if head in pages[i]), None)
        assert at is not None, f"{head} never appears after page {found[-1:]}"
        found.append(at)
    assert found == sorted(found)
    # And they now share pages: six sections inside four sheets, where before
    # Phase V there were six sheets with a section on each.
    assert found[-1] - found[0] < len(heads) - 1


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


# ── A3: the note under the grades no longer denies the section above it ─────

# ── A4: the nightly table says its two figures are not on the same footing ────

def _heads(flow):
    table = next(f for f in flow if isinstance(f, PP.Table))
    return table._cellvalues[0]


def test_the_nightly_heads_say_what_each_figure_is_measured_in(mission):
    heads = _heads(PK.nightly_page(mission, _data().nightly_goals))
    real, meta = heads[1], heads[2]
    # Both on one basis since AUDIT-2026-10-06 H4: "3.248 contra 44,8" was two
    # figures nobody could compare without dividing.
    assert real[0].label == "Real" and "área/sem" in real[1].text
    assert meta[0].label == "Meta" and "área/sem" in meta[1].text


def test_the_tablero_heads_name_whose_goal_each_column_is(mission):
    """Decision 44: META is leadership's, PROPIA the companionships'
    compromiso, printed beside it."""
    lines = PK.tablero_lines(mission, comparable=False, confident=False)
    new = next(l for l in lines if l.label == "Nuevas Personas")
    assert new.own == "180"
    text = " ".join(_notes(PK.tablero_block(mission), "note"))
    assert "Propia" in text and "compromiso" in text


def test_the_unit_lines_fit_their_columns():
    room = PP.METRIC_COLUMNS[1] - 2 * 3.5
    for _, sub in (PK.NIGHTLY_REAL_HEAD, PK.NIGHTLY_META_HEAD):
        assert PP.width_of(sub, PP.NOTE) <= room


# ── B5: leadership's goal says what it is, and rounds ──────────────────────────

def _period(key, today=date(2026, 9, 23)):
    from app.reports import periods as P
    cycles = [{"number": "2026-5", "start": date(2026, 7, 27),
               "end": date(2026, 9, 6), "weeks": 6},
              {"number": "2026-6", "start": date(2026, 9, 7),
               "end": date(2026, 10, 18), "weeks": 6}]
    return P.resolve(key, today, cycles)


def test_no_leadership_note_carries_a_decimal(mission):
    for line in PK.ki_lines(mission, comparable=False):
        if line.note.startswith("meta del traslado") or                 line.note.startswith("meta de traslado,"):
            assert "," not in line.note.split(":")[-1]


# ── B7: each column head says what its percentage is against ─────────────────

def test_the_verdict_head_says_whose_goal_it_is():
    table = PP.metric_table([], headers=PK._metric_headers(based=True))
    head = table._cellvalues[0][4]
    assert [h.label for h in head] == ["Contra su", "propia meta"]


def test_the_change_head_names_what_it_is_against():
    assert PK._metric_headers(based=True, against="2026-5")[-1] == (
        "Cambio", "vs 2026-5")
    # With no base the reason wins over the name (decision 38).
    assert PK._metric_headers(based=False, against="2026-5")[-1] == (
        PK.NO_BASE_HEAD)


def test_the_head_takes_the_short_name_and_leaves_the_qualifier_to_the_note(
        mission):
    from app.reports import periods as P
    comp = P.Comparison(P.Period(
        key="this_transfer", label="2026-5 (primeras 2 semanas)",
        start=date(2026, 7, 27), end=date(2026, 8, 9), weeks=(),
        full_end=date(2026, 8, 9), full_weeks=2), P.SAME_WEEKS_ELAPSED)
    assert PK._against_label(replace(mission, comparison=comp)) == "2026-5"
    assert PK._against_label(replace(mission, comparison=None)) == ""


@pytest.mark.parametrize("label", [
    "Semana anterior", "6 semanas anteriores", "2 semanas anteriores",
    "2026-5 (primeras 2 semanas)", "Mes anterior (primeros 23 días)", "2025",
])
def test_every_comparison_head_fits_on_one_line(mission, label):
    """A head that wraps to three lines costs four pages across the packet."""
    from app.reports import periods as P
    comp = P.Comparison(P.Period(
        key="last_week", label=label, start=date(2026, 9, 7),
        end=date(2026, 9, 13), weeks=(), full_end=date(2026, 9, 13),
        full_weeks=1), P.PREVIOUS)
    sub = PK._metric_headers(
        based=True, against=PK._against_label(replace(mission, comparison=comp)))[-1][1]
    assert PP.width_of(sub, PP.NOTE) <= PP.METRIC_COLUMNS[-1] - 2 * 3.5, sub


def _line_with_grade(mission, grade):
    row = replace(_row(mission, NEW), grade=grade)
    return PK.ki_lines(replace(mission, key_indicators=(row,)),
                       comparable=True, confident=True)[0]


def test_a_small_count_prints_in_units_with_its_direction_if_real(mission):
    """AUDIT-2026-10-06 H5 — "+260%" on five events becomes "+13"."""
    line = _line_with_grade(mission, G.Grade(change_pct=260.0,
                                             change_count=13.2))
    assert line.change == (1, "+13")
    quiet = _line_with_grade(mission, G.Grade(change_pct=-35.0,
                                              change_count=-3.8,
                                              change_clear=False))
    assert quiet.change == (0, "-4")


def test_a_percentage_inside_the_noise_prints_without_a_direction(mission):
    line = _line_with_grade(mission, G.Grade(change_pct=-12.0,
                                             change_clear=False))
    assert line.change == (0, "-12%")


def test_a_change_that_prints_as_zero_draws_no_direction(mission):
    assert _line_with_change(mission, comparable=True, confident=True,
                             pct=-0.3).change == (0, "0%")
    assert _line_with_change(mission, comparable=True, confident=True,
                             pct=0.6).change == (1, "+1%")


# ── B8: the reporting row is read, not skipped ────────────────────────────────

def _footer_strings(drawing):
    return [c for c in drawing.contents if hasattr(c, "text")]


def test_the_reporting_row_prints_at_body_weight_in_the_table_s_ink():
    weeks = [date(2026, 9, 13), date(2026, 9, 20)]
    d = PP.week_table(520, weeks, [("Nuevas", [211, 181], "392")],
                      footer=("Áreas que informaron, de 45", [36, 31], ""))
    footer = [s for s in _footer_strings(d)
              if s.text in ("Áreas que informaron, de 45", "36", "31")]
    assert len(footer) == 3
    assert all(s.fontSize == PP.CELL.size for s in footer)
    assert all(s.fillColor != PP.INK_3 for s in footer)


def test_without_week_columns_the_row_gives_the_weekly_range():
    """"Año": thirty-eight weeks, no columns — the row used to print its label
    over nothing."""
    weeks = [date(2026, 1, 4)] * (PP.WEEK_COLUMN_LIMIT + 2)
    d = PP.week_table(520, weeks, [("x", [1] * len(weeks), "9")],
                      footer=("Áreas que informaron, de 45",
                              [1] + [30] * (len(weeks) - 2) + [36], ""))
    texts = [s.text for s in _footer_strings(d)]
    assert "Áreas que informaron, de 45: entre 1 y 36 por semana" in texts


# ── C11: a unit's how-to-read lines are one line each, and its own facts darker

def _notes(flow, style):
    from reportlab.platypus import Paragraph
    return [f.text for f in flow if isinstance(f, Paragraph)
            and f.style.name == style]


def test_the_week_table_explains_itself_in_one_line_not_two(mission):
    notes = _notes(PK.trend_block(mission), "note")
    assert len(notes) == 1
    assert "sumas sin dividir" not in notes[0]


def test_no_how_to_read_note_runs_past_two_lines():
    """Measured in points at the content width, the note style's leading."""
    from reportlab.platypus import Paragraph
    st = PP.styles()
    for text in (PK.INDEX_NOTE_SHORT,):
        _, h = Paragraph(text, st["note"]).wrap(PP.CONTENT_WIDTH, 1000)
        assert h <= 2 * st["note"].leading, text


def test_the_mission_s_tablero_says_what_its_change_is_against(mission):
    """Below the mission the change column's head says it; the mission's
    tablero also prints the sentence, with the window's dates."""
    flow = PK.tablero_block(mission)
    assert PK._comparison_note(mission) in _notes(flow, "note")


# ── Reporting as a headline KPI (decision 60) ────────────────────────────────

def _with_leaders():
    roster = ROSTER.assign(Is_ZL=["TRUE", "", "TRUE"],
                           Companion1_Name=["Élder Uno", "", "Élder Tres"],
                           Companion2_Name=["Élder Dos", "", ""])
    return M.build_all(data=_data(roster=roster))


def test_the_reporting_headline_sits_above_the_tablero_on_mission_and_zone():
    from tests.test_packet_tableau import words
    built = _with_leaders()
    mission = built[0]
    norte = next(m for m in built if m.scope.name == "Norte")
    district = next(m for m in built if m.scope.level == "district")
    text = words(PK.tablero_block(mission))
    assert "50%" in text and "meta 95%" in text      # 3 of 6 reports
    assert "3 de 6 informes" in text
    assert "muy atrasado" in text
    assert "los líderes de cada zona" in text
    assert "Élder Uno y Élder Dos" in words(PK.tablero_block(norte))
    assert "meta 95%" not in words(PK.tablero_block(district))


def test_the_mission_s_reporting_list_names_each_zone_s_owners():
    from tests.test_packet_tableau import words
    text = words(PK.reporting_block(_with_leaders()[0]))
    assert "responsables: Élder Uno y Élder Dos" in text
    assert "responsables: Élder Tres" in text


def test_a_refused_comparison_prints_its_reason():
    """`Comparison` is falsy without a window; the note must still carry the
    reason it was refused (here: the month before the form began)."""
    from app.reports import periods as P
    mission = M.build_all(P.LAST_MONTH, data=_data())[0]
    note = PK._comparison_note(mission)
    assert note.startswith("Sin comparación: El formulario semanal empezó")
    assert "julio 2026" in note


def test_no_sentence_still_grades_on_the_weeks_that_reported():
    """PLAN-2026-10-13 1.5: decision 44's wording is gone from both
    renderers, and the rule they print instead is decision 59's."""
    from pathlib import Path
    from tests.test_packet_tableau import words
    built = M.build_all(data=_data())
    mission = built[0]
    text = " ".join([
        words(PK.how_to_read(mission, PK.sections_for(built))),
        words(PK.data_note(built)), words(PK.tablero_block(mission)),
        " ".join(row[1] for row in PK.COLUMN_GLOSSARY)])
    screen = Path("views/11_Informes.py").read_text(encoding="utf-8")
    for old in ("semanas y áreas que informaron", "informes que la tienen",
                "sobre las mismas semanas y"):
        assert old not in text and old not in screen
    assert "una semana sin informe cuenta como cero" in text.lower()


def test_a_partial_goal_names_its_area_weeks_on_the_tablero():
    """Decision 66 in print: REAL follows the graded area-weeks and the Meta
    head says how many of them there are."""
    from tests.test_packet_tableau import words
    goals = LEAD_GOALS[LEAD_GOALS["area"] != "B1"]
    mission = M.build_all(data=_data(transfer_goals=goals))[0]
    text = words(PK.tablero_block(mission))
    assert "4 de 6 sem.-área" in text
    assert "Real y meta cuentan las 4 de 6 semanas-área" in text
    row = mission.ki(NEW)
    line = next(l for l in PK.tablero_lines(mission, comparable=False,
                                            confident=False)
                if l.label == "Nuevas Personas")
    assert line.real == "30"                  # A1's 30; B1's 30 leaves REAL
    assert row.lead_actual == 30


def test_a_unit_that_filed_nothing_reads_sin_informes_not_sin_meta():
    """A2 filed no week: it has leadership's goal, so 'sin meta' would be a
    false statement about the goal when the truth is about the reports."""
    a2 = next(m for m in M.build_all(data=_data()) if m.scope.name == "A2")
    lines = PK.area_lines(a2)
    new = next(l for l in lines if l.label == "Nuevas Personas")
    assert new.verdict == "sin informes"
    assert new.goal == "40"
    assert new.value == "—"
