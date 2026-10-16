"""The gap to 527 and the bets — PLAN-2026-10-13 step 2.3 (C6, C8).

527 is fixed (decision 64): the packet shows the gap between the forecast and
527, and what each measured lever would close of it. It never suggests
recasting the goal, and reporting is not a baptism bet, because certified
baptisms do not depend on forms.
"""

from datetime import date

import pytest

from app.reports import focus as FC
from app.reports import forecast as F
from app.reports import packet as PK
from app.reports import scope as S
from tests.test_packet_tableau import models, words

TODAY = date(2026, 10, 16)          # 76 days to 31 Dec: 1,81 transfers
BY_MONTH = {f"2026-{m:02d}": 40 for m in range(1, 10)}       # 360 to Sep


def _year():
    return F.year_landing(BY_MONTH, 2026, goal=527)


def _pipeline(*, miss=0.4, over=10, backtests=12):
    rows = (("0-14 días", 100, 0.15), ("15-30", 60, 0.13), ("31-60", 150, 0.06),
            ("61-90", 100, 0.03), ("91-180", 400, 0.01), ("181-365", 300, 0.0))
    return F.Pipeline(open_dates=1110, expected=40, low=30, high=50,
                      by_bucket=rows, miss=miss, backtests=backtests, over=over)


def test_the_gap_is_527_less_the_landing():
    year = _year()                                 # lands at 480 every way
    gap = F.year_gap(year, None, (), TODAY)
    assert gap.low == pytest.approx(527 - year.high)
    assert gap.high == pytest.approx(527 - year.low)
    assert gap.bets == ()


def test_bet_a_carries_each_zone_s_lever_over_the_transfers_left():
    levers = (FC.Lever(name="Angol", leak="x", baptisms=(1.0, 3.0)),
              FC.Lever(name="Arauco", leak="y", baptisms=(0.5, 1.0)),
              FC.Lever(name="Camilo", leak="", baptisms=None))
    gap = F.year_gap(_year(), None, levers, TODAY)
    (bet,) = gap.bets
    transfers = 76 / 7 / 6
    assert bet.low == pytest.approx(1.5 * transfers)
    assert bet.high == pytest.approx(4.0 * transfers)
    assert "2 zonas" in bet.how and "1,8 traslados" in bet.how


def test_bet_b_moves_the_old_dates_to_the_young_rate():
    """400 dates at 1% that converted like the 31-60-day ones (6%): 20 more
    in six weeks. The fit ran high in 10 of 12, so the range runs down from
    20 by the 40% miss: 12-20."""
    (bet,) = F.year_gap(_year(), _pipeline(), (), TODAY).bets
    assert bet.high == pytest.approx(20)
    assert bet.low == pytest.approx(12)
    assert "400 fechas" in bet.how


def test_bet_b_is_symmetric_when_the_fit_has_not_run_high():
    (bet,) = F.year_gap(_year(), _pipeline(over=6), (), TODAY).bets
    assert (bet.low, bet.high) == (pytest.approx(12), pytest.approx(28))


def test_no_year_or_no_goal_is_no_gap():
    assert F.year_gap(None, _pipeline(), (), TODAY) is None
    no_goal = F.year_landing(BY_MONTH, 2026, goal=None)
    assert F.year_gap(no_goal, _pipeline(), (), TODAY) is None


def test_the_line_sizes_the_bets_against_the_gap():
    gap = F.YearGap(goal=527, low=59, high=82,
                    bets=(F.Bet("a", 10, 38), F.Bet("b", 11, 20)))
    assert PK.gap_line(gap) == ("Las palancas medidas suman 21-58 de los "
                                "59-82 que faltan para 527.")
    ahead = F.YearGap(goal=527, low=0, high=0, bets=(F.Bet("a", 1, 2),))
    assert "ya llega a 527" in PK.gap_line(ahead)


def test_no_sentence_suggests_moving_527_or_reporting_as_a_bet():
    built, _ = models()
    mission = next(m for m in built if m.scope.level == S.MISSION)
    text = words(PK.gap_block(mission)).lower()
    assert "lo que falta para 527" in text
    for phrase in ("recalibr", "ajustar la meta", "cambiar la meta",
                   "bajar la meta", "revisar la meta", "otra meta"):
        assert phrase not in text
    assert "informar no es una palanca" in text
    labels = [b.label.lower() for b in mission.forward.gap.bets]
    assert not any("inform" in label for label in labels)


def test_only_the_mission_has_a_gap():
    built, _ = models()
    zone = next(m for m in built if m.scope.level == S.ZONE)
    assert zone.forward.gap is None
    assert PK.gap_block(zone) == []
