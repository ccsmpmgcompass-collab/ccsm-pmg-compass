from app.config.flavor_loader import flavor, METRIC_LABELS
import re
import streamlit as st
from app.auth.auth import require_auth, is_leadership
from app.components.design_system import (
    inject_global_css,
    render_page_header,
    render_sidebar,
    render_section_label,
)
from app.db.queries import get_suggestions, set_suggestion_status, get_config_value

st.set_page_config(
    page_title="Suggestions — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

current_email = user["email"]

# ── Leadership-only gate ───────────────────────────────────────────────────────
if not is_leadership(current_email):
    render_page_header("Suggestions", get_config_value('MISSION_NAME', flavor.display_name))
    st.info("This page is available to mission leadership only.")
    st.stop()

render_page_header(
    "Suggestions", "Review missionary suggestions"
)

# ── Counts (suggestions only) ──────────────────────────────────────────────
all_df = get_suggestions(type_filter="Suggestion")
def _count(s):
    if all_df.empty:
        return 0
    return int((all_df["Status"] == s).sum())

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Pending", _count("Pending"))
c2.metric("AP Approval", _count("AP Approval"))
c3.metric("MP Approval", _count("Mission President Approval"))
c4.metric("Final Approval", _count("Final Approval"))
c5.metric("On Hold", _count("Hold"))
c6.metric("Done", _count("Done"))
c7.metric("Rejected", _count("Rejected"))

# ── Controls ───────────────────────────────────────────────────────────────
render_section_label("Filter")
f1, f3, f4 = st.columns([1, 2, 1])
status_filter = f1.selectbox(
    "Status",
    ["Pending", "AP Approval", "Mission President Approval", "Final Approval",
     "Hold", "Done", "Rejected", "All"],
    key="sug_status",
)
search_text = f3.text_input("Search", placeholder="Search message or name…", key="sug_search")
sort_order = f4.selectbox("Sort", ["Newest", "Oldest"], key="sug_sort")

df = get_suggestions(
    status=status_filter,
    type_filter="Suggestion",
    search=search_text or None,
)

if not df.empty:
    df = df.sort_values("Timestamp", ascending=(sort_order == "Oldest"))

render_section_label("Suggestions")

if df.empty:
    st.info("No suggestions match the current filters.")
else:
    for _, row in df.iterrows():
        key = str(row["Key"])
        rid = re.sub(r"\W+", "_", key) or "row"
        status = row["Status"]
        kind = str(row.get("Kind", "")).strip()
        name = str(row.get("Name", "")).strip()
        email = str(row.get("Email", "")).strip()
        message = str(row.get("Message", "")).strip()
        ts = str(row.get("Timestamp", "")).strip()

        with st.container(border=True):
            body_col, btn_col = st.columns([6, 1])

            body_col.markdown(message)

            meta = []
            if kind:
                meta.append(f"**{kind}**")
            if name:
                meta.append(f"_{name}_")
            if email and email.lower() != "nan":
                meta.append(email)
            if ts and ts.lower() != "nan":
                meta.append(ts)
            meta.append(f"Status: **{status}**")
            body_col.caption("  |  ".join(meta))

            reviewer = str(row.get("ReviewedBy", "")).strip()
            reviewed_at = str(row.get("ReviewedAt", "")).strip()
            reviewer_note = str(row.get("ReviewerNote", "")).strip()
            if reviewer and reviewer.lower() != "nan":
                line = f"Reviewed by {reviewer}"
                if reviewed_at and reviewed_at.lower() != "nan":
                    line += f" on {reviewed_at}"
                body_col.caption(line)
            if reviewer_note and reviewer_note.lower() != "nan":
                body_col.caption(f"Note: {reviewer_note}")

            def _apply(new_status, clear_note=False):
                note = "" if clear_note else st.session_state.get(f"note_{rid}", "")
                set_suggestion_status(
                    key, new_status, current_email, note,
                    kind=kind, name=name, email=email, message=message,
                )
                st.rerun()

            with btn_col:
                if status == "Mission President Approval":
                    if st.button("Final Approval", key=f"finapp_{rid}", type="primary",
                                  help="Mission President's final approval — emails pmg.compass@gmail.com"):
                        _apply("Final Approval")
                if status != "AP Approval":
                    if st.button("AP Approval", key=f"apapp_{rid}", type="secondary",
                                  help="Approved by an AP — send to the Mission President's queue"):
                        _apply("AP Approval")
                if status != "Mission President Approval":
                    if st.button("→ MP Approval", key=f"mpapp_{rid}", type="primary",
                                  help="Move to the Mission President's queue"):
                        _apply("Mission President Approval")
                if status != "Hold":
                    if st.button("Hold", key=f"hold_{rid}", help="Park as a future idea"):
                        _apply("Hold")
                if status != "Done":
                    if st.button("Done", key=f"impl_{rid}",
                                  help="Mark as implemented/deployed — emails pmg.compass@gmail.com"):
                        _apply("Done")
                if status != "Rejected":
                    if st.button("Reject", key=f"rej_{rid}"):
                        _apply("Rejected")
                if status != "Pending" and status != "Mission President Approval":
                    if st.button("Re-open", key=f"reo_{rid}"):
                        _apply("Pending", clear_note=True)

            body_col.text_input(
                "Reviewer note (optional)",
                key=f"note_{rid}",
                placeholder="Add a note before Accept/Reject…",
                label_visibility="collapsed",
            )
