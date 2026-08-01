"""The Mission Assistant must not be taught Utah Provo's metrics.

The system prompt defined a glossary — "Pew [KI]: a friend attended sacrament
meeting", "Gate [KI]: a friend attended their own baptism", "Baptism pipeline
order: New Friend Found -> NM Lessons -> Date -> Gate -> Baptism" — and the
analytics context labelled its numbers the same way. None of those metrics
exists on a CCSM form.

This is worse than giving a model no glossary. A model handed confident
definitions for data it will never see produces fluent, confident answers about
things that did not happen, and a missionary reading them has no way to tell
those apart from real ones. The failure is indistinguishable from working.

The prompt also carried "**528** NM Lessons — led by **Kings Peak (71)**" as its
worked example of a good answer. Kings Peak is a Utah Provo ZONE. An example is
the strongest instruction in a prompt, so the model was being shown, in the one
place it imitates most closely, that inventing a plausible zone name is correct.
"""

import re

import pandas as pd
import pytest

import app.chat.gemini_chat as gc
from app.config import metric_catalog as mc

PROVO_METRIC_WORDS = [
    "NM Lessons", "NM Attempted", "LSI Given", "LSI Follow-Ups",
    "MMM Sent", "LOCOS", "Fellowshipper Attempted",
    "nm_lessons", "nm_doors", "lsi_given", "mmm_sent", "locos_Attempt",
    "new_found", "member_lessons", "rc_total", "date_metric",
]

# Utah Provo zone names. These must never reach the model: it will repeat them
# as though they were CCSM's.
PROVO_PLACES = ["Kings Peak", "Provo", "Orem", "Springville", "Payson"]

QUESTIONS = pd.DataFrame([
    {"Metric_Key": "contacts_attempted", "Metric_Display_Name": "Intentos de Contacto",
     "Form_Type": "NIGHTLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_new_people_real", "Metric_Display_Name": "Nuevas Personas (Real)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
    {"Metric_Key": "ki_new_people_meta", "Metric_Display_Name": "Nuevas Personas (Meta)",
     "Form_Type": "WEEKLY", "Data_Type": "NUMBER", "Active": "TRUE"},
])


@pytest.fixture(autouse=True)
def _sheets(monkeypatch):
    def fake(tab_name, header_marker=None):
        if tab_name == "QUESTIONS_CONFIG":
            return QUESTIONS.copy()
        return pd.DataFrame()

    monkeypatch.setattr("app.db.sheets_client._read_tab_cached", fake)
    mc.clear_cache()
    yield
    mc.clear_cache()


def _static_prompt_text() -> str:
    """Every module-level prompt string in gemini_chat."""
    return "\n".join(
        v for k, v in vars(gc).items()
        if isinstance(v, str) and not k.startswith("__") and len(v) > 200
    )


def test_no_provo_metric_vocabulary_in_the_static_prompt():
    text = _static_prompt_text()
    # Strip Python comments: several deliberately quote the old wording to
    # explain why it was removed, and those never reach the model.
    text = re.sub(r"^\s*#.*$", "", text, flags=re.M)
    leaked = sorted({w for w in PROVO_METRIC_WORDS if w in text})
    assert leaked == [], f"Provo metric vocabulary in the system prompt: {leaked}"


def test_no_provo_place_names_in_the_static_prompt():
    text = _static_prompt_text()
    leaked = sorted({p for p in PROVO_PLACES if p in text})
    assert leaked == [], (
        f"Utah Provo place name(s) in the system prompt: {leaked}. The model "
        f"will repeat these as if they were CCSM's zones."
    )


def test_source_file_carries_no_provo_metric_outside_comments():
    """The prompt is assembled from several strings; scan the file itself so a
    new one cannot reintroduce the vocabulary."""
    from pathlib import Path
    src = Path(gc.__file__).read_text(encoding="utf-8")
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    leaked = sorted({w for w in PROVO_METRIC_WORDS if w in code})
    assert leaked == [], f"Provo metric vocabulary in gemini_chat.py: {leaked}"


def test_key_metrics_come_from_the_mission_not_a_constant():
    keys = dict(gc._key_metrics())
    assert "ki_new_people_real" in keys
    assert keys["ki_new_people_real"] == "Nuevas Personas (Real)"
    assert not ({"nm_lessons", "new_found", "member_lessons"} & set(keys))


def test_key_metrics_exclude_goal_values():
    """`_meta` is the goal a companionship set, not an achievement. A
    leaderboard of goals would rank whoever aimed highest, not who did most."""
    assert "ki_new_people_meta" not in dict(gc._key_metrics())


def test_prompt_tells_the_model_real_and_meta_are_different():
    """The single most dangerous confusion available to this model: reporting a
    target as an accomplishment."""
    text = _static_prompt_text().lower()
    assert "_real" in text and "_meta" in text, \
        "the prompt must define the _real / _meta distinction"
    assert "never add" in text or "never report" in text, \
        "the prompt must forbid combining achieved values with goals"


def test_prompt_forbids_describing_unlisted_metrics():
    text = _static_prompt_text().lower()
    assert "metrics glossary" in text, \
        "the prompt must point the model at the generated glossary"
