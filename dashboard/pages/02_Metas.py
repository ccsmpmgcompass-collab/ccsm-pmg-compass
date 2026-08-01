import math
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_page_header, render_sidebar, render_section_label,
    render_table, render_companionship_card,
)
from app.config.flavor_loader import flavor, METRIC_LABELS, GOAL_LABELS, GOAL_TO_ACTUAL
from app.config.metric_catalog import (
    key_indicator_metrics,
    metric_data_type,
    metric_options,
    nightly_metrics,
)
from app.i18n.formats import NA, fmt_month_year


def _placeholder_metric() -> str:
    """A real metric key to seed a brand-new expectation row with.

    The first nightly metric this mission asks. Empty string when the catalogue
    is unreadable — the caller then seeds an indicator with no metric, which is
    visibly incomplete, rather than one naming a metric that does not exist.
    """
    return next(iter(nightly_metrics()), "")


def _ki_keys() -> tuple[str, ...]:
    """The mission's Key Indicators, from the live weekly form.

    Was a hardcoded ("gate", "date_metric", "new_found", "pew", "renew",
    "member_lessons") — Utah Provo's six, none of which CCSM collects, so the
    subscript below raised KeyError the moment the catalogue stopped carrying
    Provo's keys. CCSM's are the seven `ki_*_real` values.
    """
    return tuple(key_indicator_metrics())


def _dropdown_metric_labels() -> dict:
    """Labels for metric DROPDOWNS.

    A function, not a module-level dict: the catalogue is read from the sheet,
    so it cannot be built at import time. Merged over METRIC_LABELS so pickers
    show the full descriptive name while compact tiles and tables keep the
    short form.
    """
    return {**dict(METRIC_LABELS), **metric_options()}


DROPDOWN_METRIC_LABELS = _dropdown_metric_labels
from app.db.queries import (
    get_goals_df,
    get_area_goals,
    get_latest_weekly_ki,
    get_weekly_ki,
    get_weekly_form_data,
    get_zones,
    get_submitting_areas,
    get_question_metrics,
    save_area_goals,
    save_all_area_goals,
    delete_area_goals,
    get_recommended_goals,
    get_recommended_monthly_goals,
    get_mission_recommended_goals,
    get_mission_monthly_expectation_total,
    get_area_weekly_expectation,
    get_area_expectation_entry,
    resolve_area_expectations,
    resolve_area_category_label,
    save_area_type_expectations,
    get_all_area_type_indicators,
    is_builtin_area_type_label,
    get_baptisms_actual,
    get_rec_stretch_pct,
    exclude_current_week,
)
from app.db.queries import _AREA_TYPE_LABELS
from app.db.goals_queries import (
    current_month_start,
    get_current_goal,
    upsert_goal,
    get_mission_goals_for_display,
    get_current_area_monthly_goal,
    upsert_area_monthly_goal,
    bulk_upsert_area_monthly_goals,
    get_app_setting,
    set_app_setting,
)

st.set_page_config(
    page_title="CCSM · Goals — PMG Compass",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)
from app.db.queries import get_config_value as _gcv
from app.i18n import t
_mission_name = _gcv("MISSION_NAME", flavor.display_name)
render_page_header(t("Goals"), t('{mission_name} — Goals vs Actuals', mission_name=_mission_name))

# ── Sidebar: Zone filter ──────────────────────────────────────────────────────

zones = get_zones()
# Sentinel translated for display and compared against this same _ALL_ZONES
# below, so a language switch cannot change which zones are shown. It sits in
# a BinOp (["All Zones"] + zones), which neither the extractor nor the codemod
# can see - hence the comment rather than a gate entry.
_ALL_ZONES = t("All Zones")
zone_options = [_ALL_ZONES] + zones
zone_filter = st.sidebar.selectbox(t("Filter by Zone"), zone_options, key="goals_zone_filter")

# ── Key metrics to display — derived from active flavor ──────────────────────

KEY_METRICS = [(k, METRIC_LABELS.get(k, k)) for k in flavor.kpi_highlights]


# Flavor-driven featured goal keys and display labels
_FEATURED_KEYS: frozenset[str] = frozenset(flavor.featured_goals)

# The 6 featured goals ("baptisms", "on_date", ...) are goal-storage keys,
# one-to-one with the 6 headline Key Indicators via GOAL_TO_ACTUAL (baptisms
# -> gate, on_date -> date_metric, etc.) — this is the METRIC-keyspace
# version of _FEATURED_KEYS above, for excluding those same 6 KIs from
# "Other Metrics" (which is keyed by raw metric key, from
# get_question_metrics(), not by goal key). Carson, 2026-07-21: without
# this, "Other Metrics" was ALSO showing Gate/Date/New/Pew/Renew/Mate as
# separate short-labeled boxes — _FEATURED_KEYS' goal keys never matched
# get_question_metrics()'s metric keys, so nothing was ever actually
# excluded there (a real bug, not just a labeling gap) — 6 stray duplicate
# boxes were part of why the grid there looked "off".
_FEATURED_METRIC_KEYS: frozenset[str] = frozenset(
    GOAL_TO_ACTUAL.get(k, k) for k in flavor.featured_goals
)

# Featured goal boxes ARE the 6 Key Indicators, so they use the same long
# "Descriptive Title (ABBREV)" convention as every metric DROPDOWN on this
# page (Carson, 2026-07-21: "Baptisms" -> "Baptized & Confirmed (GATE)") —
# looked up via the underlying KI metric key, not the goal-storage key.
_FEATURED_METRICS: list[tuple[str, str]] = [
    (k, DROPDOWN_METRIC_LABELS().get(
        GOAL_TO_ACTUAL.get(k, k), GOAL_LABELS.get(k, METRIC_LABELS.get(k, k))
    ))
    for k in flavor.featured_goals
]

_GOAL_TO_ACTUAL: dict[str, str] = GOAL_TO_ACTUAL


def _can_edit_goals(user: dict) -> bool:
    """True for MP, APs, and the system owner account."""
    return (
        user.get("role") in ("president", "assistant")
        or str(user.get("email", "")).strip().lower() == "ccsm.pmg.compass@gmail.com"
    )


# ── Helper: % of goal color ──────────────────────────────────────────────────

def _color_pct(val):
    """Return background color based on % of goal."""
    try:
        v = float(val.strip("%")) if isinstance(val, str) else float(val)
    except (ValueError, AttributeError):
        return ""
    if v >= 100:
        return "background-color: #1a6e3c; color: white"   # green
    if v >= 75:
        return "background-color: #7d6008; color: white"   # yellow/amber
    return "background-color: #7b1e1e; color: white"       # red


def _current_month_bounds() -> tuple[date, date]:
    """(first-of-month, first-of-next-month) for the CURRENT real calendar month."""
    start = date.today().replace(day=1)
    next_start = (
        date(start.year + 1, 1, 1) if start.month == 12
        else date(start.year, start.month + 1, 1)
    )
    return start, next_start


def _current_month_weeks() -> float:
    """Weeks in the CURRENT real calendar month (28-31 days -> 4.0-4.43), not
    a fixed yearly average — same dynamic scaling Mission Goals uses (see
    _weeks_in_month there). Used to scale a hypothetical weekly RATE up to a
    monthly value for Area Goals' Monthly Goals section (Mate's lesson
    target) — NOT used for REC pills, which are computed from the area's own
    real monthly totals instead (see get_recommended_monthly_goals)."""
    start, next_start = _current_month_bounds()
    return (next_start - start).days / 7


# ── Main "tabs" ───────────────────────────────────────────────────────────────
# st.tabs() has NO server-side memory of which tab is active — Streamlit's own
# docs confirm ALL tab content renders on every rerun regardless, and the
# selected tab is purely a client-side/browser concept with no `key` param to
# persist it. So ANY widget-triggered rerun (e.g. clicking Mission Goals' FILL
# ALL RECOMMENDED) can snap the visible tab back to the first one — and now
# that BOTH Area Goals and Mission Goals have real interactive widgets (REC
# pills, FILL ALL), "make the busy tab first" (the old workaround) can't cover
# both at once. Fixed by replacing st.tabs() with st.radio(), which — unlike
# st.tabs() — IS backed by st.session_state[key], so the selected section
# reliably survives any rerun no matter which widget triggered it. Styled via
# CSS below to read as a row of tab-like segments instead of default radio
# buttons.
_GOALS_SECTIONS = [
    "Area Goal Customization", "Mission Goals", "Goal Settings",
    "Area Expectation Settings",
]
if "goals_active_section" not in st.session_state:
    st.session_state["goals_active_section"] = _GOALS_SECTIONS[0]
st.markdown(
    "<style>"
    "div[class*='st-key-goals_section_picker'] div[data-testid='stRadio'] > div{"
    "flex-direction:row!important;gap:0.4rem!important;border-bottom:1px solid rgba(255,255,255,0.1);"
    "padding-bottom:0!important;margin-bottom:1rem!important}"
    "div[class*='st-key-goals_section_picker'] div[data-testid='stRadio'] label{"
    "background:transparent!important;border:none!important;border-radius:0!important;"
    "padding:0.5rem 0.2rem!important;margin-right:1.2rem!important;cursor:pointer!important}"
    "div[class*='st-key-goals_section_picker'] div[data-testid='stRadio'] label > div:first-child{display:none!important}"
    "div[class*='st-key-goals_section_picker'] div[data-testid='stRadio'] label div[data-testid='stMarkdownContainer'] p{"
    "font-size:0.95rem!important;font-weight:600!important;color:#9ca3af!important}"
    "div[class*='st-key-goals_section_picker'] div[data-testid='stRadio'] label:has(input:checked){"
    "border-bottom:2px solid #a5b4fc!important}"
    "div[class*='st-key-goals_section_picker'] div[data-testid='stRadio'] label:has(input:checked) "
    "div[data-testid='stMarkdownContainer'] p{color:#f4f4f8!important}"
    "</style>",
    unsafe_allow_html=True,
)
with st.container(key="goals_section_picker"):
    selected_section = st.radio(
        t("Section"),
        _GOALS_SECTIONS,
        key="goals_active_section",
        horizontal=True,
        label_visibility="collapsed",
    )

# An UNSAVED Area Expectation Settings draft dies the moment the editor is
# left (Carson, 2026-07-19: an added-but-not-saved indicator was still
# sitting there after a trip to Breakdowns and back, indistinguishable from
# a saved one — "we don't know which ones have been committed into an
# actual expectation or not"). Any run of this page on a different section
# is proof the editor was left, and a switch to ANOTHER PAGE is covered by
# the same guard: leaving this page lets Streamlit clean the section
# radio's widget state (it wasn't rendered on the other page's runs), so
# returning always lands on the default section first — which runs this
# pop before the user can click back into the settings tab.
if selected_section != "Area Expectation Settings":
    st.session_state.pop("area_exp_rows", None)
    st.session_state.pop("area_exp_next_id", None)


# ══════════════════════════════════════════════════════════════════════════════
# SHARED REC-PILL STYLING — used by both Area Goal Customization and Mission
# Goals, injected once here (a <style> tag applies page-wide regardless of
# which tab's script region emitted it, so this only needs to run once).
# ══════════════════════════════════════════════════════════════════════════════

