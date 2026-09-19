"""app/components/design_system.py — single source of visual design."""
from __future__ import annotations

import html as _html
import streamlit as st
import plotly.io as pio
import plotly.graph_objects as go
from app.config.theme import SERIES_COLORS, STATUS
from app.i18n import t
from app.i18n.formats import fmt_int, fmt_number
from app.analytics import period_delta as _pd


def _delta_direction(pct: float) -> int:
    """Direction for a caller that passed a bare percentage, not a change dict.

    Applies the same neutral band period_delta does, so the two entry points
    cannot disagree about whether a 3% move is a trend.
    """
    if abs(pct) < _pd.NEUTRAL_BAND_PCT:
        return _pd.FLAT
    return _pd.UP if pct > 0 else _pd.DOWN

#: RETIRED from charts (data-pages plan A3, 2026-09-18): the chart colorway is
#: theme.SERIES_COLORS and status is theme.STATUS. Kept for the pages outside
#: that plan that still import it.
PALETTE = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]

_CSS = """
<style>
.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
}

/* KPI cards (render_kpi_row): a grid that WRAPS. Four across at the 1400px
   design width, two across on a phone; auto-fit lets a short row stretch to
   fill, as the old flex row did. Audit X1 (2026-09-18): the flex row never
   wrapped and seven cards at 375px were seven illegible slivers.
   The minimum is the larger of 210px and 22% of the row: 22% caps the grid at
   four columns however wide the row gets (sidebar open, 900px: four; sidebar
   collapsed, 1235px: still four, not five), and 210px is the narrowest a card
   stays legible, which gives three columns on a tablet. Measured 2026-09-18. */
.pmg-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(max(210px, 22%), 1fr));
    gap: 12px;
    margin-bottom: 1.5rem;
}
@media (max-width: 640px) {
    .pmg-kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 8px;
    }
    .pmg-kpi { padding: 0.75rem 0.8rem !important; }
    .pmg-kpi-value { font-size: 1.5rem !important; }
}
/* Section labels with an ⓘ are a <details>; the browser's own disclosure
   triangle would fight the label's rule, so it is hidden here. */
details.pmg-sec > summary { list-style: none; }
details.pmg-sec > summary::-webkit-details-marker { display: none; }
details.pmg-sec[open] .pmg-info { background: rgba(255,255,255,0.12); }
a.pmg-kpi-link, a.pmg-kpi-link:visited, a.pmg-kpi-link:hover {
    color: inherit !important;
    text-decoration: none !important;
    cursor: pointer;
}
a.pmg-kpi-link:hover {
    border-color: rgba(57, 135, 229, 0.65) !important;
    background: rgba(255, 255, 255, 0.07) !important;
}
/* [data-testid="stMain"] is the actual scrolling element (overflow-y: auto),
   not the document body. Its vertical scrollbar only reserves width while the
   content actually overflows, so the content width silently depends on whether
   a scrollbar happens to be needed right now. That is THE cause of the "area
   view is wider" report (Carson, 2026-07-19): a tall group view (zone/district
   with many areas) always needs the scrollbar, but the short single-area view
   can fit without one, so switching to an area drops the ~15px scrollbar and
   everything below it -- the scope dropdowns and every use_container_width
   chart -- widens by that much. No chart is "too wide"; the charts follow the
   container, they don't set it.

   Two independent guards so the reserved width never depends on scrollbar
   state OR on how a given browser treats the gutter:
     - scrollbar-gutter: stable  reserves the gutter permanently (Chromium/
       Firefox honor it; some engines ignore it -- hence the second guard).
     - overflow-y: scroll        forces the scrollbar TRACK to always render,
       the decades-old always-reserve-the-scrollbar technique, effective even
       where scrollbar-gutter is ignored. On a view that fits, the track shows
       greyed/disabled instead of the width jumping -- the correct trade.
   Belt and suspenders on purpose: an overlay-scrollbar browser (thin bar, no
   reserved width) never jumped in the first place, and a classic-scrollbar
   browser (Windows Chrome, ~15-17px) is now pinned by both rules. */
[data-testid="stMain"] {
    scrollbar-gutter: stable !important;
    overflow-y: scroll !important;
}
.stApp, [data-testid="stAppViewContainer"] {
    background-color: #08080e !important;
    color: #f4f4f8 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter',
                 'Segoe UI', sans-serif !important;
}
[data-testid="stHeader"] { background-color: #08080e !important; }
[data-testid="stDecoration"] { background-color: #08080e !important; }
div[data-testid="stToolbar"] { background-color: #08080e !important; }
[data-testid="stSidebar"] {
    background-color: #0e0e15 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] * { color: #f4f4f8 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #f4f4f8 !important;
    border-radius: 8px !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(99,102,241,0.15) !important;
    border-color: rgba(99,102,241,0.3) !important;
}
h1, h2, h3, h4, h5, h6 {
    color: #f4f4f8 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter',
                 'Segoe UI', sans-serif !important;
    letter-spacing: -0.02em !important;
}
p, .stMarkdown, .stText, label,
.stCaption, [data-testid="stCaptionContainer"] {
    color: #f4f4f8 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter',
                 'Segoe UI', sans-serif !important;
}
[data-testid="stMarkdownContainer"] p { color: #f4f4f8 !important; }
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.04) !important;
    backdrop-filter: blur(12px) saturate(150%) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
    transition: all 0.2s ease !important;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(255,255,255,0.15) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.12) !important;
}
[data-testid="stMetricValue"] {
    color: #f4f4f8 !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
    font-variant-numeric: tabular-nums !important;
}
[data-testid="stMetricLabel"] {
    color: #9ca3af !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; font-weight: 600 !important; }
.stButton > button {
    background: rgba(255,255,255,0.05) !important;
    color: #f4f4f8 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
    font-family: inherit !important;
}
.stButton > button:hover {
    background: rgba(99,102,241,0.15) !important;
    border-color: rgba(99,102,241,0.4) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.15) !important;
}
.stButton > button:active { transform: translateY(0) !important; }
.stDownloadButton > button {
    background: rgba(99,102,241,0.2) !important;
    border-color: rgba(99,102,241,0.4) !important;
    color: #f4f4f8 !important;
}
.stDownloadButton > button:hover { background: rgba(99,102,241,0.35) !important; }
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stTextInput > div > div,
.stTextArea > div > div {
    background: rgba(255,255,255,0.04) !important;
    color: #f4f4f8 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
}
/* NumberInput's box+border go on the OUTER container (the one that wraps
   BOTH the text area and the +/- steppers), not on each inner div — putting
   it on the two inner divs (old behavior) gave each its own border/background,
   which reads as two boxes glued together (a visible seam between the number
   and the steppers) instead of one continuous pill. */
div[data-testid="stNumberInputContainer"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
}
.stNumberInput > div > div {
    background: transparent !important;
    color: #f4f4f8 !important;
    border: none !important;
}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within {
    border-color: rgba(99,102,241,0.5) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.1) !important;
}
.stTextInput input,
.stNumberInput input,
[data-baseweb="input"] input,
[data-baseweb="base-input"] input,
[data-testid="stTextInput"] input {
    color: #f4f4f8 !important;
    -webkit-text-fill-color: #f4f4f8 !important;
    background: transparent !important;
    caret-color: #a5b4fc !important;
}
/* [data-baseweb="base-input"] is an inner wrapper (between .stNumberInput's
   outer box and the <input> itself) that BaseWeb gives its own opaque light
   background by default. Streamlit 1.40.0 renders this wrapper (some other
   versions don't add this extra nesting level), so without this override the
   light box shows through and hides the dark styling above. Same story for
   the number input's +/- steppers, which are plain BaseWeb buttons with their
   own solid light background, independent of the input box's styling. */
[data-baseweb="base-input"],
button[data-testid="stNumberInputStepDown"],
button[data-testid="stNumberInputStepUp"] {
    background: transparent !important;
}
/* Same blue hover glow as .stButton > button:hover elsewhere in the app,
   minus the translateY lift (these sit flush inside the merged input box —
   lifting one would visually pop it out of that shared border). Excluded
   when disabled (the "-" stepper at min_value) so it doesn't invite a click
   that won't do anything. */
button[data-testid="stNumberInputStepDown"]:not(:disabled):hover,
button[data-testid="stNumberInputStepUp"]:not(:disabled):hover {
    background: rgba(99,102,241,0.15) !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.15) !important;
}
.stSelectbox label, .stMultiSelect label,
.stTextInput label, .stTextArea label,
.stNumberInput label, .stDateInput label,
.stCheckbox label, .stRadio label {
    color: #9ca3af !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
}
.stTextArea textarea {
    background: rgba(255,255,255,0.04) !important;
    color: #f4f4f8 !important;
    -webkit-text-fill-color: #f4f4f8 !important;
    caret-color: #a5b4fc !important;
}
.stDateInput > div > div {
    background: rgba(255,255,255,0.04) !important;
    color: #f4f4f8 !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}
[data-testid="stDataFrame"], .stDataFrame {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
.dvn-scroller { background: #0e0e15 !important; }
.col_heading {
    background: rgba(99,102,241,0.1) !important;
    color: #9ca3af !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
}
.data {
    background: transparent !important;
    color: #f4f4f8 !important;
    font-variant-numeric: tabular-nums !important;
    border-bottom: 1px solid rgba(255,255,255,0.04) !important;
}
.row_heading { background: rgba(255,255,255,0.02) !important; color: #9ca3af !important; }
/* Themed HTML tables (render_table) — replaces canvas st.dataframe which paints blank */
.pmg-tbl {
    width: 100%;
    overflow-x: auto;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    margin: 0.25rem 0 0.5rem 0;
}
.pmg-tbl table {
    width: 100%;
    border-collapse: collapse !important;
    font-size: 0.82rem !important;
    font-variant-numeric: tabular-nums !important;
}
.pmg-tbl thead th {
    background: rgba(99,102,241,0.10) !important;
    color: #9ca3af !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    text-align: right;
    padding: 0.55rem 0.85rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.10) !important;
    white-space: nowrap;
}
.pmg-tbl tbody td {
    color: #f4f4f8;  /* no !important — lets pandas Styler inline colors win */
    text-align: right;
    padding: 0.5rem 0.85rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.045) !important;
}
.pmg-tbl tbody tr:last-child td { border-bottom: none !important; }
.pmg-tbl tbody tr:hover td { background: rgba(255,255,255,0.025) !important; }
/* First column reads as a row label: left-aligned unless centered variant */
.pmg-tbl:not(.pmg-tbl-center) thead th:first-child,
.pmg-tbl:not(.pmg-tbl-center) tbody td:first-child {
    text-align: left;
    color: #e5e7eb !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary { color: #f4f4f8 !important; font-weight: 600 !important; }
[data-testid="stAlert"] {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #f4f4f8 !important;
}
.stSuccess { border-left: 3px solid #22c55e !important; }
.stInfo    { border-left: 3px solid #6366f1 !important; }
.stWarning { border-left: 3px solid #f59e0b !important; }
.stError   { border-left: 3px solid #ef4444 !important; }
[data-testid="stTabs"] [role="tab"] {
    color: #6b7280 !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #f4f4f8 !important;
    border-bottom: 2px solid #6366f1 !important;
}
[data-testid="stTabsContent"] { background: transparent !important; }
[data-testid="stProgressBar"] > div {
    background: rgba(255,255,255,0.06) !important;
    border-radius: 4px !important;
}
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #6366f1, #8b5cf6) !important;
    border-radius: 4px !important;
}
hr {
    border: none !important;
    border-top: 1px solid rgba(255,255,255,0.07) !important;
    margin: 1.5rem 0 !important;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.5); }
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
}
[data-testid="stSpinner"] { color: #6366f1 !important; }
.stRadio > div { color: #f4f4f8 !important; }
.stCheckbox label { color: #f4f4f8 !important; }
.stCode, code, pre {
    background: rgba(255,255,255,0.05) !important;
    color: #a5f3fc !important;
    border-radius: 6px !important;
}
.js-plotly-plot .plotly text,
.js-plotly-plot .plotly .gtitle,
.js-plotly-plot .plotly .xtick text,
.js-plotly-plot .plotly .ytick text,
.js-plotly-plot .plotly .legend text,
.js-plotly-plot .plotly .legendtext {
    fill: #9ca3af !important;
    color: #9ca3af !important;
}
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    padding: 0.5rem !important;
}
[data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px dashed rgba(99,102,241,0.4) !important;
    border-radius: 8px !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    background: rgba(99,102,241,0.08) !important;
    border-color: rgba(99,102,241,0.65) !important;
}
[data-testid="stFileUploaderDropzone"] * { color: #9ca3af !important; }
[data-testid="stFileUploaderDropzone"] button {
    background: rgba(99,102,241,0.15) !important;
    border: 1px solid rgba(99,102,241,0.35) !important;
    color: #a5b4fc !important;
    border-radius: 6px !important;
}
[data-testid="stFileUploaderDropzone"] button:hover {
    background: rgba(99,102,241,0.28) !important;
    border-color: rgba(99,102,241,0.55) !important;
}
[data-testid="uploadedFileData"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 6px !important;
    color: #f4f4f8 !important;
}
[data-testid="uploadedFileData"] * { color: #f4f4f8 !important; }
/* Sidebar page labels are written out in Home.py's st.navigation now, so they
   arrive already cased correctly. This used to be `text-transform: capitalize`,
   which was there to tidy up labels Streamlit derived from filenames — and it
   title-cased every word, turning "Embudo de Búsqueda" into "Embudo De
   Búsqueda" and "Centro de Acción" into "Centro De Acción". Spanish does not
   capitalise its prepositions; leave the declared label alone. */
[data-testid="stSidebarNavLink"] span {
    text-transform: none !important;
}
</style>
"""

