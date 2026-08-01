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
from app.db.queries import get_tableau_detail, get_tableau_ranking
from app.db.sheets_client import save_dataframe
from app.analytics.finding_funnel import (
    PRESETS, data_date_bounds, preset_range, filter_by_range, build_area_rankings,
)
from app.i18n import t
from app.i18n.formats import NA, fmt_date_range, fmt_day_month, fmt_int, fmt_percent

st.set_page_config(page_title="CCSM · Finding Funnel — PMG Compass", page_icon="", layout="wide")

user = require_auth()
inject_global_css()
render_sidebar(user)

render_page_header(
    t("Finding Funnel"),
    t("Mission finding & teaching pipeline — auto-synced daily from Tableau"),
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
    try:
        df = pd.read_csv(uploaded)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        save_dataframe(tab_name, df, uploaded_by=user.get("email", ""))
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


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

if ranking_file is not None:
    rank_df, err = _process_upload(ranking_file, "TABLEAU_RANKING")
    if err:
        st.error(t("Could not parse Ranking CSV: {err}", err=err))
        rank_df = pd.DataFrame()
    rank_by, rank_at = user.get("email", ""), "just now"
else:
    rank_df, rank_by, rank_at = get_tableau_ranking()

if detail_file is not None:
    det_df, err = _process_upload(detail_file, "TABLEAU_DETAIL")
    if err:
        st.error(t("Could not parse Detail CSV: {err}", err=err))
        det_df = pd.DataFrame()
    det_by, det_at = user.get("email", ""), "just now"
else:
    det_df, det_by, det_at = get_tableau_detail()

if rank_df.empty and det_df.empty:
    st.info(t("No finding data yet. It syncs automatically each morning, or upload a "
              "Tableau export in **Manual upload** below."))
    st.stop()

sync_note = _source_caption(rank_by, rank_at) or _source_caption(det_by, det_at)

# ── Global date filter — re-slices every section below ────────────────────────
_lo, _hi = data_date_bounds(det_df)
# Translated label -> English preset key. The key is what preset_range() looks
# up in PRESETS, so it must stay English; only the label is translated.
_opt_labels = {t(k): k for k in list(PRESETS.keys()) + ["Custom"]}
_pc, _cc = st.columns([3, 2])
with _pc:
    _preset = _opt_labels[st.radio(t("Date range"), list(_opt_labels), index=0,
                                   horizontal=True, key="ff_preset",
                                   label_visibility="collapsed")]
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
referred = int(_date(det_df, "first_referral_event_date").notna().sum()) \
    if not det_df.empty else 0

# ── Detail event milestones — the true finding-to-progress funnel ─────────────
# Each stage counts people (found in range) who reached that milestone. Ordered
# so the funnel is monotonic: every later stage is a subset of the earlier one.
# Labels are display-only (chart axis text); the second element is the Detail
# column name and must never be translated.
FUNNEL = [
    (t("Found"),                  None),
    (t("Contact Attempted"),      "first_contact_attempt_event_date"),
    (t("Successfully Contacted"), "first_successful_contact_attempt_event_date"),
    (t("Being Taught"),           "first_new_person_being_taught_date"),
    (t("Attended Church"),        "first_sacrament_date"),
    (t("Baptism Date Set"),       "first_baptism_goal_date_set"),
]

found = len(det_df)

stage_counts = {}
if not det_df.empty:
    for label, datecol in FUNNEL:
        stage_counts[label] = found if datecol is None else int(_date(det_df, datecol).notna().sum())

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
        labels = [l for l, _ in FUNNEL]
        values = [stage_counts[l] for l in labels]
        # Labels OUTSIDE each bar in white: readable on every slice color and
        # on the thin lower stages. Widen the x-range so the full-width "Found"
        # bar's label isn't clipped at the right edge.
        _fmax = max(values) or 1
        fig = go.Figure(go.Funnel(
            y=labels, x=values,
            textposition="outside", textinfo="value+percent initial",
            textfont=dict(color="#ffffff", size=13),
            outsidetextfont=dict(color="#ffffff", size=13),
            marker=dict(color=["#6366f1", "#22c55e", "#06b6d4", "#f59e0b",
                               "#ec4899", "#ef4444"], line=dict(width=0)),
            connector=dict(line=dict(color="rgba(255,255,255,0.10)", width=1)),
        ))
        fig.update_layout(height=380, margin=dict(l=140, r=20, t=10, b=10),
                          template="pmg_dark", paper_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(visible=False, range=[-_fmax * 0.05, _fmax * 1.35]))
        st.plotly_chart(fig, use_container_width=True, theme=None,
                        config={"displayModeBar": False})
        st.caption(t("Each stage = people found in range who reached that milestone "
                     "(from Tableau finding-event dates)."))
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

    # Daily finding trend
    ev_dates = _date(det_df, "event_date_selected").dt.date.dropna()
    if not ev_dates.empty:
        render_section_label(t("Findings per Day"))
        per_day = ev_dates.value_counts().sort_index()
        tbar = go.Figure(go.Bar(
            x=[str(d) for d in per_day.index], y=per_day.values.tolist(),
            marker=dict(color="#8b5cf6"), text=per_day.values.tolist(),
            textposition="outside", cliponaxis=False,
            textfont=dict(color="#ffffff", size=12)))
        tbar.update_layout(
            height=240, margin=dict(l=10, r=10, t=26, b=10), template="pmg_dark",
            yaxis=dict(visible=False, range=[0, int(per_day.max()) * 1.2]))
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
with st.expander(t("Finding Summary PDF"), expanded=False):
    if summary_file is None:
        st.caption(t("Upload the Finding Summary PDF in Manual upload below to view it here."))
    else:
        pdf_bytes = summary_file.read()
        st.caption(t('{name} · {value:.1f} KB', name=summary_file.name, value=len(pdf_bytes) / 1024))
        st.download_button(t("Download Summary PDF"), data=pdf_bytes,
                           file_name=summary_file.name, mime="application/pdf")
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        st.components.v1.html(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800px" '
            f'type="application/pdf" sandbox="allow-same-origin"></iframe>', height=820)

# ── Manual upload / re-sync ───────────────────────────────────────────────────
with st.expander(t("Manual upload / re-sync (optional)"), expanded=False):
    st.caption(t("Tableau exports sync automatically every morning. Upload here only "
                 "to override with a fresh export."))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.file_uploader(t("Detail CSV"), type=["csv"], key="detail")
    with c2:
        st.file_uploader(t("Ranking CSV"), type=["csv"], key="ranking")
    with c3:
        st.file_uploader(t("Summary PDF"), type=["pdf"], key="summary")
