"""get_weekly_form_data() must actually parse CCSM's weekly form.

It did not. The parser searched for "What is your Area?", "What is your Zone?",
"What week" and the (Pew)/(Date)/(Gate)/(Renew)/(Total) metric suffixes — Utah
Provo's English form, inherited with the fork. Against CCSM's live Spanish
header EVERY one of those patterns matches ZERO of the 182 columns, so section
detection found nothing and the function returned an empty DataFrame on every
call. Everything downstream — dashboard KI cards, KI trends, zone comparisons,
projections, Goals actuals — was blank BY CONSTRUCTION, not for want of data.

That is invisible before Aug 5, because an empty frame is also the correct
answer when no one has submitted yet. It would have stayed invisible after
Aug 5 too: real submissions would have landed and the dashboard would have kept
showing nothing, looking like a reporting problem rather than a parser bug.

The header row here is the REAL one, from the live snapshot, so these tests
cannot pass against a form CCSM does not have.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

import app.db.queries as q
from app.config import metric_catalog as mc

LIVE = (Path(__file__).resolve().parent.parent.parent
        / "tests" / "live" / "live_form_headers.json")


def _live():
    if not LIVE.exists():
        pytest.skip(f"live snapshot missing: {LIVE}")
    return json.loads(LIVE.read_text(encoding="utf-8").lstrip("﻿"))


def _dedup(headers):
    """Reproduce read_tab()'s duplicate-header renaming (name, name_1, …).
    Without this the fixture would be an easier problem than production."""
    seen, out = {}, []
    for h in headers:
        h = str(h).strip() or "_blank"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
        out.append(h)
    return out


@pytest.fixture
def live_tabs():
    return _live()


@pytest.fixture(autouse=True)
def _clear():
    mc.clear_cache()
    yield
    mc.clear_cache()


def _install(monkeypatch, weekly_grid, questions_grid):
    weekly_cols = _dedup(weekly_grid[0])
    weekly_df = pd.DataFrame(weekly_grid[1:], columns=weekly_cols)

    q_cols = [str(c).strip() for c in questions_grid[0]]
    questions_df = pd.DataFrame(questions_grid[1:], columns=q_cols)

    def fake(tab_name, header_marker=None):
        if tab_name == "WEEKLY_FORM_RAW":
            return weekly_df.copy()
        if tab_name == "QUESTIONS_CONFIG":
            return questions_df.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    for fn in (q.get_weekly_form_data, q.get_weekly_submission_data):
        fn.clear()


# ── 1. The header constants still match the live form ─────────────────────────

def test_structural_headers_match_the_live_weekly_form(live_tabs):
    """These two are hardcoded (they are structural questions with no
    QUESTIONS_CONFIG row) and mirror A3_FORM_AREA_COL / A3_FORM_ZONE_COL in
    CCSM_Agent3.gs. If the form is ever reworded, this is what catches it."""
    header = [str(c) for c in live_tabs["WEEKLY_FORM_RAW"][0]]
    assert sum(1 for c in header if c.startswith(q._FORM_AREA_COL)) == 10, \
        f"expected 10 zone sections keyed on {q._FORM_AREA_COL!r}"
    assert sum(1 for c in header if c.startswith(q._FORM_ZONE_COL)) == 1, \
        f"expected exactly one global zone column {q._FORM_ZONE_COL!r}"


def test_the_old_provo_patterns_match_nothing(live_tabs):
    """Documents why this rewrite was necessary, and would fail loudly if
    someone reinstated the Provo parser."""
    header = " | ".join(str(c) for c in live_tabs["WEEKLY_FORM_RAW"][0])
    for pat in ("What is your Area?", "What is your Zone?", "What week",
                "(Pew)", "(Date)", "(Gate)", "(Renew)", "(Total)"):
        assert pat not in header, f"unexpected Provo pattern in the live form: {pat}"


def test_layout_finds_ten_sections_in_the_live_header(live_tabs):
    cols = _dedup(live_tabs["WEEKLY_FORM_RAW"][0])
    layout = q._weekly_form_layout(cols)
    assert len(layout["sections"]) == 10
    assert layout["zone_col"] is not None
    assert layout["ts_col"] is not None
    # Sections must tile the header without overlapping.
    for (s, e) in layout["sections"]:
        assert s < e
    ends = [e for _, e in layout["sections"]]
    starts = [s for s, _ in layout["sections"]]
    assert ends[:-1] == starts[1:], "sections must be contiguous"


# ── 2. A real submission round-trips ──────────────────────────────────────────

def test_a_submission_in_the_last_zone_parses(monkeypatch, live_tabs):
    """The last section is the case that fails if the offset arithmetic is
    wrong — section 0 would pass even then, since its start index is 0."""
    weekly_grid = [list(live_tabs["WEEKLY_FORM_RAW"][0])]
    cols = _dedup(weekly_grid[0])
    layout = q._weekly_form_layout(cols)
    start, end = layout["sections"][-1]

    row = [""] * len(cols)
    row[0] = "2026-08-10 20:00:00"
    row[cols.index(layout["zone_col"])] = "Villarrica"
    row[start] = "Villarrica 1"

    # Fill the section's own date + each weekly metric with a distinct value,
    # so a wrong offset lands on the wrong key and fails loudly.
    qgrid = live_tabs["QUESTIONS_CONFIG"]
    qh = [str(c).strip() for c in qgrid[0]]
    hi, ki, fi = (qh.index("Form_Column_Header"), qh.index("Metric_Key"),
                  qh.index("Form_Type"))
    weekly_defs = [(str(r[hi]).strip(), str(r[ki]).strip())
                   for r in qgrid[1:] if str(r[fi]).strip().upper() == "WEEKLY"]

    expected = {}
    n = 0
    for header, key in weekly_defs:
        for j in range(start, end):
            if cols[j].startswith(header):
                if key == "report_date":
                    row[j] = "2026-08-09"      # a Sunday
                else:
                    n += 1
                    row[j] = n
                    expected[key] = float(n)
                break

    weekly_grid.append(row)
    _install(monkeypatch, weekly_grid, qgrid)

    out = q.get_weekly_form_data()
    assert not out.empty, "a real last-zone submission produced no rows"
    assert len(out) == 1, f"expected exactly one tidy row, got {len(out)}"

    rec = out.iloc[0]
    assert rec["area"] == "Villarrica 1"
    assert rec["zone"] == "Villarrica"
    assert rec["week_end_date"] == "2026-08-09"

    for key, want in expected.items():
        assert key in out.columns, f"{key} missing from the parsed frame"
        assert float(rec[key]) == want, \
            f"{key} parsed as {rec[key]}, expected {want} — section offsets are wrong"


def test_real_and_meta_are_both_kept_and_distinct(monkeypatch, live_tabs):
    """`_real` is what the companionship achieved; `_meta` is the goal they set.
    Collapsing or summing them would report a mission as having done its targets."""
    weekly_grid = [list(live_tabs["WEEKLY_FORM_RAW"][0])]
    cols = _dedup(weekly_grid[0])
    layout = q._weekly_form_layout(cols)
    start, end = layout["sections"][0]

    row = [""] * len(cols)
    row[0] = "2026-08-10 20:00:00"
    row[cols.index(layout["zone_col"])] = "Arauco"
    row[start] = "Arauco 1"
    for j in range(start, end):
        if cols[j].startswith("¿Qué fecha está ingresando?"):
            row[j] = "2026-08-09"
        elif "(Real)" in cols[j]:
            row[j] = 3
        elif "(Meta)" in cols[j]:
            row[j] = 9

    weekly_grid.append(row)
    _install(monkeypatch, weekly_grid, live_tabs["QUESTIONS_CONFIG"])

    out = q.get_weekly_form_data()
    assert not out.empty
    rec = out.iloc[0]
    reals = [c for c in out.columns if c.endswith("_real")]
    metas = [c for c in out.columns if c.endswith("_meta")]
    assert len(reals) == 7 and len(metas) == 7, (reals, metas)
    assert all(float(rec[c]) == 3.0 for c in reals), "achieved values were lost"
    assert all(float(rec[c]) == 9.0 for c in metas), "goal values were lost"


def test_blank_sections_do_not_become_rows(monkeypatch, live_tabs):
    """A missionary fills ONE zone's section; the other nine are blank. If those
    produced rows, every submission would become ten, and every mission total
    would be inflated tenfold."""
    weekly_grid = [list(live_tabs["WEEKLY_FORM_RAW"][0])]
    cols = _dedup(weekly_grid[0])
    layout = q._weekly_form_layout(cols)
    start, end = layout["sections"][3]

    row = [""] * len(cols)
    row[0] = "2026-08-10 20:00:00"
    row[cols.index(layout["zone_col"])] = "Concepción"
    row[start] = "Un Área"
    for j in range(start, end):
        if cols[j].startswith("¿Qué fecha está ingresando?"):
            row[j] = "2026-08-09"

    weekly_grid.append(row)
    _install(monkeypatch, weekly_grid, live_tabs["QUESTIONS_CONFIG"])

    out = q.get_weekly_form_data()
    assert len(out) == 1, f"one submission became {len(out)} rows"


def test_totals_sum_the_real_columns(monkeypatch, live_tabs):
    """get_weekly_ki_totals used a hardcoded Provo column list and would
    KeyError against CCSM's frame as soon as the parser returned real rows."""
    weekly_grid = [list(live_tabs["WEEKLY_FORM_RAW"][0])]
    cols = _dedup(weekly_grid[0])
    layout = q._weekly_form_layout(cols)

    for idx, (start, end) in enumerate(layout["sections"][:3]):
        row = [""] * len(cols)
        row[0] = "2026-08-10 20:00:00"
        row[cols.index(layout["zone_col"])] = f"Zona{idx}"
        row[start] = f"Area{idx}"
        for j in range(start, end):
            if cols[j].startswith("¿Qué fecha está ingresando?"):
                row[j] = "2026-08-09"
            elif "(Real)" in cols[j]:
                row[j] = 2
        weekly_grid.append(row)

    _install(monkeypatch, weekly_grid, live_tabs["QUESTIONS_CONFIG"])
    q.get_weekly_ki_totals.clear() if hasattr(q.get_weekly_ki_totals, "clear") else None

    totals = q.get_weekly_ki_totals(n_weeks=4)
    assert not totals.empty, "totals came back empty for three real submissions"
    assert float(totals.iloc[-1]["ki_new_people_real"]) == 6.0, \
        "three areas reporting 2 each must total 6"


def test_projection_routes_weekly_metrics_to_the_weekly_source():
    """A weekly metric projected off the NIGHTLY series would produce a
    confident-looking projection of a column that does not exist there."""
    weekly = q._weekly_form_metric_keys()
    assert "ki_new_people_real" in weekly
    assert "contacts_attempted" not in weekly, \
        "a nightly metric must not route to the weekly-form source"