def _test_mode_banner() -> str:
    """Build the TEST MODE banner at render time from the real config value.

    Never falls back to a hardcoded address — if TEST_INBOX_EMAIL is empty,
    the banner still renders but names no inbox.
    """
    from app.db.queries import get_config_value
    inbox = get_config_value("TEST_INBOX_EMAIL", "").strip()
    message = (
        f"TEST MODE ACTIVE — Emails redirected to {inbox}"
        if inbox
        else "TEST MODE ACTIVE — Emails redirected to the test inbox"
    )
    return (
        "<div style='background:linear-gradient(135deg,#7f1d1d,#991b1b);"
        "color:#fecaca;padding:10px 16px;font-weight:700;font-size:13px;"
        "text-align:center;margin-bottom:12px;border-radius:8px;"
        "border:1px solid rgba(239,68,68,0.3);letter-spacing:0.02em;'>"
        f"{_html.escape(message)}</div>"
    )

_PILL_COLORS: dict[str, tuple[str, str, str]] = {
    "blue":   ("rgba(99,102,241,0.15)",  "rgba(99,102,241,0.4)",  "#a5b4fc"),
    "green":  ("rgba(34,197,94,0.15)",   "rgba(34,197,94,0.4)",   "#86efac"),
    "amber":  ("rgba(245,158,11,0.15)",  "rgba(245,158,11,0.4)",  "#fcd34d"),
    "red":    ("rgba(239,68,68,0.15)",   "rgba(239,68,68,0.4)",   "#fca5a5"),
    "purple": ("rgba(139,92,246,0.15)",  "rgba(139,92,246,0.4)",  "#c4b5fd"),
}


