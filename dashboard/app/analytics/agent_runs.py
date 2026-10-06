"""Which Apps Script agents have stopped running.

AGENT_RUN_LOG records the runs that HAPPEN. A trigger that is missing, or a
chain step that never fires, writes no row at all — so the failed-runs check on
Mantenimiento and the Action Center bell stayed green while, measured on
2026-10-05:

  * AgentMissionReport had logged one run ever (2026-08-03): its Monday 10 PM
    trigger was not installed, and the President and the assistants received
    no mission report for two months;
  * Agent1C did not run on 2026-09-28 after Agent1A and Agent1B had, so that
    week's coaching letters never went out — and nothing said so.

This module asks the other question: who SHOULD have run by now and did not.
Pure — no Streamlit, no sheet access — so the Action Center bell and
Mantenimiento read the same answer.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

#: The longest gap, in days, each scheduled agent may go without a logged run:
#: its cadence in CCSM_Setup.gs's CCSM_TRIGGER_SCHEDULE plus a day of grace.
#: Agent1B, Agent1C and Agent6 have no trigger of their own — the chain
#: schedules them — but they run as often as the agent that starts the chain.
#: Agent2 is retired (2026-10-02) and deliberately absent.
MAX_GAP_DAYS = {
    "Agent3": 2,            # daily 6 AM and 9 PM
    "Agent5A": 2,           # daily noon
    "AgentEscalation": 2,   # daily 7 AM
    "AgentDuplicate": 2,    # daily 9:30 PM (and on every form submit)
    "Agent1A": 8,           # Monday 9:30 PM, chains 1B -> 1C
    "Agent1B": 8,
    "Agent1C": 8,
    "AgentScores": 8,       # Monday 12:05 AM
    "Agent4": 8,            # Monday 7 AM
    "AgentMissionReport": 8,  # Monday 10 PM
    "AgentReminder": 8,     # Sunday 6 PM
    "Agent5B": 8,           # Friday noon, chains Agent6
    "Agent6": 8,
}

#: (agent, the agent it schedules) — the second must log within CHAIN_HOURS of
#: a successful run of the first that says it scheduled it ("Agent1B scheduled
#: in ~1 min"). On 2026-09-28 Agent1B said exactly that, and Agent1C never ran.
CHAINS = (("Agent1A", "Agent1B"), ("Agent1B", "Agent1C"), ("Agent5B", "Agent6"))
CHAIN_HOURS = 3


def _frame(log: pd.DataFrame) -> pd.DataFrame:
    """The log with a parsed `_ts` column and stripped Agent/Status/Notes."""
    if log is None or log.empty or "Agent" not in log.columns:
        return pd.DataFrame(columns=["Agent", "Status", "Notes", "_ts"])
    ts_col = next((c for c in log.columns if c.strip().lower() == "timestamp"), None)
    if ts_col is None:
        return pd.DataFrame(columns=["Agent", "Status", "Notes", "_ts"])
    out = pd.DataFrame({
        "Agent": log["Agent"].astype(str).str.strip(),
        "Status": (log["Status"] if "Status" in log.columns else pd.Series("", index=log.index))
                  .astype(str).str.strip().str.upper(),
        "Notes": (log["Notes"] if "Notes" in log.columns else pd.Series("", index=log.index))
                 .astype(str),
        "_ts": pd.to_datetime(log[ts_col], errors="coerce"),
    })
    return out.dropna(subset=["_ts"])


def missed_runs(log: pd.DataFrame, now: datetime) -> list[dict]:
    """Every scheduled agent that is overdue, and every chain step that never
    followed its predecessor's latest run.

    Returns dicts, oldest problem first:
      ``{"kind": "overdue", "agent", "last": datetime | None, "days": int | None,
         "max_days": int}`` — ``last`` None means no run is logged at all;
      ``{"kind": "chain", "agent", "after", "when": datetime}``.

    An empty or unreadable log returns [] — Mantenimiento already says when the
    log itself is missing, and a list of thirteen "never ran" lines would bury it.
    """
    runs = _frame(log)
    if runs.empty:
        return []
    out: list[dict] = []

    for first, nxt in CHAINS:
        started = runs[(runs["Agent"] == first) & (runs["Status"] == "SUCCESS")
                       & runs["Notes"].str.contains(f"{nxt} scheduled", regex=False)]
        if started.empty:
            continue
        when = started["_ts"].max()
        if now - when.to_pydatetime() < timedelta(hours=CHAIN_HOURS):
            continue    # the chain may still be running
        followed = runs[(runs["Agent"] == nxt) & (runs["_ts"] >= when)
                        & (runs["_ts"] <= when + timedelta(hours=CHAIN_HOURS))]
        if followed.empty:
            out.append({"kind": "chain", "agent": nxt, "after": first,
                        "when": when.to_pydatetime()})
    # A skipped chain step is also "overdue" a week later; say it once, as the
    # more specific of the two.
    chained = {p["agent"] for p in out}

    last = runs.groupby("Agent")["_ts"].max()
    for agent, max_days in MAX_GAP_DAYS.items():
        if agent in chained:
            continue
        ts = last.get(agent)
        if ts is None or pd.isna(ts):
            out.append({"kind": "overdue", "agent": agent, "last": None,
                        "days": None, "max_days": max_days})
            continue
        gap = (now - ts.to_pydatetime()).days
        if gap > max_days:
            out.append({"kind": "overdue", "agent": agent, "last": ts.to_pydatetime(),
                        "days": gap, "max_days": max_days})

    def _key(p):
        return p.get("last") or p.get("when") or datetime.min
    return sorted(out, key=_key)