# Each REC pill is a real (clickable) button — click it to fill that metric's
# goal input with the recommended value. Columns get position:relative so the
# button can be absolutely positioned inside its own number_input's grey box
# (clear of the - / + steppers). The REC buttons are matched by their
# st-key-recbtn_ container class and restyled from the default button look
# into the small blue pill.
#
# IMPORTANT: keys feeding these st-key-* selectors must be UNDERSCORE-joined,
# never hyphen-joined. Streamlit 1.40.0 (pinned in requirements.txt — see
# that file's comment) truncates its key->CSS-class conversion at the FIRST
# HYPHEN: key="recbtn-w-renew" becomes class "st-key-recbtn" (not
# "st-key-recbtn-w-renew"), silently breaking every selector below. Confirmed
# via direct DOM inspection (Playwright) — underscores survive intact.
#
# The recbtn container itself can't be narrowed with width/right — Streamlit
# nests an inner div[data-testid='stButton'] with an inline style="width:164px"
# (matching the full column width) that a plain `width:auto!important` cannot
# beat, so any `right:Nrem` offset is measured from the wrong (full-width) box
# and overshoots. Fix: let the container span the full column
# (left:0;right:0), right-align its content with text-align, then pull the
# button back in with a `transform: translateX()` on the button itself —
# transforms apply post-layout and aren't subject to that width fight.
# pointer-events:none on the (now full-width) container + pointer-events:auto
# on the button keeps the number_input underneath clickable/typeable.
#
# The fraction'd boxes additionally overlay "/ N" right after the typed
# number, via st-key-renewfrac_ (a keyed container, NOT raw st.markdown —
# st.markdown's own wrapper introduces a closer positioned ancestor that
# broke the top-offset anchoring). Only `top` is fixed here; `left` is set
# per-render (see _render_fraction_overlay) since it must shift as the
# goal's digit count changes.
#
# ⚠ ANCHORING IS FROZEN (2026-07-10): COLUMN-TOP anchored, separate
# st.markdown + st.caption rendering. A bottom-anchoring rework (dfeedce)
# shifted things on live and Carson explicitly asked to put it back — never
# restructure the anchoring/rendering again. The top OFFSETS are tuned live
# with Carson's eye (his call beats any local measurement); current values
# per his 2026-07-10 evening feedback ("sits too low / slash wrong / size
# different"): fraction top:2.1rem, full-brightness text (the old 0.75
# alpha read as smaller), and the slash rendered at 0.85em via .fracslash
# so it doesn't tower over / descend below the digits. Known accepted wart:
# if a long label ever wraps to two lines, that box's overlays sit high
# over the label — do not re-anchor to fix that.
st.markdown(
    "<style>"
    "div[data-testid='stColumn']{position:relative}"
    "div[class*='st-key-recbtn_']{position:absolute!important;top:2.05rem;left:0;right:0;z-index:5;text-align:right!important;pointer-events:none;min-height:0!important;margin:0!important;padding:0!important}"
    "div[class*='st-key-recbtn_'] button{pointer-events:auto;transform:translateX(-4.2rem)!important;background:rgba(99,102,241,0.15)!important;border:1px solid rgba(99,102,241,0.4)!important;border-radius:999px!important;padding:0.1rem 0.45rem!important;min-height:0!important;height:auto!important;line-height:1.25!important;white-space:nowrap!important}"
    "div[class*='st-key-recbtn_'] button:hover{background:rgba(99,102,241,0.30)!important;border-color:rgba(99,102,241,0.6)!important;transform:translateX(-4.2rem)!important;box-shadow:none!important}"
    "div[class*='st-key-recbtn_'] button p{font-size:0.62rem!important;font-weight:700!important;letter-spacing:0.04em!important;color:#a5b4fc!important}"
    "div[class*='st-key-fillall'] button{background:rgba(99,102,241,0.15)!important;border:1px solid rgba(99,102,241,0.4)!important;border-radius:999px!important;padding:0.35rem 1rem!important;min-height:0!important;height:auto!important;white-space:nowrap!important}"
    "div[class*='st-key-fillall'] button:hover{background:rgba(99,102,241,0.30)!important;border-color:rgba(99,102,241,0.6)!important;transform:none!important;box-shadow:none!important}"
    "div[class*='st-key-fillall'] button p{font-size:0.72rem!important;font-weight:700!important;letter-spacing:0.05em!important;color:#a5b4fc!important}"
    # ROOT CAUSE FOUND (2026-07-21), replacing months of top-offset guessing:
    # the "/N" <p> tag was never given its own line-height, so it fell back
    # to Streamlit's default paragraph line-height (1.6 = 25.6px) — but the
    # number_input's own text sits in a box whose effective line-height is
    # 1.4 (22.4px). Two DIFFERENT line-height boxes, even carefully
    # top-aligned, center their text at two DIFFERENT absolute pixel
    # positions, no matter how the outer "top" offset is tuned — this is why
    # every prior "nudge top by Npx" attempt (2026-07-10, then again
    # 2026-07-21 in the opposite direction) could never fully land: the two
    # elements were fundamentally never going to line up while their
    # line-heights differed, and a top-only fix can only move the whole box,
    # never fix the mismatch INSIDE it.
    #
    # Fix: give the fraction's line-height the SAME value (1.4) as the
    # input's, and set the container's `top` to the input's own CONTENT-box
    # top (its outer top + 8px padding-top) instead of a hand-picked value —
    # both boxes now have identical height, identical line-height, identical
    # font, and identical top, so they center their text the same way by
    # construction. Verified directly against the LIVE deployed app (not a
    # local repro, which is what misled every earlier attempt): computed
    # box-center delta went from several visible pixels to 0.016px, and a
    # zoomed screenshot of 3 different boxes (NM Lessons "4/15", LSI
    # Follow-Ups "7/19", MMMs Sent "38/70") confirmed the numerator and
    # denominator now sit on the exact same baseline. 28.8125px (input's
    # own top offset within the column, for a 1-line label) + 8px
    # (input's padding-top) = 36.8125px = 2.30rem — the input's real
    # content-box top, measured live.
    #
    # ⚠ 2026-07-21 (later): a prior "close the last 0.21px" pass (bbfce03)
    # pushed this to 2.31rem (36.96px), but re-measuring the LIVE app shows
    # that OVERSHOT: the overlay's content top then sat 0.141px BELOW the
    # input's (36.953 vs 36.813), so the denominator rendered ~0.14px low
    # relative to the typed number. At DPR 1 that's invisible (both snap to
    # the same device pixel), but at Windows display scaling (125%/150%,
    # DPR 1.25/1.5 — what most users actually run) that slack can cross a
    # device-pixel boundary and snap the denominator a full pixel LOW, which
    # is exactly how Carson saw it ("sits too low") while a DPR-1 automation
    # browser measured it fine. Reverted to 2.30rem so the overlay's content
    # top matches the input's content-box top to within 0.01px, removing the
    # slack that was crossing the boundary. Do NOT re-add the 0.21px.
    "div[class*='st-key-renewfrac_']{position:absolute!important;top:2.30rem;z-index:4;pointer-events:none;width:auto!important;min-height:0!important;margin:0!important;padding:0!important}"
    # font-family: design_system.py's global `p` rule forces the app font
    # (SF Pro/Segoe UI), but the number_input's typed text keeps BaseWeb's
    # own "Source Sans Pro" — without this override the "/ N" sits right
    # next to the typed number in a visibly different font, which reads as
    # misaligned/differently-sized even though both compute to 1rem.
    # color is FULL brightness on purpose (same #f4f4f8 as the input text) —
    # the earlier rgba(...,0.75) dimming made the denominator read as
    # smaller/lighter than the typed number (Carson: "size still looks
    # different"). line-height:1.4 matches the input's own effective
    # line-height exactly (see the top: comment above — this is the actual
    # fix, not the top offset).
    "div[class*='st-key-renewfrac_'] p{font-family:\"Source Sans Pro\",sans-serif!important;font-size:1rem!important;font-weight:400!important;line-height:1.4!important;color:#f4f4f8!important;white-space:nowrap!important}"
    # .fracslash was 0.85em (2026-07-10: "doesn't tower over or descend
    # below the digits") — re-measured 2026-07-21 with real ink bounds
    # (Range.getBoundingClientRect, not eyeballed) against the CURRENT
    # font/line-height setup and the slash's ink height at FULL size (1em)
    # is exactly 20px, byte-identical to the digits' own ink height, with
    # zero extension above or below them. The 0.85em shrink was actively
    # making the "/" read as a different size than the digits it sits next
    # to (Carson: "make it the exact same text size") — full size is both
    # correct and matches the digits exactly, verified live before this
    # change.
    "div[class*='st-key-renewfrac_'] p .fracslash{font-size:1em}"
    # Bent-line grouping for each Weekly/Monthly cadence under Area
    # Expectation Settings (Carson, 2026-07-22: "make the top on the
    # vertical lines turn and underline weekly or monthly"). Two strokes,
    # same color/weight so they read as one continuous line that turns a
    # corner: an underline sized to just the "Weekly Goals"/"Monthly
    # Goals" caption text (display:inline-block so the border-bottom
    # doesn't stretch to the container's full width), then a vertical
    # rail on the indicator-boxes container directly below it, flush at
    # the same left edge (x=0 in both, neither container is itself
    # indented) so the underline's left end and the rail's top end meet.
    # Both dimmer/thinner than the category's own emphasis bar (4px solid
    # gradient) so this reads as subordinate to it, not a competing
    # divider.
    "div[class*='st-key-cadence_rail_'] [data-testid='stCaptionContainer'] p{display:inline-block!important;border-bottom:2px solid rgba(99,102,241,0.45)!important;padding-bottom:0.2rem!important;margin-bottom:0!important}"
    "div[class*='st-key-cadence_rows_']{border-left:2px solid rgba(99,102,241,0.45);padding-left:0.9rem;padding-top:0.5rem;margin-bottom:0.5rem}"
    # Areas Involved (Area Expectation Settings) must look and open EXACTLY
    # like a normal selectbox but be pure DISPLAY — no option is clickable/
    # selectable, and no per-option hover tooltip (Carson, 2026-07-22, 4th
    # pass on this one widget). The open OPTION LIST renders through a
    # shared floating-ui portal at the document BODY level (confirmed live
    # in devtools) — it is NOT a DOM descendant of this widget's own
    # st-key-area_exp_areas_involved_ container, so a normal ancestor-
    # scoped selector can't reach it, and disabling every li[role='option']
    # page-wide would silently break every OTHER selectbox on this page
    # (Indicator/Cadence pickers, the area-override picker, etc. would all
    # stop being clickable too).
    #
    # Fix: :has() bridges the gap without an ancestor relationship. Only
    # ONE dropdown can be open at a time (BaseWeb auto-closes any other
    # before opening a new one), so "the page currently has an Areas
    # Involved trigger in its expanded (aria-expanded=true) state" and
    # "the option list currently visible in the DOM belongs to THAT
    # trigger" are the same fact at any given instant — this rule reads as
    # "while one of THIS widget's triggers is open, options page-wide are
    # inert," which in practice only ever fires for its own list, since no
    # other dropdown can be simultaneously open to be caught by it.
    # Verified live: opening Areas Involved makes its own options
    # unclickable and untooltipped, while the Indicator/Cadence/area-
    # override selectboxes elsewhere on this same page remain fully normal.
    "body:has(div[class*='st-key-area_exp_areas_involved_'] [aria-expanded='true']) li[role='option']{pointer-events:none!important}"
    # Long area names were still ellipsis-truncated inside the open list
    # (Carson, 2026-07-22: "I've asked you not to do that ... wrap that
    # text ... two rows instead"). The truncation lives 3 levels inside
    # each option, on the innermost of two divs BaseWeb wraps the label in
    # (a display:table / display:table-cell pair — the table-cell one
    # carries text-overflow:ellipsis;white-space:nowrap;overflow:hidden;
    # found live via getComputedStyle at each nesting level, not guessed).
    # Overriding those three properties alone let the label wrap, but each
    # <li> itself has a FIXED height:40px (not min-height) — with
    # overflow:visible that let a 2-line label render, but the LI still
    # only occupied 40px of LAYOUT space, so the wrapped 2nd line visually
    # overlapped the next option below it instead of pushing it down.
    # height:auto (min-height 40px keeps single-line rows their original
    # size) makes the <li> itself grow to fit — but this list is virtualized
    # (react-window): each <li> is position:absolute with an inline top:Npx
    # set in fixed 40px increments by JS, not normal document flow. Letting
    # one row visually grow past 40px does NOT push the next row's (still
    # fixed-at-40px-multiples) top down, so two consecutive wrapped rows
    # actually overlapped by ~12px live (found 2026-07-23 measuring real
    # DOM rects on the live app — the 2026-07-22 "no overlap" note above was
    # wrong, never verified against the next sibling's rect). Fix: at the
    # original 16px font, two lines need a 20px line-height floor just to
    # avoid the lines themselves touching, leaving zero of the fixed 40px
    # slot to spare for breathing room between them. line-height is capped
    # at 20px per line no matter the font size (2 lines can never exceed
    # the fixed 40px slot without overlapping the next row), so the only
    # lever for MORE gap is a smaller font, which shrinks the natural ink
    # height and frees more of that 20px as pure spacing. Carson asked
    # twice for more room between the lines, so the font comes down to
    # 12px (natural single-line ink height 15px, measured live via
    # Range.getClientRects) at line-height 20px: a real ~5px gap between
    # the two lines' ink (was ~2px at 14px font), still 2 x 20px = 40px
    # total so the row stays exactly 40px with zero overlap into the next
    # one (re-verified live on "Franklin Park/East Bay 2nd/Sunset 2nd (EB)
    # Spanish", the longest wrapping name in the list).
    "body:has(div[class*='st-key-area_exp_areas_involved_'] [aria-expanded='true']) li[role='option']{height:auto!important;min-height:40px!important}"
    "body:has(div[class*='st-key-area_exp_areas_involved_'] [aria-expanded='true']) li[role='option'] .stTooltipHoverTarget div{white-space:normal!important;text-overflow:clip!important;overflow:visible!important;word-break:break-word!important;font-size:12px!important;line-height:20px!important}"
    # Wrapped multi-line labels with no separator between rows read as one
    # blob (Carson, 2026-07-22). A thin rule between consecutive options
    # (not after the last one, so it doesn't double up with the list's own
    # bottom edge) breaks that up. box-shadow instead of border-bottom:
    # a real border adds 1px to the row's layout height, which is exactly
    # the 1px of slack a 2-line wrapped row no longer has once it's sized
    # to fit the fixed 40px slot above — box-shadow paints the same line
    # without adding to box height, so it can't reopen the overlap.
    "body:has(div[class*='st-key-area_exp_areas_involved_'] [aria-expanded='true']) li[role='option']:not(:last-child){box-shadow:0 1px 0 rgba(99,102,241,0.35)!important}"
    "</style>",
    unsafe_allow_html=True,
)

