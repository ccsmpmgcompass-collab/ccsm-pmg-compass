"""Cascading Zone → District → Area → Find-by-missionary selectors.

Shared by the Breakdowns and Scores pages so the two behave identically. The
deepest selection wins: an Area beats a District beats a Zone; nothing selected
means the whole mission.

Held-outside-the-widget pattern (the reason each box carries a *_val AND a
*_pick key): every box renders with index=None and shows its live value as the
`placeholder`, holding the real value in `<prefix>_<box>_val`. That makes every
pick a change from None, so its `on_change` fires even when the user re-picks the
value already showing — which is what lets a pick reliably RESET every box below
it (Carson: "whenever I select a drop-down ... all drop downs below it reset").
A keyed selectbox would also silently drop a UI-set value when its option list
changes (e.g. a District box re-narrowed by a new Zone pick), so the value has
to live outside it. The Area box's own OPTIONS always span the whole mission
regardless of Zone/District (Carson, 2026-07-17) — only District's list is
narrowed by Zone.

Each page passes its own `prefix` so their selections are independent. The
on_change callbacks are module-level and take the prefix (and the companionship
map) through `args`, so one set of callbacks serves every prefix.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.db.queries import get_submitting_areas
from app.i18n import t

ANY = "— any —"

# Force pure-white text in the selectboxes — both the selected value shown in the
# box and the type-to-filter search input — plus a dark, readable popover menu.
# The app's global rule only reaches the wrapper div, not BaseWeb's inner
# value/input/option nodes, so the selected value would otherwise render dim.
# Injected by the component so every page that uses these selectors matches
# (Carson, 2026-07-17: the Scores dropdowns' text must look exactly like the
# Breakdowns ones). Global CSS, so it styles every selectbox on the page.
_SELECT_CSS = """
<style>
div[data-baseweb="select"] > div,
div[data-baseweb="select"] div[value],
div[data-baseweb="select"] span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}
div[data-baseweb="select"] input {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    caret-color: #a5b4fc !important;
}
/* Type-to-filter dropdown menu: dark surface, readable white options.
   BaseWeb renders these as [role="option"] inside a popover, not a <ul>. */
