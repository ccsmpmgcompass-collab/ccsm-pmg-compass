"""The weekly KI PDFs and the outbox handshake (PLAN-2026-10-10-ki-autosend.md).

A small synthetic sheet: two zones, three sectors, the live form's layout (one
area/date/7 Real/7 Meta section per zone, headers matched by text).
"""
from datetime import date, datetime

import pytest

from app.ingestion import ki_pdf_runner as R
from app.reports import ki_ranking as KR

KI = ["Nuevas personas encontradas", "Lecciones con miembros",
      "Amigos en la reunión sacramental",
      "Amigos en la Iglesia durante su primera semana de enseñanza",
      "Amigos con fecha bautismal", "Bautizados y confirmados",
      "Conversos recientes en la Iglesia"]
SECTION = (["¿En qué área sirve?", "¿Qué fecha está ingresando?"]
           + [f"{k} (Real)" for k in KI] + [f"{k} (Meta)" for k in KI])


def questions():
    rows = [["Question_ID", "Form_Type", "Form_Column_Header", "Metric_Key"]]
    for key, text in zip(KR.KEYS, KI):
        rows.append(["", "WEEKLY", f"{text} (Real)", f"{key}_real"])
        rows.append(["", "WEEKLY", f"{text} (Meta)", f"{key}_meta"])
    return rows


def form_row(ts, zone, section, area, day, real, meta):
    row = [ts, zone] + [""] * (2 * len(SECTION))
    start = 2 + section * len(SECTION)
    row[start:start + len(SECTION)] = [area, day] + [str(real)] * 7 + [str(meta)] * 7
    return row


def raw(extra=()):
    head = ["Timestamp", "¿En qué zona sirve?"] + SECTION + SECTION
    rows = [head]
    for area, zone, sec in (("Alfa 1", "Norte", 0), ("Alfa 2", "Norte", 0),
                            ("Beta 1", "Sur", 1)):
        # The Sunday forms of 20 Sep (goals) and 27 Sep; Alfa 1 alone filed 4 Oct.
        rows.append(form_row("9/20/2026 20:00:00", zone, sec, area, "9/20/2026", 1, 4))
        rows.append(form_row("9/27/2026 20:00:00", zone, sec, area, "9/27/2026", 3, 4))
    rows.append(form_row("10/4/2026 20:00:00", "Norte", 0, "Alfa 1", "10/4/2026", 4, 5))
    rows.extend(extra)
    org = [["Area_Name", "Zone", "District", "Active"],
           ["Alfa 1", "Norte", "D1", "TRUE"], ["Alfa 2", "Norte", "D1", "TRUE"],
           ["Beta 1", "Sur", "D2", "TRUE"]]
    return {"WEEKLY_FORM_RAW": rows, "MISSION_ORG": org, "QUESTIONS_CONFIG": questions()}


W2 = date(2026, 10, 4)


def reported(model, area):
    return next(s for s in model["sectors"] if s.name == area).f2


def test_cutoff_leaves_out_later_forms():
    late = form_row("10/5/2026 21:40:00", "Norte", 0, "Alfa 2", "10/4/2026", 2, 3)
    m = KR.build_model(raw([late]), W2, cutoff=datetime(2026, 10, 5, 21, 30))
    assert reported(m, "Alfa 1") == 1
    assert reported(m, "Alfa 2") == 0          # sent after the letter read the forms
    m = KR.build_model(raw([late]), W2)
    assert reported(m, "Alfa 2") == 1


def test_a_form_dated_after_the_week_counts_as_the_week():
    slip = form_row("10/5/2026 09:00:00", "Sur", 1, "Beta 1", "10/11/2026", 2, 3)
    m = KR.build_model(raw([slip]), W2)
    assert reported(m, "Beta 1") == 1


def test_documents_mission_first_then_each_zone():
    docs = KR.build_documents(raw(), W2, stamp="2026-10-05 21:30")
    assert [d["scope"] for d in docs][0] == "MISSION"
    assert sorted(d["scope"] for d in docs[1:]) == ["Norte", "Sur"]
    assert docs[0]["file_name"] == "Indicadores_clave_mision_28sep-4oct.pdf"
    assert {d["file_name"] for d in docs[1:]} == {
        "Indicadores_clave_Norte_28sep-4oct.pdf", "Indicadores_clave_Sur_28sep-4oct.pdf"}
    # Cover + the mission pair + each zone's pair; a zone's own: cover + its pair.
    assert docs[0]["pages"] == 1 + 2 + 2 * 2
    assert all(d["pages"] == 3 for d in docs[1:])
    assert all(d["pdf"].startswith(b"%PDF") for d in docs)


def test_last_sunday_matches_agent1a():
    assert R.last_sunday(date(2026, 10, 5)) == W2      # Monday -> yesterday
    assert R.last_sunday(date(2026, 10, 4)) == W2      # Sunday -> today
    assert R.last_sunday(date(2026, 10, 10)) == W2     # Saturday


def test_request_row_is_found_by_week():
    grid = [R.OUTBOX_HEADER, ["REQUEST", "2026-10-04", "", "", "2026-10-05 21:31:07"]]
    assert R.find_request(grid, W2) == datetime(2026, 10, 5, 21, 31, 7)
    assert R.find_request(grid, date(2026, 9, 27)) is None
    assert R.find_request([R.OUTBOX_HEADER], W2) is None


def test_pdf_rows_round_trip_and_stay_under_the_cell_limit():
    big = {"scope": "MISSION", "file_name": "x.pdf", "pages": 11,
           "pdf": b"%PDF" + bytes(range(256)) * 400}        # ~100 KB -> 3 cells
    rows = R.pdf_rows([big], W2, "2026-10-05 21:31:07")
    assert int(rows[0][6]) == len(rows[0]) - 7 >= 3
    assert all(len(part) <= R.PART_CHARS for part in rows[0][7:])
    assert R.decode(rows[0]) == big["pdf"]


def test_outbox_keeps_this_weeks_request_and_drops_old_weeks():
    old = [R.OUTBOX_HEADER,
           ["REQUEST", "2026-09-27", "", "", "2026-09-28 21:30:00"],
           ["PDF", "2026-09-27", "MISSION", "old.pdf", "2026-09-28 21:30:00", "11", "1", "AAAA"],
           ["REQUEST", "2026-10-04", "", "", "2026-10-05 21:31:07"]]
    new = R.pdf_rows([{"scope": "Norte", "file_name": "n.pdf", "pages": 3, "pdf": b"%PDF-1"}],
                     W2, "2026-10-05 21:31:07")
    grid = R.outbox_grid(old, W2, new)
    assert [r[0] for r in grid[1:]] == ["REQUEST", "PDF"]
    assert grid[1][1] == grid[2][1] == "2026-10-04"
    assert grid[0][:7] == R.OUTBOX_HEADER and grid[0][7] == "Part_1"
    assert R.already_built(grid, W2, "2026-10-05 21:31:07")
    assert not R.already_built(grid, W2, "2026-10-05 22:00:00")


def test_no_streamlit_on_the_job_path():
    import subprocess
    import sys
    code = ("import sys; sys.modules['streamlit'] = None\n"
            "import app.reports.ki_ranking, app.ingestion.ki_pdf_runner\n"
            "app.ingestion.ki_pdf_runner._sheet_io()\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