def _register_plotly_template() -> None:
    tmpl = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#9ca3af", family="system-ui, -apple-system"),
            colorway=SERIES_COLORS,
            xaxis=dict(
                gridcolor="rgba(255,255,255,0.06)",
                linecolor="rgba(255,255,255,0.1)",
                zerolinecolor="rgba(255,255,255,0.1)",
            ),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.06)",
                linecolor="rgba(255,255,255,0.1)",
                zerolinecolor="rgba(255,255,255,0.1)",
            ),
        )
    )
    pio.templates["pmg_dark"] = tmpl
    pio.templates.default = "pmg_dark"


def inject_stylesheet() -> None:
    """The stylesheet and the Plotly template, and nothing else.

    Split out of inject_global_css on 2026-09-02. The two things that function
    did — style the page, and announce TEST MODE — have different lifetimes: a
    fragment rerun loses the <style> block and must re-add it, but re-adding
    the banner draws a SECOND one. That was the audit's double-banner finding
    (step 1.6), and it survived the navigation rebuild because Desgloses'
    fragment legitimately needs the CSS back.
    """
    st.markdown(_CSS, unsafe_allow_html=True)
    _register_plotly_template()


def inject_global_css() -> None:
    """Page chrome: the stylesheet plus the TEST MODE banner if it applies.

    Called exactly once per script run, by Home.py's navigation router. A page
    that needs the stylesheet back after a fragment rerun wants
    inject_stylesheet() instead — this one would duplicate the banner.
    """
    inject_stylesheet()
    try:
        from app.db.queries import get_config_value
        if get_config_value("TEST_MODE", "FALSE").upper() == "TRUE":
            st.markdown(_test_mode_banner(), unsafe_allow_html=True)
    except Exception:
        pass


def render_page_header(title: str, subtitle: str, icon: str = "") -> None:
    """Render consistent page header: bold title, muted subtitle, indigo gradient divider."""
    prefix = f"{_html.escape(icon)} " if icon else ""
    st.markdown(
        f'<div style="margin-bottom:1.5rem;">'
        f'<h1 style="font-size:1.75rem;font-weight:800;letter-spacing:-0.03em;'
        f'color:#f4f4f8;margin:0 0 0.25rem 0;">{prefix}{_html.escape(title)}</h1>'
        f'<p style="font-size:0.875rem;color:#6b7280;margin:0;">{_html.escape(subtitle)}</p>'
        f'<div style="height:1px;background:linear-gradient(90deg,rgba(99,102,241,0.5),'
        f'rgba(99,102,241,0.1),transparent);margin-top:1rem;"></div></div>',
        unsafe_allow_html=True,
    )


#: Goal-bar tiers, and the one place they are written down. Four, not three:
#: amber used to run all the way from 60% to nothing, so baptismal invitation
#: at 39% of target -- the single most actionable fact the 2026-08-21 audit
#: found (H2) -- drew the same colour as a metric sitting at 55%.
#: Three states, no blue (decision 10): on pace >= 90% of pace, behind 60-89%,
#: far behind below. Blue means "this metric, this period" on every chart, so
#: it can never also mean a grade.
_GOAL_BAR_TIERS = ((90, STATUS["good"]), (60, STATUS["warn"]))
_GOAL_BAR_BELOW = STATUS["bad"]


def goal_bar_state(value, goal, *, pace=None, value_basis=None, goal_basis=None):
    """How a goal bar should draw itself: how full, how graded, where the tick.

    Pure arithmetic, lifted out of render_kpi_row so the rules below can be
    tested without a Streamlit runtime or an HTML parse.

    Returns a dict:
      ``measured``  False when the value is not a number yet (the weekly form
                    has not landed). Distinct from a value of zero, which is a
                    real reading of nothing.
      ``per_area``  whether the ratio was reduced to per-area rates first
      ``v_rate`` / ``g_rate``  those rates, when it was
      ``pct``       value against the FULL goal, for the caption. Never clamped:
                    a goal set far too low must be able to read 196%.
      ``width``     the bar's fill, value against the full goal, clamped 0-100
      ``grade_pct`` what the COLOUR is judged on -- value against ``pace`` when
                    a pace is given, else the same as ``pct``
      ``tick``      where the pace mark sits on the track, 0-100, or None

    The split between ``width`` and ``grade_pct`` is the whole point. Two days
    into a thirty-day month a zone exactly on pace has produced 7% of the
    month's goal; grading that 7% paints it red and tells the mission it is
    failing when it is precisely on track. The bar still fills to 7%, because
    that is true -- the tick sits at 7% too, and the colour comes from the
    comparison between them.
    """
    measured = isinstance(value, (int, float))
    per_area = bool(value_basis) and bool(goal_basis) and measured
    v_rate = g_rate = None

    def _ratio(numerator_total, denominator_total):
        """`numerator_total` over `denominator_total`, per-area when the two
        rest on different numbers of areas. On 2026-08-21 the week ending 08-16
        held 33 areas' results (204 new people) over 1 area's goal (10) and a
        tile read 2.040%; reducing both to rates first cancels the mismatch."""
        if per_area:
            return (float(numerator_total) / float(value_basis)) / (
                float(denominator_total) / float(goal_basis))
        return float(numerator_total) / float(denominator_total)

    try:
        if per_area:
            v_rate = float(value) / float(value_basis)
            g_rate = float(goal) / float(goal_basis)
        pct = round(_ratio(value, goal) * 100) if measured else 0
    except (TypeError, ZeroDivisionError, ValueError):
        return {"measured": False, "per_area": False, "v_rate": None,
                "g_rate": None, "pct": 0, "width": 0, "grade_pct": 0,
                "tick": None}

    grade_pct, tick = pct, None
    try:
        if measured and pace is not None and float(pace) > 0:
            grade_pct = round(_ratio(value, pace) * 100)
            tick = max(0, min(100, round(float(pace) / float(goal) * 100)))
    except (TypeError, ZeroDivisionError, ValueError):
        grade_pct, tick = pct, None

    return {
        "measured": measured, "per_area": per_area,
        "v_rate": v_rate, "g_rate": g_rate,
        "pct": pct, "width": max(0, min(100, pct)) if measured else 0,
        "grade_pct": grade_pct, "tick": tick,
    }


def goal_bar_color(grade_pct: float) -> str:
    """The tier colour for a graded percentage."""
    for threshold, color in _GOAL_BAR_TIERS:
        if grade_pct >= threshold:
            return color
    return _GOAL_BAR_BELOW


def projection_caption(projection, fmt) -> str:
    """The "where this is heading" line under a goal bar, or "" for no line.

    `fmt` writes a number the way the calling card writes numbers.

    The tilde and the hedge are both load-bearing. A landing estimate is the
    only figure on this page that describes something that has not happened, so
    it must not be able to be mistaken for one that has: "~450" reads as an
    estimate where "450" reads as a count, and a low-confidence estimate says
    so in words rather than relying on the reader to know what a tilde implies.

    "low" covers both of the ways an estimate can be weak — too little history
    to fit a trend at all, and a fitted trend whose slope is not
    distinguishable from flat. The reader's response to both is the same, so
    they are not distinguished on the card.
    """
    if not projection:
        return ""
    value = projection.get("value")
    if value is None:
        return ""
    if projection.get("confidence") == "high":
        return t("on pace for ~{n}", n=fmt(value))
    return t("on pace for ~{n} (early estimate)", n=fmt(value))