# Carson (2026-07-23): open the Areas Involved dropdown, scroll the page
# without closing it, and the option list stays put instead of following
# its trigger. Confirmed live: the popover is positioned once, in absolute
# coordinates, when it opens, and never re-anchors on scroll — scroll the
# page's real scroll container (section.stMain, not window/the iframe) by
# 300px and the trigger moves up 300px while the popover's top stays byte-
# for-byte identical. That's a gap in the underlying BaseWeb/Streamlit
# component itself (no scroll listener wired to this scroll container),
# not something reachable from here with CSS. A first pass just froze
# background scroll while the menu was open, but Carson wants scrolling to
# keep working and the menu to close itself instead. st.markdown's
# unsafe_allow_html does not execute <script> tags (Streamlit strips them;
# components.html is the documented escape hatch for real script
# execution, already used elsewhere in this codebase for the Breakdowns
# trend chart's legend-isolate handler). This component's own iframe
# reaches up via window.parent to the main app document (same-origin,
# same pattern as reading the app's DOM from outside in devtools) to wire
# a real scroll listener once per page load — guarded by a flag on
# window.parent itself so the listener isn't re-added every time this
# component remounts on a Streamlit rerun. On scroll, if the dropdown's
# trigger is aria-expanded, it dispatches a real mousedown+mouseup on
# <body> — confirmed live that a bare .click() does NOT close BaseWeb's
# popover (its outside-click detection listens for mousedown, not click),
# but mousedown+mouseup does, reliably, in isolation.
components.html(
    """
    <script>
    (function() {
      var parentDoc = window.parent.document;
      if (window.parent.__areasInvolvedScrollCloseWired) return;
      window.parent.__areasInvolvedScrollCloseWired = true;
      var main = parentDoc.querySelector('section.stMain');
      if (!main) return;
      main.addEventListener('scroll', function() {
        var openTrigger = parentDoc.querySelector(
          "div[class*='st-key-area_exp_areas_involved_'] [aria-expanded='true']"
        );
        if (openTrigger) {
          parentDoc.body.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
          parentDoc.body.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
        }
      }, {passive: true});
    })();
    </script>
    """,
    height=0,
)


def _apply_rec(widget_key: str, value: int) -> None:
    """on_click callback: write the recommended value into the goal input's
    session state so the number_input shows it on the following rerun."""
    st.session_state[widget_key] = int(value)


def _render_rec_pill(prefix: str, key: str, widget_key: str, rec_value: int) -> None:
    """Render one clickable REC pill overlaid on the number_input `widget_key`
    was just drawn into (see the st-key-recbtn_ CSS above for the
    positioning). Shared by every REC pill on the page — Area Goals and
    Mission Goals, including the boxes that also carry a "/ N" fraction
    overlay (Renew, Recent Convert Attendance) — so they all look and behave
    identically."""
    with st.container(key=f"recbtn_{prefix}_{key}"):
        st.button(
            t('REC {rec_value}', rec_value=rec_value),
            key=f"recval_{prefix}_{key}",
            on_click=_apply_rec,
            args=(widget_key, rec_value),
        )


