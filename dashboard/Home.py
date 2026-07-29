import html
import streamlit as st
from app.auth.auth import require_auth
from app.components.design_system import inject_global_css, render_page_header, render_section_label, render_sidebar
from app.db.queries import get_meta, get_config_value
from app.i18n import t
from app.chat.gemini_chat import (
    load_kb_context,
    load_live_data_context,
    load_supplemental_contexts,
    ask_gemini,
    GeminiRateLimitError,
    GeminiError,
)

st.set_page_config(
    page_title="CCSM · PMG Compass",
    page_icon="C",
    layout="wide",
)

# ── Auth and design system ────────────────────────────────────────────────────
user = require_auth()
inject_global_css()
render_sidebar(user)

# ── Chat-specific CSS enhancements ────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stChatMessage"] {
    padding: 0.85rem 1rem !important;
    margin-bottom: 0.35rem !important;
}

/* Reload / Clear buttons */
[data-testid="stBaseButton-secondary"] {
    background: rgba(255,255,255,0.06) !important;
    color: #e5e7eb !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background: rgba(99,102,241,0.18) !important;
    border-color: rgba(99,102,241,0.45) !important;
    color: #a5b4fc !important;
}

/* Send button (form submit) */
[data-testid="stBaseButton-secondaryFormSubmit"] {
    background: rgba(99,102,241,0.85) !important;
    color: #ffffff !important;
    border: 1px solid rgba(99,102,241,0.6) !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.03em !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background: #6366f1 !important;
    box-shadow: 0 4px 14px rgba(99,102,241,0.35) !important;
    transform: translateY(-1px) !important;
}

