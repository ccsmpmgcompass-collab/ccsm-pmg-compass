import math
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from app.auth.auth import can_set_goals, require_auth
from app.components.design_system import (
    render_page_header, render_section_label, render_section_tabs,
    render_table, render_companionship_card,
)
from app.config.flavor_loader import flavor, METRIC_LABELS, GOAL_LABELS, GOAL_TO_ACTUAL
from app.config.metric_catalog import (
    key_indicator_metrics,
    metric_data_type,
    metric_options,
    nightly_metrics,
)
from app.i18n.formats import NA, fmt_day_month, fmt_int, fmt_month_year, fmt_number
from app.utils.area_helpers import mission_today


#: The cadences an area-type expectation can be entered at, in the order the
#: dropdowns offer them. "transfer" joined the pair for Step 7 (PLAN §7.4h) —
#: the mission plans in six-week cycles, and the values are written to the sheet
#: verbatim, so these stay English and are translated for display only.
_CADENCES = ["weekly", "monthly", "transfer"]


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
    get_recommended_transfer_goals,
    get_mission_recommended_goals,
    get_mission_transfer_expectation_total,
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
    roster_ceiling,
)
from app.db.queries import _AREA_TYPE_LABELS
from app.db.goals_queries import (
    get_area_transfer_goal,
    upsert_area_transfer_goal,
    bulk_upsert_area_transfer_goals,
    group_goal_totals,
    goals_by_cycle_start,
    cycles_with_goals,
    areas_with_goals,
    get_app_setting,
    set_app_setting,
)
# Goals are set per TRANSFER CYCLE, not per calendar month (PLAN §7.2). The
# monthly path — MISSION_GOALS and AREA_MONTHLY_GOALS — is gone, tabs and
# functions both: neither tab ever existed on the live sheet, so nothing was
# stranded. `current_month_start`, `get_current_goal`, `upsert_goal`,
# `get_mission_goals_for_display`, `get_current_area_monthly_goal`,
# `upsert_area_monthly_goal` and `bulk_upsert_area_monthly_goals` were deleted
# with it, along with `get_recommended_monthly_goals` and
# `get_mission_monthly_expectation_total` in queries.py.
from app.analytics import transfer_year as ty
from app.utils.transfer_helpers import transfer_cycles, transfer_window

# Page chrome (set_page_config / inject_global_css / render_sidebar) is
# owned by Home.py's st.navigation router since 2026-09-02 — the router and
# this page share one script run, so calling them here would render twice.
user = require_auth()
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
    """True for MP, APs, and the system owner account.

    Delegates to `auth.can_set_goals`. This used to check the MISSION_ORG role
    plus one hardcoded gmail address, which — probed live 2026-09-05 — admitted
    that gmail account and NOBODY ELSE: none of the mission president's, the two
    assistants' or the owner's sign-in addresses appear in MISSION_ORG at all,
    so their derived role is "unknown". Every gated section on this page was
    therefore closed to the four people it was written for. Found while adding
    the same gate to the transfer-goal boxes (PLAN §7.4d), where it would have
    locked the mission out of the one thing Step 7 exists to let them do.
    """
    return can_set_goals(user)


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


def _strip_real_suffix(label: str) -> str:
    """A Key Indicator's name without the form's "(Real)" suffix.

    That suffix separates an achieved figure from the "(Meta)" beside it ON THE
    FORM, where a companionship enters both. Nowhere on this page is that the
    question: a goal box labelled "Nuevas Personas Encontradas (Real)" says the
    opposite of what it is. The Panel and the Desgloses progression header
    already make the same trim.
    """
    for suffix in (" (Real)", " (real)"):
        if label.endswith(suffix):
            return label[: -len(suffix)]
    return label


def _cycles() -> list[dict]:
    """Every transfer cycle in TRANSFER_SCHEDULE, oldest first, with real end
    dates. One read per page run — the picker, the goal boxes, the mission
    summary and the year summary all want the same list."""
    return transfer_cycles()


def _cycle_label(cycle: dict) -> str:
    """How a cycle is named on this page: "Cambio 2026-6 · 7 sep – 18 oct".

    "cambio", matching the period picker on Desgloses ("Este cambio hasta hoy")
    — the mission's own word, and the one leadership uses out loud. The dates
    ride along because the number alone does not say when: nobody remembers
    that 2026-6 is September.
    """
    from app.i18n.formats import fmt_day_month
    number = str(cycle.get("number") or "").strip()
    span = t("{start} – {end}",
             start=fmt_day_month(cycle["start"]), end=fmt_day_month(cycle["end"]))
    if not number:
        return span
    return t("Cambio {number} · {span}", number=number, span=span)


