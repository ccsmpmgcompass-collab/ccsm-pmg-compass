"""
flavor_loader.py
Loads the active mission flavor from MISSION_FLAVOR env var.
Exposes a module-level `flavor` singleton used by all pages.

The flavor file supplies PRESENTATION only — display name, colours, coaching
tone. It does NOT supply the metric vocabulary: those properties read the live
QUESTIONS_CONFIG / SCORE_CONFIG instead (see FlavorConfig below for why). With
MISSION_FLAVOR unset the loader picks member_referral.json, which is Utah
Provo's flavor, so anything sourced from this file reaches CCSM as Provo's.
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

    # ── Metric vocabulary — the SHEET decides, never this JSON ────────────────
    #
    # These four properties used to read the flavor file, falling back to Utah
    # Provo's keys. Both halves of that were wrong for a live mission:
    #
    #   * MISSION_FLAVOR is unset here, so load_flavor() picks
    #     member_referral.json — Provo's own flavor. It DECLARES
    #     weekly_metrics/kpi_highlights/metric_groups as nm_lessons, lsi_given,
    #     pew, gate, locos_Attempt … so the fallbacks never even ran. Every
    #     consumer (the Dashboard KI row, Goals' KEY_METRICS, Scores' Daily
    #     Activity groups) was handed Provo's vocabulary against CCSM's data,
    #     and because every call site is `.get(key, key)` or `[c for c in cols
    #     if c in df.columns]`, that renders as zeroes and raw keys — never an
    #     error.
    #   * The fallbacks were a fifth hardcoded copy of the same dead catalogue.
    #
    # A flavor file describes a mission being SET UP (coaching tone, colours,
    # which questions to seed onto the forms). Once QUESTIONS_CONFIG exists it
    # is the only honest answer to "what does this mission measure", and it is
    # what the Apps Script agents read. So these read the catalogue and ignore
    # the JSON entirely — which also means dropping a differently-wrong flavor
    # file in place cannot resurrect this bug.
    #
    # Empty is a legitimate answer (unreadable tab, mission mid-setup) and must
    # stay empty: consumers render "no metrics configured". A baked-in default
    # here is exactly how the app came to display a mission's worth of metrics
    # nobody collects.

    @property
    def nightly_metrics(self) -> list[str]:
        from app.config.metric_catalog import nightly_metrics
        return list(nightly_metrics())

    @property
    def weekly_metrics(self) -> list[str]:
        from app.config.metric_catalog import weekly_metrics
        return list(weekly_metrics())

    @property
    def kpi_highlights(self) -> list[str]:
        """The headline metrics for the Dashboard's KPI row and Goals' key
        metrics: CCSM's seven weekly Key Indicators.

        `_real` only. The matching `_meta` keys are the companionship's own
        goal for the week — a target, not an achievement, and never a headline
        number. See [[feedback-projection-never-beside-a-goal]].
        """
        from app.config.metric_catalog import key_indicator_metrics
        return list(key_indicator_metrics())

    @property
    def nightly_highlights(self) -> list[str]:
        """Headline metrics for the NIGHTLY-form sections — the mission-total
        KPI row and the zone leaderboard, both of which read 7-day figures out
        of DASHBOARD_SUMMARY.

        Distinct from kpi_highlights: those are weekly Key Indicators and have
        no 7-day nightly figure at all, so pointing a nightly section at them
        would swap one empty row for another.

        Sourced from SCORE_CONFIG's `effort` component — the one place the
        mission states which nightly numbers it holds areas to, and the same
        metrics AGENT_CONFIG carries GOAL_* targets for, so each tile can show
        a goal beside its value. Non-numeric metrics are dropped: CCSM weights
        `effort` (a CHOICE question) at 0.3, and a headline tile reading "0" for
        a metric answered in words is worse than no tile.

        Falls back to the first few numeric nightly metrics if SCORE_CONFIG is
        unreadable — still the mission's own vocabulary, never another's.
        """
        from app.config.metric_catalog import nightly_metrics, non_numeric_metrics
        nightly = nightly_metrics()
        skip = non_numeric_metrics()

        try:
            from app.db.queries import get_score_component_weights
            scored = [
                k for k, w in get_score_component_weights("effort", "ALL").items()
                if w and k in nightly and k not in skip
            ]
        except Exception:
            scored = []

        if scored:
            return scored
        return [k for k in nightly if k not in skip][:5]

    @property
    def featured_goals(self) -> list[str]:
        return list(GOAL_LABELS.keys())

    @property
    def metric_groups(self) -> dict[str, list[str]]:
        """Named groupings of nightly metrics.

        QUESTIONS_CONFIG has no category column, so a mission has no way to
        declare these — and Provo's five (Teaching / Member Work / Finding /
        Contacting / Support Attempts) name nothing CCSM collects. Empty is the
        truthful answer; consumers group by the catalogue's own Display_Order
        instead of inventing categories the mission never asked for.
        """
        return {}

    @property
    def scoring_weights(self) -> dict[str, float]:
        """Effectiveness composition weights: {effort, skill, ki}.

        Read from SCORE_CONFIG's second section, which is the same row
        CCSM_AgentScores.gs uses to combine the three components — so the
        dashboard explains the score the agent actually computed. CCSM's row is
        0.33/0.33/0.34; the old flavor default was Provo's 0.30/0.40/0.30 and
        silently reweighted every Effectiveness figure the app recomputed.

        Falls back to an even split, not to any mission's numbers: with no
        configuration the only defensible statement is that the three
        components count the same.
        """
        from app.db.queries import get_effectiveness_composition_weights
        try:
            return get_effectiveness_composition_weights()
        except Exception:
            return {"effort": 1 / 3, "skill": 1 / 3, "ki": 1 / 3}

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