#: The card's own look, inline so a card draws correctly even where the
#: stylesheet is missing (a fragment rerun that lost it). The GRID rule and its
#: phone breakpoint live in _CSS; the inline fallback below is the desktop grid.
_CARD_STYLE = ("background:rgba(255,255,255,0.04);backdrop-filter:blur(12px) saturate(150%);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:1rem 1.1rem;min-width:0;display:block;transition:all 0.2s ease;")
_GRID_STYLE = ("display:grid;grid-template-columns:repeat(auto-fit,minmax(max(210px,22%),1fr));"
               "gap:12px;margin-bottom:1.5rem;")

#: The goal-bar mark for the leadership goal (decision 6): a second tick on the
#: same track as the pace tick. Violet, so it reads as a reference rather than
#: as a grade — the same reason the expectation bar is violet.
_MARK_COLOR = "#9085e9"


def sparkline_svg(points, *, color: str = "#3987e5", width: int = 96,
                  height: int = 26) -> str:
    """An inline SVG polyline for a KPI card, or "" for fewer than two points.

    No axes, no labels, one hue: the sparkline says "which way is this going",
    and the card's value and change chip say everything else. The last point
    is emphasised with a dot so the reader can see where "now" is. A flat
    series draws a horizontal line through the middle rather than nothing.
    """
    try:
        vals = [float(v) for v in (points or []) if v is not None]
    except (TypeError, ValueError):
        return ""
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = hi - lo
    pad = 3
    n = len(vals)
    xs = [pad + (width - 2 * pad) * i / (n - 1) for i in range(n)]
    if span == 0:
        ys = [height / 2] * n
    else:
        ys = [pad + (height - 2 * pad) * (1 - (v - lo) / span) for v in vals]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return (
        f'<svg class="pmg-spark" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" preserveAspectRatio="none" aria-hidden="true" '
        f'style="display:block;margin-top:8px;overflow:visible;">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="2.2" fill="{color}"/>'
        f'</svg>'
    )


