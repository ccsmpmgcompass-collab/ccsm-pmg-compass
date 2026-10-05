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

Three sections, same st.radio()+CSS tab pattern as Provo's 12_Transfer_Flow.py
(and CCSM's own 02_Metas.py/18_Mantenimiento.py) — st.tabs() renders every
tab's body on every single script run regardless of which one is visually
active, so a real tab widget would run the leadership-gated section's sheet
reads even for a viewer who can't see the results:
  • Schedule — the read-only view (current transfer, performance, roster).
  • Roster Update — Pull/Preview/Apply/Sync, leadership-gated. A non-leader
    who selects this tab sees a warning instead of the tools, same as
    Provo's _is_mp_or_ap() fallback — not st.stop(), so the tab picker
    itself always finishes rendering.
  • Leadership — MISSION_LEADERSHIP, the President and the assistants under
    the addresses they sign in with (PLAN-2026-10-05-roster-access.md R4).
    Leadership-gated the same way.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.auth.auth import is_leadership, require_auth
from app.components.design_system import (
    render_kpi_row, render_page_header, render_section_label,
    render_section_tabs, render_table,
)
from app.config.flavor_loader import METRIC_LABELS, flavor
from app.config.metric_catalog import non_numeric_metrics, nightly_metrics
from app.db import sheets_client as sc
from app.db.queries import (
    LEADERSHIP_ROLES, LINEAGE_TYPES, add_area_lineage, get_area_lineage,
    get_areas_df, get_config_value, get_live_snapshot, get_mission_leadership,
    save_area_lineage, save_mission_leadership,
)
from app.db.sheets_client import read_tab
from app.i18n import t
from app.i18n.formats import NA, fmt_date, fmt_int, fmt_number
from app.components.cloud_job_ui import CloudJobFailed, CloudJobTimeout, run_cloud_job
from app.ingestion import transfer_apply_service as tas
from app.ingestion import transfer_engine as te
from app.integrations.transfer_bridge import FormSyncError, form_sync
from app.utils.area_helpers import mission_today
from app.utils.transfer_helpers import transfer_rows, transfer_window

# Page chrome (set_page_config / inject_global_css / render_sidebar) is
# owned by Home.py's st.navigation router since 2026-09-02 — the router and
# this page share one script run, so calling them here would render twice.
user = require_auth()

render_page_header(
    t("Transfers"),
    t("{mission} — the current transfer cycle",
      mission=get_config_value("MISSION_NAME", flavor.display_name)),
)

_TODAY = mission_today()   # mission-local, not the server's UTC date


# ── Schedule tab ─────────────────────────────────────────────────────────────

def _render_schedule_tab() -> None:
    # ── Which transfer are we in ────────────────────────────────────────────
    # This page used to carry its own copy of the schedule reader and the
    # "which one is current" rule. Two other places now ask the same question
    # — the Desgloses period picker and the Panel's compliance rankings — so
    # the logic lives in app/utils/transfer_helpers and this page reads it
    # like everyone else (audit item E2: never let a second copy exist).
    rows = transfer_rows()

    _win = transfer_window(0, _TODAY)
    current = None
    if _win is not None:
        current = {"number": _win["number"], "start": _win["start"],
                   "weeks": _win["weeks"], "status": _win["status"]}
    # transfer_window falls back to AGENT_CONFIG's TRANSFER_START_DATE on its
    # own; `source` is how it says which of the two answered.
    fallback_start = (_win or {}).get("source") == "config"

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

    if fallback_start:
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

    # AGENT_CONFIG's TRANSFER_START_DATE is what CCSM_Agent1A, Agent2 and
    # Agent3 measure their own transfer windows from — including the
    # LIVE_SNAPSHOT totals in the table further down THIS page. When it
    # disagrees with the schedule, the header above and the numbers below
    # describe different stretches of time and nothing on screen says so.
    _cfg_start = (get_config_value("TRANSFER_START_DATE", "") or "").strip()[:10]
    if _win and _win["source"] == "schedule" and _cfg_start:
        try:
            _cfg_date = date.fromisoformat(_cfg_start)
        except ValueError:
            _cfg_date = None
        if _cfg_date and _cfg_date != start:
            st.warning(
                t("TRANSFER_SCHEDULE says this transfer began {schedule}, but "
                  "AGENT_CONFIG's TRANSFER_START_DATE still says {config}. The "
                  "week count above uses the schedule; the totals below come "
                  "from CCSM_Agent3, which uses the config value — so the two "
                  "currently describe different windows. Update "
                  "TRANSFER_START_DATE to {schedule} to bring them back "
                  "together.", schedule=fmt_date(start), config=fmt_date(_cfg_date))
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

    # Companions 3 and 4 exist since 2026-10-05 (PLAN-2026-10-05 R2): La Marina
    # 1 and Los Huertos each have four missionaries in IMOS, and the two-column
    # tab dropped the last two of each. A column that is empty on every row is
    # left out, so a mission of pairs sees the table it always saw.
    cols = [c for c in ("Area_Name", "Zone", "District", "Companion1_Name",
                         "Companion2_Name", "Companion3_Name", "Companion4_Name")
            if c in org.columns and (not c.startswith(("Companion3", "Companion4"))
                                     or org[c].astype(str).str.strip().ne("").any())]
    roster = org[cols].rename(columns={
        "Area_Name": t("Area"), "Zone": t("Zone"), "District": t("District"),
        "Companion1_Name": t("Companion 1"), "Companion2_Name": t("Companion 2"),
        "Companion3_Name": t("Companion 3"), "Companion4_Name": t("Companion 4"),
    })
    with st.expander(t("Every area ({count})", count=fmt_int(len(roster)))):
        render_table(roster)


# ── Roster Update tab ────────────────────────────────────────────────────────

def _kind_label(kind: str) -> str:
    return {"rename": t("rename"), "split": t("split"),
            "merge": t("merge")}.get(kind, kind)


def _proposal_label(p: dict) -> str:
    why = (t("shares {names}", names=", ".join(p["Shared"])) if p.get("Shared")
           else t("similar name") if p.get("By_Name") else "")
    return t("{new} ← {old} · {kind}", new=p["New_Area"],
             old=" + ".join(p["Old_Areas"]), kind=_kind_label(p["Change_Type"])) \
        + (f" · {why}" if why else "")


def _render_lineage_proposals(proposals: list) -> None:
    """One checkbox per proposed link, ticked by default; Apply records the
    ticked ones (PLAN-2026-10-05 D6 — proposed, never written unreviewed)."""
    if not proposals:
        return
    render_section_label(
        t("Area lineage"),
        info=t("A new area that continues an area this transfer closes. A "
               "confirmed link lets the new area's goals start from its "
               "predecessor's numbers until it has two weeks of its own, and "
               "Desgloses shows where it came from. Untick any that are wrong; "
               "the Linaje editor below can fix them later."))
    for i, prop in enumerate(proposals):
        st.checkbox(_proposal_label(prop), value=True, key=f"tf_lin_{i}")


def _confirmed_lineage(proposals: list) -> list:
    return [prop for i, prop in enumerate(proposals or [])
            if st.session_state.get(f"tf_lin_{i}", True)]


def _render_lineage_editor() -> None:
    """AREA_LINEAGE by hand: every link, a way to remove one, and a form to add
    one — for the links Apply did not propose, the emergency path, and backfill."""
    with st.expander(t("Area lineage — every link")):
        lin = get_area_lineage()
        rows = ([] if lin.empty or "New_Area" not in lin.columns
                else lin.to_dict("records"))
        if rows:
            render_table(pd.DataFrame([{
                t("New area"): r.get("New_Area", ""),
                t("Came from"): str(r.get("Old_Areas", "")).replace(";", " + "),
                t("Kind"): _kind_label(str(r.get("Change_Type", "")).lower()),
                t("Transfer"): r.get("Transfer_Date", ""),
            } for r in rows]))
            labels = {i: f'{r.get("New_Area", "")} ← '
                         f'{str(r.get("Old_Areas", "")).replace(";", " + ")}'
                      for i, r in enumerate(rows)}
            drop = st.multiselect(t("Remove links"), list(labels),
                                  format_func=labels.get, key="lin_drop")
            if drop and st.button(t("Remove selected"), key="lin_drop_btn"):
                save_area_lineage([r for i, r in enumerate(rows) if i not in drop])
                st.success(t("Removed."))
                st.rerun()
        else:
            st.caption(t("No links recorded yet."))

        org = get_areas_df(active_only=False)
        if org.empty or "Area_Name" not in org.columns:
            return
        every = sorted(org["Area_Name"].dropna().astype(str).str.strip().unique())
        active = sorted(get_areas_df(active_only=True)["Area_Name"]
                        .dropna().astype(str).str.strip().unique())
        _win = transfer_window(0, _TODAY)
        with st.form("lineage_add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            new_area = c1.selectbox(t("New area"), active, key="lin_new")
            old_areas = c2.multiselect(t("Came from"), every, key="lin_old")
            c3, c4 = st.columns(2)
            kind = c3.selectbox(t("Kind"), list(LINEAGE_TYPES),
                                format_func=_kind_label, key="lin_kind")
            when = c4.date_input(t("Transfer it began"),
                                 value=(_win or {}).get("start") or _TODAY,
                                 key="lin_date")
            if st.form_submit_button(t("Add link")):
                if not old_areas or new_area in old_areas:
                    st.error(t("Pick the area(s) it came from — not the area itself."))
                else:
                    from datetime import datetime as _dt
                    add_area_lineage([{
                        "Applied_At": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Transfer_Date": when.isoformat(), "Change_Type": kind,
                        "Old_Areas": old_areas, "New_Area": new_area,
                        "Recorded_By": user.get("email", ""), "Notes": "manual"}])
                    st.success(t("Link added."))
                    st.rerun()


def _report_emails(summary: dict) -> None:
    """What Apply did with email addresses. A new area takes its mailbox from
    the roster now (PLAN-2026-10-05 R1); only an area IMOS has no address for
    still needs one typed in, and that is the line that has to be loud — an
    area with no address is never reminded and never counted as missing."""
    if summary.get("emails_filled"):
        st.info(t("Email filled in from the roster for: {areas}",
                  areas=", ".join(summary["emails_filled"])))
    if summary.get("new_emails_needed"):
        st.warning(t("No email address in the roster for: {areas}. Add one to "
                     "MISSION_ORG by hand, or these areas get no reminders.",
                     areas=", ".join(summary["new_emails_needed"])))
    if summary.get("email_mismatches"):
        st.warning(t("These areas kept an email that differs from the roster's: "
                     "{items}",
                     items="; ".join(summary["email_mismatches"])))


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

    # The pilot filter decides what Apply will touch, so it is stated BEFORE the
    # buttons rather than discovered afterwards in the diff. A mission with no
    # PILOT_ZONES set says so explicitly too — "whole mission" is a fact worth
    # reading before clicking Apply, not an absence of one.
    _zones = tas.pilot_zones()
    if _zones:
        st.caption(
            t("Scoped to {count} pilot zone(s): {zones}. Areas in every other "
              "zone are left exactly as they are — including the ones already "
              "inactive. Set AGENT_CONFIG's PILOT_ZONES to change this; clear "
              "it to go mission-wide.",
              count=fmt_int(len(_zones)), zones=", ".join(_zones))
        )
    else:
        st.caption(
            t("PILOT_ZONES is not set, so Apply covers the WHOLE mission — "
              "every area in the roster is activated.")
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
        # A configured zone matching no roster row is a spelling drift, and
        # every area in it would be deactivated. apply() refuses outright; the
        # preview has to say so before the user reaches for the override.
        if preview.get("unknown_zones"):
            st.error(
                t("PILOT_ZONES names zone(s) that appear nowhere in "
                  "TRANSFER_IMPORT: {zones}. Fix the spelling to match the "
                  "roster's own Zone column — applying now would deactivate "
                  "every area in them.",
                  zones=", ".join(preview["unknown_zones"]))
            )
        if not guard["ok"]:
            st.error(guard["msg"])
        if preview.get("assistants_moved"):
            st.warning(
                t("MISSION_LEADERSHIP lists {names} as assistant(s), but this "
                  "roster no longer places them in the assistants' area. If the "
                  "assistants changed this transfer, update the Leadership "
                  "section — the new assistant cannot sign in with his own "
                  "address until he is listed there.",
                  names=", ".join(preview["assistants_moved"]))
            )
        for label, key in [(t("New areas"), "added"), (t("Deactivating"), "deactivated"),
                            (t("Changed"), "changed"), (t("Reactivating"), "reactivated"),
                            (t("Email addresses"), "emails")]:
            items = diff.get(key) or []
            if items:
                with st.expander(f"{label} ({fmt_int(len(items))})"):
                    for item in items:
                        st.write(f"- {item}")
        _render_lineage_proposals(preview.get("lineage") or [])

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
                    summary = tas.apply(
                        override=override,
                        lineage=_confirmed_lineage(preview.get("lineage")),
                        applied_by=user.get("email", ""))
                except tas.TransferBlocked as e:
                    st.error(str(e))
                else:
                    st.success(t("Applied."))
                    _report_emails(summary)
                    if summary.get("lineage_recorded"):
                        st.info(t("Lineage recorded: {links}",
                                  links="; ".join(summary["lineage_recorded"])))
                    if summary.get("lineage_error"):
                        st.warning(t("The roster was applied, but the lineage "
                                     "could not be written ({error}). Add it in "
                                     "the Linaje editor below.",
                                     error=summary["lineage_error"]))
                    st.session_state.pop("tf_preview", None)

    _render_lineage_editor()

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
                _report_emails(summary)
                st.session_state.pop("tf_preview", None)


# ── Leadership tab ───────────────────────────────────────────────────────────

def _render_leadership_tab() -> None:
    """MISSION_LEADERSHIP, edited in place (PLAN-2026-10-05-roster-access.md).

    Plain inputs in a form rather than st.data_editor: the data editor's canvas
    cells render dark-on-dark in this theme (see 06_Puntajes.py's
    _render_weight_inputs). One row per person plus one empty row to add
    someone; untick Active rather than deleting, so the list keeps who held the
    calling. Clearing both name and email removes a row.
    """
    if not is_leadership(user.get("email", "")):
        st.warning(t("Editing the mission's leadership is available to mission "
                     "leadership only."))
        return

    render_section_label(
        t("Mission leadership"),
        info=t("This list decides who may sign in with a personal address, who "
               "opens the leadership pages (Traslados, Editar Envíos, "
               "Mantenimiento, Centro de Acción, Sugerencias), who sets goals on "
               "Metas, and who receives the Monday mission report and the "
               "mission section of the weekly letter. Zone, district and sister "
               "training leaders are not listed here: they lead from their "
               "area's mailbox, and MISSION_ORG already knows them."),
    )
    st.caption(t("The President and the assistants, each under the address he "
                 "signs in with. Update it on transfer day whenever an assistant "
                 "changes."))

    current = get_mission_leadership(active_only=False)
    moved = te.assistants_missing_from_ap_area(
        current.loc[(current["Role"] == "assistant") & (current["Active"] == "TRUE"),
                    "Name"].tolist(),
        get_areas_df(active_only=True).to_dict("records"))
    if moved:
        st.warning(t("{names}: listed as assistant(s) here, but MISSION_ORG no "
                     "longer places them in the assistants' area. Untick Active "
                     "for anyone released, and add the new assistant.",
                     names=", ".join(moved)))
    if current.empty:
        st.info(t("No one is listed yet. Until someone is, the app knows the "
                  "assistants only by their area's shared mailbox, and the "
                  "President receives no email from it."))

    role_label = {"president": t("President"), "assistant": t("Assistant")}
    records = current.to_dict("records") + [
        {"Name": "", "Email": "", "Role": "assistant", "Active": "TRUE", "Notes": ""}]
    with st.form("leadership_form"):
        edited = []
        for i, r in enumerate(records):
            vis = "visible" if i == 0 else "collapsed"
            c_name, c_mail, c_role, c_act, c_note = st.columns([3, 4, 2, 1.3, 3])
            name = c_name.text_input(t("Name"), r.get("Name", ""), key=f"ld_name_{i}",
                                     label_visibility=vis, placeholder=t("Name"))
            email = c_mail.text_input(t("Sign-in email"), r.get("Email", ""),
                                      key=f"ld_email_{i}", label_visibility=vis,
                                      placeholder=t("firstname.lastname@missionary.org"))
            role = c_role.selectbox(
                t("Role"), list(LEADERSHIP_ROLES),
                index=list(LEADERSHIP_ROLES).index(r.get("Role") or "assistant")
                if (r.get("Role") or "assistant") in LEADERSHIP_ROLES else 1,
                format_func=lambda k: role_label.get(k, k),
                key=f"ld_role_{i}", label_visibility=vis)
            active = c_act.checkbox(t("Active"), value=str(r.get("Active", "TRUE")).upper() == "TRUE",
                                    key=f"ld_active_{i}")
            notes = c_note.text_input(t("Notes"), r.get("Notes", ""), key=f"ld_notes_{i}",
                                      label_visibility=vis, placeholder=t("Notes"))
            edited.append({"Name": name, "Email": email, "Role": role,
                           "Active": active, "Notes": notes})
        submitted = st.form_submit_button(t("Save leadership"), type="primary")

    if submitted:
        try:
            save_mission_leadership(edited)
        except ValueError as e:
            st.error(t("Not saved: {problems}", problems=str(e)))
        else:
            st.success(t("Saved. Sign-in and the leadership pages follow this "
                         "list from the next page load."))
            for k in [k for k in st.session_state if str(k).startswith("ld_")]:
                del st.session_state[k]
            st.rerun()


# The app's one sub-navigation control (audit step 1.7). This was st.tabs(),
# which renders every tab's body on every script run regardless of which is
# visually active, then st.radio() repainted as a tab row by a block of CSS
# copy-pasted verbatim from views/02_Metas.py. render_section_tabs' docstring
# holds the full reasoning for all three forms; only the selected section's
# render function runs, as before.
_TRASLADOS_SECTIONS = {s: t(s) for s in ("Schedule", "Roster Update", "Leadership")}
_active_section = render_section_tabs(
    _TRASLADOS_SECTIONS, key="traslados_section_val", per_row=3)

if _active_section == "Schedule":
    _render_schedule_tab()
elif _active_section == "Leadership":
    _render_leadership_tab()
else:
    _render_roster_tab()
