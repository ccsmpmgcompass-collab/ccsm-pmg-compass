"""The four conversion rates, and how far each one is from its target.

`CCSM_Agent1A.gs` computes four ratios every Monday, each with a target in
`AGENT_CONFIG`, a Preach My Gospel page and a scripture. They are the sharpest
thing in the dataset and, until now, they appeared on no page of the dashboard
(audit H2). Live on 2026-08-21 they said, in one line, what nothing else on the
Panel could: 4.104 attempts became 673 lessons and 65 baptismal invitations —
the mission teaches well and does not invite. Baptismal invitation sits at 9,7%
against a 25% target, 39% of goal.

The agent keeps them in Script Properties for the coaching emails and never
writes them to a tab, so the dashboard has to derive them itself. This module is
that derivation, kept pure — no Streamlit, no sheet — so it can be tested
directly and reused by any page that needs the same four numbers.

Three decisions are baked in here, each one a place where a reasonable
alternative gives a different answer:

  * **A mission rate is the ratio of mission totals**, not the average of the
    areas' own rates. Both were computed live: ratio-of-totals gives 46,4 /
    51,4 / 16,4 / 9,7; averaging the 40 areas gives 50,6 / 60,0 / 20,4 / 12,4
    and flips two of the four from *under target* to *on target*. The area
    medians — 47,5 / 55,7 / 16,2 / 6,7 — sit far below those means, which is
    the tell: a handful of low-volume areas with lucky ratios drag the average
    up. The ratio of totals is also what Agent1A's own per-area arithmetic
    implies and what reconciles with the counts printed elsewhere on the page.

    This does NOT contradict `metric_catalog.is_rate_metric()`, which says rate
    metrics are averaged across areas and never summed. That rule governs a
    column that already HOLDS per-area rates, where summing 40 percentages is
    meaningless. Here the input is raw counts and the ratio is taken once, at
    the top.

  * **Change over time is measured in percentage POINTS, not percent.** A rate
    is already basis-free, so `period_delta`'s day-scaling has nothing to
    normalize; and a percent change of a percentage is the classic way to
    mislead — close_rate moving 7,4% → 9,7% is "up 31%", which sounds like the
    mission transformed and means it invited two more people per hundred
    lessons. Same reasoning kept §7's compliance percentages out of item 4.

  * **A denominator of zero is no reading, not zero percent.** A window with no
    lessons in it has no baptismal-invitation rate. Returning 0.0 there would
    report a failure the mission never had the chance to have.

Percentages are on the 0-100 scale throughout, matching `fmt_percent`. The
targets in `AGENT_CONFIG` are stored as 0-1 fractions and converted on the way
in, once, in `target_pct`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.period_delta import (
    FLAT, UP, DOWN, POINTS, MIN_COMPARABLE_DAYS, NEUTRAL_BAND_POINTS,
    point_delta,
)


@dataclass(frozen=True)
class RateMetric:
    """One derived rate: what divides what, and what it is aiming at.

    ``key`` matches `A1A_RATE_METRICS` in `CCSM_Agent1A.gs`, so the display
    label resolves through the ordinary metric catalogue in both languages.
    ``numerator`` / ``denominator`` are DAILY_LOG column names.
    ``default_target`` is a 0-1 fraction, exactly as the agent declares it, and
    is used only when `AGENT_CONFIG` has no row for ``config_key``.
    """

    key: str
    numerator: str
    denominator: str
    config_key: str
    default_target: float


#: The four true fraction rates, in funnel order. Mirrors A1A_RATE_METRICS in
#: CCSM_Agent1A.gs and is held to it by tests/test_rate_metrics.py.
#:
#: The agent declares a fifth "rate", effort_score, which is deliberately absent:
#: it has no num/den (it is a direct 1-3 weighted average of Todo / La mayor
#: parte / Algo), it does not render as a percentage, and effort already has two
#: sections of its own further down the Panel. The agent excludes it from its own
#: A1A_FRACTION_RATE_KEYS map for the first of those reasons.
RATE_METRICS: tuple[RateMetric, ...] = (
    RateMetric("contact_rate", "contacts_made", "contacts_attempted",
               "CONTACT_RATE_TARGET", 0.50),
    RateMetric("mc_rate", "meaningful_conversations", "contacts_made",
               "MC_RATE_TARGET", 0.50),
    RateMetric("lesson_rate", "friend_lessons", "contacts_attempted",
               "LESSON_RATE_TARGET", 0.20),
    RateMetric("close_rate", "baptismal_invitations", "friend_lessons",
               "CLOSE_RATE_TARGET", 0.25),
)

#: Keyed lookup for callers that have a metric key rather than the object.
RATE_METRICS_BY_KEY: dict[str, RateMetric] = {m.key: m for m in RATE_METRICS}


def _num(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out  # NaN


def mission_rate(totals: dict, metric: RateMetric) -> float | None:
    """``metric`` as a 0-100 percentage of ``totals``, or None if unreadable.

    ``totals`` is a metric-keyed dict of mission sums — `period_delta`'s
    `window_totals` produces exactly this shape.

    Returns None when the denominator is missing, zero or not a number. That is
    "no reading", and the caller must render it as such: a week in which the
    mission taught no lessons has no baptismal-invitation rate, and printing
    0,0% would state a result it never had the chance to produce.
    """
    if not totals:
        return None
    den = _num(totals.get(metric.denominator))
    if den is None or den <= 0:
        return None
    num = _num(totals.get(metric.numerator))
    if num is None:
        return None
    return num / den * 100.0


def target_pct(config: dict, metric: RateMetric) -> float:
    """``metric``'s target as a 0-100 percentage.

    `AGENT_CONFIG` stores these as 0-1 fractions (`CONTACT_RATE_TARGET` = 0.5).
    A missing, blank or unparseable row falls back to the agent's own declared
    default rather than to zero — a target of zero would paint every rate as
    comfortably met.
    """
    raw = _num((config or {}).get(metric.config_key))
    if raw is None or raw <= 0:
        raw = metric.default_target
    return raw * 100.0


def pct_of_target(value: float | None, target: float) -> float | None:
    """How much of its target a rate reached, as a percentage. None if unreadable."""
    if value is None or not target:
        return None
    return value / target * 100.0


def rate_row(metric: RateMetric, current: dict, prior: dict, config: dict,
             *, current_days: float = 0, prior_days: float = 0,
             min_days: int = MIN_COMPARABLE_DAYS,
             neutral_band: float = NEUTRAL_BAND_POINTS) -> dict:
    """Everything the page needs to draw one rate, in one dict.

    ``current`` / ``prior`` are window totals; ``current_days`` / ``prior_days``
    are how many days of real reporting each window holds, used only to decide
    whether a change may be stated at all. Neither figure is scaled by them —
    see the module docstring on why a rate needs no basis normalization.

    Keys: ``key``, ``value`` (0-100 or None), ``target`` (0-100),
    ``pct_of_target`` (or None), ``numerator`` / ``denominator`` (the counts
    behind the ratio, for the arithmetic table), ``prior`` (0-100 or None) and
    ``change`` (a `period_delta`-shaped dict in points, or None).
    """
    value = mission_rate(current, metric)
    prior_value = mission_rate(prior, metric)
    target = target_pct(config, metric)
    return {
        "key": metric.key,
        "metric": metric,
        "value": value,
        "target": target,
        "pct_of_target": pct_of_target(value, target),
        "numerator": _num((current or {}).get(metric.numerator)) or 0.0,
        "denominator": _num((current or {}).get(metric.denominator)) or 0.0,
        "prior": prior_value,
        "change": point_delta(value, prior_value,
                              current_basis=current_days,
                              prior_basis=prior_days,
                              min_basis=min_days,
                              neutral_band=neutral_band),
    }


def rate_rows(current: dict, prior: dict, config: dict, **kwargs) -> list[dict]:
    """`rate_row` for all four rates, in funnel order."""
    return [rate_row(m, current, prior, config, **kwargs) for m in RATE_METRICS]


def worst_rate(rows: list[dict]) -> dict | None:
    """The readable rate furthest below its target, or None if none is readable.

    Item 8 (the verdict line) needs exactly this, and so does anything else that
    wants to name the mission's weakest link without re-deriving the ranking.
    Ties break on funnel order, which puts the earlier stage first — the one
    whose repair changes the most downstream.
    """
    readable = [r for r in rows if r.get("pct_of_target") is not None]
    if not readable:
        return None
    return min(readable, key=lambda r: r["pct_of_target"])


__all__ = [
    "RateMetric", "RATE_METRICS", "RATE_METRICS_BY_KEY",
    "mission_rate", "target_pct", "pct_of_target",
    "rate_row", "rate_rows", "worst_rate",
    "POINTS", "UP", "FLAT", "DOWN",
]