def render_kpi_row(metrics: list[dict]) -> None:
    """
    Render a row of glass KPI cards using a single st.markdown HTML block.

    The row is a CSS grid that WRAPS: four cards per row at the 1400px design
    width, two per row on a phone, and never a crushed column. (It was a
    non-wrapping flex row until 2026-09-18, and seven Key Indicator cards at
    375px rendered as seven illegible slivers — audit finding X1.) Callers
    pass every card of a section in one call and let the grid break the rows.

    Each dict keys: label (str), value (int|float|str), change (optional dict from
    app/analytics/period_delta.period_delta — the preferred form, it has already
    decided percent vs absolute and passed the move through the neutral band),
    delta (optional int/float pct — the older, simpler form, still supported),
    delta_label (optional str), goal (optional int/float — shows a progress bar,
    color-graded by how close value is to it), expectation
    (optional int/float — shows a SECOND progress bar underneath the goal one, for
    the area-type expectation reference instead of the set goal). The expectation
    bar is deliberately styled distinct from the goal bar (Carson, 2026-07-24: the
    two must read as clearly different things, not two goal bars) — fixed violet
    #8b5cf6 rather than performance-graded, and its caption says "expectation" not
    "goal", so the difference doesn't rely on color alone.

    pace (optional int/float) is what the goal would be if the period ended
    today — a thirty-day goal three days in. When present the bar grows a tick
    at pace/goal and its COLOUR is graded on value/pace instead of value/goal.
    day / days (optional ints) name where the period stands — "día 3/30" — and
    are what the caption prints for a paced card; without them it prints the
    pace itself. goal_by (optional str, already formatted) names the date the
    full goal is due; it goes into the card's details, not its caption.

    ONE caption line under the bar, always: "{pct}% de {goal}", plus
    " · día {n}/{m}" when paced. Everything that used to stack under it —
    goal_note (the derived goal's arithmetic), the per-area pair, the landing
    projection — is folded into a single ``details`` string, shown as the
    caption's hover title and meant for the section's ⓘ (render_section_label's
    ``info``) where a page wants it on screen. A card is a glance, not a
    paragraph.

    spark (optional list of numbers) draws an inline sparkline under the value.
    href (optional str) makes the WHOLE card a link — the query string a
    drill-down reads (``?ki=<key>``) — styled identically, with a hover border.
    mark (optional int/float) is a second labelled tick on the goal bar: the
    leadership transfer goal beside the companionships' own meta (decision 6,
    PLAN-2026-09-18-data-pages.md §1). mark_label (optional str) names it in
    the tick's tooltip.

    note (optional str) prints a small caption directly under the value — for a
    card whose big number is a share and whose count would otherwise be lost
    ("143 de 301 días-área").

    change_note (optional str) is what the card says INSTEAD of an arrow when
    there is no honest comparison to draw — "sin comparación". It renders only
    when no change was passed, so it can never contradict one, and
    change_note_title carries the reason on hover. The page that sets it should
    also put that reason in the section's ⓘ, for the reader on a phone who has
    no hover.

    points_unit (optional str, default "pp") is the suffix on a POINTS change.
    Percentage points are the default because rates were the first caller; a
    card measuring something else in unscaled points (the 1-3 effort score)
    passes "" and gets the bare number in the card's own decimals.

    unit (optional str) and decimals (optional int) change how the card writes its
    numbers — the value, and the goal in the caption. unit="%" with decimals=1
    gives "46,4%" over "93% de 50%". Both default to the plain integer this
    row has always drawn, so existing callers are unaffected.

    Change colors: green above +5%, grey inside ±5% ("no trend, just noise"),
    amber -5 to -15%, red below -15%. A change measured in percentage POINTS
    (period_delta.point_delta, for rates) uses its own thresholds: ±1 point for
    the neutral band, -5 points for red. All of them live in period_delta.

    Goal bar colors are the three STATUS states (green / amber / red, no blue),
    from _GOAL_BAR_TIERS, graded on the PACE where one is
    given and on the goal otherwise. See goal_bar_state() for the arithmetic
    and why the two are separated.
    """
    cards = ""
    for m in metrics:
        label = _html.escape(m.get("label", ""))
        value = m.get("value", 0)
        delta = m.get("delta")
        delta_label = _html.escape(m.get("delta_label", ""))
        goal = m.get("goal")
        expectation = m.get("expectation")

        # "unit" and "decimals" let a card carry something that is not a whole
        # count. The Panel's conversion rates are the first: 46,4% has to render
        # with its sign and its decimal, and so does the 50% target beneath it,
        # or the goal caption reads "93% of 50 goal" and leaves the reader to
        # guess 50 what. Both default to the plain integer this row has always
        # drawn, so every existing caller is untouched.
        unit = str(m.get("unit", ""))
        decimals = int(m.get("decimals", 0) or 0)

        def _card_number(n, places=None, _unit=unit, _decimals=decimals) -> str:
            """A number written the way THIS card writes numbers."""
            return f"{fmt_number(n, _decimals if places is None else places)}{_unit}"

        # "change" is app/analytics/period_delta.py's description of a change --
        # it has already decided percent vs absolute, and has already passed the
        # change through the neutral band. "delta" is the older, simpler form:
        # a bare percentage. Both are supported; a caller passing "change" wins.
        change = m.get("change")
        if change is None and delta is not None:
            change = {"pct": float(delta), "change": None,
                      "show": _pd.PERCENT,
                      "direction": _delta_direction(float(delta))}

        delta_html = ""
        if change is not None:
            direction = int(change.get("direction", _pd.FLAT))
            pct = change.get("pct")
            points = change.get("points")
            show = change.get("show")

            # Whether a fall counts as severe is judged in the unit the change
            # is stated in. -15% off a total and -5 points off a conversion
            # rate are two different thresholds, and testing either against the
            # other's number would be meaningless.
            if show == _pd.POINTS:
                severe = points is not None and points < _pd.SEVERE_DROP_POINTS
            else:
                severe = pct is not None and pct < _pd.SEVERE_DROP_PCT

            if direction > 0:
                color, arrow = STATUS["good"], "↑"
            elif direction == 0:
                # A wobble inside the neutral band is not a trend. Colouring it
                # amber, as this did for every drop of 0 to -10%, taught the
                # reader that the colours mean nothing.
                color, arrow = "#6b7280", "→"
            elif severe:
                color, arrow = STATUS["bad"], "↓"
            else:
                color, arrow = STATUS["warn"], "↓"

            if show == _pd.POINTS and points is not None:
                # Percentage POINTS, and the card says so. The alternative -- a
                # percent change of a percentage -- turns close_rate moving
                # 7,4% to 9,7% into "+31%", which reads as a mission
                # transformed and means about two more invitations per hundred
                # lessons. See period_delta.point_delta.
                # "pp" is right for a rate on the 0-100 scale and wrong for
                # anything else measured in unscaled points — the effort score
                # moves on a 1-3 scale, where "0,2 pp" would claim a percentage
                # nobody computed. points_unit lets such a card drop the suffix
                # and print the move in the card's own decimals.
                points_unit = m.get("points_unit", "pp")
                if points_unit == "pp":
                    text = t("{n} pp", n=fmt_number(abs(points), 1))
                else:
                    text = f"{fmt_number(abs(points), decimals)}{points_unit}"
            elif show == _pd.ABSOLUTE and change.get("change") is not None:
                n = round(float(change["change"]))
                text = f"{'+' if n > 0 else ''}{fmt_int(n)}"
            elif pct is not None:
                text = f"{fmt_int(abs(pct))}%"
            else:
                text = ""

            if text:
                delta_html = (
                    f'<div style="font-size:0.78rem;color:{color};font-weight:600;'
                    f'margin-top:4px;">{arrow} {_html.escape(text)} {delta_label}</div>'
                )

        # A comparison this page REFUSES to make — too few reporting areas or
        # days behind the prior side — said on the card instead of in a
        # paragraph under the row (data-pages plan C2). A silently missing arrow
        # is audit finding M7; a paragraph explaining one is X4. The chip is the
        # third option: the fact on the card, the arithmetic on hover, and the
        # section's ⓘ for the reader who cannot hover.
        if not delta_html and m.get("change_note"):
            note_title = m.get("change_note_title") or ""
            title_attr = f' title="{_html.escape(str(note_title))}"' if note_title else ""
            delta_html = (
                f'<div class="pmg-kpi-nochange"{title_attr} '
                f'style="font-size:0.78rem;color:#6b7280;font-weight:600;'
                f'margin-top:4px;">→ {_html.escape(str(m["change_note"]))}</div>'
            )

        # "note" is a caption in the card's own right, for a card with no goal
        # bar to hang one under. The effort section's cards are percentages of
        # all possible area-days, and the count they came from ("143 de 301")
        # is what stops a share reading as a total.
        note_text = _html.escape(m.get("note", ""))
        card_note_html = (
            f'<div style="font-size:0.7rem;color:#9aa0ad;margin-top:4px;">{note_text}</div>'
            if note_text else ""
        )

        spark_html = sparkline_svg(m.get("spark"))

        goal_html = ""
        if goal is not None and float(goal) > 0:
            # pct is the TRUE ratio and can exceed 100; only the bar's width is
            # clamped. Capping the caption too made a goal set far too low read
            # exactly like one that was met precisely -- member_contacts sat at
            # 196% of its configured goal and displayed "100%", so nothing on
            # screen suggested the number needed recalibrating.
            # A non-numeric value is a metric with no reading yet (the weekly
            # form has not arrived), NOT a metric sitting at zero. Those tiles
            # show the goal on its own: "0% of 104" would report a failure the
            # mission has not had the chance to have.
            #
            # value_basis / goal_basis: how many areas are behind each side.
            # When they differ, a total-over-total ratio is meaningless — on
            # 2026-08-21 the week ending 08-16 had 33 areas' results (204 new
            # people) over 1 area's goal (10), and the tile read 2.040%. Reduce
            # both to a per-area rate first and the mismatched denominators
            # cancel: 6.2 against 10, i.e. 62%. Same rule the audit already sets
            # for zones, for the same reason. In the steady state the two bases
            # are equal and this is identical to the plain ratio, so it costs
            # nothing and only ever rescues the mismatched case.
            v_basis = m.get("value_basis")
            g_basis = m.get("goal_basis")
            pace = m.get("pace")
            state = goal_bar_state(value, goal, pace=pace,
                                   value_basis=v_basis, goal_basis=g_basis)
            measured = state["measured"]
            per_area = state["per_area"]
            v_rate, g_rate = state["v_rate"], state["g_rate"]
            pct, width = state["pct"], state["width"]
            bar = goal_bar_color(state["grade_pct"])

            # A goal is normally a whole number even on a card that prints
            # decimals -- the rate targets are 50, 20, 25 -- and "50,0%" under
            # "46,4%" is a decimal that carries no information.
            try:
                goal_places = 0 if float(goal) == int(float(goal)) else decimals
            except (TypeError, ValueError):
                goal_places = decimals
            goal_text = _card_number(goal, goal_places)

            # The one caption line. Everything else goes in `details`.
            details: list[str] = []
            if not measured:
                caption = t("Goal: {goal}", goal=goal_text)
            else:
                caption = t("{pct}% of {goal}", pct=fmt_int(pct), goal=goal_text)
                day, days = m.get("day"), m.get("days")
                if state["tick"] is not None:
                    # An in-progress period is judged against where it should
                    # be TODAY. The caption says how far through the period we
                    # are; the details say what that means in the goal's units.
                    if day is not None and days:
                        caption += " · " + t("day {n}/{m}", n=fmt_int(day),
                                             m=fmt_int(days))
                    else:
                        caption += " · " + t("{pace} expected by today",
                                             pace=_card_number(pace, 0))
                    details.append(
                        t("{value} of {pace} expected by today",
                          value=_card_number(value, goal_places),
                          pace=_card_number(pace, 0)))
                    if m.get("goal_by"):
                        details.append(t("full goal {goal} by {date}",
                                         goal=goal_text,
                                         date=str(m.get("goal_by"))))
                if per_area:
                    # The per-area pair: the tile's own big number is a mission
                    # TOTAL, so without these two figures the percentage has no
                    # visible arithmetic behind it.
                    details.append(t("{actual} vs {goal} per area",
                                     actual=fmt_number(v_rate, 1),
                                     goal=fmt_number(g_rate, 1)))
            # Where a goal is derived rather than entered -- a per-area weekly
            # target multiplied by the active area count -- the total alone is
            # unexplainable on screen; goal_note carries the arithmetic.
            if m.get("goal_note"):
                details.append(str(m["goal_note"]))
            proj_text = projection_caption(m.get("projection"), _card_number)
            if proj_text:
                details.append(proj_text)
            if m.get("details"):
                details.append(str(m["details"]))
            details_attr = (
                f' title="{_html.escape(" · ".join(details))}"' if details else ""
            )

            # The pace mark. overflow:hidden on the track would clip an
            # absolutely-positioned child, so the ticks live in a wrapper
            # OUTSIDE the clipping box and the track keeps its rounded fill.
            tick_html = (
                f'<div style="position:absolute;left:{state["tick"]}%;top:-2px;'
                f'width:2px;height:7px;background:rgba(244,244,248,0.85);'
                f'border-radius:1px;"></div>'
                if state["tick"] is not None else ""
            )
            # The leadership mark (decision 6): a second tick, in a colour that
            # is neither a grade nor the pace, with its name on hover.
            mark = m.get("mark")
            mark_html = ""
            try:
                if mark is not None and float(mark) > 0:
                    mark_pos = max(0, min(100, round(float(mark) / float(goal) * 100)))
                    mark_label = m.get("mark_label") or t("Leadership goal")
                    mark_title = f"{mark_label}: {_card_number(mark, goal_places)}"
                    mark_html = (
                        f'<div class="pmg-kpi-mark" title="{_html.escape(mark_title)}" '
                        f'style="position:absolute;left:{mark_pos}%;top:-3px;'
                        f'width:2px;height:9px;background:{_MARK_COLOR};'
                        f'border-radius:1px;"></div>'
                    )
            except (TypeError, ValueError, ZeroDivisionError):
                mark_html = ""
            goal_html = (
                f'<div style="margin-top:8px;">'
                f'<div style="position:relative;">'
                f'<div style="height:3px;background:rgba(255,255,255,0.08);'
                f'border-radius:2px;overflow:hidden;">'
                f'<div style="height:100%;width:{width}%;background:{bar};'
                f'border-radius:2px;transition:width 0.4s ease;"></div></div>'
                f'{tick_html}{mark_html}</div>'
                f'<div class="pmg-kpi-cap"{details_attr} '
                f'style="font-size:0.7rem;color:#9aa0ad;margin-top:4px;">'
                f'{_html.escape(caption)}'
                f'</div></div>'
            )

        expectation_html = ""
        if expectation is not None and float(expectation) > 0:
            try:
                exp_pct = min(100, round(float(value) / float(expectation) * 100))
            except (TypeError, ZeroDivisionError, ValueError):
                exp_pct = 0
            expectation_html = (
                f'<div style="margin-top:6px;">'
                f'<div style="height:3px;background:rgba(255,255,255,0.08);'
                f'border-radius:2px;overflow:hidden;">'
                f'<div style="height:100%;width:{exp_pct}%;background:#8b5cf6;'
                f'border-radius:2px;transition:width 0.4s ease;"></div></div>'
                f'<div class="pmg-kpi-exp" style="font-size:0.7rem;color:#9aa0ad;margin-top:4px;">'
                f'{_html.escape(t("{pct}% of {expectation} expectation", pct=fmt_int(exp_pct), expectation=fmt_int(expectation)))}'
                f'</div></div>'
            )

        # fmt_int, not f"{int(value):,}": that hardcoded the anglo thousands
        # separator into the largest number on the page, so a Spanish-language
        # dashboard showed "1,234" where Chile writes "1.234" — and to a
        # Chilean reader "1,234" is one point two three four, not one thousand.
        # int() also truncated floats, and a None value rendered as the literal
        # text "None"; fmt_int rounds and renders None as an em dash.
        fmt = (_card_number(value) if isinstance(value, (int, float))
               else _html.escape(str(value)))
        body = (
            f'<div class="pmg-kpi-label" style="font-size:0.72rem;font-weight:600;'
            f'color:#9ca3af;line-height:1.2;min-height:2.4em;margin-bottom:6px;">{label}</div>'
            f'<div class="pmg-kpi-value" style="font-size:1.9rem;font-weight:800;color:#f4f4f8;'
            f'letter-spacing:-0.03em;line-height:1;font-variant-numeric:tabular-nums;">{fmt}</div>'
            f'{delta_html}{card_note_html}{spark_html}{goal_html}{expectation_html}'
        )
        href = m.get("href")
        if href:
            # The whole card is the link. target=_self: a query-string link on
            # the page itself must not open a second tab.
            cards += (
                f'<a class="pmg-kpi pmg-kpi-link" href="{_html.escape(str(href))}" '
                f'target="_self" style="{_CARD_STYLE}">{body}</a>'
            )
        else:
            cards += f'<div class="pmg-kpi" style="{_CARD_STYLE}">{body}</div>'

    st.markdown(f'<div class="pmg-kpi-grid" style="{_GRID_STYLE}">{cards}</div>', unsafe_allow_html=True)


