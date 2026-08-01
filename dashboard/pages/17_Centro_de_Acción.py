"""
pages/17_Centro_de_Acción.py
PMG Compass | Leadership Action Center
One bell-linked page pulling together everything mission leadership needs
to act on: suggestions awaiting approval, note follow-ups due, custom
leadership-to-leadership tasks, and a rollup of the same maintenance
signals 18_Mantenimiento.py tracks. Every item links
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
from app.i18n import t

st.set_page_config(
    page_title="CCSM · Action Center — PMG Compass",
    page_icon="🔔",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

current_email = user.get("email", "")

if not is_leadership(current_email):
    render_page_header(t("Action Center"), t("PMG Compass"))
    st.info(t("This page is available to mission leadership only."))
    st.stop()

render_page_header(t("Action Center"), t("Everything that needs mission leadership's attention"))

summary = get_action_center_summary(current_email)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — NEEDS YOUR ACTION
# ══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Needs Your Action"))

_any_items = False

if summary["suggestions_ap_count"] > 0:
    _any_items = True
    with st.container(border=True):
        st.markdown(t('**{suggestions_ap_count} suggestion(s) at AP Approval**', suggestions_ap_count=summary['suggestions_ap_count']))
        if st.button(t("Review in Suggestions"), key="ac_go_ap_approval"):
            st.session_state["sug_status"] = "AP Approval"
            st.switch_page("pages/15_Sugerencias.py")

if summary["suggestions_mp_count"] > 0:
    _any_items = True
    with st.container(border=True):
        st.markdown(t('**{suggestions_mp_count} suggestion(s) at Mission President Approval**', suggestions_mp_count=summary['suggestions_mp_count']))
        if st.button(t("Review in Suggestions"), key="ac_go_mp_approval"):
            st.session_state["sug_status"] = "Mission President Approval"
            st.switch_page("pages/15_Sugerencias.py")

if summary["followups_count"] > 0:
    _any_items = True
    with st.container(border=True):
        st.markdown(t('**{followups_count} note follow-up(s) due**', followups_count=summary['followups_count']))
        if st.button(t("Review in Notes"), key="ac_go_notes"):
            st.switch_page("pages/10_Notas.py")

my_tasks = summary["my_tasks_df"]
if not my_tasks.empty:
    _any_items = True
    with st.container(border=True):
        st.markdown(t('**My Tasks — {count} open**', count=len(my_tasks)))
        for _, row in my_tasks.iterrows():
            task_id = str(row["task_id"])
            t1, t2 = st.columns([5, 1])
            due = f" · due {row['due_date']}" if str(row.get("due_date", "")).strip() else ""
            t1.markdown(t('{task_name} — _assigned by {assigned_by}{due}_', task_name=row['task_name'], assigned_by=row['assigned_by'], due=due))
            if str(row.get("notes", "")).strip():
                t1.caption(row["notes"])
            if t2.button(t("Done"), key=f"ac_task_done_{task_id}"):
                resolve_leadership_task(task_id)
                st.rerun()

if not _any_items:
    st.success(t("Nothing needs your action right now."))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — ADD A TASK
# ══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Add a Task"))
st.caption(t("Hand something to another leader — it'll show in their Action Center."))

roster = [r for r in get_leadership_roster() if r["email"].lower() != current_email.lower()]

if not roster:
    st.info(t("No other leadership accounts found in MISSION_ORG."))
else:
    # Due-date checkbox lives OUTSIDE the form (same pattern as 10_Notas.py's
    # follow-up date) so ticking it reruns immediately and the date picker
    # appears without needing to submit first.
    has_due = st.checkbox(t("Set a due date"), key="ac_task_has_due")
    due_date_val = None
    if has_due:
        due_date_val = st.date_input(t("Due date"), value=date.today(), key="ac_task_due_date")

    with st.form("ac_new_task_form", clear_on_submit=True):
        f1, f2 = st.columns([3, 2])
        task_name = f1.text_input(t("Task"), placeholder=t("What needs to happen?"))
        assignee_labels = [f"{r['name']} ({r['email']})" for r in roster]
        assignee_idx = f2.selectbox(
            t("Assign to"), range(len(roster)), format_func=lambda i: assignee_labels[i]
        )
        notes = st.text_input(t("Notes (optional)"))
        submitted = st.form_submit_button(t("Add Task"))
        if submitted:
            if not task_name.strip():
                st.warning(t("Task name cannot be empty."))
            else:
                create_leadership_task(
                    task_name=task_name.strip(),
                    assigned_to=roster[assignee_idx]["email"],
                    assigned_by=current_email,
                    due_date=due_date_val.isoformat() if due_date_val else "",
                    notes=notes.strip(),
                )
                st.success(t('Task assigned to {name}.', name=roster[assignee_idx]['name']))
                st.rerun()

with st.expander(t("All open tasks")):
    all_open = get_leadership_tasks()
    if all_open.empty:
        st.caption(t("No open tasks."))
    else:
        for _, row in all_open.iterrows():
            due = f" · due {row['due_date']}" if str(row.get("due_date", "")).strip() else ""
            st.markdown(
                t('- **{task_name}** — assigned to {assigned_to} by {assigned_by}{due}', task_name=row['task_name'], assigned_to=row['assigned_to'], assigned_by=row['assigned_by'], due=due)
            )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MAINTENANCE
# ══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Maintenance"))

if summary["maintenance_issues"]:
    for issue in summary["maintenance_issues"]:
        st.warning(issue)
    if st.button(t("Open Maintenance page"), key="ac_go_maintenance"):
        st.switch_page("pages/18_Mantenimiento.py")
else:
    st.success(t("No maintenance issues detected."))
