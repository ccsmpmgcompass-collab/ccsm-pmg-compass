from app.config.flavor_loader import flavor, METRIC_LABELS
import streamlit as st
import pandas as pd
from datetime import date
from app.auth.auth import require_auth
from app.components.design_system import inject_global_css, render_page_header, render_sidebar, render_section_label
from app.db.queries import (
    get_zones,
    get_areas_df,
    get_notes,
    get_due_follow_ups,
    create_note,
    update_note,
    delete_note,
    resolve_note,
    get_config_value,
)
from app.i18n import t

st.set_page_config(
    page_title="CCSM · Notes — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)
dark = True

current_email = user["email"]

# ── Area hierarchy helpers ─────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load_areas():
    return get_areas_df()

@st.cache_data(ttl=300)
def _load_zones():
    return get_zones()

areas_df = _load_areas()
all_zones = _load_zones()

def _districts_for(zone: str) -> list:
    if areas_df.empty or not zone:
        return []
    col = "District" if "District" in areas_df.columns else "district"
    zcol = "Zone" if "Zone" in areas_df.columns else "zone"
    return sorted(areas_df[areas_df[zcol] == zone][col].dropna().unique().tolist())

def _areas_for(district: str) -> list:
    if areas_df.empty or not district:
        return []
    col = "Area_Name" if "Area_Name" in areas_df.columns else "area"
    dcol = "District" if "District" in areas_df.columns else "district"
    candidates = areas_df[areas_df[dcol] == district]
    acol = next((c for c in ("Area_Name", "area", "Area") if c in candidates.columns), None)
    if acol is None:
        return []
    return sorted(candidates[acol].dropna().unique().tolist())

# ── Sidebar filters ────────────────────────────────────────────────────────────

st.sidebar.header(t("Filter Notes"))
# Sentinel translated for display, compared against the same _ALL below so a
# language switch cannot change which notes are shown. Sits in a BinOp, so
# neither the extractor nor the coverage gate can see it - hence the comment.
_ALL = t("All")
zone_filter = st.sidebar.selectbox(
    t("Zone"),
    options=[_ALL] + all_zones,
    key="notes_zone_filter",
)
show_resolved = st.sidebar.checkbox(
    t("Show Resolved Notes"),
    value=False,
    key="notes_show_resolved",
)

# ── Page header ───────────────────────────────────────────────────────────────

render_page_header(t("Notes"), t('{mission_name} — Searchable Notes with Follow-up Reminders', mission_name=get_config_value('MISSION_NAME', flavor.display_name)))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Follow-ups Due
# ══════════════════════════════════════════════════════════════════════════════

due_df = get_due_follow_ups(user_email=current_email)

if isinstance(due_df, pd.DataFrame):
    due_list = due_df.to_dict("records") if not due_df.empty else []
elif isinstance(due_df, list):
    due_list = due_df
else:
    due_list = []

due_list = [n for n in due_list if str(n.get("resolved", "FALSE")).upper() != "TRUE"]

if due_list:
    with st.expander(t('Follow-ups Due — {count} note(s)', count=len(due_list)), expanded=True):
        for note in due_list:
            note_id = note.get("note_id") or note.get("id", "")
            col_content, col_meta, col_btn = st.columns([5, 3, 1])
            col_content.markdown(note.get("content", ""))
            fu_date = note.get("follow_up_date", "")
            creator = note.get("created_by", "")
            area_tag = note.get("area") or note.get("zone") or ""
            meta_parts = [f"Due: **{fu_date}**"]
            if creator:
                meta_parts.append(creator)
            if area_tag:
                meta_parts.append(area_tag)
            col_meta.caption("  |  ".join(meta_parts))
            if note_id and col_btn.button(t("Resolve"), key=f"due_resolve_{note_id}"):
                resolve_note(note_id, True)
                st.rerun()

render_section_label(t("New Note"))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: New Note Form
# ══════════════════════════════════════════════════════════════════════════════

with st.expander(t("New Note"), expanded=False):
    with st.form("new_note_form", clear_on_submit=True):
        new_content = st.text_area(t("Note *"), height=120, placeholder=t("Enter note content..."))
        new_tags = st.text_input(
            t("Tags (comma-separated)"),
            placeholder=t("training, concern, zone-x"),
        )

        loc_z, loc_d, loc_a = st.columns(3)
        new_zone = loc_z.selectbox(t("Zone (optional)"), [""] + all_zones, key="new_note_zone")
        new_districts = _districts_for(new_zone)
        new_district = loc_d.selectbox(
            t("District (optional)"), [""] + new_districts, key="new_note_district"
        )
        new_areas = _areas_for(new_district)
        new_area = loc_a.selectbox(
            t("Area (optional)"), [""] + new_areas, key="new_note_area"
        )

        new_visible = st.text_input(
            t("Visible to (comma-separated emails, leave blank for everyone)"),
            placeholder=t("elder.smith@example.com, sister.jones@example.com"),
            key="new_note_visible",
        )

        submitted = st.form_submit_button(t("Save Note"), type="primary")

    # Follow-up outside the form so the checkbox triggers an immediate rerun
    # and the date picker appears without needing to submit first.
    has_followup = st.checkbox(t("Set a follow-up date"), key="new_note_has_fu")
    new_follow_up = None
    if has_followup:
        new_follow_up = st.date_input(
            t("Follow-up Date"),
            value=date.today(),
            key="new_note_fu_date",
        )

    if submitted:
        if not new_content.strip():
            st.warning(t("Note content cannot be empty."))
        else:
            tags_str = new_tags.strip()
            follow_up_str = new_follow_up.isoformat() if new_follow_up else ""
            visible_str = new_visible.strip() if new_visible.strip() else "all"
            create_note(
                created_by=current_email,
                content=new_content.strip(),
                tags=tags_str,
                zone=new_zone or "",
                district=new_district or "",
                area=new_area or "",
                follow_up_date=follow_up_str,
                visible_to=visible_str,
            )
            st.session_state["new_note_has_fu"] = False
            st.session_state.pop("new_note_fu_date", None)
            st.success(t("Note saved."))
            st.rerun()

render_section_label(t("Notes List"))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Notes List
# ══════════════════════════════════════════════════════════════════════════════

raw_notes = get_notes(user_email=current_email, show_resolved=show_resolved)

if isinstance(raw_notes, pd.DataFrame):
    all_notes = raw_notes.to_dict("records") if not raw_notes.empty else []
elif isinstance(raw_notes, list):
    all_notes = raw_notes
else:
    all_notes = []

# Search & tag filter bar
search_col, tag_col = st.columns([3, 1])
search_text = search_col.text_input(
    t("Search notes"),
    placeholder=t("Search content…"),
    key="notes_search",
)

all_tags = sorted({
    t.strip()
    for n in all_notes
    for t in str(n.get("tags", "")).split(",")
    if t.strip()
})
tag_choice = tag_col.selectbox(t("Tag"), [_ALL] + all_tags, key="notes_tag_filter")
selected_tag = None if tag_choice == _ALL else tag_choice

# Apply filters
filtered = all_notes
if search_text:
    filtered = [n for n in filtered if search_text.lower() in str(n.get("content", "")).lower()]
if selected_tag:
    filtered = [
        n for n in filtered
        if selected_tag in [t.strip() for t in str(n.get("tags", "")).split(",")]
    ]
if zone_filter != _ALL:
    filtered = [n for n in filtered if n.get("zone") == zone_filter]
if not show_resolved:
    filtered = [n for n in filtered if str(n.get("resolved", "FALSE")).upper() != "TRUE"]

# ── Render notes ──────────────────────────────────────────────────────────────

if not filtered:
    has_filter = bool(search_text or selected_tag or zone_filter != _ALL)
    if has_filter:
        st.info(t("No notes match the current filters."))
    else:
        st.info(t("No notes yet. Create your first note above."))
else:
    for note in filtered:
        note_id = note.get("note_id") or note.get("id", "")
        is_owner = note.get("created_by", "").lower() == current_email.lower()
        resolved = str(note.get("resolved", "FALSE")).upper() == "TRUE"
        is_editing = st.session_state.get("editing_note_id") == note_id

        with st.container(border=True):

            # ── Edit mode ─────────────────────────────────────────────────────
            if is_editing:
                existing_fu = note.get("follow_up_date", "") or ""
                with st.form(key=f"edit_form_{note_id}", clear_on_submit=False):
                    edit_content = st.text_area(
                        t("Note *"),
                        value=note.get("content", ""),
                        height=120,
                        key=f"edit_content_{note_id}",
                    )
                    edit_tags = st.text_input(
                        t("Tags (comma-separated)"),
                        value=note.get("tags", ""),
                        key=f"edit_tags_{note_id}",
                    )

                    ez_col, ed_col, ea_col = st.columns(3)
                    cur_zone = note.get("zone") or ""
                    cur_district = note.get("district") or ""
                    cur_area = note.get("area") or ""

                    zone_opts = [""] + all_zones
                    edit_zone = ez_col.selectbox(
                        t("Zone"),
                        zone_opts,
                        index=zone_opts.index(cur_zone) if cur_zone in zone_opts else 0,
                        key=f"ez_{note_id}",
                    )
                    dist_opts = [""] + _districts_for(edit_zone)
                    edit_district = ed_col.selectbox(
                        t("District"),
                        dist_opts,
                        index=dist_opts.index(cur_district) if cur_district in dist_opts else 0,
                        key=f"ed_{note_id}",
                    )
                    area_opts = [""] + _areas_for(edit_district)
                    edit_area = ea_col.selectbox(
                        t("Area"),
                        area_opts,
                        index=area_opts.index(cur_area) if cur_area in area_opts else 0,
                        key=f"ea_{note_id}",
                    )

                    cur_visible = note.get("visible_to", "all") or "all"
                    edit_visible = st.text_input(
                        t("Visible to (comma-separated emails, leave blank for everyone)"),
                        value="" if str(cur_visible).lower() == "all" else str(cur_visible),
                        key=f"edit_vis_{note_id}",
                    )

                    save_col, cancel_col = st.columns(2)
                    save_btn = save_col.form_submit_button(t("Save Changes"), type="primary")
                    cancel_btn = cancel_col.form_submit_button(t("Cancel"))

                # Follow-up outside the form so toggling the checkbox immediately
                # shows/hides the date picker without waiting for form submit.
                _fu_key = f"edit_has_fu_{note_id}"
                if _fu_key not in st.session_state:
                    st.session_state[_fu_key] = bool(existing_fu)
                edit_has_fu = st.checkbox(t("Set follow-up date"), key=_fu_key)
                edit_fu = None
                if edit_has_fu:
                    try:
                        fu_default = date.fromisoformat(str(existing_fu)) if existing_fu else date.today()
                    except ValueError:
                        fu_default = date.today()
                    edit_fu = st.date_input(
                        t("Follow-up Date"),
                        value=fu_default,
                        key=f"edit_fu_{note_id}",
                    )

                if save_btn:
                    if not edit_content.strip():
                        st.warning(t("Note content cannot be empty."))
                    else:
                        fu_str = edit_fu.isoformat() if edit_fu else ""
                        vis_str = edit_visible.strip() if edit_visible.strip() else "all"
                        update_note(
                            note_id,
                            content=edit_content.strip(),
                            tags=edit_tags.strip(),
                            zone=edit_zone or "",
                            district=edit_district or "",
                            area=edit_area or "",
                            follow_up_date=fu_str,
                            visible_to=vis_str,
                        )
                        st.session_state.pop(_fu_key, None)
                        st.session_state.pop(f"edit_fu_{note_id}", None)
                        st.session_state.pop("editing_note_id", None)
                        st.rerun()
                elif cancel_btn:
                    st.session_state.pop(_fu_key, None)
                    st.session_state.pop(f"edit_fu_{note_id}", None)
                    st.session_state.pop("editing_note_id", None)
                    st.rerun()

            # ── View mode ─────────────────────────────────────────────────────
            else:
                body_col, btn_col = st.columns([6, 1])

                body_col.markdown(note.get("content", ""))

                # Metadata line
                meta_parts = []
                creator = note.get("created_by", "")
                created_at = str(note.get("created_at", ""))[:10]
                if creator:
                    meta_parts.append(f"_{creator}_")
                if created_at and created_at != "nan":
                    meta_parts.append(created_at)
                updated_at = str(note.get("updated_at", ""))
                if updated_at and updated_at[:16] != str(note.get("created_at", ""))[:16]:
                    meta_parts.append(f"Edited: {updated_at[:16].replace('T', ' ')}")
                fu_date = note.get("follow_up_date", "") or ""
                if fu_date and fu_date != "nan":
                    meta_parts.append(f"Follow-up: **{fu_date}**")
                if meta_parts:
                    body_col.caption("  |  ".join(meta_parts))

                # Tags
                tags_raw = str(note.get("tags", "")).strip()
                if tags_raw and tags_raw != "nan":
                    tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
                    if tags_list:
                        body_col.markdown(" ".join(f"`{t}`" for t in tags_list))

                # Location breadcrumb
                loc_parts = [
                    p for p in [note.get("zone"), note.get("district"), note.get("area")]
                    if p and str(p) != "nan"
                ]
                if loc_parts:
                    body_col.caption(" › ".join(loc_parts))

                # Visible-to info
                visible_to = str(note.get("visible_to", "all") or "all")
                if visible_to.lower() != "all":
                    body_col.caption(t('Visible to: {visible_to}', visible_to=visible_to))

                if resolved:
                    body_col.caption(t("Resolved"))

                # Action buttons
                with btn_col:
                    if note_id and st.button(t("Edit"), key=f"edit_btn_{note_id}"):
                        st.session_state["editing_note_id"] = note_id
                        st.rerun()

                    if note_id:
                        resolve_label = "Unresolve" if resolved else "Resolve"
                        if st.button(resolve_label, key=f"resolve_btn_{note_id}"):
                            resolve_note(note_id, not resolved)
                            st.rerun()

                    if note_id and is_owner:
                        if st.button(t("Delete"), key=f"delete_btn_{note_id}"):
                            delete_note(note_id)
                            st.session_state.pop("editing_note_id", None)
                            st.rerun()