#: Section numbering state. Two keys, both reset by the router at the top of
#: every full script run (see reset_section_numbering):
#:   _ds_section_count   how many numbers have been handed out on this page
#:   _ds_section_numbers label text -> the number it was given
#:
#: The label->number map exists for FRAGMENT reruns. Desgloses renders sections
#: inside an @st.fragment, and a fragment rerun re-executes only that body —
#: the router never runs, so the counter is never reset. Looking the label up
#: means a section keeps the number it was first drawn with instead of
#: climbing every time the user changes scope.
_SECTION_COUNT_KEY = "_ds_section_count"
_SECTION_NUMBERS_KEY = "_ds_section_numbers"

#: ①-⑳. Past twenty, fall back to a plain digit rather than reaching for the
#: ㉑-㊿ block, which is missing from many of the fonts in the app's stack and
#: would render as a box. The longest page today has sixteen sections.
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def reset_section_numbering() -> None:
    """Start section numbers over at ①. Called once per full run by Home.py,
    before the selected page executes."""
    st.session_state[_SECTION_COUNT_KEY] = 0
    st.session_state[_SECTION_NUMBERS_KEY] = {}


def _section_marker(text: str) -> str:
    """The circled number for this section, as an HTML span."""
    numbers = st.session_state.setdefault(_SECTION_NUMBERS_KEY, {})
    if text in numbers:
        n = numbers[text]
    else:
        n = st.session_state.get(_SECTION_COUNT_KEY, 0) + 1
        st.session_state[_SECTION_COUNT_KEY] = n
        numbers[text] = n
    glyph = _CIRCLED[n - 1] if n <= len(_CIRCLED) else str(n)
    return (f'<span style="color:#818cf8;font-weight:700;flex:none;'
            f'font-size:0.95rem;line-height:1;">{glyph}</span>')