div[data-baseweb="popover"] ul,
div[data-baseweb="popover"] [role="listbox"] {
    background: #1a1a24 !important;
}
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] [role="option"] {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    background: #1a1a24 !important;
}
div[data-baseweb="popover"] li:hover,
div[data-baseweb="popover"] [role="option"]:hover,
div[data-baseweb="popover"] [role="option"][aria-selected="true"] {
    background: rgba(99,102,241,0.25) !important;
}
</style>
"""

# Both companions sit in ONE label ("Elder A / Elder B") on purpose: BaseWeb's
# type-to-filter substring-matches the whole label, so typing EITHER name finds
# the pair. A per-missionary option list would need two rows for one area.
_COMPANION_COLS = ("Companion1_Name", "Companion2_Name", "Companion3_Name", "Companion4_Name")


def _companionship_label(row) -> str:
    """"Name / Name" for one MISSION_ORG row — blanks and absent columns skipped."""
    names = [str(row.get(c, "") or "").strip() for c in _COMPANION_COLS]
    return " / ".join(n for n in names if n)


def _autofill_zone_district(prefix: str, area_name: str) -> None:
    """Point the Zone and District boxes at the ones `area_name` belongs to, so a
    bare Area (or missionary) pick fills in where that area actually sits.
    MISSION_ORG is the authority. A blank zone/district in the roster leaves that
    box alone rather than blanking a filter the user set deliberately."""
    org = get_submitting_areas()   # st.cache_data — no extra Sheets read
    if org.empty or not {"Area_Name", "Zone", "District"} <= set(org.columns):
        return
    row = org[org["Area_Name"].astype(str).str.strip() == area_name]
    if row.empty:
        return
    zone, district = row.iloc[0]["Zone"], row.iloc[0]["District"]
    if pd.notna(zone) and str(zone).strip():
        st.session_state[f"{prefix}_zone_val"] = str(zone).strip()
    if pd.notna(district) and str(district).strip():
        st.session_state[f"{prefix}_district_val"] = str(district).strip()


def _autofill_zone_for_district(prefix: str, district_name: str) -> None:
    """Point the Zone box at the one `district_name` belongs to (Carson,
    2026-07-24: picking a District — e.g. from the mission-wide list while
    Zone is still "any" — should fill in its Zone automatically, same idea as
    _autofill_zone_district for Area). MISSION_ORG is the authority; a blank
    Zone in the roster leaves the box alone."""
    org = get_submitting_areas()   # st.cache_data — no extra Sheets read
    if org.empty or not {"District", "Zone"} <= set(org.columns):
        return
    row = org[org["District"].astype(str).str.strip() == district_name]
    if row.empty:
        return
    zone = row.iloc[0]["Zone"]
    if pd.notna(zone) and str(zone).strip():
        st.session_state[f"{prefix}_zone_val"] = str(zone).strip()


def _on_zone_pick(prefix: str) -> None:
    picked = st.session_state[f"{prefix}_zone_pick"]
    if picked is None:      # the self-clearing write below re-enters here
        return
    st.session_state[f"{prefix}_zone_val"] = picked
    st.session_state[f"{prefix}_district_val"] = ANY
    st.session_state[f"{prefix}_area_val"] = ANY
    st.session_state[f"{prefix}_zone_pick"] = None


def _on_district_pick(prefix: str) -> None:
    # Every district pick resets the Area (and the missionary box, which mirrors
    # it). index=None makes even re-picking the same district a change from None,
    # so this fires every time — not only when the area falls out of the filter.
    picked = st.session_state[f"{prefix}_district_pick"]
    if picked is None:
        return
    st.session_state[f"{prefix}_district_val"] = picked
    st.session_state[f"{prefix}_area_val"] = ANY
    st.session_state[f"{prefix}_district_pick"] = None
    if picked != ANY:
        _autofill_zone_for_district(prefix, picked)


def _on_area_pick(prefix: str) -> None:
    picked = st.session_state[f"{prefix}_area_pick"]
    if picked is None:
        return
    st.session_state[f"{prefix}_area_val"] = picked
    st.session_state[f"{prefix}_area_pick"] = None
    if picked == ANY:
        return
    _autofill_zone_district(prefix, picked)


def _on_companionship_pick(prefix: str, comp_to_area: dict) -> None:
    """Jump straight to the area a missionary is serving in — a lookup, not a
    filter. Rewrites the boxes above so the area's own zone/district fill in."""
    picked = st.session_state[f"{prefix}_comp_pick"]
    if picked is None:
        return
    st.session_state[f"{prefix}_comp_pick"] = None
    if picked == ANY:
        st.session_state[f"{prefix}_area_val"] = ANY
        return
    area = comp_to_area.get(picked)
    if not area:
        return
    st.session_state[f"{prefix}_area_val"] = area
    _autofill_zone_district(prefix, area)


