"""
app/config/metric_catalog.py
────────────────────────────────────────────────────────────────────────────────
The mission's metric vocabulary, GENERATED from the live QUESTIONS_CONFIG tab.

Why generated rather than written down
──────────────────────────────────────
This app was copied from Utah Provo's, and its metric catalogue came with it:
lsi_given, lsi_followups, nm_doors, nm_texts, nm_contacted, nm_meaningful,
nm_lessons, pew, gate, renew, date_metric, la_lessons, locos_Attempt,
fellowshipper_Attempt, aux_Attempt, info_Attempt, online_referrals. Not one of
those is a question on a CCSM form — CCSM does not even run Love/Share/Invite.
The same dead catalogue was duplicated across three files, so they could drift
from each other as well as from reality.

QUESTIONS_CONFIG is the tab the Apps Script agents themselves read to decide
which columns exist (CCSM_Agent3.a3_loadActiveMetrics, CCSM_Agent1A's
a1a_loadCountMetrics), and it is editable from the Maintenance page. Reading it
here means the dashboard and the agents cannot disagree about what a metric is,
and a question added to the form shows up without a code change.

What is NOT in QUESTIONS_CONFIG
───────────────────────────────
The five rate/score metrics are computed by CCSM_Agent1A.gs from other
metrics; they are never asked on a form, so they have no QUESTIONS_CONFIG row
and have to be declared here. `tests/test_metric_catalog.py` parses
CCSM_Agent1A.gs's own A1A_RATE_METRICS array and asserts this declaration
matches it, so the duplication cannot silently drift — which is the entire
failure mode this module exists to end.
"""

from __future__ import annotations

import streamlit as st

from app.db.sheets_client import read_tab

# ── Derived metrics (computed, never asked) ───────────────────────────────────
# Mirrors A1A_RATE_METRICS in CCSM_Agent1A.gs — key -> Spanish display name,
# verbatim from that file. Kept in the same order for diffability.
# Enforced equal by tests/test_metric_catalog.py::test_rate_metrics_match_agent1a.
RATE_METRIC_LABELS: dict[str, str] = {
    "contact_rate": "Tasa de Contacto",
    "mc_rate":      "Tasa de Conversaciones Significativas",
    "lesson_rate":  "Tasa de Lecciones",
    "close_rate":   "Tasa de Invitación Bautismal",
    "effort_score": "Nivel de Esfuerzo",
}

#: Rate/score metrics must be AVERAGED across areas, never summed — a mission
#: "contact rate" of 47 areas added together is meaningless.
RATE_METRICS: frozenset[str] = frozenset(RATE_METRIC_LABELS)

# ── English labels (display convenience only) ─────────────────────────────────
# QUESTIONS_CONFIG stores Spanish display names, which is correct: CCSM is a
# Spanish-speaking mission and those strings are what appear on the real forms.
# This map lets the app's English mode read naturally for the few non-Spanish
# speakers who use it (the mission president's office, whoever maintains this).
#
# It is deliberately NON-AUTHORITATIVE. It can only rename a metric the sheet
# already defines; it can never add one or remove one. A key missing from here
# falls back to the Spanish name rather than disappearing, so this map going
# stale degrades to "shows Spanish" instead of "metric vanishes from the app".
EN_LABEL_OVERRIDES: dict[str, str] = {
    # Nightly
    "report_date":               "Report Date",
    "exchanges":                 "Exchanges",
    "roleplays":                 "Teaching Practices",
    "contacts_attempted":        "Contacts Attempted",
    "contacts_made":             "Contacts Made",
    "meaningful_conversations":  "Meaningful Conversations",
    "new_people_found":          "New People Found",
    "friend_lessons":            "Lessons With Friends",
    "pmf_lessons":               "Part-Member Family Lessons",
    "rc_lessons":                "Recent Convert Lessons",
    "rc_lessons_mcp":            "Recent Convert Lessons (My Covenant Path)",
    "friend_texts":              "Texts to Friends",
    "friend_calls":              "Calls to Friends",
    "member_contacts":           "Member Contacts",
    "lessons_member_present":    "Lessons With a Member Present",
    "references_asked":          "Referrals Asked For",
    "member_referrals_received": "Member Referrals Received",
    "bom_shared":                "Books of Mormon Shared",
    "church_invites":            "Church Invitations",
    "baptism_doctrine_lessons":  "Baptism Doctrine Lessons",
    "baptismal_invitations":     "Baptismal Invitations",
    "baptismal_calendars":       "Baptismal Calendars",
    "effort":                    "Effort Level",
    # Weekly
    "leader_call":               "Leader Call",
    "correlation_meeting":       "Weekly Correlation Meeting",
    # Derived
    "contact_rate":              "Contact Rate",
    "mc_rate":                   "Meaningful Conversation Rate",
    "lesson_rate":               "Lesson Rate",
    "close_rate":                "Baptismal Invitation Rate",
    "effort_score":              "Effort Score",
}

