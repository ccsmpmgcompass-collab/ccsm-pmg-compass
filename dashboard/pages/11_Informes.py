"""
11_Informes.py
────────────────────────────────────────────────────────────────────────────────
The mission's weekly report — one week, one scope, everything on a page you can
print or export.

Built from what CCSM actually collects: WEEKLY_KI (the seven Key Indicators,
real against the companionship's own goal), DAILY_LOG (nightly activity),
SCORES, and MISSION_ORG for the roster.

Utah Provo's version of this page read TABLEAU_DETAIL / TABLEAU_RANKING /
TABLEAU_BAPTISMS and hardcoded a Provo stake list. COMPASS_CCSM has none of
those tabs, which is why that page was cut from this app rather than ported.
Nothing here depends on an export anyone has to remember to upload.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_kpi_row, render_page_header, render_section_label,
    render_sidebar, render_table,
)
from app.config.flavor_loader import METRIC_LABELS, flavor
from app.config.metric_catalog import (
    goal_metric_key, key_indicator_metrics, non_numeric_metrics,
    nightly_metrics,
)
from app.db.queries import (
    get_areas_df, get_config_value, get_daily_log, get_scored_weeks, get_scores,
    get_weekly_ki,
)
from app.i18n import t
from app.i18n.formats import NA, fmt_date, fmt_int, fmt_number, fmt_percent

st.set_page_config(
    page_title="CCSM · Informes — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

_mission = get_config_value("MISSION_NAME", flavor.display_name)
render_page_header(t("Reports"), t("{mission} — weekly mission report",
                                   mission=_mission))

# ── Week and scope ────────────────────────────────────────────────────────────

_ki = get_weekly_ki()
_ki_weeks = (
    sorted({str(w)[:10] for w in _ki["week_end_date"].astype(str)
            if str(w).strip() and str(w) != "nan"}, reverse=True)
    if not _ki.empty and "week_end_date" in _ki.columns else []
)
_weeks = _ki_weeks or get_scored_weeks()

if not _weeks:
    st.info(
        t("No reported week yet. This page fills in once the weekly form has "
          "been submitted and the agents have written WEEKLY_KI.")
    )
    st.stop()

_ALL = t("Whole mission")
_zones = sorted({z for z in get_areas_df().get("Zone", pd.Series(dtype=str))
                 .astype(str) if z and z != "nan"})

_c1, _c2 = st.columns(2)
with _c1:
    _week = st.selectbox(t("Week ending"), _weeks, format_func=fmt_date,
                         key="rep_week")
with _c2:
    _zone = st.selectbox(t("Scope"), [_ALL] + _zones, key="rep_zone")

_scoped = _zone != _ALL

# Areas in scope, from the roster — so an area that reported nothing still
# counts against compliance instead of vanishing from the denominator.
_areas_df = get_areas_df()
if _scoped and "Zone" in _areas_df.columns:
    _areas_df = _areas_df[_areas_df["Zone"].astype(str) == _zone]
_area_names = set(_areas_df.get("Area_Name", pd.Series(dtype=str)).astype(str))

st.caption(
    t("Week ending {week} · {scope} · {areas} area(s)",
      week=fmt_date(_week), scope=_zone if _scoped else _ALL,
      areas=fmt_int(len(_area_names)))
)

# ── 1. Key Indicators ─────────────────────────────────────────────────────────

render_section_label(t("Key Indicators"))

_ki_week = _ki[_ki["week_end_date"].astype(str).str[:10] == _week] if not _ki.empty else pd.DataFrame()
if _scoped and not _ki_week.empty and "area" in _ki_week.columns:
    _ki_week = _ki_week[_ki_week["area"].astype(str).isin(_area_names)]

_ki_metrics = key_indicator_metrics()

if _ki_week.empty or not _ki_metrics:
    st.info(t("No weekly Key Indicator data for this week and scope."))
else:
    _rows = []
    for _key, _label in _ki_metrics.items():
        if _key not in _ki_week.columns:
            continue
        _real = pd.to_numeric(_ki_week[_key], errors="coerce").sum()
        # The companionship's own goal for the week, when the form collects
        # one. A goal sits BESIDE a result as a target — never added to it,
        # and never presented as an achievement.
        _goal_key = goal_metric_key(_key)
        _goal = (pd.to_numeric(_ki_week[_goal_key], errors="coerce").sum()
                 if _goal_key and _goal_key in _ki_week.columns else None)
        _rows.append({
            t("Key Indicator"): _label,
            t("Achieved"): fmt_int(_real),
            t("Goal set"): fmt_int(_goal) if _goal is not None else NA,
            t("% of goal"): (fmt_percent(_real / _goal * 100)
                             if _goal else NA),
        })
    if _rows:
        render_table(pd.DataFrame(_rows))
    else:
        st.info(t("No weekly Key Indicator data for this week and scope."))

# ── 2. Nightly activity for the week ──────────────────────────────────────────

render_section_label(t("Nightly Activity"))

# WEEKLY_KI weeks end on the reported Sunday; the nightly week is the seven
# days ending that Sunday.
# datetime.timedelta, not pd.Timedelta: pandas emits a DeprecationWarning here
# about the generic NumPy timedelta unit that is documented to become an error.
try:
    _end = pd.to_datetime(_week).date()
    _start = _end - timedelta(days=6)
except (ValueError, TypeError):
    _end = _start = None

_daily = get_daily_log(365)
if _daily.empty or _start is None or "Date" not in _daily.columns:
    st.info(t("No nightly data for this week."))
else:
    _d = _daily[
        (_daily["Date"].astype(str) >= _start.isoformat())
        & (_daily["Date"].astype(str) <= _end.isoformat())
    ]
    if _scoped and "Area" in _d.columns:
        _d = _d[_d["Area"].astype(str).isin(_area_names)]

    _skip = non_numeric_metrics()
    _cols = [k for k in nightly_metrics() if k not in _skip and k in _d.columns]

    if _d.empty or not _cols:
        st.info(t("No nightly data for this week."))
    else:
        st.caption(t("{start} to {end}",
                     start=fmt_date(_start), end=fmt_date(_end)))
        render_table(pd.DataFrame([
            {t("Metric"): METRIC_LABELS.get(c, c),
             t("Week total"): fmt_int(pd.to_numeric(_d[c], errors="coerce").sum()),
             t("Per area / day"): fmt_number(
                 pd.to_numeric(_d[c], errors="coerce").sum() / len(_d), 1)
             if len(_d) else NA}
            for c in _cols
        ]))

# ── 3. Scores ─────────────────────────────────────────────────────────────────

render_section_label(t("Scores"))

_sc = get_scores(_week)
if _scoped and not _sc.empty and "Zone" in _sc.columns:
    _sc = _sc[_sc["Zone"].astype(str) == _zone]

if _sc.empty:
    st.info(
        t("No scores for this week yet. CCSM_AgentScores writes them on its "
          "weekly run.")
    )
else:
    _score_cols = ["Effort_Score", "Skill_Score", "KI_Score", "Effectiveness_Score"]
    _labels = {
        "Effort_Score": t("Effort"), "Skill_Score": t("Skill"),
        "KI_Score": t("Key Indicators"), "Effectiveness_Score": t("Effectiveness"),
    }
    render_kpi_row([
        {"label": _labels[c], "value": round(float(_sc[c].mean()), 1)}
        for c in _score_cols if c in _sc.columns and _sc[c].notna().any()
    ])

    _tbl = _sc[[c for c in (["Area_Name", "Zone"] + _score_cols)
                if c in _sc.columns]].copy()
    if "Effectiveness_Score" in _tbl.columns:
        _tbl = _tbl.sort_values("Effectiveness_Score", ascending=False)
    for c in _score_cols:
        if c in _tbl.columns:
            _tbl[c] = _tbl[c].map(lambda v: fmt_number(v, 1))
    _tbl = _tbl.rename(columns={**_labels, "Area_Name": t("Area"),
                                "Zone": t("Zone")})
    render_table(_tbl)

# ── 4. Who reported ───────────────────────────────────────────────────────────

render_section_label(t("Weekly Form Compliance"))

if not _area_names:
    st.info(t("No areas in scope."))
else:
    _reported = (set(_ki_week["area"].astype(str))
                 if not _ki_week.empty and "area" in _ki_week.columns else set())
    _missing = sorted(_area_names - _reported)
    _pct = (len(_reported & _area_names) / len(_area_names) * 100)

    render_kpi_row([
        {"label": t("Areas reporting"),
         "value": len(_reported & _area_names), "goal": len(_area_names)},
        {"label": t("Not reported"), "value": len(_missing)},
    ])
    st.caption(t("{pct} of areas in scope submitted the weekly form.",
                 pct=fmt_percent(_pct)))

    if _missing:
        with st.expander(t("Areas with no weekly report ({count})",
                           count=fmt_int(len(_missing)))):
            render_table(pd.DataFrame({t("Area"): _missing}))

# ── Export ────────────────────────────────────────────────────────────────────

render_section_label(t("Export"))

if not _sc.empty:
    st.download_button(
        t("Download scores for this week (CSV)"),
        data=_sc.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"puntajes_{_week}.csv",
        mime="text/csv",
        key="rep_dl_scores",
    )
if not _ki_week.empty:
    st.download_button(
        t("Download Key Indicators for this week (CSV)"),
        data=_ki_week.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"indicadores_{_week}.csv",
        mime="text/csv",
        key="rep_dl_ki",
    )
st.caption(
    t("CSVs are written UTF-8 with a BOM so Excel opens the accents correctly.")
)
