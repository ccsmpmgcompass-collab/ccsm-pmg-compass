"""
app/db/action_center_queries.py
────────────────────────────────────────────────────────────
Leadership Action Center: LEADERSHIP_TASKS CRUD, the leadership roster,
and (added in a later task) the aggregated "needs your action" summary
used by the bell badge and the Action Center page.

LEADERSHIP_TASKS:
    task_id | task_name | assigned_to | assigned_by | created_at
    | due_date | notes | status | resolved_at
"""
import uuid
from datetime import datetime, timedelta

import pandas as pd

from app.db.sheets_client import read_tab, append_row, update_row, overwrite_tab
from app.db.queries import (
    get_areas_df,
    get_suggestions,
    get_due_follow_ups,
)
from app.i18n import t

_TASKS_TAB = "LEADERSHIP_TASKS"
_TASKS_HEADER = [
    "task_id", "task_name", "assigned_to", "assigned_by", "created_at",
    "due_date", "notes", "status", "resolved_at",
]


def _ensure_tasks_header() -> None:
    """Create LEADERSHIP_TASKS with its header row if the tab doesn't exist
    yet or is empty. overwrite_tab() creates the worksheet automatically
    when missing (same helper SCORE_CONFIG and other config tabs use)."""
    df = read_tab(_TASKS_TAB)
    if df.empty:
        overwrite_tab(_TASKS_TAB, [_TASKS_HEADER])


def create_leadership_task(
    task_name: str,
    assigned_to: str,
    assigned_by: str,
    due_date: str = "",
    notes: str = "",
) -> None:
    """Append one ad-hoc task, assigned by one leader to another (or to
    themselves). Status starts Open."""
    _ensure_tasks_header()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    row = [
        str(uuid.uuid4()), task_name, assigned_to, assigned_by, now,
        due_date, notes, "Open", "",
    ]
    append_row(_TASKS_TAB, row)


def get_leadership_tasks(assigned_to: str = None, show_resolved: bool = False) -> pd.DataFrame:
    """Open (or all, if show_resolved) LEADERSHIP_TASKS rows, optionally
    filtered to one assignee (case-insensitive email match)."""
    df = read_tab(_TASKS_TAB)
    if df.empty:
        return pd.DataFrame(columns=_TASKS_HEADER)
    if not show_resolved and "status" in df.columns:
        df = df[df["status"].astype(str) != "Done"].copy()
    if assigned_to:
        email = assigned_to.lower().strip()
        df = df[df["assigned_to"].astype(str).str.lower().str.strip() == email].copy()
    return df


