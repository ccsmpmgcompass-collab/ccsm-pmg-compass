"""Which transfer are we in — app/utils/transfer_helpers.py.

Step 5 of the Desgloses plan, unblocked on 2026-09-03 when TRANSFER_SCHEDULE
was filled in with the mission's real cycles: 2026-06-15 and 2026-07-27 as
`Actual`, and 2026-09-07 as `Scheduled`. Before that the tab held a header row
and nothing else, and every "this transfer" on the dashboard rested on a
six-week guess from AGENT_CONFIG's TRANSFER_START_DATE.

The rule this module exists to hold, and the one most likely to be "simplified"
back out: **Status does not decide which transfer is current.** The current
transfer is the latest row whose start date has arrived, whatever its Status
says. That is what makes the 2026-09-07 row take over by itself on 2026-09-07
instead of waiting for a human to flip "Scheduled" to "Actual" — a step nobody
would remember and whose omission would silently pin the whole dashboard to the
previous cycle. Status still matters elsewhere (the area-lineage badge, and
CCSM_Agent2.gs's goal recalibration), which is exactly why it is tempting to
reuse it here and exactly why these tests are explicit about it.

The sheet is stubbed throughout: these are tests of the rule, not of the tab's
current contents.
"""

from datetime import date

import pandas as pd
import pytest

from app.utils import transfer_helpers as th

# The live schedule as written on 2026-09-03.
_LIVE = [
    ("2026-4", "2026-06-15", "6", "Actual"),
    ("2026-5", "2026-07-27", "6", "Actual"),
    ("2026-6", "2026-09-07", "6", "Scheduled"),
]


def _stub(monkeypatch, rows, config_start=""):
    """Point the helper at `rows` instead of the live tab."""
    frame = pd.DataFrame(
        [{"Transfer_Number": n, "Start_Date": s, "Weeks": w, "Status": st}
         for n, s, w, st in rows],
        columns=["Transfer_Number", "Start_Date", "Weeks", "Status"])
    import app.db.sheets_client as sc
    import app.db.queries as q
    monkeypatch.setattr(sc, "read_tab", lambda *a, **k: frame)
    monkeypatch.setattr(q, "get_config_value", lambda k, d="": config_start)


@pytest.fixture
def live(monkeypatch):
    _stub(monkeypatch, _LIVE)


# ── Which cycle is current ───────────────────────────────────────────────────

def test_the_current_transfer_is_the_latest_one_that_has_started(live):
    win = th.transfer_window(0, date(2026, 9, 3))
    assert (win["start"], win["end"]) == (date(2026, 7, 27), date(2026, 9, 6))
    assert win["number"] == "2026-5"


def test_a_scheduled_row_takes_over_on_its_own_start_date(live):
    """The rule with teeth. On 7 September the 2026-6 row is still marked
    "Scheduled" — nobody has flipped it — and it is nonetheless the current
    transfer, because its start date has arrived. Gating on Status would pin
    the entire dashboard to the previous cycle until someone edited the tab."""
    win = th.transfer_window(0, date(2026, 9, 7))
    assert win["number"] == "2026-6"
    assert win["status"] == "Scheduled"
    assert win["start"] == date(2026, 9, 7)


def test_the_day_before_a_cycle_starts_still_belongs_to_the_old_one(live):
    assert th.transfer_window(0, date(2026, 9, 6))["number"] == "2026-5"


def test_offset_one_is_the_previous_cycle(live):
    win = th.transfer_window(1, date(2026, 9, 3))
    assert (win["start"], win["end"]) == (date(2026, 6, 15), date(2026, 7, 26))


def test_reaching_further_back_than_the_schedule_returns_none(live):
    """The schedule starts at 2026-06-15. There is no cycle before it, and
    subtracting six weeks from that date would invent one."""
    assert th.transfer_window(2, date(2026, 9, 3)) is None


def test_a_date_before_the_whole_schedule_has_no_current_transfer(live):
    assert th.transfer_window(0, date(2026, 5, 1)) is None


# ── A cycle ends where the next one begins ───────────────────────────────────

def test_a_cycle_ends_the_day_before_the_next_one_starts(live):
    """Not `start + weeks`. If the mission ever runs a short or long cycle, the
    schedule records it by where the NEXT row begins, and describing it as six
    weeks anyway would overlap two transfers or leave a gap between them."""
    assert th.transfer_window(1, date(2026, 9, 3))["end"] == date(2026, 7, 26)


