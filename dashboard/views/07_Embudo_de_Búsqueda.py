import base64
from datetime import date

import streamlit as st
import pandas as pd

from app.auth.auth import require_auth
from app.components.charts import (
    bars_vs_goal, chart, ranked_list, share_bar, stage_bars,
)
from app.components.cloud_job_ui import CloudJobFailed, CloudJobTimeout, run_cloud_job
from app.components.design_system import (
    render_page_header, render_section_label,
    render_table, render_kpi_row,
)
from app.config.theme import MUTED, STATUS
from app.db.drive_blob import read_dataframe_blob, save_dataframe_blob
from app.db.queries import (
    get_baptisms_actual_for_range, get_tableau_detail, get_tableau_detail_file_id,
    get_tableau_ranking,
)
from app.db.sheets_client import read_tab, save_dataframe
from app.ingestion.tableau_detail_transform import clean_detail
from app.ingestion.tableau_summary_parser import baptisms_rows, parse_summary_pdf
from app.ingestion.transfer_apply_service import pilot_zones
from app.ingestion.tableau_upload import (
    describe_replacement, is_provisional, merge_baptism_rows, read_tabular,
    summarize_months, upload_token,
)
from app.analytics.finding_funnel import (
    DEFAULT_PRESET, FUNNEL_STAGES, PRESET_LABELS, PRESETS, REFERRED_STAGE,
    bucket_counts, build_area_rankings, compute_funnel_stage_counts,
    data_date_bounds, export_age_days, export_is_stale, filter_by_range,
    preset_range, previous_window, window_buckets,
)
from app.i18n import t
from app.i18n.formats import (
    NA, fmt_date_range, fmt_day_month, fmt_int, fmt_month_abbr, fmt_percent,
)
from app.utils.area_helpers import mission_today

# Page chrome (set_page_config / inject_global_css / render_sidebar) is
# owned by Home.py's st.navigation router since 2026-09-02 — the router and
# this page share one script run, so calling them here would render twice.
user = require_auth()

render_page_header(
    t("Finding Funnel"),
    # No daily sync exists — the tab is loaded from a manual Tableau export.
    # (The scheduled job is Phase 3.4; until it runs, saying "auto-synced daily"
    # made a stale tab look fresh.) _source_caption still says "Auto-synced"
    # when the row was written by a job, so this stays honest either way.
    t("Mission finding & teaching pipeline — from the Tableau export"),
    icon="",
)

# What a cloud sync just did, shown once at the top rather than down in the
# upload expander: the button's own rerun collapses that expander, so a message
# left there would be written to a closed box.
_sync_note = st.session_state.pop("_tableau_sync_note", "")
if _sync_note:
    st.success(t("Synced from Tableau · {note}", note=_sync_note))


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _col(df: pd.DataFrame, *needles: str):
    """Resolve a column by name. An exact match (case-insensitive) wins; else the
    SHORTEST column whose lowercased name contains all needles. Shortest-match
    avoids Tableau's giant '..._and_5_more_(combined)' mashup column, which
    contains many of the same substrings as the real, short columns."""
    lowered = {str(c).lower(): c for c in df.columns}
    for n in needles:
        if n in lowered:
            return lowered[n]
    matches = [c for c in df.columns
               if all(n in str(c).lower() for n in needles)
               and "(combined)" not in str(c).lower()]
    return min(matches, key=lambda c: len(str(c))) if matches else None


def _date(df: pd.DataFrame, name: str) -> pd.Series:
    """Parse a detail date/datetime column to pandas datetime (NaT where blank)."""
    c = _col(df, name)
    if c is None:
        return pd.Series([pd.NaT] * len(df), index=df.index)
    return pd.to_datetime(df[c], errors="coerce", format="mixed")


def _disp_int(v) -> str:
    """`1.234` in Spanish, `1,234` in English. Was f"{int(round(v)):,}", which
    hardcoded the anglo separator regardless of interface language."""
    return fmt_int(v) if v else NA


def _disp_pct(v) -> str:
    return fmt_percent(v) if v else NA


def _fmt_dur(hours: float) -> str:
    if hours is None or pd.isna(hours):
        return "—"
    return f"{hours:.0f}h" if hours < 48 else f"{hours / 24:.1f}d"


def _process_upload(uploaded, tab_name: str) -> tuple:
    """Read a Ranking export and persist it. Detail goes through
    _process_detail_upload instead — it needs cleaning and a replace guard."""
    try:
        df = read_tabular(uploaded, getattr(uploaded, "name", ""))
        save_dataframe(tab_name, df, uploaded_by=user.get("email", ""))
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def _already_handled(slot: str, uploaded) -> bool:
    """True when this exact file was already processed on an earlier rerun.

    Streamlit keeps an uploaded file in session_state for the life of the
    session, and this page acted on whatever was sitting there — so changing
    the date preset re-parsed and re-wrote the export. For Detail that is nine
    Sheets API calls per click.
    """
    token = upload_token(uploaded)
    if st.session_state.get(f"_tok_{slot}") == token:
        return True
    st.session_state[f"_tok_{slot}"] = token
    return False