def _render_fraction_overlay(prefix: str, key: str, current_value: int, total: int) -> None:
    """Overlay "/ {total}" right after the typed number, inside the box, via
    the shared st-key-renewfrac_ CSS above (top is fixed there; left is set
    per-render here since it must shift as the goal's digit count changes).
    Shared by every fraction'd box on the page — Area Goals (weekly grid +
    Monthly Goals) and Mission Goals (featured + Other Metrics expander) —
    so they all look identical. ⚠ Rendering structure is part of the frozen
    user-approved position (see the CSS comment above) — keep the separate
    st.markdown + st.caption exactly as-is."""
    # Measured against the input's own metrics (Playwright, Streamlit 1.40.0):
    # the typed text starts 9px (1px border + 8px padding = 0.5625rem) from
    # the column's left edge, each digit of 16px Source Sans Pro is ~8.9px
    # (~0.55rem), and a natural single-space gap before the slash is ~4.4px
    # (~0.275rem). 0.5625 + 0.275 ≈ 0.84. The old 1.15 base left a full
    # character-width hole between the number and the "/".
    _ndigits = len(str(int(current_value)))
    _frac_left = 0.84 + 0.55 * _ndigits
    # Scope the left-shift to THIS box's own container class, not the shared
    # `st-key-renewfrac_` prefix — otherwise every fraction overlay injects a
    # style targeting ALL of them and only the last-rendered box's digit count
    # wins, so a double-digit goal (e.g. "25") stays crammed against its "/ N"
    # while a single-digit sibling elsewhere in the grid dictates the offset.
    _frac_cls = f"st-key-renewfrac_{prefix}_{key}"
    st.markdown(
        f"<style>div[class*='{_frac_cls}']"
        f"{{left:{_frac_left:.2f}rem!important}}</style>",
        unsafe_allow_html=True,
    )
    with st.container(key=f"renewfrac_{prefix}_{key}"):
        # The slash is wrapped so the shared CSS can size it down (.fracslash,
        # 0.85em) — Source Sans's full-size "/" towers over and descends
        # below the digits, which read as misaligned to Carson.
        st.caption(f"<span class='fracslash'>/</span> {total}", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MISSION GOALS
# ══════════════════════════════════════════════════════════════════════════════

if selected_section == "Mission Goals":

    # Mission Goals are set once per calendar MONTH (not per week — see
    # current_month_start()). "Actuals" for comparison are therefore summed
    # across every completed week whose week_end_date falls within the
    # current month (month-to-date), not just the latest single week.
    month_start = current_month_start()
    _month_start_date = date.fromisoformat(month_start)
    _next_month_start = (
        date(_month_start_date.year + 1, 1, 1) if _month_start_date.month == 12
        else date(_month_start_date.year, _month_start_date.month + 1, 1)
    )
    # Weeks in THIS specific month (28-31 days -> 4.0-4.43 weeks), not a fixed
    # yearly average — so a short month (February) gets a proportionally
    # smaller monthly REC/target than a long one (January, March), instead of
    # every month using the same ~4.348 constant regardless of its real length.
    _weeks_in_month = (_next_month_start - _month_start_date).days / 7
    # Sundays in THIS specific month — church attendance (Renew / Recent
    # Convert Attendance) can only happen on a Sunday, so its monthly REC
    # scales off the ACTUAL Sunday count (4 or 5, depending on how the month
    # lines up with the calendar), not the generic days/7 weeks-in-month
    # figure above, which is a fine approximation for daily-ish metrics but
    # not exact for a strictly-weekly, Sunday-only event.
    _sundays_in_month = sum(
        1 for i in range((_next_month_start - _month_start_date).days)
        if (_month_start_date + timedelta(days=i)).weekday() == 6
    )
    def _month_to_date(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "week_end_date" not in df.columns:
            return df
        wk = pd.to_datetime(df["week_end_date"], errors="coerce").dt.date
        return df[wk.notna() & (wk >= _month_start_date) & (wk < _next_month_start)]

    actual_df = _month_to_date(get_weekly_ki())
    wf_df = get_weekly_form_data()
    wf_month_td = _month_to_date(wf_df)
    current_goal_row = get_current_goal(month_start)

    # ── Section A: Set Mission Goals (MP/AP only) ─────────────────────────────

    if _can_edit_goals(user):
        render_section_label(t("Set Mission Goals — This Month"))

        def _goal_val(key: str) -> int:
            if not current_goal_row:
                return 0
            return int(current_goal_row.get(key, 0) or 0)

        def _extra_val(key: str) -> int:
            if not current_goal_row:
                return 0
            extra = current_goal_row.get("extra_goals") or {}
            return int(extra.get(key, 0) or 0)

        # Mission-wide REC: same +10% stretch formula as Area Goals' REC pills,
        # based on the WHOLE MISSION'S own history (every area's weeks summed
        # together, then averaged) — but scaled up from a weekly to a
        # MONTHLY-sized suggestion using THIS month's actual week count
        # (_weeks_in_month, e.g. 4.0 for February vs 4.43 for January — not a
        # fixed yearly average), since these goals are now set once per
        # month, not once per week. Keyed by raw metric key (e.g. "gate",
        # "renew"); featured goal keys (e.g. "baptisms") are translated via
        # _GOAL_TO_ACTUAL before lookup.
        _weekly_recommended = get_mission_recommended_goals()
        mission_recommended = {
            k: max(1, math.ceil(v * _weeks_in_month)) for k, v in _weekly_recommended.items()
        }
        # Church-attendance indicators are Sunday-only events — override their
        # generic _weeks_in_month scaling with the actual Sunday COUNT for this
        # month (4 or 5, depending on calendar alignment) rather than the days/7
        # estimate used for every other metric. Scaling by weeks inflates the
        # bar with Sundays the month does not contain: a 31-day month's 4.4286
        # "weeks" against its real 4 Sundays.
        #
        # Identified from the KI catalogue instead of a hardcoded ("renew",
        # "pew") — Provo's two keys, neither of which CCSM collects, so no
        # CCSM indicator ever got this correction.
        for _sunday_key in (k for k in key_indicator_metrics()
                            if "sacrament" in k or "church" in k):
            if _sunday_key in _weekly_recommended:
                mission_recommended[_sunday_key] = max(
                    1, math.ceil(_weekly_recommended[_sunday_key] * _sundays_in_month)
                )
        # Provo computed three hypothetical mission-wide denominators here —
        # Recent-Convert attendance potential (from rc_total), an NM Lessons
        # target and an MMM target — as fallbacks for goals with no saved
        # expectation. CCSM collects none of those three metrics, so each
        # evaluated to its max(1, 0) floor of 1, and any goal falling back to
        # one would have rendered as "goal / 1": a fraction that looks
        # meaningful and is not. See _mission_denominator, which no longer
        # falls back at all.

        def _mission_denominator(goal_key: str) -> int | None:
            """One mission goal input's "/N" fraction denominator, or None
            for no fraction.

            DYNAMIC: the mission-wide expectation total for the input's
            underlying metric, sized to THIS month exactly (per-area monthly
            figures as-is, weekly × the month's exact weeks, Sunday-only
            church-attendance KIs × the month's Sunday count — see
            get_mission_monthly_expectation_total). Any indicator given an
            expectation in Area Expectation Settings gets a fraction here the
            moment it is saved.

            Provo also carried four derived fallbacks for metrics with no saved
            expectation — renew → the mission's maximum possible Recent-Convert
            attendances (from rc_total), member/NM lessons → a hypothetical
            lesson target, mmm_sent → an MMM target, lsi_followups → whatever
            was typed into the LSI Given box. All four named metrics CCSM does
            not collect, so each could only ever have evaluated to 0 or crashed
            on a missing widget. They are gone: a metric with no expectation now
            renders with no fraction, which says "nobody has set the bar" rather
            than inventing one.
            """
            actual = _GOAL_TO_ACTUAL.get(goal_key, goal_key)
            exp_total = get_mission_monthly_expectation_total(actual, month_start)
            if exp_total > 0:
                return exp_total
            return None
        st.caption(
            t("REC is a light stretch goal — about {get_rec_stretch_pct}% above the whole mission's typical MONTHLY performance across every area, for a month this length — to nudge the mission to do slightly better. Church-attendance indicators scale by the number of Sundays this month, since attendance is a once-a-week event, rather than the general weeks-in-month figure used for other metrics. Any goal whose indicator has expectations saved in Area Expectation Settings shows goal / a hypothetical mission-wide target for this month — every area at its own expectation, summed and sized to this month's exact length — not based on actual data. A goal with no expectation saved shows no fraction at all.", get_rec_stretch_pct=get_rec_stretch_pct())
        )

        def _apply_all_mission_rec(recommended: dict) -> None:
            """on_click callback: fill every mission goal input (featured +
            other) with its recommended value in one go."""
            for key, _label in _FEATURED_METRICS:
                actual_key = _GOAL_TO_ACTUAL.get(key, key)
                if actual_key in recommended:
                    st.session_state[f"mission_goal_{key}"] = int(recommended[actual_key])
            for key, _label, _ft in get_question_metrics():
                if key not in _FEATURED_METRIC_KEYS and key in recommended:
                    st.session_state[f"mission_extra_{key}"] = int(recommended[key])

        if mission_recommended:
            with st.container(key="fillallrec_mission"):
                st.button(
                    t("FILL ALL RECOMMENDED"),
                    key="fillall_mission_btn",
                    on_click=_apply_all_mission_rec,
                    args=(mission_recommended,),
                )

        # Featured metrics — 3-per-row grid (2026-07-21: was 4-per-row, but
        # these are now the long "Descriptive Title (ABBREV)" KI names, not
        # short one-word labels — at 4-per-row's narrower column width,
        # "New Members at Sacrament Meeting (RENEW)" wrapped to a 2nd line,
        # which pushed the actual input box down while its "/N" fraction
        # overlay (position:absolute, a fixed top offset calibrated for a
        # 1-line label — see the frozen CSS block above) stayed put and
        # landed ON the wrapped label instead of next to the typed number
        # (Carson, 2026-07-21 screenshot: "the renew boxs text is way off").
        # 3-per-row's ~33% wider column keeps every one of the 6 KI labels
        # on one line, so the existing 1-line-calibrated overlay offsets
        # stay correct for all of them without needing a second, wrap-aware
        # offset (which would itself be fragile — exactly which label wraps
        # depends on its own word-break points at a given width, not just
        # character count: MATE's label is longer than RENEW's but didn't
        # wrap at the same 4-per-row width RENEW broke at). 6 goals ÷ 3 also
        # divides evenly into two full rows, instead of 4-per-row's uneven
        # trailing row of 2. Session-state pre-seeding (not value=) matches
        # Area Goals' pattern — passing value= on every rerun AND writing to
        # session_state from the REC/FILL ALL callbacks trips Streamlit's
        # "widget had both a default value and a Session State API write"
        # warning banner.
        featured_values: dict[str, int] = {}
        for i in range(0, len(_FEATURED_METRICS), 3):
            cols = st.columns(3)
            for col, (key, label) in zip(cols, _FEATURED_METRICS[i : i + 3]):
                with col:
                    widget_key = f"mission_goal_{key}"
                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = _goal_val(key)
                    featured_values[key] = st.number_input(
                        label,
                        min_value=0,
                        step=1,
                        key=widget_key,
                    )
                    _den = _mission_denominator(key)
                    if _den:
                        _render_fraction_overlay("mg", key, featured_values[key], _den)
                    actual_key = _GOAL_TO_ACTUAL.get(key, key)
                    if actual_key in mission_recommended:
                        _render_rec_pill("mg", key, widget_key, mission_recommended[actual_key])

        # Other metrics expander. rc_total is excluded entirely — same as Area
        # Goals, it's a running snapshot count, not a goal-able production
        # number (see get_latest_rc_total's docstring); its latest value is
        # only ever shown as the fixed denominator next to Renew's fraction.
        # The 6 featured KIs (Gate/Date/New/Pew/Renew/Mate) are excluded too —
        # they already have their own box up in Featured Metrics above; see
        # _FEATURED_METRIC_KEYS' comment for why _FEATURED_KEYS (goal keys)
        # couldn't do this exclusion on its own.
        # report_date is excluded too: it's asked on BOTH the Nightly and
        # Weekly forms and shares that same Metric_Key in QUESTIONS_CONFIG
        # (CcsmData.gs' CCSM_NIGHTLY_QUESTIONS/CCSM_WEEKLY_QUESTIONS each
        # define a 'report_date' question). get_question_metrics() here is
        # called with no form_type filter (unlike Area Goals' nightly_defs/
        # weekly_defs split), so both rows came through as two entries with
        # the same key, producing two `mission_extra_report_date` boxes and
        # crashing with StreamlitDuplicateElementKey. It's also a DATE field
        # (which date the report covers), not a countable production number
        # a "goal" makes sense for.
        all_metrics = get_question_metrics()
        _seen_other_keys: set[str] = set()
        other_metrics = []
        for k, lbl, ft in all_metrics:
            if k in _FEATURED_METRIC_KEYS or k == "report_date":
                continue
            # "rc_total" used to be excluded here too — Provo's running
            # recent-convert headcount, which no goal makes sense for. CCSM has
            # no such key, so the exclusion did nothing; two CCSM-specific ones
            # take its place.
            #
            # `_meta` keys are the companionship's OWN weekly goal, collected on
            # the weekly form beside each `_real` achievement. A goal box for
            # one asks leadership to set a goal for a goal, and its saved value
            # would then be compared against a target rather than an outcome.
            if k.endswith("_meta"):
                continue
            # CHOICE metrics carry no summable number — CCSM's `effort` is
            # answered Todo / La mayor parte / Algo. A weekly numeric goal for
            # one is meaningless, and _num() would coerce the answer to 0 and
            # make it look met. Detected via Data_Type, never by inspecting
            # values.
            if metric_data_type(k) == "CHOICE":
                continue
            # Belt-and-suspenders: any other Metric_Key that ends up defined
            # on both forms (a future CcsmData.gs edit repeating the
            # report_date mistake above) would otherwise reach st.number_input
            # twice with the identical widget key and crash the whole page
            # with StreamlitDuplicateElementKey — silently drop the repeat
            # instead, keeping the first (Nightly-ordered) definition.
            if k in _seen_other_keys:
                continue
            _seen_other_keys.add(k)
            other_metrics.append((k, lbl, ft))
        extra_values: dict[str, int] = {}
        if other_metrics:
            with st.expander(t("Other Metrics")):
                for i in range(0, len(other_metrics), 4):
                    # min(4, remaining) instead of a flat 4 (Carson, 2026-07-21:
                    # "boxes look off") — a flat st.columns(4) on a trailing
                    # partial row (e.g. 1 leftover box) squeezes that box into
                    # a quarter-width column with 3 empty ones beside it;
                    # sizing the row to what's actually left makes every row's
                    # boxes a consistent, proportional width.
                    _row = other_metrics[i : i + 4]
                    cols = st.columns(len(_row))
                    for col, (key, label, _ft) in zip(cols, _row):
                        with col:
                            widget_key = f"mission_extra_{key}"
                            if widget_key not in st.session_state:
                                st.session_state[widget_key] = _extra_val(key)
                            extra_values[key] = st.number_input(
                                label,
                                min_value=0,
                                step=1,
                                key=widget_key,
                            )
                            _den = _mission_denominator(key)
                            if _den:
                                _render_fraction_overlay("me", key, extra_values[key], _den)
                            if key in mission_recommended:
                                _render_rec_pill("me", key, widget_key, mission_recommended[key])

        _month_label = fmt_month_year(_month_start_date)

        if st.button(t("Save Mission Goals"), type="primary", key="mission_goal_save"):
            row, err = upsert_goal(
                month_start=month_start,
                baptisms=featured_values.get("baptisms", 0),
                # "confirmations" is no longer a featured input (removed from
                # featured_goals), but upsert_goal still has a dedicated column
                # for it — preserve whatever's already saved instead of
                # silently zeroing it out on every future save.
                confirmations=_goal_val("confirmations"),
                on_date=featured_values.get("on_date", 0),
                at_sacrament=featured_values.get("at_sacrament", 0),
                new_people_to_teach=featured_values.get("new_people_to_teach", 0),
                rc_at_church=featured_values.get("rc_at_church", 0),
                members_nonmember_lessons=featured_values.get("members_nonmember_lessons", 0),
                extra_goals=extra_values,
                set_by=user.get("email", ""),
            )
            if err:
                st.error(t('Failed to save: {err}', err=err))
            else:
                set_by = row.get("set_by", "") if row else user.get("email", "")
                st.success(t('Mission goals saved. Last set by **{set_by}** · month of {month_label}', set_by=set_by, month_label=_month_label))
                st.rerun()

        if current_goal_row:
            set_by = current_goal_row.get("set_by", "")
            ws = current_goal_row.get("month_start", "")
            if set_by:
                ws_label = fmt_month_year(ws)
                if ws_label == NA:
                    ws_label = ws
                st.caption(t('Last set by {set_by} · month of {ws_label}', set_by=set_by, ws_label=ws_label))

        st.divider()

    # ── Section B: Mission Goals vs Actuals ───────────────────────────────────

    render_section_label(t("Mission Goals vs Actuals — This Month"))

    mission_goals_display = get_mission_goals_for_display(month_start)

    if not mission_goals_display:
        st.info("No mission-wide goals set for this month yet." +
                (" Use the form above to add them." if _can_edit_goals(user) else ""))
    else:
        mission_rows = []
        for key, label in _FEATURED_METRICS:
            goal_val = float(mission_goals_display.get(key, 0) or 0)
            actual_key = _GOAL_TO_ACTUAL.get(key, key)
            actual_val = 0.0
            # Baptisms: the weekly-form "gate" field under-counts badly (missionaries
            # don't fill it in reliably — verified ~18-20 vs an official 41 for one
            # month). Prefer the real Tableau-sourced count; fall back to gate only
            # if no Tableau capture exists yet for this month.
            tableau_baptisms = get_baptisms_actual(month_start) if key == "baptisms" else None
            if tableau_baptisms is not None:
                actual_val = float(tableau_baptisms)
            elif not wf_month_td.empty and actual_key in wf_month_td.columns:
                actual_val = float(wf_month_td[actual_key].sum())
            elif not actual_df.empty and actual_key in actual_df.columns:
                actual_val = float(actual_df[actual_key].sum())
            pct_str = f"{round(actual_val / goal_val * 100)}%" if goal_val > 0 else "—"
            mission_rows.append({
                "Metric":    label,
                "Goal":      int(goal_val),
                "Actual":    int(actual_val),
                "% of Goal": pct_str,
            })

        # Non-zero extra_goals
        extra_goal_data = {k: v for k, v in mission_goals_display.items()
                           if k not in _FEATURED_KEYS and v}
        if extra_goal_data:
            all_metrics_lookup = {k: lbl for k, lbl, _ in get_question_metrics()}
            for key, goal_val in extra_goal_data.items():
                actual_val = 0.0
                if not actual_df.empty and key in actual_df.columns:
                    actual_val = float(actual_df[key].sum())
                pct_str = f"{round(actual_val / goal_val * 100)}%" if goal_val > 0 else "—"
                mission_rows.append({
                    "Metric":    all_metrics_lookup.get(key, key),
                    "Goal":      int(goal_val),
                    "Actual":    int(actual_val),
                    "% of Goal": pct_str,
                })

        mission_tbl = pd.DataFrame(mission_rows)

        def _style_mission(row):
            styles = [""] * len(row)
            pct_idx = list(row.index).index("% of Goal")
            styles[pct_idx] = _color_pct(row["% of Goal"])
            return styles

        styled_mission = mission_tbl.style.apply(_style_mission, axis=1)
        render_table(styled_mission)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AREA GOAL CUSTOMIZATION
# ══════════════════════════════════════════════════════════════════════════════

if selected_section == "Area Goal Customization":

    render_section_label(t("Area Goal Customization"))
    st.caption(
        t("Set a weekly goal for every nightly and weekly form metric for this area. "
        "Saved goals appear on the Breakdowns page's area view and roll up into "
        "zone-level goals on its zone view. Gate, Date, New, Pew, Renew, and Mate "
        "additionally get a MONTHLY goal further down, stored separately.")
    )

    # ── Load area list (real teaching areas only — no leadership rows) ────────

    areas_df = get_submitting_areas()

    if areas_df.empty or "Area_Name" not in areas_df.columns:
        st.warning(t("No active areas found. Check the MISSION_ORG tab."))
        st.stop()

    area_names = sorted(areas_df["Area_Name"].dropna().unique().tolist())

    if not area_names:
        st.warning(t("No active area names found."))
        st.stop()

    metric_defs = get_question_metrics()
    if not metric_defs:
        st.warning(t("QUESTIONS_CONFIG has no metrics defined."))
        st.stop()

    # No UI label overrides. This was {nm_doors: "NM Attempted",
    # member_lessons: "Fellowshipped Lessons", referrals_today: "Member
    # Referrals"} — a Provo rename rule ("never show 'Doors Knocked'") over
    # three keys CCSM has no question for, so it renamed nothing and only
    # risked overriding a real Spanish label if a key ever collided.
    # QUESTIONS_CONFIG's Metric_Display_Name is what the missionaries see on
    # the form itself, so it is the right label here too.
    _LABEL_OVERRIDES: dict[str, str] = {}

    # ── Bulk: Recommend All Areas ─────────────────────────────────────────────
    # One click computes the REC value for EVERY active area — weekly Nightly
    # Form Goals AND current-month Monthly Goals — shows a preview, and a
    # separate Save writes each store in ONE batched Sheets call
    # (save_all_area_goals / bulk_upsert_area_monthly_goals), not one write
    # per area, so 60 areas can't trip the API quota.

    # The mission's own Key Indicators, not a fixed list of Provo's six —
    # which would have written zeros into every area's monthly row.
    _BULK_MONTHLY_KEYS = list(key_indicator_metrics())
    _BULK_MONTH_START = current_month_start()
    _bulk_month_label = fmt_month_year(_BULK_MONTH_START)
    if _bulk_month_label == NA:
        _bulk_month_label = _BULK_MONTH_START

    def _compute_all_area_recs() -> None:
        """on_click: build the weekly + monthly REC values for every active
        area and stash them in session state until saved or cancelled.
        Weekly metrics with no REC (no data yet) keep the area's currently
        saved value instead of being zeroed."""
        weekly, monthly = {}, {}
        for _a in area_names:
            _rec = get_recommended_goals(_a)
            _cur = get_area_goals(_a)
            _row = {}
            for _k, _lbl, _ft in metric_defs:
                if _k in _rec:
                    _row[_k] = int(_rec[_k])
                else:
                    try:
                        _row[_k] = int(float(_cur.get(_k, 0) or 0))
                    except (ValueError, TypeError):
                        _row[_k] = 0
            weekly[_a] = _row
            _mrec = get_recommended_monthly_goals(_a)
            monthly[_a] = {_k: int(_mrec.get(_k, 1)) for _k in _BULK_MONTHLY_KEYS}
        st.session_state["bulk_rec_preview"] = {"weekly": weekly, "monthly": monthly}

    with st.container(key="fillallareas"):
        st.button(
            t("RECOMMEND ALL AREA GOALS"),
            key="fillallareas_btn",
            on_click=_compute_all_area_recs,
            help=t("Compute the recommended weekly and monthly goals for every "
                 "active area, preview them, then save all at once."),
        )

    if "bulk_rec_preview" in st.session_state:
        _preview = st.session_state["bulk_rec_preview"]
        st.caption(
            t("Recommended goals computed for **{count} areas** — each area's own REC values, exactly what the per-metric REC pills show. Review below, then **Save All Recommended** to write every area's weekly goals and its {bulk_month_label} monthly goals. This overwrites any custom goals already saved.", count=len(_preview['weekly']), bulk_month_label=_bulk_month_label)
        )
        _wk_labels = {k: _LABEL_OVERRIDES.get(k, lbl) for k, lbl, _f in metric_defs}
        with st.expander(t('Preview — weekly goals ({count} areas)', count=len(_preview['weekly']))):
            _wk_df = pd.DataFrame.from_dict(_preview["weekly"], orient="index")
            _wk_df.index.name = "Area"
            st.dataframe(_wk_df.rename(columns=_wk_labels), height=420)
        # Column headers for the monthly preview table. Was a fixed
        # Gate/Date/New/Pew/Renew/Mate map — Provo's six abbreviations. None
        # matched a CCSM key, so .rename() silently left every column as a raw
        # `ki_*_real` token in a table leadership reads before saving goals for
        # the whole mission.
        _MONTHLY_PREVIEW_LABELS = dict(key_indicator_metrics())
        with st.expander(t('Preview — monthly goals for {bulk_month_label}', bulk_month_label=_bulk_month_label)):
            _mo_df = pd.DataFrame.from_dict(_preview["monthly"], orient="index")
            _mo_df.index.name = "Area"
            st.dataframe(
                _mo_df[_BULK_MONTHLY_KEYS].rename(columns=_MONTHLY_PREVIEW_LABELS),
                height=420,
            )
        _col_bulk_save, _col_bulk_cancel = st.columns([1, 1])
        with _col_bulk_save:
            if st.button(t("Save All Recommended"), type="primary", key="bulk_rec_save"):
                try:
                    save_all_area_goals(_preview["weekly"])
                except Exception as e:
                    st.error(t('Failed to save weekly goals: {e}', e=e))
                else:
                    _n_month, _m_err = bulk_upsert_area_monthly_goals(
                        _BULK_MONTH_START,
                        _preview["monthly"],
                        set_by=user.get("email", ""),
                    )
                    # Drop every per-area goal input's stale session value so
                    # the grids below re-initialize from the freshly saved
                    # goals (these widgets haven't rendered yet this run, so
                    # deleting their keys here is safe).
                    for _sk in list(st.session_state.keys()):
                        if _sk.startswith("goal_n_") or _sk.startswith("mgoal_"):
                            del st.session_state[_sk]
                    del st.session_state["bulk_rec_preview"]
                    if _m_err:
                        st.error(
                            t('Weekly goals saved for {count} areas, but monthly goals failed: {m_err}', count=len(_preview['weekly']), m_err=_m_err)
                        )
                    else:
                        st.success(
                            t('Recommended goals saved for **{count} areas** — weekly + {bulk_month_label} monthly.', count=len(_preview['weekly']), bulk_month_label=_bulk_month_label)
                        )
        with _col_bulk_cancel:
            if st.button(t("Cancel"), key="bulk_rec_cancel"):
                del st.session_state["bulk_rec_preview"]
                st.rerun()

    st.divider()

    # ── Area selector ─────────────────────────────────────────────────────────

    # requirements.txt pins streamlit==1.40.0 deliberately (see comment there):
    # newer Streamlit releases have a selectbox regression where clicking the
    # search box doesn't clear it — the current selection stays as pre-filled
    # editable text, so typing appends to it instead of searching/replacing.
    # 1.40.0 doesn't have that bug (or the accept_new_options/filter_mode
    # kwargs newer versions added) — plain defaults are correct here.
    selected_area = st.selectbox(
        t("Select Area"),
        area_names,
        key="area_goal_selector",
    )

    # ── Missionary quick-jump — a second way to land on the same area, by
    # companion name instead of area name. Wired via on_change (not a value
    # read + manual session_state write below it) so it can safely both
    # retarget the Area selectbox above AND blank itself back out —
    # Streamlit forbids writing a widget's session_state key after that
    # widget has rendered in the same script run, but a callback runs BEFORE
    # the rerun that re-renders everything, so it's the only safe spot for
    # either write. Resetting itself to "" every time means it can never sit
    # showing a name whose area no longer matches the Area selectbox (e.g.
    # after the Area selectbox is changed directly afterward) — the two
    # selectors can't fall out of sync because this one never persists a
    # selection at all, it only fires a one-shot jump. Two missionaries
    # sharing a name is a rare, low-stakes collision (last one wins) — not
    # worth disambiguating in the label.
    _name_to_area: dict[str, str] = {}
    for _col in ("Companion1_Name", "Companion2_Name", "Companion3_Name", "Companion4_Name"):
        if _col in areas_df.columns:
            for _nm, _ar in zip(areas_df[_col], areas_df["Area_Name"]):
                _nm = str(_nm or "").strip()
                if _nm:
                    _name_to_area[_nm] = _ar
    _missionary_names = sorted(_name_to_area.keys())

    def _jump_to_missionary_area():
        _nm = st.session_state.get("area_goal_missionary_selector", "")
        if _nm and _nm in _name_to_area:
            st.session_state["area_goal_selector"] = _name_to_area[_nm]
        st.session_state["area_goal_missionary_selector"] = ""

    st.selectbox(
        t("Or find by missionary name"),
        [""] + _missionary_names,
        key="area_goal_missionary_selector",
        on_change=_jump_to_missionary_area,
    )

    # ── Companionship card — same box as the Breakdowns page's Companionship
    # section (shared render_companionship_card in design_system.py): each
    # companion's name + email and the zone · district · language line, so
    # whoever is setting goals can see exactly whose area they're editing.
    _sel_meta = areas_df[areas_df["Area_Name"] == selected_area]
    if not _sel_meta.empty:
        _sel_row = _sel_meta.iloc[0]
        render_section_label(t("Companionship"))
        render_companionship_card(
            _sel_row,
            zone=str(_sel_row.get("Zone", "") or ""),
            district=str(_sel_row.get("District", "") or ""),
        )

    # ── Editable per-metric goal grid (number inputs — visible on dark theme) ──
    # (metric_defs and _LABEL_OVERRIDES are defined at the top of this tab,
    # above the Recommend All Areas block.)

    current_goals = get_area_goals(selected_area)
    area_has_custom = bool(current_goals)
    if not area_has_custom:
        st.caption(t("No custom goals saved for this area yet — enter values and save."))

    recommended_goals = get_recommended_goals(selected_area)

    def _current(key: str) -> int:
        try:
            return int(float(current_goals.get(key, 0) or 0))
        except (ValueError, TypeError):
            return 0

    def _apply_all_rec(area: str, recommended: dict, defs: list) -> None:
        """on_click callback: fill every NIGHTLY metric's goal input with its
        recommended value in one go (mirrors _apply_rec for all metrics).
        Monthly Goals (below) has its own separate Fill All Recommended."""
        for key, _lbl, ftype in defs:
            if ftype == "NIGHTLY" and key in recommended:
                st.session_state[f"goal_n_{area}_{key}"] = int(recommended[key])

    def _render_goal_inputs(defs: list, prefix: str, recommended: dict, denominators: dict | None = None) -> dict:
        """4-per-row number_input grid for Nightly Form Goals. Each input is a
        WEEKLY goal (that's what the scoring agents read). Metrics with a
        recommendation get a clickable REC pill that fills the input with the
        recommended weekly value. Metrics in `denominators` get a "/ N"
        fraction overlay, same treatment as Area Goals' Monthly Goals section.
        Returns {metric_key: weekly value}."""
        denominators = denominators or {}
        values = {}
        for i in range(0, len(defs), 4):
            cols = st.columns(4)
            for col, (key, label, _f) in zip(cols, defs[i : i + 4]):
                with col:
                    widget_key = f"goal_{prefix}_{selected_area}_{key}"
                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = _current(key)
                    values[key] = st.number_input(
                        _LABEL_OVERRIDES.get(key, label),
                        min_value=0,
                        step=1,
                        key=widget_key,
                    )
                    if key in denominators:
                        _render_fraction_overlay(prefix, key, values[key], denominators[key])
                    if key in recommended:
                        _render_rec_pill(prefix, key, widget_key, recommended[key])
        return values

    # Every nightly metric the mission asks. This used to exclude
    # "online_referrals" — a Provo metric, dropped from Provo's grid at that
    # mission's request. CCSM has no such question, so the filter excluded
    # nothing here while implying a deliberate omission.
    nightly_defs = [m for m in metric_defs if m[2] == "NIGHTLY"]
    weekly_defs  = [m for m in metric_defs if m[2] == "WEEKLY"]

    # Fill every NIGHTLY input with its recommended value at once (only shown
    # when this area actually has recommendations). Styled like the REC pills.
    if recommended_goals:
        with st.container(key="fillallrec"):
            st.button(
                t("FILL ALL RECOMMENDED"),
                key="fillall_btn",
                on_click=_apply_all_rec,
                args=(selected_area, recommended_goals, metric_defs),
            )

    render_section_label(t("Nightly Form Goals (weekly totals)"))
    st.caption(
        t("REC is a light stretch goal — about {get_rec_stretch_pct}% above this area's all-time weekly average — to nudge the area to do slightly better. Any metric with an expectation saved in Area Expectation Settings shows goal / this area's weekly expectation — add or change one there and the fraction follows the moment it's saved.", get_rec_stretch_pct=get_rec_stretch_pct())
    )

    # Denominators are DYNAMIC, not a fixed metric list (Carson, 2026-07-19:
    # "if I add ... an expectation ... it will reflect that on the goals
    # page"): EVERY nightly metric whose category defines a positive
    # expectation in Area Expectation Settings gets a "/N" fraction here,
    # the moment it's saved — same any-indicator rule as the Breakdowns
    # lines. A monthly-cadence indicator shows its weekly-equivalent, and
    # drops out below 0.5/wk rather than showing a meaningless "/ 0".
    # Fellowshipped Lessons' denominator is NOT a fixed rate (unless an
    # explicit member_lessons expectation is saved, which then wins): it's
    # whatever is CURRENTLY typed into the NM Lessons box above, read
    # straight out of that widget's session_state (already up to date at
    # the top of this script run, regardless of render order) so it tracks
    # live edits. LSI Follow-Ups gets the same live-linked treatment against
    # its own LSI Given goal (Carson, 2026-07-21: "how many of those we're
    # actually following up on ... instead of having to connect the dots
    # myself") — same precedence: an explicit lsi_followups expectation, if
    # ever saved, wins over this fallback.
    #
    # Two extra live-linked pairs used to be appended here — member_lessons
    # over the NM Lessons box, and lsi_followups over the LSI Given box. Both
    # are Provo metric pairs. Against CCSM's catalogue neither key is ever
    # rendered, so each only ever wrote a denominator for a widget that does
    # not exist. They are not replaced with CCSM equivalents: which of a
    # mission's metrics is a meaningful denominator for which other is the
    # mission's call, and it can make that call by saving an expectation in
    # Area Expectation Settings — which the loop below already honours for
    # every metric, live.
    _weekly_denominators = {}
    for _wk_key, _wk_lbl, _wk_ft in nightly_defs:
        _wk_e = get_area_expectation_entry(selected_area, _wk_key)
        if _wk_e and int(round(_wk_e["weekly"])) >= 1:
            _weekly_denominators[_wk_key] = int(round(_wk_e["weekly"]))

    new_goals = _render_goal_inputs(nightly_defs, "n", recommended_goals, _weekly_denominators)

    # Preserve the saved goals of any metric not shown above (e.g. weekly
    # metrics that aren't key indicators) so a Save doesn't zero them out.
    for _k, _lbl, _ft in metric_defs:
        if _k not in new_goals:
            new_goals[_k] = _current(_k)

    # ── Save / Reset ──────────────────────────────────────────────────────────

    col_save, col_reset = st.columns([1, 1])

    with col_save:
        if st.button(t("Save Goals"), type="primary", key="area_goal_save"):
            try:
                save_area_goals(selected_area, new_goals)
                st.success(t('Goals saved for **{selected_area}**.', selected_area=selected_area))
            except Exception as e:
                st.error(t('Failed to save goals: {e}', e=e))

    with col_reset:
        if area_has_custom:
            reset_key = f"area_goal_confirm_reset_{selected_area}"
            if st.session_state.get(reset_key, False):
                st.warning(
                    t('This will remove the custom goals row for **{selected_area}** and revert to mission-wide defaults. Are you sure?', selected_area=selected_area)
                )
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button(t("Yes, reset"), key="area_goal_reset_yes"):
                        try:
                            delete_area_goals(selected_area)
                            st.success(t('Custom goals removed for **{selected_area}**.', selected_area=selected_area))
                            st.session_state[reset_key] = False
                        except Exception as e:
                            st.error(t('Failed to reset goals: {e}', e=e))
                with col_no:
                    if st.button(t("Cancel"), key="area_goal_reset_no"):
                        st.session_state[reset_key] = False
                        st.rerun()
            else:
                if st.button(
                    t("Reset to Mission Defaults"),
                    key="area_goal_reset_btn",
                    type="secondary",
                ):
                    st.session_state[reset_key] = True
                    st.rerun()
        else:
            st.caption(t("No custom goals to reset for this area."))

    st.divider()

    # ── Monthly Goals: the mission's Key Indicators ───────────────────────────
    # Stored SEPARATELY from GOALS_CONFIG, in AREA_MONTHLY_GOALS (keyed by
    # area + month_start) — NOT read by the live AgentScores scoring script,
    # which compares GOALS_CONFIG's number directly against ONE week of real
    # data with no conversion. Making these boxes monthly without a separate
    # tab would silently break every area's weekly score.

    render_section_label(t("Monthly Goals"))

    # The seven Key Indicators, in the order the weekly form asks them.
    #
    # This used to pick them by KEYWORD — matching "gate", "date", "renew",
    # "pew" anywhere in a metric's key or label, plus the exact keys
    # "new_found" and "member_lessons". Against CCSM's metrics that selection
    # collapses to exactly ONE box: nothing matches gate/renew/pew/new_found/
    # member_lessons, and "date" matches `ki_baptismal_date_real` purely by
    # coincidence of spelling. A single arbitrary metric would have appeared
    # here under the heading "Monthly Goals", looking deliberate.
    #
    # Keyword matching over metric names is the wrong tool regardless: it
    # depends on the mission's language. Taking the catalogue's own KI set is
    # both correct and self-correcting when the form changes.
    _ki_catalog = key_indicator_metrics()
    _weekly_by_key = {m[0]: m for m in weekly_defs}
    monthly_ki_defs = [
        _weekly_by_key.get(k, (k, label, "WEEKLY"))
        for k, label in _ki_catalog.items()
    ]
    _MONTHLY_LABEL_OVERRIDES: dict[str, str] = {}

    _monthly_month_start = current_month_start()
    _monthly_row = get_current_area_monthly_goal(selected_area, _monthly_month_start)
    _monthly_label = fmt_month_year(_monthly_month_start)
    if _monthly_label == NA:
        _monthly_label = _monthly_month_start

    def _monthly_current(key: str) -> int:
        if not _monthly_row:
            return 0
        return int(_monthly_row.get(key, 0) or 0)

    # Monthly REC = the same ~10% stretch used everywhere else on this page,
    # but computed from this area's own actual CALENDAR-MONTH totals (every
    # completed month's data summed together, then averaged across full
    # history) via get_recommended_monthly_goals() — NOT a weekly average
    # projected up by a fixed weeks-per-month factor. Applies uniformly to
    # every Monthly Goals box, including Renew.
    _monthly_weeks = _current_month_weeks()
    _monthly_ki_keys = {m[0] for m in monthly_ki_defs}
    _monthly_recommended_goals = get_recommended_monthly_goals(selected_area)
    monthly_recommended = {
        k: v for k, v in _monthly_recommended_goals.items() if k in _monthly_ki_keys
    }

    st.caption(
        t("Key indicators for **{monthly_label}**, in order: Gate, Date, New, Pew, Renew, Mate. REC is a light stretch goal — about {get_rec_stretch_pct}% above this area's own real average monthly performance (every completed calendar month in this area's history, not a weekly number scaled up). Any indicator with an expectation saved in Area Expectation Settings shows goal / that expectation sized to this month — a monthly figure as-is, a weekly one times this month's exact weeks (Renew, a Sunday-only event, times its actual Sunday count). Two fallbacks when no expectation is set: Renew shows goal / the MAX possible Recent-Convert attendances this month — every recent convert, every Sunday they were eligible for (a convert baptized mid-month only counts for the Sundays after their baptism, not the ones before) — and Mate shows goal / this area's own hypothetical monthly Non-Member Lesson target (its NM Lessons expectation scaled to this month), not based on actual data. New and Mate also appear above under Nightly Form Goals as a separate WEEKLY number — the two boxes are independent, not kept in sync.", monthly_label=_monthly_label, get_rec_stretch_pct=get_rec_stretch_pct())
    )

    def _apply_all_monthly_rec(area: str, recommended: dict, defs: list) -> None:
        """on_click callback: fill every Monthly Goals input with its
        recommended monthly value in one go."""
        for key, _lbl, _ft in defs:
            if key in recommended:
                st.session_state[f"mgoal_{area}_{key}"] = int(recommended[key])

    if monthly_recommended:
        with st.container(key="fillallmonthlyrec"):
            st.button(
                t("FILL ALL RECOMMENDED"),
                key="fillall_monthly_btn",
                on_click=_apply_all_monthly_rec,
                args=(selected_area, monthly_recommended, monthly_ki_defs),
            )

    # Monthly denominators are DYNAMIC: every monthly KI whose category defines
    # an expectation in Area Expectation Settings gets a "/N" fraction — a
    # monthly-cadence indicator counts as-is, a weekly-cadence one scales by
    # THIS month's exact weeks. Church-attendance KIs are Sunday-only events, so
    # they scale by the month's actual SUNDAY count instead; scaling those by
    # weeks would set a bar for Sundays that do not exist in the month.
    # ceil, floored at 1 — a fraction out of 0 means nothing.
    #
    # Provo had two derived fallbacks here for KIs with no explicit expectation:
    # Renew's was the maximum possible Recent-Convert attendances this month
    # (from rc_total, a running headcount of the recent converts an area works
    # with), and Mate's was the area's NM Lessons expectation scaled to the
    # month. Both are gone. CCSM's weekly form asks no rc_total — there is no
    # recent-convert headcount anywhere in its data — so that denominator could
    # only ever have been 0, and "3 / 0" is worse than no fraction at all. A KI
    # with no expectation set now simply renders without one, which is honest:
    # nobody has said what the bar is.
    _SUNDAY_ONLY_KIS = {
        k for k in _ki_catalog
        if "sacrament" in k or "church" in k
    }

    def _area_monthly_exp_target(key: str) -> int | None:
        _e = get_area_expectation_entry(selected_area, key)
        if not _e:
            return None
        if _e["cadence"] == "monthly":
            _v = _e["value"]
        else:
            _v = _e["value"] * (
                _sundays_this_month if key in _SUNDAY_ONLY_KIS else _monthly_weeks
            )
        return max(1, math.ceil(_v))

    try:
        _month_start_d = date.fromisoformat(_monthly_month_start)
        _next_month_d = (
            date(_month_start_d.year + 1, 1, 1) if _month_start_d.month == 12
            else date(_month_start_d.year, _month_start_d.month + 1, 1)
        )
        _sundays_this_month = sum(
            1 for _i in range((_next_month_d - _month_start_d).days)
            if (_month_start_d + timedelta(days=_i)).weekday() == 6
        )
    except ValueError:
        _sundays_this_month = 4

    _monthly_denominators: dict[str, int] = {}
    for _mk, _mlbl, _mft in monthly_ki_defs:
        _t = _area_monthly_exp_target(_mk)
        if _t is not None:
            _monthly_denominators[_mk] = _t

    monthly_values = {}
    for i in range(0, len(monthly_ki_defs), 4):
        cols = st.columns(4)
        for col, (key, label, _f) in zip(cols, monthly_ki_defs[i : i + 4]):
            with col:
                widget_key = f"mgoal_{selected_area}_{key}"
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = _monthly_current(key)
                monthly_values[key] = st.number_input(
                    _MONTHLY_LABEL_OVERRIDES.get(key, label),
                    min_value=0,
                    step=1,
                    key=widget_key,
                )
                if key in _monthly_denominators:
                    _render_fraction_overlay("m", key, monthly_values[key], _monthly_denominators[key])
                if key in monthly_recommended:
                    _render_rec_pill("m", key, widget_key, monthly_recommended[key])

    if st.button(t("Save Monthly Goals"), type="primary", key="area_monthly_save"):
        try:
            def _mv(key: str) -> int:
                return int(monthly_values.get(key, _monthly_current(key)))

            # Every KI actually on screen, not six fixed Provo keyword args.
            # Those evaluated to 0 for CCSM, so this button reported "saved"
            # and stored nothing the user had typed.
            _row, _err = upsert_area_monthly_goal(
                selected_area,
                _monthly_month_start,
                goals={k: _mv(k) for k, _lbl, _ft in monthly_ki_defs},
                set_by=user.get("email", ""),
            )
            if _err:
                st.error(t('Failed to save monthly goals: {err}', err=_err))
            else:
                st.success(t('Monthly goals saved for **{selected_area}** — {monthly_label}.', selected_area=selected_area, monthly_label=_monthly_label))
        except Exception as e:
            st.error(t('Failed to save monthly goals: {e}', e=e))

    st.divider()

    # ── Goals vs Actuals by Area — overview of every area's saved goals ───────

    actual_df = get_latest_weekly_ki()
    goals_df = get_goals_df()

    render_section_label(t("Goals vs Actuals by Area — Latest Week"))
    st.caption(
        t("Goal from GOALS_CONFIG tab. Actual from the most recent week in WEEKLY_KI. "
        "Color: green ≥ 100%  amber ≥ 75%  red < 75%.")
    )

    if goals_df.empty and actual_df.empty:
        st.info(t("No goals or actuals data available yet."))
    else:
        rows = []

        if not goals_df.empty and "Area" in goals_df.columns:
            for _, g_row in goals_df.iterrows():
                area = g_row.get("Area", "")
                if not area:
                    continue

                zone_val     = ""
                district_val = ""
                if not actual_df.empty and "area" in actual_df.columns:
                    a_match = actual_df[actual_df["area"] == area]
                    if not a_match.empty:
                        zone_val     = str(a_match.iloc[0].get("zone",     ""))
                        district_val = str(a_match.iloc[0].get("district", ""))

                if zone_filter != _ALL_ZONES and zone_val != zone_filter:
                    continue

                row: dict = {
                    "Area":     area,
                    "Zone":     zone_val,
                    "District": district_val,
                }

                for key, label in KEY_METRICS:
                    goal_val = float(g_row.get(key, 0) or 0)

                    actual_val = 0.0
                    if not actual_df.empty and "area" in actual_df.columns and key in actual_df.columns:
                        a_match = actual_df[actual_df["area"] == area]
                        if not a_match.empty:
                            actual_val = float(a_match.iloc[0].get(key, 0) or 0)

                    if goal_val > 0:
                        pct_str = f"{round(actual_val / goal_val * 100)}%"
                    else:
                        pct_str = "—"

                    row[f"{label} Goal"]   = int(goal_val)
                    row[f"{label} Actual"] = int(actual_val)
                    row[f"{label} %"]      = pct_str

                rows.append(row)

        if not rows:
            st.info(t("No area goal data matches the current filter."))
        else:
            tbl = pd.DataFrame(rows)

            base_cols = ["Area", "Zone", "District"]
            metric_cols = []
            for _, label in KEY_METRICS:
                metric_cols += [f"{label} Goal", f"{label} Actual", f"{label} %"]
            display_cols = base_cols + [c for c in metric_cols if c in tbl.columns]
            tbl = tbl[display_cols].sort_values(["Zone", "Area"])

            pct_cols = [c for c in tbl.columns if c.endswith(" %")]

            def _style_row(row):
                styles = [""] * len(row)
                for i, col in enumerate(row.index):
                    if col in pct_cols:
                        styles[i] = _color_pct(row[col])
                return styles

            styled = tbl.style.apply(_style_row, axis=1)
            render_table(styled)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — GOAL SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

if selected_section == "Goal Settings":

    # ── Recommended Goal Nudge ─────────────────────────────────────────────────
    # Controls the "stretch" percentage every REC badge on this page (Area
    # Goals' Nightly Form Goals + Monthly Goals, and Mission Goals) uses:
    # ceil(this area's/the mission's own average history * (1 + nudge%)).
    # Backed by APP_SETTINGS (rec_stretch_pct key, see get_rec_stretch_pct() /
    # get_app_setting() in app/db/queries.py + app/db/goals_queries.py) — a
    # Streamlit-only settings tab, NOT read by any docs/*.gs agent, so changing
    # it here never touches live scoring/emails.
    render_section_label(t("Recommended Goal Nudge"))
    st.caption(
        t("Every Recommended (REC) badge on Area Goals and Mission Goals recommends that "
        "area's (or the whole mission's) own average performance, stretched "
        "up by this percentage. 0% = the plain average itself; 10% = a light "
        "stretch (the original behavior); 100% = double the average. "
        "Example: an area averaging 10/week shows REC 11 at 10%, REC 15 at "
        "50%, and REC 20 at 100%. Applies mission-wide, everywhere a REC "
        "badge appears.")
    )

    _current_nudge_pct = get_rec_stretch_pct()
    _nudge_options = list(range(0, 101, 10))
    if _current_nudge_pct not in _nudge_options:
        _nudge_options = sorted(set(_nudge_options + [_current_nudge_pct]))

    if not _can_edit_goals(user):
        st.caption(t('Current nudge: **{current_nudge_pct}%**. Only the Mission President or Assistants can change it.', current_nudge_pct=_current_nudge_pct))
    else:
        def _apply_nudge_change() -> None:
            """on_change: persist the new percentage and clear the three REC
            caches (each @st.cache_data(ttl=300) in app/db/queries.py) the
            moment the slider moves — no separate Save click. Without the
            clears, badges would keep showing values computed under the old
            percentage for up to 5 minutes."""
            _pct = st.session_state["rec_stretch_pct_selector"]
            _err = set_app_setting("rec_stretch_pct", str(_pct), user.get("email", ""))
            if _err:
                st.session_state["_nudge_save_error"] = _err
            else:
                st.session_state.pop("_nudge_save_error", None)
                get_recommended_goals.clear()
                get_recommended_monthly_goals.clear()
                get_mission_recommended_goals.clear()

        # Session-state pre-seed pattern (no value= param) — same as every
        # goal input on this page: passing value= on each rerun while the
        # on_change callback also writes session state trips Streamlit's
        # "widget had both a default value and a Session State API write".
        if "rec_stretch_pct_selector" not in st.session_state:
            st.session_state["rec_stretch_pct_selector"] = _current_nudge_pct
        st.select_slider(
            "Nudge percentage",
            options=_nudge_options,
            key="rec_stretch_pct_selector",
            on_change=_apply_nudge_change,
        )
        if st.session_state.get("_nudge_save_error"):
            st.error(t('Failed to save nudge percentage: {nudge_save_error}', nudge_save_error=st.session_state['_nudge_save_error']))
        else:
            st.caption(
                t('Active nudge: **{current_nudge_pct}%** — changes apply immediately; REC badges on the other tabs update the next time they render.', current_nudge_pct=_current_nudge_pct)
            )

    # ── Projection preview chart ───────────────────────────────────────────────
    # Mission-wide weekly totals for one metric, with the mission's actual
    # average and the projected goal at the CURRENT slider position (the same
    # ceil(avg × (1 + nudge%)) math the REC badges use, on the mission-wide
    # basis get_mission_recommended_goals() uses) — so moving the slider
    # visibly moves the green goal line relative to real performance.
    # Was `if k != "rc_total"` — Provo's headcount key, absent from CCSM. The
    # projection charts a weekly total against a projected goal, so the metrics
    # to leave out here are the ones that cannot be totalled: CHOICE answers,
    # and the `_meta` keys (a goal, not a result — projecting one and drawing a
    # goal line beside it would put two targets on the same chart).
    _proj_defs = [
        (k, lbl, f) for k, lbl, f in get_question_metrics()
        if not k.endswith("_meta") and metric_data_type(k) != "CHOICE"
    ]
    if _proj_defs:
        _proj_pct = get_rec_stretch_pct()

        _proj_key = st.selectbox(
            t("Metric to preview"),
            [k for k, _lbl, _f in _proj_defs],
            format_func=lambda k: next(lbl for kk, lbl, _f in _proj_defs if kk == k),
            key="nudge_proj_metric",
        )
        _proj_cadence = next(f for k, _lbl, f in _proj_defs if k == _proj_key)
        _proj_label = next(lbl for k, lbl, _f in _proj_defs if k == _proj_key)

        _proj_df = get_weekly_ki() if _proj_cadence == "NIGHTLY" else get_weekly_form_data()
        if _proj_df.empty or _proj_key not in _proj_df.columns or "week_end_date" not in _proj_df.columns:
            st.info(t("No weekly history for this metric yet."))
        else:
            # Same basis as the mission-wide REC math: drop the in-progress
            # week, sum every area together per week.
            _proj_sub = exclude_current_week(_proj_df.copy())
            _proj_sub[_proj_key] = pd.to_numeric(_proj_sub[_proj_key], errors="coerce")
            _totals = (
                _proj_sub.groupby("week_end_date")[_proj_key]
                .sum(min_count=1)
                .dropna()
                .sort_index()
            )
            if _totals.empty:
                st.info(t("No completed weeks for this metric yet."))
            else:
                _avg = float(_totals.mean())
                _proj_goal = max(1, math.ceil(_avg * (1 + _proj_pct / 100)))

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=_totals.index, y=_totals.values,
                    name="Mission weekly total",
                    mode="lines+markers",
                    line=dict(color="#6366f1", width=2),
                    marker=dict(size=6),
                ))
                fig.add_trace(go.Scatter(
                    x=[_totals.index[0], _totals.index[-1]],
                    y=[_avg, _avg],
                    name=f"Average ({_avg:.1f})",
                    mode="lines",
                    line=dict(color="#9ca3af", width=2, dash="dash"),
                    hovertemplate=f"Average: {_avg:.1f}<extra></extra>",
                ))
                fig.add_trace(go.Scatter(
                    x=[_totals.index[0], _totals.index[-1]],
                    y=[_proj_goal, _proj_goal],
                    name=f"Projected goal at {_proj_pct}% ({_proj_goal})",
                    mode="lines",
                    line=dict(color="#22c55e", width=2, dash="dot"),
                    hovertemplate=f"Projected goal: {_proj_goal}<extra></extra>",
                ))
                fig.update_layout(
                    template="pmg_dark",
                    height=340,
                    margin=dict(l=0, r=20, t=30, b=0),
                    xaxis_title=None,
                    yaxis_title=f"{_proj_label} per week (mission-wide)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                    yaxis=dict(rangemode="tozero"),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    t("Mission average: **{avg:.1f}/week** · projected goal at **{proj_pct}%** nudge: **{proj_goal}/week**. The green line is what the mission-wide REC badge recommends at the current slider position; per-area REC badges use the same math on each area's own history.", avg=_avg, proj_pct=_proj_pct, proj_goal=_proj_goal)
                )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — AREA EXPECTATION SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