def render_scope_selectors(
    areas_all: pd.DataFrame,
    *,
    prefix: str,
    zones: list | None = None,
) -> tuple[str, str, str, str | None]:
    """Render the four cascading selectors in a 3-column row (+ a full-width
    missionary box) and return ``(zone, district, area, level)``.

    Values are ``ANY`` when unselected; ``level`` is the deepest selection, one
    of ``{None, "zone", "district", "area"}``. Pass a distinct ``prefix`` per
    page so their selections don't share state. ``zones`` defaults to the zones
    present in ``areas_all``.
    """
    st.markdown(_SELECT_CSS, unsafe_allow_html=True)

    comp_to_area: dict[str, str] = {}
    if not areas_all.empty and "Area_Name" in areas_all.columns:
        for _, _row in areas_all.iterrows():
            _lbl = _companionship_label(_row)
            _nm = str(_row.get("Area_Name", "") or "").strip()
            if _lbl and _nm:
                comp_to_area[_lbl] = _nm     # identical rosters collide; rare, accepted
    comp_labels = sorted(comp_to_area)

    if zones is None:
        zones = (
            sorted(areas_all["Zone"].dropna().astype(str).str.strip().unique().tolist())
            if not areas_all.empty and "Zone" in areas_all.columns else []
        )

    # ── Reset the whole cascade on page ENTRY (Carson, 2026-07-17: "if I select
    # Provo South ... go to a different tab and come back, I want it all reset
    # to any"). Detection: the *_pick keys are WIDGET keys, and Streamlit evicts
    # a widget's session_state entry the moment a script run finishes without
    # rendering it — i.e. any run of another page. The *_val keys are plain
    # session values and survive navigation, which is exactly why they must be
    # cleared here. On-page reruns keep the pick key alive (the selectbox
    # renders every run), so this never fires mid-session.
    if f"{prefix}_zone_pick" not in st.session_state:
        st.session_state[f"{prefix}_zone_val"] = ANY
        st.session_state[f"{prefix}_district_val"] = ANY
        st.session_state[f"{prefix}_area_val"] = ANY

    st.session_state.setdefault(f"{prefix}_zone_val", ANY)
    st.session_state.setdefault(f"{prefix}_district_val", ANY)
    st.session_state.setdefault(f"{prefix}_area_val", ANY)

    col_z, col_d, col_a = st.columns(3)

    # ── Zone ──────────────────────────────────────────────────────────────────
    selected_zone = st.session_state[f"{prefix}_zone_val"]
    if selected_zone != ANY and selected_zone not in zones:
        # A held value can outlive its option (a zone that left MISSION_ORG).
        st.session_state[f"{prefix}_zone_val"] = selected_zone = ANY
    with col_z:
        st.selectbox(
            t("Zone"), [ANY] + zones, key=f"{prefix}_zone_pick", index=None,
            placeholder=selected_zone, on_change=_on_zone_pick, args=(prefix,),
        )

    # ── District (narrowed to the zone) ───────────────────────────────────────
    if selected_zone != ANY:
        districts = sorted(
            areas_all[areas_all["Zone"] == selected_zone]["District"].dropna().unique().tolist()
        )
    elif "District" in areas_all.columns:
        districts = sorted(areas_all["District"].dropna().unique().tolist())
    else:
        districts = []
    selected_district = st.session_state[f"{prefix}_district_val"]
    if selected_district != ANY and selected_district not in districts:
        st.session_state[f"{prefix}_district_val"] = selected_district = ANY
    with col_d:
        st.selectbox(
            t("District"), [ANY] + districts, key=f"{prefix}_district_pick", index=None,
            placeholder=selected_district, on_change=_on_district_pick, args=(prefix,),
        )

    # area_pool still narrows the MISSIONARY box below (unchanged) — kept here
    # so both boxes read the same zone/district filter.
    area_pool = areas_all
    if selected_zone != ANY:
        area_pool = area_pool[area_pool["Zone"] == selected_zone]
    if selected_district != ANY and "District" in area_pool.columns:
        area_pool = area_pool[area_pool["District"] == selected_district]

    # ── Area — options span the WHOLE mission, not just the current Zone/
    # District (Carson, 2026-07-17: typing into Area should pull up every area
    # in the mission, not just the ones the Zone/District boxes have narrowed
    # to). Picking one still autofills Zone/District behind it either way, so
    # jumping to an area outside the current zone no longer needs Zone widened
    # to "any" first — that old workaround is gone.
    filtered = (
        areas_all["Area_Name"].dropna().sort_values().tolist()
        if "Area_Name" in areas_all.columns else []
    )
    selected_area = st.session_state[f"{prefix}_area_val"]
    if selected_area != ANY and selected_area not in filtered:
        st.session_state[f"{prefix}_area_val"] = selected_area = ANY
    with col_a:
        st.selectbox(
            t("Area"), [ANY] + filtered, key=f"{prefix}_area_pick", index=None,
            placeholder=selected_area, on_change=_on_area_pick, args=(prefix,),
        )

    # ── Find by missionary (full width, narrowed to zone + district) ──────────
    comp_placeholder = ANY
    if selected_area != ANY and "Area_Name" in areas_all.columns:
        _sel = areas_all[areas_all["Area_Name"].astype(str).str.strip() == selected_area]
        if not _sel.empty:
            comp_placeholder = _companionship_label(_sel.iloc[0]) or ANY
    _pool_names = (
        set(area_pool["Area_Name"].astype(str).str.strip())
        if "Area_Name" in area_pool.columns else set()
    )
    comp_options = [l for l in comp_labels if comp_to_area.get(l) in _pool_names]
    st.selectbox(
        t("Find by missionary"), [ANY] + comp_options, key=f"{prefix}_comp_pick", index=None,
        placeholder=comp_placeholder, on_change=_on_companionship_pick,
        args=(prefix, comp_to_area),
    )

    level = (
        "area"     if selected_area     != ANY
        else "district" if selected_district != ANY
        else "zone"     if selected_zone     != ANY
        else None
    )
    return selected_zone, selected_district, selected_area, level
