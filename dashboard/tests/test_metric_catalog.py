"""The metric vocabulary must be CCSM's, and must come from the sheet.

Two separate properties are asserted here.

1. The catalogue is GENERATED. Feed it a QUESTIONS_CONFIG and that is exactly
   what comes out — no baked-in additions, no baked-in survivors. A catalogue
   that merged a hardcoded list with the sheet would pass a naive "does it
   contain X" test while still showing metrics CCSM does not collect.

2. The five derived rate metrics, which have no QUESTIONS_CONFIG row and so
   must be declared in Python, still match CCSM_Agent1A.gs. That is a genuine
   cross-language duplication and the only honest way to hold it together is to
   parse the .gs file and compare. Without this test the Python copy would
   drift the moment anyone edits the agent, which is the exact failure this
   whole module exists to end.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from app.config import metric_catalog as mc

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Snapshot of the LIVE QUESTIONS_CONFIG, pulled read-only by
#: dashboard/tools/probe_live.py. Several assertions below have to run against
#: what the real sheet holds rather than this file's small fake — "does the
#: agent score a metric the mission collects" is only a real question when both
#: sides are real. Re-pull with:
#:   venv\Scripts\python.exe tools\probe_live.py json ..\tests\live\live_form_headers.json \
#:       NIGHTLY_FORM_RAW WEEKLY_FORM_RAW QUESTIONS_CONFIG
_LIVE_SNAPSHOT = REPO_ROOT / "tests" / "live" / "live_form_headers.json"


def _live_question_keys() -> set[str]:
    """Every Metric_Key in the live QUESTIONS_CONFIG snapshot, active or not."""
    import json

    if not _LIVE_SNAPSHOT.exists():
        pytest.skip(f"live snapshot missing: {_LIVE_SNAPSHOT}")
    grid = json.loads(_LIVE_SNAPSHOT.read_text(encoding="utf-8").lstrip("﻿"))
    rows = grid.get("QUESTIONS_CONFIG") or []
    if not rows:
        pytest.skip("live snapshot has no QUESTIONS_CONFIG")
    header = [str(c).strip() for c in rows[0]]
    ki = header.index("Metric_Key")
    return {str(r[ki]).strip() for r in rows[1:] if len(r) > ki and str(r[ki]).strip()}

# Every Provo key found in the three hardcoded catalogues this module replaced.
# None is a question on any CCSM form; CCSM does not run Love/Share/Invite.
PROVO_KEYS = [
    "lsi_given", "lsi_followups", "nm_doors", "nm_texts", "nm_contacted",
    "nm_meaningful", "nm_lessons", "pew", "gate", "renew", "date_metric",
    "la_lessons", "locos_Attempt", "fellowshipper_Attempt", "aux_Attempt",
    "info_Attempt", "online_referrals", "new_found", "member_lessons",
    "referrals_today", "la_Attempt", "mmm_sent", "door_lesson_rate",
    "nm_knocked_rate", "rc_total",
]

FAKE_QUESTIONS = pd.DataFrame([
    {"Metric_Key": "report_date", "Metric_Display_Name": "Fecha del Informe",
     "Form_Type": "NIGHTLY", "Data_Type": "DATE", "Active": "TRUE"},
    {"Metric_Key": "contacts_attempted", "Metric_Display_Name": "Intentos de Contacto",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "contacts_made", "Metric_Display_Name": "Contactos",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "effort", "Metric_Display_Name": "Nivel de Esfuerzo",
     "Form_Type": "NIGHTLY", "Data_Type": "CHOICE", "Active": "TRUE"},
    {"Metric_Key": "retired_question", "Metric_Display_Name": "Pregunta Retirada",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "FALSE"},
    {"Metric_Key": "report_date", "Metric_Display_Name": "Fecha del Informe Semanal",
     "Form_Type": "WEEKLY", "Data_Type": "DATE", "Active": "TRUE"},
    {"Metric_Key": "ki_new_people_real", "Metric_Display_Name": "Nuevas Personas (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_new_people_meta", "Metric_Display_Name": "Nuevas Personas (Meta)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
])


@pytest.fixture(autouse=True)
def _fake_questions_config(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return FAKE_QUESTIONS.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    mc.clear_cache()
    yield
    mc.clear_cache()


# ── 1. Generated, not baked in ────────────────────────────────────────────────

def test_catalogue_is_exactly_what_the_sheet_says():
    """Not "contains the right keys" — IS the right keys. A hardcoded survivor
    would show up here as an extra."""
    assert set(mc.metric_options(include_rates=False)) == {
        "contacts_attempted", "contacts_made", "effort",
        "ki_new_people_real", "ki_new_people_meta",
    }


def test_no_provo_metric_survives_anywhere_in_the_catalogue():
    everything = (
        set(mc.metric_options())
        | set(mc.nightly_metrics())
        | set(mc.weekly_metrics())
        | set(mc.RATE_METRICS)
        | set(mc.EN_LABEL_OVERRIDES)
    )
    leaked = sorted(set(PROVO_KEYS) & everything)
    assert leaked == [], f"Provo metric vocabulary still present: {leaked}"


def test_inactive_questions_are_excluded():
    assert "retired_question" not in mc.metric_options()


def test_report_date_is_not_a_metric():
    """It is the date a report covers, not a measurement — and it is the key
    that appears on BOTH forms, which crashed the Goals page (37823bd)."""
    assert "report_date" not in mc.metric_options()
    assert "report_date" not in mc.nightly_metrics()
    assert "report_date" not in mc.weekly_metrics()


def test_a_key_on_both_forms_appears_once():
    keys = list(mc.metric_options())
    assert len(keys) == len(set(keys))


def test_labels_come_from_the_sheet_not_from_code():
    """Renaming a question on the Maintenance page must change the dashboard."""
    assert mc.metric_options()["contacts_made"] == "Contactos"

    renamed = FAKE_QUESTIONS.copy()
    renamed.loc[renamed["Metric_Key"] == "contacts_made",
                "Metric_Display_Name"] = "Contactos Efectivos"
    import app.db.sheets_client as sc
    sc._read_tab_cached = lambda tab, header_marker=None: (
        renamed.copy() if tab == "QUESTIONS_CONFIG" else pd.DataFrame())
    mc.clear_cache()
    assert mc.metric_options()["contacts_made"] == "Contactos Efectivos"


def test_empty_questions_config_yields_an_empty_catalogue_not_a_fallback():
    """The dangerous failure would be quietly serving a baked-in list when the
    sheet is unreadable — that is how a dead vocabulary survives a rewrite."""
    import app.db.sheets_client as sc
    sc._read_tab_cached = lambda tab, header_marker=None: pd.DataFrame()
    mc.clear_cache()
    assert mc.metric_options(include_rates=False) == {}


# ── 2. Form-type partitioning ─────────────────────────────────────────────────

def test_nightly_and_weekly_are_partitioned():
    assert set(mc.nightly_metrics()) == {"contacts_attempted", "contacts_made", "effort"}
    assert set(mc.weekly_metrics()) == {"ki_new_people_real", "ki_new_people_meta"}
    assert not set(mc.nightly_metrics()) & set(mc.weekly_metrics())


def test_key_indicators_are_real_values_only():
    """A `_meta` value is the companionship's GOAL for the week. Mixing it into
    a list of achieved results would double every KI and make a mission look
    twice as productive as it was."""
    assert set(mc.key_indicator_metrics()) == {"ki_new_people_real"}


def test_goal_counterpart_resolves_and_is_not_invented():
    assert mc.goal_metric_key("ki_new_people_real") == "ki_new_people_meta"
    assert mc.goal_metric_key("contacts_made") is None
    assert mc.goal_metric_key("ki_absent_real") is None


# ── 3. Rates ──────────────────────────────────────────────────────────────────

def test_rates_are_included_by_default_and_excluded_on_request():
    assert "contact_rate" in mc.metric_options()
    assert "contact_rate" not in mc.metric_options(include_rates=False)


def test_rate_metrics_are_never_summable():
    for k in mc.RATE_METRICS:
        assert mc.is_rate_metric(k)
    assert not mc.is_rate_metric("contacts_made")


def test_rate_metrics_match_agent1a():
    """THE anti-drift assertion.

    The five rate metrics are computed by CCSM_Agent1A.gs and have no
    QUESTIONS_CONFIG row, so Python has to declare them. That duplication is
    only safe if something checks it, so this parses A1A_RATE_METRICS out of
    the agent and compares keys AND display names.
    """
    src = (REPO_ROOT / "CCSM_Agent1A.gs").read_text(encoding="utf-8-sig")
    block = re.search(r"var A1A_RATE_METRICS = \[(.*?)\n\];", src, re.S)
    assert block, "A1A_RATE_METRICS not found in CCSM_Agent1A.gs — did it get renamed?"

    pairs = re.findall(
        r"\{\s*key:\s*'([^']+)'\s*,\s*display:\s*'([^']+)'", block.group(1))
    assert pairs, "parsed no key/display pairs out of A1A_RATE_METRICS"

    assert dict(pairs) == mc.RATE_METRIC_LABELS, (
        "RATE_METRIC_LABELS has drifted from CCSM_Agent1A.gs's A1A_RATE_METRICS.\n"
        f"  agent:  {dict(pairs)}\n"
        f"  python: {mc.RATE_METRIC_LABELS}"
    )


def test_every_scored_metric_is_one_the_mission_actually_collects():
    """CCSM_AgentScores.gs hardcodes the Effort and Skill weight maps. Scoring
    an area on a metric nobody collects silently drags that component toward
    zero for all 98 areas — the score still renders, it is just wrong, and
    nothing in the pipeline complains.

    (The KI map needs no check: ASC_KI_WEIGHTS is derived from
    CCSM_WEEKLY_QUESTIONS at runtime, so it cannot drift by construction.)

    Checked against the LIVE QUESTIONS_CONFIG snapshot, not this file's small
    fake, because the question is whether the real sheet and the real agent
    agree.
    """
    src = (REPO_ROOT / "CCSM_AgentScores.gs").read_text(encoding="utf-8-sig")
    scored: set[str] = set()
    for name in ("ASC_EFFORT_WEIGHTS", "ASC_SKILL_WEIGHTS"):
        block = re.search(rf"var {name} = \{{(.*?)\n\}};", src, re.S)
        assert block, f"{name} not found in CCSM_AgentScores.gs — renamed?"
        scored |= set(re.findall(r"^\s*(\w+):", block.group(1), re.M))
    assert scored, "parsed no scored metric keys"

    collected = _live_question_keys() | set(mc.RATE_METRICS)
    unknown = sorted(scored - collected)
    assert unknown == [], (
        f"CCSM_AgentScores.gs scores areas on metric(s) the mission does not "
        f"collect: {unknown}")


# ── 4. Labels ─────────────────────────────────────────────────────────────────

def test_spanish_label_is_the_default():
    assert mc.format_metric_label("contacts_made") == "Contactos"


def test_english_mode_uses_the_override():
    assert mc.format_metric_label("contacts_made", lang="en") == "Contacts Made"


def test_english_falls_back_to_spanish_rather_than_vanishing():
    """A key the override map has never heard of must still render."""
    assert mc.format_metric_label("ki_new_people_real", lang="en") == "Nuevas Personas (Real)"


def test_unknown_key_renders_readably():
    assert mc.format_metric_label("some_new_thing") == "Some New Thing"


def test_english_overrides_cannot_invent_a_metric():
    """The override map is display-only: it may rename a metric the sheet
    defines, never introduce one. Checked against the LIVE QUESTIONS_CONFIG
    snapshot — an entry for a key the mission does not collect is a Provo
    leftover wearing a new coat, and would be invisible in Spanish mode.
    """
    known = _live_question_keys() | set(mc.RATE_METRICS)
    stray = sorted(set(mc.EN_LABEL_OVERRIDES) - known)
    assert stray == [], (
        f"EN_LABEL_OVERRIDES names metric(s) that do not exist in the live "
        f"QUESTIONS_CONFIG: {stray}")


def test_every_live_metric_has_an_english_label():
    """The other direction. A missing entry degrades gracefully (Spanish shows)
    rather than crashing, so this is a completeness check, not a safety one —
    but a half-translated English mode is worse than an obviously absent one.
    """
    live = _live_question_keys() - {"report_date"}
    missing = sorted(live - set(mc.EN_LABEL_OVERRIDES))
    # The seven KI pairs read the same in both languages apart from
    # (Real)/(Meta), which are already understood; they are exempt by design.
    missing = [k for k in missing if not k.startswith("ki_")]
    assert missing == [], f"no English label for: {missing}"
