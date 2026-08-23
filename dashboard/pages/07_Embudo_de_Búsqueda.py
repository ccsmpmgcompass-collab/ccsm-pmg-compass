import base64
from datetime import date

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from app.auth.auth import require_auth
from app.components.design_system import (
    inject_global_css, render_page_header, render_sidebar, render_section_label,
    render_table, render_kpi_row, PALETTE,
)
from app.db.drive_blob import save_dataframe_blob
from app.db.queries import (
    get_tableau_detail, get_tableau_detail_file_id, get_tableau_ranking,
)
from app.db.sheets_client import read_tab, save_dataframe
from app.ingestion.tableau_detail_transform import clean_detail
from app.ingestion.tableau_summary_parser import baptisms_rows, parse_summary_pdf
from app.ingestion.tableau_upload import (
    describe_replacement, merge_baptism_rows, read_tabular, summarize_months,
    upload_token,
)
from app.analytics.finding_funnel import (
    DEFAULT_PRESET, FUNNEL_STAGES, PRESETS, REFERRED_STAGE, build_area_rankings,
    compute_funnel_stage_counts, data_date_bounds, filter_by_range, preset_range,
    trend_series,
)
from app.i18n import t
from app.i18n.formats import NA, fmt_date_range, fmt_day_month, fmt_int, fmt_percent

st.set_page_config(page_title="CCSM · Finding Funnel — PMG Compass", page_icon="", layout="wide")

user = require_auth()
inject_global_css()
render_sidebar(user)

render_page_header(
    t("Finding Funnel"),
    # No daily sync exists — the tab is loaded from a manual Tableau export.
    # (The scheduled job is Phase 3.4; until it runs, saying "auto-synced daily"
    # made a stale tab look fresh.) _source_caption still says "Auto-synced"
    # when the row was written by a job, so this stays honest either way.
    t("Mission finding & teaching pipeline — from the Tableau export"),
    icon="",
)


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


def _render_uploaders(expanded: bool = False) -> None:
    """The manual upload controls.

    A function, and not inline at the foot of the page, because the no-data
    branch `st.stop()`s — so the page told you to upload the export "in Manual
    upload below" and then rendered nothing below. The funnel could not be
    bootstrapped through the UI at all: no data meant no uploader, and no
    uploader meant no data. It is rendered in that branch too, opened.
    """
    with st.expander(t("Manual upload / re-sync"), expanded=expanded):
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


def _source_caption(by: str, at: str) -> str:
    if by.startswith("auto:"):
        return t("Auto-synced · {source} · {at}",
                 source=by.split(":", 1)[1].replace("_", " "), at=at)
    if by:
        return t("Uploaded by {by} · {at}", by=by, at=at)
    return ""


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

# ── Global date filter — re-slices every section below ────────────────────────
_lo, _hi = data_date_bounds(det_df)
# Translated label -> English preset key. The key is what preset_range() looks
# up in PRESETS, so it must stay English; only the label is translated.
_opt_labels = {t(k): k for k in list(PRESETS.keys()) + ["Custom"]}
# Open on DEFAULT_PRESET rather than whatever sits first. The page used to open
# on "All", which was a harmless ~3-week window only because DATA_FLOOR was
# wrongly clamping the data to May 2026; with the real 2.6 years visible, "All"
# as an opening view is 89,800 people and ~950 daily bars.
_keys = list(_opt_labels.values())
_default_idx = _keys.index(DEFAULT_PRESET) if DEFAULT_PRESET in _keys else 0
_pc, _cc = st.columns([3, 2])
with _pc:
    _preset = _opt_labels[st.radio(t("Date range"), list(_opt_labels),
                                   index=_default_idx, horizontal=True,
                                   key="ff_preset", label_visibility="collapsed")]
if _preset == "Custom":
    with _cc:
        _d1, _d2 = st.columns(2)
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

det_df = filter_by_range(det_df, sel_start, sel_end)
if det_df.empty:
    st.info(t("No findings in the selected date range — widen the range to see data."))

# Report window — the date range Tableau was pulled for + how many days it spans
_rstart, _rend = sel_start, sel_end
if _rstart and _rend:
    _days = (_rend - _rstart).days + 1
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap;'
        f'margin:0 0 0.5rem 0;">'
        f'<span style="display:inline-flex;align-items:center;gap:0.4rem;'
        f'background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.35);'
        f'color:#a5b4fc;border-radius:999px;padding:0.3rem 0.85rem;font-size:0.8rem;'
        f'font-weight:700;letter-spacing:0.02em;">📅 {_fmt_range(_rstart, _rend)}</span>'
        f'<span style="color:#6b7280;font-size:0.8rem;font-weight:600;">'
        f'{_days} day{"s" if _days != 1 else ""}</span>'
        f'{"<span style=\'color:#4b5563;font-size:0.78rem;\'>·&nbsp;" + sync_note + "</span>" if sync_note else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