def _cycle_weeks(cycle: dict) -> float:
    """A cycle's length in weeks, from its REAL dates rather than its Weeks
    column — a cycle that ran short is described as it ran, here as everywhere
    else. Floors at 1: every scaling below divides or multiplies by this."""
    return max(1.0, ty.weeks_in_cycle(cycle["start"], cycle["end"]))


def _cycle_has_ended(cycle: dict) -> bool:
    """True once the cycle's end date has passed.

    Past cycles stay EDITABLE (Zackary, 2026-09-05) so 2026-4 and 2026-5 can be
    backfilled and the year summary is not a fraction of the year on day one.
    This only drives the caption that says so — a goal typed into a finished
    cycle should be visibly a backfill, not look like a plan.
    """
    from app.utils.area_helpers import mission_today
    return cycle["end"] < mission_today()


def _certified_baptisms_for_year(year: int, today: date) -> tuple[int | None, str]:
    """The certified TABLEAU_BAPTISMS total for `year`, and how far it reaches.

    `get_baptisms_actual_for_range` refuses a range whose months are not ALL
    captured — correctly, because a partial sum reads LOW and looks like a real
    total. A year in progress is always partial, so this walks January forward
    and STOPS at the first month with no capture, returning what it has along
    with the name of the last month it covers.

    That is the honest shape for this row: the capture lags a month or two, and
    a number labelled "certified through August" is usable where an unlabelled
    one is a quiet undercount. Returns (None, "") when not even January is in.

    Never blended with the mission's own weekly figure — the two appear as two
    named rows (§7.7), which is `annual_baptisms.py`'s "One source" rule.
    """
    last_month = 12 if year < today.year else (today.month if year == today.year else 0)
    if last_month == 0:
        return None, ""
    total, reach = 0, None
    for m in range(1, last_month + 1):
        val = get_baptisms_actual(f"{year:04d}-{m:02d}-01")
        if val is None:
            break
        total += int(val)
        reach = date(year, m, 1)
    if reach is None:
        return None, ""
    label = fmt_month_year(reach)
    return total, (reach.isoformat()[:7] if label == NA else label)


def _pick_cycle(key: str) -> dict | None:
    """The cycle picker: every cycle in the schedule, newest first, defaulting
    to the one today falls in.

    Newest first because the cycle being planned is almost always the current or
    next one; the older ones are there to be backfilled, not scrolled past.
    Returns None when the schedule is empty, which the caller reports rather
    than papering over — a goal has to belong to a cycle.
    """
    cycles = _cycles()
    if not cycles:
        return None
    newest_first = list(reversed(cycles))
    current = transfer_window(0)
    default = 0
    if current:
        for i, c in enumerate(newest_first):
            if c["start"] == current["start"]:
                default = i
                break
    labels = [_cycle_label(c) for c in newest_first]
    choice = st.selectbox(t("Cambio"), labels, index=default, key=key)
    return newest_first[labels.index(choice)]


# ── Main "tabs" ───────────────────────────────────────────────────────────────
# Was st.tabs(), then st.radio() repainted as tabs by a block of CSS, and now
# the app's one shared sub-navigation control (audit step 1.7). Both earlier
# forms are described in render_section_tabs' docstring, including why st.tabs
# had to go: it has no server-side memory of which tab is active, so ANY
# widget-triggered rerun — clicking Mission Goals' FILL ALL RECOMMENDED, say —
# snapped the view back to the first tab, and with interactive widgets on two
# tabs the old "put the busy tab first" workaround could not cover both.
#
# The CSS this replaces was copy-pasted verbatim into Traslados, and depended
# on Streamlit's internal st-key- class names to repaint radio labels.
#
# The stored value is still the English id, so a mid-session language switch
# cannot strand a Spanish string in the option list.
# "Mission Goals" became "Mission Summary" when MISSION_TRANSFER_GOALS was
# dropped (PLAN §7.4a). There is no mission goal to SET any more — the mission's
# figure for a cycle is its areas' summed goals — so the slot holds a read-only
# summary of this cycle and then the year instead of an editor.
_GOALS_SECTIONS = {
    s: t(s) for s in (
        "Area Goal Customization", "Mission Summary", "Goal Settings",
        "Area Expectation Settings",
    )
}
selected_section = render_section_tabs(
    _GOALS_SECTIONS, key="goals_section_val", per_row=4)

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
# TAB 2 — MISSION SUMMARY  ("Resumen de la misión")
# ══════════════════════════════════════════════════════════════════════════════
# Replaces "Mission Goals", which set a monthly mission-wide target in its own
# tab. That tab is gone and so is the idea behind it (PLAN §7.4a): the mission's
# figure for a cycle IS its areas' summed goals, so there is nothing here to
# edit and everything here is read.
#
# What the old section got wrong, beyond the cadence: it rendered the flavor's
# six GOAL keys, of which `baptisms` and `confirmations` BOTH mapped to
# ki_baptized_confirmed_real — one metric shown twice — while
# ki_friends_first_week_real had no goal key at all and never appeared. Keying on
# the seven Key Indicators directly (§7.1) fixes both by construction.
#
# Two parts: this cycle, then the year.