def _save_detail(df: pd.DataFrame) -> None:
    """Persist the cleaned Detail export.

    Drive blob when TABLEAU_DETAIL_FILE_ID is configured in AGENT_CONFIG,
    otherwise the sheet tab. Same choice get_tableau_detail() makes on the way
    back in, so the two can never disagree about where the data lives.
    """
    who = user.get("email", "")
    file_id = get_tableau_detail_file_id()
    if file_id:
        out = save_dataframe_blob(file_id, df, uploaded_by=who)
        if out["ok"]:
            st.caption(t("Saved to Drive · {mb:.2f} MB gzipped",
                         mb=out["bytes"] / 1e6))
        return
    save_dataframe("TABLEAU_DETAIL", df, uploaded_by=who)


def _cloud_sync_control() -> None:
    """The nightly Tableau job, on demand.

    Same workflow, same command and same window rules as the 09:00 UTC cron —
    the button exists for the day somebody needs this morning's figure before
    tonight, not as a second way of doing it. Dispatch, poll and error display
    are `cloud_job_ui`'s, shared with the Traslados roster pull.

    The caches are cleared and the page rerun on success: read_tab and the
    Drive blob both hold five minutes, so without this the page would sit there
    showing the very numbers the job just replaced.
    """
    st.caption(t("A scheduled job re-pulls this month and the one before it "
                 "from Tableau every night, and refreshes the Detail export. "
                 "Run it now if you need today's figures before tonight."))
    if st.button(t("Sync from Tableau now"), key="ff_tableau_sync"):
        try:
            job = run_cloud_job(
                job_type="tableau_finding",
                workflow_file="tableau-reports.yml",
                dispatch_inputs={},
                running_label=t("Pulling the finding exports from Tableau..."),
                timeout_s=1800,
            )
        except (CloudJobFailed, CloudJobTimeout):
            return   # run_cloud_job already rendered the error/warning
        read_tab.clear()
        read_dataframe_blob.clear()
        st.session_state["_tableau_sync_note"] = job.get("result_summary", "")
        st.rerun()


def _upload_controls() -> None:
    """The cloud sync, then the three uploaders and the note above them, with no
    container of their own — Streamlit forbids an expander inside an expander,
    and on the normal path these sit inside "Datos y carga" (E6)."""
    _cloud_sync_control()
    st.divider()
    st.caption(t("Export the Mission Finding Summary view from Tableau and drop the "
                 "files here. The Detail export REPLACES the stored data, so export "
                 "the full view, not a recent slice. Summary PDFs merge by month — "
                 "upload as many as you like at once."))
    c1, c2, c3 = st.columns(3)
    with c1:
        # .xlsx first: that is what the real export is. This uploader was
        # pd.read_csv only, so the actual file could never be loaded.
        st.file_uploader(t("Detail export (.xlsx or .csv)"),
                         type=["xlsx", "xlsm", "xls", "csv"], key="detail")
    with c2:
        st.file_uploader(t("Ranking export (.xlsx or .csv)"),
                         type=["xlsx", "xlsm", "xls", "csv"], key="ranking")
    with c3:
        st.file_uploader(t("Summary PDFs (one per month)"), type=["pdf"],
                         key="summary", accept_multiple_files=True)


def _render_uploaders(expanded: bool = False) -> None:
    """The manual upload controls in an expander of their own.

    A function, and not inline at the foot of the page, because the no-data
    branch `st.stop()`s — so the page told you to upload the export "in Manual
    upload below" and then rendered nothing below. The funnel could not be
    bootstrapped through the UI at all: no data meant no uploader, and no
    uploader meant no data. It is rendered in that branch too, opened.
    """
    with st.expander(t("Manual upload / re-sync"), expanded=expanded):
        _upload_controls()


def _source_caption(by: str, at: str) -> str:
    if by.startswith("auto:"):
        return t("Auto-synced · {source} · {at}",
                 source=by.split(":", 1)[1].replace("_", " "), at=at)
    if by:
        return t("Uploaded by {by} · {at}", by=by, at=at)
    return ""


def _bucket_label(day: date, granularity: str) -> str:
    """A trend bucket's x-axis label: `ago 26` for a month, `5 de jul` for a
    day or a seven-day block (the block's first day)."""
    if granularity == "month":
        return f"{fmt_month_abbr(day.month)} {day.year % 100:02d}"
    return fmt_day_month(day)


def _fmt_range(a: date, b: date) -> str:
    """'5 de ago – 11 de ago de 2026' in Spanish, 'Aug 5 – Aug 11, 2026' in English.

    strftime('%b') emits English month abbreviations whatever the interface
    language is set to — it follows the process locale, not ours — so this range
    read "Jun 15 – Jun 18" on an otherwise fully Spanish page.
    """
    if a.year == b.year:
        return fmt_date_range(a, b)
    return f"{fmt_day_month(a, with_year=True)} – {fmt_day_month(b, with_year=True)}"