def resolve_leadership_task(task_id: str) -> None:
    """Mark one task Done, stamping resolved_at. No-op if the id isn't found
    (mirrors app/db/queries.py's resolve_note / update_note pattern)."""
    df = read_tab(_TASKS_TAB)
    if df.empty or "task_id" not in df.columns:
        return
    idx = df.index[df["task_id"] == task_id].tolist()
    if not idx:
        return
    row_s = df.loc[idx[0]].copy()
    row_s["status"] = "Done"
    row_s["resolved_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    update_row(_TASKS_TAB, idx[0] + 2, row_s.reindex(_TASKS_HEADER).tolist())


def get_leadership_roster() -> list[dict]:
    """The President and the assistants as [{"name": ..., "email": ...}] — the
    people a task can be handed to. Active MISSION_LEADERSHIP rows, by the
    address each signs in with.

    Was MISSION_ORG's Is_MP / Is_AP rows until 2026-10-05, which meant one
    entry: La Marina 1's shared mailbox, under whichever companion's name came
    first. That mailbox no longer opens the Action Center (D11), so a task
    handed to it could never be read.
    """
    from app.db.queries import get_mission_leadership

    df = get_mission_leadership()
    if df.empty:
        return []
    roster: dict[str, str] = {}
    for _, row in df.iterrows():
        email = str(row.get("Email", "")).strip().lower()
        if email and "@" in email and email not in roster:
            roster[email] = str(row.get("Name", "")).strip() or email
    return [
        {"name": name, "email": email}
        for email, name in sorted(roster.items(), key=lambda kv: kv[1])
    ]


def _latest_date(tab: str, marker: str, candidates: tuple):
    """Return the max date found in `tab`'s first matching column, or None.
    Mirrors 18_Mantenimiento.py's _latest_date helper exactly (same tabs, same
    header_marker/candidate conventions) so the two pages never disagree."""
    df = read_tab(tab, header_marker=marker)
    if df.empty:
        return None
    col = next((c for c in df.columns if c.strip().lower() in candidates), None)
    if not col:
        return None
    vals = pd.to_datetime(df[col], errors="coerce").dropna()
    return vals.max() if not vals.empty else None


def missed_run_messages() -> list[str]:
    """`agent_runs.missed_runs` as one sentence each, for the bell and for
    Mantenimiento's Agent Runs section — the agents that SHOULD have run and
    left no row (a missing trigger, a chain step that never fired)."""
    from app.analytics.agent_runs import missed_runs

    msgs = []
    for p in missed_runs(read_tab("AGENT_RUN_LOG", header_marker="Agent"), datetime.now()):
        if p["kind"] == "chain":
            msgs.append(t("{agent} did not run after {after} on {date} — that run's "
                          "emails may not have gone out",
                          agent=p["agent"], after=p["after"],
                          date=p["when"].strftime("%Y-%m-%d")))
        elif p["last"] is None:
            msgs.append(t("{agent} has no run in AGENT_RUN_LOG — its trigger is "
                          "probably not installed", agent=p["agent"]))
        elif p["max_days"] <= 2:
            msgs.append(t("{agent} last ran {days} days ago, and it runs every day — "
                          "its trigger may be missing", agent=p["agent"], days=p["days"]))
        else:
            msgs.append(t("{agent} last ran {days} days ago, and it runs every week — "
                          "its trigger may be missing", agent=p["agent"], days=p["days"]))
    return msgs


def _maintenance_issues() -> list[str]:
    """Re-run the same two health signals 18_Mantenimiento.py surfaces (agent
    failures, stale data) as short messages for the Action Center.

    B6 (AUDIT-IA-2026-08-22.md): these used to be bare f-strings, so they were
    the one place on an otherwise-Spanish page that rendered in English — the
    same signal Mantenimiento.py's own copies already run through t()."""
    issues: list[str] = []

    log = read_tab("AGENT_RUN_LOG", header_marker="Agent")
    if not log.empty and "Status" in log.columns:
        ts_col = next((c for c in log.columns if c.strip().lower() == "timestamp"), None)
        fails = log[~log["Status"].astype(str).str.strip().str.upper().isin(["SUCCESS", "OK", ""])]
        if ts_col:
            ts = pd.to_datetime(fails[ts_col], errors="coerce")
            fails = fails[ts >= datetime.now() - timedelta(days=14)]
        if not fails.empty:
            issues.append(t("{count} agent run(s) failed in the last 14 days",
                             count=len(fails)))
    # A run that never happened writes no row, so the check above cannot see it
    # (2026-10-05: the mission report had not run for two months).
    issues.extend(missed_run_messages())

    dl_date = _latest_date("DAILY_LOG", "Date", ("date",))
    if dl_date is not None and (datetime.now() - dl_date).days > 2:
        issues.append(t("DAILY_LOG hasn't been written in {days} day(s)",
                         days=(datetime.now() - dl_date).days))

    wk_date = _latest_date("WEEKLY_KI", "Area_Code", ("week_end_date", "week_ending_date", "week_end"))
    if wk_date is not None and (datetime.now() - wk_date).days > 9:
        issues.append(t("WEEKLY_KI's latest week ended {days} day(s) ago",
                         days=(datetime.now() - wk_date).days))

    return issues


def get_action_center_summary(user_email: str) -> dict:
    """Everything the bell badge and the Action Center page need, in one
    call. Suggestions/maintenance are team-wide (shared leadership queue);
    follow-ups and tasks are personal to user_email."""
    email = (user_email or "").lower().strip()

    subs = get_suggestions(type_filter="Suggestion")
    if subs.empty or "Status" not in subs.columns:
        ap_df = pd.DataFrame(columns=subs.columns)
        mp_df = pd.DataFrame(columns=subs.columns)
    else:
        ap_df = subs[subs["Status"] == "AP Approval"]
        mp_df = subs[subs["Status"] == "Mission President Approval"]

    followups = get_due_follow_ups(user_email=email)
    my_tasks = get_leadership_tasks(assigned_to=email)
    issues = _maintenance_issues()

    return {
        "suggestions_ap_count": len(ap_df),
        "suggestions_mp_count": len(mp_df),
        "followups_count": len(followups),
        "my_tasks_count": len(my_tasks),
        "maintenance_issues": issues,
        "total": (
            len(ap_df) + len(mp_df)
            + len(followups) + len(my_tasks) + len(issues)
        ),
        "suggestions_ap_df": ap_df,
        "suggestions_mp_df": mp_df,
        "followups_df": followups,
        "my_tasks_df": my_tasks,
    }