elif sync_note:
    st.caption(sync_note)


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


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — TOP-LINE KPIs
# ══════════════════════════════════════════════════════════════════════════════

render_kpi_row([
    {"label": "People Found",   "value": int(found)},
    {"label": "Contact Attempted", "value": int(attempted)},
    {"label": "Contacted",      "value": int(contacted)},
    {"label": "Being Taught",   "value": int(teaching)},
    {"label": "New Referrals",  "value": int(referred)},
])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PIPELINE FUNNEL  +  FINDING MIX
# ══════════════════════════════════════════════════════════════════════════════

fcol, dcol = st.columns([3, 2])

with fcol:
    render_section_label(t("Finding Pipeline"))
    if stage_counts:
        # Translate for the axis only; the counts stay keyed in English.
        labels = [t(l) for l, _ in FUNNEL_STAGES]
        values = [stage_counts[l] for l, _ in FUNNEL_STAGES]
        # Labels OUTSIDE each bar in white: readable on every slice color and
        # on the thin lower stages. Widen the x-range so the full-width "Found"
        # bar's label isn't clipped at the right edge.
        _fmax = max(values) or 1
        fig = go.Figure(go.Funnel(
            y=labels, x=values,
            textposition="outside", textinfo="value+percent initial",
            textfont=dict(color="#ffffff", size=13),
            outsidetextfont=dict(color="#ffffff", size=13),
            # Seventh colour is gold — Baptized is the outcome the whole funnel
            # exists for, and it was the stage this chart used to leave out.
            marker=dict(color=["#6366f1", "#22c55e", "#06b6d4", "#f59e0b",
                               "#ec4899", "#ef4444", "#facc15"],
                        line=dict(width=0)),
            connector=dict(line=dict(color="rgba(255,255,255,0.10)", width=1)),
        ))
        fig.update_layout(height=430, margin=dict(l=140, r=20, t=10, b=10),
                          template="pmg_dark", paper_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(visible=False, range=[-_fmax * 0.05, _fmax * 1.35]))
        st.plotly_chart(fig, use_container_width=True, theme=None,
                        config={"displayModeBar": False})
        st.caption(t("Each stage = people found in range who reached at least that "
                     "far. A milestone that was never logged is inherited from a "
                     "later one, so the funnel never widens."))
    else:
        st.caption(t("Detail records needed to build the pipeline funnel."))

with dcol:
    render_section_label(t("Finding Mix"))
    cat_col = _col(det_df, "finding_category") if not det_df.empty else None
    if cat_col:
        cats = (det_df[cat_col].astype(str).str.strip()
                .replace({"": "Unknown", "nan": "Unknown"}).value_counts())
        # Labels sit OUTSIDE the ring in a single white color: high-contrast on
        # the dark background and version-proof (Cloud's plotly ignores per-point
        # text-color arrays and won't fit a horizontal % inside the thin ring).
        _total = int(cats.sum()) or 1
        _pct_text = [f"{v / _total * 100:.0f}%" if v / _total >= 0.02 else ""
                     for v in cats.values]
        donut = go.Figure(go.Pie(
            labels=cats.index.tolist(), values=cats.values.tolist(),
            hole=0.62, sort=False, rotation=270,
            marker=dict(colors=PALETTE, line=dict(color="#08080e", width=2)),
            text=_pct_text, textinfo="text", textposition="outside",
            textfont=dict(color="#ffffff", size=14),
            outsidetextfont=dict(color="#ffffff", size=14),
            insidetextfont=dict(color="#ffffff", size=14),
        ))
        donut.update_layout(
            height=400, margin=dict(l=30, r=30, t=20, b=80), template="pmg_dark",
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.18, x=0.5, xanchor="center"),
            annotations=[dict(text=f"{int(found)}<br>found", x=0.5, y=0.5,
                              font=dict(size=18, color="#f4f4f8"), showarrow=False)],
        )
        st.plotly_chart(donut, use_container_width=True, theme=None,
                        config={"displayModeBar": False})
    else:
        st.caption(t("No detail records to break down."))


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CONTACT PERFORMANCE  (speed + conversion)
# ══════════════════════════════════════════════════════════════════════════════