if selected_section == "Mission Summary":

    _ki_catalog = key_indicator_metrics()

    _BAPTISM_KEY = "ki_baptized_confirmed_real"

    def _weekly_between(df, start: date, end: date):
        """Weekly-form rows whose week_end_date falls in [start, end].

        A reporting week is placed by its Sunday, which is the only grain the
        weekly form offers. Over a transfer cycle that is exact — cycles are
        whole Monday-to-Sunday weeks (§7.0a). Over a calendar YEAR a week
        straddling New Year lands wholly in the year its Sunday falls in, which
        is a real approximation and is why the year rows say "por semana
        informada".
        """
        if df.empty or "week_end_date" not in df.columns:
            return df
        wk = pd.to_datetime(df["week_end_date"], errors="coerce").dt.date
        return df[wk.notna() & (wk >= start) & (wk <= end)]

    def _sum_ki(df, key: str) -> float:
        if df.empty or key not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[key], errors="coerce").fillna(0).sum())

    def _pct(actual: float, goal: float) -> str:
        return f"{round(actual / goal * 100)}%" if goal > 0 else "—"

    def _style_summary(row):
        styles = [""] * len(row)
        idx = list(row.index).index(t("% of Goal"))
        styles[idx] = _color_pct(row[t("% of Goal")])
        return styles

    _wf_all = get_weekly_form_data()
    _all_cycles = _cycles()

    if not _all_cycles:
        st.warning(t("TRANSFER_SCHEDULE has no cycles, so there is nothing to "
                     "summarise. Add the mission's cycles on the Traslados page."))
        st.stop()

    # ── Part 1: this cycle ────────────────────────────────────────────────────

    render_section_label(t("Mission — this transfer"))
    st.caption(t("Mission-wide, and not affected by the zone filter in the "
                 "sidebar. The goal is every area's own goal for this cambio, "
                 "summed — there is no separate mission-wide goal to set."))

    _sum_cycle = _pick_cycle("mission_summary_cycle")
    _from = _sum_cycle["start"]
    _to = min(_sum_cycle["end"], mission_today())
    _cycle_goals = group_goal_totals(_sum_cycle["start"])
    _n_areas_set = areas_with_goals(_sum_cycle["start"])
    _n_areas_total = len(get_submitting_areas())

    if not _cycle_goals or not _n_areas_set:
        st.info(t("No area has set a goal for {cycle} yet. Set them under Area "
                  "Goal Customization.", cycle=_cycle_label(_sum_cycle)))
    else:
        # The basis, said out loud. A mission total resting on six areas out of
        # forty-three must not read the same as one every area signed up to —
        # the same rule _ki_goal_note enforces on the Panel's bars.
        st.caption(t("{n} of {total} areas have set a goal for this cambio. "
                     "Results counted through {through}.",
                     n=fmt_int(_n_areas_set), total=fmt_int(_n_areas_total),
                     through=fmt_day_month(_to)))

        _cycle_rows = []
        for _key, _raw in _ki_catalog.items():
            _goal = float(_cycle_goals.get(_key, 0) or 0)
            _actual = _sum_ki(_weekly_between(_wf_all, _from, _to), _key)
            _label = _strip_real_suffix(_raw)
            # §7.7: a transfer window cannot carry a certified baptism count —
            # TABLEAU_BAPTISMS holds whole calendar months and a cycle never is
            # one. The mission's own weekly figure is used and NAMED, never
            # silently substituted for the certified number it undercounts.
            if _key == _BAPTISM_KEY:
                _label = t("{label} (weekly report)", label=_label)
            _cycle_rows.append({
                t("Indicator"): _label,
                t("Goal"):      int(round(_goal)),
                t("Actual"):    int(round(_actual)),
                t("% of Goal"): _pct(_actual, _goal),
            })

        render_table(pd.DataFrame(_cycle_rows).style.apply(_style_summary, axis=1))
        st.caption(t("Baptisms here are the mission's own weekly report, which "
                     "under-counts. The certified Tableau figure is monthly and "
                     "cannot describe a cambio; it is shown in the year below."))

    st.divider()

    # ── Part 2: the year ──────────────────────────────────────────────────────

    render_section_label(t("Mission — the year"))

    _years = ty.years_in_schedule(_all_cycles)
    if not _years:
        st.info(t("No cycle in the schedule can be placed in a calendar year."))
    else:
        _today = mission_today()
        _default_year = _years.index(_today.year) if _today.year in _years else len(_years) - 1
        _year = st.selectbox(t("Year"), _years, index=_default_year, key="mission_year")

        _goals_by_cycle = goals_by_cycle_start()
        _owned = ty.cycles_owned_by(_all_cycles, _year)
        _planned = {c["start"] for c in _owned} & cycles_with_goals()
        _y_from, _y_to = ty.year_bounds(_year, _today)

        # MANDATORY (§7.8). With the tab empty on day one, a year total resting
        # on three of eight cycles is the normal case, not an edge case, and
        # without this caption it reads as the whole year's target.
        st.caption(t("{n} of {total} cambios in {year} have goals set. "
                     "Results counted through {through}.",
                     n=fmt_int(len(_planned)), total=fmt_int(len(_owned)),
                     year=_year, through=fmt_day_month(_y_to)))

        # A cycle that crosses New Year contributes its goal to BOTH years, split
        # by days (§7.3). Naming it is what makes the total addable by eye — a
        # pro-rated figure that does not explain itself is unreadable.
        for _straddler in ty.straddlers_for_year(_all_cycles, _year):
            _share = ty.year_share(_straddler["start"], _straddler["end"], _year)
            st.caption(t(
                "{label} crosses into another year, so {pct}% of its goal "
                "({days} of its {total} days) counts toward {year}.",
                label=_cycle_label(_straddler), pct=round(_share * 100),
                days=fmt_int(ty.days_in_year(_straddler["start"], _straddler["end"], _year)),
                total=fmt_int(ty.cycle_days(_straddler["start"], _straddler["end"])),
                year=_year))

        _y_weekly = _weekly_between(_wf_all, _y_from, _y_to)
        _year_rows = []
        for _key, _raw in _ki_catalog.items():
            _goal = ty.year_goal_total(_all_cycles, _goals_by_cycle, _key, _year)
            _actual = _sum_ki(_y_weekly, _key)
            _label = _strip_real_suffix(_raw)
            if _key == _BAPTISM_KEY:
                _label = t("{label} (weekly report)", label=_label)
            _year_rows.append({
                t("Indicator"): _label,
                t("Goal"):      int(round(_goal)),
                t("Actual"):    int(round(_actual)),
                t("% of Goal"): _pct(_actual, _goal),
            })

        # §7.7: both baptism sources, as two named rows, never spliced into one.
        # The gap between them is itself worth seeing — the weekly figure came in
        # at ~18-20 against an official 41 for one month — and neither source
        # quietly does the other's job. That is annual_baptisms.py's "One source"
        # rule, applied to a table instead of a chart.
        _certified, _reach = _certified_baptisms_for_year(_year, _today)
        if _certified is not None:
            _bapt_goal = ty.year_goal_total(_all_cycles, _goals_by_cycle, _BAPTISM_KEY, _year)
            _year_rows.append({
                t("Indicator"): t("Baptisms (Tableau, certified through {reach})",
                                  reach=_reach),
                t("Goal"):      int(round(_bapt_goal)),
                t("Actual"):    int(_certified),
                t("% of Goal"): _pct(_certified, _bapt_goal),
            })

        render_table(pd.DataFrame(_year_rows).style.apply(_style_summary, axis=1))
        st.caption(t("A year's goal is every cambio's goal for that year, with a "
                     "cambio that crosses New Year split by days. Results are "
                     "counted by the week they were reported in, always by real "
                     "date — never by which cambio a week belonged to."))
        if _certified is None:
            st.caption(t("No certified Tableau baptism figure has been captured "
                         "for {year} yet, so only the mission's own weekly "
                         "report is shown.", year=_year))

        # The Panel's annual baptism chart keeps its own certified source and its
        # own GOAL_ANNUAL_baptisms target, and is deliberately untouched by any
        # of this (§7.8, and acceptance check 6).


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — AREA GOAL CUSTOMIZATION
# ══════════════════════════════════════════════════════════════════════════════