# ══════════════════════════════════════════════════════════════════════════════
# LOAD DATA  (uploaded this session → else persisted / auto-synced)
# ══════════════════════════════════════════════════════════════════════════════

# Uploaders live at the bottom of the page inside an expander; read any pending
# upload from session_state set on the previous run.
detail_file  = st.session_state.get("detail")
ranking_file = st.session_state.get("ranking")
summary_file = st.session_state.get("summary")

if ranking_file is not None and not _already_handled("ranking", ranking_file):
    rank_df, err = _process_upload(ranking_file, "TABLEAU_RANKING")
    if err:
        st.error(t("Could not read the Ranking export: {err}", err=err))
        rank_df = pd.DataFrame()
    st.session_state["_df_ranking"] = rank_df
    rank_by, rank_at = user.get("email", ""), "just now"
elif ranking_file is not None:
    rank_df = st.session_state.get("_df_ranking", pd.DataFrame())
    rank_by, rank_at = user.get("email", ""), "just now"
else:
    rank_df, rank_by, rank_at = get_tableau_ranking()

# ── Detail: read → clean → guard → save ───────────────────────────────────────
# The clean step is not optional. It is what drops the investigators' names and
# person ids (the privacy decision recorded in tableau_detail_transform), drops
# Tableau's 2,705 artifact rows — which otherwise inflate "Found" and rank as
# an "Unknown" area at the top of the mission — and prunes 24 columns to the 14
# the app reads, taking the write from 2.2M cells to 1.26M.
det_by, det_at = "", ""
if detail_file is not None:
    if not _already_handled("detail", detail_file):
        try:
            raw = read_tabular(detail_file, getattr(detail_file, "name", ""))
            clean, stats = clean_detail(raw)
            stored, _, _ = get_tableau_detail()
            plan = describe_replacement(stored, clean)
            st.session_state["_df_detail"] = clean
            st.session_state["_detail_stats"] = stats
            st.session_state["_detail_plan"] = plan
            # A Detail upload REPLACES the tab — it cannot merge, because the
            # only stable per-person key is the person_id we deliberately drop.
            # So a narrower export silently destroys history; hold it for
            # confirmation instead of writing it.
            st.session_state["_detail_saved"] = not plan["narrower"]
            if not plan["narrower"]:
                _save_detail(clean)
        except Exception as e:
            st.error(t("Could not read the Detail export: {err}", err=e))
            st.session_state["_df_detail"] = pd.DataFrame()
            st.session_state["_detail_stats"] = None
            st.session_state["_detail_plan"] = None
            st.session_state["_detail_saved"] = True

    det_df = st.session_state.get("_df_detail", pd.DataFrame())
    det_by, det_at = user.get("email", ""), "just now"

    _plan = st.session_state.get("_detail_plan")
    if _plan and _plan["narrower"] and not st.session_state.get("_detail_saved"):
        _o1, _o2 = _plan["existing_span"]
        _n1, _n2 = _plan["incoming_span"]
        st.warning(t(
            "**Not saved.** This export covers {new_from} → {new_to} "
            "({new_rows} people), but the stored data covers {old_from} → "
            "{old_to} ({old_rows} people). Saving would replace the history, "
            "not add to it — a Detail export cannot be merged. Re-export the "
            "full view, or replace anyway if that is what you intend.",
            new_from=_n1, new_to=_n2, new_rows=fmt_int(_plan["incoming_rows"]),
            old_from=_o1, old_to=_o2, old_rows=fmt_int(_plan["existing_rows"])))
        if st.button(t("Replace anyway"), key="ff_force_detail"):
            _save_detail(det_df)
            st.session_state["_detail_saved"] = True
            st.rerun()
    elif st.session_state.get("_detail_stats"):
        _s = st.session_state["_detail_stats"]
        st.success(t(
            "Detail export saved · {rows} people ({dropped} Tableau artifact "
            "rows dropped) · names and person ids removed",
            rows=fmt_int(_s.get("rows_out", 0)),
            dropped=fmt_int(_s.get("artifact_rows_dropped", 0))))
        if _s.get("dropped_unknown"):
            st.info(t("New columns in this export, not stored: {cols}",
                      cols=", ".join(_s["dropped_unknown"])))
else:
    det_df, det_by, det_at = get_tableau_detail()

