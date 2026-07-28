"""
pages/17_Action_Center.py
PMG Compass | Leadership Action Center
One bell-linked page pulling together everything mission leadership needs
to act on: suggestions awaiting approval, note follow-ups due, custom
leadership-to-leadership tasks, and a rollup of the same maintenance
signals 18_Maintenance.py tracks. Every item links
straight to where it gets handled, pre-filtered when the target page
supports it (see the session_state keys set before each st.switch_page).
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from app.auth.auth import require_auth, is_leadership
from app.components.design_system import (
    inject_global_css,
    render_page_header,
    render_sidebar,
    render_section_label,
)
from app.db.action_center_queries import (
    get_action_center_summary,
    get_leadership_roster,
    create_leadership_task,
    resolve_leadership_task,
    get_leadership_tasks,
)

st.set_page_config(
    page_title="Action Center — PMG Compass",
    page_icon="🔔",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

current_email = user.get("email", "")

if not is_leadership(current_email):
    render_page_header("Action Center", "PMG Compass")
    st.info("This page is available to mission leadership only.")
    st.stop()

render_page_header("Action Center", "Everything that needs mission leadership's attention")

summary = get_action_center_summary(current_email)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — NEEDS YOUR ACTION
# ══════════════════════════════════════════════════════════════════════════════
render_section_label("Needs Your Action")

_any_items = False

if summary["suggestions_ap_count"] > 0:
    _any_items = True
    with st.container(border=True):
        st.markdown(f"**{summary['suggestions_ap_count']} suggestion(s) at AP Approval**")
        if st.button("Review in Suggestions", key="ac_go_ap_approval"):
            st.session_state["sug_status"] = "AP Approval"
            st.switch_page("pages/15_Suggestions.py")

if summary["suggestions_mp_count"] > 0:
    _any_items = True
    with st.container(border=True):
        st.markdown(f"**{summary['suggestions_mp_count']} suggestion(s) at Mission President Approval**")
        if st.button("Review in Suggestions", key="ac_go_mp_approval"):
            st.session_state["sug_status"] = "Mission President Approval"
            st.switch_page("pages/15_Suggestions.py")

if summary["followups_count"] > 0:
    _any_items = True
    with st.container(border=True):
        st.markdown(f"**{summary['followups_count']} note follow-up(s) due**")
        if st.button("Review in Notes", key="ac_go_notes"):
            st.switch_page("pages/10_Notes.py")

my_tasks = summary["my_tasks_df"]
if not my_tasks.empty:
    _any_items = True
    with st.container(border=True):
        st.markdown(f"**My Tasks — {len(my_tasks)} open**")
        for _, row in my_tasks.iterrows():
            task_id = str(row["task_id"])
            t1, t2 = st.columns([5, 1])
            due = f" · due {row['due_date']}" if str(row.get("due_date", "")).strip() else ""
            t1.markdown(f"{row['task_name']} — _assigned by {row['assigned_by']}{due}_")
            if str(row.get("notes", "")).strip():
                t1.caption(row["notes"])
            if t2.button("Done", key=f"ac_task_done_{task_id}"):
                resolve_leadership_task(task_id)
                st.rerun()

if not _any_items:
    st.success("Nothing needs your action right now.")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — ADD A TASK
# ══════════════════════════════════════════════════════════════════════════════
render_section_label("Add a Task")
st.caption("Hand something to another leader — it'll show in their Action Center.")

roster = [r for r in get_leadership_roster() if r["email"].lower() != current_email.lower()]

if not roster:
    st.info("No other leadership accounts found in MISSION_ORG.")
else:
    # Due-date checkbox lives OUTSIDE the form (same pattern as 10_Notes.py's
    # follow-up date) so ticking it reruns immediately and the date picker
    # appears without needing to submit first.
    has_due = st.checkbox("Set a due date", key="ac_task_has_due")
    due_date_val = None
    if has_due:
        due_date_val = st.date_input("Due date", value=date.today(), key="ac_task_due_date")

    with st.form("ac_new_task_form", clear_on_submit=True):
        f1, f2 = st.columns([3, 2])
        task_name = f1.text_input("Task", placeholder="What needs to happen?")
        assignee_labels = [f"{r['name']} ({r['email']})" for r in roster]
        assignee_idx = f2.selectbox(
            "Assign to", range(len(roster)), format_func=lambda i: assignee_labels[i]
        )
        notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Add Task")
        if submitted:
            if not task_name.strip():
                st.warning("Task name cannot be empty.")
            else:
                create_leadership_task(
                    task_name=task_name.strip(),
                    assigned_to=roster[assignee_idx]["email"],
                    assigned_by=current_email,
                    due_date=due_date_val.isoformat() if due_date_val else "",
                    notes=notes.strip(),
                )
                st.success(f"Task assigned to {roster[assignee_idx]['name']}.")
                st.rerun()

with st.expander("All open tasks"):
    all_open = get_leadership_tasks()
    if all_open.empty:
        st.caption("No open tasks.")
    else:
        for _, row in all_open.iterrows():
            due = f" · due {row['due_date']}" if str(row.get("due_date", "")).strip() else ""
            st.markdown(
                f"- **{row['task_name']}** — assigned to {row['assigned_to']} "
                f"by {row['assigned_by']}{due}"
            )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MAINTENANCE
# ══════════════════════════════════════════════════════════════════════════════
render_section_label("Maintenance")

if summary["maintenance_issues"]:
    for issue in summary["maintenance_issues"]:
        st.warning(issue)
    if st.button("Open Maintenance page", key="ac_go_maintenance"):
        st.switch_page("pages/18_Maintenance.py")
else:
    st.success("No maintenance issues detected.")
