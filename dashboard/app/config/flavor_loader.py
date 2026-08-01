"""
flavor_loader.py
Loads the active mission flavor from MISSION_FLAVOR env var.
Exposes a module-level `flavor` singleton used by all pages.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_FLAVORS_DIR = Path(__file__).parent / "flavors"

from collections.abc import Mapping


class _LiveMetricLabels(Mapping):
    """Metric key -> display label, read from the live QUESTIONS_CONFIG.

    This was a hardcoded dict of Utah Provo's metrics — nm_lessons, lsi_given,
    locos_Attempt, pew, gate, renew, rc_total and the rest — inherited with the
    fork and the FOURTH copy of that vocabulary in this app (the others were
    app/config/metrics.py, app/breakdowns_engine.py and
    app/utils/area_helpers.py, all now sourced from app/config/metric_catalog).

    Because every call site is `METRIC_LABELS.get(key, key)`, a catalogue full
    of keys CCSM does not collect did not raise anything — it silently fell
    through to the raw key, so charts, tiles and table headers across the
    Dashboard, Scores and Goals pages rendered `meaningful_conversations`
    instead of "Conversaciones Significativas".

    Implemented as a lazy Mapping rather than a dict so it can be built at USE
    time (there is no Streamlit session or sheet at import time) while keeping
    every existing `.get()` / `in` / iteration call site working unchanged.
    """

    def _data(self) -> dict[str, str]:
        try:
            from app.config.metric_catalog import metric_options
            from app.i18n import get_lang
            from app.config.metric_catalog import EN_LABEL_OVERRIDES
            labels = dict(metric_options())
            if get_lang() == "en":
                labels.update({k: v for k, v in EN_LABEL_OVERRIDES.items()
                               if k in labels})
            return labels
        except Exception:
            # Never let a label lookup take down a page that was only drawing
            # an axis title. Callers all pass a fallback of the key itself.
            return {}

    def __getitem__(self, key):
        return self._data()[key]

    def __iter__(self):
        return iter(self._data())

    def __len__(self):
        return len(self._data())


#: Display labels for every metric the mission actually collects.
METRIC_LABELS: Mapping = _LiveMetricLabels()

# Display labels for mission-goal keys (outcome metrics, not nightly inputs).
# These are the dashboard's own goal vocabulary, not form questions, so they
# stay declared here — but they now name outcomes CCSM actually tracks.
GOAL_LABELS: dict[str, str] = {
    "baptisms":                  "Bautismos",
    "confirmations":             "Confirmaciones",
    "on_date":                   "Amigos con Fecha Bautismal",
    "at_sacrament":              "Amigos en la Reunión Sacramental",
    "new_people_to_teach":       "Nuevas Personas Encontradas",
    "rc_at_church":              "Conversos Recientes en la Iglesia",
    "members_nonmember_lessons": "Lecciones con Miembros",
}

# Maps a mission-goal key to the Key Indicator that carries its ACTUAL value.
#
# Remapped from Provo's gate/date_metric/pew/new_found/renew/member_lessons —
# none of which exist in CCSM's data, so every goal on the Goals page compared
# its target against a column that was never there and read as 0/N forever.
# CCSM's actuals are the weekly form's seven `ki_*_real` values.
#
# `baptisms` and `confirmations` both point at ki_baptized_confirmed_real
# because CCSM's weekly form asks the two as ONE question ("Bautizados y
# confirmados"). That is the mission's own definition, not a shortcut — do not
# "fix" it by inventing a separate confirmations metric that no form collects.
GOAL_TO_ACTUAL: dict[str, str] = {
    "baptisms":                  "ki_baptized_confirmed_real",
    "confirmations":             "ki_baptized_confirmed_real",
    "on_date":                   "ki_baptismal_date_real",
    "at_sacrament":              "ki_friends_sacrament_real",
    "new_people_to_teach":       "ki_new_people_real",
    "rc_at_church":              "ki_rc_at_church_real",
    "members_nonmember_lessons": "ki_member_lessons_real",
}


class FlavorConfig:
    def __init__(self, data: dict) -> None:
        self._d = data

    @property
    def id(self) -> str:
        return self._d["id"]

    @property
    def display_name(self) -> str:
        return self._d.get("display_name", self.id)

    @property
    def nightly_metrics(self) -> list[str]:
        return self._d.get("nightly_metrics", [])

    @property
    def weekly_metrics(self) -> list[str]:
        return self._d.get("weekly_metrics", ["pew", "date_metric", "gate", "renew", "rc_total"])

    @property
    def kpi_highlights(self) -> list[str]:
        return self._d.get("kpi_highlights", ["nm_lessons", "new_found"])

    @property
    def featured_goals(self) -> list[str]:
        return self._d.get("featured_goals", list(GOAL_LABELS.keys()))

    @property
    def metric_groups(self) -> dict[str, list[str]]:
        return self._d.get("metric_groups", {})

    @property
    def scoring_weights(self) -> dict[str, float]:
        """Effectiveness composition weights: {effort, skill, ki}."""
        return self._d.get("scoring_weights", {"effort": 0.30, "skill": 0.30, "ki": 0.40})

    @property
    def weekly_ki_patterns(self) -> dict[str, str]:
        return self._d.get("weekly_ki_patterns", {
            "(Pew)": "pew", "(Date)": "date_metric", "(Gate)": "gate",
            "(Renew)": "renew", "(Total)": "rc_total",
        })

    def label(self, key: str) -> str:
        return METRIC_LABELS.get(key, GOAL_LABELS.get(key, key))


def load_flavor(flavor_id: str | None = None) -> FlavorConfig:
    fid = flavor_id or os.environ.get("MISSION_FLAVOR", "member_referral")
    path = _FLAVORS_DIR / f"{fid}.json"
    if not path.exists():
        path = _FLAVORS_DIR / "member_referral.json"
    with open(path, encoding="utf-8") as f:
        return FlavorConfig(json.load(f))


# Module-level singleton — imported by all pages
flavor = load_flavor()