if selected_section == "Area Expectation Settings":

    # AREA_TYPE_EXPECTATIONS is long/normalized: one row per INDICATOR
    # (category, metric, cadence, value), not a fixed 5-column row per
    # category (Carson, 2026-07-18: "what the indicator is and whether it's
    # weekly or monthly" should both be changeable, plus the ability to add
    # more). Backs THREE things at once: the Goals pages' fixed "/N"
    # fractions (Area Goal Customization, Monthly Goals' Gate, Mission
    # Goals' totals), the Breakdowns trend chart's expectation lines (ANY
    # indicator with an expectation draws one when its metric is selected
    # there), and the Scores page's Effort score — editing a category here
    # moves all three together, immediately on Save. Custom categories
    # (Carson: "type in Japanese or whatever area") layer on top of the 6
    # built-in language categories — resolve_area_expectations() checks an
    # exact-area-name override first, then substring custom categories,
    # then falls back to the built-in group.
    render_section_label(t("Area Expectation Settings"))
    st.caption(
        t("Weekly and monthly expectations by area category — the single "
        "source of truth for the Goals pages' \"/N\" fractions (including "
        "Monthly Goals' Gate and Mission Goals' totals), the Breakdowns "
        "trend chart's expectation lines (any indicator with an "
        "expectation gets a line when that metric is selected there), and "
        "the Scores page's Effort score. Save, and every page reflects it "
        "immediately. A category is matched off each area's MISSION_ORG "
        "Language_Type or area name — Haitian, Creole and French are also "
        "matched by area name even with a blank/English Language_Type — "
        "and a category named exactly after one area overrides everything "
        "else for just that area.")
    )

    _metric_keys = list(METRIC_LABELS.keys())

    def _area_exp_category_order(rows: list[dict]) -> list[str]:
        """Built-ins first (fixed order), then custom categories in the
        order they first appear — the order sections render in."""
        seen: set[str] = set()
        present: list[str] = []
        for r in rows:
            if r["category"] not in seen:
                seen.add(r["category"])
                present.append(r["category"])
        ordered = [lbl for lbl in _AREA_TYPE_LABELS.values() if lbl in present]
        ordered += [lbl for lbl in present if lbl not in _AREA_TYPE_LABELS.values()]
        return ordered

    if not _can_edit_goals(user):
        _display_rows = [
            {
                "Category": r["category"],
                "Indicator": METRIC_LABELS.get(r["metric"], r["metric"]),
                "Cadence": r["cadence"].capitalize(),
                "Target": int(round(r["value"])),
            }
            for r in get_all_area_type_indicators()
        ]
        render_table(pd.DataFrame(_display_rows))
        st.caption(t("Only the Mission President or Assistants can change these."))
    else:
        # Held in session_state — not re-read from the sheet on every rerun —
        # so an in-progress add/remove/edit survives the rerun each widget
        # triggers, without needing a Save click first. Each row carries a
        # synthetic "_id" (assigned once, at load/add time — stripped back
        # out before saving) so widgets stay correctly attached to THEIR OWN
        # row even after that row's metric or category is edited; keying
        # widgets by content or list position would go stale the moment
        # either changes.
        if "area_exp_rows" not in st.session_state:
            _loaded = get_all_area_type_indicators()
            for _i, _r in enumerate(_loaded):
                _r["_id"] = _i
            st.session_state["area_exp_rows"] = _loaded
            st.session_state["area_exp_next_id"] = len(_loaded)
        _rows = st.session_state["area_exp_rows"]

        # Save sits at the TOP of the page (Carson, 2026-07-19: "move the
        # save expectations button to the top ... add a thing that says you
        # have to press it so that it will save"), so its click is processed
        # BEFORE this rerun's editor widgets get a chance to write their
        # current values back into _rows. The widget session_state keys DO
        # already hold the latest values (widget state lands before the
        # script re-executes), so sync every row from its own widgets first
        # — without this, an edit made immediately before the click (no
        # blur/rerun in between) would save one value stale.
        st.info(
            t("Nothing here saves itself — edits below (including added or "
            "removed indicators and categories) only take effect everywhere "
            "once you press **Save Area Expectations**.")
        )
        if st.button(t("Save Area Expectations"), type="primary", key="save_area_type_exp_btn"):
            for _r in _rows:
                _rid = _r["_id"]
                if f"area_ind_metric_{_rid}" in st.session_state:
                    _r["metric"] = st.session_state[f"area_ind_metric_{_rid}"]
                if f"area_ind_cadence_{_rid}" in st.session_state:
                    _r["cadence"] = st.session_state[f"area_ind_cadence_{_rid}"]
                if f"area_ind_value_{_rid}" in st.session_state:
                    _r["value"] = float(st.session_state[f"area_ind_value_{_rid}"])
            _to_save = [{k: v for k, v in r.items() if k != "_id"} for r in _rows]
            _err = save_area_type_expectations(_to_save)
            if _err:
                st.error(t('Failed to save: {err}', err=_err))
            else:
                st.session_state.pop("area_exp_rows", None)
                st.session_state.pop("area_exp_next_id", None)
                st.success(t("Area expectations saved."))
                st.rerun()

        # Roster names back two things below: telling an exact-area
        # override apart from a substring keyword in each custom section's
        # caption, and the "override a specific area" picker in the add
        # expander (Carson, 2026-07-18: categories are the backbone, "set
        # one for a specific area if I need to").
        _roster_df = get_submitting_areas()
        _roster_names = (
            sorted(_roster_df["Area_Name"].dropna().astype(str).str.strip().unique())
            if not _roster_df.empty and "Area_Name" in _roster_df.columns
            else []
        )
        _roster_names_l = {n.lower() for n in _roster_names}

        def _on_area_ind_cadence(_id: int) -> None:
            """Cadence-dropdown on_change: copy the picked value into the
            row held in session_state BEFORE the rerun's render pass runs,
            so the Weekly/Monthly partition below sees it and the row
            renders in its new section on the SAME rerun the change
            triggers — not one interaction later."""
            for _r in st.session_state.get("area_exp_rows", []):
                if _r["_id"] == _id:
                    _r["cadence"] = st.session_state[f"area_ind_cadence_{_id}"]
                    break

        _remove_id = None
        for _category in _area_exp_category_order(_rows):
            _is_builtin = is_builtin_area_type_label(_category)
            _cat_rows = [r for r in _rows if r["category"] == _category]

            # The category is its own SECTION now — not tucked inside a
            # collapsible expander's small title text (Carson, 2026-07-19:
            # "have the area type be a section not inside of the box").
            # render_section_label is the app's OWN standard "divider
            # between content sections" component (design_system.py) —
            # already used everywhere else on this page (e.g. "Score Tier
            # Key", "Effectiveness Score by Area"), so this matches the rest
            # of the app instead of introducing a plain markdown heading
            # (tried first — Carson: "so big it almost looks like they are
            # titles," and it wasn't themed the same as everything else).
            # Its own extending horizontal rule is the "line to show what
            # section is which." Trades away collapse/expand (every
            # category is always visible now); if that ever makes the page
            # too long, that's the next ask, not something to preempt here.
            # emphasis=True (Carson, 2026-07-19: "make it more obvious what
            # section is english and what not ... more obvious but still in
            # theme") — the label's own stronger tier, not a new style.
            # English displays as "English / Default" (Carson, 2026-07-22)
            # since it's also the fallback every unrecognized/blank
            # Language_Type lands on (_language_group) — display-only, a
            # separate variable so _category itself (used below for row
            # filtering, widget keys, and the roster/override matching)
            # stays the real stored label "English".
            _display_category = (
                f"{_category} / Default" if _category == "English" else _category
            )
            #
            # "Areas Involved" (Carson, 2026-07-22: shorten the header's
            # rule a bit and show which roster areas actually resolve here
            # — e.g. Chinese should list "Chinese North"/"Chinese South";
            # 2026-07-22 follow-up: make it a plain non-clickable display,
            # not a dropdown, and never truncate a name — wrap instead)
            # sits in a narrower column next to the header —
            # render_section_label's own rule already fills whatever width
            # its column gives it (flex:1), so putting it in a narrower
            # column is what shortens it; no separate CSS needed. Matched
            # via resolve_area_category_label (the same exact-override ->
            # substring -> built-in-group resolution every fraction/
            # Breakdowns-line/Effort-score on the app already uses), not a
            # duplicated matching rule, so this always agrees with what the
            # category ACTUALLY affects.
            #
            # 4th pass (2026-07-22): Carson wants it back to looking EXACTLY
            # like the original selectbox — collapsed "N areas" box, opens
            # to one area per row, not a popover's wrapped comma-separated
            # blob — just non-selectable and without the hover tooltip. So
            # this is a real st.selectbox again (same placeholder/disabled
            # shape as the 1st pass), with `li[role='option']{pointer-
            # events:none!important}` (the CSS rule above) doing BOTH jobs
            # at once: pointer-events:none blocks the click that would
            # normally select an option (clicks fall through to the
            # non-interactive list/popover behind it, selecting nothing),
            # AND blocks hover from ever reaching that option, so
            # BaseWeb's per-option tooltip never triggers either — one
            # rule, two asks, no separate tooltip-only rule needed anymore.
            _matched_areas = sorted(
                nm for nm in _roster_names if resolve_area_category_label(nm) == _category
            )
            _hdr_col, _areas_col = st.columns([6, 1.6], vertical_alignment="bottom")
            with _hdr_col:
                render_section_label(_display_category, emphasis=True)
            with _areas_col:
                st.selectbox(
                    t("Areas Involved"),
                    _matched_areas,
                    index=None,
                    placeholder=(
                        f"{len(_matched_areas)} area{'s' if len(_matched_areas) != 1 else ''}"
                        if _matched_areas else "No areas yet"
                    ),
                    disabled=not _matched_areas,
                    key=f"area_exp_areas_involved_{_category}",
                )
            if not _is_builtin:
                if _category.strip().lower() in _roster_names_l:
                    st.caption(
                        t('Area override — applies only to {category}, ahead of any language category.', category=_category)
                    )
                else:
                    st.caption(
                        t("Custom category — matched by substring against an "
                        "area's Language_Type or its own name.")
                    )

            # Weekly and Monthly are their own SECTIONS too (Carson,
            # 2026-07-19: "have two different sections inside of that for
            # monthly and weekly"), and flipping a row's Cadence dropdown
            # moves it to the other section ON THAT SAME rerun (Carson,
            # 2026-07-18: "if I move the cadence to weekly, I want it to
            # move to the weekly [section]") — the dropdown's on_change
            # callback below writes the new cadence into the row BEFORE
            # the rerun's render pass, so this partition already sees it.
            # Without the callback the move lagged one interaction behind:
            # the partition here ran before the widget's return value
            # mutated the row, so the row only jumped sections after the
            # NEXT unrelated rerun.
            #
            # ⚠ Still split BEFORE rendering either group, not filtered
            # fresh inside each pass — with the callback the cadence no
            # longer changes mid-run, but keeping the snapshot means a
            # future in-render mutation can never re-introduce the
            # StreamlitDuplicateElementKey crash this partition originally
            # fixed (a just-flipped row rendering in BOTH passes of one
            # script run — see 25d6bd1).
            _rows_by_cadence: dict[str, list[dict]] = {"weekly": [], "monthly": []}
            for _r in _cat_rows:
                _rows_by_cadence.setdefault(_r["cadence"], []).append(_r)

            for _cadence, _cadence_heading in (
                ("weekly", "Weekly Goals"), ("monthly", "Monthly Goals"),
            ):
                _cadence_rows = _rows_by_cadence.get(_cadence, [])
                if not _cadence_rows:
                    continue
                # st.caption, not a markdown heading (Carson: the earlier
                # "### Weekly Goals" "almost looks like [it's] a title" —
                # captions use the app's normal bright text color, just at
                # Streamlit's smaller caption size, so this reads as a
                # label under the category's render_section_label, not a
                # second title competing with it.
                #
                # The cadence heading gets an underline sized to its own
                # text (not the group's full width), and the indicator
                # boxes below sit in a SEPARATE keyed container with a
                # vertical rail on its left edge, starting flush under the
                # underline's left end — the two strokes read as one bent
                # line that turns from the underline into the rail (Carson,
                # 2026-07-22: "make the top on the vertical lines turn and
                # underline weekly or monthly"). Deliberately not a full
                # horizontal rule under the heading (tried first): that
                # would repeat the SAME pattern as the category's own
                # render_section_label rule right above it, reading as a
                # second, competing section boundary instead of a subgroup.
                # See the "st-key-cadence_rail_" / "st-key-cadence_rows_"
                # rules below for the actual stroke styling.
                with st.container(key=f"cadence_rail_{_cadence}_{_category}"):
                    st.caption(f"**{_cadence_heading}**")
                    with st.container(key=f"cadence_rows_{_cadence}_{_category}"):
                        for _row in _cadence_rows:
                            # One bordered section per INDICATOR (Carson,
                            # 2026-07-18: "make a section for each of those,
                            # instead of having them grouped together in a
                            # larger box") — st.container(border=True) is a
                            # native Streamlit primitive already used
                            # elsewhere in this app (10_Notas.py,
                            # 17_Centro_de_Acción.py), not custom CSS. This
                            # also resolves the earlier "boxes uneven,
                            # Potential Members at Church out of line"
                            # complaint: no indicator shares a row with
                            # neighbors anymore, so nothing to misalign
                            # against.
                            with st.container(border=True):
                                # vertical_alignment="bottom" (same fix as
                                # the transfer-schedule exact-date row,
                                # b053aff) so Remove sits on the same line
                                # as the boxes next to it instead of
                                # floating above them.
                                _c1, _c2, _c3, _c4 = st.columns(
                                    [2, 1, 1, 1], vertical_alignment="bottom"
                                )
                                with _c1:
                                    _opts = (
                                        _metric_keys if _row["metric"] in _metric_keys
                                        else [_row["metric"]] + _metric_keys
                                    )
                                    _row["metric"] = st.selectbox(
                                        t("Indicator"), _opts,
                                        index=_opts.index(_row["metric"]),
                                        format_func=lambda k: DROPDOWN_METRIC_LABELS().get(k, k),
                                        key=f"area_ind_metric_{_row['_id']}",
                                    )
                                with _c2:
                                    _row["cadence"] = st.selectbox(
                                        # Options stay English - this value is
                                        # written to GOALS_CONFIG. format_func
                                        # translates the display only.
                                        t("Cadence"), ["weekly", "monthly"],
                                        index=0 if _row["cadence"] == "weekly" else 1,
                                        format_func=lambda c: t(c).capitalize(),
                                        key=f"area_ind_cadence_{_row['_id']}",
                                        on_change=_on_area_ind_cadence,
                                        args=(_row["_id"],),
                                    )
                                with _c3:
                                    _row["value"] = float(st.number_input(
                                        t("Target"), min_value=0, step=1,
                                        value=int(round(_row["value"])),
                                        key=f"area_ind_value_{_row['_id']}",
                                    ))
                                with _c4:
                                    if st.button(t("Remove"), key=f"area_ind_remove_{_row['_id']}"):
                                        _remove_id = _row["_id"]

            st.caption(t("Add another indicator to this category:"))
            # _add_gen suffixes the three widget keys below and bumps by 1
            # every successful Add (Carson, 2026-07-22: after pressing Add,
            # the Indicator dropdown still showed the just-added metric's
            # text instead of resting back on "SELECT INDICATOR"). Popping
            # the key from session_state before st.rerun() (the old
            # approach) DOES reset the Python-side value back to None —
            # confirmed directly with an AppTest harness, the backend was
            # never wrong — but BaseWeb's Select keeps its own DOM-level
            # input text tied to the widget's REACT KEY, and reusing the
            # same key across a rerun can leave that visible text stale
            # even though the underlying value is genuinely None. Changing
            # the key itself (not just clearing session_state) forces a
            # full remount with no stale DOM to inherit from.
            _add_gen = st.session_state.get(f"area_ind_add_gen_{_category}", 0)
            _a1, _a2, _a3, _a4 = st.columns(
                [2, 1, 1, 1], vertical_alignment="bottom"
            )
            with _a1:
                # Rests on a SELECT INDICATOR placeholder (index=None), not
                # the first metric (Carson, 2026-07-19: "i dont want this to
                # register as a indicator ... so we can distinguish which
                # are set and which we can add with") — an untouched add-row
                # can never be mistaken for a configured indicator, and Add
                # does nothing until one is actually picked.
                _new_metric = st.selectbox(
                    t("Indicator"), _metric_keys,
                    index=None,
                    placeholder=t("SELECT INDICATOR"),
                    format_func=lambda k: DROPDOWN_METRIC_LABELS().get(k, k),
                    key=f"area_ind_new_metric_{_category}_{_add_gen}",
                )
            with _a2:
                # Same resting-placeholder treatment as Indicator above
                # (Carson, 2026-07-21: "do the same thing for the cadence
                # and the target") — index=None so an untouched add-row
                # never silently defaults to Weekly.
                _new_cadence = st.selectbox(
                    # Options stay English - written to GOALS_CONFIG.
                    t("Cadence"), ["weekly", "monthly"],
                    index=None,
                    placeholder=t("SELECT CADENCE"),
                    format_func=lambda c: t(c).capitalize(),
                    key=f"area_ind_new_cadence_{_category}_{_add_gen}",
                )
            with _a3:
                # NOT placeholder-mode (value=None): Streamlit's number_input
                # silently no-ops its +/- steppers with no value to step
                # from, and its empty-state box renders a visibly different
                # color than the selectboxes' — confirmed live, not just a
                # theory. A real default keeps the steppers working and
                # matches how Target already looks on existing rows.
                _new_value = st.number_input(
                    t("Target"), min_value=0, step=1, value=0,
                    key=f"area_ind_new_value_{_category}_{_add_gen}",
                )
            with _a4:
                if st.button(t("Add"), key=f"area_ind_add_{_category}"):
                    if _new_metric is None:
                        st.warning(t("Pick an indicator first."))
                    elif _new_cadence is None:
                        st.warning(t("Pick a cadence first."))
                    elif any(r["metric"] == _new_metric for r in _cat_rows):
                        st.warning(
                            t('{metric_labels} is already in this category.', metric_labels=METRIC_LABELS.get(_new_metric, _new_metric))
                        )
                    else:
                        _new_id = st.session_state["area_exp_next_id"]
                        st.session_state["area_exp_next_id"] += 1
                        _rows.append({
                            "_id": _new_id, "category": _category,
                            "metric": _new_metric, "cadence": _new_cadence,
                            "value": float(_new_value),
                        })
                        # Bump the generation instead of popping the old
                        # keys — see the _add_gen comment above.
                        st.session_state[f"area_ind_add_gen_{_category}"] = _add_gen + 1
                        st.rerun()

        if _remove_id is not None:
            st.session_state["area_exp_rows"] = [r for r in _rows if r["_id"] != _remove_id]
            st.rerun()

        st.divider()
        # Add a NEW category beyond the built-ins — a typed language keyword
        # ("Japanese", matched the same substring way _language_group()
        # already matches Haitian/Creole/French by name), or an EXACT area
        # picked from the roster (Carson, 2026-07-18: "set one for a
        # specific area if I need to" — a dropdown, so "Provo" the override
        # can never accidentally catch Provo North too; exact-name matches
        # win over substring ones in resolve_area_expectations). A typed
        # keyword starts with one placeholder NM Lessons/weekly/0 indicator
        # rather than an empty, indicator-less category; an area override
        # starts seeded with the area's CURRENTLY-resolved expectations, so
        # Carson edits from its real baseline instead of a page of zeros.
        with st.expander(t("➕ Add a custom expectation category")):
            _existing = {r["category"].strip().lower() for r in _rows}
            st.caption(
                t("Type a language (e.g. \"Japanese\") or any keyword (e.g. "
                "\"BYU\") — it matches every area whose Language_Type OR "
                "area name contains it, so \"BYU\" catches BYU East and "
                "BYU North whatever their languages. Add its indicators in "
                "its own section above once the category exists.")
            )
            _new_cat = st.text_input(t("Language or keyword"), key="area_type_exp_new_category")
            if st.button(t("Add Category"), key="area_type_exp_add_category_btn"):
                _label = _new_cat.strip()
                if not _label:
                    st.warning(t("Enter a language or keyword first."))
                elif _label.lower() in _existing:
                    st.warning(t('"{label}" is already in the list.', label=_label))
                else:
                    _new_id = st.session_state["area_exp_next_id"]
                    st.session_state["area_exp_next_id"] += 1
                    # Placeholder indicator for the new category. Was
                    # "nm_lessons" — a metric CCSM does not collect, so every
                    # custom category was born holding an indicator that
                    # matches no column and can never resolve. The first
                    # nightly metric the mission actually asks is a real,
                    # editable starting point.
                    _rows.append({
                        "_id": _new_id, "category": _label,
                        "metric": _placeholder_metric(), "cadence": "weekly",
                        "value": 0.0,
                    })
                    st.session_state.pop("area_type_exp_new_category", None)
                    st.rerun()

            st.caption(
                t("— or override ONE specific area: pick it here and it gets "
                "its own section above, pre-filled with what it currently "
                "resolves to. Its numbers then beat its language category "
                "everywhere (fractions, Breakdowns lines, Effort score).")
            )
            _ovr_area = st.selectbox(
                t("Specific area"), _roster_names, index=None,
                placeholder=t("Pick an area…"),
                key="area_type_exp_new_override",
            )
            if st.button(t("Add Area Override"), key="area_type_exp_add_override_btn"):
                if not _ovr_area:
                    st.warning(t("Pick an area first."))
                elif _ovr_area.strip().lower() in _existing:
                    st.warning(t('"{ovr_area}" already has its own section above.', ovr_area=_ovr_area))
                else:
                    _seed = resolve_area_expectations(_ovr_area) or {
                        _placeholder_metric(): {"cadence": "weekly", "value": 0.0}
                    }
                    for _m, _entry in _seed.items():
                        _new_id = st.session_state["area_exp_next_id"]
                        st.session_state["area_exp_next_id"] += 1
                        _rows.append({
                            "_id": _new_id, "category": _ovr_area.strip(),
                            "metric": _m, "cadence": _entry["cadence"],
                            "value": float(_entry["value"]),
                        })
                    st.session_state.pop("area_type_exp_new_override", None)
                    st.rerun()

