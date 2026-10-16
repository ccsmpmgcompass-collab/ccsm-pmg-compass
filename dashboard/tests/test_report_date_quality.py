"""What a date is worth — PLAN-2026-10-13 step 3.1 (C4, decision 65).

The mission page prints the open dates' ages now against a year ago and what
the same months' dates became, 2025 against 2026; each zone its share of
dates older than 90 days; each district a count per area to review or
release (counts only, never names). The 2026 jump is printed once, with both
readings, and names no cause (Q-J).
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from app.reports import forecast as F
from app.reports import packet as PK
from app.reports import scope as S
from tests.test_packet_tableau import models, words


def _dates(values):
    return pd.Series(pd.to_datetime(list(values)))


def test_the_cohort_window_is_the_last_whole_months_with_their_six_weeks():
    assert F.cohort_window(date(2026, 10, 16)) == (date(2026, 6, 1),
                                                  date(2026, 8, 31))
    # 42 days before 12 Oct is 31 Aug, a month-end: August counts.
    assert F.cohort_window(date(2026, 10, 12)) == (date(2026, 6, 1),
                                                  date(2026, 8, 31))
    assert F.cohort_window(date(2026, 10, 11)) == (date(2026, 5, 1),
                                                  date(2026, 7, 31))
    # Across the year boundary.
    assert F.cohort_window(date(2027, 2, 20)) == (date(2026, 10, 1),
                                                 date(2026, 12, 31))


def test_date_quality_counts_ages_and_the_same_months_a_year_apart():
    asof = date(2026, 10, 16)
    rows = [
        # (found, set, confirmed, attended church)
        # 2025 cohort (Jun-Aug): two dates, one baptised in six weeks, both
        # after church, one set a week after being found.
        ("2025-06-01", "2025-06-05", "2025-06-30", "2025-06-02"),
        ("2025-05-01", "2025-07-10", None, "2025-07-01"),
        # 2026 cohort: four dates, none baptised within six weeks (one at
        # day 50), all set within a week of being found, one after church.
        ("2026-06-01", "2026-06-03", "2026-07-23", None),
        ("2026-07-01", "2026-07-02", None, "2026-07-01"),
        ("2026-08-01", "2026-08-01", None, None),
        ("2026-08-10", "2026-08-12", None, "2026-08-20"),
        # Open today, fresh: set 10 days ago.
        ("2026-10-01", "2026-10-06", None, None),
    ]
    found, set_d, conf, attend = (_dates(c) for c in zip(*rows))
    by_month = {f"{y}-{m:02d}": 10 for y in (2025, 2026) for m in range(1, 13)}
    by_month["2026-07"] = 13
    q = F.date_quality(found, set_d, conf, attend, asof, by_month=by_month)
    before, now = q.cohorts
    assert (before.start, before.end) == (date(2025, 6, 1), date(2025, 8, 31))
    assert (before.dates, before.baptized, before.quick,
            before.after_church) == (2, 1, 1, 2)
    assert (now.dates, now.baptized, now.quick, now.after_church) == (4, 0, 4, 1)
    assert q.set == (2, 4)
    assert q.found == (1, 4)
    assert q.certified == (30, 33)
    # Today: the 2026 cohort's three unbaptised dates plus the fresh one are
    # open; only 2 Jul (106 days) is over 90 — 1 Aug is 76, 12 Aug 65.
    assert (q.now.open, q.now.old, q.now.fresh) == (4, 1, 1)
    # A year ago: only 10 Jul 2025 was open (98 days old).
    assert (q.before.open, q.before.old) == (1, 1)
    assert F.DateQuality.ratio(q.set) == 2


def test_a_month_without_a_certified_figure_prints_no_baptism_change():
    q = F.date_quality(_dates(["2026-06-01"]), _dates(["2026-06-02"]),
                       _dates([None]), _dates([None]), date(2026, 10, 16),
                       by_month={"2026-06": 5})
    assert q.certified == ()
    assert "bautizó" not in PK.dates_sentence(
        F.DateQuality(now=q.now, before=q.before,
                      cohorts=(F.DateCohort(date(2025, 6, 1),
                                            date(2025, 8, 31), 10, 4, 2, 7),
                               F.DateCohort(date(2026, 6, 1),
                                            date(2026, 8, 31), 30, 4, 15, 10)),
                      found=(100, 190), set=(10, 30)))


def test_stale_by_area_counts_the_old_open_dates_per_area_only():
    asof = date(2026, 10, 16)
    names = pd.Series(["A", "A", "A", "B", "C"])
    set_d = _dates(["2026-05-01", "2026-09-30", "2026-05-02", "2026-06-01",
                    "2025-06-01"])
    conf = _dates([None, None, "2026-06-01", None, None])
    # A: one old open, one fresh, one baptised; B: one old; C: over a year,
    # so not open at all.
    assert F.stale_by_area(names, set_d, conf, asof, ["A", "B", "C"]) == (
        ("A", 1), ("B", 1), ("C", 0))


def test_the_pipeline_says_its_share_of_old_dates():
    rows = (("0-14 días", 10, 0.1), ("15-30", 10, 0.1), ("31-60", 10, 0.1),
            ("61-90", 10, 0.1), ("91-180", 40, 0.0), ("181-365", 20, 0.0))
    pl = F.Pipeline(open_dates=100, expected=4, low=2, high=6, by_bucket=rows)
    assert pl.old == 60
    assert pl.old_share == pytest.approx(0.6)


@pytest.mark.parametrize("ratio, words_", [
    (1.88, "casi el doble de personas"), (2.0, "el doble de personas"),
    (2.6, "más del doble de personas"), (3.48, "más del triple de personas"),
    (1.4, "un 40% más de personas"), (0.8, "un 20% menos de personas")])
def test_times_in_words(ratio, words_):
    assert PK._times_of(ratio, "personas") == words_


def test_shares_in_words():
    assert PK._share_of(0.516, "fechas") == "la mitad de las fechas"
    assert PK._share_of(0.68) == "dos de cada tres"
    assert PK._share_of(0.41, "fechas") == "4 de cada 10 fechas"


LIVE = F.DateQuality(
    now=F.DateAges(date(2026, 10, 16), 1247, 815, 183),
    before=F.DateAges(date(2025, 10, 16), 451, 322, 55),
    cohorts=(F.DateCohort(date(2025, 6, 1), date(2025, 8, 31), 158, 37, 36, 116),
             F.DateCohort(date(2026, 6, 1), date(2026, 8, 31), 550, 74, 284,
                          176)),
    found=(7591, 14271), set=(158, 550), certified=(100, 110))


def test_the_sentence_carries_both_readings_in_phase_0_s_words():
    line = PK.dates_sentence(LIVE)
    assert line.startswith("Entre junio y agosto de 2026 la misión encontró "
                           "casi el doble de personas, fijó más del triple de "
                           "fechas y bautizó un 10% más que en los mismos "
                           "meses de 2025.")
    assert "Parte del salto puede ser cómo se registra" in line
    assert ("13 de cada 100 terminaron en bautismo dentro de seis semanas; en "
            "2025, 23.") in line
    assert "la mitad de las fechas se fijó en la primera semana" in line
    assert "dos de cada tres antes de que asistiera a la Iglesia" in line


def test_the_sentence_names_no_cause():
    line = PK.dates_sentence(LIVE).lower()
    for cause in ("porque", "debido", "causa", "instrucci", "capacitaci",
                  "cambio de pol", "por orden"):
        assert cause not in line


def test_only_the_mission_prints_the_dates_block():
    built, _ = models()
    mission = next(m for m in built if m.scope.level == S.MISSION)
    zone = next(m for m in built if m.scope.level == S.ZONE)
    assert mission.forward.dates is not None
    assert zone.forward.dates is None
    assert PK.dates_block(zone) == []
    text = words(PK.dates_block(mission))
    assert "Fechas: cuántas, qué edad, cuántas llegan" in text
    assert "no su causa" in text


def test_a_district_line_counts_per_area_and_names_no_one():
    built, _ = models()
    district = next(m for m in built if m.scope.level == S.DISTRICT)
    assert [a for a, _ in district.forward.stale] == sorted(district.scope.areas)
    line = PK.stale_sentence(district)
    assert line.startswith("revisar o liberar")
    # The fixture's people carry no names; the line is areas and counts.
    for area, n in district.forward.stale:
        if n:
            assert f"{area}: {n}" in line