/* Chat text input — single source of truth: black text on white field */
[data-testid="stTextInputRootElement"] > div {
    background: #ffffff !important;
    border: 1px solid rgba(0,0,0,0.18) !important;
    border-radius: 8px !important;
}
[data-testid="stTextInputRootElement"] input {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    background: #ffffff !important;
    caret-color: #003087 !important;
}
[data-testid="stTextInputRootElement"] input::placeholder {
    color: #6b7280 !important;
    -webkit-text-fill-color: #6b7280 !important;
    opacity: 1 !important;
}
[data-testid="stTextInputRootElement"] > div:focus-within {
    border-color: rgba(0,48,135,0.55) !important;
    box-shadow: 0 0 0 3px rgba(0,48,135,0.12) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
from app.components.design_system import render_language_switch
render_language_switch("home_lang")

render_page_header(
    t("PMG Compass"),
    t("{mission} · Welcome back, {name}",
      mission=get_config_value("MISSION_NAME", t("Mission")),
      name=user.get("name", user.get("email", ""))),
    icon="",
)

# ── Status bar ────────────────────────────────────────────────────────────────
# Reporting weeks run Monday → Sunday. Compute from today's date so the range
# always displays even if DASHBOARD_SUMMARY meta is missing or stale.
from datetime import date, timedelta

_today      = date.today()
_week_start = _today - timedelta(days=_today.weekday())   # Monday
_week_end   = _week_start + timedelta(days=6)             # Sunday

def _fmt_short(d: date) -> str:
    return f"{d.month}/{d.day}/{d.strftime('%y')}"

meta = get_meta()
safe_start = html.escape(_fmt_short(_week_start))
safe_end   = html.escape(_fmt_short(_week_end))
safe_upd   = html.escape(meta.get("generated_at", ""))

status_parts = f"{t('Week')}&nbsp;&nbsp;{safe_start} → {safe_end}"
if safe_upd:
    status_parts += f"&nbsp;&nbsp;·&nbsp;&nbsp;{t('Last updated')}&nbsp;&nbsp;{safe_upd}"

st.markdown(
    f'<div style="display:inline-flex;align-items:center;gap:0.5rem;'
    f'background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.25);'
    f'border-radius:999px;padding:0.3rem 0.9rem;font-size:0.78rem;'
    f'color:#a5b4fc;margin-bottom:1.25rem;letter-spacing:0.01em;">'
    f'<span style="width:7px;height:7px;border-radius:50%;background:#22c55e;'
    f'flex-shrink:0;display:inline-block;"></span>{status_parts}</div>',
    unsafe_allow_html=True,
)

# ── App guide (folded in from the old Page Breakdown page) ────────────────────
with st.expander(t("App Guide — what each page does")):
    st.markdown(t("""
**Overview & assistant**
- **Home** — Mission Assistant. Ask natural-language questions about mission data, procedures, or performance.
- **Dashboard** — Mission pulse: weekly KPIs, submission compliance (with per-area detail), zone summary, and trend charts.
- **Goals** — Every area's progress against weekly and transfer goals, color-coded.

**Drill down (mission → zone → district → area)**
- **Breakdowns** — Zone, district, or area in one place: pick a zone for period comparisons and pipeline data, add a district to drill in, or pick an area for the single-area view (compliance calendar, anomaly flags, notes).

**Performance & analysis**
- **Scores** — Weekly composite Effort / Skill / KI / Effectiveness scores per area, with a configurable weight editor. Also has Daily Activity (day-by-day nightly-form explorer) and Analyze (anomaly detection + next-week projections) tabs.
- **Finding Funnel** — Upload Tableau exports to see the finding-to-baptism pipeline and area rankings.

**Operations**
- **Notes** — Area notes with tags, search, and email follow-up reminders.
- **Maintenance** — System health, weekly to-do, knowledge base, agent settings, and form-question configuration.
"""))

# ── Load KB and live data once per session ────────────────────────────────────
if "kb_context" not in st.session_state:
    with st.spinner(t("Loading knowledge base...")):
        st.session_state["kb_context"] = load_kb_context()

if "live_data_context" not in st.session_state:
    st.session_state["live_data_context"] = load_live_data_context()

if "supplemental_contexts" not in st.session_state:
    with st.spinner(t("Loading mission data...")):
        st.session_state["supplemental_contexts"] = load_supplemental_contexts()

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# ── Chat ──────────────────────────────────────────────────────────────────────
col_chat_header, col_chat_actions = st.columns([7, 2])
with col_chat_header:
    render_section_label(t("Mission Assistant"))
with col_chat_actions:
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button(t("Reload"), use_container_width=True, help=t("Refresh live mission data")):
            st.session_state.pop("live_data_context", None)
            st.session_state.pop("supplemental_contexts", None)
            st.session_state["live_data_context"] = load_live_data_context()
            st.session_state["supplemental_contexts"] = load_supplemental_contexts()
            st.rerun()
    with action_col2:
        if st.session_state["chat_history"]:
            if st.button(t("Clear"), use_container_width=True, help=t("Clear chat history")):
                st.session_state["chat_history"] = []
                st.rerun()

if not st.session_state.get("live_data_context"):
    st.warning(t("Live data unavailable — click **Reload** to retry."))

# Starter questions — shown only before the first message, for instant first-use
# value. Clicking one queues it as the next question.
_STARTERS = [
    t("Give me a 30-second briefing on the mission right now"),
    t("Which areas need my attention this week?"),
    t("Who are the top-performing areas right now?"),
    t("How is our baptism pipeline looking?"),
    t("Which zone is strongest at finding new people?"),
    t("Who hasn't submitted recently?"),
]
if not st.session_state["chat_history"]:
    st.caption(t("Try asking:"))
    _srows = [_STARTERS[:3], _STARTERS[3:]]
    for _ri, _row in enumerate(_srows):
        _cols = st.columns(len(_row))
        for _ci, _starter in enumerate(_row):
            with _cols[_ci]:
                if st.button(_starter, key=f"starter_{_ri}_{_ci}", use_container_width=True):
                    st.session_state["pending_question"] = _starter
                    st.rerun()

# Input form — in normal page flow so it stays visible on mobile
with st.form(key="chat_form", clear_on_submit=True):
    col_q, col_send = st.columns([8, 1])
    with col_q:
        question = st.text_input(
            t("question"),
            placeholder=t("Ask about mission data, procedures, or performance..."),
            label_visibility="collapsed",
        )
    with col_send:
        submitted = st.form_submit_button(t("Send"), use_container_width=True)

# A question can arrive either from the form or from a clicked starter chip.
_pending = st.session_state.pop("pending_question", None)
q = None
if submitted and question.strip():
    q = question.strip()
elif _pending:
    q = _pending.strip()

if q:
    st.session_state["chat_history"].append({"role": "user", "content": q})

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except (KeyError, AttributeError):
        st.error(t("GEMINI_API_KEY not configured. Add it to .streamlit/secrets.toml."))
        st.stop()

    with st.spinner(t("Thinking...")):
        try:
            answer = ask_gemini(
                question=q,
                history=st.session_state["chat_history"][:-1],
                kb_context=st.session_state["kb_context"],
                live_context=st.session_state["live_data_context"],
                api_key=api_key,
                extra_contexts=st.session_state.get("supplemental_contexts", {}),
            )
        except GeminiRateLimitError:
            answer = t("Gemini is rate-limited — please wait a few seconds and try again.")
        except (GeminiError, Exception):
            answer = t("I wasn't able to generate an answer. Please rephrase your question.")

    st.session_state["chat_history"].append({"role": "assistant", "content": answer})
    st.rerun()

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