# ── Summary PDFs → TABLEAU_BAPTISMS ───────────────────────────────────────────
# Merged by month, never replaced: the mission's history is 31 monthly PDFs and
# uploading next month's must not wipe the previous thirty. This is what makes
# get_baptisms_actual() return a real number, so Metas stops falling back to
# the weekly-form gate proxy that under-counts roughly two to one.
if summary_file:
    _files = summary_file if isinstance(summary_file, list) else [summary_file]
    _tok = "|".join(upload_token(f) for f in _files)
    if st.session_state.get("_tok_summary") != _tok:
        st.session_state["_tok_summary"] = _tok
        parsed, failed = [], []
        for f in _files:
            try:
                f.seek(0)
                parsed.append(parse_summary_pdf(f))
            except Exception as e:
                failed.append(f"{getattr(f, 'name', '?')}: {e}")
        if parsed:
            try:
                merged = merge_baptism_rows(read_tab("TABLEAU_BAPTISMS"),
                                            baptisms_rows(parsed))
                save_dataframe("TABLEAU_BAPTISMS", merged,
                               uploaded_by=user.get("email", ""))
                st.success(t("{n} summary PDFs parsed · TABLEAU_BAPTISMS now "
                             "holds {total} months · {span}",
                             n=len(parsed), total=len(merged),
                             span=summarize_months(merged["month"])))
                # A month-to-date export is stored, but it must never be
                # mistaken for the finished month — the strict readers hide it
                # and the reader deserves to know why the figure they just
                # uploaded is not going to appear on the Panel's annual line.
                for _s in parsed:
                    if is_provisional(_s.month, _s.end_date):
                        st.info(t("{month} is a month-to-date capture ({start} "
                                  "to {end}), stored as partial. It is left out "
                                  "of certified monthly figures until the "
                                  "finished month is exported.",
                                  month=_s.month, start=_s.start_date,
                                  end=_s.end_date))
            except Exception as e:
                st.error(t("Could not save baptism counts: {err}", err=e))
        for msg in failed:
            st.error(t("Could not parse {msg}", msg=msg))

if rank_df.empty and det_df.empty:
    st.info(t("No finding data yet. Export the Mission Finding Summary view from "
              "Tableau and upload it in **Manual upload** below."))
    # Render the uploaders BEFORE stopping, or "below" is a lie and the page
    # can never be bootstrapped from empty.
    _render_uploaders(expanded=True)
    st.stop()

sync_note = _source_caption(rank_by, rank_at) or _source_caption(det_by, det_at)

# ── E1: freshness first — what this export is, and how old ─────────────────────
# The page is a Tableau export somebody pulls by hand, and every window below
# is measured from the export's own last date, not from today. Until this strip
# existed the page said neither: on 2026-09-19 it opened on "last 30 days" and
# drew 5 Jul – 3 Aug, six weeks stale, with nothing on screen to say so
# (audit E1). The span, who loaded it and its age lead the page now, and the
# strip turns amber past a week.
_lo, _hi = data_date_bounds(det_df)
_today = mission_today()
_age_days = export_age_days(_hi, _today)
_stale = export_is_stale(_hi, _today)
_fresh = t("Tableau export · data from {first} to {last}",
           first=fmt_day_month(_lo, with_year=True),
           last=fmt_day_month(_hi, with_year=True))
if sync_note:
    _fresh += " · " + sync_note
_fresh += " · " + (t("updated today") if _age_days == 0
                   else t("1 day old") if _age_days == 1
                   else t("{n} days old", n=_age_days))
st.markdown(
    f'<div style="display:flex;align-items:flex-start;gap:0.5rem;'
    f'background:{"rgba(242,177,52,0.12)" if _stale else "rgba(255,255,255,0.035)"};'
    f'border:1px solid {"rgba(242,177,52,0.40)" if _stale else "rgba(255,255,255,0.10)"};'
    f'border-radius:8px;padding:0.5rem 0.8rem;margin:0 0 0.75rem 0;'
    f'font-size:0.8rem;line-height:1.45;'
    f'color:{STATUS["warn"] if _stale else MUTED};">'
    f'<span style="flex:none;">{"&#9888;" if _stale else "&#128197;"}</span>'
    f'<span>{_fresh}</span></div>',
    unsafe_allow_html=True,
)

# ── The window — every preset counts back from the export's last date ─────────
# Translated label -> English preset key. The key is what preset_range() looks
# up in PRESETS, so it must stay English; only the label is translated. The
# labels say "of the export" because that is what the window is anchored on:
# a reader who takes "last 30 days" to run up to today is wrong by exactly the
# staleness named above.
_opt_labels = {t(PRESET_LABELS[k]): k for k in list(PRESETS.keys()) + ["Custom"]}
# Open on DEFAULT_PRESET rather than whatever sits first. The page used to open
# on "All", which was a harmless ~3-week window only because DATA_FLOOR was
# wrongly clamping the data to May 2026; with the real 2.6 years visible, "All"
# as an opening view is 89,800 people and ~950 daily bars.
_keys = list(_opt_labels.values())
_default_idx = _keys.index(DEFAULT_PRESET) if DEFAULT_PRESET in _keys else 0
# The row is full width. It used to be the left three fifths of a 3:2 split
# reserved for the custom date boxes, which at these longer labels wrapped the
# five presets onto three lines at 1400px; the boxes now take their own row and
# only when Custom is chosen, which is the only time they are live anyway.
_preset = _opt_labels[st.radio(t("Date range"), list(_opt_labels),
                               index=_default_idx, horizontal=True,
                               key="ff_preset", label_visibility="collapsed")]
