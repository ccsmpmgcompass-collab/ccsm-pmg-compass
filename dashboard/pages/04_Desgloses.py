"""
04_Desgloses.py
────────────────────────────────────────────────────────────────────────────────
Zone / District / Area breakdowns on one page — replaces the old separate
04_Zone_Breakdown.py and 05_Area_Breakdown.py (combined 2026-07-15).

Three cascading selectors; the DEEPEST selection wins and its breakdown
replaces whatever was showing:

  - Area picked     → single-area deep-dive (companionship, KPIs, rolling
                      windows, goals-vs-actuals, compliance calendars,
                      anomalies, notes) — the old Area Breakdown.
  - District picked → group breakdown scoped to that district's areas (new;
                      same sections as the zone view, one level down).
  - Zone picked     → group breakdown scoped to that zone's areas — the old
                      Zone Breakdown.

Zone/District also stay optional narrowing filters for the Area box, so picking
an area directly still works and derives its own zone/district.

Reads WEEKLY_KI, DAILY_LOG, WEEKLY_FORM_RAW, LIVE_SNAPSHOT, MISSION_ORG and
TABLEAU_DETAIL via the query layer. Plotly charts. No writes except Notes.
"""

import html as _html
from datetime import date

import pandas as pd
import streamlit as st

from app.auth.auth import require_auth
from app.breakdowns_engine import (
    _ANY,
    _group_area_names,
    _load_daily_history,
    _load_zones,
    _render_compliance,
    _scope_to_areas,
    render_group_breakdown,
    render_lineage_badge,
    render_lineage_marker,
)
from app.components.design_system import (
    inject_global_css,
    render_companionship_card,
    render_page_header,
    render_section_label,
    render_sidebar,
)
from app.components.scope_selector import render_scope_selectors
from app.config.flavor_loader import flavor
from app.i18n import t
from app.db.queries import (
    create_note,
    get_area_goals,
    get_config_value,
    get_district_goals,
    get_lineage_visible_areas,
    get_live_snapshot,
    get_notes,
    get_zone_goals,
)

