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

# Display labels for all 19 nightly metrics + 5 weekly KIs
METRIC_LABELS: dict[str, str] = {
    "nm_lessons":             "NM Lessons",
    "member_lessons":         "Mate",
    "rc_lessons":             "RC Lessons",
    "la_lessons":             "LA Lessons",
    "lsi_given":              "LSI Given",
    "lsi_followups":          "LSI Follow-Ups",
    "new_found":              "New",
    "online_referrals":       "Online Referrals",
    "nm_doors":               "NM Attempted",
    "nm_contacted":           "NM Contacted",
    "nm_meaningful":          "Meaningful Contacts",
    "mmm_sent":               "MMM Sent",
    "la_Attempt":             "LA Members Attempted",
    "fellowshipper_Attempt":  "Fellowshipper Attempted",
    "aux_Attempt":            "Aux/Coord Attempted",
    "info_Attempt":           "Informational Attempted",
    "locos_Attempt":          "LOCOS Attempted",
    "referrals_today":        "Referrals Today",
    "nm_texts":               "NM Texts Sent",
    # Weekly KIs — short KI names; the metric DROPDOWNS render the long
    # "Descriptive Title (ABBREV)" from METRIC_OPTIONS instead (see Goals /
    # Breakdowns). These short forms feed compact tiles/charts/tables.
    "pew":         "Pew",
    "date_metric": "Date",
    "gate":        "Gate",
    "renew":       "Renew",
    "rc_total":    "RC Total",
}

# Display labels for mission-goal keys (outcome metrics, not nightly inputs)
GOAL_LABELS: dict[str, str] = {
    "baptisms":                  "Baptisms",
    "confirmations":             "Confirmations",
    "on_date":                   "Date for Baptism",
    "at_sacrament":              "Potential Member at Church",
    "new_people_to_teach":       "New People Found",
    "rc_at_church":              "Recent Convert Attendance",
    "members_nonmember_lessons": "Members at Non-Member Lessons",
}

# Maps a mission-goal key to the KI/nightly metric that represents the actual
GOAL_TO_ACTUAL: dict[str, str] = {
    "baptisms":                  "gate",
    "confirmations":             "gate",
    "on_date":                   "date_metric",
    "at_sacrament":              "pew",
    "new_people_to_teach":       "new_found",
    "rc_at_church":              "renew",
    "members_nonmember_lessons": "member_lessons",
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
