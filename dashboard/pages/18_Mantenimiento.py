"""
18_Mantenimiento.py
PMG Compass | Maintenance
The mission's back office in one tabbed page — COMPASS_CCSM is meant to be
backend-only, so anything that used to require opening the Sheet should be
doable here instead:
  ✅ To-Do & Health — weekly checklist, data snapshot, pipeline health, agent runs
  📚 Knowledge Base — add Q&A entries AgentQA answers missionaries with
  ⚙️ Agent Settings — every AGENT_CONFIG value, editable in place
  📝 Form Questions — activate/deactivate form questions + push to Google Forms
  🔧 System         — links, test mode, cache controls, connected-systems inventory
Writes: KNOWLEDGE_BASE (new entries), AGENT_CONFIG (setting edits + TEST_MODE),
QUESTIONS_CONFIG (toggles + new questions). Everything else is read-only.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from app.config.flavor_loader import flavor
from app.auth.auth import is_leadership, require_auth
from app.components.design_system import (
    inject_global_css,
    render_page_header,
    render_sidebar,
    render_section_label,
)
from app.db.queries import (
    get_alltime_compliance,
    get_config_value,
    get_daily_log,
    get_meta,
)
from app.db.sheets_client import (
    _get_spreadsheet,
    append_row,
    read_tab,
    read_values,
    update_cells,
)
from app.i18n import t
from app.i18n.formats import fmt_date, fmt_day_month, fmt_int
from app.utils.area_helpers import mission_today

st.set_page_config(
    page_title="CCSM · Maintenance — PMG Compass",
    page_icon="",
    layout="wide",
)

user = require_auth()
inject_global_css()
render_sidebar(user)

render_page_header(
    t("Maintenance"),
    t('{mission_name} — PMG Compass', mission_name=get_config_value('MISSION_NAME', flavor.display_name)),
)

_IS_LEAD = is_leadership(user.get("email", ""))


# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _col_a1(col_1based: int) -> str:
    """1-based column index → A1 letter(s)."""
    letters = ""
    while col_1based > 0:
        col_1based, rem = divmod(col_1based - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _set_config_value(key: str, value: str) -> None:
    """Write one AGENT_CONFIG value in place; append the row if the key is new.
    update_cells/append_row clear the read caches, so get_config_value and the
    agents' next run both see the change immediately."""
    grid = read_values("AGENT_CONFIG")
    headers = [str(h).strip().lower() for h in (grid[0] if grid else [])]
    k_i = next((i for i, h in enumerate(headers) if h in ("config_key", "key")), None)
    v_i = next((i for i, h in enumerate(headers) if h in ("value", "config_value")), None)
    if k_i is None or v_i is None:
        raise RuntimeError("AGENT_CONFIG is missing its Config_Key / Value columns.")
    for r in range(1, len(grid)):
        row = list(grid[r]) + [""] * (max(k_i, v_i) + 1)
        if str(row[k_i]).strip() == key:
            update_cells("AGENT_CONFIG", [(f"{_col_a1(v_i + 1)}{r + 1}", value)])
            return
    new_row = [""] * max(len(grid[0]), max(k_i, v_i) + 1)
    new_row[k_i], new_row[v_i] = key, value
    append_row("AGENT_CONFIG", new_row)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION NAV
# ══════════════════════════════════════════════════════════════════════════════
# Not st.tabs: the editors below call st.rerun() constantly (schedule pencils,
# config saves, KB submits) and st.tabs snaps back to the first tab on every
# rerun. A keyed segmented control keeps the selection sticky.

_TAB_HEALTH = "✅ To-Do & Health"
_TAB_KB = "📚 Knowledge Base"
_TAB_AGENTS = "⚙️ Agent Settings"
_TAB_QUESTIONS = "📝 Form Questions"
_TAB_SYSTEM = "🔧 System"
_SECTIONS = [_TAB_HEALTH, _TAB_KB, _TAB_AGENTS, _TAB_QUESTIONS, _TAB_SYSTEM]