if _preset == "Custom":
    _d1, _d2, _spacer = st.columns([1, 1, 3])
    with _d1:
        sel_start = st.date_input(t("Start"), value=_lo, min_value=_lo,
                                  max_value=_hi, key="ff_start")
    with _d2:
        sel_end = st.date_input(t("End"), value=_hi, min_value=_lo,
                                max_value=_hi, key="ff_end")
    if sel_start > sel_end:
        sel_start, sel_end = sel_end, sel_start
else:
    sel_start, sel_end = preset_range(_preset, _lo, _hi)

# The unfiltered frame stays reachable: E5's trend draws the equal-length
# window BEFORE this one as ghost bars, and that cannot be recovered from a
# frame already cut to the selection.
det_all = det_df
det_df = filter_by_range(det_df, sel_start, sel_end)
if det_df.empty:
    st.info(t("No findings in the selected date range — widen the range to see data."))

#: The window every section below reports on, for a section label's right-hand
#: line. It replaces the indigo chip that used to sit under the presets
#: restating what the selected pill already said — and whose day count was
#: the one string on this page that never went through t().
_window_days = (sel_end - sel_start).days + 1 if sel_start and sel_end else 0
_window_note = (f"{_fmt_range(sel_start, sel_end)} · "
                + t("{n} days", n=_window_days)) if _window_days else ""


# ══════════════════════════════════════════════════════════════════════════════
# DERIVE — pull every usable metric out of the two exports
# ══════════════════════════════════════════════════════════════════════════════

# ── Mission-wide reference numbers — now sourced from filtered Detail so they
#    honor the active date window (Ranking export has no dates to slice by) ────
#    Referred is NOT a funnel stage — see REFERRED_STAGE in finding_funnel.py.
referred = int(_date(det_df, REFERRED_STAGE[1]).notna().sum()) \
    if not det_df.empty else 0

# ── Detail event milestones — the true finding-to-progress funnel ─────────────
# The stage list lives in app/analytics/finding_funnel.py and is imported, not
# restated: this page kept its own 6-stage copy while the per-area table below
# used a 7-stage one, so the chart silently omitted every baptism.
#
# stage_counts is keyed by the ENGLISH label. It used to be keyed by t(label)
# and then read back with English literals four lines later — on the Spanish
# interface (the mission default) every one of those lookups missed, so the
# KPI row and the whole Contact Performance section reported 0.
stage_counts = compute_funnel_stage_counts(det_df)

# ── Official baptisms — from Tableau's own certified monthly PDFs, NOT from
# Detail's confirmation_date (the funnel's "Baptized" stage below). Detail only
# has a row for people whose finding record made it into the app, so it
# undercounts anyone baptized before that tracking caught up — found live:
# 301 tracked vs. 403 certified over one full year. Available for a whole
# number of calendar months, and — since 2026-09-19 — for one other window:
# the exact one a stored export was itself run for, which is the certified
# figure for precisely those days rather than a partial sum of anything. Every
# other window still shows a dash; see get_baptisms_actual_for_range.
official_baptisms = get_baptisms_actual_for_range(sel_start, sel_end)

found = len(det_df)
attempted = stage_counts.get("Contact Attempted", 0)
contacted = stage_counts.get("Successfully Contacted", 0)
teaching  = stage_counts.get("Being Taught", 0)
lessons   = int(_date(det_df, "first_lesson_date").notna().sum()) if not det_df.empty else 0
bap_dates = stage_counts.get("Baptism Date Set", 0)

# ── Speed-to-contact (hours from finding event to first attempt / success) ────
median_attempt = within24 = within48 = None
median_success = None
if not det_df.empty:
    ev  = _date(det_df, "event_date_selected")
    att = _date(det_df, "first_contact_attempt_event_date")
    suc = _date(det_df, "first_successful_contact_attempt_event_date")
    h_att = ((att - ev).dt.total_seconds() / 3600)
    h_att = h_att[h_att.notna() & (h_att >= 0)]
    h_suc = ((suc - ev).dt.total_seconds() / 3600)
    h_suc = h_suc[h_suc.notna() & (h_suc >= 0)]
    if len(h_att):
        median_attempt = float(h_att.median())
        within24 = float((h_att <= 24).mean() * 100)
        within48 = float((h_att <= 48).mean() * 100)
    if len(h_suc):
        median_success = float(h_suc.median())


#: Tableau's finding categories, as the export writes them. The data keeps the
#: English value (it is the sheet's own vocabulary and the filter key); only
#: what the reader sees is translated. Probed live 2026-09-18: Missionary,
#: Media, Member, Visitors Centers and Events.
_FINDING_CATEGORY_LABELS = {
    "Missionary": "Missionary",
    "Media": "Media",
    "Member": "Member",
    "Visitors Centers and Events": "Visitors Centers and Events",
    "Unknown": "Unknown",
}


def _finding_category_label(value: str) -> str:
    key = _FINDING_CATEGORY_LABELS.get(str(value))
    return t(key) if key else str(value)


def _unknown_label(value: str) -> str:
    """Free-text sources and zone names are shown as written; only the
    placeholder this page itself inserts is translated."""
    return t("Unknown") if str(value) == "Unknown" else str(value)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — THE SCOREBOARD  (E2)