if not det_df.empty:
    render_section_label(t("Contact Performance"))
    contact_rate = (attempted / found * 100) if found else 0
    success_rate = (contacted / found * 100) if found else 0
    render_kpi_row([
        {"label": "Contact to Friend", "value": f"{contact_rate:.0f}%"},
        {"label": "Success Rate",    "value": f"{success_rate:.0f}%"},
        {"label": "Median to Contact", "value": _fmt_dur(median_attempt)},
        {"label": "Within 24h", "value": f"{within24:.0f}%" if within24 is not None else "—"},
        {"label": "Within 48h", "value": f"{within48:.0f}%" if within48 is not None else "—"},
    ])


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SOURCES  +  ZONES  +  DAILY TREND
# ══════════════════════════════════════════════════════════════════════════════

if not det_df.empty:
    src_col  = _col(det_df, "finding_source")
    zone_col = _col(det_df, "latest_zone")

    s1, s2 = st.columns(2)
    with s1:
        render_section_label(t("Top Finding Sources"))
        if src_col:
            src = (det_df[src_col].astype(str).str.strip()
                   .replace({"": "Unknown", "nan": "Unknown"})
                   .value_counts().head(10).sort_values())
            bar = go.Figure(go.Bar(
                x=src.values.tolist(), y=src.index.tolist(), orientation="h",
                marker=dict(color="#6366f1"), text=src.values.tolist(),
                textposition="outside", cliponaxis=False,
                textfont=dict(color="#ffffff", size=12)))
            bar.update_layout(
                height=340, margin=dict(l=10, r=55, t=10, b=10), template="pmg_dark",
                xaxis=dict(visible=False, range=[0, int(src.max()) * 1.18]))
            st.plotly_chart(bar, use_container_width=True, theme=None,
                            config={"displayModeBar": False})

    with s2:
        render_section_label(t("Findings by Zone"))
        if zone_col:
            zn = (det_df[zone_col].astype(str).str.strip()
                  .replace({"": "Unknown", "nan": "Unknown"})
                  .value_counts().sort_values())
            zbar = go.Figure(go.Bar(
                x=zn.values.tolist(), y=zn.index.tolist(), orientation="h",
                marker=dict(color="#22c55e"), text=zn.values.tolist(),
                textposition="outside", cliponaxis=False,
                textfont=dict(color="#ffffff", size=12)))
            zbar.update_layout(
                height=340, margin=dict(l=10, r=55, t=10, b=10), template="pmg_dark",
                xaxis=dict(visible=False, range=[0, int(zn.max()) * 1.18]))
            st.plotly_chart(zbar, use_container_width=True, theme=None,
                            config={"displayModeBar": False})

    # Finding trend. Buckets by month once the window is long — with the bogus
    # DATA_FLOOR gone, "All" spans 2.6 years and a per-day chart is ~950 bars
    # of illegible labels. trend_series() decides and says which it drew.
    _tlabels, _tvalues, _tgran = trend_series(det_df)
    if _tlabels:
        render_section_label(t("Findings per Month") if _tgran == "month"
                             else t("Findings per Day"))
        tbar = go.Figure(go.Bar(
            x=_tlabels, y=_tvalues,
            marker=dict(color="#8b5cf6"), text=_tvalues,
            textposition="outside", cliponaxis=False,
            textfont=dict(color="#ffffff", size=12)))
        tbar.update_layout(
            height=240, margin=dict(l=10, r=10, t=26, b=10), template="pmg_dark",
            yaxis=dict(visible=False, range=[0, max(_tvalues) * 1.2]))
        st.plotly_chart(tbar, use_container_width=True, theme=None,
                        config={"displayModeBar": False})


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — RAW DATA  (dropdowns)
# ══════════════════════════════════════════════════════════════════════════════

render_section_label(t("Detailed Data"))

# ── Area Rankings table ───────────────────────────────────────────────────────
with st.expander(t("Area Rankings (per-area table)"), expanded=False):
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
        render_table(disp.reset_index(drop=True))
        st.download_button(t("Download Rankings CSV"),
                           data=ranks.to_csv(index=False).encode("utf-8"),
                           file_name="finding_rankings.csv", mime="text/csv")

# ── Finding Records table ─────────────────────────────────────────────────────
with st.expander(t("Finding Records — {n} people",
                   n=0 if det_df.empty else len(det_df)),
                 expanded=False):
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

# ── Raw Tableau export (every column, untouched) ──────────────────────────────
with st.expander(t("Raw Tableau export (all columns)"), expanded=False):
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

# ── Finding Summary PDF ───────────────────────────────────────────────────────
# Only ever previews the LAST file: uploading 31 at once for a backfill should
# not try to render 31 embedded viewers.
with st.expander(t("Finding Summary PDF"), expanded=False):
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

# ── Manual upload / re-sync ───────────────────────────────────────────────────
_render_uploaders()