def render_section_label(text: str, *, emphasis: bool = False,
                         numbered: bool = False, info: str | None = None,
                         right: str | None = None) -> None:
    """Small uppercase label with an extending horizontal rule — the one
    heading idiom between content sections.

    Two tiers. The base tier (#9ca3af at 0.8rem, 7.9:1 on the app background)
    is every section; ``emphasis=True`` is brighter, larger and carries a
    short indigo accent bar, for labels that must read as a page's primary
    groupings (Goals' area-type categories — Carson, 2026-07-19 and
    2026-07-22). Both are uppercase-with-rule so they stay one visual family.

    ``info`` renders an ⓘ beside the label; clicking the label line toggles a
    muted paragraph beneath it (a pure-CSS <details>, so no rerun). This is
    where a section's explanation lives — the one place, instead of a caption
    under every card (data-pages plan A4, audit X4). ``right`` renders a muted
    string at the label's right edge: the period, the coverage. It wraps, and
    drops to its own row under the label when the two cannot share one.

    ``numbered=True`` prefixes the circled number the page hands out in render
    order (①②③…). Numbers were the DEFAULT until 2026-09-18: the Panel was
    twelve sections over ten screens and they were its only wayfinding
    (AUDIT-IA-2026-08-22.md). The redesign cut the Panel to five sections and
    retired the numbers; the machinery stays for any page that asks.
    """
    marker = _section_marker(text) if numbered else ""
    label = _html.escape(text)
    # The right-hand line wraps, and takes its own row under the label when the
    # two cannot share one. It carries a window and a coverage count ("cambio
    # 2026-6 · semana 2 de 6 · 39 de 45 areas informaron"), which at 375px is
    # wider than the pane on its own; nowrap made the main pane scroll sideways
    # (PLAN STATUS, B3 note a). margin-left:auto keeps it at the right edge on
    # whichever row it lands on.
    right_html = (
        f'<span style="flex:0 1 auto;margin-left:auto;text-align:right;'
        f'color:#6b7280;font-size:0.75rem;font-weight:500;'
        f'letter-spacing:0;text-transform:none;white-space:normal;">'
        f'{_html.escape(right)}</span>' if right else ""
    )
    info_glyph = (
        f'<span class="pmg-info" title="{_html.escape(t("More about this section"))}" '
        f'style="flex:none;display:inline-flex;align-items:center;justify-content:center;'
        f'width:1rem;height:1rem;border-radius:50%;border:1px solid rgba(255,255,255,0.28);'
        f'color:#9aa0ad;font-size:0.65rem;font-weight:700;letter-spacing:0;'
        f'text-transform:none;line-height:1;cursor:pointer;">i</span>' if info else ""
    )
    if emphasis:
        row = (
            f'<span style="width:5px;height:1.4rem;border-radius:2px;flex:none;'
            f'background:linear-gradient(180deg,#6366f1,#8b5cf6);"></span>'
            f'{marker}'
            f'<span style="font-size:1.05rem;font-weight:800;letter-spacing:0.12em;'
            f'color:#f4f4f8;text-transform:uppercase;white-space:nowrap;">{label}</span>'
            f'{info_glyph}'
            f'<div style="flex:1;height:1px;background:rgba(99,102,241,0.35);"></div>'
            f'{right_html}'
        )
        row_style = ("display:flex;flex-wrap:wrap;align-items:center;gap:0.75rem;"
                     "margin:2rem 0 0.9rem 0;")
    else:
        row = (
            f'{marker}'
            f'<span style="font-size:0.8rem;font-weight:700;letter-spacing:0.12em;'
            f'color:#9ca3af;text-transform:uppercase;white-space:nowrap;">{label}</span>'
            f'{info_glyph}'
            f'<div style="flex:1;height:1px;background:rgba(255,255,255,0.07);"></div>'
            f'{right_html}'
        )
        row_style = ("display:flex;flex-wrap:wrap;align-items:center;gap:0.6rem;"
                     "margin:1.5rem 0 0.75rem 0;")

    if info:
        # The whole label line is the <summary>, so the ⓘ needs no script; the
        # paragraph opens beneath the rule, full width.
        html = (
            f'<details class="pmg-sec">'
            f'<summary style="{row_style}list-style:none;cursor:pointer;">{row}</summary>'
            f'<p class="pmg-sec-info" style="margin:-0.25rem 0 0.9rem 0;font-size:0.8rem;'
            f'line-height:1.45;color:#9aa0ad;max-width:70ch;">{_html.escape(info)}</p>'
            f'</details>'
        )
    else:
        html = f'<div class="pmg-sec" style="{row_style}">{row}</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_section_tabs(options: dict, *, key: str, per_row: int = 5) -> str:
    """The app's one sub-navigation control. Returns the active option's id.

    ``options`` maps a STABLE id to its display label:

        active = render_section_tabs(
            {"scores": t("Scores"), "daily": t("Daily Activity")},
            key="scores_section")

    Ids are what gets stored, so a mid-session language switch cannot strand a
    Spanish label in an English option list — the same stable-id discipline the
    section-tab translations already run on.

    WHY THIS SHAPE, AND NOT ONE OF THE FOUR IT REPLACED
    The app had five sub-navigation idioms (AUDIT-IA-2026-08-22.md step 1.7).
    They are not interchangeable:

    * ``st.tabs`` renders EVERY tab's body on every script run — on this app
      that means every hidden section's queries fire too — and has no
      server-side memory of which tab is active, so any widget inside it snaps
      the view back to the first tab on rerun. Metas, Traslados and
      Mantenimiento each discovered this independently and each left it.
    * ``st.segmented_control`` renders inside a flex row carrying
      ``max-width: fit-content`` and refuses to fill the width: measured live,
      a 780px row with two flex-grow:1 children whose buttons stayed 167px.
    * ``st.radio`` + a CSS block that repaints radios as tabs works, but the
      block was copy-pasted verbatim between Metas and Traslados, and it
      depends on Streamlit's internal ``st-key-`` class names.

    Real buttons in real columns fill their share by construction, only the
    active section's body runs, and the state is a plain session value nothing
    else owns.

    ``key`` should not reuse a name that was previously a WIDGET key on the
    same page. This is a plain session value, and Streamlit keeps a retired
    widget's own cached state under its key; the Panel hit that collision when
    it replaced an st.segmented_control and deliberately moved to a new name
    (see its `panel_rank_scope_val` comment). Every page migrated here follows
    that precedent with a fresh ``*_section_val`` name, as a precaution rather
    than in response to an observed failure.

    The selected state is drawn here rather than left to ``type="primary"``
    because this design system sets ``background`` on ``.stButton > button``
    with ``!important``, which flattens Streamlit's own primary styling — both
    halves would render identically and nothing would look selected.
    """
    ids = list(options)
    if not ids:
        return ""
    if key not in st.session_state or st.session_state[key] not in ids:
        st.session_state[key] = ids[0]

    active = st.session_state[key]

    # Keyed on the ACTIVE button's own st-key- class, which is known before any
    # button is drawn.
    #
    # The suffix is the option's INDEX, not its id. Streamlit turns a widget
    # key into a CSS class by replacing everything non-alphanumeric with "-",
    # so an id like "✅ To-Do & Health" or "Area Goal Customization" produced a
    # selector that matched nothing and left every button looking unselected —
    # measured live on Mantenimiento, five buttons, none highlighted. An index
    # is CSS-safe by construction, and the id stays what gets stored.
    active_idx = ids.index(active)
    st.markdown(
        f"""
        <style>
        div[class*="st-key-{key}__{active_idx}"] button {{
            background: linear-gradient(135deg, rgba(99,102,241,0.28),
                                        rgba(139,92,246,0.28)) !important;
            border: 1px solid rgba(99,102,241,0.70) !important;
            box-shadow: 0 0 14px rgba(99,102,241,0.28) !important;
        }}
        div[class*="st-key-{key}__{active_idx}"] button p {{
            color: #ffffff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Wrapped past `per_row` so a page with many sections gets a second row of
    # readable buttons rather than one row of unreadably narrow ones.
    for start in range(0, len(ids), per_row):
        chunk = ids[start:start + per_row]
        cols = st.columns(per_row)
        for offset, (col, opt) in enumerate(zip(cols, chunk)):
            with col:
                if st.button(
                    options[opt],
                    key=f"{key}__{start + offset}",
                    use_container_width=True,
                    type=("primary" if st.session_state[key] == opt
                          else "secondary"),
                ):
                    st.session_state[key] = opt
                    # Rerun rather than falling through: `type=` for every
                    # button was evaluated from the OLD value earlier in this
                    # same run, so without this the body would switch while the
                    # highlight stayed put until the next interaction.
                    st.rerun()

    return active


def render_table(data, *, index: bool = False, align_first_left: bool = True) -> None:
    """Render a DataFrame or pandas Styler as a themed HTML table.

    Streamlit's st.dataframe uses a canvas-based glide-data-grid that ignores the
    design-system CSS and frequently paints blank in this dark-glass theme. This
    helper emits a real HTML <table> the CSS in ``_CSS`` (.pmg-tbl) fully controls,
    so tables always render and match the rest of the app.

    Accepts a pandas DataFrame or a Styler. For a Styler, the caller's formatting
    is preserved; the index is hidden unless ``index=True``.
    """
    import pandas as pd  # local import keeps module import light

    styler_cls = getattr(getattr(pd.io, "formats", None), "style", None)
    is_styler = styler_cls is not None and isinstance(data, styler_cls.Styler)

    if is_styler:
        try:
            html_table = data.hide(axis="index").to_html() if not index else data.to_html()
        except Exception:
            # Older/newer pandas API differences — fall back to raw render
            html_table = data.to_html()
    else:
        html_table = data.to_html(index=index, escape=True, border=0, na_rep="—")

    cls = "pmg-tbl" + ("" if align_first_left else " pmg-tbl-center")
    st.markdown(f'<div class="{cls}">{html_table}</div>', unsafe_allow_html=True)


def render_status_pill(text: str, color: str = "blue") -> None:
    """Inline glass pill badge. Colors: blue, green, amber, red, purple."""
    bg, border, fg = _PILL_COLORS.get(color, _PILL_COLORS["blue"])
    st.markdown(
        f'<span style="display:inline-flex;align-items:center;background:{bg};'
        f'border:1px solid {border};color:{fg};border-radius:999px;'
        f'padding:0.2rem 0.65rem;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.06em;">{_html.escape(text)}</span>',
        unsafe_allow_html=True,
    )


def render_companionship_card(area_row, zone: str = "", district: str = "") -> None:
    """Glass info card for one area's companionship: each companion's name
    (+ email where MISSION_ORG has one — Companion1/2 only, Companion3/4
    never have an email column by this mission's convention), a dim
    zone · district · language line, and leadership role pills (ZL/STL/DL/AP)
    when the area's flags are set.

    `area_row` is one MISSION_ORG row (a pandas Series — e.g.
    `get_submitting_areas()` filtered to the selected Area_Name, `.iloc[0]`).

    Sole implementation of this card: views/02_Metas.py and the Breakdowns
    page's area view both call it. (The old 05_Area_Breakdown.py carried a
    duplicate inline copy of this markup; combining the breakdown pages
    retired that copy, so there is no longer a second version to keep in sync.)
    """
    c1_name  = str(area_row.get("Companion1_Name",  "") or "")
    c1_email = str(area_row.get("Companion1_Email", "") or "")
    c2_name  = str(area_row.get("Companion2_Name",  "") or "")
    c2_email = str(area_row.get("Companion2_Email", "") or "")
    c3_name  = str(area_row.get("Companion3_Name",  "") or "")
    c4_name  = str(area_row.get("Companion4_Name",  "") or "")
    lang     = str(area_row.get("Language_Type",    "") or "")

    companions_html = ""
    for name, email in [(c1_name, c1_email), (c2_name, c2_email), (c3_name, ""), (c4_name, "")]:
        if name or email:
            companions_html += (
                f'<div style="margin-bottom:0.3rem;">'
                f'<strong style="color:#f4f4f8;">{_html.escape(name)}</strong>'
                + (f' <span style="color:#9ca3af;font-size:0.82rem;">· {_html.escape(email)}</span>' if email else "")
                + "</div>"
            )

    role_pills = ""
    for flag, label in [("Is_ZL", "ZL"), ("Is_STL", "STL"), ("Is_DL", "DL"), ("Is_AP", "AP")]:
        val = str(area_row.get(flag, "") or "").upper()
        if val in ("TRUE", "1", "YES"):
            role_pills += (
                f'<span style="background:rgba(99,102,241,0.2);color:#a5b4fc;'
                f'padding:2px 8px;border-radius:999px;font-size:0.72rem;'
                f'font-weight:600;margin-right:4px;">{label}</span>'
            )

    meta_bits = [b for b in (zone, district, lang) if b]
    meta_line = " · ".join(_html.escape(b) for b in meta_bits)
    role_section = (f'<div style="margin-top:0.5rem;">{role_pills}</div>') if role_pills else ""
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:12px;padding:1rem 1.25rem;margin-bottom:1rem;">'
        f'{companions_html}'
        f'<div style="color:#9ca3af;font-size:0.8rem;margin-top:0.5rem;">{meta_line}</div>'
        f'{role_section}'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_language_switch(key: str) -> None:
    """Language selector. Rendered at the top of Home and mirrored in the
    sidebar so the choice can be changed from any page.

    Home and the sidebar render this same control under two different keys,
    so each has its own independently stored widget value. They stay in
    agreement because `index` is recomputed from the active language on every
    run and Streamlit treats a widget's parameters as part of its identity:
    changing `index` re-creates the untouched mirror with the corrected
    default instead of leaving it reporting the old language. Verified, not
    assumed - test_mirrored_switches_agree_after_one_is_changed pins it, since
    a Streamlit upgrade that changed that identity rule would otherwise leave
    the two mirrors driving each other in an endless rerun.
    """
    from app.i18n import get_lang, set_lang

    options = {"English": "en", "Español": "es"}
    labels = list(options)
    current = get_lang()
    index = 1 if current == "es" else 0

    chosen = st.radio(
        t("Language / Idioma"),
        labels,
        index=index,
        horizontal=True,
        key=key,
        label_visibility="collapsed",
    )
    if options[chosen] != current:
        set_lang(options[chosen])
        st.rerun()


def render_sidebar(user: dict) -> None:
    """Render consistent sidebar: user name + email at top, Sign Out button
    below divider. Also renders the leadership Action Center bell (see
    _render_action_bell) — called here, not per-page, since every page
    already calls render_sidebar(user)."""
    _render_action_bell(user)
    with st.sidebar:
        render_language_switch("ds_lang_sidebar")
        name = _html.escape(user.get("name", user.get("email", "")))
        email = _html.escape(user.get("email", ""))
        st.markdown(
            f'<div style="padding:0.5rem 0 0.75rem 0;">'
            f'<div style="font-weight:700;font-size:0.95rem;color:#f4f4f8;">{name}</div>'
            f'<div style="font-size:0.72rem;color:#6b7280;margin-top:2px;">{email}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        if st.button(t("Sign Out"), use_container_width=True, key="ds_signout"):
            from app.auth.auth import clear_session
            clear_session()
            st.rerun()


def _render_action_bell(user: dict) -> None:
    """Fixed-position bell badge, top-right of every page, leadership only.
    Links to the Action Center page; the count is the total open items
    across suggestions/follow-ups/tasks/maintenance."""
    from app.auth.auth import is_leadership
    email = user.get("email", "")
    if not is_leadership(email):
        return
    from app.db.action_center_queries import get_action_center_summary
    try:
        total = get_action_center_summary(email).get("total", 0)
    except Exception:
        total = 0
    pill = (
        f'<span style="background:#ef4444;color:#fff;border-radius:999px;'
        f'padding:0.05rem 0.4rem;font-size:0.68rem;font-weight:700;'
        f'margin-left:0.35rem;">{total}</span>'
        if total > 0 else ""
    )
    # B5 (AUDIT-IA-2026-08-22.md): this pointed at /Action_Center, which does
    # not exist — the real page is views/17_Centro_de_Acción.py, so Streamlit
    # silently served Home instead of the Action Center on every click.
    # Streamlit derives a page's URL from its filename stem verbatim
    # (source_util.page_icon_and_name / navigation/page.py's inferred_name) —
    # no ASCII transliteration — so the path keeps the accent.
    st.markdown(
        f'<a href="/Centro_de_Acción" target="_self" style="position:fixed;'
        f'top:0.75rem;right:1.25rem;z-index:999;text-decoration:none;'
        f'background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.14);'
        f'border-radius:999px;padding:0.3rem 0.7rem;font-size:0.95rem;'
        f'display:inline-flex;align-items:center;color:#f4f4f8;">🔔{pill}</a>',
        unsafe_allow_html=True,
    )
