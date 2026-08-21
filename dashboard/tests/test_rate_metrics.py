"""The four conversion rates — app/analytics/rate_metrics.py, and the percentage-
point comparison in app/analytics/period_delta.py that goes with them.

Audit finding H2: CCSM_Agent1A.gs computes four ratios with configured targets
and none of them appeared anywhere in the dashboard. The numbers used in these
tests are the live mission totals for 14–20 August 2026, so a change that breaks
the arithmetic breaks a test whose expected values can be checked against the
sheet by hand.
"""

import re
from pathlib import Path

import pytest

from app.analytics.period_delta import (
    DOWN, FLAT, MIN_COMPARABLE_DAYS, POINTS, UP, point_delta,
)
from app.analytics.rate_metrics import (
    RATE_METRICS, RATE_METRICS_BY_KEY, mission_rate, pct_of_target, rate_row,
    rate_rows, target_pct, worst_rate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Mission totals for the seven days ending 2026-08-20, read from DAILY_LOG.
LIVE = {
    "contacts_attempted": 4104.0,
    "contacts_made": 1903.0,
    "meaningful_conversations": 978.0,
    "friend_lessons": 673.0,
    "baptismal_invitations": 65.0,
}

#: The seven days before that. Only four of them are reporting days, which is
#: why nothing on the live page shows an arrow yet.
LIVE_PRIOR = {
    "contacts_attempted": 1757.0,
    "contacts_made": 834.0,
    "meaningful_conversations": 445.0,
    "friend_lessons": 310.0,
    "baptismal_invitations": 23.0,
}

TARGETS = {
    "CONTACT_RATE_TARGET": "0.5",
    "MC_RATE_TARGET": "0.5",
    "LESSON_RATE_TARGET": "0.2",
    "CLOSE_RATE_TARGET": "0.25",
}


# ── The anti-drift assertion ──────────────────────────────────────────────────

def test_rate_definitions_match_agent1a():
    """Numerators, denominators, config keys and default targets are declared in
    two languages. This parses the agent's own array and holds Python to it, the
    same way tests/test_metric_catalog.py already holds the display names.
    """
    src = (REPO_ROOT / "CCSM_Agent1A.gs").read_text(encoding="utf-8-sig")
    block = re.search(r"var A1A_RATE_METRICS = \[(.*?)\n\];", src, re.S)
    assert block, "A1A_RATE_METRICS not found in CCSM_Agent1A.gs — renamed?"

    # Each entry spans several lines; split on the key so one regex per field
    # does not have to span the whole object.
    entries = re.findall(
        r"\{\s*key:\s*'([^']+)'(.*?)\}", block.group(1), re.S)
    agent = {}
    for key, body in entries:
        num = re.search(r"num:\s*'([^']+)'", body)
        den = re.search(r"den:\s*'([^']+)'", body)
        cfg = re.search(r"configKey:\s*'([^']+)'", body)
        dft = re.search(r"defaultTarget:\s*([0-9.]+)", body)
        if not (num and den):
            continue  # effort_score — no num/den, deliberately not ours
        agent[key] = (num.group(1), den.group(1), cfg.group(1), float(dft.group(1)))

    assert agent, "parsed no fraction rates out of A1A_RATE_METRICS"
    ours = {m.key: (m.numerator, m.denominator, m.config_key, m.default_target)
            for m in RATE_METRICS}
    assert ours == agent, (
        "rate_metrics.RATE_METRICS has drifted from CCSM_Agent1A.gs.\n"
        f"  agent:  {agent}\n  python: {ours}")


def test_effort_score_is_not_a_conversion_rate():
    """The agent's fifth 'rate' has no num/den and is a 1-3 score, not a
    percentage. Including it would put a 2,75 on a row of percentages."""
    assert "effort_score" not in RATE_METRICS_BY_KEY


def test_rates_are_in_funnel_order():
    assert [m.key for m in RATE_METRICS] == [
        "contact_rate", "mc_rate", "lesson_rate", "close_rate"]


# ── mission_rate ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key, expected", [
    ("contact_rate", 46.4),
    ("mc_rate", 51.4),
    ("lesson_rate", 16.4),
    ("close_rate", 9.7),
])
def test_mission_rate_matches_the_live_numbers(key, expected):
    got = mission_rate(LIVE, RATE_METRICS_BY_KEY[key])
    assert round(got, 1) == expected