st.set_page_config(
    page_title="CCSM · Breakdowns — PMG Compass",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

# The pure-white selectbox CSS moved into render_scope_selectors (the shared
# scope component injects it), so the Breakdowns and Scores dropdowns match.



# ══════════════════════════════════════════════════════════════════════════════
# AREA EXTRAS — what the single-area view keeps AROUND the shared group body:
# the companionship card above it (rendered at the dispatch site) and these
# Notes below it. Everything else the old Area Breakdown carried — rolling
# windows, goals-vs-actuals, compliance calendars, the 30-day daily activity
# table, KI history, anomalies — was dropped 2026-07-17 when the area view
# adopted the zone/district layout wholesale (Carson: "I want the area and
# district pages to look exactly like the zone one"). Recoverable from git
# history if any of it is ever missed.
# ══════════════════════════════════════════════════════════════════════════════

def _render_area_notes(
    selected_area: str,
    selected_zone: str,
    selected_district: str,
) -> None:
    """Leadership notes for one area — list them, and add new ones."""
    render_section_label(t("Notes"))

    try:
        _notes_raw = get_notes(user_email=user["email"], show_resolved=True)
    except Exception:
        _notes_raw = pd.DataFrame()

    if not _notes_raw.empty and "area" in _notes_raw.columns:
        _area_notes = _notes_raw[_notes_raw["area"] == selected_area].copy()
    else:
        _area_notes = pd.DataFrame()

    _show_resolved = st.checkbox(t("Show resolved notes"), value=False, key="show_resolved_notes")

    if not _area_notes.empty and "resolved" in _area_notes.columns:
        if not _show_resolved:
            _area_notes = _area_notes[
                _area_notes["resolved"].astype(str).str.upper() != "TRUE"
            ]

    if _area_notes.empty:
        st.info(t("No notes for this area."))
    else:
        for _, _note in _area_notes.iterrows():
            _content = str(_note.get("content", ""))
            _created_by = str(_note.get("created_by", ""))
            _created_at = str(_note.get("created_at", ""))
            _tags = str(_note.get("tags", "") or "")
            _follow_up = str(_note.get("follow_up_date", "") or "")

            _meta_parts = [_created_by, _created_at]
            if _tags:
                _meta_parts.append(_tags)
            if _follow_up and _follow_up not in ("", "None", "nan"):
                _meta_parts.append(f"follow-up: {_follow_up}")
            _meta_line = " · ".join(p for p in _meta_parts if p and p not in ("None", "nan", ""))

            st.markdown(
                f'<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.10);'
                f'border-radius:12px;padding:14px 18px;margin-bottom:10px;">'
                f'<div style="color:#e8e8ed;font-size:0.95rem;margin-bottom:6px;">{_html.escape(_content)}</div>'
                f'<div style="color:rgba(255,255,255,0.45);font-size:0.78rem;">{_html.escape(_meta_line)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with st.expander(t("Add Note"), expanded=False):
        _new_content = st.text_area(t("Note *"), height=100, placeholder=t("Enter note content..."), key="note_content_input")
        _new_tags = st.text_input(t("Tags (comma-separated)"), placeholder=t("training, concern"), key="note_tags_input")
        _has_fu = st.checkbox(t("Set a follow-up date"), key="note_has_followup")
        _new_fu = st.date_input(t("Follow-up Date"), value=date.today(), key="note_followup_date") if _has_fu else None
        if st.button(t("Save Note"), key="note_save_btn"):
            if not _new_content.strip():
                st.warning(t("Note content is required."))
            else:
                _fu_str = str(_new_fu) if _new_fu is not None else ""
                create_note(
                    created_by=user["email"],
                    content=_new_content.strip(),
                    tags=_new_tags.strip(),
                    zone=selected_zone,
                    district=selected_district,
                    area=selected_area,
                    follow_up_date=_fu_str,
                )
                st.success(t("Note saved."))
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE — selectors, then the deepest selection's breakdown
# ══════════════════════════════════════════════════════════════════════════════

render_page_header(
    t("Breakdowns"),
    t("{mission} — Zone, District & Area Performance",
      mission=get_config_value("MISSION_NAME", flavor.display_name)),
)

# Everything from the selectors down lives in ONE st.fragment: a dropdown /
# Period / Metric pick then reruns JUST this section instead of the whole
# script. On a full-page rerun the app chrome — the injected global CSS, page
# header and custom sidebar — is torn down and re-sent, which flashed the page
# unstyled (default fonts, wide layout, raw sidebar page names) for a beat on
# EVERY switch; Carson's 2026-07-17 screen recording caught it frame-by-frame.
# The fragment never touches those elements, so the frame stays put and only
# this scoped body rebuilds. st.stop() inside the old inline version became
# plain returns — nothing renders after the fragment, so they're equivalent,
# and a return can't accidentally halt a FULL run that happens to execute the
# fragment inline (initial page load, Save Note's st.rerun).
@st.fragment
def _scope_body() -> None:
    # Re-inject the global CSS at the top of every fragment rerun (cheap: just
    # re-adds the same <style> tag, no visible flash since the header/sidebar
    # outside the fragment never move). Confirmed live 2026-07-24: picking an
    # Area for the first time in a session sometimes routes through an
    # internal Streamlit fragment-navigation path (URL grows a "/~/+/" segment)
    # that drops the top-level inject_global_css() call's <style> block
    # entirely — .block-container jumped from its capped 1400px straight to
    # the full ~1578px stMain width, and every later Zone/District/Area switch
    # stayed inside that same now-unstyled fragment (only a real navigation to
    # another page and back re-runs the page module and restores it). This
    # call is the guard so the fragment can never end up CSS-less again.
    inject_global_css()

    # Load areas once, exclude leadership rows (by Area_Name pattern — a
    # leadership flag can legitimately be TRUE on a real area row, see
    # get_submitting_areas())
    _areas_all = get_lineage_visible_areas()

    # ── Scope selectors (shared with the Scores page) ──────────────────
    # Zone → District → Area → Find-by-missionary, deepest selection wins. The
    # held-outside-the-widget pattern and cascade-reset behaviour live in
    # app/components/scope_selector.py now, shared verbatim with 06_Puntajes.py.
    selected_zone, selected_district, selected_area, _level = render_scope_selectors(
        _areas_all, prefix="bd", zones=_load_zones(),
    )

    # The group views own their Period and Metric pickers now — Period sits
    # above the Key Indicators cards and drives every section, and Metric sits
    # down with the bar chart it controls.

    st.divider()

    if _level is None:
        st.info(
            t("Pick a Zone, District or Area above — type in any box to search. "
              "The deepest selection is what gets broken down: choose a zone for the "
              "zone view, add a district to drill into it, add an area for the "
              "single-area deep-dive.")
        )
        return

    # ── Scope — all three levels share the group body ─────────────────────────
    # A single area is just a group of one (Carson, 2026-07-17: "I want the area
    # and district pages to look exactly like the zone one"); the area level
    # adds a companionship card above the shared body and Notes below it. Every
    # period-driven section reads DAILY_LOG, so that is the only activity tab
    # any level loads — WEEKLY_KI and WEEKLY_FORM_RAW are weekly-grained and
    # can't be cut to an arbitrary period.

    if _level == "area":
        if render_lineage_marker(selected_area, area_val_key="bd_area_val"):
            return

        # Derive zone/district from the chosen area so the companionship card
        # and notes are labelled correctly even when those filters were left on
        # "any".
        _area_meta = _areas_all[_areas_all["Area_Name"] == selected_area]
        if not _area_meta.empty:
            if selected_zone == _ANY:
                selected_zone = str(_area_meta.iloc[0].get("Zone", "") or "")
            if selected_district == _ANY:
                selected_district = str(_area_meta.iloc[0].get("District", "") or "")

        scope_kind, scope_value = "Area", selected_area
        group_areas = {selected_area}
        snap_scope = _scope_to_areas(get_live_snapshot(), "Area", group_areas)
        group_goals = get_area_goals(selected_area)   # an area has its own goals
    elif _level == "district":
        scope_kind, scope_value = "District", selected_district
        group_areas = _group_area_names(_areas_all, "District", selected_district)
        snap_scope = _scope_to_areas(get_live_snapshot(), "Area", group_areas)
        # Same pattern as the zone level: sum of per-area weekly goals across
        # the district's submitting areas (Carson, 2026-07-24 — wants the same
        # Key Indicators goal bars zone/area already have).
        group_goals = get_district_goals(selected_district)
    else:
        scope_kind, scope_value = "Zone", selected_zone
        group_areas = _group_area_names(_areas_all, "Zone", selected_zone)
        snap_scope = _scope_to_areas(get_live_snapshot(), "Area", group_areas)
        group_goals = get_zone_goals(selected_zone)

    # The companionship card sits ABOVE the data guards on purpose: an area with
    # no submissions yet should still show who is serving there.
    if _level == "area":
        render_lineage_badge(selected_area)
        render_section_label(t("Companionship"))
        _card_row = _areas_all[
            _areas_all["Area_Name"].astype(str).str.strip() == selected_area
        ]
        if not _card_row.empty:
            # Shared helper — the Goals page renders the identical card.
            render_companionship_card(
                _card_row.iloc[0],
                zone=selected_zone,
                district=selected_district,
            )
        else:
            st.warning(t("Companionship info not found in MISSION_ORG."))

    daily_hist = _scope_to_areas(_load_daily_history(), "Area", group_areas)

    if not group_areas:
        st.info(
            t("MISSION_ORG lists no active areas for {scope}.", scope=scope_value)
        )
        return

    if daily_hist.empty:
        st.info(
            t("No data yet for {scope}. Submit the nightly form or run a data refresh.",
              scope=scope_value)
        )
        # An area with no submissions yet still gets its Notes — leadership may
        # well want to write one about exactly that.
        if _level == "area":
            _render_area_notes(selected_area, selected_zone, selected_district)
        return

    # Accountability floor per area — the first date a missing nightly report
    # counts as a miss on the trend chart. Existing areas floor at
    # SYSTEM_START_DATE; a blank Area_ID marks an area created/renamed at the
    # latest transfer (mission_org_merge_preview.py's convention), which didn't
    # exist under this name before TRANSFER_START_DATE. Mirrors
    # get_alltime_compliance's floors.
    _sys_start = get_config_value("SYSTEM_START_DATE", "")[:10]
    _new_start = max(_sys_start, get_config_value("TRANSFER_START_DATE", "")[:10])
    area_floors = {
        str(_r.get("Area_Name", "")).strip():
            _new_start if str(_r.get("Area_ID", "")).strip() == "" else _sys_start
        for _, _r in _areas_all.iterrows()
        if str(_r.get("Area_Name", "")).strip() in group_areas
    }

    render_group_breakdown(
        scope_kind=scope_kind,
        scope_value=scope_value,
        daily_hist=daily_hist,
        goals=group_goals,
        group_areas=group_areas,
        snap_scope=snap_scope,
        area_floors=area_floors,
    )

    # Compliance calendars sit below the breakdown. Called from the dispatch
    # site, not inside render_group_breakdown, so it renders once after the
    # funnel even on the funnel's early-return path — and it has
    # daily_hist/group_areas/area_floors right here already.
    _render_compliance(
        scope_kind=scope_kind,
        scope_value=scope_value,
        group_areas=group_areas,
        daily_hist=daily_hist,
        area_floors=area_floors,
    )

    if _level == "area":
        _render_area_notes(selected_area, selected_zone, selected_district)


_scope_body()
