"""
12_Traslados.py
────────────────────────────────────────────────────────────────────────────────
Where the mission is inside the current transfer, and how each area is doing
across it.

Utah Provo's Transfer Flow page ran the area-lineage and transfer-import
machinery — AREA_LINEAGE, TRANSFER_LOG, TRANSFER_IMPORT, a Supabase instance
and a deployed TransferWebApp.gs. CCSM has none of that, which is why that page
was cut rather than ported.

What CCSM does have is TRANSFER_SCHEDULE (Transfer_Number | Start_Date | Weeks |
Status), TRANSFER_START_DATE in AGENT_CONFIG, MISSION_ORG's roster, and
LIVE_SNAPSHOT's `<metric>_transfer` columns — which CCSM_Agent3 computes from
TRANSFER_START_DATE through today. That is enough to answer the questions a
transfer actually raises: which week are we in, who is where, and how has each
area done since it started.

This page is READ-ONLY. It plans nothing and moves nobody.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_kpi_row, render_page_header, render_section_label,
    render_sidebar, render_table,
)
from app.config.flavor_loader import METRIC_LABELS, flavor
from app.config.metric_catalog import non_numeric_metrics, nightly_metrics
from app.db.queries import (
    get_areas_df, get_config_value, get_live_snapshot,
)
from app.db.sheets_client import read_tab
from app.i18n import t
from app.i18n.formats import NA, fmt_date, fmt_int, fmt_number
from app.utils.area_helpers import mission_today

st.set_page_config(
    page_title="CCSM · Traslados — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

render_page_header(
    t("Transfers"),
    t("{mission} — the current transfer cycle",
      mission=get_config_value("MISSION_NAME", flavor.display_name)),
)

_TODAY = mission_today()   # mission-local, not the server's UTC date

# ── Which transfer are we in ──────────────────────────────────────────────────


def _transfer_rows() -> list[dict]:
    """TRANSFER_SCHEDULE as dicts, oldest first. Rows without a usable
    Start_Date are dropped — a schedule row that cannot be placed on a calendar
    cannot tell anyone which week it is."""
    df = read_tab("TRANSFER_SCHEDULE")
    if df.empty or "Start_Date" not in df.columns:
        return []
    out = []
    for _, r in df.iterrows():
        start = str(r.get("Start_Date", "")).strip()[:10]
        try:
            start_d = date.fromisoformat(start)
        except ValueError:
            continue
        try:
            weeks = int(float(str(r.get("Weeks", "")).strip() or 6))
        except (TypeError, ValueError):
            weeks = 6
        out.append({
            "number": str(r.get("Transfer_Number", "")).strip(),
            "start": start_d,
            "weeks": max(1, weeks),
            "status": str(r.get("Status", "")).strip(),
        })
    return sorted(out, key=lambda x: x["start"])


_rows = _transfer_rows()

# Fall back to AGENT_CONFIG when TRANSFER_SCHEDULE has not been filled in. That
# is the same value CCSM_Agent3 uses for its transfer-to-date totals, so the
# window described here and the numbers below always agree.
_fallback_start = (get_config_value("TRANSFER_START_DATE", "") or "").strip()[:10]

_current = next((r for r in reversed(_rows) if r["start"] <= _TODAY), None)

if _current is None and _fallback_start:
    try:
        _current = {"number": "", "start": date.fromisoformat(_fallback_start),
                    "weeks": 6, "status": ""}
    except ValueError:
        _current = None

if _current is None:
    st.info(
        t("No transfer has been scheduled yet. Fill in TRANSFER_SCHEDULE "
          "(Transfer_Number, Start_Date, Weeks, Status), or set "
          "TRANSFER_START_DATE in AGENT_CONFIG.")
    )
    st.stop()

_start = _current["start"]
_weeks = _current["weeks"]
_end = _start + timedelta(weeks=_weeks) - timedelta(days=1)
_elapsed_days = (_TODAY - _start).days
_week_no = max(1, min(_weeks, _elapsed_days // 7 + 1))
_days_left = (_end - _TODAY).days

if not _rows and _fallback_start:
    st.caption(
        t("TRANSFER_SCHEDULE is empty, so this uses TRANSFER_START_DATE from "
          "AGENT_CONFIG and assumes a {weeks}-week cycle.",
          weeks=fmt_int(_weeks))
    )

render_section_label(
    t("Transfer {number}", number=_current["number"]) if _current["number"]
    else t("Current transfer")
)

render_kpi_row([
    {"label": t("Week"), "value": _week_no, "goal": _weeks},
    {"label": t("Days elapsed"), "value": max(0, _elapsed_days)},
    {"label": t("Days remaining"), "value": max(0, _days_left)},
])

st.caption(
    t("{start} to {end} · {weeks} weeks{status}",
      start=fmt_date(_start), end=fmt_date(_end), weeks=fmt_int(_weeks),
      status=f" · {_current['status']}" if _current["status"] else "")
)

if _days_left < 0:
    st.warning(
        t("This transfer ended on {end} and no later one is scheduled. Add "
          "the next row to TRANSFER_SCHEDULE so the transfer-to-date figures "
          "below start counting from the right day.", end=fmt_date(_end))
    )

# ── Schedule ──────────────────────────────────────────────────────────────────

if _rows:
    with st.expander(t("Full transfer schedule ({count})",
                       count=fmt_int(len(_rows)))):
        render_table(pd.DataFrame([{
            t("Transfer"): r["number"] or NA,
            t("Starts"): fmt_date(r["start"]),
            t("Ends"): fmt_date(r["start"] + timedelta(weeks=r["weeks"])
                                - timedelta(days=1)),
            t("Weeks"): fmt_int(r["weeks"]),
            t("Status"): r["status"] or NA,
            t("Current"): "●" if r is _current else "",
        } for r in _rows]))

# ── Performance across the transfer ───────────────────────────────────────────

render_section_label(t("Area Performance This Transfer"))

st.caption(
    t("Totals from the start of the transfer through today, as CCSM_Agent3 "
      "computes them into LIVE_SNAPSHOT. Non-numeric questions are left out — "
      "a running sum of a Sí/No or Todo/Algo answer means nothing.")
)

_snap = get_live_snapshot()

if _snap.empty:
    st.info(
        t("LIVE_SNAPSHOT is empty. CCSM_Agent3 rebuilds it on each run from "
          "DAILY_LOG — check Agent Runs on the Mantenimiento page.")
    )
else:
    _ALL = t("All zones")
    _zones = sorted({z for z in _snap.get("Zone", pd.Series(dtype=str)).astype(str)
                     if z and z != "nan"})
    _zone = st.selectbox(t("Zone"), [_ALL] + _zones, key="tf_zone")
    if _zone != _ALL and "Zone" in _snap.columns:
        _snap = _snap[_snap["Zone"].astype(str) == _zone]

    _skip = non_numeric_metrics()
    _metrics = [k for k in nightly_metrics()
                if k not in _skip and f"{k}_transfer" in _snap.columns]

    if not _metrics:
        st.info(
            t("LIVE_SNAPSHOT has no transfer-to-date columns yet. They appear "
              "once the nightly agent has run against a populated DAILY_LOG.")
        )
    else:
        _default = _metrics[:4]
        _picked = st.multiselect(
            t("Metrics"), options=_metrics, default=_default,
            format_func=lambda k: METRIC_LABELS.get(k, k),
            key="tf_metrics",
        )
        if not _picked:
            st.info(t("Pick at least one metric."))
        else:
            _cols = ["Area"] + (["Zone"] if "Zone" in _snap.columns else [])
            _tbl = _snap[_cols + [f"{m}_transfer" for m in _picked]].copy()
            for _m in _picked:
                _tbl[f"{_m}_transfer"] = _tbl[f"{_m}_transfer"].map(fmt_int)
            _tbl = _tbl.rename(columns={
                **{f"{m}_transfer": METRIC_LABELS.get(m, m) for m in _picked},
                "Area": t("Area"), "Zone": t("Zone"),
            })
            render_table(_tbl)

# ── Roster ────────────────────────────────────────────────────────────────────

render_section_label(t("Roster"))

_org = get_areas_df()
if _org.empty:
    st.info(t("MISSION_ORG has no active areas."))
else:
    _by_zone = (_org.groupby("Zone").size().reset_index(name="n")
                if "Zone" in _org.columns else pd.DataFrame())
    if not _by_zone.empty:
        render_kpi_row(
            [{"label": t("Areas"), "value": int(len(_org))},
             {"label": t("Zones"), "value": int(len(_by_zone))}]
            + ([{"label": t("Districts"),
                 "value": int(_org["District"].nunique())}]
               if "District" in _org.columns else [])
        )

    _cols = [c for c in ("Area_Name", "Zone", "District", "Companion1_Name",
                         "Companion2_Name") if c in _org.columns]
    _roster = _org[_cols].rename(columns={
        "Area_Name": t("Area"), "Zone": t("Zone"), "District": t("District"),
        "Companion1_Name": t("Companion 1"), "Companion2_Name": t("Companion 2"),
    })
    with st.expander(t("Every area ({count})", count=fmt_int(len(_roster)))):
        render_table(_roster)
