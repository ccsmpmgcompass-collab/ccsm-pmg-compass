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
from app.db.queries import get_suggestions, set_suggestion_status, get_miracles, get_config_value
from app.export.miracle_pdf import correct_and_translate, build_miracle_pdf

st.set_page_config(
    page_title="Suggestions & Miracles — PMG Compass",
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
    "Suggestions & Miracles", "Review missionary suggestions and miracles"
)

# A plain st.tabs() has no persisted state — Streamlit always reopens it on
# tab 1 after any rerun, including the st.rerun() the miracle-PDF button
# below triggers, which was bouncing users back to Suggestions every time.
# A session_state-backed radio survives reruns because widget state is keyed
# and preserved across the whole session, not just the current script run.
active_tab = st.radio(
    "View", ["Suggestions", "Miracles"],
    key="sugg_active_tab", horizontal=True, label_visibility="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SUGGESTIONS & QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
if active_tab == "Suggestions":
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MIRACLES
# ══════════════════════════════════════════════════════════════════════════════
else:
    render_section_label("Filter")
    m1, m2 = st.columns([3, 1])
    mir_search = m1.text_input("Search", placeholder="Search miracles…", key="mir_search")
    mir_sort = m2.selectbox("Sort", ["Newest", "Oldest"], key="mir_sort")

    mdf = get_miracles(search=mir_search or None)

    render_section_label("Miracles")

    if mdf.empty:
        st.info("No miracles found.")
    else:
        # Sort by Timestamp if present
        if "Timestamp" in mdf.columns:
            mdf = mdf.sort_values("Timestamp", ascending=(mir_sort == "Oldest"))

        # Pick the story column: whichever non-Timestamp column has the longest median text
        non_ts_cols = [c for c in mdf.columns if c.lower() != "timestamp"]
        if non_ts_cols:
            story_col = max(
                non_ts_cols,
                key=lambda c: mdf[c].astype(str).str.len().median(),
            )
            meta_cols = [c for c in non_ts_cols if c != story_col]
        else:
            story_col = None
            meta_cols = []

        st.caption(f"{len(mdf)} miracle{'s' if len(mdf) != 1 else ''}")

        for idx, row in mdf.iterrows():
            ts = str(row.get("Timestamp", "") or "").strip()

            with st.container(border=True):
                if story_col:
                    story = str(row.get(story_col, "") or "").strip()
                    if story and story.lower() != "nan":
                        st.markdown(story)

                meta = []
                for col in meta_cols:
                    val = str(row.get(col, "") or "").strip()
                    if val and val.lower() != "nan":
                        meta.append(f"**{col}:** {val}")
                if ts and ts.lower() != "nan":
                    meta.append(ts)
                if meta:
                    st.caption("  |  ".join(meta))

                # ── Generate Miracle PDF ────────────────────────────────
                rid = re.sub(r"\W+", "_", str(idx)) or "row"
                state_key = f"mir_pdf_{rid}"

                if st.button("Generate Miracle PDF", key=f"genpdf_{rid}"):
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                    except (KeyError, AttributeError):
                        st.error("GEMINI_API_KEY not configured. Add it to .streamlit/secrets.toml.")
                        st.stop()
                    raw_story = story if story_col else ""
                    with st.spinner("Correcting spelling and translating..."):
                        try:
                            corrected = correct_and_translate(raw_story, api_key)
                            error_detail = None
                        except Exception as e:
                            corrected = raw_story
                            error_detail = str(e)
                    st.session_state[state_key] = {"text": corrected, "error": error_detail}
                    st.rerun()

                if state_key in st.session_state:
                    pdf_state = st.session_state[state_key]
                    if pdf_state["error"]:
                        st.warning(
                            "Automatic spelling/translation didn't run "
                            f"({pdf_state['error']}) — review the text below manually."
                        )
                    edited_text = st.text_area(
                        "Miracle text (edit before sharing)",
                        value=pdf_state["text"],
                        key=f"mir_pdf_text_{rid}",
                        height=160,
                    )

                    # No dedicated name/area columns on this branch (the
                    # "Submitter Info" enrichment lives on _merge-work only)
                    # — fall back to whatever meta columns look name/area-ish.
                    name_val = " ".join(
                        v for v in (
                            str(row.get(c, "") or "").strip() for c in meta_cols
                            if "name" in c.lower()
                        ) if v and v.lower() != "nan"
                    ).strip()
                    area_val = " ".join(
                        v for v in (
                            str(row.get(c, "") or "").strip() for c in meta_cols
                            if "area" in c.lower()
                        ) if v and v.lower() != "nan"
                    ).strip()

                    pdf_bytes = build_miracle_pdf(
                        story=edited_text,
                        name=name_val,
                        area=area_val,
                        date_str=ts,
                        mission_name=get_config_value('MISSION_NAME', flavor.display_name),
                    )

                    dl_col, discard_col = st.columns([1, 1])
                    dl_col.download_button(
                        "Download PDF",
                        data=pdf_bytes,
                        file_name=f"miracle_{rid}.pdf",
                        mime="application/pdf",
                        key=f"dl_{rid}",
                    )
                    if discard_col.button("Discard", key=f"discard_{rid}"):
                        del st.session_state[state_key]
                        st.rerun()
