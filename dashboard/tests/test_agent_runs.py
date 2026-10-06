"""Agents that SHOULD have run and left no row in AGENT_RUN_LOG.

The fixtures are the live log's own shape and its two real misses, found
2026-10-05: AgentMissionReport had one run ever (2026-08-03), and on 2026-09-28
Agent1A and Agent1B ran but Agent1C never did — while the failed-runs check
stayed green, because a run that never happens writes nothing.
"""

from datetime import datetime, timedelta

import pandas as pd

from app.analytics import agent_runs as AR


def _log(rows):
    return pd.DataFrame(rows, columns=["Timestamp", "Agent", "Status", "Notes"])


def _healthy_week(monday: datetime) -> list:
    """Every scheduled agent logging normally in the week starting `monday`."""
    rows = []
    for d in range(7):
        day = monday + timedelta(days=d)
        for agent in ("Agent3", "Agent5A", "AgentEscalation", "AgentDuplicate"):
            rows.append([day.strftime("%m/%d/%Y 06:00:00"), agent, "SUCCESS", ""])
    m = monday.strftime("%m/%d/%Y")
    rows += [
        [f"{m} 00:05:00", "AgentScores", "SUCCESS", ""],
        [f"{m} 07:00:00", "Agent4", "SUCCESS", ""],
        [f"{m} 18:28:00", "Agent1A", "SUCCESS", "Analyzed 45 areas | Agent1B scheduled in ~1 min"],
        [f"{m} 18:30:00", "Agent1B", "SUCCESS", "Messages selected | Agent1C scheduled in ~1 min"],
        [f"{m} 18:33:00", "Agent1C", "SUCCESS", "Emails sent: 48, errors: 0"],
        [f"{m} 19:00:00", "AgentMissionReport", "SUCCESS", "Sent: 3"],
        [(monday + timedelta(days=4)).strftime("%m/%d/%Y 09:55:00"), "Agent5B", "SUCCESS",
         "Checked 45 area(s) | Agent6 scheduled in ~1 min"],
        [(monday + timedelta(days=4)).strftime("%m/%d/%Y 09:57:00"), "Agent6", "SUCCESS", "Sent: 10"],
        [(monday + timedelta(days=6)).strftime("%m/%d/%Y 15:45:00"), "AgentReminder", "SUCCESS", ""],
    ]
    return rows


MON = datetime(2026, 9, 28)
NOW = datetime(2026, 10, 3, 12, 0)     # the Saturday after


def test_a_healthy_week_flags_nothing():
    assert AR.missed_runs(_log(_healthy_week(MON)), NOW) == []


def test_the_2026_09_28_chain_break_is_named():
    rows = [r for r in _healthy_week(MON) if r[1] != "Agent1C"]
    (p,) = AR.missed_runs(_log(rows), NOW)
    assert p["kind"] == "chain" and p["agent"] == "Agent1C" and p["after"] == "Agent1B"
    assert p["when"] == datetime(2026, 9, 28, 18, 30)


def test_a_chain_still_running_is_not_a_miss():
    rows = [r for r in _healthy_week(MON) if r[1] != "Agent1C"]
    rows += [[(MON - timedelta(days=7)).strftime("%m/%d/%Y 18:33:00"), "Agent1C",
              "SUCCESS", "Emails sent: 45"]]       # last week's letters
    assert AR.missed_runs(_log(rows), datetime(2026, 9, 28, 19, 0)) == []


def test_a_skipped_step_is_said_once_not_twice():
    """Ten days on, Agent1C is both "after 1B" and overdue; the chain message
    is the more specific, so it is the only one."""
    rows = [r for r in _healthy_week(MON) if r[1] != "Agent1C"]
    rows += [[(MON - timedelta(days=7)).strftime("%m/%d/%Y 18:33:00"), "Agent1C",
              "SUCCESS", "Emails sent: 45"]]
    found = [p for p in AR.missed_runs(_log(rows), datetime(2026, 10, 8, 9, 0))
             if p["agent"] == "Agent1C"]
    assert [p["kind"] for p in found] == ["chain"]


def test_the_mission_report_that_ran_once_in_august_is_overdue():
    rows = [r for r in _healthy_week(MON) if r[1] != "AgentMissionReport"]
    rows += [["8/3/2026 20:12:54", "AgentMissionReport", "ERROR", "QUOTA EXHAUSTED"]]
    (p,) = AR.missed_runs(_log(rows), NOW)
    assert p["kind"] == "overdue" and p["agent"] == "AgentMissionReport"
    assert p["days"] == 60 and p["last"] == datetime(2026, 8, 3, 20, 12, 54)


def test_an_agent_with_no_row_at_all_is_named():
    rows = [r for r in _healthy_week(MON) if r[1] != "AgentMissionReport"]
    (p,) = AR.missed_runs(_log(rows), NOW)
    assert p["agent"] == "AgentMissionReport" and p["last"] is None


def test_a_daily_agent_two_days_quiet_is_overdue():
    rows = [r for r in _healthy_week(MON) if not (r[1] == "Agent3" and r[0] >= "10/01")]
    (p,) = AR.missed_runs(_log(rows), datetime(2026, 10, 4, 12, 0))
    assert p["agent"] == "Agent3" and p["max_days"] == 2


def test_the_retired_agent2_is_never_expected():
    assert "Agent2" not in AR.MAX_GAP_DAYS


def test_an_empty_or_unreadable_log_says_nothing():
    assert AR.missed_runs(pd.DataFrame(), NOW) == []
    assert AR.missed_runs(pd.DataFrame({"Agent": ["Agent3"]}), NOW) == []