def test_a_rate_is_the_ratio_of_totals_not_the_mean_of_areas():
    """The decision this module exists to hold.

    Two areas, one large and one small. Ratio-of-totals says 20%; averaging the
    two areas' own rates says 55%, because the small area's 90% counts as much
    as the large one's 10%. Live, that difference flipped contact_rate and
    lesson_rate from under target to on target.
    """
    combined = {"contacts_made": 100 + 90, "contacts_attempted": 900 + 50}
    assert round(mission_rate(combined, RATE_METRICS_BY_KEY["contact_rate"]), 1) == 20.0
    area_mean = ((100 / 900) + (90 / 50)) / 2 * 100
    assert round(area_mean) == 96  # nothing like 20 — and not what we report


def test_zero_denominator_is_no_reading_not_zero_percent():
    """A week with no lessons has no baptismal-invitation rate. Reporting 0,0%
    would state a failure the mission never had the chance to have."""
    assert mission_rate({"friend_lessons": 0, "baptismal_invitations": 0},
                        RATE_METRICS_BY_KEY["close_rate"]) is None


def test_missing_columns_are_no_reading():
    assert mission_rate({}, RATE_METRICS_BY_KEY["contact_rate"]) is None
    assert mission_rate({"contacts_attempted": 100},
                        RATE_METRICS_BY_KEY["contact_rate"]) is None


def test_a_rate_may_exceed_its_target_without_being_capped():
    over = {"contacts_made": 900, "contacts_attempted": 1000}
    assert mission_rate(over, RATE_METRICS_BY_KEY["contact_rate"]) == 90.0


# ── Targets ───────────────────────────────────────────────────────────────────

def test_targets_convert_from_the_config_fraction_to_a_percentage():
    assert target_pct(TARGETS, RATE_METRICS_BY_KEY["contact_rate"]) == 50.0
    assert target_pct(TARGETS, RATE_METRICS_BY_KEY["close_rate"]) == 25.0


@pytest.mark.parametrize("config", [{}, {"CLOSE_RATE_TARGET": ""},
                                    {"CLOSE_RATE_TARGET": "0"},
                                    {"CLOSE_RATE_TARGET": "not a number"}])
def test_an_unusable_target_falls_back_to_the_agents_default(config):
    """Never to zero: a target of zero paints every rate as comfortably met."""
    assert target_pct(config, RATE_METRICS_BY_KEY["close_rate"]) == 25.0


def test_pct_of_target_names_the_mission_worst_number():
    """close_rate at 9,7 against 25 is 39% of goal — the single figure audit H2
    was written about, and the one that draws red on the goal bar."""
    rate = mission_rate(LIVE, RATE_METRICS_BY_KEY["close_rate"])
    assert round(pct_of_target(rate, 25.0)) == 39


def test_pct_of_target_is_none_when_there_is_no_reading():
    assert pct_of_target(None, 25.0) is None


# ── rate_row / rate_rows ──────────────────────────────────────────────────────

def test_rate_row_carries_the_counts_behind_the_ratio():
    """The expander prints the arithmetic, so the row has to hold it."""
    row = rate_row(RATE_METRICS_BY_KEY["close_rate"], LIVE, LIVE_PRIOR, TARGETS,
                   current_days=7, prior_days=7)
    assert row["numerator"] == 65.0
    assert row["denominator"] == 673.0
    assert round(row["value"], 1) == 9.7
    assert row["target"] == 25.0


def test_rate_rows_returns_all_four_in_order():
    rows = rate_rows(LIVE, LIVE_PRIOR, TARGETS, current_days=7, prior_days=7)
    assert [r["key"] for r in rows] == [m.key for m in RATE_METRICS]


def test_worst_rate_is_the_furthest_below_target():
    rows = rate_rows(LIVE, LIVE_PRIOR, TARGETS, current_days=7, prior_days=7)
    assert worst_rate(rows)["key"] == "close_rate"


def test_worst_rate_ignores_rates_with_no_reading():
    rows = rate_rows({"contacts_attempted": 100, "contacts_made": 10},
                     {}, TARGETS, current_days=7, prior_days=7)
    # Only contact_rate is readable; the other three divide by nothing.
    assert worst_rate(rows)["key"] == "contact_rate"