# ══════════════════════════════════════════════════════════════════════════════

# Six cards under one heading whose right-hand line names the window and whose
# ⓘ carries the one rule a reader needs: why Official Baptisms is sometimes a
# dash. It used to be a caption under the card, phrased as an instruction
# ("pick a range of full calendar months") rather than as the reason; the
# explanation belongs to the section, the card keeps a four-word note (plan A4).
render_section_label(
    t("Finding snapshot"), emphasis=True, right=_window_note,
    info=t("Every number here counts people whose finding event falls inside "
           "the selected window, from the Detail export. Official Baptisms is "
           "the exception: it comes from Tableau's own certified summary PDFs, "
           "so it answers for whole calendar months, or for the exact window "
           "one of those exports was run for — any other window shows a dash "
           "rather than a wrong total."),
)
render_kpi_row([
    {"label": t("People Found"),      "value": int(found)},
    {"label": t("Contact Attempted"), "value": int(attempted)},
    {"label": t("Contacted"),         "value": int(contacted)},
    {"label": t("Being Taught"),      "value": int(teaching)},
    {"label": t("New Referrals"),     "value": int(referred)},
    {"label": t("Official Baptisms"),
     "value": int(official_baptisms) if official_baptisms is not None else "—",
     "note": (t("Certified — Tableau summary PDF") if official_baptisms is not None
              else t("Whole months, or an exact export window"))},
])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — THE PIPELINE, AND WHAT FOUND THESE PEOPLE  (E3)
# ══════════════════════════════════════════════════════════════════════════════

# Stage bars, not a Plotly funnel. A funnel's shrinking trapezoids encode
# nothing that a bar and a percentage do not, its stage labels were clipped,
# and at 375px it was unreadable. The step conversions are written between the
# rows, and the step that loses the most people is named rather than left for
# the reader to find (live: 2.545 being taught → 167 at sacrament, 7%).
_pipeline_info = t("Each stage = people found in range who reached at least that "
                   "far. A milestone that was never logged is inherited from a "
                   "later one, so the funnel never widens.")
if (official_baptisms is not None
        and official_baptisms != stage_counts.get("Baptized", 0)):
    # This was a six-line caption under the chart. It is the same sentence,
    # one tap away, under the section it belongs to (plan A4).
    _pipeline_info += " " + t(
        "⚠️ Baptized here only counts people with a tracked finding "
        "record — {tracked} here vs. {official} certified by Tableau's "
        "own monthly summary for this period. The gap is people "
        "baptized before their finding record existed in the app. "
        "Official Baptisms above is the number that matters for "
        "reporting.",
        tracked=fmt_int(stage_counts.get("Baptized", 0)),
        official=fmt_int(official_baptisms))

render_section_label(t("Finding Pipeline"), emphasis=True, info=_pipeline_info,
                     right=t("{n} people found", n=fmt_int(found)) if found else "")
if stage_counts:
    st.markdown(
        stage_bars([(t(label), stage_counts[label]) for label, _ in FUNNEL_STAGES],
                   highlight_worst=True),
        unsafe_allow_html=True,
    )
else:
    st.caption(t("Detail records needed to build the pipeline funnel."))

