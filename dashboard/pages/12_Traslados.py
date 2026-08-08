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

Below the read-only view, this page can also PULL the roster (via the cloud
Playwright job — see Task 6/7), PREVIEW the diff against MISSION_ORG, APPLY
it, and SYNC the nightly/weekly form area dropdowns. No Drive automation —
CCSM has none, and this build doesn't add any.

Two sections, same st.radio()+CSS tab pattern as Provo's 12_Transfer_Flow.py
(and CCSM's own 02_Metas.py/18_Mantenimiento.py) — st.tabs() renders every
tab's body on every single script run regardless of which one is visually
active, so a real tab widget would run the leadership-gated section's sheet
reads even for a viewer who can't see the results:
  • Schedule — the read-only view (current transfer, performance, roster).
  • Roster Update — Pull/Preview/Apply/Sync, leadership-gated. A non-leader
    who selects this tab sees a warning instead of the tools, same as
    Provo's _is_mp_or_ap() fallback — not st.stop(), so the tab picker
    itself always finishes rendering.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.auth.auth import is_leadership, require_auth
from app.components.design_system import (
    inject_global_css, render_kpi_row, render_page_header, render_section_label,
    render_sidebar, render_table,
)
from app.config.flavor_loader import METRIC_LABELS, flavor
from app.config.metric_catalog import non_numeric_metrics, nightly_metrics
from app.db import sheets_client as sc
from app.db.queries import (
    get_areas_df, get_config_value, get_live_snapshot,
)
from app.db.sheets_client import read_tab
from app.i18n import t
from app.i18n.formats import NA, fmt_date, fmt_int, fmt_number
from app.components.cloud_job_ui import CloudJobFailed, CloudJobTimeout, run_cloud_job
from app.ingestion import transfer_apply_service as tas
from app.integrations.transfer_bridge import FormSyncError, form_sync
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


# ── Schedule tab ─────────────────────────────────────────────────────────────

def _render_schedule_tab() -> None:
    # ── Which transfer are we in ────────────────────────────────────────────
    def _transfer_rows() -> list[dict]:
        """TRANSFER_SCHEDULE as dicts, oldest first. Rows without a usable
        Start_Date are dropped — a schedule row that cannot be placed on a
        calendar cannot tell anyone which week it is."""
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

    rows = _transfer_rows()

    # Fall back to AGENT_CONFIG when TRANSFER_SCHEDULE has not been filled in.
    # That is the same value CCSM_Agent3 uses for its transfer-to-date
    # totals, so the window described here and the numbers below always agree.
    fallback_start = (get_config_value("TRANSFER_START_DATE", "") or "").strip()[:10]

    current = next((r for r in reversed(rows) if r["start"] <= _TODAY), None)

    if current is None and fallback_start:
        try:
            current = {"number": "", "start": date.fromisoformat(fallback_start),
                       "weeks": 6, "status": ""}
        except ValueError:
            current = None

    if current is None:
        st.info(
            t("No transfer has been scheduled yet. Fill in TRANSFER_SCHEDULE "
              "(Transfer_Number, Start_Date, Weeks, Status), or set "
              "TRANSFER_START_DATE in AGENT_CONFIG.")
        )
        return

    start = current["start"]
    weeks = current["weeks"]
    end = start + timedelta(weeks=weeks) - timedelta(days=1)
    elapsed_days = (_TODAY - start).days
    week_no = max(1, min(weeks, elapsed_days // 7 + 1))
    days_left = (end - _TODAY).days

    if not rows and fallback_start:
        st.caption(
            t("TRANSFER_SCHEDULE is empty, so this uses TRANSFER_START_DATE "
              "from AGENT_CONFIG and assumes a {weeks}-week cycle.",
              weeks=fmt_int(weeks))
        )

    render_section_label(
        t("Transfer {number}", number=current["number"]) if current["number"]
        else t("Current transfer")
    )

    render_kpi_row([
        {"label": t("Week"), "value": week_no, "goal": weeks},
        {"label": t("Days elapsed"), "value": max(0, elapsed_days)},
        {"label": t("Days remaining"), "value": max(0, days_left)},
    ])

    st.caption(
        t("{start} to {end} · {weeks} weeks{status}",
          start=fmt_date(start), end=fmt_date(end), weeks=fmt_int(weeks),
          status=f" · {current['status']}" if current["status"] else "")
    )

    if days_left < 0:
        st.warning(
            t("This transfer ended on {end} and no later one is scheduled. "
              "Add the next row to TRANSFER_SCHEDULE so the transfer-to-date "
              "figures below start counting from the right day.",
              end=fmt_date(end))
        )

    # ── Schedule ─────────────────────────────────────────────────────────────
    if rows:
        with st.expander(t("Full transfer schedule ({count})",
                           count=fmt_int(len(rows)))):
            render_table(pd.DataFrame([{
                t("Transfer"): r["number"] or NA,
                t("Starts"): fmt_date(r["start"]),
                t("Ends"): fmt_date(r["start"] + timedelta(weeks=r["weeks"])
                                    - timedelta(days=1)),
                t("Weeks"): fmt_int(r["weeks"]),
                t("Status"): r["status"] or NA,
                t("Current"): "●" if r is current else "",
            } for r in rows]))

    # ── Performance across the transfer ─────────────────────────────────────
    render_section_label(t("Area Performance This Transfer"))

    st.caption(
        t("Totals from the start of the transfer through today, as "
          "CCSM_Agent3 computes them into LIVE_SNAPSHOT. Non-numeric "
          "questions are left out — a running sum of a Sí/No or Todo/Algo "
          "answer means nothing.")
    )

    snap = get_live_snapshot()

    if snap.empty:
        st.info(
            t("LIVE_SNAPSHOT is empty. CCSM_Agent3 rebuilds it on each run "
              "from DAILY_LOG — check Agent Runs on the Mantenimiento page.")
        )
    else:
        all_zones_label = t("All zones")
        zones = sorted({z for z in snap.get("Zone", pd.Series(dtype=str)).astype(str)
                        if z and z != "nan"})
        zone = st.selectbox(t("Zone"), [all_zones_label] + zones, key="tf_zone")
        if zone != all_zones_label and "Zone" in snap.columns:
            snap = snap[snap["Zone"].astype(str) == zone]

        skip = non_numeric_metrics()
        metrics = [k for k in nightly_metrics()
                   if k not in skip and f"{k}_transfer" in snap.columns]

        if not metrics:
            st.info(
                t("LIVE_SNAPSHOT has no transfer-to-date columns yet. They "
                  "appear once the nightly agent has run against a "
                  "populated DAILY_LOG.")
            )
        else:
            default = metrics[:4]
            picked = st.multiselect(
                t("Metrics"), options=metrics, default=default,
                format_func=lambda k: METRIC_LABELS.get(k, k),
                key="tf_metrics",
            )
            if not picked:
                st.info(t("Pick at least one metric."))
            else:
                cols = ["Area"] + (["Zone"] if "Zone" in snap.columns else [])
                tbl = snap[cols + [f"{m}_transfer" for m in picked]].copy()
                for m in picked:
                    tbl[f"{m}_transfer"] = tbl[f"{m}_transfer"].map(fmt_int)
                tbl = tbl.rename(columns={
                    **{f"{m}_transfer": METRIC_LABELS.get(m, m) for m in picked},
                    "Area": t("Area"), "Zone": t("Zone"),
                })
                render_table(tbl)

    # ── Roster ───────────────────────────────────────────────────────────────
    render_section_label(t("Roster"))

    org = get_areas_df()
    if org.empty:
        st.info(t("MISSION_ORG has no active areas."))
        return

    by_zone = (org.groupby("Zone").size().reset_index(name="n")
               if "Zone" in org.columns else pd.DataFrame())
    if not by_zone.empty:
        render_kpi_row(
            [{"label": t("Areas"), "value": int(len(org))},
             {"label": t("Zones"), "value": int(len(by_zone))}]
            + ([{"label": t("Districts"),
                 "value": int(org["District"].nunique())}]
               if "District" in org.columns else [])
        )

    cols = [c for c in ("Area_Name", "Zone", "District", "Companion1_Name",
                         "Companion2_Name") if c in org.columns]
    roster = org[cols].rename(columns={
        "Area_Name": t("Area"), "Zone": t("Zone"), "District": t("District"),
        "Companion1_Name": t("Companion 1"), "Companion2_Name": t("Companion 2"),
    })
    with st.expander(t("Every area ({count})", count=fmt_int(len(roster)))):
        render_table(roster)


# ── Roster Update tab ────────────────────────────────────────────────────────

def _render_roster_tab() -> None:
    # Mission-leadership-only, same gate as 19_Editar_Envíos.py — this
    # section pulls a real IMOS login and can mutate live MISSION_ORG.
    if not is_leadership(user.get("email", "")):
        st.warning(t("Applying a transfer is available to mission leadership only."))
        return

    render_section_label(t("Apply a Transfer"))

    st.caption(
        t("Pull the current roster from IMOS, preview what would change in "
          "MISSION_ORG, then apply it. Each step needs a separate click — "
          "nothing here runs automatically.")
    )

    st.info(
        t("**Transfer day checklist**\n"
          "1. **Pull roster from IMOS** — wait for the success message.\n"
          "2. **Preview** — review New/Deactivating/Changed/Reactivating "
          "below; tick the override box only if the guard blocks Apply and "
          "the number of deactivations is genuinely correct for this "
          "transfer.\n"
          "3. **Apply** — updates MISSION_ORG.\n"
          "4. **Sync forms** — updates the nightly/weekly dropdowns; run "
          "this after Apply.")
    )

    import_rows = sc.read_values("TRANSFER_IMPORT")
    if len(import_rows) <= 1:
        st.info(
            t("TRANSFER_IMPORT is empty. Pull the roster first (below), or "
              "paste it into the TRANSFER_IMPORT tab by hand.")
        )
    else:
        st.caption(
            t("TRANSFER_IMPORT has {count} rows.",
              count=fmt_int(len(import_rows) - 1))
        )

    if st.button(t("0 · Pull roster from IMOS (cloud)"), key="tf_pull_btn"):
        try:
            run_cloud_job(
                job_type="transfer_pull",
                workflow_file="transfer-roster-pull.yml",
                dispatch_inputs={},
                running_label=t("Pulling the roster from IMOS..."),
            )
        except (CloudJobFailed, CloudJobTimeout):
            pass   # run_cloud_job already rendered the error/warning
        else:
            sc.read_values.clear()  # pull wrote directly to sheet; invalidate cache
            st.success(t("Roster pulled. Click Preview to see the diff."))

    if st.button(t("1 · Preview"), key="tf_preview_btn"):
        with st.spinner(t("Reading MISSION_ORG and TRANSFER_IMPORT...")):
            st.session_state["tf_preview"] = tas.preview()

    preview = st.session_state.get("tf_preview")
    if preview:
        guard, diff = preview["guard"], preview["diff"]
        st.caption(
            t("{roster} roster rows vs {org} MISSION_ORG rows.",
              roster=fmt_int(preview["roster_count"]), org=fmt_int(preview["org_count"]))
        )
        if not guard["ok"]:
            st.error(guard["msg"])
        for label, key in [(t("New areas"), "added"), (t("Deactivating"), "deactivated"),
                            (t("Changed"), "changed"), (t("Reactivating"), "reactivated")]:
            items = diff[key]
            if items:
                with st.expander(f"{label} ({fmt_int(len(items))})"):
                    for item in items:
                        st.write(f"- {item}")

        override = False
        if not guard["ok"]:
            override = st.checkbox(
                t("Override the deactivation guard (only if this many "
                  "deactivations is genuinely correct)"),
                key="tf_override",
            )

        if st.button(t("2 · Apply"), key="tf_apply_btn",
                     disabled=(not guard["ok"] and not override)):
            with st.spinner(t("Applying to MISSION_ORG...")):
                try:
                    summary = tas.apply(override=override)
                except tas.TransferBlocked as e:
                    st.error(str(e))
                else:
                    st.success(t("Applied."))
                    if summary.get("new_emails_needed"):
                        st.warning(
                            t("New areas need an email address added by "
                              "hand: {areas}",
                              areas=", ".join(summary["new_emails_needed"]))
                        )
                    st.session_state.pop("tf_preview", None)

    st.divider()

    if st.button(t("3 · Sync nightly + weekly form dropdowns"), key="tf_sync_btn"):
        with st.spinner(t("Syncing form dropdowns...")):
            try:
                result = form_sync("both")
            except FormSyncError as e:
                st.error(str(e))
            else:
                for label, key in [("Nightly", "nightly"), ("Weekly", "weekly")]:
                    r = result.get(key)
                    if r:
                        (st.success if r["status"] == "OK" else st.warning)(
                            f"{label}: {r['msg']}"
                        )

    st.divider()

    # ── Emergency update ─────────────────────────────────────────────────────
    render_section_label(t("4 · Emergency update (pull + apply)"))
    st.write(
        t("One click for a mid-cycle move: pulls the roster, then applies "
          "it immediately — skipping the review step above. Run **3 · Sync "
          "forms** separately afterward if the form dropdowns need updating.")
    )
    st.caption(
        t("Tip: run 1 · Preview above first if you want to review the diff "
          "before it's applied — this button applies right away, showing "
          "you what changed only after the fact.")
    )
    if st.button(t("4 · Run emergency update"), key="tf_emergency_btn"):
        status = st.empty()
        status.info(t("Step 1/2 — pulling roster..."))
        try:
            run_cloud_job(
                job_type="transfer_pull",
                workflow_file="transfer-roster-pull.yml",
                dispatch_inputs={},
                running_label=t("Step 1/2 — pulling roster..."),
            )
        except (CloudJobFailed, CloudJobTimeout) as e:
            status.error(t("Pull failed — stopped before apply.\n\n{error}",
                            error=str(e)))
        else:
            status.info(t("Step 2/2 — applying transfer..."))
            try:
                summary = tas.apply(override=False)
            except tas.TransferBlocked as e:
                status.error(
                    t("Apply blocked by the guard: {error}\n\nUse 1 · "
                      "Preview and 2 · Apply above to review and override.",
                      error=str(e))
                )
            except Exception as e:
                status.error(t("Emergency update failed after pull: {error}",
                                error=str(e)))
            else:
                status.success(t("Emergency update complete."))
                if summary.get("new_emails_needed"):
                    st.warning(
                        t("New areas need an email address added by hand: "
                          "{areas}", areas=", ".join(summary["new_emails_needed"]))
                    )
                st.session_state.pop("tf_preview", None)


# st.tabs() renders every tab's body on every single script run regardless of
# which one is visually active (see pages/02_Metas.py and
# pages/18_Mantenimiento.py for the same fix + full explanation). st.radio()
# + CSS reads as a tab row but only runs the selected section's render
# function per rerun.
_TRASLADOS_SECTIONS = ["Schedule", "Roster Update"]
st.markdown(
    "<style>"
    "div[class*='st-key-traslados_section_picker'] div[data-testid='stRadio'] > div{"
    "flex-direction:row!important;gap:0.4rem!important;border-bottom:1px solid rgba(255,255,255,0.1);"
    "padding-bottom:0!important;margin-bottom:1rem!important}"
    "div[class*='st-key-traslados_section_picker'] div[data-testid='stRadio'] label{"
    "background:transparent!important;border:none!important;border-radius:0!important;"
    "padding:0.5rem 0.2rem!important;margin-right:1.2rem!important;cursor:pointer!important}"
    "div[class*='st-key-traslados_section_picker'] div[data-testid='stRadio'] label > div:first-child{display:none!important}"
    "div[class*='st-key-traslados_section_picker'] div[data-testid='stRadio'] label div[data-testid='stMarkdownContainer'] p{"
    "font-size:0.95rem!important;font-weight:600!important;color:#9ca3af!important}"
    "div[class*='st-key-traslados_section_picker'] div[data-testid='stRadio'] label:has(input:checked){"
    "border-bottom:2px solid #a5b4fc!important}"
    "div[class*='st-key-traslados_section_picker'] div[data-testid='stRadio'] label:has(input:checked) "
    "div[data-testid='stMarkdownContainer'] p{color:#f4f4f8!important}"
    "</style>",
    unsafe_allow_html=True,
)
with st.container(key="traslados_section_picker"):
    _active_section = st.radio(
        t("Section"), _TRASLADOS_SECTIONS, key="traslados_active_section",
        horizontal=True, label_visibility="collapsed",
    )

if _active_section == "Schedule":
    _render_schedule_tab()
else:
    _render_roster_tab()