def test_worst_rate_is_none_when_nothing_is_readable():
    assert worst_rate(rate_rows({}, {}, TARGETS)) is None


# ── point_delta ───────────────────────────────────────────────────────────────

def test_a_rate_change_is_measured_in_points():
    d = point_delta(9.7, 7.4, current_basis=7, prior_basis=7)
    assert d["show"] == POINTS
    assert round(d["points"], 1) == 2.3
    assert d["direction"] == UP
    # NOT +31%, which is what a percent change of a percentage would have said.
    assert d["pct"] is None


def test_a_rate_is_never_scaled_by_its_window():
    """period_delta scales the prior side onto the current basis because a total
    grows with the days behind it. A ratio does not, so an uneven pair of
    windows must give the same answer as an even one."""
    even = point_delta(46.4, 47.5, current_basis=7, prior_basis=7)
    uneven = point_delta(46.4, 47.5, current_basis=7, prior_basis=5)
    assert even["points"] == uneven["points"]


def test_a_short_prior_window_refuses_the_comparison():
    """Four reporting days is the live case on 2026-08-21. A rate cannot be
    corrected for a short window the way a total can, only refused."""
    assert point_delta(46.4, 47.5, current_basis=7,
                       prior_basis=MIN_COMPARABLE_DAYS - 1) is None


def test_a_short_current_window_refuses_too():
    assert point_delta(46.4, 47.5, current_basis=MIN_COMPARABLE_DAYS - 1,
                       prior_basis=7) is None


def test_a_move_under_a_point_reads_as_flat():
    d = point_delta(46.4, 47.0, current_basis=7, prior_basis=7)
    assert d["direction"] == FLAT


def test_a_fall_over_a_point_reads_as_a_fall():
    d = point_delta(44.0, 47.5, current_basis=7, prior_basis=7)
    assert d["direction"] == DOWN
    assert round(d["points"], 1) == -3.5


def test_no_comparison_without_a_reading_on_both_sides():
    assert point_delta(None, 47.5, current_basis=7, prior_basis=7) is None
    assert point_delta(46.4, None, current_basis=7, prior_basis=7) is None


def test_rate_row_suppresses_the_change_on_the_live_short_window():
    """End to end on the live figures: 7 current reporting days against 4 prior
    ones, so the page shows no arrow and says why."""
    rows = rate_rows(LIVE, LIVE_PRIOR, TARGETS, current_days=7, prior_days=4)
    assert all(r["change"] is None for r in rows)


def test_rate_row_produces_the_change_once_the_window_fills():
    rows = rate_rows(LIVE, LIVE_PRIOR, TARGETS, current_days=7, prior_days=7)
    by_key = {r["key"]: r for r in rows}
    # contact_rate 46,4 vs 47,5 — down 1,1 points, inside the two-point neutral
    # band. This is the exact case NEUTRAL_BAND_POINTS was raised for: at one
    # point it drew an amber arrow on the mission's contacting for a wobble.
    assert by_key["contact_rate"]["change"]["direction"] == FLAT
    assert round(by_key["contact_rate"]["change"]["points"], 1) == -1.1
    # close_rate 9,7 vs 7,4 — up 2,3 points, through the band, and on this data
    # the ONLY one of the four that is. Which is the point of the band: the
    # mission's baptismal invitation genuinely moved, and the page should not
    # bury that under three arrows describing wobbles.
    assert by_key["close_rate"]["change"]["direction"] == UP
    assert round(by_key["close_rate"]["change"]["points"], 2) == 2.24
    # mc_rate 51,39 vs 53,36 — a 1,96-point fall. Under the band by four
    # hundredths of a point, so it reads flat. Pinned along with close_rate's
    # 2,24 because these two straddle the threshold: lower the band and mc_rate
    # is the first arrow to appear, raise it and close_rate is the first to go.
    assert by_key["mc_rate"]["change"]["direction"] == FLAT
    assert round(by_key["mc_rate"]["change"]["points"], 2) == -1.96
    # lesson_rate 16,4 vs 17,6 — 1,2 points, comfortably flat.
    assert by_key["lesson_rate"]["change"]["direction"] == FLAT