# The mix is one 100% stacked bar. It was a donut whose labels sat outside the
# ring — at 375px that left about 120px of ring — and whose four arcs the
# reader had to compare by eye.
_cat_col = _col(det_df, "finding_category") if not det_df.empty else None
if _cat_col is not None:
    _cats = (det_df[_cat_col].astype(str).str.strip()
             .replace({"": "Unknown", "nan": "Unknown"}).value_counts())
    render_section_label(t("Finding Mix"))
    st.markdown(
        share_bar([(_finding_category_label(c), int(v))
                   for c, v in _cats.items()]),
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CONTACT PERFORMANCE  (speed + conversion)
# ══════════════════════════════════════════════════════════════════════════════

if not det_df.empty:
    render_section_label(t("Contact Performance"))
    contact_rate = (attempted / found * 100) if found else 0
    success_rate = (contacted / found * 100) if found else 0
    render_kpi_row([
        {"label": t("Contact to Friend"), "value": f"{contact_rate:.0f}%"},
        {"label": t("Success Rate"),      "value": f"{success_rate:.0f}%"},
        {"label": t("Median to Contact"), "value": _fmt_dur(median_attempt)},
        {"label": t("Within 24h"), "value": f"{within24:.0f}%" if within24 is not None else "—"},
        {"label": t("Within 48h"), "value": f"{within48:.0f}%" if within48 is not None else "—"},
    ])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SOURCES  +  ZONES  +  DAILY TREND
# ══════════════════════════════════════════════════════════════════════════════

if not det_df.empty:
    src_col  = _col(det_df, "finding_source")
    zone_col = _col(det_df, "latest_zone")

    # Both were horizontal Plotly bar charts with a 10px left margin, so every
    # category name was clipped to two letters — audit E2, the finding that
    # made a chart of source names unreadable. A ranked row writes the name in
    # HTML: it cannot be clipped by a margin, it carries the full name on
    # hover when the column is narrow, and it wraps instead of scrolling.
    _pilot = {z.casefold() for z in pilot_zones()}

    s1, s2 = st.columns(2)
    with s1:
        render_section_label(t("Top Finding Sources"),
                             right=t("top {n}", n=10))
        if src_col:
            src = (det_df[src_col].astype(str).str.strip()
                   .replace({"": "Unknown", "nan": "Unknown"})
                   .value_counts().head(10))
            st.markdown(ranked_list([
                {"name": _unknown_label(k), "value": int(v),
                 "sub": fmt_percent(v / found * 100) if found else ""}
                for k, v in src.items()
            ]), unsafe_allow_html=True)

    with s2:
        render_section_label(t("Findings by Zone"),
                             right=t("{n} zones", n=fmt_int(
                                 0 if zone_col is None
                                 else det_df[zone_col].astype(str).str.strip()
                                 .replace({"": "Unknown", "nan": "Unknown"}).nunique())))
        if zone_col:
            zn = (det_df[zone_col].astype(str).str.strip()
                  .replace({"": "Unknown", "nan": "Unknown"}).value_counts())
            st.markdown(ranked_list([
                {"name": _unknown_label(k), "value": int(v),
                 "sub": (t("Pilot zone")
                         if str(k).casefold() in _pilot else "")}
                for k, v in zn.items()
            ]), unsafe_allow_html=True)

    # ── E5: the trend, against the window before it ──────────────────────────
    # Buckets come from the WINDOW, not from the data's own span: day for a
    # short window, seven-day blocks counted back from its end, month once it
    # passes a year. The blocks are what let the previous equal-length window
    # ride behind as ghost bars — two 30-day windows bucket identically, so
    # bar for bar the comparison is exact (window_buckets' docstring has why
    # calendar weeks would not be).
    _tbuckets, _tgran = window_buckets(sel_start, sel_end)
    _tvalues = bucket_counts(det_df, _tbuckets)
    if _tbuckets:
        _pstart, _pend = previous_window(sel_start, sel_end)
        # Only when the export actually covers it. A window that runs off the
        # front of the data would draw a row of zeroes, which reads as "nobody
        # was found" rather than "nothing was exported".
        _twin = (bucket_counts(filter_by_range(det_all, _pstart, _pend),
                               window_buckets(_pstart, _pend)[0])
                 if _pstart >= _lo else None)
        _trend_info = t(
            "Each bar counts the people found in that stretch. Seven-day "
            "blocks are counted back from the end of the window, so the most "
            "recent block is always a whole week and only the oldest can be "
            "short.")
        if _twin is None:
            _trend_info += " " + t(
                "The export does not reach back far enough to draw the "
                "previous window behind it.")
        render_section_label(
            t("Findings per Month") if _tgran == "month"
            else t("Findings per Week") if _tgran == "week"
            else t("Findings per Day"),
            info=_trend_info,
            right=(t("vs. {range}", range=_fmt_range(_pstart, _pend))
                   if _twin is not None else ""),
        )
        chart(bars_vs_goal(
            [_bucket_label(a, _tgran) for a, _ in _tbuckets],
            _tvalues, None, twin=_twin,
            actual_label=t("This window"), twin_label=t("Previous window"),
        ), height=280)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — DATA AND UPLOAD  (E6)
# ══════════════════════════════════════════════════════════════════════════════

# Two tables, a raw dump, a PDF viewer and the upload controls used to be five
# expanders stacked under a "DATOS DETALLADOS" heading — a screen and a half
# of page spent saying "there is more down here". They are one expander now,
# with the four readings behind st.pills so only the one asked for is built.
# That is not only tidiness: the records table formats every row of the window
# one cell at a time, and the raw dump renders 200 rows of every column.
#
# The uploaders are NOT behind a pill. Streamlit drops a widget's session
# state the moment the widget stops being rendered, and this page reads
# st.session_state["detail"] / ["ranking"] / ["summary"] at the top of the
# script to decide whether a fresh export is in hand. A pill that un-rendered
# them would throw a just-uploaded file away as soon as the reader looked at
# something else, so they sit under the pills' output, always drawn.
with st.expander(t("Data and upload"), expanded=False):
    _DATA_VIEWS = {
        t("Area rankings"): "rankings",
        t("Finding records"): "records",
        t("Raw Tableau export"): "raw",
        t("Finding Summary PDF"): "pdf",
    }
    _view = _DATA_VIEWS.get(st.pills(
        t("Data and upload"), list(_DATA_VIEWS), key="ff_data_view",
        label_visibility="collapsed"))

    if _view == "rankings":
        ranks = build_area_rankings(det_df)
        if ranks.empty:
            st.caption(t("No finding records in the selected range to rank."))
        else:
            _pct_cols = {"Contact %", "Contacted %"}
            disp = pd.DataFrame()
            for label in ranks.columns:
                if label == "Area":
                    disp[label] = ranks[label]
                elif label in _pct_cols:
                    disp[label] = ranks[label].map(_disp_pct)
                else:
                    disp[label] = ranks[label].map(_disp_int)
            # Headers translated only for display; the loop above matched on the
            # English names build_area_rankings() produces, and the CSV below is
            # exported from `ranks`, so downloads keep their English columns.
            disp = disp.rename(columns={c: t(c) for c in disp.columns})
            st.caption(t("{n} areas with activity · sorted by people found "
                         "· reflects the selected date range", n=disp.shape[0]))
            st.caption(t("Baptized here is a lower bound — Tableau only certifies "
                         "mission/zone totals, not a per-area breakdown (see "
                         "Official Baptisms above)."))
            render_table(disp.reset_index(drop=True))
            st.download_button(t("Download Rankings CSV"),
                               data=ranks.to_csv(index=False).encode("utf-8"),
                               file_name="finding_rankings.csv", mime="text/csv")

    elif _view == "records":
        st.caption(t("Finding Records — {n} people",
                     n=0 if det_df.empty else len(det_df)))
        if det_df.empty:
            st.caption(t("No detail export loaded."))
        else:
            colmap = [
                ("Date",     _col(det_df, "event_date_selected")),
                ("Zone",     _col(det_df, "latest_zone")),
                ("District", _col(det_df, "latest_district")),
                ("Area",     _col(det_df, "latest_teaching_area")),
                ("Source",   _col(det_df, "finding_source")),
                ("Category", _col(det_df, "finding_category")),
                ("Name",     _col(det_df, "full_name")),
            ]
            recs = pd.DataFrame()
            for label, src in colmap:
                if src is not None:
                    recs[label] = det_df[src].astype(str).str.strip().replace({"nan": ""})

            # The "All" sentinel is translated for display and compared against
            # the same _all below. Every other option is a zone/category/source
            # value read from the sheet, which stays exactly as stored so the
            # equality filters keep matching.
            _all = t("All")
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                zsel = (st.selectbox(t("Zone"), [_all] + sorted(recs["Zone"].dropna().unique()),
                                     key="rec_zone") if "Zone" in recs.columns else _all)
            with fc2:
                csel = (st.selectbox(t("Category"), [_all] + sorted(recs["Category"].dropna().unique()),
                                     key="rec_cat") if "Category" in recs.columns else _all)
            with fc3:
                ssel = (st.selectbox(t("Source"), [_all] + sorted(recs["Source"].dropna().unique()),
                                     key="rec_src") if "Source" in recs.columns else _all)
            filt = recs.copy()
            if "Zone" in filt.columns and zsel != _all:
                filt = filt[filt["Zone"] == zsel]
            if "Category" in filt.columns and csel != _all:
                filt = filt[filt["Category"] == csel]
            if "Source" in filt.columns and ssel != _all:
                filt = filt[filt["Source"] == ssel]
            st.caption(t("{shown} of {total} records",
                         shown=filt.shape[0], total=recs.shape[0]))
            render_table(filt.head(250).rename(columns={c: t(c) for c in filt.columns})
                         .reset_index(drop=True))
            if filt.shape[0] > 250:
                st.caption(t("Showing first 250 — download for the full set."))
            st.download_button(t("Download Records CSV"),
                               data=det_df.to_csv(index=False).encode("utf-8"),
                               file_name="finding_records.csv", mime="text/csv")

    elif _view == "raw":
        if not rank_df.empty:
            st.markdown(t("**Ranking — raw**"))
            render_table(rank_df.head(200))
        if not det_df.empty:
            st.markdown(t("**Detail — raw**"))
            # Drop the giant '(combined)' mashup column from the on-screen raw view
            raw_det = det_df[[c for c in det_df.columns if "(combined)" not in str(c).lower()]]
            render_table(raw_det.head(200))
            if len(det_df) > 200:
                st.caption(t("Showing first 200 of {n} rows — download above for all.",
                             n=len(det_df)))

    elif _view == "pdf":
        _pdfs = ([] if not summary_file
                 else summary_file if isinstance(summary_file, list) else [summary_file])
        if not _pdfs:
            st.caption(t("Upload the Finding Summary PDF in Manual upload below to view it here."))
        else:
            _pdf = _pdfs[-1]
            if len(_pdfs) > 1:
                st.caption(t("{n} PDFs uploaded — previewing the last.", n=len(_pdfs)))
            _pdf.seek(0)
            pdf_bytes = _pdf.read()
            st.caption(t('{name} · {value:.1f} KB', name=_pdf.name, value=len(pdf_bytes) / 1024))
            st.download_button(t("Download Summary PDF"), data=pdf_bytes,
                               file_name=_pdf.name, mime="application/pdf")
            b64 = base64.b64encode(pdf_bytes).decode("utf-8")
            st.components.v1.html(
                f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800px" '
                f'type="application/pdf" sandbox="allow-same-origin"></iframe>', height=820)

    st.divider()
    st.markdown(t("**Manual upload / re-sync**"))
    _upload_controls()