# The switcher must read as real page tabs — at its default size it renders as
# a row of small pills that's easy to miss entirely.
st.markdown(
    """
    <style>
    div[class*="st-key-maint_section"] button,
    div[data-testid="stSegmentedControl"] button,
    div[data-testid="stButtonGroup"] button {
        font-size: 1rem !important;
        padding: 0.6rem 1.2rem !important;
        border-radius: 10px !important;
    }
    div[class*="st-key-maint_section"] button p {
        font-size: 1rem !important;
        font-weight: 600 !important;
    }
    div[class*="st-key-maint_section"] {
        border-bottom: 1px solid rgba(255,255,255,0.10);
        padding-bottom: 0.6rem;
        margin-bottom: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if hasattr(st, "segmented_control"):
    _sec = st.segmented_control(
        "Maintenance section", _SECTIONS,
        key="maint_section", default=_TAB_HEALTH,
        label_visibility="collapsed",
    )
else:  # Streamlit < 1.40 fallback
    _sec = st.radio(
        t("Maintenance section"), _SECTIONS,
        horizontal=True, key="maint_section", label_visibility="collapsed",
    )
_sec = _sec or _TAB_HEALTH

# Flash message from the previous run's save (st.rerun() drops normal output)
_flash_msg = st.session_state.pop("_maint_flash", "")
if _flash_msg:
    st.success(_flash_msg)


# ══════════════════════════════════════════════════════════════════════════════
# ✅ TO-DO & HEALTH
# ══════════════════════════════════════════════════════════════════════════════

if _sec == _TAB_HEALTH:
    render_section_label(t("Weekly To-Do"))
    # mission_today(), not date.today(): this app runs on Streamlit Cloud in
    # UTC, which is already tomorrow through the Chilean evening — so "this
    # week" would roll over on a Sunday night while the mission is still in
    # Saturday, and the checkboxes would reset a day early.
    _today = mission_today()
    _monday = _today - timedelta(days=_today.weekday())
    _wk = _monday.strftime("%Y-%m-%d")   # session-state key — stays ISO
    st.caption(
        t('The weekly maintenance routine — week of {week_of}. Checkboxes reset each Monday and live in your browser session only; everything they ask about is verifiable further down this tab.', week_of=fmt_day_month(_monday))
    )
    _TODOS = [
        "Every agent's last run is green (Agent Runs below)",
        "DAILY_LOG's latest date is yesterday or today (Data Freshness below)",
        "SCORES has the week that just ended",
        "Any red run: open its Notes/Error message in Agent Runs below",
        "First Monday of the month: Streamlit Cloud analytics + Apps Script quotas checked",
    ]
    _done = 0
    for _i, _t in enumerate(_TODOS):
        if st.checkbox(_t, key=f"maint_todo_{_wk}_{_i}"):
            _done += 1
    st.progress(_done / len(_TODOS), text=f"{_done} of {len(_TODOS)} done")

    # ── Data snapshot (absorbed from the old Data Status page) ────────────────
    render_section_label(t("Data Snapshot"))
    st.info(
        t("PMG Compass data updates automatically every day at noon from Google "
        "Sheets. No manual refresh is needed.")
    )

    _meta = get_meta()
    _last_updated = _meta.get("generated_at", "")
    _week_start = _meta.get("current_week_start", "")
    _week_end = _meta.get("current_week_end", "")
    _total_areas = _meta.get("total_areas", "")
    _submitted_today = _meta.get("submitted_today", "")

    try:
        _compliance_today = (
            round(float(_submitted_today) / float(_total_areas) * 100, 1)
            if _submitted_today != "" and _total_areas not in ("", "0") else ""
        )
    except (ValueError, TypeError):
        _compliance_today = ""

    _monday_str = _monday.strftime("%Y-%m-%d")
    _dl14 = get_daily_log(14)
    _submitted_week = (
        int(len(_dl14[_dl14["Date"] >= _monday_str]))
        if not _dl14.empty and "Date" in _dl14.columns else ""
    )

    _comp = get_alltime_compliance()
    _alltime_compliance = (
        round(_comp["days_submitted"].sum() / _comp["days_possible"].sum() * 100, 1)
        if not _comp.empty and _comp["days_possible"].sum() > 0 else ""
    )

    def _pct_label(raw) -> str:
        if raw is None or str(raw).strip() == "":
            return "—"
        try:
            return f"{float(str(raw).replace('%', '').strip()):.1f}%"
        except (ValueError, TypeError):
            return str(raw)

    def _int_label(raw) -> str:
        if raw is None or str(raw).strip() == "":
            return "—"
        try:
            return str(int(float(str(raw).strip())))
        except (ValueError, TypeError):
            return str(raw)

    if _last_updated or _week_start:
        _ic1, _ic2 = st.columns(2)
        if _last_updated:
            _ic1.markdown(t('**Last Updated:** {last_updated}', last_updated=_last_updated))
        if _week_start and _week_end:
            _ic2.markdown(t('**Current Week:** {week_start} — {week_end}', week_start=_week_start, week_end=_week_end))
        if _total_areas:
            _ic1.markdown(t('**Total Areas:** {total_areas}', total_areas=_total_areas))

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric(t("Areas Submitted Today"), _int_label(_submitted_today),
               help=t("Number of areas that submitted their nightly report today."))
    _m2.metric(t("Compliance Today"), _pct_label(_compliance_today),
               help=t("Percentage of active areas that submitted today."))
    _m3.metric(t("Submitted This Week"), _int_label(_submitted_week),
               help=t("Total area-day submissions received so far this week (Mon–Sun)."))
    _m4.metric(t("All-Time Compliance"), _pct_label(_alltime_compliance),
               help=t("Submissions received vs expected across all areas."))

    if not _meta:
        st.warning(t("No metadata available yet — Agent5A may not have run today."))

    # ── Connection & Configuration ────────────────────────────────────────────
    render_section_label(t("Connection & Configuration"))

    # Tabs the app and agents cannot function without. Read from COMPASS_CCSM
    # live so a renamed/deleted tab is caught here before it surfaces as a
    # blank page.
    _REQUIRED_TABS = [
        "NIGHTLY_FORM_RAW", "WEEKLY_FORM_RAW", "DAILY_LOG", "WEEKLY_KI",
        "MISSION_ORG", "GOALS_CONFIG", "AGENT_CONFIG", "SCORE_CONFIG",
        "SCORES", "DASHBOARD_SUMMARY", "AGENT_RUN_LOG", "NOTES",
        "TRANSFER_SCHEDULE", "KNOWLEDGE_BASE", "QUESTIONS_CONFIG",
    ]

    _ok, _bad = [], []

    # Secrets presence (names only — values are never displayed)
    _has_sa = ("gcp_service_account" in st.secrets) or ("GCP_SA_B64" in st.secrets)
    (_ok if _has_sa else _bad).append(
        ("Service account key",
         "found in secrets" if _has_sa
         else "MISSING — gcp_service_account / GCP_SA_B64 not in secrets")
    )
    _has_name = "COMPASS_SHEET_NAME" in st.secrets
    (_ok if _has_name else _bad).append(
        ("COMPASS_SHEET_NAME",
         "found in secrets" if _has_name
         else "MISSING from secrets — app cannot open the spreadsheet")
    )
    _has_gem = "GEMINI_API_KEY" in st.secrets
    (_ok if _has_gem else _bad).append(
        ("GEMINI_API_KEY",
         "found in secrets" if _has_gem
         else "missing — Home page chatbot will not work (agents have their own copy)")
    )

    _missing_tabs: list[str] = []
    try:
        _ss = _get_spreadsheet()
        _titles = {ws.title for ws in _ss.worksheets()}
        _ok.append(("Google Sheets connection",
                    f"connected to “{_ss.title}” — {len(_titles)} tabs"))
        _missing_tabs = [t for t in _REQUIRED_TABS if t not in _titles]
        if _missing_tabs:
            _bad.append(("Required tabs", "MISSING: " + ", ".join(_missing_tabs)))
        else:
            _ok.append(("Required tabs", f"all {len(_REQUIRED_TABS)} present"))
    except Exception as e:
        _bad.append(("Google Sheets connection", f"FAILED — {e}"))

    for _label, _msg in _bad:
        st.error(f"**{_label}:** {_msg}")
    for _label, _msg in _ok:
        st.success(f"**{_label}:** {_msg}")

    if _missing_tabs:
        st.caption(
            t("A required tab going missing usually means someone renamed or "
            "deleted it in COMPASS_CCSM. Restore the exact name — agents and "
            "this app look tabs up by name.")
        )

    # ── Data freshness ────────────────────────────────────────────────────────
    render_section_label(t("Data Freshness"))
    st.caption(
        t("How recently each pipeline stage wrote data. Stale rows here mean an "
        "agent or ingestion run didn't fire — check the agent runs below, then "
        "the Apps Script triggers.")
    )

    def _latest_date(tab: str, marker: str, candidates: tuple[str, ...]) -> tuple[str, str]:
        """Return (latest date string, column used) for the first matching date
        column in `tab`, or ("", "") if the tab is empty/unreadable."""
        try:
            df = read_tab(tab, header_marker=marker)
            if df.empty:
                return "", ""
            col = next(
                (c for c in df.columns if c.strip().lower() in candidates), None
            )
            if not col:
                return "", ""
            vals = pd.to_datetime(df[col], errors="coerce").dropna()
            if vals.empty:
                return "", ""
            return vals.max().strftime("%Y-%m-%d"), col
        except Exception:
            return "", ""

    def _age_days(date_str: str) -> float | None:
        try:
            return (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days
        except (ValueError, TypeError):
            return None

    _fresh_rows = []
    _fresh_rows.append((
        "DASHBOARD_SUMMARY (Agent5A)", _last_updated or "—",
        "META generated_at — rewritten daily at noon",
    ))
    _dl_date, _ = _latest_date("DAILY_LOG", "Date", ("date",))
    _fresh_rows.append((
        "DAILY_LOG (nightly ingestion)", _dl_date or "—",
        "latest Date row — should be yesterday or today",
    ))
    _wk_date, _ = _latest_date(
        "WEEKLY_KI", "Area_Code", ("week_end_date", "week_ending_date", "week_end"))
    _fresh_rows.append((
        "WEEKLY_KI (weekly form)", _wk_date or "—",
        "latest week end — should be within the last 7 days",
    ))
    _sc_date, _ = _latest_date("SCORES", "Area_Code", ("week_ending_date", "week_end_date"))
    _fresh_rows.append((
        "SCORES (AgentScores)", _sc_date or "—",
        "latest scored week — should match WEEKLY_KI",
    ))

    _c1, _c2, _c3, _c4 = st.columns(4)
    for _col, (_label, _val, _help) in zip((_c1, _c2, _c3, _c4), _fresh_rows):
        _col.metric(label=_label, value=_val, help=_help)

    _dl_age = _age_days(_dl_date)
    if _dl_age is not None and _dl_age > 2:
        st.error(
            t("DAILY_LOG hasn't been written in {dl_age} days. The nightly ingestion likely failed — check the agent runs below and the Apps Script triggers.", dl_age=_dl_age)
        )
    _wk_age = _age_days(_wk_date)
    if _wk_age is not None and _wk_age > 9:
        st.warning(
            t("WEEKLY_KI's latest week ended {wk_age} days ago — a weekly cycle may have been missed.", wk_age=_wk_age)
        )

    # ── Agent runs ────────────────────────────────────────────────────────────
    render_section_label(t("Agent Runs"))
    st.caption(
        t("Every Apps Script agent appends a row to AGENT_RUN_LOG when it runs. "
        "An agent missing from the last-run table, or a red status, means its "
        "trigger didn't fire or the run errored.")
    )

    try:
        _log = read_tab("AGENT_RUN_LOG", header_marker="Agent")
    except Exception:
        _log = pd.DataFrame()

    if _log.empty or "Agent" not in _log.columns:
        st.warning(
            t("AGENT_RUN_LOG is empty or unreadable. If agents are running, they "
            "log there on every run — an empty log means the whole chain may be "
            "stopped.")
        )
    else:
        _ts_col = next((c for c in _log.columns if c.strip().lower() == "timestamp"), None)
        if _ts_col:
            _log["_ts"] = pd.to_datetime(_log[_ts_col], errors="coerce")
            _log = _log.sort_values("_ts")

        _last = _log.groupby("Agent", as_index=False).tail(1)
        if "_ts" in _last.columns:
            _last = _last.sort_values("_ts", ascending=False)

        def _status_icon(s: str) -> str:
            s = str(s).strip().upper()
            if s in ("SUCCESS", "OK"):
                return "🟢"
            if s in ("", "NAN"):
                return "⚪"
            return "🔴"

        _rows = []
        for _, r in _last.iterrows():
            _status = str(r.get("Status", "")).strip()
            _when = (
                r["_ts"].strftime("%Y-%m-%d %H:%M")
                if "_ts" in r and pd.notna(r["_ts"]) else str(r.get(_ts_col, ""))
            )
            _rows.append({
                "": _status_icon(_status),
                "Agent": r.get("Agent", ""),
                "Last run": _when,
                "Status": _status,
                "Notes / Error": (
                    str(r.get("Notes", "")) + " " + str(r.get("Error", ""))
                ).strip()[:160],
            })
        st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)

        _fails = _log[
            ~_log["Status"].astype(str).str.strip().str.upper().isin(["SUCCESS", "OK", ""])
        ]
        if "_ts" in _fails.columns:
            _fails = _fails[_fails["_ts"] >= datetime.now() - timedelta(days=14)]
        if not _fails.empty:
            st.error(t('{count} non-success run(s) in the last 14 days:', count=len(_fails)))
            _show_cols = [
                c for c in (_ts_col, "Agent", "Status", "Notes", "Error")
                if c and c in _fails.columns
            ]
            st.dataframe(_fails[_show_cols].tail(20),
                         use_container_width=True, hide_index=True)
        else:
            st.success(t("No failed agent runs in the last 14 days."))

        with st.expander(t("Raw log — last 50 runs")):
            _raw_cols = [c for c in _log.columns if not c.startswith("_")]
            st.dataframe(_log[_raw_cols].tail(50),
                         use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# 📚 KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════

elif _sec == _TAB_KB:
    render_section_label(t("Add a Question & Answer"))
    st.caption(
        t("AgentQA auto-answers missionary questions from the Questions & "
        "Suggestions form using the KNOWLEDGE_BASE tab — every entry added here "
        "makes the next question more likely to be answered without a human. "
        "New entries take the next sequential ID and are live for the very next "
        "question; no code change needed.")
    )

    _kb_grid = read_values("KNOWLEDGE_BASE")
    _KB_COLS = ["ID", "Category", "Question", "Answer", "Keywords",
                "Source", "DateAdded", "UseCount"]

    if not _kb_grid:
        st.warning(
            t("KNOWLEDGE_BASE tab is missing — run setupKnowledgeBase() once from "
            "the Apps Script editor (AgentQA.gs) to create and seed it.")
        )
    else:
        _kbh = [str(h).strip() for h in _kb_grid[0]]
        _kb_missing = [c for c in _KB_COLS if c not in _kbh]
        if _kb_missing:
            st.error(
                "KNOWLEDGE_BASE header row changed — missing column(s): "
                + ", ".join(_kb_missing) + ". Expected: " + ", ".join(_KB_COLS)
            )
        else:
            _kbi = {c: _kbh.index(c) for c in _KB_COLS}
            _kb_rows = [
                r for r in _kb_grid[1:]
                if len(r) > _kbi["ID"] and str(r[_kbi["ID"]]).strip()
            ]

            # Next sequential ID — the tab was seeded faq-001…faq-036 and
            # AgentQA's escalation email tells leadership to keep the sequence.
            _max_n = 0
            for r in _kb_rows:
                m = re.match(r"faq-(\d+)$", str(r[_kbi["ID"]]).strip(), re.I)
                if m:
                    _max_n = max(_max_n, int(m.group(1)))
            _next_id = f"faq-{(_max_n if _max_n else len(_kb_rows)) + 1:03d}"

            _cats = sorted({
                str(r[_kbi["Category"]]).strip() for r in _kb_rows
                if len(r) > _kbi["Category"] and str(r[_kbi["Category"]]).strip()
            })
            if "General" not in _cats:
                _cats = sorted(_cats + ["General"])

            _KW_STOP = {
                "the", "a", "an", "and", "or", "but", "if", "of", "to", "in",
                "on", "for", "with", "is", "are", "was", "were", "be", "been",
                "do", "does", "did", "how", "what", "when", "where", "why",
                "who", "which", "can", "could", "should", "would", "will",
                "my", "our", "your", "their", "his", "her", "its", "it", "we",
                "you", "they", "them", "this", "that", "these", "those", "not",
                "no", "yes", "at", "by", "as", "from", "into", "about", "than",
                "then", "there", "here", "have", "has", "had", "get", "got",
                "put", "every", "each", "all", "any", "some", "more", "most",
                "only", "just", "also", "very", "out", "use", "it's", "don't",
                "doesn't", "isn't", "i'm", "you're",
            }

            def _auto_keywords(question: str, answer: str, limit: int = 8) -> str:
                """First-pass keywords: distinct meaningful words, question
                words first — they're what a future asker is most likely to
                repeat."""
                words = re.findall(r"[a-z][a-z']+", f"{question} {answer}".lower())
                out: list[str] = []
                for w in words:
                    if len(w) < 3 or w in _KW_STOP or w in out:
                        continue
                    out.append(w)
                    if len(out) >= limit:
                        break
                return ", ".join(out)

            if not _IS_LEAD:
                st.caption(t("Only mission leadership can add knowledge-base entries."))
            else:
                with st.form("kb_add_form", clear_on_submit=True):
                    _kb_q = st.text_area(
                        t("Question"),
                        placeholder=t("What the missionary asked — or is likely to ask"),
                    )
                    _kb_a = st.text_area(
                        t("Answer"),
                        placeholder=t("The answer AgentQA should send back"),
                    )
                    _kb_kw = st.text_input(
                        t("Keywords"),
                        placeholder=t("comma-separated — leave blank to auto-generate from the Q&A"),
                    )
                    _fc1, _fc2 = st.columns(2)
                    _kb_src = _fc1.text_input(
                        t("Added by"), value=user.get("name") or user.get("email", ""))
                    _kb_cat = _fc2.selectbox(t("Category"), _cats,
                                             index=_cats.index("General"))
                    _kb_submit = st.form_submit_button(
                        t('Add to Knowledge Base as {next_id}', next_id=_next_id), type="primary")

                if _kb_submit:
                    if not _kb_q.strip() or not _kb_a.strip():
                        st.error(t("Both the question and the answer are required."))
                    else:
                        _kw_final = _kb_kw.strip() or _auto_keywords(_kb_q, _kb_a)
                        _new = [""] * len(_kbh)
                        for _c, _v in {
                            "ID": _next_id,
                            "Category": _kb_cat,
                            "Question": _kb_q.strip(),
                            "Answer": _kb_a.strip(),
                            "Keywords": _kw_final,
                            "Source": _kb_src.strip() or user.get("email", ""),
                            "DateAdded": date.today().strftime("%Y-%m-%d"),
                            "UseCount": 0,
                        }.items():
                            _new[_kbi[_c]] = _v
                        try:
                            append_row("KNOWLEDGE_BASE", _new)
                        except Exception as e:
                            st.error(t('Could not write to KNOWLEDGE_BASE: {e}', e=e))
                        else:
                            st.session_state["_maint_flash"] = (
                                f"{_next_id} added to the knowledge base"
                                + (" — keywords auto-generated." if not _kb_kw.strip() else ".")
                            )
                            st.rerun()

            # ── Existing entries ──────────────────────────────────────────────
            render_section_label(t('Existing Entries ({count})', count=len(_kb_rows)))
            _kb_search = st.text_input(
                t("Search the knowledge base"), key="kb_search",
                placeholder=t("Filter by any word in the question, answer, or keywords"),
            )
            _kb_df = pd.DataFrame([
                {c: (r[_kbi[c]] if len(r) > _kbi[c] else "") for c in _KB_COLS}
                for r in _kb_rows
            ])
            if _kb_search.strip():
                _needle = _kb_search.strip().lower()
                _kb_df = _kb_df[_kb_df.apply(
                    lambda row: _needle in " ".join(str(v).lower() for v in row.values),
                    axis=1,
                )]
            st.dataframe(_kb_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# ⚙️ AGENT SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

elif _sec == _TAB_AGENTS:
    render_section_label(t("Agent Configuration (AGENT_CONFIG)"))
    st.caption(
        t("Every setting the Apps Script agents read at run time. Edits here take "
        "effect on the next agent run automatically — no Apps Script paste "
        "needed. Secret-looking values are masked; editing one replaces it "
        "outright.")
    )

    _cfg_grid = read_values("AGENT_CONFIG")
    if not _cfg_grid or len(_cfg_grid) < 2:
        st.warning(t("AGENT_CONFIG is missing or empty."))
    else:
        _ch = [str(h).strip() for h in _cfg_grid[0]]
        _ck = next((i for i, h in enumerate(_ch)
                    if h.lower() in ("config_key", "key")), None)
        _cv = next((i for i, h in enumerate(_ch)
                    if h.lower() in ("value", "config_value")), None)
        _cd = next((i for i, h in enumerate(_ch)
                    if h.lower() in ("description", "notes", "purpose")), None)
        if _ck is None or _cv is None:
            st.error(
                t("AGENT_CONFIG header row changed — expected Config_Key and "
                "Value columns. Fix the header in the Sheet.")
            )
        else:
            if not _IS_LEAD:
                st.caption(t("Only mission leadership can edit settings."))
            _cfg_filter = st.text_input(
                t("Filter settings"), key="cfg_filter",
                placeholder=t("e.g. EMAIL, TEST, FORM"),
            )
            _val_a1 = _col_a1(_cv + 1)

            for _r in range(1, len(_cfg_grid)):
                _row = list(_cfg_grid[_r]) + [""] * len(_ch)
                _key = str(_row[_ck]).strip()
                if not _key:
                    continue
                if _cfg_filter.strip() and _cfg_filter.strip().lower() not in _key.lower():
                    continue
                _val = str(_row[_cv]).strip()
                _desc = str(_row[_cd]).strip() if _cd is not None else ""
                # Mask anything credential-shaped — the value never renders.
                _secret = bool(
                    re.search(r"SECRET|TOKEN|PASSWORD|API_KEY", _key, re.I)
                    or _key.upper().endswith("_KEY")
                )
                _shown = ("••••••••" if _val else "—") if _secret else (_val or "—")

                if st.session_state.get("_cfg_editing") == _key:
                    with st.container(border=True):
                        st.markdown(f"**{_key}**")
                        if _desc:
                            st.caption(_desc)
                        if _secret:
                            st.caption(
                                t("This value is masked — whatever you type "
                                "replaces it. Leave and Cancel to keep it."))
                            _new_val = st.text_input(
                                t("New value"), key=f"cfg_new_{_key}", type="password")
                        else:
                            _new_val = st.text_input(
                                t("New value"), value=_val, key=f"cfg_new_{_key}")
                        _bs, _bc, _ = st.columns([1, 1, 4])
                        if _bs.button(t("Save"), key=f"cfg_save_{_key}", type="primary"):
                            try:
                                update_cells(
                                    "AGENT_CONFIG",
                                    [(f"{_val_a1}{_r + 1}", _new_val)],
                                )
                            except Exception as e:
                                st.error(t('Could not write AGENT_CONFIG: {e}', e=e))
                            else:
                                st.session_state.pop("_cfg_editing", None)
                                st.session_state["_maint_flash"] = (
                                    f"{_key} updated — agents pick it up on "
                                    "their next run."
                                )
                                st.rerun()
                        if _bc.button(t("Cancel"), key=f"cfg_cancel_{_key}"):
                            st.session_state.pop("_cfg_editing", None)
                            st.rerun()
                else:
                    _cc1, _cc2, _cc3 = st.columns([3, 4, 0.5])
                    _cc1.markdown(f"**{_key}**")
                    _cc2.markdown(_shown)
                    if _desc:
                        _cc2.caption(_desc)
                    if _IS_LEAD and _cc3.button(t("✏️"), key=f"cfg_edit_{_r}"):
                        st.session_state["_cfg_editing"] = _key
                        st.rerun()

            if _IS_LEAD:
                with st.expander(t("➕ Add a new setting")):
                    st.caption(
                        t("Only useful for a key an agent actually reads — "
                        "unknown keys are ignored harmlessly.")
                    )
                    _nk = st.text_input(
                        t("Key"), key="cfg_add_key",
                        placeholder=t("e.g. ESCALATION_NIGHTLY_HOUR"),
                    )
                    _nv = st.text_input(t("Value"), key="cfg_add_val")
                    if st.button(t("Add setting"), key="cfg_add_btn",
                                 disabled=not _nk.strip()):
                        try:
                            _set_config_value(_nk.strip(), _nv.strip())
                        except Exception as e:
                            st.error(t('Could not write AGENT_CONFIG: {e}', e=e))
                        else:
                            st.session_state["_maint_flash"] = f"{_nk.strip()} saved."
                            st.rerun()

    st.info(
        t("The failsafe/escalation email times (nightly ~10 AM, weekly ~8:45 PM "
        "MT) are baked into Apps Script triggers today. To control them from "
        "here: paste **docs/EscalationHoursConfig.gs** into the Apps Script "
        "editor once and run its setup — after that, the "
        "ESCALATION_NIGHTLY_HOUR / ESCALATION_WEEKLY_HOUR settings above are "
        "what set the send times."),
        icon="⏰",
    )


# ══════════════════════════════════════════════════════════════════════════════
# 📝 FORM QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════

elif _sec == _TAB_QUESTIONS:
    render_section_label(t("Form Question Configuration (QUESTIONS_CONFIG)"))
    st.caption(
        t("The questions on the nightly and weekly report forms. Active drives "
        "what the agents process and what most pages show. Toggling here (or "
        "adding a question) does **not** touch the Google Forms until you push "
        "below — the push adds active questions to every zone's section and "
        "removes inactive ones.")
    )

    _q_grid = read_values("QUESTIONS_CONFIG")
    _Q_NEED = ["Question_ID", "Form_Type", "Form_Column_Header",
               "Metric_Key", "Metric_Display_Name", "Active"]

    if not _q_grid or len(_q_grid) < 2:
        st.warning(t("QUESTIONS_CONFIG is missing or empty."))
    else:
        _qh = [str(h).strip() for h in _q_grid[0]]
        _q_missing = [c for c in _Q_NEED if c not in _qh]
        if _q_missing:
            st.error(
                "QUESTIONS_CONFIG header row changed — missing column(s): "
                + ", ".join(_q_missing)
            )
        else:
            _qi = {c: _qh.index(c) for c in _Q_NEED}
            _qi_order = _qh.index("Display_Order") if "Display_Order" in _qh else None
            _active_a1 = _col_a1(_qi["Active"] + 1)

            _qrows = []
            for _r in range(1, len(_q_grid)):
                _row = list(_q_grid[_r]) + [""] * len(_qh)
                _qid = str(_row[_qi["Question_ID"]]).strip()
                if not _qid:
                    continue
                _qrows.append({
                    "sheet_row": _r + 1,
                    "id": _qid,
                    "form": str(_row[_qi["Form_Type"]]).strip().upper(),
                    "header": str(_row[_qi["Form_Column_Header"]]).strip(),
                    "key": str(_row[_qi["Metric_Key"]]).strip(),
                    "active": str(_row[_qi["Active"]]).strip().upper() == "TRUE",
                })

            _changes: list[tuple[str, str]] = []
            for _label, _ft in (("Nightly form", "NIGHTLY"), ("Weekly form", "WEEKLY")):
                _group = [q for q in _qrows if q["form"] == _ft]
                if not _group:
                    continue
                st.markdown(
                    t('**{label}** — {sum} of {count} active', label=_label, sum=sum(q['active'] for q in _group), count=len(_group))
                )
                for q in _group:
                    _t = st.toggle(
                        f"{q['header']}  ·  `{q['key']}`",
                        value=q["active"],
                        key=f"qact_{q['sheet_row']}",
                        disabled=not _IS_LEAD,
                    )
                    if _t != q["active"]:
                        _changes.append(
                            (f"{_active_a1}{q['sheet_row']}", "TRUE" if _t else "FALSE"))

            _other = [q for q in _qrows if q["form"] not in ("NIGHTLY", "WEEKLY")]
            if _other:
                st.markdown(t('**Other / both forms** — {count} question(s)', count=len(_other)))
                for q in _other:
                    _t = st.toggle(
                        f"{q['header']}  ·  `{q['key']}`",
                        value=q["active"],
                        key=f"qact_{q['sheet_row']}",
                        disabled=not _IS_LEAD,
                    )
                    if _t != q["active"]:
                        _changes.append(
                            (f"{_active_a1}{q['sheet_row']}", "TRUE" if _t else "FALSE"))

            if _changes and _IS_LEAD:
                st.warning(
                    t('{count} unsaved change(s). Saving updates QUESTIONS_CONFIG (agents follow it on their next run) — push to the Google Forms separately below.', count=len(_changes))
                )
                if st.button(t("Save question changes"), type="primary", key="q_save"):
                    try:
                        update_cells("QUESTIONS_CONFIG", _changes)
                    except Exception as e:
                        st.error(t('Could not write QUESTIONS_CONFIG: {e}', e=e))
                    else:
                        st.session_state["_maint_flash"] = (
                            f"{len(_changes)} question change(s) saved to "
                            "QUESTIONS_CONFIG."
                        )
                        st.rerun()

            # ── Add a question ────────────────────────────────────────────────
            if _IS_LEAD:
                with st.expander(t("➕ Add a question")):
                    st.caption(
                        t("Adds the question to QUESTIONS_CONFIG as Active. It "
                        "reaches the real Google Forms when you push below, and "
                        "the agents start processing it on their next run. "
                        "Note: a few hard-coded metric lists (the Breakdowns "
                        "metric picker) still need a code change to show a "
                        "brand-new metric.")
                    )
                    # Options stay English - these values are written to the form
                    # config and read by the Apps Script agents. format_func
                    # translates the display only.
                    _aq_form = st.selectbox(t("Form"), ["NIGHTLY", "WEEKLY"],
                                            format_func=t, key="q_add_form")
                    _aq_text = st.text_input(
                        t("Question text — exactly as it should appear on the form"),
                        key="q_add_text",
                        placeholder=t("e.g. Contactos con amigos"),
                    )
                    _aq_name = st.text_input(
                        t("Short display name (charts and reports)"),
                        key="q_add_name", placeholder=t("e.g. Contactos"),
                    )
                    _aq_key = st.text_input(
                        t("Metric key — leave blank to derive from the display name"),
                        key="q_add_key", placeholder=t("e.g. contacts_made"),
                    )
                    # These four are the Data_Type values QUESTIONS_CONFIG
                    # actually holds and the rest of the app branches on
                    # (metric_catalog.non_numeric_metrics / metric_data_type,
                    # CCSM_Agent1A's parsing). The picker used to offer
                    # INTEGER / TEXT / DATE, none of which except DATE is one of
                    # them: a question added as TEXT would be classified numeric
                    # everywhere downstream and its written answers coerced to 0,
                    # which is indistinguishable from an area reporting zero.
                    _aq_dtype = st.selectbox(
                        t("Data type"), ["NUMBER", "YESNO", "CHOICE", "DATE"],
                        format_func=t, key="q_add_dtype")

                    if st.button(t("Add question"), key="q_add_btn", type="primary"):
                        _slug_src = _aq_key.strip() or _aq_name.strip() or _aq_text.strip()
                        _slug = re.sub(r"[^a-z0-9]+", "_", _slug_src.lower()).strip("_")
                        if not _aq_text.strip() or not _slug:
                            st.error(t("Question text and a metric key (or display name) are required."))
                        elif any(q["key"] == _slug for q in _qrows):
                            st.error(t('Metric key `{slug}` already exists — pick another.', slug=_slug))
                        elif any(
                            q["header"].lower() == _aq_text.strip().lower()
                            and q["form"] == _aq_form for q in _qrows
                        ):
                            st.error(t("That exact question is already on this form."))
                        else:
                            # IDs follow the seeded Q-N-### / Q-W-### convention
                            _pfx = "Q-N-" if _aq_form == "NIGHTLY" else "Q-W-"
                            _max_qn = 0
                            for q in _qrows:
                                m = re.match(rf"{_pfx}(\d+)$", q["id"], re.I)
                                if m:
                                    _max_qn = max(_max_qn, int(m.group(1)))
                            _new_qid = f"{_pfx}{_max_qn + 1:03d}"
                            _orders = []
                            if _qi_order is not None:
                                for _r in range(1, len(_q_grid)):
                                    _row = list(_q_grid[_r]) + [""] * len(_qh)
                                    if str(_row[_qi["Form_Type"]]).strip().upper() == _aq_form:
                                        try:
                                            _orders.append(int(float(_row[_qi_order])))
                                        except (ValueError, TypeError):
                                            pass
                            _new_row = [""] * len(_qh)
                            _fill = {
                                "Question_ID": _new_qid,
                                "Form_Type": _aq_form,
                                "Form_Column_Header": _aq_text.strip(),
                                "Metric_Key": _slug,
                                "Metric_Display_Name": _aq_name.strip() or _aq_text.strip(),
                                "Data_Type": _aq_dtype,
                                "Include_In_Daily_Log": "TRUE",
                                "Include_In_Live_Snapshot": "TRUE",
                                "Include_In_Weekly_Breakdown": "TRUE",
                                "Display_Order": (max(_orders) + 1) if _orders else len(_qrows) + 1,
                                "Active": "TRUE",
                            }
                            for _c, _v in _fill.items():
                                if _c in _qh:
                                    _new_row[_qh.index(_c)] = _v
                            try:
                                append_row("QUESTIONS_CONFIG", _new_row)
                            except Exception as e:
                                st.error(t('Could not write QUESTIONS_CONFIG: {e}', e=e))
                            else:
                                st.session_state["_maint_flash"] = (
                                    f"{_new_qid} ({_slug}) added as Active — "
                                    "push below to put it on the form."
                                )
                                st.rerun()

            # ── Push to the Google Forms ──────────────────────────────────────
            render_section_label(t("Push to Google Forms"))
            _sync_url = str(
                st.secrets.get("QUESTION_SYNC_WEBAPP_URL",
                               get_config_value("QUESTION_SYNC_WEBAPP_URL", ""))
            ).strip()
            _sync_secret = str(
                st.secrets.get("QUESTION_SYNC_WEBAPP_SECRET", "")
            ).strip()

            if not _sync_url or not _sync_secret:
                st.info(
                    t("The question-sync web app isn't deployed yet, so pushing "
                    "from here is disabled. One-time setup: paste "
                    "**docs/FormQuestionSyncWebApp.gs** into the COMPASS_CCSM "
                    "Apps Script editor, deploy it as a web app, then add "
                    "QUESTION_SYNC_WEBAPP_URL and QUESTION_SYNC_WEBAPP_SECRET "
                    "to this app's secrets. Until then, form questions have to "
                    "be edited in the Google Forms editor by hand."),
                    icon="🔌",
                )
            else:
                st.caption(
                    t("Adds every Active question to every zone section of its "
                    "form and deletes questions that are no longer active. "
                    "Already-collected responses in the Sheet are never touched.")
                )
                if st.button(
                    t("Push questions to the Google Forms"),
                    type="primary", key="q_push", disabled=not _IS_LEAD,
                ):
                    import requests as _requests
                    with st.spinner(t("Syncing both forms — this can take a minute...")):
                        try:
                            _resp = _requests.post(
                                _sync_url,
                                json={
                                    "secret": _sync_secret,
                                    "action": "questionSync",
                                    "which": "both",
                                },
                                timeout=300,
                            )
                            _data = _resp.json()
                        except Exception as e:
                            st.error(t('Push failed: {e}', e=e))
                        else:
                            if _data.get("ok"):
                                for _f in ("nightly", "weekly"):
                                    _fr = _data.get(_f) or {}
                                    if _fr:
                                        st.success(f"**{_f.title()}:** {_fr.get('msg', _fr)}")
                            else:
                                st.error(t('Push failed: {data}', data=_data.get('error', _data)))


# ══════════════════════════════════════════════════════════════════════════════
# 🔧 SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

elif _sec == _TAB_SYSTEM:
    render_section_label(t("Quick Links"))
    st.caption(
        t("If the app is ever wrong or down, COMPASS_CCSM is the source of truth "
        "— everything the mission reports lives there.")
    )
    _l1, _l2, _l3 = st.columns(3)
    try:
        _l1.link_button(t("Open COMPASS_CCSM ↗"), _get_spreadsheet().url,
                        use_container_width=True)
    except Exception as e:
        _l1.error(t('COMPASS_CCSM link unavailable — {e}', e=e))
    _nf_link = get_config_value("NIGHTLY_FORM_LINK", "")
    if _nf_link:
        _l2.link_button(t("Nightly form ↗"), _nf_link, use_container_width=True)
    _wf_link = get_config_value("WEEKLY_FORM_LINK", "")
    if _wf_link:
        _l3.link_button(t("Weekly form ↗"), _wf_link, use_container_width=True)
    st.page_link(
        "pages/06_Puntajes.py",
        label="Effectiveness score weights are edited on the **Scores** page →",
    )

    # ── Test mode ─────────────────────────────────────────────────────────────
    render_section_label(t("Test Mode"))
    _test_on = get_config_value("TEST_MODE", "FALSE").upper() == "TRUE"
    if _test_on:
        st.warning(
            t("**TEST MODE is ON.** All agent emails are redirected to the test "
            "inbox and data is written to TEST_* tabs. Missionaries receiving "
            "nothing is expected while this is on.")
        )
        if _IS_LEAD:
            if st.button(t("Disable Test Mode (Go Live)"), type="primary", key="tm_off"):
                try:
                    _set_config_value("TEST_MODE", "FALSE")
                except Exception as e:
                    st.error(t('Could not update AGENT_CONFIG: {e}', e=e))
                else:
                    st.session_state["_maint_flash"] = (
                        "Test Mode disabled — the system is LIVE.")
                    st.rerun()
        else:
            st.caption(t("Only mission leadership can change test mode."))
    else:
        st.success(t("**System is LIVE.** Test Mode is off."))
        if _IS_LEAD:
            _tm_sure = st.checkbox(
                t("I understand missionaries stop receiving real emails while "
                "Test Mode is on."),
                key="tm_confirm",
            )
            if st.button(t("Enable Test Mode"), key="tm_on", disabled=not _tm_sure):
                try:
                    _set_config_value("TEST_MODE", "TRUE")
                except Exception as e:
                    st.error(t('Could not update AGENT_CONFIG: {e}', e=e))
                else:
                    st.session_state["_maint_flash"] = (
                        "TEST MODE is ON — emails now go to the test inbox.")
                    st.rerun()
        else:
            st.caption(t("Only mission leadership can change test mode."))

    # ── App controls ──────────────────────────────────────────────────────────
    render_section_label(t("App Controls"))
    st.caption(
        t("These only affect this Streamlit app — never the Sheet, the agents, "
        "or any emails. Safe to use any time.")
    )
    _b1, _b2 = st.columns(2)
    with _b1:
        if st.button(
            t("Clear data cache"),
            use_container_width=True,
            help=t("Drops all 5-minute cached reads so every page refetches live "
                 "from COMPASS_CCSM. Use when the Sheet was just edited and "
                 "pages still show old numbers."),
        ):
            st.cache_data.clear()
            st.success(t("Data cache cleared — pages will refetch on next load."))
    with _b2:
        if st.button(
            t("Reset Google Sheets connection"),
            use_container_width=True,
            help=t("Rebuilds the gspread client and reopens the spreadsheet, plus "
                 "clears the data cache. Use when reads fail with "
                 "auth/connection errors that a cache clear doesn't fix."),
        ):
            st.cache_resource.clear()
            st.cache_data.clear()
            st.success(t("Connection reset — it will reconnect on next read."))

    # ── Connected systems ─────────────────────────────────────────────────────
    render_section_label(t("Everything This System Is Connected To"))
    st.markdown(
        t("- **COMPASS_CCSM (Google Sheet)** — the only data store. Every tab the "
        "agents and this app read or write lives there (link above).\n"
        "- **Google Forms** — the nightly + weekly report forms (links above) "
        "write into NIGHTLY_FORM_RAW / WEEKLY_FORM_RAW; the Questions & "
        "Suggestions form feeds AgentQA.\n"
        "- **Apps Script agents** — live *inside* COMPASS_CCSM (Extensions → "
        "Apps Script). The table below lists them; `docs/` in the git repo "
        "holds reference copies, but **only code pasted into the online editor "
        "actually runs**.\n"
        "- **This app (Streamlit Cloud)** — auto-deploys the `main` branch. "
        "Reads COMPASS_CCSM via the service account; writes Notes, Score "
        "Config, and the tabs this page edits.\n"
        "- **GitHub Actions** — cloud buttons in this app dispatch "
        "`transfer-roster-pull.yml` (portal roster → TRANSFER_IMPORT), "
        "`referral-scraper.yml` (referrals → REFERRAL_DATA), and "
        "`tableau-reports.yml` (quarterly Tableau exports).\n"
        "- **Gemini API** — the Home-page chatbot, AgentQA's auto-answers, and "
        "Agent1C's leadership narratives.")
    )
    _agents_df = pd.DataFrame(
        [
            ("Agent1A", "Sunday coaching — collects & analyzes the week's nightly data", "Sunday night (starts the 1A→1B→1C chain)"),
            ("Agent1B", "Sunday coaching — picks messages from MESSAGE_BANK", "chained after 1A"),
            ("Agent1C", "Sunday coaching — sends the coaching emails", "chained after 1B"),
            ("Agent2", "Transfer goal recalibration", "start of each transfer"),
            ("Agent3", "Daily refresh — nightly form → DAILY_LOG / LIVE_SNAPSHOT", "nightly ~9:30 PM"),
            ("Agent4", "System health check", "scheduled"),
            ("Agent5A", "Dashboard summary aggregator → DASHBOARD_SUMMARY", "daily at noon"),
            ("Agent5B", "Friday encouragement checker", "Friday"),
            ("Agent6", "Friday encouragement email sender", "Friday PM"),
            ("Agent7", "Nightly report for the Mission President's wife", "nightly ~10:15 PM"),
            ("AgentScores", "Weekly Effort/Skill/KI/Effectiveness scores → SCORES", "Monday"),
            ("AgentQA", "Auto-answers Q&S form submissions (KNOWLEDGE_BASE + Gemini)", "on form submit"),
            ("AgentEscalation", "Failsafe emails for missing nightly/weekly reports", "daily 10 AM & ~8:45 PM MT"),
            ("AgentReminder", "Notes follow-up reminder emails", "hourly"),
            ("AgentDuplicate", "Duplicate submission detector", "on nightly form submit"),
            ("AgentValidation", "Data validation checks", "scheduled"),
            ("AgentTransfer + TransferWebApp", "Transfer apply + form zone sync", "Transfer Tools menu / called by this app"),
            ("WardPlanForm + FileMover", "Ward plan upload handling", "on submit / scheduled"),
        ],
        columns=["Agent", "What it does", "When it runs"],
    )
    st.dataframe(_agents_df, use_container_width=True, hide_index=True)
    st.caption(
        t("Schedules shown are the intended ones — Apps Script → Triggers (clock "
        "icon) is the live truth.")
    )

    # ── Environment ───────────────────────────────────────────────────────────
    render_section_label(t("Environment"))

    def _pkg_version(name: str) -> str:
        try:
            from importlib.metadata import version
            return version(name)
        except Exception:
            return "?"

    _e1, _e2 = st.columns(2)
    _e1.markdown(
        t('**Python:** {value}  \n**Streamlit:** {streamlit}  \n**pandas:** {pandas} · **gspread:** {gspread}', value=sys.version.split()[0], streamlit=_pkg_version('streamlit'), pandas=_pkg_version('pandas'), gspread=_pkg_version('gspread'))
    )
    _e2.markdown(
        t('**Mission flavor:** {id} ({display_name})  \n**Test mode:** {value}  \n**Signed in as:** {user} ({user2})', id=flavor.id, display_name=flavor.display_name, value='🟠 ON — emails redirected to test inbox' if _test_on else '🟢 off (live)', user=user.get('email', ''), user2=user.get('role', 'unknown'))
    )

    # ── Runbook ───────────────────────────────────────────────────────────────
    render_section_label(t("Runbook"))

    with st.expander(t("If the app is stale, blank, or erroring")):
        st.markdown(
            t("1. **Clear data cache** (button above). Fixes 90% of \"the Sheet "
            "says X but the app says Y\" — reads are cached for 5 minutes.\n"
            "2. **Reset the Sheets connection** if reads are failing outright.\n"
            "3. **Reboot the app**: Streamlit Cloud → the app's ⋮ menu → "
            "Reboot. Also forces the latest commit from `main` to deploy.\n"
            "4. **Check secrets**: Streamlit Cloud → app → Settings → Secrets "
            "must contain the service account, COMPASS_SHEET_NAME, and "
            "GEMINI_API_KEY. The service account email must have access to "
            "COMPASS_CCSM (share the Sheet with it).\n"
            "5. **No data at all?** The agents write the tabs this app reads — "
            "check Agent Runs (To-Do & Health tab) and Apps Script triggers, "
            "not the app.")
        )

    with st.expander(t("If agents stopped running or emails stopped sending")):
        st.markdown(
            t("1. Open COMPASS_CCSM → **Extensions → Apps Script → Triggers** "
            "(clock icon) and confirm each agent's time-driven trigger still "
            "exists.\n"
            "2. Check **Executions** in the same editor for red failed runs — "
            "the stack trace there is more detailed than AGENT_RUN_LOG.\n"
            "3. Remember **TEST_MODE**: if it's on (see above), all emails go "
            "to the test inbox — missionaries receiving nothing is expected.\n"
            "4. The Sunday chain is Agent1A → 1B → 1C; if 1A fails the whole "
            "chain stops. Start diagnosis at 1A.\n"
            "5. ⚠️ **Code changes**: editing `docs/*.gs` in the git repo does "
            "NOT change the live agents. Live code is only what's pasted into "
            "the Apps Script editor — every fix must be copy-pasted there by "
            "hand.")
        )
