"""app/components/design_system.py — single source of visual design."""
from __future__ import annotations

import html as _html
import streamlit as st
import plotly.io as pio
import plotly.graph_objects as go
from app.i18n import t
from app.i18n.formats import fmt_int

PALETTE = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"]

_CSS = """
<style>
.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
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
[data-testid="stSidebarNavLink"] span {
    text-transform: capitalize !important;
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
            colorway=PALETTE,
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


def inject_global_css() -> None:
    """Inject design system CSS. Call once per page after require_auth()."""
    st.markdown(_CSS, unsafe_allow_html=True)
    _register_plotly_template()
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


def render_kpi_row(metrics: list[dict]) -> None:
    """
    Render a horizontal row of glass KPI cards using a single st.markdown HTML block.

    Each dict keys: label (str), value (int|float|str), delta (optional int/float pct),
    delta_label (optional str), goal (optional int/float — shows a progress bar,
    color-graded green/indigo/amber by how close value is to it), expectation
    (optional int/float — shows a SECOND progress bar underneath the goal one, for
    the area-type expectation reference instead of the set goal). The expectation
    bar is deliberately styled distinct from the goal bar (Carson, 2026-07-24: the
    two must read as clearly different things, not two goal bars) — fixed violet
    #8b5cf6 rather than performance-graded, and its caption says "expectation" not
    "goal", so the difference doesn't rely on color alone.
    Delta colors: green >0, amber -10..0, red <=-10.
    """
    cards = ""
    for m in metrics:
        label = _html.escape(m.get("label", ""))
        value = m.get("value", 0)
        delta = m.get("delta")
        delta_label = _html.escape(m.get("delta_label", ""))
        goal = m.get("goal")
        expectation = m.get("expectation")

        delta_html = ""
        if delta is not None:
            if delta > 0:
                color, arrow = "#22c55e", "↑"
            elif delta > -10:
                color, arrow = "#f59e0b", "↓"
            else:
                color, arrow = "#ef4444", "↓"
            delta_html = (
                f'<div style="font-size:0.78rem;color:{color};font-weight:600;'
                f'margin-top:4px;">{arrow} {abs(delta)}% {delta_label}</div>'
            )

        goal_html = ""
        if goal is not None and float(goal) > 0:
            try:
                pct = min(100, round(float(value) / float(goal) * 100))
            except (TypeError, ZeroDivisionError, ValueError):
                pct = 0
            bar = "#22c55e" if pct >= 90 else "#6366f1" if pct >= 60 else "#f59e0b"
            goal_html = (
                f'<div style="margin-top:8px;">'
                f'<div style="height:3px;background:rgba(255,255,255,0.08);'
                f'border-radius:2px;overflow:hidden;">'
                f'<div style="height:100%;width:{pct}%;background:{bar};'
                f'border-radius:2px;transition:width 0.4s ease;"></div></div>'
                f'<div style="font-size:0.65rem;color:#4b5563;margin-top:3px;">'
                f'{_html.escape(t("{pct}% of {goal} goal", pct=fmt_int(pct), goal=fmt_int(goal)))}'
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
                f'<div style="font-size:0.65rem;color:#4b5563;margin-top:3px;">'
                f'{_html.escape(t("{pct}% of {expectation} expectation", pct=fmt_int(exp_pct), expectation=fmt_int(expectation)))}'
                f'</div></div>'
            )

        # fmt_int, not f"{int(value):,}": that hardcoded the anglo thousands
        # separator into the largest number on the page, so a Spanish-language
        # dashboard showed "1,234" where Chile writes "1.234" — and to a
        # Chilean reader "1,234" is one point two three four, not one thousand.
        # int() also truncated floats, and a None value rendered as the literal
        # text "None"; fmt_int rounds and renders None as an em dash.
        fmt = (fmt_int(value) if isinstance(value, (int, float))
               else _html.escape(str(value)))
        cards += (
            f'<div style="background:rgba(255,255,255,0.04);'
            f'backdrop-filter:blur(12px) saturate(150%);'
            f'border:1px solid rgba(255,255,255,0.08);border-radius:12px;'
            f'padding:1rem 1.1rem;flex:1;min-width:0;transition:all 0.2s ease;">'
            f'<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.1em;'
            f'color:#6b7280;text-transform:uppercase;margin-bottom:6px;">{label}</div>'
            f'<div style="font-size:2rem;font-weight:800;color:#f4f4f8;'
            f'letter-spacing:-0.03em;line-height:1;font-variant-numeric:tabular-nums;">'
            f'{fmt}</div>{delta_html}{goal_html}{expectation_html}</div>'
        )

    st.markdown(
        f'<div style="display:flex;gap:0.75rem;margin-bottom:1.5rem;">{cards}</div>',
        unsafe_allow_html=True,
    )


def render_section_label(text: str, *, emphasis: bool = False) -> None:
    """Small uppercase label with extending horizontal rule — use between content sections.

    ``emphasis=True`` is a stronger tier of the same pattern for labels that
    must read as the page's primary groupings (e.g. each category on Goals >
    Area Expectation Settings — Carson, 2026-07-19: "make it more obvious
    what section is english and what not ... but still in theme"): brighter
    text, larger size, and a short indigo accent bar (the app's primary
    #6366f1→#8b5cf6 gradient), still uppercase-with-rule so it stays the
    same visual family rather than a competing heading style. Bumped again
    2026-07-22 (Carson: "make the title of the area type bigger so it is
    more noticeable") — font-size 0.85rem → 1.05rem, accent bar scaled to
    match; only caller is the Area Expectation Settings category loop, so
    this doesn't touch any other page.
    """
    if emphasis:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:0.75rem;'
            f'margin:2rem 0 0.9rem 0;">'
            f'<span style="width:5px;height:1.4rem;border-radius:2px;flex:none;'
            f'background:linear-gradient(180deg,#6366f1,#8b5cf6);"></span>'
            f'<span style="font-size:1.05rem;font-weight:800;letter-spacing:0.12em;'
            f'color:#f4f4f8;text-transform:uppercase;white-space:nowrap;">{_html.escape(text)}</span>'
            f'<div style="flex:1;height:1px;background:rgba(99,102,241,0.35);"></div></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0.75rem;'
        f'margin:1.5rem 0 0.75rem 0;">'
        f'<span style="font-size:0.65rem;font-weight:700;letter-spacing:0.14em;'
        f'color:#6b7280;text-transform:uppercase;white-space:nowrap;">{_html.escape(text)}</span>'
        f'<div style="flex:1;height:1px;background:rgba(255,255,255,0.07);"></div></div>',
        unsafe_allow_html=True,
    )


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

    Sole implementation of this card: pages/02_Metas.py and the Breakdowns
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
    st.markdown(
        f'<a href="/Action_Center" target="_self" style="position:fixed;'
        f'top:0.75rem;right:1.25rem;z-index:999;text-decoration:none;'
        f'background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.14);'
        f'border-radius:999px;padding:0.3rem 0.7rem;font-size:0.95rem;'
        f'display:inline-flex;align-items:center;color:#f4f4f8;">🔔{pill}</a>',
        unsafe_allow_html=True,
    )