if selected_section == "Area Goal Customization":

    render_section_label(t("Area Goal Customization"))
    st.caption(
        t("Set a weekly goal for every nightly and weekly form metric for this area. "
        "Saved goals appear on the Breakdowns page's area view and roll up into "
        "zone-level goals on its zone view. The mission's Key Indicators "
        "additionally get a goal PER TRANSFER CYCLE further down, stored separately.")
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
    # Form Goals AND this cambio's Key Indicator goals — shows a preview, and a
    # separate Save writes each store in ONE batched Sheets call
    # (save_all_area_goals / bulk_upsert_area_transfer_goals), not one write per
    # area, so 60 areas can't trip the API quota.
    #
    # This is the only realistic way to populate AREA_TRANSFER_GOALS at all:
    # forty-three areas times seven indicators is 301 numbers to type by hand.
    # The first draft of PLAN §7 missed this button entirely (§7.4e).

    # The mission's own Key Indicators, not a fixed list of Provo's six —
    # which would have written zeros into every area's row.
    _BULK_KI_KEYS = list(key_indicator_metrics())
    _bulk_cycle = transfer_window(0)
    _bulk_cycle_label = _cycle_label(_bulk_cycle) if _bulk_cycle else ""
    _bulk_weeks = _cycle_weeks(_bulk_cycle) if _bulk_cycle else 0

    # The bulk button writes the transfer goals of every area in the mission, so
    # it is gated exactly as the per-area transfer boxes are (§7.4d).
    _may_bulk = _can_edit_goals(user) and _bulk_cycle is not None

    def _compute_all_area_recs() -> None:
        """on_click: build the weekly + transfer REC values for every active
        area and stash them in session state until saved or cancelled.
        Weekly metrics with no REC (no data yet) keep the area's currently
        saved value instead of being zeroed."""
        weekly, transfer = {}, {}
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
            _trec = get_recommended_transfer_goals(_a, _bulk_weeks)
            transfer[_a] = {_k: int(_trec.get(_k, 1)) for _k in _BULK_KI_KEYS}
        st.session_state["bulk_rec_preview"] = {"weekly": weekly, "transfer": transfer}

    if _may_bulk:
        with st.container(key="fillallareas"):
            st.button(
                t("RECOMMEND ALL AREA GOALS"),
                key="fillallareas_btn",
                on_click=_compute_all_area_recs,
                help=t("Compute the recommended weekly goals and this cambio's "
                       "goals for every active area, preview them, then save "
                       "all at once."),
            )

    if _may_bulk and "bulk_rec_preview" in st.session_state:
        _preview = st.session_state["bulk_rec_preview"]
        st.caption(
            t("Recommended goals computed for **{count} areas** — each area's own REC values, exactly what the per-metric REC pills show. Review below, then **Save All Recommended** to write every area's weekly goals and its goals for {cycle}. This overwrites any custom goals already saved.", count=len(_preview['weekly']), cycle=_bulk_cycle_label)
        )
        _wk_labels = {k: _LABEL_OVERRIDES.get(k, lbl) for k, lbl, _f in metric_defs}
        with st.expander(t('Preview — weekly goals ({count} areas)', count=len(_preview['weekly']))):
            _wk_df = pd.DataFrame.from_dict(_preview["weekly"], orient="index")
            _wk_df.index.name = "Area"
            st.dataframe(_wk_df.rename(columns=_wk_labels), height=420)
        # Column headers for the transfer preview table. Was a fixed
        # Gate/Date/New/Pew/Renew/Mate map — Provo's six abbreviations. None
        # matched a CCSM key, so .rename() silently left every column as a raw
        # `ki_*_real` token in a table leadership reads before saving goals for
        # the whole mission.
        _KI_PREVIEW_LABELS = dict(key_indicator_metrics())
        with st.expander(t('Preview — goals for {cycle}', cycle=_bulk_cycle_label)):
            _tr_df = pd.DataFrame.from_dict(_preview["transfer"], orient="index")
            _tr_df.index.name = "Area"
            st.dataframe(
                _tr_df[_BULK_KI_KEYS].rename(columns=_KI_PREVIEW_LABELS),
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
                    _n_tr, _t_err = bulk_upsert_area_transfer_goals(
                        _bulk_cycle["start"].isoformat(),
                        _preview["transfer"],
                        set_by=user.get("email", ""),
                        transfer_number=str(_bulk_cycle.get("number") or ""),
                    )
                    # Drop every per-area goal input's stale session value so
                    # the grids below re-initialize from the freshly saved
                    # goals (these widgets haven't rendered yet this run, so
                    # deleting their keys here is safe).
                    for _sk in list(st.session_state.keys()):
                        if _sk.startswith("goal_n_") or _sk.startswith("tgoal_"):
                            del st.session_state[_sk]
                    del st.session_state["bulk_rec_preview"]
                    if _t_err:
                        st.error(
                            t('Weekly goals saved for {count} areas, but the cambio goals failed: {err}', count=len(_preview['weekly']), err=_t_err)
                        )
                    else:
                        st.success(
                            t('Recommended goals saved for **{count} areas** — weekly, plus {cycle}.', count=len(_preview['weekly']), cycle=_bulk_cycle_label)
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

    # ── Metas de este cambio: the mission's Key Indicators ────────────────────
    # Stored SEPARATELY from GOALS_CONFIG, in AREA_TRANSFER_GOALS (keyed by
    # area + transfer_start) — NOT read by the live AgentScores scoring script,
    # which compares GOALS_CONFIG's number directly against ONE week of real
    # data with no conversion, and which CCSM_Agent2.gs recalibrates every
    # cycle. Making the weekly boxes above transfer-scoped would silently break
    # every area's weekly score, so they stay weekly and these are their own
    # thing (PLAN §7.4i).
    #
    # Was "Monthly Goals", written to a tab that never existed. The cadence is
    # the change that matters: a transfer cycle is whole Monday-to-Sunday
    # reporting weeks, so every scaling below is exact where the monthly version
    # needed a days/7 estimate and a counted-Sundays correction to approximate
    # it. Both estimates are gone rather than ported (§7.0a).

    render_section_label(t("Goals for this transfer"))

    # The seven Key Indicators, in the order the weekly form asks them.
    #
    # This used to pick them by KEYWORD — matching "gate", "date", "renew",
    # "pew" anywhere in a metric's key or label, plus the exact keys
    # "new_found" and "member_lessons". Against CCSM's metrics that selection
    # collapses to exactly ONE box: nothing matches gate/renew/pew/new_found/
    # member_lessons, and "date" matches `ki_baptismal_date_real` purely by
    # coincidence of spelling. A single arbitrary metric would have appeared
    # here under the heading, looking deliberate.
    #
    # Keyword matching over metric names is the wrong tool regardless: it
    # depends on the mission's language. Taking the catalogue's own KI set is
    # both correct and self-correcting when the form changes.
    _ki_catalog = key_indicator_metrics()
    _weekly_by_key = {m[0]: m for m in weekly_defs}
    # Labels trimmed of "(Real)": these are goal boxes, and the suffix names the
    # achieved half of the pair the weekly FORM collects.
    transfer_ki_defs = [
        (k, _strip_real_suffix(_weekly_by_key.get(k, (k, label, "WEEKLY"))[1]), "WEEKLY")
        for k, label in _ki_catalog.items()
    ]

    _tg_cycle = _pick_cycle("area_goal_cycle")
    if _tg_cycle is None:
        st.warning(t("TRANSFER_SCHEDULE has no cycles, so a goal has nothing to "
                     "belong to. Add the mission's cycles on the Traslados page."))
    else:
        _tg_start = _tg_cycle["start"].isoformat()
        _tg_weeks = _cycle_weeks(_tg_cycle)
        _tg_label = _cycle_label(_tg_cycle)
        _tg_row = get_area_transfer_goal(selected_area, _tg_start)

        # Past cycles stay editable so 2026-4 and 2026-5 can be backfilled
        # (§7.4c) — but a goal typed into a finished cycle should read as a
        # backfill, not as a plan.
        if _cycle_has_ended(_tg_cycle):
            st.caption(t("This cambio has already ended. Goals saved for it are "
                         "a record of what was expected, not a plan."))

        def _transfer_current(key: str) -> int:
            if not _tg_row:
                return 0
            return int(_tg_row.get(key, 0) or 0)

        # Only the MP and the APs set the mission's targets (§7.4d). This is a
        # real change: Area Goal Customization was the one tab on this page with
        # no gate, and with Mission Goals deleted these boxes are now the only
        # leadership goal in the app. The WEEKLY nightly-form boxes above are
        # deliberately left as they were — this step does not take away edit
        # rights anyone has today.
        _may_edit_transfer = _can_edit_goals(user)

        # REC = the area's own weekly stretch average times THIS cycle's real
        # weeks. Not an average cycle length, and not an average of completed
        # cycles: WEEKLY_KI begins 2026-08-09, so no area has one completed
        # transfer of history yet and that average would divide by zero cycles
        # (§7.4g). Sunday-only KIs need no correction here — over a transfer the
        # Sunday count IS the week count, which is why the monthly version's
        # _sundays_in_month special case is gone rather than ported.
        _transfer_ki_keys = {m[0] for m in transfer_ki_defs}
        _all_transfer_recs = get_recommended_transfer_goals(selected_area, _tg_weeks)
        transfer_recommended = {
            k: v for k, v in _all_transfer_recs.items() if k in _transfer_ki_keys
        }

        st.caption(
            t("Key indicators for **{cycle}** — {weeks} weeks. REC is a light "
              "stretch goal, about {pct}% above this area's own typical weekly "
              "performance, times this cambio's real length. Any indicator with "
              "an expectation saved in Area Expectation Settings shows goal / "
              "that expectation sized to this cambio: a transfer-cadence figure "
              "as-is, a weekly one times {weeks} weeks. An indicator with no "
              "expectation shows no fraction at all — nobody has said what the "
              "bar is. These are separate boxes from the weekly Nightly Form "
              "Goals above; the two are not kept in sync.",
              cycle=_tg_label, weeks=fmt_number(_tg_weeks, 0) if _tg_weeks == int(_tg_weeks) else fmt_number(_tg_weeks, 1),
              pct=get_rec_stretch_pct())
        )

        def _apply_all_transfer_rec(area: str, recommended: dict, defs: list) -> None:
            """on_click callback: fill every transfer-goal input with its
            recommended value in one go."""
            for key, _lbl, _ft in defs:
                if key in recommended:
                    st.session_state[f"tgoal_{area}_{key}"] = int(recommended[key])

        if transfer_recommended and _may_edit_transfer:
            with st.container(key="fillalltransferrec"):
                st.button(
                    t("FILL ALL RECOMMENDED"),
                    key="fillall_transfer_btn",
                    on_click=_apply_all_transfer_rec,
                    args=(selected_area, transfer_recommended, transfer_ki_defs),
                )

        # Denominators are DYNAMIC: every KI whose category defines an
        # expectation gets a "/N" fraction. A transfer-cadence expectation counts
        # as-is; a weekly one scales by the cycle's real weeks. ceil, floored at
        # 1 — a fraction out of 0 means nothing.
        #
        # Provo had two derived fallbacks here for KIs with no explicit
        # expectation: Renew's was the maximum possible Recent-Convert
        # attendances, and Mate's was the area's NM Lessons expectation scaled up.
        # Both are gone. CCSM's weekly form asks no rc_total — there is no
        # recent-convert headcount anywhere in its data — so that denominator
        # could only ever have been 0, and "3 / 0" is worse than no fraction.
        def _area_transfer_exp_target(key: str) -> int | None:
            _e = get_area_expectation_entry(selected_area, key)
            if not _e:
                return None
            _v = _e["value"] if _e["cadence"] == "transfer" else _e["weekly"] * _tg_weeks
            return max(1, math.ceil(_v))

        _transfer_denominators: dict[str, int] = {}
        for _tk, _tlbl, _tft in transfer_ki_defs:
            _t = _area_transfer_exp_target(_tk)
            if _t is not None:
                _transfer_denominators[_tk] = _t

        # 3-per-row, not 4. These are the long descriptive KI names, and at
        # 4-per-row's narrower column "Nuevas Personas Encontradas" and
        # "Amigos en la Iglesia (Primera Semana)" wrap to a second line — which
        # pushes the input box down while its REC pill and "/N" overlay
        # (position:absolute, at a fixed top offset calibrated for a one-line
        # label — see the frozen CSS block above) stay put and land ON the
        # label. That block names this exact remedy and forbids re-anchoring to
        # fix it, which is the reason Mission Goals used 3-per-row too.
        #
        # A flat st.columns(3) on the trailing row of one, rather than sizing the
        # row to what is left: a lone box in a full-width column is a different
        # width from the six above it.
        transfer_values = {}
        for i in range(0, len(transfer_ki_defs), 3):
            cols = st.columns(3)
            for col, (key, label, _f) in zip(cols, transfer_ki_defs[i : i + 3]):
                with col:
                    widget_key = f"tgoal_{selected_area}_{key}"
                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = _transfer_current(key)
                    transfer_values[key] = st.number_input(
                        label,
                        min_value=0,
                        step=1,
                        key=widget_key,
                        disabled=not _may_edit_transfer,
                    )
                    if key in _transfer_denominators:
                        _render_fraction_overlay("tg", key, transfer_values[key],
                                                 _transfer_denominators[key])
                    if key in transfer_recommended and _may_edit_transfer:
                        _render_rec_pill("tg", key, widget_key, transfer_recommended[key])

        # A roster-capped KI has a ceiling no amount of work can pass: every
        # recent convert the area has, at church every Sunday of the cycle. The
        # REC is already clamped to it in get_recommended_transfer_goals; this
        # says the number out loud, because a REC of 12 where the area's average
        # implies 14 is otherwise unexplained.
        #
        # What leadership TYPES is deliberately NOT clamped. A baptism during
        # the cycle raises the real ceiling, and the companionship's own goal
        # box is where that expectation belongs — the app does not know a
        # baptism is coming and must not overrule someone who does.
        _tg_weekly_df = get_weekly_form_data()
        for _ck, _clbl, _cft in transfer_ki_defs:
            _ceiling = roster_ceiling(_tg_weekly_df, _ck, selected_area, _tg_weeks)
            if _ceiling is None:
                continue
            _sundays = max(1, int(round(_tg_weeks)))
            st.caption(t(
                "{label}: this area's ceiling for this cambio is {ceiling} — "
                "{roster} at church every one of its {sundays} Sundays. The "
                "recommendation never goes above it.",
                label=_clbl, ceiling=fmt_int(_ceiling),
                roster=fmt_int(int(_ceiling / _sundays)), sundays=fmt_int(_sundays)))
            if int(transfer_values.get(_ck, 0) or 0) > _ceiling:
                st.warning(t(
                    "{label}: {value} is above that ceiling of {ceiling}. Save it "
                    "only if you expect another baptism during the cambio — the "
                    "ceiling rises when the area does.",
                    label=_clbl, value=fmt_int(transfer_values.get(_ck, 0)),
                    ceiling=fmt_int(_ceiling)))

        if not _may_edit_transfer:
            st.caption(t("Only the mission president and the assistants can set "
                         "goals for a cambio."))
        elif st.button(t("Save goals for this transfer"), type="primary",
                       key="area_transfer_save"):
            try:
                def _tv(key: str) -> int:
                    return int(transfer_values.get(key, _transfer_current(key)))

                # Every KI actually on screen, not six fixed Provo keyword args.
                # Those evaluated to 0 for CCSM, so the predecessor of this
                # button reported "saved" and stored nothing the user had typed.
                _row, _err = upsert_area_transfer_goal(
                    selected_area,
                    _tg_start,
                    goals={k: _tv(k) for k, _lbl, _ft in transfer_ki_defs},
                    set_by=user.get("email", ""),
                    transfer_number=str(_tg_cycle.get("number") or ""),
                )
                if _err:
                    st.error(t('Failed to save goals: {err}', err=_err))
                else:
                    st.success(t('Goals saved for **{selected_area}** — {cycle}.',
                                 selected_area=selected_area, cycle=_tg_label))
            except Exception as e:
                st.error(t('Failed to save goals: {e}', e=e))

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
                get_recommended_transfer_goals.clear()
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
                # numbered=False: these are the area-type categories inside one
                # section, drawn in a loop — numbering them would make each
                # category read as a peer of the page's real sections.
                render_section_label(_display_category, emphasis=True,
                                     numbered=False)
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
            # "transfer" joined weekly/monthly for Step 7 (PLAN §7.4h): the
            # mission plans in six-week cycles, and an expectation entered per
            # cambio was previously narrowed to per week — an eightfold
            # overstatement, silently.
            _rows_by_cadence: dict[str, list[dict]] = {
                "weekly": [], "monthly": [], "transfer": []}
            for _r in _cat_rows:
                _rows_by_cadence.setdefault(_r["cadence"], []).append(_r)

            for _cadence, _cadence_heading in (
                ("weekly", "Weekly Goals"), ("monthly", "Monthly Goals"),
                ("transfer", "Goals per Transfer"),
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
                    st.caption(f"**{t(_cadence_heading)}**")
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
                                        t("Cadence"), _CADENCES,
                                        index=(_CADENCES.index(_row["cadence"])
                                               if _row["cadence"] in _CADENCES else 0),
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
                    t("Cadence"), _CADENCES,
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