def test_a_short_cycle_is_described_as_it_really_was(monkeypatch):
    _stub(monkeypatch, [("A", "2026-06-15", "6", "Actual"),
                        ("B", "2026-07-13", "6", "Actual")])   # only 4 weeks
    win = th.transfer_window(1, date(2026, 8, 1))
    assert win["end"] == date(2026, 7, 12)
    assert (win["end"] - win["start"]).days + 1 == 28


def test_the_last_row_falls_back_to_its_own_week_count(monkeypatch):
    """Nothing follows it to bound it, so its Weeks column is all there is."""
    _stub(monkeypatch, [("A", "2026-07-27", "6", "Actual")])
    assert th.transfer_window(0, date(2026, 8, 1))["end"] == date(2026, 9, 6)


# ── Falling back when the schedule cannot answer ─────────────────────────────

def test_an_empty_schedule_falls_back_to_agent_config(monkeypatch):
    """The state this mission was in until 2026-09-03, and the state a new
    mission starts in."""
    _stub(monkeypatch, [], config_start="2026-08-09")
    win = th.transfer_window(0, date(2026, 9, 3))
    assert win["start"] == date(2026, 8, 9)
    assert win["source"] == "config"


def test_the_fallback_says_it_is_a_fallback(monkeypatch):
    """`source` is what lets the Traslados page tell the reader the window is
    an assumption rather than a record."""
    _stub(monkeypatch, _LIVE)
    assert th.transfer_window(0, date(2026, 9, 3))["source"] == "schedule"


def test_no_schedule_and_no_config_is_no_window(monkeypatch):
    _stub(monkeypatch, [], config_start="")
    assert th.transfer_window(0, date(2026, 9, 3)) is None


def test_the_fallback_has_no_previous_cycle(monkeypatch):
    """One synthetic row cannot answer "the transfer before this one", and
    guessing six weeks back from a placeholder would be a fact-shaped guess."""
    _stub(monkeypatch, [], config_start="2026-08-09")
    assert th.transfer_window(1, date(2026, 9, 3)) is None


# ── Rows that cannot be placed on a calendar ─────────────────────────────────

def test_an_unparseable_start_date_is_dropped(monkeypatch):
    _stub(monkeypatch, [("A", "not a date", "6", "Actual"),
                        ("B", "2026-07-27", "6", "Actual")])
    assert len(th.transfer_rows()) == 1


def test_a_missing_week_count_defaults_to_six(monkeypatch):
    _stub(monkeypatch, [("A", "2026-07-27", "", "Actual")])
    assert th.transfer_rows()[0]["weeks"] == th.DEFAULT_WEEKS


def test_rows_come_back_oldest_first_whatever_order_the_tab_holds(monkeypatch):
    _stub(monkeypatch, [("B", "2026-07-27", "6", "Actual"),
                        ("A", "2026-06-15", "6", "Actual")])
    assert [r["number"] for r in th.transfer_rows()] == ["A", "B"]


# ── The two windows the period pickers offer ─────────────────────────────────

def test_this_transfer_so_far_ends_today_not_at_the_cycle_end(live):
    """It is an in-progress period like "This Month So Far". Running it to the
    cycle's real end would divide six weeks of goal by however many days had
    actually happened."""
    bounds = th.transfer_period_bounds(date(2026, 9, 3))
    assert bounds["This Transfer So Far"] == (date(2026, 7, 27), date(2026, 9, 3))


def test_last_transfer_is_the_whole_completed_cycle(live):
    bounds = th.transfer_period_bounds(date(2026, 9, 3))
    assert bounds["Last Transfer"] == (date(2026, 6, 15), date(2026, 7, 26))


def test_a_label_the_schedule_cannot_supply_is_simply_absent(monkeypatch):
    """Which is what lets the pickers hide an option rather than offer one that
    resolves to nothing."""
    _stub(monkeypatch, [("A", "2026-07-27", "6", "Actual")])
    bounds = th.transfer_period_bounds(date(2026, 9, 3))
    assert "This Transfer So Far" in bounds
    assert "Last Transfer" not in bounds


def test_no_transfer_at_all_offers_neither_label(monkeypatch):
    _stub(monkeypatch, [], config_start="")
    assert th.transfer_period_bounds(date(2026, 9, 3)) == {}