#: Columns of DAILY_LOG that identify the row rather than measure anything.
DAILY_META: frozenset[str] = frozenset({"Date", "Area", "Zone", "District"})

#: Score dimensions written by CCSM_AgentScores.gs — column order matches
#: get_scores_by_area()'s frame. These are score COMPONENTS, not form metrics,
#: so they are not in QUESTIONS_CONFIG either.
SCORE_LABELS: dict[str, str] = {
    "Effort_Score":        "Esfuerzo",
    "Skill_Score":         "Habilidad",
    "KI_Score":            "Indicadores Clave",
    "Effectiveness_Score": "Efectividad",
}

#: report_date is a QUESTIONS_CONFIG row on BOTH forms, but it is the date the
#: report covers — not a measurement. Excluded from every catalogue below.
_NON_METRIC_KEYS: frozenset[str] = frozenset({"report_date"})


# ── Catalogue construction ────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _load_question_rows() -> list[dict]:
    """QUESTIONS_CONFIG as plain dicts. Cached with the same 5-minute TTL as
    every other sheet read, so building the catalogue costs no extra API call
    on a warm page."""
    df = read_tab("QUESTIONS_CONFIG")
    if df.empty or "Metric_Key" not in df.columns:
        return []

    rows: list[dict] = []
    seen: set[str] = set()
    for _, r in df.iterrows():
        key = str(r.get("Metric_Key", "")).strip()
        if not key:
            continue
        active = str(r.get("Active", "TRUE")).strip().upper()
        if active not in ("TRUE", "YES", "1", ""):
            continue
        form_type = str(r.get("Form_Type", "")).strip().upper()
        row = {
            "key": key,
            "label": str(r.get("Metric_Display_Name", "")).strip() or key,
            "form_type": form_type,
            "data_type": str(r.get("Data_Type", "")).strip().upper(),
        }
        # A key defined on BOTH forms (report_date is) must appear once. Keeping
        # the first (Nightly-ordered) definition matches how 02_Metas.py dedupes
        # and how the agents read it. Without this, callers building a dict keyed
        # on metric would silently drop one and callers building a list would
        # render two widgets with the same key — the crash fixed in 37823bd.
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def _catalog(include_rates: bool, form_type: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in _load_question_rows():
        if row["key"] in _NON_METRIC_KEYS:
            continue
        if form_type and row["form_type"] != form_type.upper():
            continue
        out[row["key"]] = row["label"]
    if include_rates and not form_type:
        out.update(RATE_METRIC_LABELS)
    return out


def metric_options(include_rates: bool = True) -> dict[str, str]:
    """{metric_key: display label} for every active metric this mission tracks.

    This replaces the three hardcoded METRIC_OPTIONS dicts. Returns an empty
    dict when QUESTIONS_CONFIG is unreadable — callers must render "no metrics
    configured" rather than falling back to a baked-in list, because a stale
    baked-in list is exactly what produced a dashboard full of metrics CCSM
    does not collect.
    """
    return _catalog(include_rates=include_rates, form_type=None)


def nightly_metrics() -> dict[str, str]:
    """Metrics asked on the nightly form — one value per area per DAY."""
    return _catalog(include_rates=False, form_type="NIGHTLY")


def weekly_metrics() -> dict[str, str]:
    """Metrics asked on the weekly form — one value per area per WEEK.

    These cannot be bucketed by day: there is no daily grain to toggle to, and
    charting them as if there were produces one spike per week and six zeroes.
    """
    return _catalog(include_rates=False, form_type="WEEKLY")


def weekly_metric_keys() -> frozenset[str]:
    return frozenset(weekly_metrics())


def key_indicator_metrics() -> dict[str, str]:
    """The seven Key Indicators, "real" (achieved) values only.

    These are the mission's headline outcomes and the KI component of every
    area's score (SCORE_CONFIG, Score_Component = 'ki'). The matching `_meta`
    keys are the companionship's own GOAL for the week, so they belong beside a
    real value as a target — never in a list of achieved results, and never
    added to one. See [[feedback-projection-never-beside-a-goal]] for the same
    distinction elsewhere.
    """
    return {k: v for k, v in weekly_metrics().items() if k.endswith("_real")}


def goal_metric_key(real_key: str) -> str | None:
    """The `_meta` (goal) counterpart of a `_real` KI key, if the mission
    collects one."""
    if not real_key.endswith("_real"):
        return None
    meta = real_key[: -len("_real")] + "_meta"
    return meta if meta in weekly_metrics() else None


def is_rate_metric(key: str) -> bool:
    """Rates and scores are averaged across areas, never summed."""
    return key in RATE_METRICS


def metric_data_type(key: str) -> str:
    """QUESTIONS_CONFIG's Data_Type for a metric: NUMBER, YESNO, CHOICE, DATE.
    Empty string for a key the sheet does not define (the derived rates)."""
    for row in _load_question_rows():
        if row["key"] == key:
            return row["data_type"]
    return ""


def non_numeric_metrics() -> frozenset[str]:
    """Metrics that carry no summable number.

    `effort` is CHOICE — the missionary picks Todo / La mayor parte / Algo, and
    the agents convert it through ccsmEffortScore(). `exchanges` is YESNO.
    DAILY_LOG stores the raw word, and get_daily_log() runs every metric column
    through _num(), which coerces an unparseable value to NaN and then FILLS IT
    WITH 0. So a CHOICE metric silently reads as a hard zero downstream, and
    nothing about the value itself reveals that it was never a number.

    Anything summing or scoring metrics must consult this rather than inspect
    values: an area that answered "Todo" every single day would otherwise be
    scored as having given no effort at all.
    """
    return frozenset(
        row["key"] for row in _load_question_rows()
        if row["data_type"] in ("CHOICE", "YESNO", "DATE")
    )


def format_metric_label(key: str, lang: str = "es") -> str:
    """Display label for a metric key.

    Order: the sheet's own display name (authoritative), then the derived-rate
    label, then a Title Case fallback so an unknown key still renders as
    something a human can read instead of a bare snake_case token.

    In English mode EN_LABEL_OVERRIDES is preferred, but only for keys the
    catalogue already contains — see that map's note on why it cannot define
    the vocabulary.
    """
    key = str(key)
    if lang == "en" and key in EN_LABEL_OVERRIDES:
        return EN_LABEL_OVERRIDES[key]
    catalog = metric_options(include_rates=True)
    if key in catalog:
        return catalog[key]
    if key in RATE_METRIC_LABELS:
        return RATE_METRIC_LABELS[key]
    return key.replace("_", " ").title()


def clear_cache() -> None:
    """Drop the cached QUESTIONS_CONFIG read. Call after the Maintenance page
    writes that tab, or the catalogue serves the pre-edit vocabulary for up to
    five minutes."""
    _load_question_rows.clear()
