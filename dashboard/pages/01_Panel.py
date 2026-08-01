"""
01_Panel.py
────────────────────────────────────────────────────────────────────────────────
Whole-mission executive snapshot — combines the former Dashboard and Mission
Breakdown pages into one. Mission-level only; for zone/district/area drilldown
use the Breakdowns page.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_page_header, render_sidebar,
    render_section_label, render_kpi_row, render_table,
)
from app.config.flavor_loader import flavor, METRIC_LABELS
from app.config.metric_catalog import key_indicator_metrics
from app.i18n import t
from app.config.theme import CHART_COLORS
from app.db.queries import (
    get_mission_totals,
    get_zone_totals,
    get_effort_data,
    get_effort_by_area,
    get_weekly_ki_trends,
    get_weekly_ki_totals,
    exclude_current_week,
    get_daily_summary,
    get_alltime_compliance,
    get_mission_goals,
    get_submitting_areas,
    get_daily_log,
    get_weekly_submission_data,
    get_config_value,
)
from app.utils.area_helpers import (
    compliance_anchor_date, build_calendar_data,
    latest_due_sunday, weekly_due_weeks,
)
from datetime import date, timedelta

st.set_page_config(
    page_title="CCSM · Dashboard — PMG Compass",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

_mission_name = get_config_value("MISSION_NAME", flavor.display_name)
render_page_header(t("PMG Compass"),
                   t("{mission} — Executive Dashboard", mission=_mission_name))

_EMPTY_MSG = t("No data for this section yet.")

st.caption(
    t("Summary data refreshes daily at noon. Submission compliance is computed "
      "live. Mission-level only — drill into a zone, district or area on the "
      "Breakdowns page.")
)


# ── Load data ─────────────────────────────────────────────────────────────────

mission_df = get_mission_totals()
zone_df    = get_zone_totals()
effort_df  = get_effort_data()
trends_df  = get_weekly_ki_trends(8)
daily_df   = get_daily_summary(7)
ki_df      = get_weekly_ki_totals(8)
app_goals  = get_mission_goals()

all_empty = (
    mission_df.empty
    and zone_df.empty
    and trends_df.empty
    and daily_df.empty
    and ki_df.empty
)
if all_empty:
    st.info(_EMPTY_MSG)
    st.stop()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mission_val(metric_key: str, col: str = "val_7d") -> float:
    if mission_df.empty or "metric_key" not in mission_df.columns:
        return 0.0
    row = mission_df[mission_df["metric_key"] == metric_key]
    if row.empty:
        return 0.0
    return float(row.iloc[0].get(col, 0) or 0)


def _mission_goal(metric_key: str) -> float:
    if not mission_df.empty and "metric_key" in mission_df.columns:
        row = mission_df[mission_df["metric_key"] == metric_key]
        if not row.empty and float(row.iloc[0].get("goal_weekly", 0) or 0) > 0:
            return float(row.iloc[0]["goal_weekly"])
    return float(app_goals.get(metric_key, 0) or 0)


def _ki_val(metric_key: str) -> float:
    """Latest-week mission total for a weekly-form KI metric."""
    if ki_df.empty or metric_key not in ki_df.columns:
        return 0.0
    return float(ki_df.iloc[-1][metric_key])


# ═══════════════════════════════════════════════════════════════════════════════
# 1. NIGHTLY ACTIVITY — mission totals, last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Nightly Activity — Last 7 Days"))

_nightly_keys = flavor.nightly_highlights
if not _nightly_keys:
    st.info(_EMPTY_MSG)
else:
    render_kpi_row([
        {
            "label": METRIC_LABELS.get(k, k),
            "value": int(_mission_val(k)),
            "goal":  _mission_goal(k),
        }
        for k in _nightly_keys
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# 2. KEY INDICATOR TILES — weekly form, latest week
# ═══════════════════════════════════════════════════════════════════════════════
# Was a fixed Pew / Date / Gate / Renew row: Utah Provo's four Key Indicators,
# none of which is a column in CCSM's WEEKLY_KI. _ki_val returns 0.0 for a
# missing column, so this row showed four zeroes under four English labels for
# every week the mission ever reported — a plausible screen, not an error.
#
# CCSM's KIs are the seven `ki_*_real` values the weekly form collects. `_real`
# only: the matching `_meta` keys are that companionship's GOAL for the week and
# belong beside a value as a target, never in a row of achieved results.
ki_week = str(ki_df.iloc[-1]["week_end_date"]) if not ki_df.empty else ""
render_section_label(
    t("Key Indicators — Week Ending {week}", week=ki_week) if ki_week
    else t("Key Indicators")
)

_ki_metrics = key_indicator_metrics()
if not _ki_metrics:
    st.info(_EMPTY_MSG)
else:
    render_kpi_row([
        {
            "label": METRIC_LABELS.get(k, label),
            "value": int(_ki_val(k)),
            "goal":  _mission_goal(k),
        }
        for k, label in _ki_metrics.items()
    ])

# ═══════════════════════════════════════════════════════════════════════════════
# 3. ZONE LEADERBOARD — flavor-driven columns, ranked (last 7 days)
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Zone Leaderboard — Last 7 Days"))

if (zone_df.empty or "metric_key" not in zone_df.columns
        or "zone" not in zone_df.columns or not flavor.nightly_highlights):
    st.info(_EMPTY_MSG)
else:
    _kpi_keys = flavor.nightly_highlights
    zone_rows = []
    for zone_name, grp in zone_df.groupby("zone"):
        row: dict = {"Zone": zone_name}
        for key in _kpi_keys:
            mrow = grp[grp["metric_key"] == key]
            row[key] = float(mrow.iloc[0]["val_7d"]) if not mrow.empty else 0.0
        zone_rows.append(row)

    if not zone_rows:
        st.info(_EMPTY_MSG)
    else:
        rename_map = {k: METRIC_LABELS.get(k, k) for k in _kpi_keys}
        zone_tbl = pd.DataFrame(zone_rows).rename(columns=rename_map)
        display_cols = [METRIC_LABELS.get(k, k) for k in _kpi_keys]
        for col in display_cols:
            zone_tbl[col] = zone_tbl[col].astype(int)
        sort_col = display_cols[0]
        zone_tbl = zone_tbl.sort_values(sort_col, ascending=False).reset_index(drop=True)
        zone_tbl.insert(0, "Rank", range(1, len(zone_tbl) + 1))
        zone_tbl = zone_tbl[["Rank", "Zone"] + display_cols]
        render_table(zone_tbl)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. EIGHT-WEEK TRENDS (mission totals)
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("8-Week Trend — Mission Totals"))

trends_chart = exclude_current_week(trends_df)
ki_chart     = exclude_current_week(ki_df)
if trends_chart.empty or "week_end_date" not in trends_chart.columns:
    st.info(_EMPTY_MSG)
else:
    weeks = trends_chart["week_end_date"].astype(str)

    col_a, col_b = st.columns(2)

    with col_a:
        fig1 = go.Figure()
        for i, key in enumerate(flavor.nightly_highlights):
            if key in trends_chart.columns:
                fig1.add_trace(go.Scatter(
                    x=weeks, y=trends_chart[key], mode="lines+markers",
                    name=METRIC_LABELS.get(key, key),
                    line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                    marker=dict(size=6),
                ))
        fig1.update_layout(
            title=t("Nightly Activity"),
            xaxis_title=t("Week Ending"), yaxis_title=t("Count"),
            xaxis_type="category", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, b=40, l=40, r=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        fig2 = go.Figure()
        ki_weeks = ki_chart["week_end_date"].astype(str) if not ki_chart.empty else weeks
        for i, key in enumerate(key_indicator_metrics()):
            if not ki_chart.empty and key in ki_chart.columns:
                fig2.add_trace(go.Scatter(
                    x=ki_weeks, y=ki_chart[key], mode="lines+markers",
                    name=METRIC_LABELS.get(key, key),
                    line=dict(color=CHART_COLORS[(i + 2) % len(CHART_COLORS)], width=2),
                    marker=dict(size=6),
                ))
        fig2.update_layout(
            title=t("Key Indicators"),
            xaxis_title=t("Week Ending"), yaxis_title=t("Count"),
            xaxis_type="category", hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, b=40, l=40, r=20),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. DAILY TREND — headline nightly metric, last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
# Was hardcoded to nm_lessons ("Non-Member Lessons per Day"). CCSM's nightly
# form has no such question, so the guard below always fell to _EMPTY_MSG and
# this section has never drawn anything.
_daily_key = next(
    (k for k in flavor.nightly_highlights if k in daily_df.columns),
    "",
) if not daily_df.empty else ""
_daily_label = METRIC_LABELS.get(_daily_key, _daily_key)

render_section_label(
    t("Daily {metric} — Last 7 Days", metric=_daily_label) if _daily_key
    else t("Daily Trend — Last 7 Days")
)

if not _daily_key:
    st.info(_EMPTY_MSG)
else:
    date_col = "Date" if "Date" in daily_df.columns else daily_df.columns[0]
    fig_daily = px.bar(
        daily_df,
        x=date_col,
        y=_daily_key,
        labels={date_col: t("Date"), _daily_key: _daily_label},
        title=t("{metric} per day (mission total)", metric=_daily_label),
        color_discrete_sequence=["#6366f1"],
    )
    fig_daily.update_layout(
        xaxis_title=t("Date"),
        xaxis_type="category",
        yaxis_title=_daily_label,
        margin=dict(t=40, b=20),
    )
    st.plotly_chart(fig_daily, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 6. DAILY EFFORT BREAKDOWN — last 7 days
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Daily Effort Breakdown — Last 7 Days"))

if effort_df.empty:
    st.info(_EMPTY_MSG)
else:
    all_count  = int(effort_df["all_count"].sum())
    most_count = int(effort_df["most_count"].sum())
    some_count = int(effort_df["some_count"].sum())

    effort_data = pd.DataFrame({
        "Effort Level": ["All", "Most", "Some"],
        "Count":        [all_count, most_count, some_count],
    })

    fig_effort = px.bar(
        effort_data,
        x="Effort Level",
        y="Count",
        color="Effort Level",
        color_discrete_map={
            "All":  "#22c55e",
            "Most": "#f59e0b",
            "Some": "#ef4444",
        },
        title="Area Effort Levels Across Last 7 Days",
    )
    fig_effort.update_layout(
        showlegend=False,
        margin=dict(t=40, b=20),
        yaxis_title="Day-Area Count",
    )
    st.plotly_chart(fig_effort, use_container_width=True)

    e1, e2, e3 = st.columns(3)
    e1.metric(t("All Effort"),  all_count,  help=t("Areas reporting full effort"))
    e2.metric(t("Most Effort"), most_count, help=t("Areas reporting most effort"))
    e3.metric(t("Some Effort"), some_count, help=t("Areas reporting some effort"))

    area_effort = get_effort_by_area(days=7)
    with st.expander(t("Effort by area — who reported what (last 7 days)")):
        if area_effort.empty:
            st.caption(t("No per-area effort responses in the last 7 days."))
        else:
            st.caption(
                t("{n} areas · sorted by effort score "
                  "(All=3, Most=2, Some=1, averaged per submission). "
                  "Counts are submissions per area over the last 7 days.",
                  n=len(area_effort))
            )
            render_table(area_effort)

# ═══════════════════════════════════════════════════════════════════════════════
# 7. SUBMISSION COMPLIANCE — all-time summary, calendars, per-area detail
# ═══════════════════════════════════════════════════════════════════════════════
render_section_label(t("Submission Compliance"))

comp_df = get_alltime_compliance()

if comp_df.empty:
    mission_pct, days_tracked, areas_current, total_forms = "—", "—", "—", "—"
else:
    total_sub      = int(comp_df["days_submitted"].sum())
    total_possible = int(comp_df["days_possible"].sum())
    mission_pct    = round(total_sub / total_possible * 100) if total_possible else 0
    days_tracked   = int(comp_df["days_possible"].max())
    areas_current  = int((comp_df["pct"] >= 100).sum())
    total_forms    = total_sub

render_kpi_row([
    {"label": "Total Forms Submitted", "value": str(total_forms)},
    {"label": "Compliance All-Time", "value": f"{mission_pct}%" if mission_pct != "—" else "—"},
    {"label": "Days Tracked",        "value": str(days_tracked)},
    {"label": "Areas at 100%",       "value": str(areas_current)},
])

# ── Nightly submission compliance — daily % calendar heatmap ──────────────────
render_section_label(t("Nightly Submission Compliance — Daily %"))

_subm_areas  = get_submitting_areas()
_daily_all   = get_daily_log(days=45)
_total_areas = (
    _subm_areas["Area_Name"].astype(str).str.strip().nunique()
    if not _subm_areas.empty and "Area_Name" in _subm_areas.columns else 0
)

if _total_areas == 0 or _daily_all.empty or "Date" not in _daily_all.columns:
    st.info(t("No nightly compliance data yet."))
else:
    _submitting_set = set(_subm_areas["Area_Name"].dropna().astype(str).str.strip())
    _dl = _daily_all.copy()
    _dl["Area"] = _dl["Area"].astype(str).str.strip()
    _dl = _dl[_dl["Area"].isin(_submitting_set)]
    _per_day_counts = _dl.groupby("Date")["Area"].nunique().to_dict()

    _mb_sys_start = get_config_value("SYSTEM_START_DATE", "")
    _mb_anchor    = compliance_anchor_date()
    _mb_win_end   = _mb_anchor.isoformat()
    _mb_thirty    = (_mb_anchor - timedelta(days=29)).isoformat()
    _mb_win_start = max(_mb_sys_start, _mb_thirty) if _mb_sys_start else _mb_thirty

    _mb_cal = build_calendar_data(set(), _mb_win_end, n_weeks=5, anchor_date=_mb_anchor)

    def _mb_pct_color(p: int):
        if p >= 85:
            return "rgba(34,197,94,0.25)", "#22c55e"
        if p >= 70:
            return "rgba(245,158,11,0.22)", "#f59e0b"
        return "rgba(239,68,68,0.20)", "#ef4444"

    _mb_day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _mb_hdr = "".join(
        f'<th style="text-align:center;padding:4px 8px;color:#9ca3af;font-size:0.72rem;font-weight:600;">{d}</th>'
        for d in _mb_day_labels
    )

    _counted_pcts = []
    _mb_body = ""
    for week in _mb_cal:
        cells = ""
        for cell in week:
            d = cell["date"]
            day_num = d[8:]
            if cell["future"]:
                bg, fg, pct_txt, title = "rgba(255,255,255,0.02)", "#374151", "", f"{d} — upcoming"
            elif d < _mb_win_start:
                bg, fg, pct_txt, title = "rgba(255,255,255,0.03)", "#4b5563", "", f"{d} — before tracking started"
            else:
                n = _per_day_counts.get(d, 0)
                pct = round(n / _total_areas * 100) if _total_areas else 0
                _counted_pcts.append(pct)
                bg, fg = _mb_pct_color(pct)
                pct_txt = f"{pct}%"
                title = f"{d} — {n}/{_total_areas} areas submitted ({pct}%)"
            pct_html = (
                f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{pct_txt}</div>'
                if pct_txt else '<div style="font-size:0.8rem;">&nbsp;</div>'
            )
            cells += (
                f'<td title="{title}" style="text-align:center;padding:5px 4px;background:{bg};'
                f'border-radius:4px;vertical-align:middle;">'
                f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1;">{day_num}</div>'
                f'{pct_html}</td>'
            )
        _mb_body += f"<tr>{cells}</tr>"

    def _mb_legend_item(color, label):
        return (
            f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
            f'border-radius:2px;margin-right:4px;"></span>{label}&nbsp;&nbsp;&nbsp;'
        )

    st.markdown(
        f'<table style="width:100%;border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<thead><tr>{_mb_hdr}</tr></thead><tbody>{_mb_body}</tbody></table>'
        f'<div style="font-size:0.72rem;color:#9ca3af;margin-bottom:0.5rem;">'
        + _mb_legend_item("rgba(34,197,94,0.25)", "&ge;85%")
        + _mb_legend_item("rgba(245,158,11,0.22)", "70–84%")
        + _mb_legend_item("rgba(239,68,68,0.20)", "&lt;70%")
        + _mb_legend_item("rgba(255,255,255,0.03)", "Upcoming / pre-tracking")
        + "</div>",
        unsafe_allow_html=True,
    )

    if _counted_pcts:
        _avg = round(sum(_counted_pcts) / len(_counted_pcts))
        st.markdown(
            f'<p style="color:#9ca3af;font-size:0.82rem;">Each box is the share of the mission\'s '
            f'<strong style="color:#f4f4f8;">{_total_areas}</strong> submitting areas that turned in '
            f'the nightly form that day. Window average: '
            f'<strong style="color:#f4f4f8;">{_avg}%</strong>.</p>',
            unsafe_allow_html=True,
        )

# ── Weekly report submission — % of areas submitting the weekly form, by week ─
render_section_label(t("Weekly Report Submission — By Week"))

_nightly_avg = (
    sum(_counted_pcts) / len(_counted_pcts)
    if "_counted_pcts" in locals() and _counted_pcts else None
)

_wk_all       = get_weekly_submission_data()
_wk_sys_start = get_config_value("SYSTEM_START_DATE", "")
_wk_anchor    = latest_due_sunday()
_wk_due_weeks = weekly_due_weeks(_wk_sys_start, anchor_sunday=_wk_anchor, n_weeks=8)

def _wk_leg(color, label):
    return (
        f'<span style="display:inline-block;width:10px;height:10px;background:{color};'
        f'border-radius:2px;margin-right:4px;"></span>{label}&nbsp;&nbsp;&nbsp;'
    )

_weekly_avg = None
if _total_areas == 0 or not _wk_due_weeks:
    st.info(t("No weekly submission data yet."))
else:
    _wk_submitting = (
        set(_subm_areas["Area_Name"].dropna().astype(str).str.strip())
        if not _subm_areas.empty and "Area_Name" in _subm_areas.columns else set()
    )
    if not _wk_all.empty and "area" in _wk_all.columns:
        _wk = _wk_all.copy()
        _wk["area"] = _wk["area"].astype(str).str.strip()
        if _wk_submitting:
            _wk = _wk[_wk["area"].isin(_wk_submitting)]
        _per_week_counts = _wk.groupby("week_end_date")["area"].nunique().to_dict()
    else:
        _per_week_counts = {}

    def _wk_pct_color(p):
        if p >= 85:
            return "rgba(34,197,94,0.25)", "#22c55e"
        if p >= 70:
            return "rgba(245,158,11,0.22)", "#f59e0b"
        return "rgba(239,68,68,0.20)", "#ef4444"

    _wk_pcts, _wk_cells = [], ""
    for w in _wk_due_weeks:
        _wd = date.fromisoformat(w)
        n   = _per_week_counts.get(w, 0)
        pct = round(n / _total_areas * 100) if _total_areas else 0
        _wk_pcts.append(pct)
        bg, fg = _wk_pct_color(pct)
        _wk_cells += (
            f'<td title="Week ending {w} — {n}/{_total_areas} areas submitted ({pct}%)" '
            f'style="text-align:center;padding:6px 8px;background:{bg};border-radius:4px;'
            f'vertical-align:middle;min-width:52px;">'
            f'<div style="font-size:0.6rem;color:#9ca3af;line-height:1.2;">{_wd.month}/{_wd.day}</div>'
            f'<div style="font-size:0.8rem;font-weight:700;color:{fg};">{pct}%</div></td>'
        )
    st.markdown(
        '<table style="border-collapse:separate;border-spacing:3px;margin-bottom:0.5rem;">'
        f'<tbody><tr>{_wk_cells}</tr></tbody></table>'
        '<div style="font-size:0.72rem;color:#9ca3af;margin-bottom:0.5rem;">'
        + _wk_leg("rgba(34,197,94,0.25)", "&ge;85%")
        + _wk_leg("rgba(245,158,11,0.22)", "70–84%")
        + _wk_leg("rgba(239,68,68,0.20)", "&lt;70%")
        + '</div>',
        unsafe_allow_html=True,
    )

    _weekly_avg = sum(_wk_pcts) / len(_wk_pcts) if _wk_pcts else None
    if _weekly_avg is not None:
        st.markdown(
            f'<p style="color:#9ca3af;font-size:0.82rem;">Each box is the share of the mission\'s '
            f'<strong style="color:#f4f4f8;">{_total_areas}</strong> areas that submitted the weekly '
            f'form for that Mon–Sun week (credited by the day it arrived). Window average: '
            f'<strong style="color:#f4f4f8;">{round(_weekly_avg)}%</strong>.</p>',
            unsafe_allow_html=True,
        )

if _nightly_avg is not None and _weekly_avg is not None:
    _combined = round((_nightly_avg + _weekly_avg) / 2)
    _cc = "#22c55e" if _combined >= 85 else ("#f59e0b" if _combined >= 70 else "#ef4444")
    st.markdown(
        f'<div style="margin-top:0.5rem;padding:10px 14px;border-radius:6px;'
        f'background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);">'
        f'<span style="color:#9ca3af;font-size:0.82rem;">Combined submission compliance '
        f'(nightly + weekly, averaged): </span>'
        f'<strong style="color:{_cc};font-size:1.05rem;">{_combined}%</strong>'
        f'<span style="color:#6b7280;font-size:0.75rem;"> &nbsp;— nightly {round(_nightly_avg)}%, '
        f'weekly {round(_weekly_avg)}%</span></div>',
        unsafe_allow_html=True,
    )

# ── Per-area submission detail (folded in from the old Submissions page) ───────
with st.expander(t("Area Submission Detail — all-time compliance per area")):
    if comp_df.empty:
        st.info(t("No per-area submission data available yet."))
    else:
        detail = comp_df.copy()

        def _sub_status(pct: float) -> str:
            if pct >= 90:
                return "On Track"
            if pct >= 50:
                return "Partial"
            return "Behind"

        detail["Status"] = detail["pct"].apply(_sub_status)

        f1, f2 = st.columns([2, 2])
        # Sentinel is translated for display but compared against the same
        # t() call below, never against a bare English literal.
        _all_zones = t("All Zones")
        zone_opts = [_all_zones] + sorted(detail["zone"].dropna().astype(str).unique().tolist())
        with f1:
            zsel = st.selectbox(t("Zone"), zone_opts, key="dash_sub_zone")
        with f2:
            # Translated label -> English value. Only the label is shown; every
            # comparison below still runs on the English value, so filtering
            # behaves identically in either language.
            _show_opts = {
                t("All"): "All",
                t("Behind only"): "Behind only",
                t("On Track only"): "On Track only",
            }
            ssel = _show_opts[st.radio(
                t("Show"), list(_show_opts),
                horizontal=True, key="dash_sub_show",
            )]

        view = detail
        if zsel != _all_zones:
            view = view[view["zone"] == zsel]
        if ssel == "Behind only":
            view = view[view["Status"] == "Behind"]
        elif ssel == "On Track only":
            view = view[view["Status"] == "On Track"]

        view = view.sort_values(["pct", "area"], ascending=[True, True])

        # Headers are translated only at the point of display, after every
        # filter and sort above has run on the English column names.
        _cols = {
            "area": t("Area"), "zone": t("Zone"), "district": t("District"),
            "days_submitted": t("Days Submitted"),
            "days_possible": t("Days Possible"),
            "pct": t("Compliance %"), "last_date": t("Last Submitted"),
            "Status": t("Status"),
        }
        disp = view.rename(columns=_cols)[list(_cols.values())]
        # detail["Status"] stays English so the filters above keep working;
        # translate the cell values for display only.
        disp[t("Status")] = disp[t("Status")].map(lambda s: t(s))

        st.caption(t("{n} area(s) shown — worst first", n=len(disp)))
        if disp.empty:
            st.info(t("No areas match the current filter."))
        else:
            render_table(disp)
