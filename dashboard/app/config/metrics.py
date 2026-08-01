"""
app/config/metrics.py
────────────────────────────────────────────────────────────────────────────────
Compatibility shim. The metric catalogue now lives in
`app/config/metric_catalog.py` and is GENERATED from the live QUESTIONS_CONFIG
tab rather than written down here.

What used to be here was Utah Provo's vocabulary, inherited with the fork:
lsi_given, lsi_followups, nm_doors, nm_texts, nm_contacted, nm_meaningful,
nm_lessons, pew, gate, renew, date_metric, la_lessons, locos_Attempt,
fellowshipper_Attempt, aux_Attempt, info_Attempt, online_referrals. Not one is a
question on a CCSM form — CCSM does not run Love/Share/Invite at all — and the
same list was duplicated in `breakdowns_engine.py` and `area_helpers.py`, so the
three could drift from each other as well as from the mission.

`METRIC_OPTIONS` is deliberately a FUNCTION now, not a dict. A module-level dict
would have to be built at import time, when there is no Streamlit session and no
sheet to read; making it a call is what forces every consumer to fetch the
catalogue at use time, which is the whole point of generating it.
"""

from app.config.metric_catalog import (  # noqa: F401  (re-exported)
    DAILY_META,
    RATE_METRICS,
    SCORE_LABELS,
    format_metric_label,
    key_indicator_metrics,
    metric_options,
    nightly_metrics,
    weekly_metric_keys,
    weekly_metrics,
)

#: Kept as the old name so existing imports read naturally, but it is the
#: generated catalogue — call it, don't subscript it.
METRIC_OPTIONS = metric_options

#: Metrics collected only on the weekly form: one value per area per WEEK.
#: Replaces the old WF_KEYS = {"pew", "date_metric", "gate", "renew",
#: "rc_total"} — five Provo keys CCSM has never collected.
WF_KEYS = weekly_metric_keys
